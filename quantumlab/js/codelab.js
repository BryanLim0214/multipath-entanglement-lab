/**
 * The Code Lab: the player writes choose_paths(net, request) in Python. The code runs in the browser
 * (Pyodide in a Web Worker) through the real engine in src/qmp, and every answer goes through qmp.core.validate.
 * Three challenges compare the rule with a baseline on 10 paired seeds and report the paired difference and its 95% interval.
 */
import { h, caption, loadJson, fixed, announce, storeGet, storeSet } from "./ui.js";
import { createLadder } from "./help-ladder.js";
import { chapterHead, taskBox } from "./chapters/common.js";
import { createRuntime } from "./codelab-runtime.js";
import { alignLines } from "./codelab-diff.js";

const C1_TASK_ID = "codelab-c1";
const C2_TASK_ID = "codelab-c2";
const C3_TASK_ID = "codelab-c3";
const BADGE_KEY = "quantumlab.codelab.badges.v1";
const LIMIT_MS = 45000;
const LIMIT_TEXT = "45 seconds";
const CHALLENGES = [
  { id: "c1", taskId: C1_TASK_ID, title: "Challenge 1: beat Lazy Walker", baseline: "lazy", zeroIllegal: false,
    goal: "Block fewer requests than Lazy Walker. You win when the upper end of the 95% interval of (your blocking ratio minus Lazy Walker's) is below 0." },
  { id: "c2", taskId: C2_TASK_ID, title: "Challenge 2: beat SP-Heu with no illegal answers", baseline: "sp_heu", zeroIllegal: true,
    goal: "Block fewer requests than SP-Heu, the paper's single-path heuristic, and have the referee reject none of your answers. Same winning test as challenge 1." },
  { id: "c3", taskId: C3_TASK_ID, title: "Challenge 3: beat MP-Heu", baseline: "mp_heu", zeroIllegal: false,
    goal: "Block fewer requests than MP-Heu, the paper's multipath heuristic. Same winning test. Hint: the extension in the report is one way." },
];
const SOURCE_URLS = {
  lazy: "../py/templates/lazy_walker.py",
  splitter: "../py/templates/splitter.py",
  heuristic: "../../src/qmp/heuristic.py",
};
const textCache = new Map();

/**
 * Fetch a text file next to this script, once.
 * @param {string} relative Path relative to this file.
 * @returns {Promise<string>} The text.
 */
function loadText(relative) {
  if (!textCache.has(relative)) {
    textCache.set(relative, fetch(new URL(relative, import.meta.url)).then((response) => {
      if (!response.ok) {
        throw new Error(`Could not load ${relative} (HTTP ${response.status}).`);
      }
      return response.text();
    }));
  }
  return textCache.get(relative);
}

/**
 * A plain code editor: a textarea with a line-number gutter. Tab indents, and Escape then Tab leaves the box.
 * @param {string} label Accessible name of the textarea.
 * @returns {{element: HTMLElement, getValue: function(): string, setValue: function(string): void}} Editor handle.
 */
function createEditor(label) {
  const gutter = h("pre", { class: "gutter", "aria-hidden": "true" });
  const area = h("textarea", { class: "code", spellcheck: false, wrap: "off", "aria-label": label, autocapitalize: "off", autocomplete: "off" });
  let tabLeaves = false;
  /** Rewrite the line numbers to match the text. */
  const renumber = () => {
    const count = area.value.split("\n").length;
    gutter.textContent = Array.from({ length: count }, (_, i) => String(i + 1)).join("\n");
    gutter.scrollTop = area.scrollTop;
  };
  area.addEventListener("input", renumber);
  area.addEventListener("scroll", () => { gutter.scrollTop = area.scrollTop; });
  area.addEventListener("blur", () => { tabLeaves = false; });
  area.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      tabLeaves = true;
    } else if (event.key === "Tab" && !event.shiftKey && !tabLeaves) {
      event.preventDefault();
      area.setRangeText("    ", area.selectionStart, area.selectionEnd, "end");
      renumber();
    } else {
      tabLeaves = false;
    }
  });
  return {
    element: h("div", { class: "editor" }, gutter, area),
    getValue: () => area.value,
    /**
     * Replace the text.
     * @param {string} text New text.
     * @returns {void}
     */
    setValue(text) {
      area.value = text;
      renumber();
    },
  };
}

/**
 * Build the room.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {Promise<function(): void>} Cleanup function.
 */
async function mount(ctx) {
  const { narrative, hints } = ctx;
  const data = await loadJson("codelab.json");
  const lab = document.getElementById("view-lab");
  const stageColumn = document.querySelector(".stage-col");
  lab.classList.add("is-wide");
  stageColumn.hidden = true;

  const seeds = Array.from({ length: data.seeds }, (_, i) => i);
  const state = { challenge: 0, q: data.q_values[0], running: false, ready: false, skeletons: new Set(), previous: null };
  const editor = createEditor("Your choose_paths code");
  const status = h("p", { class: "loading", role: "status" });
  const retryButton = h("button", { class: "btn", type: "button", text: "Try again", hidden: true, onclick: () => loadRuntime(true) });
  const runButton = h("button", { class: "btn btn-primary", type: "button", text: "Run on 10 seeds", disabled: true, onclick: () => runCode() });
  const restoreButton = h("button", { class: "btn btn-small", type: "button", text: "Restore my previous code", hidden: true, onclick: () => restorePrevious() });
  const goalText = h("p", {});
  const badgeText = h("p", { class: "progress" });
  const resultHost = h("div", { "aria-live": "polite" });
  const diffHost = h("div", {});
  const viewHost = h("div", {});
  const ladderHost = h("div", {});
  const qSelect = h("select", { id: "codelab-q", onchange: () => { state.q = Number(qSelect.value); clearResults(); } },
    ...data.q_values.map((q) => h("option", { value: String(q), text: String(q) })));
  const runtime = createRuntime((text) => { status.textContent = text; });
  let ladder = null;

  /**
   * The challenge being worked on.
   * @returns {object} Challenge definition.
   */
  function current() {
    return CHALLENGES[state.challenge];
  }

  /**
   * Plain-text badge lines from localStorage.
   * @returns {void}
   */
  function renderBadges() {
    const badges = storeGet(BADGE_KEY, {});
    badgeText.textContent = `Badges: ${CHALLENGES.map((c, i) => `challenge ${i + 1} ${badges[c.id] ? "earned" : "not yet"}`).join(", ")}.`;
  }

  /**
   * Remember that a challenge was won (storage may be blocked, which storeSet handles).
   * @param {string} id Challenge id.
   * @returns {void}
   */
  function saveBadge(id) {
    const badges = storeGet(BADGE_KEY, {});
    badges[id] = true;
    storeSet(BADGE_KEY, badges);
    renderBadges();
  }

  /**
   * Start (or restart) Python in the worker and show the loading state.
   * @param {boolean} [fresh] True to throw away a failed worker first.
   * @returns {Promise<void>} Resolves when the attempt has finished.
   */
  async function loadRuntime(fresh = false) {
    if (fresh) { runtime.restart(); }
    state.ready = false;
    retryButton.hidden = true;
    runButton.disabled = true;
    status.className = "loading";
    status.textContent = "Starting Python. The first load is a large download (tens of megabytes) from cdn.jsdelivr.net, and your browser keeps it afterwards.";
    try {
      await runtime.ready();
      state.ready = true;
      status.textContent = "Python is ready. The real engine from src/qmp is loaded.";
      runButton.disabled = false;
    } catch (error) {
      status.className = "error-box";
      status.textContent = error.offline
        ? `${error.message} The Code Lab needs an internet connection the first time. Check the connection and press Try again.`
        : `Python could not start: ${error.message}`;
      retryButton.hidden = false;
    }
  }

  /**
   * Empty the result area and the diff.
   * @returns {void}
   */
  function clearResults() {
    resultHost.replaceChildren();
    diffHost.replaceChildren();
  }

  /**
   * Show a plain error where the results go.
   * @param {string} text What went wrong.
   * @returns {void}
   */
  function showError(text) {
    resultHost.replaceChildren(h("p", { class: "error-box", role: "alert", text }));
  }

  /**
   * Draw the results of one run: the per-seed table, the paired difference, the verdict and the referee's messages.
   * @param {object} r Result dict from codelab_adapter.run_challenge.
   * @returns {void}
   */
  function renderResult(r) {
    const challenge = current();
    const rows = r.seeds.map((seed, i) => h("tr", {}, h("td", { class: "num", text: String(seed) }),
      h("td", { class: "num", text: fixed(r.player[i], 3) }), h("td", { class: "num", text: fixed(r.baseline_values[i], 3) }),
      h("td", { class: "num", text: fixed(r.player[i] - r.baseline_values[i], 3) })));
    const upper = r.mean_diff + r.ci;
    const legalOk = !challenge.zeroIllegal || r.illegal === 0;
    const verdict = r.won
      ? `Win. The upper end of the interval is ${fixed(upper, 3)}, below 0${challenge.zeroIllegal ? ", and the referee rejected none of your answers" : ""}.`
      : `Not yet. ${upper < 0 ? "" : `The upper end of the interval is ${fixed(upper, 3)}, which is not below 0. `}${legalOk ? "" : `The referee rejected ${r.illegal} answers, and this challenge needs 0.`}`;
    resultHost.replaceChildren(
      h("h3", { text: `Your rule against ${r.baseline}, q = ${r.q}, ${r.seeds.length} paired seeds` }),
      h("div", { class: "table-scroll", role: "region", "aria-label": "Blocking ratio per seed", tabIndex: 0 },
        h("table", {}, h("thead", {}, h("tr", {}, h("th", { class: "num", text: "Seed" }), h("th", { class: "num", text: "Yours" }),
          h("th", { class: "num", text: r.baseline }), h("th", { class: "num", text: "Yours minus baseline" }))), h("tbody", {}, ...rows))),
      h("p", { class: "readout", text: `Paired difference ${fixed(r.mean_diff, 3)} ± ${fixed(r.ci, 3)} (95% interval)` }),
      h("p", { class: `verdict ${r.won ? "is-right" : "is-wrong"}`, text: verdict }),
      h("p", { text: `Answers served: ${r.served}. Declined with []: ${r.declined}. Rejected by the referee: ${r.illegal}.` }));
    if (r.messages.length) {
      resultHost.append(h("h3", { text: "What the referee said" }),
        h("ul", { class: "referee" }, ...r.messages.map((m) => h("li", { text: `Seed ${m.seed}, window ${m.window}: ${m.text}` }))));
    }
    if (r.printed) {
      resultHost.append(h("h3", { text: "What your code printed" }), h("pre", { class: "code-view", text: r.printed }));
    }
    announce(`${verdict} Paired difference ${fixed(r.mean_diff, 3)} plus or minus ${fixed(r.ci, 3)}.`);
    if (r.won) {
      saveBadge(challenge.id);
      ladder.solve();
    } else {
      ladder.wrong();
    }
  }

  /**
   * Run the code in the editor on the paired seeds, with a time limit.
   * @returns {Promise<void>} Resolves when the result (or the error) is on screen.
   */
  async function runCode() {
    if (state.running || !state.ready) { return; }
    const challenge = current();
    state.running = true;
    runButton.disabled = true;
    clearResults();
    status.className = "loading";
    status.textContent = `Running ${seeds.length} paired seeds at q = ${state.q}. A run is stopped after ${LIMIT_TEXT}.`;
    try {
      const result = await runtime.run({ source: editor.getValue(), baseline: challenge.baseline, q: state.q, seeds,
        nSpec: data.config.n_spec, zeroIllegal: challenge.zeroIllegal }, LIMIT_MS);
      status.textContent = "Done.";
      if (result.error) {
        showError(result.error);
      } else {
        renderResult(result);
      }
    } catch (error) {
      if (error.timeout) {
        showError(`Your code ran for more than ${LIMIT_TEXT}, so it was stopped. A loop that never ends, or a search over far too many roads, can cause this. Python is restarting.`);
        status.textContent = "Run stopped. Python is restarting.";
        await loadRuntime(true);
        return;
      }
      showError(`The run failed: ${error.message}`);
    } finally {
      state.running = false;
      runButton.disabled = !state.ready;
    }
  }

  /**
   * Put new code in the editor, remembering what was there so it can be restored.
   * @param {string} text New code.
   * @returns {void}
   */
  function replaceCode(text) {
    const old = editor.getValue();
    if (old.trim() && old !== text) {
      state.previous = old;
      restoreButton.hidden = false;
    }
    editor.setValue(text);
    clearResults();
  }

  /**
   * Bring back the code that a template or solution replaced.
   * @returns {void}
   */
  function restorePrevious() {
    if (state.previous !== null) {
      editor.setValue(state.previous);
      state.previous = null;
      restoreButton.hidden = true;
    }
  }

  /**
   * Load a template into the editor.
   * @param {string} key "lazy" or "splitter".
   * @returns {Promise<void>} Resolves when the text is in the editor.
   */
  async function useTemplate(key) {
    replaceCode(await loadText(SOURCE_URLS[key]));
    if (ladder) { ladder.progress(); }
  }

  /**
   * Show or hide the paper's heuristic.py, read only.
   * @returns {Promise<void>} Resolves when the source is shown or hidden.
   */
  async function toggleHeuristic() {
    if (viewHost.childElementCount) {
      viewHost.replaceChildren();
      return;
    }
    const text = await loadText(SOURCE_URLS.heuristic);
    const view = createEditor("The paper's heuristic, read only (src/qmp/heuristic.py)");
    view.setValue(text);
    view.element.querySelector("textarea").readOnly = true;
    viewHost.replaceChildren(h("h3", { text: "The paper's heuristic (src/qmp/heuristic.py, read only)" }), view.element);
  }

  /**
   * Level 3: add the fill-in-the-blank outline as comments after the player's code, once per challenge.
   * @returns {Promise<void>} Resolves when it is added.
   */
  async function insertSkeleton() {
    const challenge = current();
    if (state.skeletons.has(challenge.id)) { return; }
    state.skeletons.add(challenge.id);
    const skeleton = await loadText(`../py/skeletons/${challenge.id}.py`);
    editor.setValue(`${editor.getValue().replace(/\s+$/, "")}\n${skeleton}`);
  }

  /**
   * Level 4: show the player's code beside the working solution, with differing lines marked.
   * @returns {Promise<void>} Resolves when the table is on screen.
   */
  async function showDiff() {
    const solution = await loadText(`../py/solutions/${current().id}.py`);
    const rows = alignLines(editor.getValue(), solution);
    const markText = { same: "", minus: "-", plus: "+", change: "-/+" };
    const cell = (text) => h("td", { class: "code-cell", text: text === null ? "" : text });
    diffHost.replaceChildren(
      h("h3", { text: "Your code (left) and a working solution (right)" }),
      h("div", { class: "table-scroll", role: "region", "aria-label": "Your code beside the working solution", tabIndex: 0 },
        h("table", { class: "diff" }, h("thead", {}, h("tr", {}, h("th", { text: "" }), h("th", { text: "Yours" }), h("th", { text: "Solution" }))),
          h("tbody", {}, ...rows.map((row) => h("tr", { class: row.mark === "same" ? "" : "is-diff" },
            h("td", { class: "num", text: markText[row.mark] }), cell(row.left), cell(row.right)))))));
  }

  /**
   * Level 5: put the working solution in the editor and run it.
   * @returns {Promise<void>} Resolves when the run has finished.
   */
  async function insertSolutionAndRun() {
    replaceCode(await loadText(`../py/solutions/${current().id}.py`));
    await runCode();
  }

  /**
   * Switch to another challenge: new goal text, new help ladder, empty results.
   * @param {number} index Position in CHALLENGES.
   * @returns {void}
   */
  function selectChallenge(index) {
    state.challenge = index;
    state.skeletons = new Set();
    if (ladder) { ladder.dispose(); }
    const challenge = current();
    goalText.textContent = challenge.goal;
    clearResults();
    ladder = createLadder({
      taskId: challenge.taskId,
      hints,
      /** Task actions that help levels 3 to 5 call. */
      handlers: {
        highlight: (on) => { if (on) { insertSkeleton(); } },
        show: () => { showDiff(); },
        doIt: () => { insertSolutionAndRun(); },
        similar: () => {
          state.q = data.q_values[(data.q_values.indexOf(state.q) + 1) % data.q_values.length];
          qSelect.value = String(state.q);
          state.skeletons = new Set();
          clearResults();
        },
      },
    });
    ladderHost.replaceChildren(ladder.element);
  }

  const challengeBox = h("fieldset", {}, h("legend", { text: "Challenge" }),
    ...CHALLENGES.map((c, i) => h("label", { class: "choice" },
      h("input", { type: "radio", name: "codelab-challenge", value: c.id, checked: i === 0, onchange: () => selectChallenge(i) }), c.title)));

  narrative.append(
    chapterHead("Code Lab", "Write the placement rule",
      "You decide which roads each request gets. The referee is the real one from the engine, and your rule is scored against the paper's methods."),
    caption({
      kid: "You are the traffic planner. For each request you pick roads and say how many pairs go on each road. A referee checks that your answer is allowed.",
      student: "choose_paths(net, request) returns a list of (road, pairs), or [] to turn the request away. The engine asks it for each request in its own priority order and takes the seats only if the answer passes the referee.",
      expert: `The adapter in quantumlab/py/codelab_adapter.py wraps your function as a qmp placer and calls qmp.sim.simulate with the Part A setup (${data.config.rows} by ${data.config.cols} grid, |R| = ${data.config.R}, M = ${data.config.M}, T = ${data.config.T}, t_c = ${data.config.tc}, f = ${data.config.f}). The baseline sees the same seeds (A19). The paired difference uses qmp.stats.paired_diff_ci.`,
      breaks: "A rule that wins on 10 seeds can lose on other seeds or other grids. Your code runs in your browser, but the referee and the baselines are the same Python as in the experiments.",
    }),
    taskBox("Task: write a rule and beat a baseline",
      challengeBox,
      goalText,
      h("details", { class: "api" }, h("summary", { text: "What choose_paths receives" }),
        h("ul", {},
          h("li", {}, h("code", { text: "net.neighbors(u)" }), ": cities next to u over a link with a free seat, in increasing order."),
          h("li", {}, h("code", { text: "net.pairs(u, v)" }), ": free seats on the link u-v right now, after the requests already placed in this window."),
          h("li", {}, h("code", { text: "net.max_middle" }), ": most middle cities a road may have (the fidelity limit, A5)."),
          h("li", {}, h("code", { text: "net.spare" }), ": 2. The paper's methods keep one spare seat per pair, so a request uses at most seats // net.spare of a link. That is a strategy, and the referee does not require it."),
          h("li", {}, h("code", { text: "request.src, request.dst, request.n" }), ": where it starts, where it ends, how many pairs."),
          h("li", {}, h("code", { text: "request.last_chance" }), ": True if this window is the last one where the request can still run."),
          h("li", {}, "Return a list of (road, pairs), where road is a list of cities from request.src to request.dst. Return [] to decline."))),
      h("div", { class: "btn-row" },
        h("button", { class: "btn", type: "button", text: "Load Lazy Walker", onclick: () => useTemplate("lazy") }),
        h("button", { class: "btn", type: "button", text: "Load Splitter (with a TODO)", onclick: () => useTemplate("splitter") }),
        h("button", { class: "btn", type: "button", text: "Show or hide the paper's heuristic", onclick: () => toggleHeuristic() }),
        restoreButton),
      viewHost,
      editor.element,
      h("p", { class: "small muted", text: "Tab indents. To leave the box with the keyboard, press Escape and then Tab." }),
      h("div", { class: "field" }, h("label", { for: "codelab-q", text: "q (chance a plane lands)" }), qSelect),
      h("div", { class: "btn-row" }, runButton, retryButton),
      h("p", { class: "small", text: "Each run uses 10 paired seeds, not 30, because the code runs in your browser and 30 would be too slow. Fewer seeds make the interval wider, so a win is a little harder to show." }),
      status,
      resultHost,
      diffHost,
      badgeText,
      ladderHost));

  renderBadges();
  selectChallenge(0);
  loadText(SOURCE_URLS.lazy).then((text) => editor.setValue(text));
  loadRuntime();
  return () => {
    runtime.dispose();
    if (ladder) { ladder.dispose(); }
    lab.classList.remove("is-wide");
    stageColumn.hidden = false;
  };
}

export default { id: "codelab", title: "Code Lab", mount };

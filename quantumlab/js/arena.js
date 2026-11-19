/**
 * The Arena: a single-path network and a multipath network replay the same real trace side by side.
 * The viewer scrubs through the windows, switches off a rule on the multipath side, and clicks a request
 * to read what happened to it. All numbers come from data/arena.json, written by tools/export_data.py.
 */
import { h, caption, predictBox, loadJson, fixed, announce, motionReduced } from "./ui.js";
import { createLadder } from "./help-ladder.js";
import { chapterHead, taskBox, outliner } from "./chapters/common.js";
import {
  rightTraceName, leftTraceName, gridLinks, requestMap, computeFates, statusAt, isBlocked, isTurnedAway,
  countersAt, windowSeats, fateChanges, findRightWins,
} from "./arena-model.js";
import { sideStory, requestCaption } from "./arena-story.js";

const FIND_TASK_ID = "arena-find";
const ABLATE_TASK_ID = "arena-ablate";
const SPACING = 2.4; // scene units between neighbouring cities
const PLAY_GAP_MS = 600; // rest between two windows while playing, after the animation of the first has finished
const PLAY_STEP_REDUCED_MS = 1400; // with reduced motion there is no animation, so each window stays this long
const STATUS_TEXT = {
  "served-now": "served now", "served-earlier": "served earlier", "turned-away": "turned away, may retry",
  "blocked-now": "blocked (last chance)", "blocked-earlier": "blocked earlier", "not-open": "not open yet",
  "never-fits": "blocked (never fits)",
};

/**
 * Where a city sits in the scene.
 * @param {number} city City id from 1 to 9.
 * @param {boolean} isRight True for the multipath network.
 * @param {boolean} stacked True on a narrow screen, where the networks sit one above the other.
 * @returns {{x: number, y: number}} Scene position.
 */
function cityPosition(city, isRight, stacked) {
  const col = (city - 1) % 3;
  const row = Math.floor((city - 1) / 3);
  const shift = isRight ? 1 : -1;
  return {
    x: (col - 1) * SPACING + (stacked ? 0 : shift * 3.7),
    y: (1 - row) * SPACING + (stacked ? -shift * 3.9 : 0),
  };
}

/**
 * Build the room.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {Promise<function(): void>} Cleanup function.
 */
async function mount(ctx) {
  const { narrative, extra, stage, hints } = ctx;
  const data = await loadJson("arena.json");
  const config = data.config;
  const lastWindow = Math.ceil(config.T / config.tc) - 1;
  const links = gridLinks(config.rows, config.cols);
  const lab = document.getElementById("view-lab");
  const narrowQuery = window.matchMedia("(max-width: 760px)");
  const state = { q: 0.5, seed: 0, pair: "Heu", rules: { split: true, spare: true, hop: true }, w: 0,
    selected: null, onlyDiff: false, hintOn: false,
    playing: false, playId: 0, timer: null, wake: null, animating: false };
  let seqToken = 0; // each window animation takes a number; a newer one, or any redraw, makes the older one stop
  const fateCache = new Map();
  let ladderA = null;
  let ladderB = null;

  lab.classList.add("is-arena");

  // ---- controls ---------------------------------------------------------------------------
  const qSelect = h("select", { id: "arena-q", onchange: () => { state.q = Number(qSelect.value); restart(); } },
    ...data.q_values.map((q) => h("option", { value: String(q), text: String(q) })));
  const seedSelect = h("select", { id: "arena-seed", onchange: () => { state.seed = Number(seedSelect.value); restart(); } },
    ...data.seeds.map((s) => h("option", { value: String(s), text: String(s) })));
  const pairSelect = h("select", { id: "arena-pair", onchange: () => { state.pair = pairSelect.value; restart(); } },
    h("option", { value: "Heu", text: "Heuristics (SP-Heu and MP-Heu)" }),
    h("option", { value: "ILP", text: "Exact solver (SP-ILP and MP-ILP)" }));
  const ruleBoxes = {};
  /** One rule switch with its label. @param {string} key Rule key. @param {string} label Text beside the box. @returns {HTMLElement} The label element. */
  const ruleRow = (key, label) => {
    ruleBoxes[key] = h("input", { type: "checkbox", id: `arena-rule-${key}`, checked: true, onchange: () => onRule(key) });
    return h("label", { class: "choice" }, ruleBoxes[key], label);
  };
  const rulesBox = h("fieldset", {},
    h("legend", { text: "Rules on the multipath side" }),
    ruleRow("spare", "Spare-seat rule (δ = 2)"),
    ruleRow("split", "Splitting over several roads"),
    ruleRow("hop", "Hop limit (middle cities)"),
    h("p", { class: "small muted", id: "arena-rules-note", text: "Each switch replays the matching precomputed run of the heuristic." }));
  const onlyDiffBox = h("input", { type: "checkbox", id: "arena-only-diff", onchange: () => { state.onlyDiff = onlyDiffBox.checked; if (ladderA) { ladderA.progress(); } renderTable(); } });
  const onlyDiffLabel = h("label", {}, onlyDiffBox, "Show only requests where the two sides differ in this window");
  const guess = predictBox({
    name: "arena-guess",
    legend: "if you turn one rule off, will the multipath side serve more, fewer or the same number of requests at the end?",
    options: [["more", "More"], ["fewer", "Fewer"], ["same", "The same number"]].map(([value, label]) => ({ value, label })),
  });

  // ---- scrubber and counters (under the picture) --------------------------------------------
  const windowLabel = h("p", { class: "readout", id: "arena-window" });
  const slider = h("input", { type: "range", id: "arena-slider", min: 1, max: lastWindow + 1, step: 1, value: 1,
    "aria-label": "Window", oninput: () => { stopPlay(); setWindow(Number(slider.value) - 1); } });
  const backButton = h("button", { class: "btn btn-small", type: "button", text: "Back one window", onclick: () => { stopPlay(); setWindow(state.w - 1); } });
  const stepButton = h("button", { class: "btn btn-small", type: "button", text: "Next window", onclick: () => { stopPlay(); setWindow(state.w + 1, true); } });
  const playButton = h("button", { class: "btn btn-small btn-primary", type: "button", text: "Play", "aria-pressed": "false", onclick: () => togglePlay() });
  const counterHead = [h("th", { text: "" }), h("th", { class: "num" }), h("th", { class: "num" })];
  const counterCells = ["served", "blocked", "waiting", "ratio"].map(() => [h("td", { class: "num" }), h("td", { class: "num" })]);
  const counterTable = h("table", { "aria-label": "Counters after the current window" },
    h("thead", {}, h("tr", {}, ...counterHead)),
    h("tbody", {}, ...["Served", "Blocked", "Still waiting", "Blocking ratio"].map((name, i) => h("tr", {}, h("th", { scope: "row", text: name }), ...counterCells[i]))));

  // ---- request table, story, changes -----------------------------------------------------------
  const tableHost = h("div", { class: "table-scroll scroll-y", role: "region", "aria-label": "Requests waiting in this window", tabIndex: 0 });
  const storyHost = h("div", { "aria-live": "polite" });
  const changesHost = h("div", { "aria-live": "polite" });
  const statusLine = h("p", { class: "small", role: "status" });
  const hostA = h("div", {});
  const hostB = h("div", {});
  const startB = h("button", { class: "btn", type: "button", text: "Start task 2 and its help", onclick: () => startTaskB() });

  /**
   * The run being replayed.
   * @returns {object} Run from arena.json for the chosen q and seed.
   */
  function run() {
    return data.runs[`${state.q}/${state.seed}`];
  }

  /**
   * The two traces on screen.
   * @returns {{left: {name: string, trace: object}, right: {name: string, trace: object}}} Names and traces.
   */
  function traces() {
    const leftName = leftTraceName(state.pair);
    const rightName = rightTraceName(state.pair, state.rules);
    return { left: { name: leftName, trace: run().traces[leftName] }, right: { name: rightName, trace: run().traces[rightName] } };
  }

  /**
   * Fates of every request in a trace, cached.
   * @param {string} name Trace name.
   * @returns {Map<number, object>} Fates by request id.
   */
  function fatesOf(name) {
    const key = `${state.q}/${state.seed}/${name}`;
    if (!fateCache.has(key)) {
      fateCache.set(key, computeFates(run(), run().traces[name]));
    }
    return fateCache.get(key);
  }

  /**
   * Both sides' names, traces, fates, and counters for the current window.
   * @returns {object[]} Two side records, left then right.
   */
  function sides() {
    const t = traces();
    return [["Single-path", "The single-path plan", t.left, "sp"], ["Multipath", "The multipath plan", t.right, "mp"]].map(([name, kidName, side, color]) => ({
      name, kidName, color, traceName: side.name, trace: side.trace, fates: fatesOf(side.name),
      counts: countersAt(fatesOf(side.name), state.w),
    }));
  }

  // ---- drawing -----------------------------------------------------------------------------
  /**
   * Draw both networks for the current window.
   * @param {boolean} [animate] True to change smoothly from the picture on screen (seats grow or shrink, pairs come and go).
   * @param {boolean} [refill] True to draw the window with every seat free and no pair placed, as at the start of a round.
   * @returns {Promise<void>} Resolves when the change has finished.
   */
  function drawStage(animate = false, refill = false) {
    const stacked = narrowQuery.matches;
    const reqs = requestMap(run());
    const picked = state.selected === null ? null : reqs.get(state.selected);
    const nodes = [];
    const stageLinks = [];
    const captions = [];
    sides().forEach((side, index) => {
      const prefix = index === 0 ? "L" : "R";
      const seats = windowSeats(run(), side.trace, state.w);
      const status = picked ? statusAt(side.fates.get(picked.id), state.w) : null;
      for (let city = 1; city <= config.rows * config.cols; city += 1) {
        const isEnd = picked && (city === picked.s || city === picked.d);
        const roleText = picked && city === picked.s ? "S" : picked && city === picked.d ? "E" : ""; // S = start, E = end
        nodes.push({ id: `${prefix}${city}`, ...cityPosition(city, index === 1, stacked), label: `${roleText}${city}`, onNode: true,
          color: isEnd ? (isBlocked(status) || isTurnedAway(status) ? "fail" : side.color) : "ink", picked: Boolean(isEnd) });
      }
      links.forEach(([a, b]) => {
        const key = `${a}-${b}`;
        stageLinks.push({ from: `${prefix}${a}`, to: `${prefix}${b}`, seats: 0.5, color: "rule" });
        const free = refill ? seats.cap.get(key) : seats.left.get(key);
        stageLinks.push({ from: `${prefix}${a}`, to: `${prefix}${b}`, seats: free, color: "muted",
          beads: refill ? 0 : seats.used.get(key), beadColor: side.color, label: `${free}/${seats.cap.get(key)}`,
          small: true, labelShift: b - a === config.cols ? { x: 0.6, y: 0 } : { x: 0, y: 0.5 } }); // one side only: right of vertical links, above horizontal ones
      });
      if (status === "served-now" && !refill) {
        side.fates.get(picked.id).alloc.paths.forEach((road) => road.nodes.slice(0, -1).forEach((u, i) => {
          stageLinks.push({ from: `${prefix}${u}`, to: `${prefix}${road.nodes[i + 1]}`, key: `pick|${prefix}${u}|${road.nodes[i + 1]}`, seats: road.pairs, color: "ink", lift: 0.7 });
        }));
      }
      const mid = cityPosition(2, index === 1, stacked);
      captions.push({ x: mid.x, y: mid.y + 1.5, text: `${side.name} (${side.traceName})` });
    });
    const done = stage.show({ nodes, links: stageLinks, captions, pad: 1.9, view: "top" }, { animate });
    const [left, right] = sides();
    stage.setAlt(`Two grids of 9 cities. Left, single-path: ${left.counts.served} served and ${left.counts.blocked} blocked so far. `
      + `Right, multipath: ${right.counts.served} served and ${right.counts.blocked} blocked so far. Window ${state.w + 1} of ${lastWindow + 1}. `
      + "Thicker tubes have more seats left, and beads are pairs placed in this window.");
    return done;
  }

  /**
   * Update the window label, slider and counters.
   * @returns {void}
   */
  function renderControls() {
    const first = state.w * config.tc + 1;
    windowLabel.textContent = `Window ${state.w + 1} of ${lastWindow + 1} (slots ${first} to ${Math.min((state.w + 1) * config.tc, config.T)})`;
    slider.value = String(state.w + 1);
    backButton.disabled = state.w === 0 || state.animating;
    stepButton.disabled = state.w === lastWindow || state.animating;
    slider.disabled = state.animating;
    playButton.disabled = state.animating && !state.playing; // while playing, the button must stay free to pause
    const [left, right] = sides();
    counterHead[1].textContent = left.traceName;
    counterHead[2].textContent = right.traceName;
    [left, right].forEach((side, col) => {
      const values = [side.counts.served, side.counts.blocked, side.counts.waiting, fixed(side.counts.ratio, 3)];
      values.forEach((value, row) => { counterCells[row][col].textContent = String(value); });
    });
  }

  /**
   * One text cell for a request status, marked as blocked when it is.
   * @param {string} status A status from statusAt.
   * @returns {HTMLElement} The table cell.
   */
  function statusCell(status) {
    return h("td", { class: isBlocked(status) ? "is-blocked" : "", text: STATUS_TEXT[status] });
  }

  /**
   * Rebuild the table of requests that matter in this window: served now, turned away now, or blocked earlier.
   * @returns {void}
   */
  function renderTable() {
    const [left, right] = sides();
    const reqs = requestMap(run());
    const rows = [];
    for (const [id, req] of reqs) {
      const a = statusAt(left.fates.get(id), state.w);
      const b = statusAt(right.fates.get(id), state.w);
      const active = [a, b].some((s) => s === "served-now" || isTurnedAway(s) || s === "blocked-earlier" || s === "never-fits");
      const differs = (a === "served-now") !== (b === "served-now");
      if (active && (!state.onlyDiff || differs)) {
        rows.push(h("tr", { class: id === state.selected ? "is-selected" : "" },
          h("td", {}, h("button", { class: "btn btn-small", type: "button", "aria-pressed": String(id === state.selected),
            "aria-label": `Request ${id}, city ${req.s} to city ${req.d}. Show its story.`, text: String(id), onclick: () => selectRequest(id) })),
          h("td", { class: "num", text: `${req.s} to ${req.d}` }),
          h("td", { class: "num", text: String(req.n) }),
          statusCell(a), statusCell(b)));
      }
    }
    tableHost.replaceChildren(rows.length
      ? h("table", {}, h("thead", {}, h("tr", {}, h("th", { text: "Request" }), h("th", { text: "Cities" }), h("th", { class: "num", text: "Pairs" }),
        h("th", { text: left.traceName }), h("th", { text: right.traceName }))), h("tbody", {}, ...rows))
      : h("p", { class: "muted", text: state.onlyDiff ? "No request differs between the two sides in this window." : "No request is waiting or blocked in this window." }));
  }

  /**
   * Show the story of the selected request, or a hint to pick one.
   * @returns {void}
   */
  function renderStory() {
    if (state.selected === null) {
      storyHost.replaceChildren(h("p", { class: "muted", text: "Click a request number in the table to read what happened to it." }));
      return;
    }
    const req = requestMap(run()).get(state.selected);
    const parts = sides().map((side) => ({ name: side.name, kidName: side.kidName,
      story: sideStory({ run: run(), trace: side.trace, traceName: side.traceName, config, fates: side.fates, id: req.id }) }));
    storyHost.replaceChildren(h("h3", { text: `Request ${req.id}: why did each side do this?` }), caption(requestCaption(req, parts)));
  }

  /**
   * Show how the multipath side differs from "all rules on", or say why the switches are fixed.
   * @returns {void}
   */
  function renderChanges() {
    const exact = state.pair === "ILP";
    Object.values(ruleBoxes).forEach((box) => { box.disabled = exact; });
    document.getElementById("arena-rules-note").textContent = exact
      ? "The rules are fixed for the exact solver. Pick the heuristics to use the switches."
      : "Each switch replays the matching precomputed run of the heuristic.";
    const rules = state.rules;
    if (exact || (rules.split && rules.spare && rules.hop)) {
      changesHost.replaceChildren();
      return;
    }
    const base = run().traces["MP-Heu"];
    const now = traces().right.trace;
    const change = fateChanges(base, now);
    /** A line of request buttons, or "none". @param {number[]} ids Request ids. @param {string} kind Line title. @returns {HTMLElement} The paragraph. */
    const list = (ids, kind) => (ids.length
      ? h("p", {}, `${kind}: `, ...ids.flatMap((id) => [h("button", { class: "btn btn-small", type: "button", text: String(id), onclick: () => selectRequest(id, kind === "Newly served") }), " "]))
      : h("p", { text: `${kind}: none.` }));
    changesHost.replaceChildren(
      h("h3", { text: "What changed compared with all rules on" }),
      h("p", { text: `Blocking ratio ${fixed(base.blocking_ratio, 3)} with all rules on, ${fixed(now.blocking_ratio, 3)} now (${traces().right.name}).` }),
      list(change.newlyServed, "Newly served"), list(change.newlyBlocked, "Newly blocked"));
  }

  /**
   * Update the text parts that depend on the window: controls, request table, story and rule changes.
   * @returns {void}
   */
  function refreshText() {
    renderControls();
    renderTable();
    renderStory();
    renderChanges();
  }

  /**
   * Stop a window animation that is running, so a redraw can take over cleanly.
   * @returns {void}
   */
  function cancelSequence() {
    seqToken += 1;
    state.animating = false;
  }

  /**
   * Redraw everything that depends on the window, the run or the rules, at once and without animation.
   * @returns {void}
   */
  function refreshAll() {
    cancelSequence();
    refreshText();
    drawStage();
  }

  // ---- actions -----------------------------------------------------------------------------
  /**
   * Total pairs placed on all links of both networks in a window (zero means nothing is used up).
   * @param {number} w Window index from 0.
   * @returns {number} Pairs placed.
   */
  function pairsPlaced(w) {
    return sides().reduce((sum, side) => sum + side.trace.windows[w].allocations
      .reduce((n, alloc) => n + alloc.paths.reduce((m, road) => m + road.pairs, 0), 0), 0);
  }

  /**
   * Animate one step forward: the seats refill for the new round, a bead runs each road of every request served
   * in this window (both networks at once) while a red ring marks each request blocked for good, and the seats
   * then shrink to what is left. Stops quietly if a redraw or a newer step takes over.
   * @returns {Promise<void>} Resolves when the picture shows the window, or when the sequence was stopped.
   */
  async function runWindowSequence() {
    cancelSequence();
    const token = seqToken;
    state.animating = true;
    renderControls();
    if (pairsPlaced(state.w - 1) > 0) {
      await drawStage(true, true); // new round: the seats are free again
    }
    if (token !== seqToken) { return; }
    const moves = [];
    const reqs = requestMap(run());
    sides().forEach((side, index) => {
      const prefix = index === 0 ? "L" : "R";
      side.trace.windows[state.w].allocations.forEach((alloc) => alloc.paths.forEach((road) => {
        moves.push(stage.travel(road.nodes.map((city) => `${prefix}${city}`), { color: side.color })); // a served pair crosses its road
      }));
      for (const [id, req] of reqs) {
        if (statusAt(side.fates.get(id), state.w) === "blocked-now") {
          moves.push(stage.ring(`${prefix}${req.s}`, "fail")); // blocked for good: red ring at its start city
        }
      }
    });
    await Promise.all(moves);
    if (token !== seqToken) { return; }
    await drawStage(true); // the used seats shrink
    if (token === seqToken) {
      state.animating = false;
      renderControls();
    }
  }

  /**
   * Move to a window.
   * @param {number} w Window index from 0, clamped to the valid range.
   * @param {boolean} [withSequence] True for a single step forward, which plays the full animation; any other jump only changes the seats smoothly.
   * @returns {Promise<void>} Resolves when the picture has finished changing.
   */
  function setWindow(w, withSequence = false) {
    const from = state.w;
    state.w = Math.min(lastWindow, Math.max(0, w));
    cancelSequence();
    if (ladderA) { ladderA.progress(); }
    refreshText();
    const [left, right] = sides();
    announce(`Window ${state.w + 1}. Single-path: ${left.counts.served} served, ${left.counts.blocked} blocked. Multipath: ${right.counts.served} served, ${right.counts.blocked} blocked.`);
    return withSequence && state.w === from + 1 ? runWindowSequence() : drawStage(true);
  }

  /**
   * Wait between two windows while playing. Pausing wakes the wait at once.
   * @param {number} ms Wait in milliseconds.
   * @returns {Promise<void>} Resolves after the wait or when play is stopped.
   */
  function rest(ms) {
    return new Promise((resolve) => {
      state.wake = resolve;
      state.timer = window.setTimeout(() => { state.wake = null; resolve(); }, ms);
    });
  }

  /**
   * Play: step forward one animated window at a time. The next step starts only after the last one has finished
   * and rested, so frames never pile up.
   * @returns {Promise<void>} Resolves when play ends.
   */
  async function playLoop() {
    const id = state.playId;
    while (state.playing && id === state.playId && state.w < lastWindow) {
      await setWindow(state.w + 1, true);
      if (!state.playing || id !== state.playId) { return; }
      await rest(motionReduced() ? PLAY_STEP_REDUCED_MS : PLAY_GAP_MS);
    }
    if (id === state.playId) { stopPlay(); }
  }

  /**
   * Start or stop the automatic stepping.
   * @returns {Promise<void>} Resolves when play ends (or at once when it was stopped).
   */
  async function togglePlay() {
    if (state.playing) {
      stopPlay();
      return;
    }
    if (state.animating) { return; }
    state.playing = true;
    state.playId += 1;
    playButton.textContent = "Pause";
    playButton.setAttribute("aria-pressed", "true");
    if (state.w === lastWindow) { await setWindow(0); }
    await playLoop();
  }

  /**
   * Stop the automatic stepping (a window animation that is running finishes on its own).
   * @returns {void}
   */
  function stopPlay() {
    state.playing = false;
    state.playId += 1;
    window.clearTimeout(state.timer);
    if (state.wake) {
      state.wake();
      state.wake = null;
    }
    playButton.textContent = "Play";
    playButton.setAttribute("aria-pressed", "false");
    playButton.disabled = state.animating && !state.playing;
  }

  /**
   * A new q, seed or pair: go back to window 1 with nothing selected.
   * @returns {void}
   */
  function restart() {
    stopPlay();
    state.w = 0;
    state.selected = null;
    if (ladderA) { ladderA.progress(); }
    refreshAll();
  }

  /**
   * Select a request, optionally jumping to the window where the multipath side placed it, and finish task 1 if it fits.
   * @param {number} id Request id.
   * @param {boolean} [jumpToServed] True to move to the window where the right side served it.
   * @returns {void}
   */
  function selectRequest(id, jumpToServed = false) {
    const right = fatesOf(traces().right.name).get(id);
    if (jumpToServed && right.servedWindow !== null) {
      state.w = right.servedWindow;
    }
    state.selected = id;
    refreshAll();
    const [left, rightSide] = sides();
    const found = statusAt(rightSide.fates.get(id), state.w) === "served-now" && isTurnedAway(statusAt(left.fates.get(id), state.w));
    if (found && ladderA) {
      statusLine.textContent = `Found one: in window ${state.w + 1} the multipath side served request ${id} and the single-path side turned it away.`;
      ladderA.solve();
      startTaskB();
    } else if (ladderA) {
      ladderA.progress();
    }
  }

  /**
   * The rule switches. Turning a rule off with a guess made shows whether the guess was right.
   * @param {string} key "spare", "split" or "hop".
   * @returns {void}
   */
  function onRule(key) {
    const before = traces().right.trace;
    const servedBefore = config.R - Math.round(before.blocking_ratio * config.R);
    state.rules[key] = ruleBoxes[key].checked;
    refreshAll();
    const after = traces().right.trace;
    const servedAfter = config.R - Math.round(after.blocking_ratio * config.R);
    if (ruleBoxes[key].checked || !guess.ready()) {
      return;
    }
    const actual = servedAfter > servedBefore ? "more" : servedAfter < servedBefore ? "fewer" : "same";
    const right = guess.value() === actual;
    guess.reveal(actual, `By the end the multipath side served ${servedBefore} before and ${servedAfter} after, out of ${config.R}.`);
    guess.clearChoice();
    if (ladderB) { if (right) { ladderB.solve(); } else { ladderB.wrong(); } }
  }

  /**
   * Find the first run, starting from the current one, where the right side serves a request the left turns away.
   * @returns {{q: number, seed: number, w: number, id: number}|null} Where to look, or null.
   */
  function searchAcrossRuns() {
    const all = data.q_values.flatMap((q) => data.seeds.map((seed) => ({ q, seed })));
    const start = all.findIndex((r) => r.q === state.q && r.seed === state.seed);
    for (let k = 0; k < all.length; k += 1) {
      const { q, seed } = all[(start + k) % all.length];
      const r = data.runs[`${q}/${seed}`];
      const name = traceNamesFor(state.pair);
      const win = findRightWins(computeFates(r, r.traces[name.left]), computeFates(r, r.traces[name.right]), k === 0 ? state.w : 0, lastWindow + 1);
      if (win) { return { q, seed, ...win }; }
    }
    return null;
  }

  /**
   * Trace names for the two sides with the rules on (used by the search, which looks at the full plans).
   * @param {string} pair "Heu" or "ILP".
   * @returns {{left: string, right: string}} Names.
   */
  function traceNamesFor(pair) {
    return { left: leftTraceName(pair), right: rightTraceName(pair, { split: true, spare: true, hop: true }) };
  }

  /**
   * Show me and Do it for me for task 1: put every control where the answer is visible.
   * @returns {void}
   */
  function showTheAnswer() {
    const target = searchAcrossRuns();
    if (!target) {
      statusLine.textContent = "No window in these runs has a request that only the multipath side serves.";
      return;
    }
    stopPlay();
    state.q = target.q;
    state.seed = target.seed;
    state.rules = { split: true, spare: true, hop: true };
    Object.values(ruleBoxes).forEach((box) => { box.checked = true; });
    qSelect.value = String(target.q);
    seedSelect.value = String(target.seed);
    onlyDiffBox.checked = true;
    state.onlyDiff = true;
    state.w = target.w;
    state.selected = target.id;
    refreshAll();
    statusLine.textContent = `Window ${target.w + 1} of the run with q = ${target.q} and seed ${target.seed}: request ${target.id} is served on the right and turned away on the left.`;
  }

  /**
   * Begin task 2 and its help ladder, and hand the H key to it.
   * @returns {void}
   */
  function startTaskB() {
    if (ladderB) { return; }
    ladderA.dispose();
    ladderA = null;
    startB.hidden = true;
    ladderB = createLadder({
      taskId: ABLATE_TASK_ID,
      hints,
      /** Task actions that help levels 3 to 5 call. */
      handlers: {
        highlight: (on) => { rulesBox.classList.toggle("hint-target", on); },
        show: () => { putRuleOff(); },
        doIt: () => { putRuleOff(); },
        similar: () => { nextRun(); },
      },
    });
    hostB.replaceChildren(ladderB.element);
  }

  /**
   * Turn the spare-seat rule off (task 2's answer), at a q where the heuristic pair is on screen.
   * @returns {void}
   */
  function putRuleOff() {
    state.pair = "Heu";
    pairSelect.value = "Heu";
    state.rules.spare = false;
    ruleBoxes.spare.checked = false;
    state.w = lastWindow;
    refreshAll();
  }

  /**
   * Move to the next (q, seed) run with every rule back on, for "Try a similar one".
   * @returns {void}
   */
  function nextRun() {
    const all = data.q_values.flatMap((q) => data.seeds.map((seed) => ({ q, seed })));
    const at = all.findIndex((r) => r.q === state.q && r.seed === state.seed);
    const next = all[(at + 1) % all.length];
    state.q = next.q;
    state.seed = next.seed;
    qSelect.value = String(next.q);
    seedSelect.value = String(next.seed);
    state.rules = { split: true, spare: true, hop: true };
    Object.values(ruleBoxes).forEach((box) => { box.checked = true; });
    state.onlyDiff = false;
    onlyDiffBox.checked = false;
    guess.reset();
    restart();
  }

  ladderA = createLadder({
    taskId: FIND_TASK_ID,
    hints,
    /** Task actions that help levels 3 to 5 call. */
    handlers: {
      highlight: outliner([onlyDiffLabel]),
      show: () => { showTheAnswer(); },
      doIt: () => { showTheAnswer(); startTaskB(); },
      similar: () => { nextRun(); },
    },
  });
  hostA.append(ladderA.element);

  narrative.append(
    chapterHead("Arena", "Same requests, two plans",
      "Both networks get the same requests and the same seats in every window. The left plan puts each request on one road. The right plan may split it over roads that share no link."),
    caption({
      kid: "Two towns get exactly the same requests and the same planes. One town sends every request down one road. The other may share a request between two roads.",
      student: "Each window is one round of seat sampling. Tube thickness is the seats left in that window, and beads are pairs placed in it. A blocked request found no legal road with enough seats before its deadline.",
      expert: "The replay shows the traces of qmp.sim for 60 requests on a 3 by 3 grid, 100 slots, windows of 10 slots (Alg. 1). Both sides share requests and link outcomes per seed (A19). The spare-seat rule keeps floor(seats / delta) per request and link (A21).",
      breaks: "These are three seeds of one setup. The 30-seed averages are in chapter 6, and the replay of one seed can differ from the average.",
    }),
    taskBox("Task 1: find a window where multipath serves a request that single-path turns away",
      h("div", { class: "arena-pickers" },
        h("div", { class: "field" }, h("label", { for: "arena-q", text: "q (chance a plane lands)" }), qSelect),
        h("div", { class: "field" }, h("label", { for: "arena-seed", text: "Seed" }), seedSelect),
        h("div", { class: "field" }, h("label", { for: "arena-pair", text: "Pair of plans" }), pairSelect)),
      h("p", {}, "Use the slider under the picture to move through the windows. In the table, click a request to read its story."),
      h("div", { class: "field" }, onlyDiffLabel),
      statusLine,
      tableHost,
      storyHost,
      hostA),
    taskBox("Task 2: turn one rule off and predict the change first",
      guess.element,
      rulesBox,
      changesHost,
      h("div", { class: "btn-row" }, startB),
      hostB));
  extra.append(h("div", { class: "arena-controls" },
    windowLabel, slider, h("div", { class: "btn-row" }, backButton, playButton, stepButton), counterTable,
    h("p", { class: "stage-hint", text: "Tube thickness is seats left. Beads are pairs placed in this window. Labels show seats left over seats this round. S marks the start and E the end of the selected request. A red city belongs to a request that was turned away." })));

  /** Redraw when the screen crosses the narrow-layout width. */
  const onResize = () => drawStage();
  narrowQuery.addEventListener("change", onResize);
  refreshAll();
  return () => {
    stopPlay();
    narrowQuery.removeEventListener("change", onResize);
    cancelSequence();
    lab.classList.remove("is-arena");
    if (ladderA) { ladderA.dispose(); }
    if (ladderB) { ladderB.dispose(); }
  };
}

export default { id: "arena", title: "Arena", mount };

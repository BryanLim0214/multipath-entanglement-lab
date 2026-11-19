/**
 * Chapter 1, "Two questions": two coins in two cities, each with a question dial (Z or X).
 * The viewer predicts, flips 20 times, and reads a results table with correct Bell-pair statistics.
 */
import { h, caption, predictBox } from "../ui.js";
import { seededRandom } from "../math.js";
import { createLadder } from "../help-ladder.js";
import { chapterHead, taskBox, outliner, createLock } from "./common.js";

const FLIPS = 20;
const TASK_ID = "ch1-coins";

/**
 * One flip of a |Phi+> pair: same dial gives equal results, different dials give independent 50/50 results.
 * @param {function(): number} random Random source.
 * @param {string} dial1 City 1 dial, "Z" or "X".
 * @param {string} dial2 City 2 dial, "Z" or "X".
 * @returns {number[]} The two results, each 0 or 1.
 */
export function flipPair(random, dial1, dial2) {
  const first = random() < 0.5 ? 0 : 1;
  const second = dial1 === dial2 ? first : (random() < 0.5 ? 0 : 1);
  return [first, second];
}

/**
 * Color token for a result bit.
 * @param {number|null} bit 0, 1, or null before any flip.
 * @returns {string} Color token name.
 */
function bitColor(bit) {
  return bit === null ? "muted" : bit === 1 ? "mp" : "ink";
}

/**
 * Build the chapter.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {function(): void} Cleanup function.
 */
function mount(ctx) {
  const { narrative, stage, hints } = ctx;
  const state = { runs: [], seed: 100, sameDone: false, mixedDone: false };

  const dial1 = h("select", { id: "dial1" }, h("option", { value: "Z", text: "Z" }), h("option", { value: "X", text: "X" }));
  const dial2 = h("select", { id: "dial2" }, h("option", { value: "Z", text: "Z" }), h("option", { value: "X", text: "X" }));
  const flipButton = h("button", { class: "btn btn-primary", type: "button", text: `Flip ${FLIPS} times`, disabled: true });
  const guess = predictBox({
    name: "ch1-guess",
    legend: "out of 20 flips, how many times will the two coins agree?",
    options: [{ value: "all", label: "All 20" }, { value: "half", label: "About 10" }, { value: "none", label: "None" }],
    onChange: () => { updateButtons(); },
  });
  const lock = createLock(() => updateButtons());
  const flipsHost = h("div", { class: "table-scroll", role: "region", "aria-label": "Results of the latest 20 flips", tabIndex: 0 });
  const summaryHost = h("div", {});
  const ladder = createLadder({
    taskId: TASK_ID,
    hints,
    /** Task actions that help levels 3 to 5 call. */
    handlers: {
      highlight: outliner([dial1, dial2]),
      show: () => { runBoth(); },
      doIt: () => { runBoth(); },
      similar: () => {
        if (lock.busy) { return; }
        state.runs = []; state.sameDone = false; state.mixedDone = false; state.seed += 50; renderTables(); drawStage(null);
      },
    },
  });

  /**
   * Enable or disable the flip button and the dials: nothing can be pressed while an animation runs.
   * @returns {void}
   */
  function updateButtons() {
    flipButton.disabled = !guess.ready() || lock.busy;
    dial1.disabled = lock.busy;
    dial2.disabled = lock.busy;
  }

  /**
   * Draw the two cities, colored by the last flip's results.
   * @param {number[]|null} last Last flip results, or null before any flip.
   * @param {boolean} [animate] True to change from the old colors to the new ones smoothly.
   * @returns {Promise<void>} Resolves when the colors have changed.
   */
  function drawStage(last, animate = false) {
    const bits = last || [null, null];
    const shown = stage.show({
      nodes: [
        { id: 1, x: -3, y: 0, color: bitColor(bits[0]), label: `City 1, dial ${dial1.value}${last ? `: ${bits[0]}` : ""}` },
        { id: 2, x: 3, y: 0, color: bitColor(bits[1]), label: `City 2, dial ${dial2.value}${last ? `: ${bits[1]}` : ""}` },
      ],
      links: [{ from: 1, to: 2, seats: 1.5, color: "rule", beads: 1, beadColor: "mp" }],
    }, { animate });
    stage.setAlt(last
      ? `Two cities joined by one entangled pair. City 1 shows ${bits[0]} and City 2 shows ${bits[1]} on the last flip.`
      : "Two cities joined by one entangled pair. Neither city has a result yet.");
    return shown;
  }

  /**
   * Draw the latest-run table and the list of runs so far.
   * @returns {void}
   */
  function renderTables() {
    const latest = state.runs[state.runs.length - 1];
    if (!latest) {
      flipsHost.replaceChildren(h("p", { class: "muted", text: "No flips yet. Make a guess, then press the flip button." }));
      summaryHost.replaceChildren();
      return;
    }
    const rows = latest.flips.map((f, i) => h("tr", {},
      h("td", { class: "num", text: String(i + 1) }),
      h("td", { class: "num", text: String(f[0]) }),
      h("td", { class: "num", text: String(f[1]) }),
      h("td", { text: f[0] === f[1] ? "same" : "different" })));
    flipsHost.replaceChildren(h("table", {},
      h("thead", {}, h("tr", {}, h("th", { class: "num", text: "Flip" }), h("th", { class: "num", text: "City 1" }),
        h("th", { class: "num", text: "City 2" }), h("th", { text: "Result" }))),
      h("tbody", {}, ...rows)));
    const lines = state.runs.map((r, i) => h("tr", {},
      h("td", { class: "num", text: String(i + 1) }),
      h("td", { text: `${r.d1} and ${r.d2}` }),
      h("td", { class: "num", text: `${r.agree} of ${FLIPS}` })));
    summaryHost.replaceChildren(h("table", {},
      h("caption", { class: "sr-only", text: "All runs so far" }),
      h("thead", {}, h("tr", {}, h("th", { class: "num", text: "Run" }), h("th", { text: "Dials" }), h("th", { class: "num", text: "Agreed" }))),
      h("tbody", {}, ...lines)));
  }

  /**
   * Flip the pair 20 times with the current dials and record the run.
   * @returns {Promise<void>} Resolves after both answers have shown.
   */
  async function runFlips() {
    const random = seededRandom(state.seed);
    state.seed += 1;
    const d1 = dial1.value;
    const d2 = dial2.value;
    const flips = Array.from({ length: FLIPS }, () => flipPair(random, d1, d2));
    const agree = flips.filter((f) => f[0] === f[1]).length;
    state.runs.push({ d1, d2, flips, agree });
    renderTables();
    const last = flips[FLIPS - 1];
    const colored = drawStage(last, true); // each city changes to the color of its answer
    if (guess.ready()) {
      const actual = agree === FLIPS ? "all" : agree === 0 ? "none" : "half";
      const rule = d1 === d2
        ? "Same dial on both sides, so the results match every time."
        : "Different dials, so each result is an independent 50/50 toss.";
      const right = guess.value() === actual;
      guess.reveal(actual, `The coins agreed ${agree} of ${FLIPS} times. ${rule}`);
      if (right) { ladder.progress(); } else { ladder.wrong(); }
      guess.clearChoice();
    }
    if (d1 === d2) { state.sameDone = true; } else { state.mixedDone = true; }
    if (state.sameDone && state.mixedDone) { ladder.solve(); }
    await colored;
    // a ring in the answer color at each city says "this city just gave its answer"
    await Promise.all([stage.ring(1, bitColor(last[0])), stage.ring(2, bitColor(last[1])), stage.pulse(1), stage.pulse(2)]);
  }

  /**
   * Used by Show me and Do it for me: run one same-dial and one mixed-dial run, one after the other.
   * @returns {Promise<boolean>} Resolves when both runs have finished (false if another sequence was running).
   */
  function runBoth() {
    return lock.run(async () => {
      for (const [a, b] of [["Z", "Z"], ["Z", "X"]]) {
        dial1.value = a;
        dial2.value = b;
        await runFlips();
      }
    });
  }

  flipButton.addEventListener("click", () => { lock.run(runFlips); });
  [dial1, dial2].forEach((d) => d.addEventListener("change", () => { drawStage(null, true); ladder.progress(); }));

  narrative.append(
    chapterHead("Chapter 1 of 6", "Two questions",
      "Two magic coins sit in two cities. Each city asks its coin one question: dial Z or dial X."),
    caption({
      kid: "You have two magic coins. Ask both the same question and they always agree. Ask them different questions and the answers look random.",
      student: "A Bell pair is two qubits whose measurement results match when you measure both the same way. Neither result is decided before the measurement.",
      expert: "|Φ⁺⟩ = (|00⟩ + |11⟩)/√2. Its correlations violate the classical CHSH bound (S = 2√2 > 2).",
      breaks: "Real coins have a hidden answer from the start. Bell pairs do not. You cannot send a message with them either, because each side on its own only sees random results.",
    }),
    taskBox("Task: find when the coins always agree",
      h("div", { class: "field" }, h("label", { for: "dial1", text: "City 1 dial" }), dial1),
      h("div", { class: "field" }, h("label", { for: "dial2", text: "City 2 dial" }), dial2),
      guess.element,
      h("div", { class: "btn-row" }, flipButton),
      h("div", { "aria-live": "polite" }, flipsHost),
      summaryHost,
      ladder.element));

  renderTables();
  drawStage(null);
  return () => ladder.dispose();
}

export default { id: "ch1", number: 1, title: "Two questions", mount };

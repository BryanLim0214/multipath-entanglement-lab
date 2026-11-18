/**
 * Chapter 2, "Planes and rivers": every road throws M = 6 paper planes per round, each landing with chance q.
 * The viewer plays one round at a time, then 30 rounds, and compares the counts with exact Binomial(6, q) bars.
 */
import { h, caption, predictBox, fixed } from "../ui.js";
import { binomialPmf, seededRandom, throwAttempts } from "../math.js";
import { createLadder } from "../help-ladder.js";
import { chapterHead, taskBox, outliner } from "./common.js";

const M = 6; // attempts per road in the small setup of the paper
const ROUNDS = 30;
const TASK_ID = "ch2-links";
const CITIES = [
  { id: "A", x: -4, y: 0 }, { id: "B", x: 0, y: 2.2 }, { id: "C", x: 0, y: -2.2 }, { id: "D", x: 4, y: 0 },
];
const ROADS = [["A", "B"], ["A", "C"], ["B", "D"], ["C", "D"]];
const SVG_NS = "http://www.w3.org/2000/svg";

/**
 * Make an SVG element with attributes.
 * @param {string} tag SVG tag name.
 * @param {Object<string, string|number>} attrs Attributes.
 * @param {string} [text] Optional text content.
 * @returns {SVGElement} The element.
 */
function svg(tag, attrs, text) {
  const el = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    el.setAttribute(k, String(v));
  }
  if (text !== undefined) {
    el.textContent = text;
  }
  return el;
}

/**
 * Bar chart of observed shares (solid) next to exact Binomial bars (outlined).
 * @param {number[]} counts Observed roads with 0..M seats.
 * @param {number[]} exact Exact probabilities for 0..M seats.
 * @returns {SVGElement} The chart.
 */
export function histogram(counts, exact) {
  const total = counts.reduce((a, b) => a + b, 0);
  const share = counts.map((c) => (total ? c / total : 0));
  const top = Math.max(0.1, Math.ceil(Math.max(...share, ...exact) * 10) / 10);
  const left = 48;
  const bottom = 210;
  const plotW = 420;
  const plotH = 180;
  const step = plotW / (M + 1);
  const chart = svg("svg", { class: "chart", viewBox: "0 0 480 250", role: "img",
    "aria-label": `Histogram of seats per road. ${total} roads counted.` });
  for (let t = 0; t <= top * 10 + 1e-9; t += top <= 0.5 ? 1 : 2) {
    const y = bottom - (t / 10 / top) * plotH;
    chart.append(svg("line", { class: "grid", x1: left, x2: left + plotW, y1: y, y2: y }),
      svg("text", { x: left - 8, y: y + 4, "text-anchor": "end" }, fixed(t / 10, 1)));
  }
  share.forEach((s, k) => {
    const x = left + k * step + step * 0.15;
    const bw = step * 0.7;
    const sh = (s / top) * plotH;
    const eh = (exact[k] / top) * plotH;
    chart.append(svg("rect", { class: "bar-obs", x, y: bottom - sh, width: bw / 2, height: sh }),
      svg("rect", { class: "bar-exact", x: x + bw / 2, y: bottom - eh, width: bw / 2, height: eh }),
      svg("text", { x: x + bw / 2, y: bottom + 16, "text-anchor": "middle" }, String(k)));
  });
  chart.append(svg("line", { class: "axis", x1: left, x2: left + plotW, y1: bottom, y2: bottom }),
    svg("line", { class: "axis", x1: left, x2: left, y1: bottom - plotH, y2: bottom }),
    svg("text", { x: left + plotW / 2, y: 244, "text-anchor": "middle" }, "Seats on a road (planes that landed)"),
    svg("text", { x: 4, y: 14 }, "Share of roads"));
  return chart;
}

/**
 * Build the chapter.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {function(): void} Cleanup function.
 */
function mount(ctx) {
  const { narrative, extra, stage, hints } = ctx;
  const state = { q: 0.8, counts: new Array(M + 1).fill(0), rounds: 0, seed: 500, landed: null, done: false };

  const slider = h("input", { type: "range", id: "q-slider", min: 0.5, max: 0.9, step: 0.1, value: 0.8,
    "aria-describedby": "q-readout" });
  const readout = h("output", { id: "q-readout", class: "num", for: "q-slider" });
  const nextButton = h("button", { class: "btn", type: "button", text: "Next round", disabled: true });
  const runButton = h("button", { class: "btn btn-primary", type: "button", text: `Run ${ROUNDS} rounds`, disabled: true });
  const status = h("p", { "aria-live": "polite", class: "num" });
  const chartHost = h("div", {});
  const guess = predictBox({
    name: "ch2-guess",
    legend: "what number of landed planes is most likely on one road?",
    options: Array.from({ length: M + 1 }, (_, k) => ({ value: String(k), label: `${k} of ${M}` })),
    onChange: () => { nextButton.disabled = !guess.ready(); runButton.disabled = !guess.ready(); },
  });
  const ladder = createLadder({
    taskId: TASK_ID,
    hints,
    /** Task actions that help levels 3 to 5 call. */
    handlers: {
      highlight: outliner([slider]),
      show: () => { runRounds(); },
      doIt: () => { runRounds(); },
      similar: () => { resetCounts(); slider.value = String((5 + ((state.seed * 7) % 5)) / 10); onSlide(); },
    },
  });

  /**
   * Exact most likely number of landed planes for the current q.
   * @returns {number} Mode of Binomial(M, q).
   */
  function exactMode() {
    const pmf = binomialPmf(M, state.q);
    return pmf.indexOf(Math.max(...pmf));
  }

  /**
   * Draw the four roads for a given count of landed planes per road.
   * @param {number[]|null} shown Planes shown so far on each road, or null for an empty round.
   * @returns {void}
   */
  function drawRoads(shown) {
    const links = [];
    ROADS.forEach(([from, to], i) => {
      links.push({ from, to, seats: 0.5, color: "rule" });
      const seats = shown ? shown[i] : 0;
      links.push({ from, to, seats, color: "mp", beads: seats, beadColor: "ink",
        label: shown ? `${state.landed ? state.landed[i].filter(Boolean).length : seats} of ${M}` : `0 of ${M}` });
    });
    stage.show({ nodes: CITIES.map((c) => ({ ...c, label: c.id, color: "ink" })), links });
    stage.setAlt(shown
      ? `Four roads between cities A, B, C and D. Each road shows how many of its ${M} planes landed.`
      : `Four roads between cities A, B, C and D. No round has been played yet.`);
  }

  /**
   * Redraw the histogram and the status line.
   * @returns {void}
   */
  function drawChart() {
    chartHost.replaceChildren(histogram(state.counts, binomialPmf(M, state.q)));
    const roads = state.counts.reduce((a, b) => a + b, 0);
    status.textContent = roads ? `Roads counted: ${roads} (${state.rounds} rounds). q = ${fixed(state.q, 1)}.` : `No rounds yet. q = ${fixed(state.q, 1)}.`;
  }

  /**
   * Forget all counted rounds (used when q changes).
   * @returns {void}
   */
  function resetCounts() {
    state.counts = new Array(M + 1).fill(0);
    state.rounds = 0;
    state.landed = null;
    guess.reset();
    nextButton.disabled = true;
    runButton.disabled = true;
  }

  /**
   * Play one round: every road throws M planes. Planes appear one by one on the roads.
   * @returns {Promise<void>} Resolves when the animation ends.
   */
  async function playRound() {
    const random = seededRandom(state.seed);
    state.seed += 1;
    state.landed = ROADS.map(() => throwAttempts(random, M, state.q));
    const finals = state.landed.map((a) => a.filter(Boolean).length);
    finals.forEach((k) => { state.counts[k] += 1; });
    state.rounds += 1;
    await stage.tween(400, (t) => drawRoads(finals.map((f) => Math.round(f * t))));
    drawRoads(finals);
    drawChart();
    reveal(`This round the roads got ${finals.join(", ")} seats.`);
  }

  /**
   * Play 30 rounds at once and add them to the histogram.
   * @returns {void}
   */
  function runRounds() {
    const random = seededRandom(state.seed);
    state.seed += 1;
    for (let r = 0; r < ROUNDS; r += 1) {
      ROADS.forEach(() => { state.counts[throwAttempts(random, M, state.q).filter(Boolean).length] += 1; });
    }
    state.rounds += ROUNDS;
    drawChart();
    reveal(`${ROUNDS} rounds counted.`);
    ladder.solve();
  }

  /**
   * Tell the viewer whether their guess was the exact most likely number.
   * @param {string} lead First sentence describing what just happened.
   * @returns {void}
   */
  function reveal(lead) {
    if (!guess.ready()) {
      return;
    }
    const mode = exactMode();
    const p = binomialPmf(M, state.q)[mode];
    const right = guess.value() === String(mode);
    guess.reveal(String(mode), `${lead} The most likely number is ${mode} (exact chance ${fixed(p, 2)}).`);
    if (right) { ladder.progress(); } else { ladder.wrong(); }
    guess.clearChoice();
    nextButton.disabled = true;
    runButton.disabled = true;
  }

  /**
   * React to the q slider.
   * @returns {void}
   */
  function onSlide() {
    state.q = Number(slider.value);
    readout.textContent = `q = ${fixed(state.q, 1)}`;
    resetCounts();
    drawRoads(null);
    drawChart();
    ladder.progress();
  }

  nextButton.addEventListener("click", () => { playRound(); });
  runButton.addEventListener("click", () => { runRounds(); });
  slider.addEventListener("input", onSlide);

  narrative.append(
    chapterHead("Chapter 2 of 6", "Planes and rivers",
      "Cities are joined by roads across a river. Every round, each road throws 6 paper planes, and each plane lands with chance q."),
    caption({
      kid: "Every round, each road throws 6 paper planes across a river. Each plane lands with chance q, and a bell rings when one lands, so you know it worked.",
      student: "In each round (a window), every pair of neighbouring nodes makes M attempts. The attempts that succeed are that link's capacity, C_ij, and each one is a seat for one pair.",
      expert: "C_ij ~ Binomial(M, q). The paper uses M = 6 (small setup) and q in {0.5, ..., 0.9}.",
      breaks: "Real attempts take time and hardware. Here, a whole round happens in a single step.",
    }),
    taskBox("Task: count the seats over 30 rounds",
      h("div", { class: "field" }, h("label", { for: "q-slider", text: "Chance q that a plane lands" }), slider, " ", readout),
      guess.element,
      h("div", { class: "btn-row" }, nextButton, runButton),
      status,
      ladder.element));

  extra.append(
    h("h3", { text: "Seats per road" }),
    chartHost,
    h("div", { class: "legend" },
      h("span", {}, h("span", { class: "swatch swatch-obs" }), "Counted in your rounds"),
      h("span", {}, h("span", { class: "swatch swatch-exact" }), "Exact Binomial(6, q)")));

  onSlide();
  return () => ladder.dispose();
}

export default { id: "ch2", number: 2, title: "Planes and rivers", mount };

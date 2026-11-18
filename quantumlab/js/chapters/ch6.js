/**
 * Chapter 6, "Same dice, two plans": the viewer guesses which plan blocks fewer requests, then sees the
 * paired 30-seed results with 95% error bars next to the paper's printed values. Numbers come from
 * data/arena.json, which tools/export_data.py builds from results/partA_small.csv and data/paper_values.yaml.
 */
import { h, caption, predictBox, loadJson, fixed } from "../ui.js";
import { createLadder } from "../help-ladder.js";
import { chapterHead, taskBox, outliner, svgEl } from "./common.js";

const TASK_ID = "ch6-dice";
const FOCUS_Q = "0.9"; // the q at which the paper prints its blocking ratios
const LINES = [
  { method: "SP-Heu", css: "sp", dashed: true, shift: -4 },
  { method: "MP-Heu", css: "mp", dashed: true, shift: -1.3 },
  { method: "SP-ILP", css: "sp", dashed: false, shift: 1.3 },
  { method: "MP-ILP", css: "mp", dashed: false, shift: 4 },
];
const TABLE_METHODS = ["SP-SPF", "SP-Heu", "MP-Heu", "SP-ILP", "MP-ILP"];

/**
 * Which plan the paired difference favours, using its 95% interval.
 * @param {{mean: number, ci: number}} diff Single-path minus multipath blocking ratio, paired over seeds.
 * @returns {string} "multi" if multipath blocks fewer, "single" if single-path does, otherwise "same".
 */
export function favoured(diff) {
  if (diff.mean - diff.ci > 0) { return "multi"; }
  if (diff.mean + diff.ci < 0) { return "single"; }
  return "same";
}

/**
 * Spread labels vertically so that none overlaps the next.
 * @param {{y: number}[]} items Labels with a wanted y position (pixels, downward).
 * @param {number} gap Smallest distance between two labels.
 * @returns {void} The y values are changed in place.
 */
function spreadLabels(items, gap) {
  const sorted = [...items].sort((a, b) => a.y - b.y);
  for (let i = 1; i < sorted.length; i += 1) {
    sorted[i].y = Math.max(sorted[i].y, sorted[i - 1].y + gap);
  }
}

/**
 * Line chart of the blocking ratio against q, with 95% error bars and the paper's printed values.
 * @param {{summary: object, paper: object}} data The arena.json content.
 * @returns {SVGElement} The chart.
 */
export function blockingChart(data) {
  const qs = Object.keys(data.summary.blocking_ratio);
  const left = 56;
  const top = 16;
  const plotW = 400;
  const plotH = 240;
  const yMax = 0.8;
  /** Pixel x of a q column. */
  const x = (q) => left + (qs.indexOf(q) / (qs.length - 1)) * plotW;
  /** Pixel y of a blocking ratio. */
  const y = (v) => top + plotH - (Math.min(v, yMax) / yMax) * plotH;
  const chart = svgEl("svg", { class: "chart", viewBox: "0 0 600 320", role: "img",
    "aria-label": "Blocking ratio against q for four plans, with 95 percent error bars over 30 seeds. The values are in the table below." });
  for (let t = 0; t <= 4; t += 1) {
    const v = (t * yMax) / 4;
    chart.append(svgEl("line", { class: "grid", x1: left, x2: left + plotW, y1: y(v), y2: y(v) }),
      svgEl("text", { x: left - 8, y: y(v) + 4, "text-anchor": "end" }, fixed(v, 1)));
  }
  qs.forEach((q) => chart.append(svgEl("text", { x: x(q), y: top + plotH + 20, "text-anchor": "middle" }, q)));
  chart.append(svgEl("line", { class: "axis", x1: left, x2: left + plotW, y1: top + plotH, y2: top + plotH }),
    svgEl("text", { x: left + plotW / 2, y: top + plotH + 44, "text-anchor": "middle" }, "q (chance a plane lands)"),
    svgEl("text", { x: 14, y: top + plotH / 2, "text-anchor": "middle", transform: `rotate(-90 14 ${top + plotH / 2})` }, "Blocking ratio"));
  const labels = [];
  LINES.forEach((line) => {
    const cells = qs.map((q) => ({ q, ...data.summary.blocking_ratio[q][line.method] }));
    const points = cells.map((c) => `${x(c.q) + line.shift},${y(c.mean)}`).join(" ");
    chart.append(svgEl("polyline", { class: `line line-${line.css}${line.dashed ? " dashed" : ""}`, points }));
    cells.forEach((c) => {
      const px = x(c.q) + line.shift;
      chart.append(svgEl("line", { class: `bar bar-${line.css}`, x1: px, x2: px, y1: y(Math.max(0, c.mean - c.ci)), y2: y(c.mean + c.ci) }),
        svgEl("circle", { class: `dot dot-${line.css}`, cx: px, cy: y(c.mean), r: 3 }));
    });
    const end = cells[cells.length - 1];
    labels.push({ text: line.method, y: y(end.mean) + 4, x: x(end.q) + 14 });
  });
  spreadLabels(labels, 14);
  labels.forEach((l) => chart.append(svgEl("text", { x: l.x, y: l.y }, l.text)));
  Object.entries(data.paper).forEach(([method, value]) => {
    chart.append(svgEl("circle", { class: "paper-dot", cx: x(FOCUS_Q), cy: y(value), r: 5 }),
      svgEl("text", { x: x(FOCUS_Q) + 14, y: y(value) + 4 }, `paper, ${method}: ${fixed(value, 2)}`));
  });
  return chart;
}

/**
 * A table of mean and 95% interval per method and q, and the paired differences.
 * @param {{summary: object}} data The arena.json content.
 * @returns {HTMLElement} The table inside a scroll box.
 */
function resultsTable(data) {
  const qs = Object.keys(data.summary.blocking_ratio);
  /** A table cell with mean plus or minus the 95% half-width. */
  const cell = (c) => h("td", { class: "num", text: `${fixed(c.mean, 3)} ± ${fixed(c.ci, 3)}` });
  const rows = TABLE_METHODS.map((m) => h("tr", {}, h("th", { scope: "row", text: m }), ...qs.map((q) => cell(data.summary.blocking_ratio[q][m]))));
  const diffs = ["Heu", "ILP"].map((pair) => h("tr", {}, h("th", { scope: "row", text: `SP-${pair} minus MP-${pair}` }),
    ...qs.map((q) => cell(data.summary.single_minus_multi[q][pair]))));
  return h("div", { class: "table-scroll", role: "region", "aria-label": "Blocking ratio table", tabIndex: 0 }, h("table", { "aria-label": "Blocking ratio, mean and 95 percent interval over 30 seeds" },
    h("thead", {}, h("tr", {}, h("th", { text: "Method" }), ...qs.map((q) => h("th", { class: "num", text: `q = ${q}` })))),
    h("tbody", {}, ...rows, ...diffs)));
}

/**
 * Build the chapter.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {Promise<function(): void>} Cleanup function.
 */
async function mount(ctx) {
  const { narrative, hints } = ctx;
  const data = await loadJson("arena.json");
  const lab = document.getElementById("view-lab");
  const stageColumn = document.querySelector(".stage-col");
  lab.classList.add("is-wide");
  stageColumn.hidden = true;

  const heu = data.summary.single_minus_multi[FOCUS_Q].Heu;
  const actual = favoured(heu);
  const guess = predictBox({
    name: "ch6-guess",
    legend: `at q = ${FOCUS_Q} on the 3 by 3 grid, over 30 seeds, which plan blocks fewer requests (heuristic pair)?`,
    options: [["single", "Single-path blocks fewer"], ["multi", "Multipath blocks fewer"], ["same", "No difference we can measure"]]
      .map(([value, label]) => ({ value, label })),
    onChange: () => { runButton.disabled = !guess.ready() || resultHost.childElementCount > 0; },
  });
  const runButton = h("button", { class: "btn btn-primary", type: "button", text: "Show the 30 seeds", disabled: true, onclick: () => showResults() });
  const againButton = h("button", { class: "btn", type: "button", text: "Hide and guess again", hidden: true, onclick: () => hideResults() });
  const resultHost = h("div", { "aria-live": "polite" });
  const ladder = createLadder({
    taskId: TASK_ID,
    hints,
    /** Task actions that help levels 3 to 5 call. */
    handlers: {
      highlight: outliner([guess.element.querySelector("fieldset")]),
      show: () => { showResults(true); },
      doIt: () => { showResults(true); },
      similar: () => { hideResults(); },
    },
  });

  /**
   * The honest note about our levels against the paper's.
   * @returns {HTMLElement} The note.
   */
  function levelsNote() {
    const ours = data.summary.blocking_ratio[FOCUS_Q];
    return h("p", { class: "callout" },
      `Our levels are lower than the paper's printed ${fixed(data.paper["MP-ILP"], 2)} and ${fixed(data.paper["SP-ILP"], 2)} `
      + `(our ILP pair at q = ${FOCUS_Q}: ${fixed(ours["MP-ILP"].mean, 3)} and ${fixed(ours["SP-ILP"].mean, 3)}). `
      + "The paper does not say how many pairs a request needs (A1), so our load differs from theirs, which is the likely reason. "
      + "The comparison between the two plans is still fair, because each seed gives both plans the same requests and the same link outcomes (A19).");
  }

  /**
   * Show the chart, the table and the verdict.
   * @param {boolean} [helped] True when a help level opened it, so the guess is not scored.
   * @returns {void}
   */
  function showResults(helped = false) {
    if (resultHost.childElementCount > 0) { return; }
    const ours = data.summary.blocking_ratio[FOCUS_Q];
    const sentence = `At q = ${FOCUS_Q} the heuristic pair blocked ${fixed(ours["SP-Heu"].mean, 3)} (single-path) and ${fixed(ours["MP-Heu"].mean, 3)} (multipath). `
      + `The paired difference is ${fixed(heu.mean, 3)} with a 95% interval of plus or minus ${fixed(heu.ci, 3)}.`;
    resultHost.replaceChildren(
      h("h3", { text: "Blocking ratio over 30 seeds, 95% error bars" }),
      h("div", { class: "table-scroll", role: "region", "aria-label": "Chart of blocking ratio against q", tabIndex: 0 }, blockingChart(data)),
      h("div", { class: "legend" },
        h("span", {}, h("span", { class: "swatch swatch-sp" }), "Single-path"),
        h("span", {}, h("span", { class: "swatch swatch-mp" }), "Multipath"),
        h("span", {}, "Solid lines: exact solver (ILP). Dashed lines: heuristic."),
        h("span", {}, "Hollow circles: values the paper prints in its text.")),
      resultsTable(data),
      levelsNote());
    runButton.disabled = true;
    againButton.hidden = false;
    if (helped || !guess.ready()) {
      return;
    }
    guess.reveal(actual, sentence);
    if (guess.value() === actual) { ladder.solve(); } else { ladder.wrong(); }
  }

  /**
   * Remove the results so the viewer can guess again.
   * @returns {void}
   */
  function hideResults() {
    resultHost.replaceChildren();
    guess.reset();
    againButton.hidden = true;
    runButton.disabled = true;
  }

  narrative.append(
    chapterHead("Chapter 6 of 6", "Same dice, two plans",
      "The paper says that splitting a request over several roads blocks fewer requests. Here you check that claim on our own runs."),
    caption({
      kid: "Two towns get the very same requests and the very same planes, thirty times in a row. Only the plan differs, so any gap between the towns comes from the plan.",
      student: "For each seed both plans see the same requests and the same link outcomes (A19). We subtract the blocking ratios seed by seed, and the 95% interval of that difference tells us whether the gap is more than luck.",
      expert: `BR = (|R| - sum of X^r) / |R| for a ${data.config.rows} by ${data.config.cols} grid, |R| = ${data.config.R}, M = ${data.config.M}, T = ${data.config.T}, t_c = ${data.config.tc}, f = ${data.config.f}. `
        + "The paired difference uses a t interval over 30 seeds (qmp.stats.paired_diff_ci). "
        + `The paper prints BR = ${fixed(data.paper["MP-ILP"], 2)} (MP-ILP) and ${fixed(data.paper["SP-ILP"], 2)} (SP-ILP) at q = ${FOCUS_Q} (Sec. IV-A).`,
      breaks: "A paired interval only says the plans differ in this setup. It does not say how large the gap is on other grids or request mixes.",
    }),
    taskBox("Task: guess, then read the 30 seeds",
      guess.element,
      h("div", { class: "btn-row" }, runButton, againButton),
      resultHost,
      h("p", {}, h("a", { class: "btn", href: "#/arena", text: "Replay one seed in the Arena" })),
      ladder.element));

  return () => {
    ladder.dispose();
    lab.classList.remove("is-wide");
    stageColumn.hidden = false;
  };
}

export default { id: "ch6", number: 6, title: "Same dice, two plans", mount };

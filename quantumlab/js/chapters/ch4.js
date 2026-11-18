/**
 * Chapter 4, "Paint mixing": every swap mixes in grey paint. The viewer adds middle cities one at a time
 * and watches an exact Werner-state fidelity meter cross the threshold f.
 */
import { h, caption, predictBox, loadJson, fixed } from "../ui.js";
import { pathFidelity, maxIntermediate } from "../math.js";
import { rampColor } from "../three-stage.js";
import { createLadder } from "../help-ladder.js";
import { chapterHead, taskBox, outliner } from "./common.js";

const TASK_ID = "ch4-fidelity";
const MAX_MIDDLE = 15;
const FLOOR = 0.25; // a Werner pair never gets worse than 0.25
const SPAN_X = 5;

/**
 * Build the chapter.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {Promise<function(): void>} Cleanup function.
 */
async function mount(ctx) {
  const { narrative, stage, hints } = ctx;
  const data = await loadJson("fidelity.json");
  const F = data.link_fidelity;
  const state = { middle: 0, f: 0.78, revealed: false };

  const addButton = h("button", { class: "btn btn-primary", type: "button", text: "Add a middle city", disabled: true });
  const removeButton = h("button", { class: "btn", type: "button", text: "Remove", disabled: true });
  const slider = h("input", { type: "range", id: "f-slider", min: 0.5, max: 0.9, step: 0.01, value: 0.78, "aria-describedby": "f-readout" });
  const fReadout = h("output", { id: "f-readout", class: "num", for: "f-slider" });
  const readout = h("p", { class: "readout", "aria-live": "polite" });
  const limitLine = h("p", {});
  const fill = h("div", { class: "meter-fill" });
  const line = h("div", { class: "meter-line" });
  const lineLabel = h("span", { class: "meter-line-label num" });
  const meter = h("div", { class: "meter", role: "img" }, fill, line, lineLabel);
  const dataError = h("div", { class: "error-box", hidden: true, role: "alert" });
  const guess = predictBox({
    name: "ch4-guess",
    legend: "how many middle cities can a pair cross before it falls below f = 0.78?",
    options: [2, 4, 6, 10].map((n) => ({ value: String(n), label: `${n} middle cities` })),
    onChange: () => { refresh(); },
  });
  const ladder = createLadder({
    taskId: TASK_ID,
    hints,
    /** Task actions that help levels 3 to 5 call. */
    handlers: {
      highlight: outliner([addButton]),
      show: () => { autoAdd(); },
      doIt: () => { autoAdd(); },
      similar: () => { state.middle = 0; state.revealed = false; guess.reset(); refresh(); },
    },
  });

  /**
   * Compare the exported numbers with the formula computed here, and show a message if they differ.
   * @returns {void}
   */
  function crossCheck() {
    const bad = data.table.filter((row) => Math.abs(row.fidelity - pathFidelity(F, row.links)) > 1e-5);
    const badLimits = Object.entries(data.limits).filter(([f, n]) => maxIntermediate(F, Number(f)) !== n);
    if (bad.length || badLimits.length) {
      dataError.hidden = false;
      dataError.textContent = "The exported fidelity table and the formula in this page disagree. Please report this.";
    }
  }

  /**
   * Draw the chain of cities for the current count of middle cities.
   * @returns {void}
   */
  function drawStage() {
    const n = state.middle + 2;
    const links = [];
    const nodes = Array.from({ length: n }, (_, i) => ({
      id: i, x: -SPAN_X + (2 * SPAN_X * i) / (n - 1), y: -0.8,
      label: i === 0 ? "A" : i === n - 1 ? "B" : String(i), color: i === 0 || i === n - 1 ? "ink" : "muted",
    }));
    for (let i = 0; i + 1 < n; i += 1) {
      links.push({ from: i, to: i + 1, seats: 1, color: rampColor(F), beads: 1, beadColor: "ink" });
    }
    const end = pathFidelity(F, state.middle + 1);
    if (state.middle > 0) {
      links.push({ from: 0, to: n - 1, seats: 1.2, color: end < state.f ? "fail" : rampColor(end), arc: 2.4,
        label: `end to end ${fixed(end, 2)}`, note: true });
    }
    stage.show({ nodes, links });
    stage.setAlt(`A chain from city A to city B with ${state.middle} middle cities. `
      + `The end-to-end fidelity is ${fixed(end, 3)} and the threshold is ${fixed(state.f, 2)}.`);
  }

  /**
   * Update the meter, the readout, the buttons, and the limit line.
   * @returns {void}
   */
  function refresh() {
    const links = state.middle + 1;
    const end = pathFidelity(F, links);
    const failed = end < state.f;
    /**
     * Position on the meter, from the 0.25 floor to 1.
     * @param {number} value Fidelity.
     * @returns {string} CSS percentage.
     */
    const share = (value) => `${(100 * (value - FLOOR)) / (1 - FLOOR)}%`;
    fill.style.width = share(end);
    fill.style.background = failed ? "var(--fail)" : rampColor(end);
    line.style.left = share(state.f);
    lineLabel.style.left = share(state.f);
    lineLabel.textContent = `f = ${fixed(state.f, 2)}`;
    meter.setAttribute("aria-label", `Fidelity ${fixed(end, 3)} against the threshold ${fixed(state.f, 2)}.`);
    readout.textContent = `${state.middle} middle ${state.middle === 1 ? "city" : "cities"}, ${links} ${links === 1 ? "link" : "links"}: F = ${fixed(end, 3)}${failed ? " (too washed out)" : ""}`;
    readout.style.color = failed ? "var(--fail)" : "var(--ink)";
    const limit = data.limits[fixed(state.f, 2)];
    limitLine.textContent = `At f = ${fixed(state.f, 2)} a path may have at most ${limit} middle cities. `
      + `Recomputed in this page: ${maxIntermediate(F, state.f)}.`;
    fReadout.textContent = `f = ${fixed(state.f, 2)}`;
    addButton.disabled = !guess.ready() || state.middle >= MAX_MIDDLE;
    removeButton.disabled = !guess.ready() || state.middle === 0;
    drawStage();
    if (failed && !state.revealed && guess.ready()) {
      state.revealed = true;
      const right = guess.value() === String(limit);
      guess.reveal(String(limit), `With F = ${fixed(F, 2)} the limit at f = ${fixed(state.f, 2)} is ${limit} middle cities, so the meter fails at ${limit + 1}.`);
      if (!right) { ladder.wrong(); }
    }
    if (failed) { ladder.solve(); }
  }

  /**
   * Add middle cities one at a time until the meter fails (Show me and Do it for me).
   * @returns {Promise<void>} Resolves when done.
   */
  async function autoAdd() {
    while (pathFidelity(F, state.middle + 1) >= state.f && state.middle < MAX_MIDDLE) {
      state.middle += 1;
      refresh();
      await stage.tween(200, () => {});
    }
  }

  addButton.addEventListener("click", () => { state.middle += 1; ladder.progress(); refresh(); });
  removeButton.addEventListener("click", () => { state.middle -= 1; ladder.progress(); refresh(); });
  slider.addEventListener("input", () => { state.f = Number(slider.value); ladder.progress(); refresh(); });

  narrative.append(
    chapterHead("Chapter 4 of 5", "Paint mixing",
      "Every join mixes a little grey paint into the pair. Add middle cities and see when the pair is too washed out to use."),
    caption({
      kid: "Every join mixes in a little grey paint. A long chain gets too washed out to use.",
      student: "Fidelity measures how close a pair is to perfect. It drops with every swap, so a path can only pass through a limited number of middle nodes.",
      expert: "Werner parameter w = (4F - 1)/3. Over L links, F_L = (3w^L + 1)/4. With F = 0.95 and f = 0.78 the limit is 4 intermediate nodes; with f = 0.6 it is 10.",
      breaks: "The grey is random noise, not a copy, because quantum states cannot be copied. Real swaps also add noise of their own, which this model ignores.",
    }),
    taskBox("Task: add middle cities until the meter turns red",
      guess.element,
      h("div", { class: "btn-row" }, addButton, removeButton),
      readout,
      meter,
      dataError,
      h("div", { class: "field" }, h("label", { for: "f-slider", text: "Smallest fidelity f the request accepts" }), slider, " ", fReadout),
      limitLine,
      ladder.element));

  crossCheck();
  refresh();
  return () => ladder.dispose();
}

export default { id: "ch4", number: 4, title: "Paint mixing", mount };

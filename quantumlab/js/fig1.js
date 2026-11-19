/**
 * The Fig. 1 debugger: steps through the paper's worked example (request 7 to 6, n = 4, delta = 2) using
 * data/fig1_steps.json, which the exporter produced by running the real heuristic in src/qmp.
 */
import { h, caption, predictBox, loadJson } from "./ui.js";
import { createLadder } from "./help-ladder.js";
import { chapterHead, taskBox, createLock } from "./chapters/common.js";

const TASK_ID = "fig1-walk";
const POSITIONS = {
  7: [-5, -0.5], 1: [-3.5, 2.2], 2: [-0.5, 2.8], 4: [3, 2.8], 6: [5.5, 0.3],
  3: [-1.2, 0.2], 5: [2.3, 0.3], 8: [0, -2.4], 9: [3.6, -2.4],
};
const PAPER_PRINTS_ALPHA3 = "4/2";

/**
 * A fraction as the paper prints it, with its decimal value.
 * @param {{num: number, den: number}} c Candidate with numerator and denominator.
 * @returns {string} Text such as "4/2 = 2.00".
 */
function fractionText(c) {
  return `${c.num}/${c.den} = ${(c.num / c.den).toFixed(2)}`;
}

/**
 * Build the debugger.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {Promise<function(): void>} Cleanup function.
 */
async function mount(ctx) {
  const { narrative, extra, stage, hints } = ctx;
  const data = await loadJson("fig1_steps.json");
  const req = data.request;
  const total = data.steps.length;
  const state = { frame: 0, hintOn: false };

  const stepButton = h("button", { class: "btn btn-primary", type: "button", text: "Step", disabled: true });
  const backButton = h("button", { class: "btn", type: "button", text: "Back", disabled: true });
  const resetButton = h("button", { class: "btn", type: "button", text: "Start again" });
  const counter = h("p", { class: "step-count", "aria-live": "polite" });
  const frameHost = h("div", { "aria-live": "polite" });
  const guess = predictBox({
    name: "fig1-guess",
    legend: `from city ${req.s}, which neighbour will the walk choose first?`,
    options: [{ value: "1", label: "City 1" }, { value: "8", label: "City 8" }],
    onChange: () => { refresh(); },
  });
  const lock = createLock(() => updateButtons());
  const ladder = createLadder({
    taskId: TASK_ID,
    hints,
    /** Task actions that help levels 3 to 5 call. */
    handlers: {
      highlight: (on) => { state.hintOn = on; refresh(); },
      show: () => { autoStep(); },
      doIt: () => { if (!lock.busy) { state.frame = total; refresh(true); } },
      similar: () => { if (!lock.busy) { state.frame = 0; guess.reset(); refresh(true); } },
    },
  });

  /**
   * Walks, found paths and the pieces the stage should draw for the current frame.
   * @returns {{node: Object<number, string>, labels: Object<number, string>, tubes: object[], seatsNow: Map<string, number>}} Drawing instructions.
   */
  function frameDrawing() {
    const node = {};
    const labels = {};
    const tubes = [];
    const seatsNow = new Map(data.links.map((l) => [`${l.a}-${l.b}`, l.seats]));
    const done = data.steps.slice(0, state.frame - 1).filter((s) => s.kind === "found");
    const now = state.frame > 0 ? data.steps[state.frame - 1] : null;
    done.forEach((s) => s.path.slice(0, -1).forEach((v, i) => tubes.push({ a: v, b: s.path[i + 1], seats: 2, color: "ink", lift: 0.45 })));
    if (now && now.kind === "choose") {
      const route = [...now.so_far, now.chosen];
      route.slice(0, -1).forEach((v, i) => tubes.push({ a: v, b: route[i + 1], seats: 2, color: "mp", lift: 0.6 }));
      route.forEach((v) => { node[v] = "mp"; });
      now.candidates.forEach((c) => {
        labels[c.node] = `${c.node}: ${c.num}/${c.den}`;
        if (c.node !== now.chosen) { node[c.node] = "warn"; }
      });
    }
    if (now && now.kind === "found") {
      now.path.slice(0, -1).forEach((v, i) => tubes.push({ a: v, b: now.path[i + 1], seats: 2, color: "mp", lift: 0.6 }));
      now.path.forEach((v) => { node[v] = "mp"; });
    }
    if (now && (now.kind === "allocation" || now.kind === "residual")) {
      const split = data.steps.find((s) => s.kind === "allocation").split;
      split.forEach(({ path, pairs }) => {
        path.slice(0, -1).forEach((v, i) => tubes.push({ a: v, b: path[i + 1], seats: pairs, color: "mp", lift: 0.6 }));
        path.forEach((v) => { node[v] = "mp"; });
      });
    }
    if (now && now.kind === "residual") {
      now.links.forEach((l) => seatsNow.set(`${l.a}-${l.b}`, l.after));
    }
    return { node, labels, tubes, seatsNow };
  }

  /**
   * Draw the network for the current frame.
   * @param {boolean} [animate] True to grow the new path tubes and shrink the seats that were used.
   * @param {number} [ms] Length of the change.
   * @returns {Promise<void>} Resolves when the change has finished.
   */
  function drawStage(animate = false, ms = 360) {
    const { node, labels, tubes, seatsNow } = frameDrawing();
    const residual = state.frame > 0 && data.steps[state.frame - 1].kind === "residual";
    const was = residual ? new Map(data.steps[state.frame - 1].links.map((l) => [`${l.a}-${l.b}`, l.before])) : new Map();
    const nodes = Object.entries(POSITIONS).map(([key, [x, y]]) => {
      const id = Number(key);
      const base = id === req.s ? `S${id}` : id === req.d ? `E${id}` : String(id); // S = start, E = end
      return { id, x, y, color: node[id] || "ink", label: base, onNode: true,
        hint: state.hintOn && state.frame === 0 && (id === 1 || id === 8) };
    });
    const links = data.links.map((l) => {
      const key = `${l.a}-${l.b}`;
      const left = seatsNow.get(key);
      const text = was.has(key) ? `${left} (was ${was.get(key)})` : String(left);
      return { from: l.a, to: l.b, seats: left, color: "muted", label: text, small: true };
    });
    tubes.forEach((t) => links.push({ from: t.a, to: t.b, key: `over|${t.a}|${t.b}|${t.lift}`, seats: t.seats, color: t.color, lift: t.lift }));
    const captions = Object.entries(labels).map(([key, text]) => ({ x: POSITIONS[key][0], y: POSITIONS[key][1] + 1.0, text: `alpha ${text.split(": ")[1]}` }));
    const done = stage.show({ nodes, links, captions, view: "top", pad: 1.6 }, { animate, ms });
    stage.setAlt(`The paper's 9 city network with link seats. Request from city ${req.s} to city ${req.d}. `
      + `Step ${state.frame} of ${total}.`);
    return done;
  }

  /**
   * Plain-English text for the current frame.
   * @returns {HTMLElement[]} Elements to place in the frame area.
   */
  function frameText() {
    if (state.frame === 0) {
      return [h("p", {}, `Request: send ${req.n} pairs from city ${req.s} to city ${req.d}. At most ${req.max_mid} middle cities are allowed by fidelity. `
        + `The spare-seat rule is delta = ${req.delta}: one request may use at most half of a path's seats.`)];
    }
    const s = data.steps[state.frame - 1];
    if (s.kind === "choose") {
      return chooseText(s);
    }
    if (s.kind === "found") {
      return [h("p", {}, `Reached city ${req.d}. Path ${s.path.join("-")} has a bottleneck of ${s.bottleneck} seats. `
        + `Its links are set aside, so the next path shares no link with it.`)];
    }
    if (s.kind === "allocation") {
      const need = req.n * s.delta;
      const rows = s.sorted_paths.map((p) => `${p.path.join("-")}: bottleneck ${p.bottleneck}, offers ${p.bottleneck} / ${s.delta} = ${p.seats_offered} pairs`);
      return [h("p", {}, `No single path has ${need} seats (${req.n} pairs times delta ${s.delta}), so the request is split.`),
        h("ul", { class: "num" }, ...rows.map((r) => h("li", { text: r }))),
        h("p", {}, `Allocation: ${s.split.map((x) => `${x.pairs} pairs on ${x.path.join("-")}`).join(" and ")}.`)];
    }
    return [h("p", {}, "Seats left after placing the pairs. Tubes show the seats now; labels show the new count and the old one in brackets. "
      + "These equal the capacities in Fig. 1c of the paper.")];
  }

  /**
   * The text for a walking step: scores, the winner, ties, and the alpha 3 callout.
   * @param {object} s A "choose" step from the data.
   * @returns {HTMLElement[]} Elements.
   */
  function chooseText(s) {
    const items = s.candidates.map((c) => h("li", { class: c.node === s.chosen ? "is-chosen" : "" },
      h("span", { class: "num", text: `City ${c.node}` }), h("span", { class: "num", text: fractionText(c) }),
      h("span", { text: c.node === s.chosen ? "chosen" : "" })));
    const out = [
      h("p", {}, `Path ${s.path_no}, standing at city ${s.at}. Each neighbour gets a score: the smaller of its link's seats and the best bottleneck beyond it, `
        + `divided by the hops left. The highest score wins.`),
      h("ul", { class: "alpha-list" }, ...items),
    ];
    if (s.tied.length > 1) {
      out.push(h("p", { class: "small" }, `Tie between cities ${s.tied.join(" and ")}. This page takes the lowest id, ${s.chosen}. ${data.random_tie_note}`));
    }
    const three = s.candidates.find((c) => c.node === 3);
    if (s.path_no === 1 && s.at === 8 && three) {
      out.push(h("div", { class: "callout" }, h("p", {},
        `The paper prints ${PAPER_PRINTS_ALPHA3}; the rule that matches its other values gives ${three.num}/${three.den}. The chosen path does not change.`)));
    }
    return out;
  }

  /**
   * Enable or disable the buttons: nothing can be pressed while a step is animating.
   * @returns {void}
   */
  function updateButtons() {
    stepButton.disabled = state.frame >= total || (state.frame === 0 && !guess.ready()) || lock.busy;
    backButton.disabled = state.frame === 0 || lock.busy;
    resetButton.disabled = lock.busy;
  }

  /**
   * Redraw everything for the current frame.
   * @param {boolean} [animate] True to animate the picture from the one on screen.
   * @param {number} [ms] Length of the picture change.
   * @returns {Promise<void>} Resolves when the picture has finished changing.
   */
  function refresh(animate = false, ms = 360) {
    counter.textContent = `Step ${state.frame} of ${total}`;
    updateButtons();
    frameHost.replaceChildren(...frameText());
    const drawn = drawStage(animate, ms);
    if (state.frame === total) {
      ladder.solve();
    }
    return drawn;
  }

  /**
   * Swell the alpha candidates of a walking step, so the eye sees which cities were scored.
   * @returns {Promise<void>} Resolves when the swelling is done.
   */
  function highlightCandidates() {
    const now = state.frame > 0 ? data.steps[state.frame - 1] : null;
    return now && now.kind === "choose" ? Promise.all(now.candidates.map((c) => stage.pulse(c.node))).then(() => {}) : Promise.resolve();
  }

  /**
   * Animate what the current frame means: the walker runs the chosen hop;
   * a found path is run end to end, and each part of an allocation runs its own path.
   * @returns {Promise<void>} Resolves when the walker has arrived.
   */
  async function playFrame() {
    const now = state.frame > 0 ? data.steps[state.frame - 1] : null;
    if (!now) { return; }
    if (now.kind === "choose") {
      await stage.travel([now.at, now.chosen], { color: "mp" });
    } else if (now.kind === "found") {
      await stage.travel(now.path, { color: "mp" });
    } else if (now.kind === "allocation") {
      await Promise.all(now.split.map(({ path }) => stage.travel(path, { color: "mp" })));
    }
  }

  /**
   * Move forward one frame, judge the first prediction, and animate the step.
   * @param {number} [ms] Length of the picture change (Show me uses a shorter one).
   * @returns {Promise<void>} Resolves when the walker has arrived.
   */
  async function step(ms = 360) {
    if (state.frame >= total) { return; }
    const first = state.frame === 0;
    state.frame += 1;
    ladder.progress();
    const drawn = Promise.all([refresh(true, ms), highlightCandidates()]);
    if (first && guess.ready()) {
      const chosen = String(data.steps[0].chosen);
      const right = guess.value() === chosen;
      guess.reveal(chosen, `The walk chose city ${chosen}.`);
      if (!right) { ladder.wrong(); }
      guess.clearChoice();
    }
    await drawn;
    await playFrame();
  }

  /**
   * Show me: advance one step at a time until the end, animating each step.
   * @returns {Promise<boolean>} Resolves at the last step (false if another sequence was already running).
   */
  function autoStep() {
    return lock.run(async () => {
      while (state.frame < total) {
        await step(200);
      }
    });
  }

  stepButton.addEventListener("click", () => { lock.run(step); });
  backButton.addEventListener("click", () => { state.frame -= 1; refresh(true); });
  resetButton.addEventListener("click", () => { state.frame = 0; guess.reset(); refresh(true); });

  narrative.append(
    chapterHead("Fig. 1 debugger", "Step through the paper's worked example",
      `The paper's 9 city network, with its seats. One request wants ${req.n} pairs from city ${req.s} to city ${req.d}.`),
    caption({
      kid: "The heuristic is a fast rule of thumb. It walks toward the goal and picks the neighbour with the best score.",
      student: "The heuristic walks greedily toward the destination. At each step it picks the neighbour with the best ratio of bottleneck capacity to number of hops.",
      expert: "Algorithms 1 to 3 of the paper. The score is alpha_i = min(c(k,i), beta) / (1 + l). Ties go to the lowest city id here; the engine can also break them at random.",
      breaks: "Best only means best within one window. Over many windows, either method can end up ahead.",
    }),
    taskBox("Task: predict the first choice, then step to the end",
      guess.element,
      h("div", { class: "btn-row" }, stepButton, backButton, resetButton),
      counter,
      frameHost,
      ladder.element));

  extra.append(h("p", { class: "stage-hint", text: "Labels on links show seats. The blue tube laid over the links is the path being built. S marks the start, E the end, and alpha is the score of a candidate city." }));
  refresh();
  return () => ladder.dispose();
}

export default { id: "fig1", title: "Fig. 1 debugger", mount };

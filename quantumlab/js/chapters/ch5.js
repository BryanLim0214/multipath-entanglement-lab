/**
 * Chapter 5, "Rush hour": a 2 by 3 grid with limited seats and 3 requests. The viewer draws a road for each
 * request by clicking cities. A JavaScript port of the Python referee checks the answer in plain English.
 * The best answers come from data/rushhour.json, which the exporter solved with qmp.ilp.solve_path.
 */
import { h, caption, predictBox, loadJson } from "../ui.js";
import { createLadder } from "../help-ladder.js";
import { validate, servedRequests, linkKey, seatMap } from "../referee.js";
import { chapterHead, taskBox, outliner } from "./common.js";

const TASK_ID = "ch5-rush";
const SPARE_DELTA = 2; // A21: a request may use at most floor(seats / delta) of a link

/**
 * Where a city sits on the stage: cities 1 to 3 on the top row, 4 to 6 on the bottom row.
 * @param {number} id City id from 1 to 6.
 * @returns {{x: number, y: number}} Scene position.
 */
function cityPosition(id) {
  const column = (id - 1) % 3;
  const row = Math.floor((id - 1) / 3);
  return { x: (column - 1) * 3.6, y: row === 0 ? 1.5 : -1.5 };
}

/**
 * Edges of a node list as link keys, in order.
 * @param {number[]} nodes City ids along a road.
 * @returns {{from: number, to: number, key: string}[]} One entry per step.
 */
function steps(nodes) {
  return nodes.slice(0, -1).map((from, i) => ({ from, to: nodes[i + 1], key: linkKey(from, nodes[i + 1]) }));
}

/**
 * Build the chapter.
 * @param {{narrative: HTMLElement, extra: HTMLElement, stage: object, hints: object}} ctx Room context.
 * @returns {Promise<function(): void>} Cleanup function.
 */
async function mount(ctx) {
  const { narrative, extra, stage, hints } = ctx;
  const data = await loadJson("rushhour.json");
  const state = { inst: 0, mode: "single", spare: false, splitAllowed: false, active: 0, answer: {}, ghost: null, hintOn: false };

  const guess = predictBox({
    name: "ch5-guess",
    legend: "if a request may split over several roads, how many of the 3 requests can be served?",
    options: [1, 2, 3].map((n) => ({ value: String(n), label: `${n} of 3` })),
    onChange: () => { allowButton.disabled = !guess.ready() || state.splitAllowed; },
  });
  const allowButton = h("button", { class: "btn btn-primary", type: "button", text: "Allow split", disabled: true });
  const modeBox = h("fieldset", { hidden: true },
    h("legend", { text: "Roads per request" }),
    ...[["single", "One road per request"], ["split", "Split over roads that share no link"]].map(([value, label]) =>
      h("label", { class: "choice" },
        h("input", { type: "radio", name: "ch5-mode", value, checked: value === "single", onchange: () => setMode(value) }), label)));
  const spareBox = h("input", { type: "checkbox", id: "ch5-spare", onchange: () => { state.spare = spareBox.checked; ladder.progress(); refreshAll(); } });
  const cityRow = h("div", { class: "btn-row", role: "group", "aria-label": "Add a city to the current road" });
  const newRoad = h("button", { class: "btn", type: "button", text: "New road", onclick: () => addRoad() });
  const undo = h("button", { class: "btn", type: "button", text: "Undo last city", onclick: () => undoCity() });
  const clear = h("button", { class: "btn", type: "button", text: "Clear this request", onclick: () => clearRequest() });
  const requestHost = h("div", {});
  const refereeHost = h("div", { "aria-live": "polite" });
  const infoHost = h("p", {});
  const solutionHost = h("div", {});
  const ladder = createLadder({
    taskId: TASK_ID,
    hints,
    /** Task actions that help levels 3 to 5 call. */
    handlers: {
      highlight: (on) => { state.hintOn = on; drawStage(); },
      show: () => { state.ghost = solution().ilp; refreshAll(); },
      doIt: () => { state.ghost = null; applySolution(); },
      similar: () => { nextInstance(); },
    },
  });

  /**
   * The current instance from the exported data.
   * @returns {object} Instance with links, requests and solutions.
   */
  function inst() {
    return data.instances[state.inst];
  }

  /**
   * The exported solution block for the current mode and spare-seat setting.
   * @returns {{served: number, ilp: object[], heuristic: object[], heuristic_served: number}} Solutions.
   */
  function solution() {
    return inst().solutions[`${state.mode}_${state.spare ? "spare" : "off"}`];
  }

  /**
   * The current request.
   * @returns {{id: number, s: number, d: number, n: number}} Request.
   */
  function activeRequest() {
    return inst().requests[state.active];
  }

  /**
   * The roads drawn for a request.
   * @param {number} id Request id.
   * @returns {{nodes: number[], pairs: number}[]} Roads, possibly empty.
   */
  function roadsOf(id) {
    if (!state.answer[id]) {
      state.answer[id] = [];
    }
    return state.answer[id];
  }

  /**
   * The answer in the shape the referee expects.
   * @returns {{request: number, roads: object[]}[]} One entry per request that has a road.
   */
  function answerList() {
    return inst().requests.filter((r) => roadsOf(r.id).length > 0).map((r) => ({ request: r.id, roads: roadsOf(r.id) }));
  }

  /**
   * Whether the last road of the active request already reaches its destination.
   * @returns {boolean} True when it does.
   */
  function lastRoadDone() {
    const roads = roadsOf(activeRequest().id);
    const last = roads[roads.length - 1];
    return Boolean(last) && last.nodes[last.nodes.length - 1] === activeRequest().d;
  }

  /**
   * Add a city to the current road, starting a new road at the request's start city if needed.
   * @param {number} city City id that was clicked.
   * @returns {void}
   */
  function clickCity(city) {
    const req = activeRequest();
    const roads = roadsOf(req.id);
    if (roads.length === 0) {
      roads.push({ nodes: [req.s], pairs: req.n });
    }
    const road = roads[roads.length - 1];
    if (road.nodes[road.nodes.length - 1] === req.d) {
      say(`Road ${roads.length} already reaches city ${req.d}. Press New road to add another, or Undo last city.`);
      return;
    }
    if (road.nodes[road.nodes.length - 1] !== city) {
      road.nodes.push(city);
    }
    ladder.progress();
    refreshAll();
  }

  /**
   * Start another road for the active request (split mode only).
   * @returns {void}
   */
  function addRoad() {
    const req = activeRequest();
    const roads = roadsOf(req.id);
    const used = roads.reduce((sum, r) => sum + r.pairs, 0);
    roads.push({ nodes: [req.s], pairs: Math.max(1, req.n - used) });
    ladder.progress();
    refreshAll();
  }

  /**
   * Remove the last city of the last road, and the road itself when only its start is left.
   * @returns {void}
   */
  function undoCity() {
    const roads = roadsOf(activeRequest().id);
    const road = roads[roads.length - 1];
    if (!road) {
      return;
    }
    road.nodes.pop();
    if (road.nodes.length <= 1) {
      roads.pop();
    }
    refreshAll();
  }

  /**
   * Remove every road of the active request.
   * @returns {void}
   */
  function clearRequest() {
    state.answer[activeRequest().id] = [];
    refreshAll();
  }

  /**
   * Switch between one road and split mode, trimming extra roads when going back to one.
   * @param {string} mode "single" or "split".
   * @returns {void}
   */
  function setMode(mode) {
    state.mode = mode;
    if (mode === "single") {
      inst().requests.forEach((r) => {
        state.answer[r.id] = roadsOf(r.id).slice(0, 1).map((road) => ({ nodes: road.nodes, pairs: r.n }));
      });
    }
    state.ghost = null;
    ladder.progress();
    refreshAll();
  }

  /**
   * Put the exported best answer in place of the viewer's answer (Do it for me).
   * @returns {void}
   */
  function applySolution() {
    state.answer = {};
    solution().ilp.forEach((a) => { state.answer[a.request] = a.roads.map((r) => ({ nodes: [...r.nodes], pairs: r.pairs })); });
    refreshAll();
  }

  /**
   * Move to the next exported instance for "Try a similar one".
   * @returns {void}
   */
  function nextInstance() {
    state.inst = (state.inst + 1) % data.instances.length;
    state.answer = {};
    state.active = 0;
    state.ghost = null;
    refreshAll();
  }

  /**
   * Redraw the grid with seats left on each link, beads for pairs, and the viewer's roads.
   * @returns {void}
   */
  function drawStage() {
    const req = activeRequest();
    const seats = seatMap(inst());
    const load = new Map();
    const mine = new Set();
    inst().requests.forEach((r) => roadsOf(r.id).forEach((road) => steps(road.nodes).forEach((st) => {
      if (seats.has(st.key)) {
        load.set(st.key, (load.get(st.key) || 0) + road.pairs);
        if (r.id === req.id) { mine.add(st.key); }
      }
    })));
    const onRoad = new Set(roadsOf(req.id).flatMap((road) => road.nodes));
    const nodes = [1, 2, 3, 4, 5, 6].map((id) => ({
      id, ...cityPosition(id),
      label: id === req.s ? `${id} start` : id === req.d ? `${id} end` : String(id),
      color: onRoad.has(id) ? "mp" : "ink",
      hint: state.hintOn && (id === req.s || id === req.d),
      onClick: (city) => clickCity(city),
      tabless: true,
    }));
    const links = inst().links.map((l) => {
      const key = linkKey(l.a, l.b);
      const used = load.get(key) || 0;
      return { from: l.a, to: l.b, seats: l.seats, color: "muted", beads: Math.min(used, l.seats),
        beadColor: mine.has(key) ? "mp" : "paper", label: `${l.seats - used}/${l.seats}` };
    });
    if (state.ghost) {
      state.ghost.forEach((a) => a.roads.forEach((road) => steps(road.nodes).forEach((st) => {
        links.push({ from: st.from, to: st.to, seats: road.pairs, color: "ext", lift: 0.6 });
      })));
    }
    stage.show({ nodes, links });
    stage.setAlt(`A grid of 6 cities in 2 rows. Each link shows seats left over seats in total. `
      + `You are drawing request ${req.id}, from city ${req.s} to city ${req.d}, with ${req.n} pairs.`);
  }

  /**
   * Rebuild the list of requests and their roads.
   * @returns {void}
   */
  function renderRequests() {
    const items = inst().requests.map((req, index) => {
      const roads = roadsOf(req.id);
      const rows = roads.map((road, k) => {
        const pairs = state.mode === "split"
          ? h("label", {}, "pairs ", h("input", {
            type: "number", min: 1, max: req.n, value: road.pairs, "aria-label": `Pairs on road ${k + 1} of request ${req.id}`,
            oninput: (e) => { road.pairs = Number(e.target.value) || 0; drawStage(); renderReferee(); },
            onchange: () => refreshAll(),
          }))
          : h("span", { class: "num", text: `${road.pairs} pairs` });
        return h("div", { class: "road-row" }, h("span", { class: "num", text: `Road ${k + 1}: ${road.nodes.join("-")}` }), pairs);
      });
      return h("li", { class: index === state.active ? "is-active" : "" },
        h("p", { class: "req-title" }, `Request ${req.id}: city ${req.s} to city ${req.d}, ${req.n} pairs`),
        h("button", {
          class: "btn btn-small", type: "button", "aria-pressed": String(index === state.active),
          text: index === state.active ? "Drawing this one" : "Draw this one",
          onclick: () => { state.active = index; refreshAll(); },
        }),
        ...rows);
    });
    requestHost.replaceChildren(h("ul", { class: "request-list" }, ...items));
  }

  /**
   * Show the referee's messages and the score, and finish the task when the answer is as good as possible.
   * @returns {void}
   */
  function renderReferee() {
    const options = { delta: state.spare ? SPARE_DELTA : null };
    const answer = answerList();
    const errors = validate(inst(), answer, options);
    const served = servedRequests(inst(), answer, options);
    const sol = solution();
    let headline = "No roads drawn yet.";
    if (answer.length > 0) {
      headline = errors.length === 0
        ? `Legal answer. Requests served: ${served.length} of ${inst().requests.length}.`
        : "Not a legal answer yet. The referee says:";
    }
    refereeHost.replaceChildren(h("p", { text: headline }));
    if (errors.length) {
      refereeHost.append(h("ul", { class: "referee" }, ...errors.map((e) => h("li", { text: e }))));
    }
    infoHost.textContent = `Best possible in this setting (exact solver, ILP): ${sol.served} of ${inst().requests.length}. `
      + `The quick rule of thumb (heuristic) serves ${sol.heuristic_served}.`;
    if (errors.length === 0 && sol.served > 0 && served.length === sol.served) {
      ladder.solve();
      refereeHost.append(h("p", { class: "verdict is-right", text: "This matches the best possible answer." }));
    }
    const nothing = state.ghost
      ? h("div", {}, h("h3", { text: "Best answer (green roads on the picture)" }),
        h("ul", {}, ...state.ghost.map((a) => h("li", { class: "num", text: `Request ${a.request}: ${a.roads.map((r) => `${r.nodes.join("-")} (${r.pairs})`).join(" and ")}` }))),
        state.ghost.length === 0 ? h("p", { text: "No request can be served in this setting." }) : null)
      : null;
    solutionHost.replaceChildren(...(nothing ? [nothing] : []));
  }

  /**
   * Update every part of the page after a change.
   * @returns {void}
   */
  function refreshAll() {
    const req = activeRequest();
    const roads = roadsOf(req.id);
    newRoad.disabled = state.mode !== "split" || roads.length === 0 || !lastRoadDone();
    undo.disabled = roads.length === 0;
    clear.disabled = roads.length === 0;
    allowButton.disabled = !guess.ready() || state.splitAllowed;
    modeBox.hidden = !state.splitAllowed;
    renderRequests();
    renderReferee();
    drawStage();
  }

  /**
   * Announce a short message in the referee area.
   * @param {string} text Message.
   * @returns {void}
   */
  function say(text) {
    refereeHost.replaceChildren(h("p", { text }));
  }

  allowButton.addEventListener("click", () => {
    const actual = String(inst().solutions.split_off.served);
    const right = guess.value() === actual;
    state.splitAllowed = true;
    guess.reveal(actual, `With split allowed the best possible answer serves ${actual} of 3. With one road each it serves ${inst().solutions.single_off.served}.`);
    if (right) { ladder.progress(); } else { ladder.wrong(); }
    guess.clearChoice();
    refreshAll();
    modeBox.querySelector('input[value="split"]').focus();
  });
  for (let id = 1; id <= 6; id += 1) {
    cityRow.append(h("button", { class: "btn btn-small", type: "button", text: `City ${id}`, onclick: () => clickCity(id) }));
  }

  narrative.append(
    chapterHead("Chapter 5 of 5", "Rush hour",
      "Three requests want pairs at the same time, and every link has a fixed number of seats. A request is served only if all its pairs fit."),
    caption({
      kid: "A request says: send n pairs from here to there before my deadline. If no route has enough seats, the request is turned away. That is called blocked.",
      student: "Single-path routing puts all n pairs on one route. Multipath splits them over several routes that share no link. A pair is never cut in half.",
      expert: "Sum over k of pi^rk = n^r. The paths of one request are edge-disjoint, and the sum over r and k of beta stays at or below C_ij on every link. BR = (|R| - sum of X^r) / |R|.",
      breaks: "A pair is never cut in half. Each pair travels whole, on a single route.",
    }),
    taskBox("Task: serve as many requests as the best possible answer",
      h("p", {}, "Pick a request, then press city buttons in order to draw its road. The picture shows seats left over seats in total on each link. Blue beads are pairs on your current request."),
      requestHost,
      cityRow,
      h("div", { class: "btn-row" }, newRoad, undo, clear),
      refereeHost,
      infoHost,
      guess.element,
      h("div", { class: "btn-row" }, allowButton),
      modeBox,
      h("div", { class: "field" }, h("label", {}, spareBox, "Keep a spare seat (δ = 2): one request takes at most half of a link's seats")),
      solutionHost,
      ladder.element));
  extra.append(h("p", { class: "stage-hint", text: "Link labels show seats left over seats in total. Thicker tubes have more seats. Green tubes above the grid are the best answer." }));

  refreshAll();
  return () => ladder.dispose();
}

export default { id: "ch5", number: 5, title: "Rush hour", mount };

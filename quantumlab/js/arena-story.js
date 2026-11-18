/**
 * Plain-language stories for the Arena: what happened to one request on each side, and why it was blocked
 * when that can be known. It builds text only. The numbers come from arena-model.js and arena.json.
 */
import { blockedFacts } from "./arena-model.js";

/**
 * "1 pair" or "3 pairs".
 * @param {number} n Count.
 * @returns {string} Count with the right noun.
 */
export function pairsText(n) {
  return `${n} pair${n === 1 ? "" : "s"}`;
}

/**
 * One road as text, such as "3-2-5 (2 pairs)".
 * @param {{nodes: number[], pairs: number}} road A road from arena.json.
 * @returns {string} Text.
 */
export function roadText(road) {
  return `${road.nodes.join("-")} (${pairsText(road.pairs)})`;
}

/**
 * The rules a trace was run with, read from its name.
 * @param {string} traceName Name such as "MP-Heu-d1" or "SP-ILP".
 * @param {{spare_seat_delta: number, max_middle_on: number, max_middle_off: number}} config Setup from arena.json.
 * @returns {{single: boolean, exact: boolean, delta: number, maxMiddle: number}} Single road only, exact solver, spare-seat divisor, hop limit.
 */
export function rulesOf(traceName, config) {
  const exact = traceName.includes("ILP");
  return {
    single: traceName.startsWith("SP"),
    exact,
    delta: exact || traceName.includes("-d1") ? 1 : config.spare_seat_delta, // A21
    maxMiddle: traceName.includes("-nohop") ? config.max_middle_off : config.max_middle_on, // A5
  };
}

/**
 * The reason a request was blocked, in a kid line, a student line and an expert line.
 * @param {object} ctx run, trace, traceName, config, id and the last window (from 0) the request waited in.
 * @returns {{kid: string, student: string, expert: string}} The three lines for this side.
 */
function blockedStory(ctx) {
  const rules = rulesOf(ctx.traceName, ctx.config);
  const facts = blockedFacts({ run: ctx.run, trace: ctx.trace, config: ctx.config, id: ctx.id, w: ctx.w,
    delta: rules.delta, maxMiddle: rules.maxMiddle, atItsTurn: !rules.exact });
  const when = rules.exact ? `at the end of window ${ctx.w + 1}, its last chance` : `when its turn came in window ${ctx.w + 1}, its last chance`;
  const road = facts.bestRoad;
  const roadFits = road !== null && road.bottleneck >= facts.needSingle;
  const roadLine = road === null
    ? `No road from city ${facts.req.s} to city ${facts.req.d} stays within the limit of ${rules.maxMiddle} middle cities.`
    : `The widest road, ${road.nodes.join("-")}, had ${road.bottleneck} free seats at its thinnest link, and ${pairsText(facts.req.n)} need ${facts.needSingle}.`;
  const splitFits = facts.bound >= facts.req.n;
  const expert = `Seats left ${when}: widest single road ${road ? road.nodes.join("-") : "none"}, ${road ? road.bottleneck : 0} free at its thinnest link, `
    + `needs n x delta = ${facts.needSingle}. Upper bound on pairs by splitting (floor(seats / delta) per link, ignoring the hop limit and the disjoint-roads rule): ${facts.bound} of ${facts.req.n}. `
    + `Hop limit ${rules.maxMiddle} middle cities, delta = ${rules.delta} (A21).`;
  if (rules.single) {
    if (!roadFits) {
      return { kid: "blocked it, because no single road had enough free seats.", student: `Blocked. ${roadLine}`, expert };
    }
    return {
      kid: rules.exact ? "left it out of its plan." : "blocked it, because the road search did not pick the one wide road.",
      student: `Blocked, although a wide enough road existed on paper. ${roadLine} ${rules.exact ? "The exact solver left this request out of its plan." : "The quick rule of thumb did not find that road."}`,
      expert,
    };
  }
  if (!splitFits) {
    return { kid: "blocked it, because even all the roads together had too few free seats.",
      student: `Blocked. Even splitting over every road could carry at most ${pairsText(facts.bound)} of the ${facts.req.n} needed (${when}).`, expert };
  }
  return {
    kid: rules.exact ? "left it out of its plan." : "blocked it. The seats were there, but the road search did not find a legal split.",
    student: `Blocked. Splitting could carry up to ${pairsText(facts.bound)} on paper, so seats alone were enough. `
      + `The roads of one request must share no link and stay within ${rules.maxMiddle} middle cities, and ${rules.exact ? "the exact solver chose a plan without it" : "the quick rule of thumb found no legal split"}.`,
    expert,
  };
}

/**
 * What happened to one request on one side of the Arena.
 * @param {object} ctx run, trace, traceName, config, fates (Map), id.
 * @returns {{kid: string, student: string, expert: string, blocked: boolean}} The three lines and whether it was blocked.
 */
export function sideStory(ctx) {
  const fate = ctx.fates.get(ctx.id);
  if (fate.servedWindow !== null) {
    const roads = fate.alloc.paths;
    const how = roads.length === 1 ? `on road ${roadText(roads[0])}` : `split over ${roads.length} roads: ${roads.map(roadText).join(" and ")}`;
    return { kid: `served it in window ${fate.servedWindow + 1}.`, student: `Served in window ${fate.servedWindow + 1}, ${how}.`,
      expert: `Seats are used one per pair on every link of a road (A8).`, blocked: false };
  }
  if (fate.firstPending === null) {
    return { kid: "could not serve it, because it never fits inside one window.",
      student: "Blocked. The request never fits entirely inside a window (A14), so no plan can serve it.", expert: "Eligible windows: none.", blocked: true };
  }
  return { ...blockedStory({ ...ctx, w: fate.lastPending }), blocked: true };
}

/**
 * The caption lines for the whole request, joining the single-path and multipath stories.
 * @param {{id: number, s: number, d: number, n: number, a: number, h: number, b: number}} req The request.
 * @param {{name: string, kidName: string, story: object}[]} sides The two sides, left first.
 * @returns {{kid: string, student: string, expert: string, breaks: string}} Caption text for ui.caption.
 */
export function requestCaption(req, sides) {
  const head = `Request ${req.id} wanted ${pairsText(req.n)} between city ${req.s} and city ${req.d}.`;
  const kidJoin = sides.map((side) => `${side.kidName} ${side.story.kid}`).join(" ");
  const studentJoin = sides.map((side) => `${side.name}: ${side.story.student}`).join(" ");
  return {
    kid: `${head} ${kidJoin}`,
    student: `Request ${req.id} arrives in slot ${req.a}, takes ${req.h} slot${req.h === 1 ? "" : "s"}, and its deadline is slot ${req.b}. ${studentJoin}`,
    expert: sides.map((side) => `${side.name}: ${side.story.expert}`).join(" "),
    breaks: "Seats are counted when the request's turn comes in the window, the way the heuristic works. The exact solver has no turns, so its numbers are the seats left at the end of the window.",
  };
}

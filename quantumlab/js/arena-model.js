/**
 * Replay logic for the Arena, with no page elements: which request has which fate in which window,
 * the seats left on each link, the counters, what changes when a rule is switched off, and the facts
 * behind a blocked request. tools/arena_check.mjs runs these functions against the exported numbers.
 */
import { linkKey } from "./referee.js";

const TURNED_AWAY = new Set(["turned-away", "blocked-now"]);
const BLOCKED = new Set(["blocked-now", "blocked-earlier", "never-fits"]);

/**
 * Name of the trace for a multipath-side setting, matching variant_name in tools/export_data.py.
 * @param {string} pair "Heu" or "ILP".
 * @param {{split: boolean, spare: boolean, hop: boolean}} rules Which rules are on.
 * @returns {string} Trace name such as "MP-Heu", "MP-Heu-d1" or "SP-Heu-nohop".
 */
export function rightTraceName(pair, rules) {
  if (pair === "ILP") {
    return "MP-ILP";
  }
  return `${rules.split ? "MP" : "SP"}-Heu${rules.spare ? "" : "-d1"}${rules.hop ? "" : "-nohop"}`;
}

/**
 * Name of the trace for the single-path side.
 * @param {string} pair "Heu" or "ILP".
 * @returns {string} "SP-Heu" or "SP-ILP".
 */
export function leftTraceName(pair) {
  return pair === "ILP" ? "SP-ILP" : "SP-Heu";
}

/**
 * The links of a grid, as city pairs.
 * @param {number} rows Grid rows.
 * @param {number} cols Grid columns.
 * @returns {number[][]} Pairs [a, b] with a < b, cities numbered row by row from 1 (like model.grid).
 */
export function gridLinks(rows, cols) {
  const links = [];
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const node = r * cols + c + 1;
      if (c + 1 < cols) { links.push([node, node + 1]); }
      if (r + 1 < rows) { links.push([node, node + cols]); }
    }
  }
  return links;
}

/**
 * Requests as objects, by id.
 * @param {{requests: number[][]}} run One (q, seed) run from arena.json.
 * @returns {Map<number, {id: number, s: number, d: number, n: number, a: number, h: number, b: number}>} Lookup.
 */
export function requestMap(run) {
  return new Map(run.requests.map(([id, s, d, n, a, h, b]) => [id, { id, s, d, n, a, h, b }]));
}

/**
 * For every request: the window where it was placed, its roads, and its first and last window as a waiting request.
 * @param {object} run One run from arena.json.
 * @param {{windows: object[]}} trace One trace of that run.
 * @returns {Map<number, {servedWindow: (number|null), alloc: (object|null), firstPending: (number|null), lastPending: (number|null)}>} Fates by request id (windows counted from 0).
 */
export function computeFates(run, trace) {
  const fates = new Map(run.requests.map((r) => [r[0], { servedWindow: null, alloc: null, firstPending: null, lastPending: null }]));
  trace.windows.forEach((win, w) => {
    win.eligible.forEach((id) => {
      const fate = fates.get(id);
      if (fate.firstPending === null) { fate.firstPending = w; }
      fate.lastPending = w;
    });
    win.allocations.forEach((alloc) => {
      const fate = fates.get(alloc.request);
      fate.servedWindow = w;
      fate.alloc = alloc;
    });
  });
  return fates;
}

/**
 * Where a request stands when window w has just been decided.
 * @param {{servedWindow: (number|null), firstPending: (number|null), lastPending: (number|null)}} fate Fate of one request.
 * @param {number} w Window index from 0.
 * @returns {string} One of served-now, served-earlier, turned-away, blocked-now, blocked-earlier, not-open, never-fits.
 */
export function statusAt(fate, w) {
  if (fate.servedWindow !== null && fate.servedWindow < w) { return "served-earlier"; }
  if (fate.servedWindow === w) { return "served-now"; }
  if (fate.firstPending === null) { return "never-fits"; }
  if (w < fate.firstPending) { return "not-open"; }
  if (fate.servedWindow === null && w > fate.lastPending) { return "blocked-earlier"; }
  return fate.servedWindow === null && w === fate.lastPending ? "blocked-now" : "turned-away";
}

/**
 * Whether the request was refused in this very window (it may still get a later window).
 * @param {string} status A value from statusAt.
 * @returns {boolean} True for turned-away and blocked-now.
 */
export function isTurnedAway(status) {
  return TURNED_AWAY.has(status);
}

/**
 * Whether the request is lost for good by this window.
 * @param {string} status A value from statusAt.
 * @returns {boolean} True for blocked-now, blocked-earlier and never-fits.
 */
export function isBlocked(status) {
  return BLOCKED.has(status);
}

/**
 * The counters shown beside the picture after window w.
 * @param {Map<number, object>} fates Fates from computeFates.
 * @param {number} w Window index from 0.
 * @returns {{served: number, blocked: number, waiting: number, total: number, ratio: number}} Counts and blocking ratio so far.
 */
export function countersAt(fates, w) {
  let served = 0;
  let blocked = 0;
  for (const fate of fates.values()) {
    const status = statusAt(fate, w);
    if (status === "served-now" || status === "served-earlier") {
      served += 1;
    } else if (isBlocked(status)) {
      blocked += 1;
    }
  }
  const total = fates.size;
  return { served, blocked, waiting: total - served - blocked, total, ratio: total ? blocked / total : 0 };
}

/**
 * Seats on every link in window w, after the placements of that window.
 * @param {object} run One run from arena.json.
 * @param {{windows: object[]}} trace One trace of that run.
 * @param {number} w Window index from 0.
 * @returns {{cap: Map<string, number>, used: Map<string, number>, left: Map<string, number>}} Seats this round, pairs placed, and seats left, by link key.
 */
export function windowSeats(run, trace, w) {
  const cap = new Map(Object.entries(run.capacity[w]));
  const used = new Map([...cap.keys()].map((key) => [key, 0]));
  trace.windows[w].allocations.forEach((alloc) => alloc.paths.forEach((road) => {
    for (let i = 0; i + 1 < road.nodes.length; i += 1) {
      const key = linkKey(road.nodes[i], road.nodes[i + 1]);
      used.set(key, used.get(key) + road.pairs); // A8: seats consumed = pairs carried
    }
  }));
  const left = new Map([...cap].map(([key, seats]) => [key, seats - used.get(key)]));
  return { cap, used, left };
}

/**
 * Windows (counted from 1) in which a request fits entirely, like model.eligible_windows (A14).
 * @param {{a: number, h: number, b: number}} req The request.
 * @param {number} T Number of slots.
 * @param {number} tc Slots per window.
 * @returns {number[]} Window numbers from 1.
 */
export function eligibleWindows(req, T, tc) {
  const out = [];
  for (let w = 1; w <= Math.ceil(T / tc); w += 1) {
    const start = (w - 1) * tc + 1;
    const end = Math.min(w * tc, T);
    if (Math.max(req.a, start) + req.h - 1 <= Math.min(req.b, end)) {
      out.push(w);
    }
  }
  return out;
}

/**
 * The order the heuristic tries waiting requests in window w: highest priority, then earlier arrival, then id (A16).
 * @param {Map<number, object>} requests Requests by id.
 * @param {number[]} pending Ids of the requests waiting in this window.
 * @param {number} w Window index from 0.
 * @param {{T: number, tc: number}} config Setup with T and tc.
 * @returns {number[]} The ids in trying order.
 */
export function heuristicOrder(requests, pending, w, config) {
  /** Priority of a request in this window: its position among its eligible windows over their count. */
  const rho = (id) => {
    const windows = eligibleWindows(requests.get(id), config.T, config.tc);
    return (windows.indexOf(w + 1) + 1) / windows.length;
  };
  return [...pending].sort((x, y) => (rho(y) - rho(x)) || (requests.get(x).a - requests.get(y).a) || (x - y));
}

/**
 * Requests whose fate differs between two traces of the same run.
 * @param {{never_placed: number[]}} base The trace to compare against.
 * @param {{never_placed: number[]}} other The trace being looked at.
 * @returns {{newlyServed: number[], newlyBlocked: number[]}} Ids blocked in base but served in other, and the reverse.
 */
export function fateChanges(base, other) {
  const was = new Set(base.never_placed);
  const now = new Set(other.never_placed);
  /** Ids in set a that are not in set b, in order. */
  const ids = (a, b) => [...a].filter((id) => !b.has(id)).sort((x, y) => x - y);
  return { newlyServed: ids(was, now), newlyBlocked: ids(now, was) };
}

/**
 * The first request (from window `from` onward, wrapping round) that the right side serves in that window
 * while the left side turns it away in the same window.
 * @param {Map<number, object>} leftFates Fates on the single-path side.
 * @param {Map<number, object>} rightFates Fates on the multipath side.
 * @param {number} from Window index to start at.
 * @param {number} windowCount Number of windows.
 * @returns {{w: number, id: number}|null} The window and request, or null if there is none.
 */
export function findRightWins(leftFates, rightFates, from, windowCount) {
  for (let k = 0; k < windowCount; k += 1) {
    const w = (from + k) % windowCount;
    for (const [id, fate] of rightFates) {
      if (statusAt(fate, w) === "served-now" && isTurnedAway(statusAt(leftFates.get(id), w))) {
        return { w, id };
      }
    }
  }
  return null;
}

/**
 * Every simple road between two cities, as city lists, with at most maxMiddle middle cities.
 * @param {number[][]} links Grid links.
 * @param {number} s Start city.
 * @param {number} d End city.
 * @param {number} maxMiddle Most middle cities allowed (the hop limit).
 * @returns {number[][]} Roads from s to d.
 */
function simpleRoads(links, s, d, maxMiddle) {
  const next = new Map();
  links.forEach(([a, b]) => {
    next.set(a, [...(next.get(a) || []), b]);
    next.set(b, [...(next.get(b) || []), a]);
  });
  const roads = [];
  /** Extend a road one city at a time, stopping at the destination or the hop limit. */
  const walk = (road) => {
    const last = road[road.length - 1];
    if (last === d) { roads.push(road); return; }
    if (road.length - 1 > maxMiddle) { return; }
    for (const city of next.get(last) || []) {
      if (!road.includes(city)) { walk([...road, city]); }
    }
  };
  walk([s]);
  return roads;
}

/**
 * Largest number of pairs any set of roads could carry when each link offers floor(seats / delta),
 * by augmenting paths. It ignores the hop limit and the disjoint-roads rule, so it is an upper bound.
 * @param {number[][]} links Grid links.
 * @param {Map<string, number>} seats Seats left per link key.
 * @param {number} s Start city.
 * @param {number} d End city.
 * @param {number} delta Spare-seat divisor (A21).
 * @returns {number} Upper bound on the pairs that fit.
 */
function pairsUpperBound(links, seats, s, d, delta) {
  const room = new Map();
  links.forEach(([a, b]) => {
    const each = Math.floor((seats.get(linkKey(a, b)) || 0) / delta);
    room.set(`${a}>${b}`, each);
    room.set(`${b}>${a}`, each);
  });
  const cities = [...new Set(links.flat())].sort((x, y) => x - y);
  let flow = 0;
  for (;;) {
    const from = new Map([[s, null]]);
    const queue = [s];
    while (queue.length && !from.has(d)) {
      const u = queue.shift();
      cities.forEach((v) => {
        if (!from.has(v) && (room.get(`${u}>${v}`) || 0) > 0) { from.set(v, u); queue.push(v); }
      });
    }
    if (!from.has(d)) { return flow; }
    let push = Infinity;
    for (let v = d; from.get(v) !== null; v = from.get(v)) { push = Math.min(push, room.get(`${from.get(v)}>${v}`)); }
    for (let v = d; from.get(v) !== null; v = from.get(v)) {
      const u = from.get(v);
      room.set(`${u}>${v}`, room.get(`${u}>${v}`) - push);
      room.set(`${v}>${u}`, room.get(`${v}>${u}`) + push);
    }
    flow += push;
  }
}

/**
 * The facts behind a request that was turned away in window w: the seats left when its turn came,
 * its widest single road, and an upper bound on what splitting could carry.
 * @param {object} args Everything needed: run, trace, config, id, w (from 0), delta, maxMiddle, atItsTurn.
 *   atItsTurn is true for the heuristic (it tries requests one by one), false for the exact solver.
 * @returns {{seats: Map<string, number>, bestRoad: ({nodes: number[], bottleneck: number}|null), needSingle: number, needSplit: number, bound: number, req: object}} The facts.
 */
export function blockedFacts({ run, trace, config, id, w, delta, maxMiddle, atItsTurn }) {
  const requests = requestMap(run);
  const req = requests.get(id);
  const seats = new Map(Object.entries(run.capacity[w]));
  const win = trace.windows[w];
  const before = atItsTurn ? heuristicOrder(requests, win.eligible, w, config) : null;
  const ahead = atItsTurn ? new Set(before.slice(0, before.indexOf(id))) : null;
  win.allocations.forEach((alloc) => {
    if (ahead && !ahead.has(alloc.request)) { return; }
    alloc.paths.forEach((road) => {
      for (let i = 0; i + 1 < road.nodes.length; i += 1) {
        const key = linkKey(road.nodes[i], road.nodes[i + 1]);
        seats.set(key, seats.get(key) - road.pairs);
      }
    });
  });
  const links = [...seats.keys()].map((key) => key.split("-").map(Number));
  let bestRoad = null;
  simpleRoads(links, req.s, req.d, maxMiddle).forEach((nodes) => {
    const bottleneck = Math.min(...nodes.slice(0, -1).map((u, i) => seats.get(linkKey(u, nodes[i + 1]))));
    if (!bestRoad || bottleneck > bestRoad.bottleneck) { bestRoad = { nodes, bottleneck }; }
  });
  return { seats, bestRoad, needSingle: req.n * delta, needSplit: req.n,
    bound: pairsUpperBound(links, seats, req.s, req.d, delta), req };
}

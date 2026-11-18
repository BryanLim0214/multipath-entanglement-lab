/**
 * JavaScript port of the referee in src/qmp/core.py (validate). It checks a hand-drawn answer for
 * Rush hour and returns the same plain-English messages. It touches no page elements.
 */

/**
 * Key for an undirected link, smaller city first, like core.edge.
 * @param {number} u One city.
 * @param {number} v The other city.
 * @returns {string} Text such as "2-5".
 */
export function linkKey(u, v) {
  return u < v ? `${u}-${v}` : `${v}-${u}`;
}

/**
 * Seats per link from an instance.
 * @param {{links: {a: number, b: number, seats: number}[]}} instance Rush hour instance.
 * @returns {Map<string, number>} Link key to seats.
 */
export function seatMap(instance) {
  return new Map(instance.links.map((l) => [linkKey(l.a, l.b), l.seats]));
}

/**
 * Check one road against the rules that belong to a single request.
 * @param {object} ctx Shared state: request, seats, errors, taken, and used.
 * @param {{nodes: number[], pairs: number}} road The road to check.
 * @param {number} k Road number starting at 1.
 * @returns {number} Pairs carried (counted even if the road is wrong).
 */
function checkRoad(ctx, road, k) {
  const { request: req, seats, errors, taken, used } = ctx;
  const { nodes, pairs } = road;
  if (pairs < 1) {
    errors.push(`Request ${req.id}, road ${k}: every road must carry at least 1 pair.`);
  }
  if (nodes.length === 0 || nodes[0] !== req.s || nodes[nodes.length - 1] !== req.d) {
    errors.push(`Request ${req.id}, road ${k}: must start at ${req.s} and end at ${req.d}.`);
    return pairs;
  }
  if (new Set(nodes).size !== nodes.length) {
    errors.push(`Request ${req.id}, road ${k}: visits a city twice (${nodes.join("-")}).`);
  }
  for (let i = 0; i + 1 < nodes.length; i += 1) {
    const key = linkKey(nodes[i], nodes[i + 1]);
    if (!seats.has(key)) {
      errors.push(`Request ${req.id}, road ${k}: there is no link ${key}.`);
      continue;
    }
    if (taken.has(key)) {
      errors.push(`Request ${req.id}: roads ${taken.get(key)} and ${k} both use link ${key}.`);
    }
    taken.set(key, k);
    used.set(key, (used.get(key) || 0) + pairs);
  }
  return pairs;
}

/**
 * Spare-seat rule: one request may use at most floor(seats / delta) of a link (A21).
 * @param {Map<string, number>} seats Seats per link.
 * @param {number} requestId Request being checked.
 * @param {Map<string, number>} loadOfRequest Pairs this request puts on each link.
 * @param {number} delta The spare-seat divisor, 2 in the paper.
 * @param {string[]} errors List that receives new messages.
 * @returns {void}
 */
function checkSpareSeat(seats, requestId, loadOfRequest, delta, errors) {
  for (const [key, load] of [...loadOfRequest].sort()) {
    const allowed = Math.floor(seats.get(key) / delta);
    if (load > allowed) {
      errors.push(`Request ${requestId} puts ${load} pairs on link ${key}, but keeping a spare seat `
        + `(δ = ${delta}) allows at most ${allowed} of its ${seats.get(key)} seats.`);
    }
  }
}

/**
 * Every rule an answer breaks, in plain words. An empty list means the answer is legal.
 * Mirrors core.validate. The middle-city (fidelity) rule is left out because a 2x3 grid has at
 * most 4 middle cities, which every Rush hour request allows.
 * @param {{links: object[], requests: {id: number, s: number, d: number, n: number}[]}} instance Rush hour instance.
 * @param {{request: number, roads: {nodes: number[], pairs: number}[]}[]} answer One entry per routed request.
 * @param {{delta?: number|null}} [options] delta is 2 when the spare-seat rule is on.
 * @returns {string[]} Messages.
 */
export function validate(instance, answer, options = {}) {
  const delta = options.delta || null;
  const seats = seatMap(instance);
  const byId = new Map(instance.requests.map((r) => [r.id, r]));
  const errors = [];
  const used = new Map();
  const seen = new Set();
  for (const alloc of answer) {
    const request = byId.get(alloc.request);
    if (!request) {
      errors.push(`Request ${alloc.request} is not waiting in this round.`);
      continue;
    }
    if (seen.has(request.id)) {
      errors.push(`Request ${request.id} was placed twice.`);
    }
    seen.add(request.id);
    if (alloc.roads.length === 0) {
      errors.push(`Request ${request.id} was placed with no road.`);
    }
    const ctx = { request, seats, errors, taken: new Map(), used };
    const before = new Map(used);
    let total = 0;
    alloc.roads.forEach((road, i) => { total += checkRoad(ctx, road, i + 1); });
    if (total !== request.n) {
      errors.push(`Request ${request.id}: promised ${request.n} pairs but routed ${total}. All or nothing.`);
    }
    if (delta) {
      const mine = new Map();
      for (const [key, load] of used) {
        mine.set(key, load - (before.get(key) || 0));
      }
      checkSpareSeat(seats, request.id, mine, delta, errors);
    }
  }
  for (const [key, load] of [...used].sort()) {
    const cap = seats.get(key) || 0;
    if (load > cap) {
      errors.push(`Link ${key} has ${cap} seats this round, but ${load} pairs were routed over it.`);
    }
  }
  return errors;
}

/**
 * Requests whose own roads are legal when checked alone (a request still waiting for roads is not served).
 * @param {object} instance Rush hour instance.
 * @param {object[]} answer Answer as for validate.
 * @param {{delta?: number|null}} [options] Same options as validate.
 * @returns {number[]} Ids of the requests that are completely and legally routed.
 */
export function servedRequests(instance, answer, options = {}) {
  return answer
    .filter((alloc) => validate(instance, [alloc], options).length === 0)
    .map((alloc) => alloc.request);
}

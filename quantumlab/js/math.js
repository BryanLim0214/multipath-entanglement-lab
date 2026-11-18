/**
 * Small exact formulas shared by the chapters: binomial bars, Werner fidelity, and a seeded dice roller.
 * Nothing here touches the page, so it can be checked from the command line.
 */

/**
 * Binomial coefficient "n choose k" as a plain number (n is small here).
 * @param {number} n Number of attempts.
 * @param {number} k Number of successes.
 * @returns {number} The coefficient.
 */
export function choose(n, k) {
  let result = 1;
  for (let i = 1; i <= k; i += 1) {
    result = (result * (n - k + i)) / i;
  }
  return Math.round(result);
}

/**
 * Exact Binomial(m, q) probabilities for 0..m successes.
 * @param {number} m Attempts per road (M in the paper).
 * @param {number} q Chance that one attempt lands.
 * @returns {number[]} Array of length m + 1 whose entries add up to 1.
 */
export function binomialPmf(m, q) {
  const bars = [];
  for (let k = 0; k <= m; k += 1) {
    bars.push(choose(m, k) * q ** k * (1 - q) ** (m - k));
  }
  return bars;
}

/**
 * Werner parameter of a pair with fidelity F (assumption A5).
 * @param {number} fidelity The pair's fidelity F.
 * @returns {number} w = (4F - 1) / 3.
 */
export function wernerW(fidelity) {
  return (4 * fidelity - 1) / 3;
}

/**
 * Fidelity after ideal swapping over several links of equal fidelity (A5).
 * @param {number} fidelity Fidelity F of one link.
 * @param {number} links Number of links L on the path.
 * @returns {number} F_L = (3 w^L + 1) / 4.
 */
export function pathFidelity(fidelity, links) {
  return (3 * wernerW(fidelity) ** links + 1) / 4;
}

/**
 * Largest number of middle cities whose path fidelity still reaches the threshold (A5).
 * @param {number} fidelity Fidelity F of one link.
 * @param {number} threshold Minimum end-to-end fidelity f (above 0.25).
 * @returns {number} Middle cities allowed, or -1 if even one link is too weak.
 */
export function maxIntermediate(fidelity, threshold) {
  if (pathFidelity(fidelity, 1) < threshold) {
    return -1;
  }
  let links = 1;
  while (pathFidelity(fidelity, links + 1) >= threshold) {
    links += 1;
  }
  return links - 1;
}

/**
 * Seeded random number generator (mulberry32), so every run with the same seed repeats.
 * @param {number} seed Any integer.
 * @returns {function(): number} Function returning a number in [0, 1) on each call.
 */
export function seededRandom(seed) {
  let state = seed >>> 0;
  return function next() {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Throw m paper planes, each landing with chance q.
 * @param {function(): number} random Random source from seededRandom.
 * @param {number} m Attempts.
 * @param {number} q Chance per attempt.
 * @returns {boolean[]} One entry per attempt, true when it landed.
 */
export function throwAttempts(random, m, q) {
  const landed = [];
  for (let i = 0; i < m; i += 1) {
    landed.push(random() < q);
  }
  return landed;
}

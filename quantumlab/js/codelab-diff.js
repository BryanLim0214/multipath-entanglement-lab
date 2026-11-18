/**
 * Line-by-line comparison of two texts for the Code Lab's "Show me" level. It touches no page elements.
 */

/**
 * Align two texts line by line using the longest common subsequence of equal lines.
 * @param {string} mine The player's text.
 * @param {string} theirs The working solution's text.
 * @returns {{left: (string|null), right: (string|null), mark: string}[]} Rows in order. mark is "same", "minus" (only in mine), "plus" (only in the solution) or "change" (both differ here).
 */
export function alignLines(mine, theirs) {
  const a = mine.replace(/\s+$/, "").split("\n");
  const b = theirs.replace(/\s+$/, "").split("\n");
  const table = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      table[i][j] = a[i] === b[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const rows = [];
  let i = 0;
  let j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      rows.push({ left: a[i], right: b[j], mark: "same" });
      i += 1;
      j += 1;
      continue;
    }
    const onlyMine = [];
    const onlyTheirs = [];
    while (i < a.length && (j >= b.length || a[i] !== b[j]) && (j >= b.length || table[i + 1][j] >= table[i][j + 1])) {
      onlyMine.push(a[i]);
      i += 1;
    }
    while (j < b.length && (i >= a.length || a[i] !== b[j]) && (i >= a.length || table[i][j + 1] > table[i + 1][j])) {
      onlyTheirs.push(b[j]);
      j += 1;
    }
    const paired = Math.min(onlyMine.length, onlyTheirs.length);
    for (let k = 0; k < paired; k += 1) {
      rows.push({ left: onlyMine[k], right: onlyTheirs[k], mark: "change" });
    }
    onlyMine.slice(paired).forEach((line) => rows.push({ left: line, right: null, mark: "minus" }));
    onlyTheirs.slice(paired).forEach((line) => rows.push({ left: null, right: line, mark: "plus" }));
  }
  return rows;
}

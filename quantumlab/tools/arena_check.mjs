/**
 * Runs the Arena's JavaScript replay logic over data/arena.json and prints, for every trace, what the page
 * would show at the last window, so tests/test_quantumlab_data.py can compare it with the exported numbers.
 * Usage: node arena_check.mjs path/to/arena.json
 */
import { readFileSync } from "node:fs";
import { computeFates, countersAt, windowSeats, heuristicOrder, requestMap } from "../js/arena-model.js";

const data = JSON.parse(readFileSync(process.argv[2], "utf-8"));
const out = [];
for (const [key, run] of Object.entries(data.runs)) {
  const requests = requestMap(run);
  for (const [name, trace] of Object.entries(run.traces)) {
    const fates = computeFates(run, trace);
    const last = trace.windows.length - 1;
    const counts = countersAt(fates, last);
    let orderOk = true;
    let seatsOk = true;
    trace.windows.forEach((win, w) => {
      const placed = win.allocations.map((a) => a.request);
      if (name.includes("Heu")) {
        const order = heuristicOrder(requests, win.eligible, w, data.config).filter((id) => placed.includes(id));
        orderOk = orderOk && JSON.stringify(order) === JSON.stringify(placed);
      }
      seatsOk = seatsOk && [...windowSeats(run, trace, w).left.values()].every((seats) => seats >= 0);
    });
    out.push({ run: key, trace: name, ...counts, neverPlaced: trace.never_placed.length,
      blockingRatio: trace.blocking_ratio, orderOk, seatsOk });
  }
}
process.stdout.write(JSON.stringify(out));

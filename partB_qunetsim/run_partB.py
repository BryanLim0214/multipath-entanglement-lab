"""Runs the Part B experiments E1 to E4 on QuNetSim in a process pool (MAX_WORKERS = 3 workers) and writes
results/partB.csv, results/partB_analytic.csv and results/partB_timeouts.csv. Run from the project root:
python -m partB_qunetsim.run_partB [--smoke | --crosscheck | --analytic-only]
"""
import argparse
import csv
import itertools
import json
import os
import pathlib
import random
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from partB_qunetsim import analytic, routing, topologies           # noqa: E402
from partB_qunetsim.budget import Budget, dry_request              # noqa: E402
from partB_qunetsim.delivery import serve_request                  # noqa: E402

RESULTS = ROOT / "results"
MAX_WORKERS = 3                       # QuNetSim starts a process per qubit; keep memory bounded (docs/TROUBLESHOOTING.md)
SEEDS = list(range(1, 21))            # 20 seeds per setting
QS = [0.5, 0.6, 0.7, 0.8, 0.9]
WAIT_BUDGET = 10.0                    # s, E1-E3: waits are never expected to expire (an expired wait counts as failure)
WAIT_DROP = 2.0                       # s, E4: ACK and fetch waits; an expired wait is a failure
BIG_M = 100                           # E4: the attempt budget never binds (q = 1, failures come from the simulator)
CSV_COLUMNS = ["experiment", "topology", "method", "k", "q", "M", "n", "drop_rate", "seed", "requests", "served",
               "success_rate", "completion_time", "delivered", "attempts", "correlated"]
TOPOLOGY_MAKERS = {"chain": topologies.chain, "two_branch": topologies.two_branch, "grid": topologies.grid}
ENDS = {"chain": ("A", "C"), "two_branch": ("S", "D")}


@dataclass(frozen=True)
class Task:
    """One run: a fixed setting and seed, `windows` windows of `per_window` requests each."""
    experiment: str
    topology: str
    method: str            # "SP" or "MP"
    k: int
    q: float
    M: int
    n: object              # pairs per request (int), or "1-3" for the grid (n drawn per request)
    drop_rate: float
    seed: int
    windows: int
    per_window: int
    wait: float


# ---------- task lists ----------
def tasks_main():
    """E1 chain, E2 two-branch, E3 grid (plus the k=3 sensitivity row)."""
    out = []
    for q in (1.0, 0.6):
        out += [Task("E1", "chain", "SP", 1, q, 4, 1, 0.0, s, 10, 1, WAIT_BUDGET) for s in SEEDS]
    for n in (2, 4):
        for q in QS:
            for method, k in (("SP", 1), ("MP", 2)):
                out += [Task("E2", "two_branch", method, k, q, 4, n, 0.0, s, 10, 1, WAIT_BUDGET) for s in SEEDS]
    for q in QS:
        for exp, method, k in (("E3", "SP", 1), ("E3", "MP", 2), ("E3_sensitivity", "MP", 3)):
            out += [Task(exp, "grid", method, k, q, 6, "1-3", 0.0, s, 10, 4, WAIT_BUDGET) for s in SEEDS]
    return out


def tasks_drops():
    """E4: simulator packet_drop_rate, budget never binding (q = 1)."""
    out = []
    for drop in (0.0, 0.1, 0.2, 0.3):
        for method, k in (("SP", 1), ("MP", 2)):
            out += [Task("E4", "two_branch", method, k, 1.0, BIG_M, 2, drop, s, 10, 1, WAIT_DROP) for s in SEEDS]
            out += [Task("E4", "grid", method, k, 1.0, BIG_M, "1-3", drop, s, 5, 2, WAIT_DROP) for s in SEEDS]
    return out


# ---------- one run ----------
def requests_for_window(task, graph, window):
    """The (source, dest, n) requests of one window. Same for SP and MP: the RNG sees only (seed, window)."""
    if task.topology in ENDS:
        s, d = ENDS[task.topology]
        return [(s, d, task.n)]
    nodes = sorted(graph.nodes)
    rng = np.random.default_rng([task.seed, 1000, window])
    out = []
    for _ in range(task.per_window):
        s, d = rng.choice(nodes, size=2, replace=False)           # random distinct source and destination
        out.append((str(s), str(d), int(rng.integers(1, 4))))     # n uniform in {1, 2, 3}
    return out


def paths_for(task, net, source, dest):
    """SP: QuNetSim's default route. MP: up to k edge-disjoint paths from our function."""
    if task.method == "SP":
        return [routing.sp_route(source, dest)]
    return routing.k_disjoint_paths(net.quantum_network, source, dest, task.k)


def run_one(task, net, hosts):
    """Execute one Task on an already built network. Returns a CSV row dict plus bookkeeping fields."""
    graph, _ = TOPOLOGY_MAKERS[task.topology]()
    budget = Budget(graph.edges, task.M, task.q, task.seed)
    dice_check = Budget(graph.edges, task.M, task.q, task.seed)    # same dice, replayed without the simulator
    bases = itertools.cycle("ZX")
    random.seed(task.seed)                         # the library's packet-drop dice use the global `random` module
    net.packet_drop_rate = task.drop_rate          # network.py:161
    requests = served = pairs = attempts = correlated = timeouts = mismatches = 0
    served_seconds = []
    try:
        for w in range(task.windows):
            budget.new_window(w)
            dice_check.new_window(w)
            for s, d, n in requests_for_window(task, graph, w):
                loads = routing.split_pairs(n, paths_for(task, net, s, d))
                res = serve_request(hosts, budget, loads, bases, task.wait)
                requests += 1
                pairs, attempts, correlated = pairs + res.pairs, attempts + res.attempts, correlated + res.correlated
                timeouts += int(res.reason == "timeout")
                if res.served:
                    served += 1
                    served_seconds.append(res.seconds)
                if task.drop_rate == 0 and res.reason != "timeout":
                    mismatches += int(dry_request(dice_check, loads) != res.served)
    finally:
        net.packet_drop_rate = 0
    row = {"experiment": task.experiment, "topology": task.topology, "method": task.method, "k": task.k, "q": task.q,
           "M": task.M, "n": task.n, "drop_rate": task.drop_rate, "seed": task.seed, "requests": requests,
           "served": served, "success_rate": served / requests,
           "completion_time": sum(served_seconds) / len(served_seconds) if served_seconds else "",
           "delivered": pairs, "attempts": attempts, "correlated": correlated}
    return {"row": row, "timeouts": timeouts, "dice_mismatches": mismatches}


# ---------- worker process ----------
_STATE = {}


def warm_up(hosts, a, b):
    """One neighbour pair, created and measured, so the first timed request does not pay the ~3 s start-up."""
    q_id, _ = hosts[a].send_epr(b, await_ack=True)
    for q in (hosts[a].get_epr(b, q_id, wait=30), hosts[b].get_epr(a, q_id, wait=30)):
        q.measure()


def init_worker():
    """Build one network with all three topologies (disjoint node names) and warm it up."""
    graphs = [TOPOLOGY_MAKERS[t]()[0] for t in ("chain", "two_branch", "grid")]
    net, hosts = topologies.build_hosts(graphs)
    warm_up(hosts, "A", "B")
    _STATE.update(net=net, hosts=hosts)


def run_task(task):
    """Pool entry point. Errors are returned, not raised, so one bad run does not stop the pool."""
    try:
        return run_one(task, _STATE["net"], _STATE["hosts"])
    except Exception as exc:              # report and continue
        return {"error": f"{type(exc).__name__}: {exc}", "task": task}
    finally:
        time.sleep(0.2)                   # let stray packets of a lossy run drain


def kill_pool(pool):
    """Stop the pool without waiting. A worker never exits by itself: its QuNetSim network keeps host threads
    and one EQSN process per qubit alive, so a plain shutdown(wait=True) blocks forever (docs/TROUBLESHOOTING.md)."""
    procs = list(getattr(pool, "_processes", {}).values())
    pool.shutdown(wait=False, cancel_futures=True)
    for p in procs:
        if os.name == "nt":            # /T also ends the worker's EQSN child processes
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        else:                          # kill the EQSN children too, or they keep our stdout pipe open
            for pid in _descendants(p.pid) + [p.pid]:
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass


def _descendants(root):
    """Linux: every process below `root`, found through /proc (no psutil dependency). Empty elsewhere."""
    children = {}
    for stat in pathlib.Path("/proc").glob("[0-9]*/stat"):
        try:
            fields = stat.read_text().rsplit(")", 1)[1].split()
            children.setdefault(int(fields[1]), []).append(int(stat.parent.name))
        except (OSError, IndexError, ValueError):
            continue
    out, todo = [], [root]
    while todo:
        for c in children.get(todo.pop(), []):
            out.append(c)
            todo.append(c)
    return out


def run_group(tasks, label, partial):
    """Run tasks in a pool of at most MAX_WORKERS processes. Each finished run is appended to `partial`
    (JSON lines) at once, so a crash loses nothing. Returns (rows, timeout_rows, mismatches, errors)."""
    rows, tos, mism, errors = [], [], 0, []
    t0 = time.perf_counter()
    pool = ProcessPoolExecutor(max_workers=MAX_WORKERS, initializer=init_worker)
    try:
        futures = [pool.submit(run_task, t) for t in tasks]
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            with open(partial, "a") as f:
                f.write(json.dumps(res, default=str) + "\n")
            if "error" in res:
                errors.append(res)
                continue
            rows.append(res["row"])
            mism += res["dice_mismatches"]
            tos.append({**{c: res["row"][c] for c in ("experiment", "topology", "method", "k", "q", "n", "drop_rate", "seed")},
                        "timeouts": res["timeouts"]})
            if i % 50 == 0 or i == len(futures):
                say(f"[{label}] {i}/{len(futures)} runs, {time.perf_counter() - t0:.0f} s")
    finally:
        kill_pool(pool)
    return rows, tos, mism, errors


# ---------- outputs ----------
def sort_key(row):
    """Stable row order for the CSV files."""
    return (row["experiment"], row["topology"], row["method"], row["k"], row["q"], str(row["n"]),
            row["drop_rate"], row["seed"])


def write_csv(path, rows, columns):
    """Write rows (dicts) to a CSV with the given column order."""
    path.parent.mkdir(exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)


def write_analytic():
    """results/partB_analytic.csv: closed-form success probability for E1 and E2 (A22, independent attempts)."""
    rows = []
    for q in (1.0, 0.6):
        rows.append({"experiment": "E1", "topology": "chain", "method": "SP", "k": 1, "q": q, "M": 4, "n": 1,
                     "analytic": analytic.p_sp(1, 4, q, links=2)})
    for n in (2, 4):
        for q in QS:
            rows.append({"experiment": "E2", "topology": "two_branch", "method": "SP", "k": 1, "q": q, "M": 4, "n": n,
                         "analytic": analytic.p_sp(n, 4, q)})
            rows.append({"experiment": "E2", "topology": "two_branch", "method": "MP", "k": 2, "q": q, "M": 4, "n": n,
                         "analytic": analytic.p_mp(n, 4, q)})
    write_csv(RESULTS / "partB_analytic.csv", rows, ["experiment", "topology", "method", "k", "q", "M", "n", "analytic"])


# ---------- single-process modes ----------
def smoke():
    """Small QuNetSim check on the chain at q = 1 (used by tests/test_partB.py). Prints one JSON line."""
    t0 = time.perf_counter()
    graph, build = topologies.chain()
    net, hosts = build()
    try:
        warm_up(hosts, "A", "B")
        t_run = time.perf_counter()
        task = Task("E1", "chain", "SP", 1, 1.0, 4, 1, 0.0, 1, 3, 1, WAIT_BUDGET)
        out = run_one(task, net, hosts)
        run_seconds = time.perf_counter() - t_run
    finally:
        net.stop(True)
    print(json.dumps({**out["row"], "timeouts": out["timeouts"], "dice_mismatches": out["dice_mismatches"],
                      "run_seconds": run_seconds, "total_seconds": time.perf_counter() - t0}))


def crosscheck():
    """Loss-free run of QuNetSim's own swap with our dispenser as routing function; writes results/partB_crosscheck.csv."""
    graphs = [TOPOLOGY_MAKERS[t]()[0] for t in ("chain", "two_branch", "grid")]
    net, hosts = topologies.build_hosts(graphs)
    rows = []
    try:
        warm_up(hosts, "A", "B")
        cases = {"chain": [["A", "B", "C"]],
                 "two_branch": routing.k_disjoint_paths(net.quantum_network, "S", "D", 2),
                 "grid": routing.k_disjoint_paths(net.quantum_network, "n00", "n22", 2)}
        for topo, paths in cases.items():
            for path, basis, ok in routing.crosscheck_native_swap(net, hosts, paths):
                rows.append({"topology": topo, "path": "-".join(path), "basis": basis, "correlated": int(ok)})
    finally:
        net.stop(True)
    write_csv(RESULTS / "partB_crosscheck.csv", rows, ["topology", "path", "basis", "correlated"])
    print(f"crosscheck: {sum(r['correlated'] for r in rows)}/{len(rows)} pairs correlated")


def main():
    """Parse the command line and run the chosen mode."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--crosscheck", action="store_true")
    ap.add_argument("--analytic-only", action="store_true")
    ap.add_argument("--groups", default="main,drops", help="comma list of: main, drops")
    ap.add_argument("--limit", type=int, default=None, help="run only the first N tasks per group (testing)")
    ap.add_argument("--quick", action="store_true", help="4 tasks per group, outputs in results/quick/")
    ap.add_argument("--resume", action="store_true",
                    help="keep the runs saved in partB_partial.jsonl and run only the missing ones")
    args = ap.parse_args()
    if args.smoke:
        return smoke()
    if args.crosscheck:
        return crosscheck()
    global RESULTS
    if args.quick:
        RESULTS = ROOT / "results" / "quick"
        args.limit = args.limit or 4
    write_analytic()
    if args.analytic_only:
        return
    errors = []
    t0 = time.perf_counter()
    partial = RESULTS / "partB_partial.jsonl"
    partial.parent.mkdir(parents=True, exist_ok=True)
    done = set(saved_runs(partial)) if args.resume else set()
    if not args.resume:
        partial.unlink(missing_ok=True)
    for group, maker in (("main", tasks_main), ("drops", tasks_drops)):
        if group not in args.groups.split(","):
            continue
        tasks = [t for t in maker()[:args.limit] if task_key(t) not in done]
        say(f"[{group}] {len(tasks)} runs to do" + (f" ({len(done)} saved runs kept)" if args.resume else ""))
        if tasks:
            g_rows, g_tos, mism, g_err = run_group(tasks, group, partial)
            errors += g_err
            say(f"[{group}] done: {len(g_rows)} runs, dice mismatches {mism}, errors {len(g_err)}, "
                f"timeouts {sum(t['timeouts'] for t in g_tos)}, {time.perf_counter() - t0:.0f} s")
        write_outputs(partial)        # after every group, from every saved run, so nothing finished is lost
    for e in errors[:10]:
        say(f"ERROR {e['task']} {e['error']}")
    try:
        sys.stdout.flush()
    except (OSError, ValueError):
        pass
    os._exit(1 if errors else 0)       # outputs are written; do not let a leftover QuNetSim thread hold the exit


def say(msg):
    """Progress line that cannot kill the run: if the console or pipe has gone away, the message is dropped
    (results are saved per run anyway). A broken pipe once ended a run part-way (docs/TROUBLESHOOTING.md)."""
    try:
        print(msg, flush=True)
    except (OSError, ValueError):
        pass


def task_key(t):
    """Identity of one run, shared by Task objects and saved CSV rows."""
    return (t.experiment, t.topology, t.method, t.k, t.q, t.M, str(t.n), t.drop_rate, t.seed)


def row_key(r):
    return (r["experiment"], r["topology"], r["method"], r["k"], r["q"], r["M"], str(r["n"]), r["drop_rate"], r["seed"])


def saved_runs(partial):
    """{run key: saved result} for every successful run in the JSON-lines log (the last copy wins)."""
    out = {}
    if partial.exists():
        for line in partial.read_text().splitlines():
            res = json.loads(line)
            if "row" in res:
                out[row_key(res["row"])] = res
    return out


def write_outputs(partial):
    """results/partB.csv and partB_timeouts.csv from every saved run."""
    saved = saved_runs(partial).values()
    rows = [r["row"] for r in saved]
    tos = [{**{c: r["row"][c] for c in ("experiment", "topology", "method", "k", "q", "n", "drop_rate", "seed")},
            "timeouts": r["timeouts"]} for r in saved]
    write_csv(RESULTS / "partB.csv", sorted(rows, key=sort_key), CSV_COLUMNS)
    write_csv(RESULTS / "partB_timeouts.csv", sorted(tos, key=sort_key),
              ["experiment", "topology", "method", "k", "q", "n", "drop_rate", "seed", "timeouts"])


if __name__ == "__main__":      # guard needed: EQSN starts child processes (Windows 'spawn')
    main()

"""P6: how long does QuNetSim take for r single-path EPR requests sent one after another (swap ON, delay=0)?
Topologies: the 6-node two-branch network (S->D) and a 3x3 grid (corner n00 -> corner n22), r in 1,2,4,8,16,
3 repeats each; plus one run with the default network delay (0.1 s). Writes results/partB_probe_runtime.csv
and figures/F0_qunetsim_runtime.png. Each measurement runs in a fresh process; one untimed warm-up request first.
"""
import sys, os, csv, time, subprocess, pathlib
from _common import build, TWO_BRANCH, grid3x3, say

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOPOS = {"two_branch_6": (TWO_BRANCH, "S", "D"), "grid_3x3": (grid3x3(), "n00", "n22")}
R_LIST = [1, 2, 4, 8, 16]
REPEATS = 3


def worker(topo, r, delay):
    """Time r sequential requests. Prints one line:  RESULT <seconds> <cold_start_seconds>"""
    edges, src, dst = TOPOS[topo]
    net, hosts = build(edges, delay=delay, ent_swap=True)
    try:
        t0 = time.perf_counter()
        q_id, ack = hosts[src].send_epr(dst, await_ack=True)      # warm-up (starts EQSN workers)
        hosts[src].get_epr(dst, q_id, wait=10)
        hosts[dst].get_epr(src, q_id, wait=10)
        cold = time.perf_counter() - t0
        t0 = time.perf_counter()
        for _ in range(r):                                          # sequential: wait for ACK each time
            q_id, ack = hosts[src].send_epr(dst, await_ack=True)    # host.py:844
            q1 = hosts[src].get_epr(dst, q_id, wait=10)
            q2 = hosts[dst].get_epr(src, q_id, wait=10)
            assert ack and q1 is not None and q2 is not None, "request failed"
        secs = time.perf_counter() - t0
        print(f"RESULT {secs:.4f} {cold:.4f}", flush=True)
    finally:
        net.stop(True)


def run_worker(topo, r, delay, timeout=180):
    p = subprocess.Popen([sys.executable, __file__, "worker", topo, str(r), str(delay)],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    try:
        out, _ = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        return None
    for line in out.splitlines():
        if line.startswith("RESULT"):
            _, secs, cold = line.split()
            return float(secs), float(cold)
    return None


def main():
    rows, colds = [], []
    for topo in TOPOS:
        for r in R_LIST:
            for rep in range(1, REPEATS + 1):
                res = run_worker(topo, r, 0.0)
                if res is None:
                    say("FAIL", f"{topo} r={r} repeat={rep}: worker failed or hung")
                    continue
                rows.append((topo, r, rep, res[0]))
                colds.append(res[1])
                say("OBSERVED", f"{topo} r={r:2d} repeat={rep}: {res[0]:.2f} s")
    (ROOT / "results").mkdir(exist_ok=True)
    with open(ROOT / "results" / "partB_probe_runtime.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["topology", "n_requests", "repeat", "seconds"])
        w.writerows((t, r, rep, f"{s:.4f}") for t, r, rep, s in rows)
    say("OBSERVED", f"first (warm-up) request incl. process start: mean {sum(colds)/len(colds):.2f} s (excluded from the timings)")

    # per-request cost and growth (least-squares slope of seconds vs r)
    import numpy as np
    for topo in TOPOS:
        pts = [(r, s) for t, r, rep, s in rows if t == topo]
        slope, icpt = np.polyfit([p[0] for p in pts], [p[1] for p in pts], 1)
        say("OBSERVED", f"{topo}: seconds ~ {icpt:.2f} + {slope:.2f} * r   (about {slope:.2f} s per request, linear growth)")

    # one run with the library's default network delay (0.1 s) for comparison
    for topo in TOPOS:
        res = run_worker(topo, 4, 0.1, timeout=300)
        mean0 = np.mean([s for t, r, rep, s in rows if t == topo and r == 4])
        say("OBSERVED", f"{topo}: r=4 with default delay 0.1 s -> {res[0]:.2f} s, versus delay=0 mean {mean0:.2f} s" if res else f"{topo}: default-delay run failed")
        if res:
            with open(ROOT / "results" / "partB_probe_runtime_default_delay.csv", "a", newline="") as f:
                w = csv.writer(f)
                if f.tell() == 0:
                    w.writerow(["topology", "n_requests", "delay", "seconds"])
                w.writerow([topo, 4, 0.1, f"{res[0]:.4f}"])

    plot()
    say("PASS" if len(rows) == len(TOPOS) * len(R_LIST) * REPEATS else "FAIL",
        f"{len(rows)} timings saved to results/partB_probe_runtime.csv; figure saved to figures/F0_qunetsim_runtime.png")


def plot():
    """Draw F0 from the saved CSV in the house style (docs/DESIGN_RULES.md), so it can be re-rendered without re-timing."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.style.use(ROOT / "figures" / "qmp.mplstyle")
    with open(ROOT / "results" / "partB_probe_runtime.csv", newline="") as f:
        rows = [(r["topology"], int(r["n_requests"]), float(r["seconds"])) for r in csv.DictReader(f)]
    styles = {"grid_3x3": ("#222222", "o", "3x3 grid"), "two_branch_6": ("#666666", "s", "6-node two-branch")}
    fig, ax = plt.subplots()
    slopes = []
    for topo, (color, marker, label) in styles.items():
        rs = sorted({r for t, r, _ in rows if t == topo})
        vals = [[s for t, rr, s in rows if t == topo and rr == r] for r in rs]
        means = np.array([np.mean(v) for v in vals])
        err = [means - [min(v) for v in vals], [max(v) for v in vals] - means]
        ax.errorbar(rs, means, yerr=err, color=color, marker=marker, markersize=3.5, linewidth=1.2)
        ax.annotate(label, (rs[-1], means[-1]), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=8, color=color)
        slopes.append(np.polyfit([r for t, r, _ in rows if t == topo], [s for t, _, s in rows if t == topo], 1)[0])
    ax.set_xticks(R_LIST, [str(r) for r in R_LIST])
    ax.set_xlim(0, 26)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("EPR requests, sent one after another")
    ax.set_ylabel("Wall-clock time (s)")
    ax.set_title(f"QuNetSim: about {np.mean(slopes):.2f} s per sequential request (delay 0)")
    ax.text(0.98, 0.04, "bars: min to max of 3 runs", transform=ax.transAxes, ha="right", fontsize=7, color="#555555")
    (ROOT / "figures").mkdir(exist_ok=True)
    fig.savefig(ROOT / "figures" / "F0_qunetsim_runtime.png")
    fig.savefig(ROOT / "figures" / "F0_qunetsim_runtime.pdf")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker(sys.argv[2], int(sys.argv[3]), float(sys.argv[4]))
    elif len(sys.argv) > 1 and sys.argv[1] == "plot":
        plot()
    else:
        main()

"""P7: can we inject the Part B link-failure model (A22) into QuNetSim? Three ways are tried on the chain A-B-C
and the 6-node two-branch network (M=4 attempts per link per window, success probability q=0.6, seeded):
(i) inject inside swap mode, (ii) pre-drawn outcomes then the library's end-to-end send_epr, (iii) manual hop-by-hop swaps.
Each scenario runs in its own process (run_each); results are appended to results/partB_probe_p7_failure_injection.csv.
"""
import sys, csv, time, threading, inspect, pathlib
import numpy as np
from qunetsim.components import Host
from _common import build, measure_pair, CHAIN, TWO_BRANCH, say, run_each

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "partB_probe_p7_failure_injection.csv"
Q, SEED = 0.6, 7
TOPOS = {"chain": (CHAIN, [["A", "B", "C"]]),
         "two_branch": (TWO_BRANCH, [["S", "a1", "a2", "D"], ["S", "b1", "b2", "D"]])}   # branches used in turn
# name -> (implementation, topology, M attempts per link, windows)
SCENARIOS = {
    "i_chain": ("i", "chain", 4, 30), "i_chain_M1": ("i", "chain", 1, 8), "i_two_branch": ("i", "two_branch", 4, 30),
    "ii_chain": ("ii", "chain", 4, 30), "ii_two_branch": ("ii", "two_branch", 4, 30),
    "iii_chain": ("iii", "chain", 4, 30), "iii_two_branch": ("iii", "two_branch", 4, 30),
}
I_DEADLINE = 90          # (i) stops starting new windows after this many seconds (swap failures wait ~10 s each)


# ---------- the A22 failure model, shared by all three implementations ----------
class Budget:
    """Per-window attempt budget of every link plus one seeded RNG per link (deterministic, thread-safe)."""

    def __init__(self, edges, M, q):
        self.M, self.q, self.lock = M, q, threading.Lock()
        self.rngs = {self.key(*e): np.random.default_rng([SEED, i]) for i, e in enumerate(sorted(self.key(*e) for e in edges))}
        self.left = {}
        self.new_window()

    @staticmethod
    def key(a, b):
        return tuple(sorted((a, b)))

    def new_window(self):
        self.left = {k: self.M for k in self.rngs}

    def attempt(self, a, b):
        """One hop attempt (A22). Returns None if the link has no attempts left, else True (landed) or False."""
        k = self.key(a, b)
        with self.lock:
            if self.left[k] == 0:
                return None
            self.left[k] -= 1
            return bool(self.rngs[k].random() < self.q)

    def hop_lands(self, a, b):
        """Retry the hop while the link has attempts left. True if it landed within the budget."""
        while True:
            r = self.attempt(a, b)
            if r is None or r:
                return bool(r)


def expected_success(hops, M, q):
    return (1 - (1 - q) ** M) ** hops          # one pair per window, every hop must land within M attempts


# ---------- (i) inject inside swap mode ----------
class InjectingHost(Host):
    """send_epr between neighbours 'fails' (creates no pair) when the link budget is used up (A22 inside swap mode)."""
    budget = None
    adj = set()

    def send_epr(self, receiver_id, q_id=None, *args, **kwargs):
        if frozenset((self.host_id, receiver_id)) not in InjectingHost.adj:       # end-to-end request: pass through
            return super().send_epr(receiver_id, q_id, *args, **kwargs)
        if InjectingHost.budget.hop_lands(self.host_id, receiver_id):
            return super().send_epr(receiver_id, q_id, *args, **kwargs)
        return (q_id, False) if kwargs.get("await_ack") else q_id                   # fake failure: no pair is made


def orphans(hosts):
    """Number of EPR halves still stored anywhere (get_epr_pairs, host.py:1199)."""
    return sum(len(h.get_epr_pairs(o)) for h in hosts.values() for o in hosts if o != h.host_id)


def make_routing(net, paths):
    """Install a routing function that returns the path chosen for the current window (a dispenser)."""
    current = {"path": paths[0]}
    net.quantum_routing_algo = lambda graph, source, dest: list(current["path"])    # 3 args, network.py:109-128
    return current


def run_i(topo, M, windows):
    edges, paths = TOPOS[topo]
    InjectingHost.adj = {frozenset(e) for e in edges}
    InjectingHost.budget = Budget(edges, 1000, 1.0)                                  # warm-up: no failures
    net, hosts = build(edges, ent_swap=True, host_cls=InjectingHost)
    for h in hosts.values():
        h.max_ack_wait = 15                                                          # host.py:161; default waits forever
    current = make_routing(net, paths)
    src, dst = paths[0][0], paths[0][-1]
    res = {"delivered": 0, "windows": 0, "z": [0, 0], "x": [0, 0], "durations": []}
    try:
        q_id, _ = hosts[src].send_epr(dst, await_ack=True)
        hosts[src].get_epr(dst, q_id, wait=10); hosts[dst].get_epr(src, q_id, wait=10)
        InjectingHost.budget = Budget(edges, M, Q)
        t_start = time.perf_counter()
        for w in range(windows):
            if time.perf_counter() - t_start > I_DEADLINE:
                say("OBSERVED", f"[i] deadline {I_DEADLINE}s reached, stopped after {w} windows")
                break
            InjectingHost.budget.new_window()
            current["path"] = paths[w % len(paths)]
            t0 = time.perf_counter()
            q_id, ack = hosts[src].send_epr(dst, await_ack=True)
            q1 = hosts[src].get_epr(dst, q_id, wait=2)
            q2 = hosts[dst].get_epr(src, q_id, wait=2)
            res["durations"].append(time.perf_counter() - t0)
            res["windows"] += 1
            if ack and q1 is not None and q2 is not None:
                basis = "Z" if res["delivered"] % 2 == 0 else "X"
                m1, m2 = measure_pair(q1, q2, basis)
                res["delivered"] += 1
                res[basis.lower()][0] += int(m1 == m2); res[basis.lower()][1] += 1
        res["seconds"] = time.perf_counter() - t_start
        res["orphans"] = orphans(hosts)
        say("OBSERVED", f"[i] longest window {max(res['durations']):.1f} s; shortest {min(res['durations']):.2f} s; "
                        f"orphan EPR halves left in storage: {res['orphans']}")
    finally:
        net.stop(True)
    return res


# ---------- (ii) pre-drawn outcomes, then the library's end-to-end send_epr ----------
def window_delivered(budget, path):
    """Pre-draw every hop of the path (all hops attempted, so every budget is consumed). True if all landed."""
    return all([budget.hop_lands(a, b) for a, b in zip(path, path[1:])])


def run_ii(topo, M, windows):
    edges, paths = TOPOS[topo]
    net, hosts = build(edges, ent_swap=True)
    current = make_routing(net, paths)
    src, dst = paths[0][0], paths[0][-1]
    budget = Budget(edges, M, Q)
    res = {"delivered": 0, "windows": 0, "z": [0, 0], "x": [0, 0], "durations": []}
    try:
        q_id, _ = hosts[src].send_epr(dst, await_ack=True)                           # warm-up
        hosts[src].get_epr(dst, q_id, wait=10); hosts[dst].get_epr(src, q_id, wait=10)
        t_start = time.perf_counter()
        for w in range(windows):
            budget.new_window()
            path = paths[w % len(paths)]
            res["windows"] += 1
            if not window_delivered(budget, path):
                continue
            current["path"] = path
            q_id, ack = hosts[src].send_epr(dst, await_ack=True)
            q1 = hosts[src].get_epr(dst, q_id, wait=5); q2 = hosts[dst].get_epr(src, q_id, wait=5)
            basis = "Z" if res["delivered"] % 2 == 0 else "X"
            m1, m2 = measure_pair(q1, q2, basis)
            res["delivered"] += 1
            res[basis.lower()][0] += int(m1 == m2); res[basis.lower()][1] += 1
        res["seconds"] = time.perf_counter() - t_start
        res["orphans"] = orphans(hosts)
    finally:
        net.stop(True)
    return res


# ---------- (iii) manual hop-by-hop with our own Bell-state measurements ----------
def make_hop_pair(hosts, budget, a, b):
    """Run attempts on link a-b. Each attempt really creates a pair with send_epr (host.py:844); a failed attempt
    consumes budget and releases both halves (qubit.py:146). Returns (half_at_a, half_at_b) or None."""
    while True:
        r = budget.attempt(a, b)
        if r is None:
            return None
        q_id, _ = hosts[a].send_epr(b, await_ack=True)
        qa = hosts[a].get_epr(b, q_id, wait=5)
        qb = hosts[b].get_epr(a, q_id, wait=5)
        if r:
            return qa, qb
        qa.release(); qb.release()


def bell_measure(q_left, q_right):
    """Bell-state measurement on two qubits held by the same host: cnot, H, measure (qubit.py:221,188,319)."""
    q_left.cnot(q_right)
    q_left.H()
    return q_left.measure(), q_right.measure()


def deliver_pair_manual(hosts, budget, path):
    """Build one end-to-end pair hop by hop. Returns (half_at_src, half_at_dst) or None if some hop failed."""
    halves = [make_hop_pair(hosts, budget, a, b) for a, b in zip(path, path[1:])]       # all hops attempted
    if any(h is None for h in halves):
        for h in halves:
            if h is not None:
                h[0].release(); h[1].release()
        return None
    dst = path[-1]
    for i, mid in enumerate(path[1:-1]):
        m1, m2 = bell_measure(halves[i][1], halves[i + 1][0])                           # both qubits are at host mid
        hosts[mid].send_classical(dst, f"{m1}{m2}", await_ack=True)                      # host.py:810
    x_par = z_par = 0
    for mid in path[1:-1]:
        msg = hosts[dst].get_next_classical(mid, wait=5)                                 # host.py:1457; returns Message
        z_par ^= int(msg.content[0]); x_par ^= int(msg.content[1])
    q_dst = halves[-1][1]
    if x_par:
        q_dst.X()                                                                        # qubit.py:158
    if z_par:
        q_dst.Z()                                                                        # qubit.py:170
    return halves[0][0], q_dst


def run_iii(topo, M, windows):
    edges, paths = TOPOS[topo]
    net, hosts = build(edges, ent_swap=True)
    budget = Budget(edges, M, Q)
    res = {"delivered": 0, "windows": 0, "z": [0, 0], "x": [0, 0], "durations": []}
    try:
        q_id, _ = hosts[paths[0][0]].send_epr(paths[0][1], await_ack=True)               # warm-up (neighbour pair)
        hosts[paths[0][0]].get_epr(paths[0][1], q_id, wait=10); hosts[paths[0][1]].get_epr(paths[0][0], q_id, wait=10)
        t_start = time.perf_counter()
        for w in range(windows):
            budget.new_window()
            res["windows"] += 1
            pair = deliver_pair_manual(hosts, budget, paths[w % len(paths)])
            if pair is None:
                continue
            basis = "Z" if res["delivered"] % 2 == 0 else "X"
            m1, m2 = measure_pair(pair[0], pair[1], basis)
            res["delivered"] += 1
            res[basis.lower()][0] += int(m1 == m2); res[basis.lower()][1] += 1
        res["seconds"] = time.perf_counter() - t_start
        res["orphans"] = orphans(hosts)
    finally:
        net.stop(True)
    return res


# ---------- reporting ----------
def code_lines(*funcs):
    """Non-blank, non-comment, non-docstring-opening source lines of the given functions or classes."""
    n = 0
    for f in funcs:
        for line in inspect.getsource(f).splitlines():
            s = line.strip()
            if s and not s.startswith(("#", '"""')):
                n += 1
    return n


LOC = {"i": lambda: code_lines(InjectingHost, run_i), "ii": lambda: code_lines(window_delivered, run_ii),
       "iii": lambda: code_lines(make_hop_pair, bell_measure, deliver_pair_manual, run_iii)}


def report(name, impl, topo, M, res):
    hops = len(TOPOS[topo][1][0]) - 1
    d, wn = res["delivered"], res["windows"]
    per = res["seconds"] / d if d else float("nan")
    zc, zn, xc, xn = res["z"][0], res["z"][1], res["x"][0], res["x"][1]
    say("OBSERVED", f"[{name}] windows {wn}, delivered {d} ({d/wn:.2f}; model predicts {expected_success(hops, M, Q):.2f}), "
                    f"{res['seconds']:.1f} s total, {per:.2f} s per delivered pair, orphans {res.get('orphans')}, "
                    f"Z-correlated {zc}/{zn}, X-correlated {xc}/{xn}, lines of code {LOC[impl]()}")
    OUT.parent.mkdir(exist_ok=True)
    new = not OUT.exists()
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["scenario", "impl", "topology", "M", "q", "windows", "delivered", "expected_rate", "seconds",
                        "seconds_per_delivered", "z_correlated", "z_total", "x_correlated", "x_total", "orphan_halves", "code_lines"])
        w.writerow([name, impl, topo, M, Q, wn, d, f"{expected_success(hops, M, Q):.4f}", f"{res['seconds']:.2f}",
                    f"{per:.3f}", zc, zn, xc, xn, res.get("orphans"), LOC[impl]()])
    ok = zc == zn and xc == xn and d > 0
    say("PASS" if ok else "FAIL", f"[{name}] delivered pairs are Bell pairs (Z and X agree on every delivered pair)")


def scenario(name):
    impl, topo, M, windows = SCENARIOS[name]
    runner = {"i": run_i, "ii": run_ii, "iii": run_iii}[impl]
    report(name, impl, topo, M, runner(topo, M, windows))


def main():
    if len(sys.argv) > 1:
        scenario(sys.argv[1])
        return
    OUT.unlink(missing_ok=True)
    run_each(__file__, list(SCENARIOS), timeout=240)


if __name__ == "__main__":      # guard needed: EQSN starts child processes (Windows 'spawn')
    main()

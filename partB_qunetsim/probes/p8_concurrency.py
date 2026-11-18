"""P8: are two EPR requests that are in flight at the same time safe in QuNetSim (GitHub issue #170 reports
"Qid doesent match id!" and lost qubits under concurrency)? On the 6-node two-branch network, swap ON, we send two
requests from S at the same time (two threads) and check both pairs. Scenarios, 20 trials each:
a_seq (baseline: the two requests one after another), a_conc (one request per branch),
b_same_path (both requests over the same 3 links), b_partial (S->D on branch a and S->a2, sharing 2 links),
c_same_path4 (four requests at once over the same 3 links). Each trial also records whether the request intervals overlapped.
"""
import sys, csv, time, threading, pathlib
from _common import build, measure_pair, TWO_BRANCH, say, run_each

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "results" / "partB_probe_p8_concurrency.csv"
A_BRANCH, B_BRANCH, A_SHORT = ["S", "a1", "a2", "D"], ["S", "b1", "b2", "D"], ["S", "a1", "a2"]
TRIALS, TRIAL_DEADLINE = 20, 120
# name -> (destinations of the two requests, concurrent?)
SCENARIOS = {"a_seq": (("D", "D"), False), "a_conc": (("D", "D"), True),
             "b_same_path": (("D", "D"), True), "b_partial": (("D", "a2"), True),
             "c_same_path4": (("D", "D", "D", "D"), True)}


def make_route_fn(name, calls):
    """Routing function (3 arguments, network.py:109-128) for each scenario; `calls` counts requests seen."""
    def route(graph, source, dest):
        calls.append(dest)
        if name in ("a_seq", "a_conc"):
            return list(A_BRANCH if len(calls) % 2 == 1 else B_BRANCH)     # one request per branch
        return list(A_SHORT if dest == "a2" else A_BRANCH)
    return route


def one_request(hosts, dst, out, spans, k):
    """Send one EPR request from S and record (q_id, ack) in out[k] and its (start, end) time in spans[k].
    Exceptions are recorded, not raised."""
    spans[k] = [time.perf_counter(), None]
    try:
        out[k] = hosts["S"].send_epr(dst, await_ack=True)                   # host.py:844
    except Exception as e:                                                  # noqa: BLE001, we want to count them
        out[k] = e
    spans[k][1] = time.perf_counter()


def check_pair(hosts, dst, result, basis):
    """True if the request was acked, both halves exist and agree in the given basis. Also returns a short reason."""
    if isinstance(result, Exception):
        return False, f"exception {type(result).__name__}"
    q_id, ack = result
    q1 = hosts["S"].get_epr(dst, q_id, wait=3)
    q2 = hosts[dst].get_epr("S", q_id, wait=3)
    if not ack:
        return False, "no ack"
    if q1 is None or q2 is None:
        return False, "half missing"
    m1, m2 = measure_pair(q1, q2, basis)
    return (m1 == m2), ("ok" if m1 == m2 else "uncorrelated")


def run_trial(hosts, dsts, concurrent, t):
    """All requests of one trial: threads started together if concurrent, else one after another.
    Returns (per-request check results, True if the request time intervals overlapped)."""
    out, spans = [None] * len(dsts), [None] * len(dsts)
    threads = [threading.Thread(target=one_request, args=(hosts, d, out, spans, k)) for k, d in enumerate(dsts)]
    for th in threads:
        th.start()
        if not concurrent:
            th.join()
    for th in threads:
        th.join()
    basis = "Z" if t % 2 == 0 else "X"
    overlapped = max(sp[0] for sp in spans) < min(sp[1] for sp in spans)
    return [check_pair(hosts, d, out[k], basis) for k, d in enumerate(dsts)], overlapped


def scenario(name):
    dsts, concurrent = SCENARIOS[name]
    calls = []
    net, hosts = build(TWO_BRANCH, ent_swap=True)
    for h in hosts.values():
        h.max_ack_wait = 10                                                 # host.py:161
    net.quantum_routing_algo = make_route_fn(name, calls)
    reasons, trials_both, trials_done, req_ok, n_overlap = {}, 0, 0, 0, 0
    try:
        q_id, _ = hosts["S"].send_epr("D", await_ack=True)                  # warm-up (starts EQSN workers)
        hosts["S"].get_epr("D", q_id, wait=10); hosts["D"].get_epr("S", q_id, wait=10)
        calls.clear()
        t_start = time.perf_counter()
        for t in range(TRIALS):
            if time.perf_counter() - t_start > TRIAL_DEADLINE:
                say("OBSERVED", f"[{name}] deadline reached after {t} trials")
                break
            results, overlapped = run_trial(hosts, dsts, concurrent, t)
            n_overlap += int(overlapped)
            say("TRIAL", f"[{name}] trial {t + 1}: {[why for _, why in results]}")   # progress line, shows where a hang starts
            trials_done += 1
            req_ok += sum(ok for ok, _ in results)
            trials_both += int(all(ok for ok, _ in results))
            for _, why in results:
                reasons[why] = reasons.get(why, 0) + 1
        secs = time.perf_counter() - t_start
        left = sum(len(h.get_epr_pairs(o)) for h in hosts.values() for o in hosts if o != h.host_id)
    finally:
        net.stop(True)
    say("OBSERVED", f"[{name}] trials {trials_done}, requests ok {req_ok}/{len(dsts)*trials_done}, all ok in {trials_both}/{trials_done} trials, "
                    f"request intervals overlapped in {n_overlap}/{trials_done}, {secs/trials_done:.2f} s per trial of {len(dsts)} requests, outcomes {reasons}, EPR halves left in storage {left}")
    new = not OUT.exists()
    with open(OUT, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["scenario", "trials", "requests_ok", "requests", "trials_all_ok", "trials_overlapped", "seconds_per_trial", "left_in_storage", "outcomes"])
        w.writerow([name, trials_done, req_ok, len(dsts) * trials_done, trials_both, n_overlap, f"{secs/trials_done:.3f}", left, str(reasons)])


def main():
    if len(sys.argv) > 1:
        scenario(sys.argv[1])
        return
    OUT.unlink(missing_ok=True)
    run_each(__file__, list(SCENARIOS), timeout=300)


if __name__ == "__main__":      # guard needed: EQSN starts child processes (Windows 'spawn')
    main()

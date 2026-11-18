"""P2: is the routing function we can install actually used? On a 6-node two-branch network
(S-a1-a2-D and S-b1-b2-D) we install a 3-argument function that logs each call and returns the b-branch.
We run it with use_ent_swap True and False, then with a 'path dispenser' (branch a, then branch b).
"""
import sys, os
from _common import build, MeteredHost, link_counts, TWO_BRANCH, say, run_each

A_BRANCH = ["S", "a1", "a2", "D"]
B_BRANCH = ["S", "b1", "b2", "D"]


def scenario(name):
    swap = name in ("swap_on", "dispenser")
    net, hosts = build(TWO_BRANCH, ent_swap=swap, host_cls=MeteredHost)
    route_log = []

    if name == "dispenser":
        queue = [A_BRANCH, B_BRANCH]

        def route_fn(graph, source, dest):            # exactly 3 parameters (network.py:117-123)
            route = queue[min(len(route_log), len(queue) - 1)]
            route_log.append((source, dest, route))
            return route
    else:
        def route_fn(graph, source, dest):
            route_log.append((source, dest, B_BRANCH))
            return B_BRANCH

    try:
        net.quantum_routing_algo = route_fn             # setter, network.py:109-128
        n_req = 2 if name == "dispenser" else 1
        used = []                                       # links actually used, per request
        for i in range(n_req):
            MeteredHost.calls.clear()
            q_id, ack = hosts["S"].send_epr("D", await_ack=True)
            q1 = hosts["S"].get_epr("D", q_id, wait=5)
            q2 = hosts["D"].get_epr("S", q_id, wait=5)
            per_link, e2e = link_counts(TWO_BRANCH)
            used.append(set(per_link))
            say("OBSERVED", f"[{name}] request {i+1}: ack={ack}, both halves present={q1 is not None and q2 is not None}, "
                            f"per-link send_epr calls={per_link}, routing-fn calls so far={len(route_log)}")
        for s, d, r in route_log:
            say("OBSERVED", f"[{name}] routing fn called with ({s},{d}) -> returned {r}")
        links = lambda r: {"-".join(sorted(p)) for p in zip(r, r[1:])}
        if name == "swap_off":
            ok = len(route_log) >= 1 and used[0] == set()
            say("PASS" if ok else "FAIL", "swap OFF: routing fn was CALLED but its route was NOT used (no hop-by-hop EPR)")
        elif name == "swap_on":
            ok = used[0] == links(B_BRANCH)
            say("PASS" if ok else "FAIL", "swap ON: EPR was built hop by hop along exactly the route our function returned")
        else:
            ok = used == [links(A_BRANCH), links(B_BRANCH)]
            say("PASS" if ok else "FAIL", "dispenser: request 1 used branch a, request 2 used branch b")
    finally:
        net.stop(True)


def main():
    if len(sys.argv) > 1:
        scenario(sys.argv[1])
        return
    run_each(os.path.abspath(__file__), ["swap_on", "swap_off", "dispenser"])


if __name__ == "__main__":
    main()

"""P4: can we COUNT how many EPR attempts each link carries, without editing the library?
We use a Host subclass (MeteredHost in _common.py) whose send_epr/send_teleport record (sender, receiver)
and then call the normal method. We print per-link counts for ONE end-to-end request on the chain and
on the two-branch network (swap ON), and once more on the two-branch network with swap OFF.
"""
import sys, os
from _common import build, MeteredHost, link_counts, CHAIN, TWO_BRANCH, say, run_each

CASES = {                      # name: (edges, source, destination, use_ent_swap)
    "chain": (CHAIN, "A", "C", True),
    "two_branch": (TWO_BRANCH, "S", "D", True),
    "two_branch_noswap": (TWO_BRANCH, "S", "D", False),
}


def scenario(name):
    edges, src, dst, swap = CASES[name]
    net, hosts = build(edges, ent_swap=swap, host_cls=MeteredHost)
    try:
        MeteredHost.calls.clear()
        MeteredHost.teleports.clear()
        q_id, ack = hosts[src].send_epr(dst, await_ack=True)
        ok = hosts[src].get_epr(dst, q_id, wait=5) is not None and hosts[dst].get_epr(src, q_id, wait=5) is not None
        per_link, e2e = link_counts(edges)
        say("OBSERVED", f"[{name}] swap={swap} request {src}->{dst}: pair delivered={ok}")
        say("OBSERVED", f"[{name}] EPR attempts per link: {per_link or 'none (pair created directly, links never used)'}")
        say("OBSERVED", f"[{name}] end-to-end send_epr calls (non-neighbours): {e2e}; teleports (swap corrections): {MeteredHost.teleports}")
        if swap:
            hops = len(per_link)
            say("PASS" if ok and hops >= 2 and all(v == 1 for v in per_link.values()) else "FAIL",
                f"metering works: {hops} links used once each, no library edit")
        else:
            say("PASS" if ok and not per_link else "FAIL",
                "metering shows swap OFF uses NO links at all (so link usage can only be metered with swap ON)")
    finally:
        net.stop(True)


def main():
    if len(sys.argv) > 1:
        scenario(sys.argv[1])
    else:
        run_each(os.path.abspath(__file__), list(CASES))


if __name__ == "__main__":
    main()

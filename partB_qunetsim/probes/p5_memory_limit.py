"""P5: what does the EPR memory limit do? Host B gets set_epr_memory_limit(1), then A sends B three EPR pairs.
We report how many halves B and A end up holding, whether anything raised an error, and whether the
limit can also be set per partner or through the property.  We also try the data-qubit limit property.
"""
import sys, os, time
from _common import build, CHAIN, say, run_each


def stored(host, partner):
    return len(host.get_epr_pairs(partner))          # host.py:1199 (does not remove them)


def scenario(name):
    net, hosts = build(CHAIN)
    A, B = hosts["A"], hosts["B"]
    try:
        A.send_epr("B", await_ack=True)              # warm-up pair (EQSN cold start), then clean up
        time.sleep(0.5)
        for h, p in ((A, "B"), (B, "A")):
            while h.get_epr(p) is not None:
                pass
        if name == "global":
            B.set_epr_memory_limit(1)                # host.py:1285-1297
        elif name == "per_partner":
            B.set_epr_memory_limit(1, host_id="A")
        elif name == "property":
            B.storage_epr_limit = 1                  # host.py:191-203
        elif name == "none":
            pass
        elif name == "data_limit_property":
            try:
                B.storage_limit = 1                  # host.py:215-227
                say("OBSERVED", "Host.storage_limit = 1 worked")
            except Exception as e:
                say("OBSERVED", f"Host.storage_limit = 1 raised {type(e).__name__}: {e}  (library bug, host.py:227)")
            return
        acks = []
        for _ in range(3):
            q_id, ack = A.send_epr("B", await_ack=True)
            acks.append(ack)
        time.sleep(0.5)
        nb, na = stored(B, "A"), stored(A, "B")
        say("OBSERVED", f"[{name}] 3 pairs requested A->B; ACKs={acks}; halves stored at B={nb}, at A={na}; no exception reached the caller")
        if name != "none":
            say("PASS" if nb == 1 and na == 3 else "FAIL",
                "limit=1 keeps 1 half at B; extra halves are silently released (no error, no overwrite); A still keeps 3 orphan halves")
        else:
            say("PASS" if nb == 3 and na == 3 else "FAIL", "without a limit all 3 pairs are stored on both sides")
    finally:
        net.stop(True)


def main():
    if len(sys.argv) > 1:
        scenario(sys.argv[1])
    else:
        run_each(os.path.abspath(__file__), ["none", "global", "per_partner", "property", "data_limit_property"])


if __name__ == "__main__":
    main()

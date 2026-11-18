"""P3: does QuNetSim loss reach EPR pairs? On the chain A-B-C (swap ON) we (1) set the network-wide
packet_drop_rate to 0 / 0.2 / 0.5 and count end-to-end EPR successes in 30 attempts each,
(2) check that classical packets are dropped too, and (3) put a Fibre model (p=0.7) on one link.
"""
import sys, os, time
from qunetsim.objects import Qubit
from qunetsim.objects.connections.channel_models.fibre import Fibre
from _common import build, CHAIN, say, run_each, measure_pair

N = 30
WAIT = 1.5          # seconds to wait for an end-to-end pair (a clean swap takes ~0.2 s at delay=0)


def drain(hosts):
    """Throw away every EPR half still stored (leftovers of failed attempts)."""
    for h in hosts.values():
        for p in hosts:
            while True:
                q = h.get_epr(p)                 # host.py:1470, wait=0 -> returns None when empty
                if q is None:
                    break
                q.release()


def epr_attempts(hosts, n=N):
    ok = zcorr = 0
    for _ in range(n):
        q_id = hosts["A"].send_epr("C")                         # no ACK wait: a dropped ACK must not block us
        q1 = hosts["A"].get_epr("C", q_id, wait=WAIT)
        q2 = hosts["C"].get_epr("A", q_id, wait=WAIT if q1 is not None else 0.2)
        if q1 is not None and q2 is not None:
            ok += 1
            m1, m2 = measure_pair(q1, q2, "Z")
            zcorr += int(m1 == m2)
        else:
            time.sleep(1.2)                                     # let stale swap threads time out
        drain(hosts)
    return ok, zcorr


def warm_up(hosts):
    """The first request starts EQSN worker processes (~2.5 s). Do it once before counting anything."""
    q_id = hosts["A"].send_epr("C")
    hosts["A"].get_epr("C", q_id, wait=15)
    hosts["C"].get_epr("A", q_id, wait=15)
    drain(hosts)


def scenario(name):
    kind, _, val = name.partition("=")
    q_models = {("A", "B"): Fibre(length=10, alpha=0.155)} if kind.startswith("fibre") else None
    net, hosts = build(CHAIN, ent_swap=True, q_models=q_models)
    try:
        for h in hosts.values():
            h.max_ack_wait = 1                                   # host.py:152-175: never wait forever
        warm_up(hosts)
        if kind == "drop":
            net.packet_drop_rate = float(val)                    # network.py:160-175
            ok, zc = epr_attempts(hosts)
            say("OBSERVED", f"drop_rate={val}: end-to-end EPR success {ok}/{N} = {ok/N:.2f}; among successes Z-correlated {zc}/{ok}")
            if float(val) == 0:
                say("PASS" if ok == N and zc == ok else "FAIL", "baseline without loss: every attempt gives a correlated pair")
            else:
                say("OBSERVED", "loss lowers the END-TO-END success; halves that do arrive are still perfectly correlated" if zc == ok else "some arrived pairs were NOT correlated")
        elif kind == "classical":
            net.packet_drop_rate = float(val)
            for i in range(100):
                hosts["A"].send_classical("B", f"m{i}", no_ack=True)        # host.py:810
            time.sleep(1.5)
            got = len(hosts["B"].get_classical("A"))                        # host.py:1434
            say("OBSERVED", f"drop_rate={val}: classical neighbour messages delivered {got}/100 (expect ~{100*(1-float(val)):.0f})")
            say("PASS" if 25 <= got <= 75 else "FAIL", "classical packets ARE dropped by the same network-wide rate")
        elif kind == "fibre_epr":
            print("transmission_p of the A-B model =", Fibre(length=10, alpha=0.155).transmission_p)   # fibre.py transmission_p
            ok, zc = epr_attempts(hosts)
            say("OBSERVED", f"Fibre p~0.7 on link A-B (swap ON): end-to-end EPR success {ok}/{N}")
            say("PASS" if ok == N else "FAIL", "Fibre model does NOT affect EPR creation (hop EPR is made by backend.create_EPR, never by qubit_func)")
        elif kind == "fibre_qubit":
            for _ in range(N):                                               # send all, then count what arrived
                hosts["A"].send_qubit("B", Qubit(hosts["A"]), no_ack=True)   # host.py:1135
            time.sleep(4)
            got = len(hosts["B"].get_data_qubits("A"))                       # host.py:1216
            say("OBSERVED", f"Fibre p~0.7 on link A-B: data qubits delivered {got}/{N} (expect ~{0.7*N:.0f})")
            say("PASS" if 12 <= got <= 28 else "FAIL", "Fibre model DOES drop data qubits sent with send_qubit (but not EPR pairs)")
    finally:
        net.stop(True)


def main():
    if len(sys.argv) > 1:
        scenario(sys.argv[1])
        return
    run_each(os.path.abspath(__file__),
             ["drop=0", "drop=0.2", "drop=0.5", "classical=0.5", "fibre_epr", "fibre_qubit"], timeout=400)


if __name__ == "__main__":
    main()

"""P1: three hosts A-B-C in a line, entanglement swapping ON. A asks for an EPR pair with C.
We then measure both halves 20 times in the Z basis and 20 times in the X basis;
a real shared Bell pair gives equal Z results and equal X results every time.
"""
from _common import build, request_epr, measure_pair, CHAIN, say

REPS = 20


def main():
    net, hosts = build(CHAIN, ent_swap=True)
    try:
        ok = {"Z": 0, "X": 0}
        missing = 0
        for basis in ("Z", "X"):
            for _ in range(REPS):
                q_id, ack, q1, q2 = request_epr("A", "C", hosts)
                if q1 is None or q2 is None:
                    missing += 1
                    continue
                m1, m2 = measure_pair(q1, q2, basis)
                ok[basis] += int(m1 == m2)
        say("OBSERVED", f"missing halves: {missing}/{2*REPS}; Z-correlated {ok['Z']}/{REPS}; X-correlated {ok['X']}/{REPS}")
        left = {h: [o for o in "ABC" if o != h and hosts[h].get_epr_pairs(o)] for h in "ABC"}   # host.py:1199
        say("OBSERVED", f"EPR halves left in storage after all requests (host: partners): {left}")
        no_leftovers = all(not partners for partners in left.values())
        passed = missing == 0 and ok["Z"] == REPS and ok["X"] == REPS and no_leftovers
        say("PASS" if passed else "FAIL", "end-to-end EPR A-C via swap: both halves present, perfectly correlated in Z and X, no leftover halves at A, B or C")
    finally:
        net.stop(True)


if __name__ == "__main__":      # guard needed: EQSN starts child processes (Windows 'spawn')
    main()

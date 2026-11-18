"""Deliver one end-to-end EPR pair over a given path, hop by hop, with real QuNetSim calls (probe P7 iii).
Link failures come from the A22 budget; Bell measurements, classical bits and Pauli fixes run in the simulator.
Also serves a whole request (all-or-nothing) as a sequence of such pairs.
"""
import itertools
import time
from typing import NamedTuple

_pair_ids = itertools.count()      # tags classical messages so a late message from a failed pair is skipped


class Delivery(NamedTuple):
    """Result of one pair. reason is "ok", "budget" (a link ran out of attempts) or "timeout" (simulator wait expired)."""
    delivered: bool
    attempts: int
    seconds: float
    correlated: bool
    reason: str


class RequestResult(NamedTuple):
    """Result of one request. pairs and correlated count every delivered pair, also those wasted by a failure."""
    served: bool
    pairs: int
    attempts: int
    correlated: int
    seconds: float
    reason: str


def release_all(qubits):
    """Release qubits that are still alive (qubit.py:146)."""
    for q in qubits:
        q.release()


def make_hop_pair(hosts, budget, a, b, wait):
    """Attempts on link a-b. Each attempt really creates a pair with send_epr (host.py:844) and fetches both
    halves with get_epr (host.py:1470). A22: the budget draw decides if the attempt counts as landed; a failed
    draw consumes the attempt and releases both halves. A simulator timeout is a failure and is not retried.
    Returns ((half_at_a, half_at_b), "ok") or (None, reason)."""
    while True:
        landed = budget.attempt(a, b)
        if landed is None:
            return None, "budget"
        q_id, ack = hosts[a].send_epr(b, await_ack=True)
        w = wait if ack else 0
        qa = hosts[a].get_epr(b, q_id, wait=w)
        qb = hosts[b].get_epr(a, q_id, wait=w)
        if not (ack and qa is not None and qb is not None):
            release_all([q for q in (qa, qb) if q is not None])
            return None, "timeout"
        if landed:
            return (qa, qb), "ok"
        release_all([qa, qb])


def bell_measure(q_left, q_right):
    """Bell-state measurement on two qubits held by one host: cnot, H, measure (qubit.py:221, 188, 319)."""
    q_left.cnot(q_right)
    q_left.H()
    return q_left.measure(), q_right.measure()


def read_bits(host, sender, pair_id, wait):
    """Next classical message from `sender` that belongs to this pair (host.py:1457). None on timeout."""
    for _ in range(5):
        msg = host.get_next_classical(sender, wait=wait)
        if msg is None:
            return None
        tag, bits = msg.content.split(":")
        if tag == pair_id:
            return int(bits[0]), int(bits[1])
    return None


def swap_and_correct(hosts, path, halves, wait, pair_id):
    """Bell measurement at every intermediate node, 2 bits to the destination each (host.py:810), then X/Z
    corrections at the destination (qubit.py:158, 170). Returns (src_half, dst_half) or None on timeout.
    Qubits that are still alive are released on failure."""
    dst = path[-1]
    alive = [q for pair in halves for q in pair]
    for i, mid in enumerate(path[1:-1]):
        left, right = halves[i][1], halves[i + 1][0]
        m1, m2 = bell_measure(left, right)
        alive.remove(left)
        alive.remove(right)
        if not hosts[mid].send_classical(dst, f"{pair_id}:{m1}{m2}", await_ack=True):
            release_all(alive)
            return None
    z_par = x_par = 0
    for mid in path[1:-1]:
        bits = read_bits(hosts[dst], mid, pair_id, wait)
        if bits is None:
            release_all(alive)
            return None
        z_par ^= bits[0]
        x_par ^= bits[1]
    q_dst = halves[-1][1]
    if x_par:
        q_dst.X()
    if z_par:
        q_dst.Z()
    return halves[0][0], q_dst


def check_correlation(q_src, q_dst, basis):
    """Measure both halves in Z or X (X = Hadamard first); a Bell pair gives equal outcomes in both bases."""
    if basis == "X":
        q_src.H()
        q_dst.H()
    return q_src.measure() == q_dst.measure()


def deliver_pair(hosts, budget, path, basis, wait=10.0):
    """Build one end-to-end pair over `path`. Stops at the first hop that runs out of budget or times out and
    releases the halves already made. Returns Delivery(delivered, attempts, seconds, correlated, reason)."""
    t0, used0 = time.perf_counter(), budget.used
    pair_id = f"p{next(_pair_ids)}"
    halves = []
    for a, b in zip(path, path[1:]):
        pair, reason = make_hop_pair(hosts, budget, a, b, wait)
        if pair is None:
            release_all([q for h in halves for q in h])
            return Delivery(False, budget.used - used0, time.perf_counter() - t0, False, reason)
        halves.append(pair)
    ends = swap_and_correct(hosts, path, halves, wait, pair_id)
    if ends is None:
        return Delivery(False, budget.used - used0, time.perf_counter() - t0, False, "timeout")
    ok = check_correlation(ends[0], ends[1], basis)
    return Delivery(True, budget.used - used0, time.perf_counter() - t0, ok, "ok")


def serve_request(hosts, budget, loads, bases, wait=10.0):
    """One request, all or nothing. loads = [(path, number_of_pairs), ...], pairs delivered one after another.
    At the first failed pair the request fails and its delivered pairs are wasted. `bases` cycles "Z", "X"."""
    t0, used0 = time.perf_counter(), budget.used
    pairs = correlated = 0
    for path, m in loads:
        for _ in range(m):
            d = deliver_pair(hosts, budget, path, next(bases), wait)
            if not d.delivered:
                return RequestResult(False, pairs, budget.used - used0, correlated, time.perf_counter() - t0, d.reason)
            pairs += 1
            correlated += int(d.correlated)
    return RequestResult(True, pairs, budget.used - used0, correlated, time.perf_counter() - t0, "ok")

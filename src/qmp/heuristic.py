"""The paper's greedy placement heuristic (Algorithms 2 and 3) and a shortest-path baseline.

Each window's requests are handled in priority order on a shared working graph of residual
capacities. Capacities are stored as a plain dict of dicts: caps[u][v] = free seats on link u-v.
"""
from __future__ import annotations

import copy
import time
from collections import deque
from fractions import Fraction

import numpy as np

from qmp.core import Allocation, PlaceResult, Request, WindowInput, path_edges

Caps = dict[int, dict[int, int]]


def build_caps(win: WindowInput) -> Caps:
    """Working graph G': only links with residual capacity > 0 (Alg. 2)."""
    caps: Caps = {}
    for (u, v), c in sorted(win.capacity.items()):
        if c > 0 and win.graph.has_edge(u, v):
            caps.setdefault(u, {})[v] = c
            caps.setdefault(v, {})[u] = c
    return caps


def remove_link(caps: Caps, u: int, v: int) -> None:
    del caps[u][v]
    del caps[v][u]


def use_seats(caps: Caps, path: list[int], pairs: int) -> None:
    """Subtract `pairs` from every link of the path and drop links that reach 0 (A8: gamma seats)."""
    for u, v in path_edges(path):
        caps[u][v] -= pairs
        caps[v][u] -= pairs
        if caps[u][v] == 0:
            remove_link(caps, u, v)


def bottleneck(caps: Caps, path: list[int]) -> int:
    return min(caps[u][v] for u, v in zip(path, path[1:]))


def best_continuation(caps: Caps, start: int, d: int, banned: set[int]):
    """Fewest-hop route start -> d avoiding `banned`, ties broken by largest bottleneck (A9).

    Returns (hops, bottleneck), or None if there is no route.
    """
    dist = {d: 0}
    order = [d]
    queue = deque([d])
    while queue:
        v = queue.popleft()
        for u in sorted(caps.get(v, {})):
            if u not in dist and u not in banned:
                dist[u] = dist[v] + 1
                order.append(u)
                queue.append(u)
    if start not in dist:
        return None
    best = {d: None}  # None stands for "no limit" at the destination
    for v in order[1:]:
        options = [caps[v][u] if best[u] is None else min(caps[v][u], best[u])
                   for u in caps[v] if dist.get(u) == dist[v] - 1]
        best[v] = max(options)
    return dist[start], best[start]


def alpha_scores(graph_caps: Caps, path: list[int], d: int) -> dict[int, Fraction]:
    """alpha_i for every usable neighbour i of the walk's current node (A9).

    alpha_i = min(c(k,i), beta) / (1 + l), where beta and l belong to the best route i -> d that
    avoids the nodes already on `path`. Since 1 + l equals the hops from i to d, we divide by hops.
    Neighbours with no route are left out. Meant for a current node not next to d.
    """
    k = path[-1]
    banned = set(path)
    scores = {}
    for i in sorted(graph_caps.get(k, {})):
        if i in banned or i == d:
            continue
        route = best_continuation(graph_caps, i, d, banned)
        if route is not None:
            hops, beta = route
            scores[i] = Fraction(min(graph_caps[k][i], beta), hops)
    return scores


def pick_best(scores: dict[int, Fraction], rng: np.random.Generator, tie_break: str) -> int:
    """Neighbour with the highest alpha; ties by lowest id ('first') or seeded random (A9)."""
    top = max(scores.values())
    tied = sorted(i for i, a in scores.items() if a == top)
    if tie_break == "first" or len(tied) == 1:
        return tied[0]
    return tied[int(rng.integers(len(tied)))]


def greedy_walk(caps: Caps, s: int, d: int, rng: np.random.Generator, tie_break: str):
    """One walk from s to d (Alg. 3 lines 3-15). Returns the node list, or None at a dead end."""
    path = [s]
    while True:
        k = path[-1]
        if d in caps.get(k, {}):
            return path + [d]
        scores = alpha_scores(caps, path, d)
        if not scores:
            return None
        path.append(pick_best(scores, rng, tie_break))


def find_paths(caps: Caps, s: int, d: int, rng: np.random.Generator, tie_break: str):
    """Edge-disjoint paths with bottlenecks, found on a private copy of G' (A10)."""
    private = copy.deepcopy(caps)
    found = []
    while private.get(s):
        path = greedy_walk(private, s, d, rng, tie_break)
        if path is None:  # A11: a dead end ends the search, found paths are kept
            break
        found.append((path, bottleneck(private, path)))
        for u, v in path_edges(path):
            remove_link(private, u, v)
    return found


def choose_split(paths: list[tuple[list[int], int]], n: int, delta: int, multipath: bool):
    """Decide how n pairs go onto the sorted paths (Alg. 3 lines 22-35), or None if blocked."""
    for path, bc in paths:
        if bc >= n * delta:  # A12: first qualifying path takes everything
            return [(path, n)]
    if not multipath:
        return None
    if sum(bc // delta for _, bc in paths) < n:
        return None
    chosen, remaining = [], n
    for path, bc in paths:
        gamma = min(bc // delta, remaining)  # A8: seats consumed = gamma
        if gamma > 0:
            chosen.append((path, gamma))
            remaining -= gamma
    return chosen


def delta_for(policy: str, delta: int, rho: float) -> int:
    """'fixed' uses delta for all; 'deadline' uses 1 for requests on their last chance (Part C)."""
    if policy == "deadline" and rho == 1.0:
        return 1
    return delta


def request_order(win: WindowInput) -> list[Request]:
    """Highest rho first, then earlier arrival, then id (A16)."""
    return sorted(win.requests, key=lambda r: (-win.rho[r.id], r.a, r.id))


def place_heuristic(win: WindowInput, *, multipath: bool = True, delta: int = 2,
                    delta_policy: str = "fixed", tie_break: str = "random") -> PlaceResult:
    """MP-Heu (multipath=True) or SP-Heu (multipath=False) for one window (Alg. 2 and 3)."""
    start = time.perf_counter()
    caps = build_caps(win)
    rng = np.random.default_rng(win.seed)
    allocations = []
    for req in request_order(win):
        paths = find_paths(caps, req.s, req.d, rng, tie_break)
        paths = [(p, bc) for p, bc in paths if len(p) - 2 <= win.max_mid[req.id]]  # line 19
        paths.sort(key=lambda pb: -pb[1])  # stable
        d_r = delta_for(delta_policy, delta, win.rho[req.id])
        split = choose_split(paths, req.n, d_r, multipath)
        if split is None:
            continue
        for path, pairs in split:
            use_seats(caps, path, pairs)
        allocations.append(Allocation(req.id, split))
    return PlaceResult(allocations, "heuristic", time.perf_counter() - start)


def shortest_paths(caps: Caps, s: int, d: int) -> list[list[int]]:
    """All hop-shortest s -> d paths in the working graph."""
    dist = {s: 0}
    queue = deque([s])
    while queue:
        v = queue.popleft()
        for u in sorted(caps.get(v, {})):
            if u not in dist:
                dist[u] = dist[v] + 1
                queue.append(u)
    if d not in dist:
        return []
    results = []

    def extend(path: list[int]) -> None:
        v = path[-1]
        if v == d:
            results.append(path)
            return
        for u in sorted(caps[v]):
            if dist.get(u) == dist[v] + 1 and dist[u] <= dist[d]:
                extend(path + [u])

    extend([s])
    return results


def best_spf_path(caps: Caps, s: int, d: int):
    """Hop-shortest path; ties by largest bottleneck, then lexicographic node list (A4)."""
    candidates = shortest_paths(caps, s, d)
    if not candidates:
        return None
    return min(candidates, key=lambda p: (-bottleneck(caps, p), p))


def place_spf(win: WindowInput, *, delta: int = 2, delta_policy: str = "fixed") -> PlaceResult:
    """SP-SPF baseline: one hop-shortest path per request, same delta rule as the heuristics (A4)."""
    start = time.perf_counter()
    caps = build_caps(win)
    allocations = []
    for req in request_order(win):
        path = best_spf_path(caps, req.s, req.d)
        if path is None or len(path) - 2 > win.max_mid[req.id]:
            continue
        d_r = delta_for(delta_policy, delta, win.rho[req.id])
        if bottleneck(caps, path) >= req.n * d_r:
            use_seats(caps, path, req.n)
            allocations.append(Allocation(req.id, [(path, req.n)]))
    return PlaceResult(allocations, "heuristic", time.perf_counter() - start)

"""Shared data types and the referee for the multipath entanglement model (paper Sec. II).

Every placement method (heuristics, ILPs, QuantumLab player code) returns Allocations for one
window, and validate() checks them against the paper's rules, so all methods are judged alike.
"""
from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

Edge = tuple[int, int]


def edge(u: int, v: int) -> Edge:
    """Undirected edge key with the smaller node first (A6, A7)."""
    return (u, v) if u < v else (v, u)


def path_edges(path: list[int]) -> list[Edge]:
    return [edge(u, v) for u, v in zip(path, path[1:])]


@dataclass(frozen=True)
class Request:
    id: int
    s: int
    d: int
    n: int      # pairs demanded (A1)
    a: int      # arrival slot (A3, A24)
    h: int      # execution time in slots (A15)
    b: int      # deadline slot (A15)
    f: float    # minimum end-to-end fidelity (A5)


@dataclass
class WindowInput:
    """Everything a placement method sees for one window (Alg. 1 line 14)."""
    graph: nx.Graph
    capacity: dict[Edge, int]
    requests: list[Request]
    rho: dict[int, float]       # request id -> priority in this window
    max_mid: dict[int, int]     # request id -> max intermediate nodes I^r
    seed: int = 0               # tie-break seed, so every method is reproducible (A9, A19)


@dataclass
class Allocation:
    request_id: int
    paths: list[tuple[list[int], int]]   # (node sequence from s to d, pairs carried on it)


@dataclass
class PlaceResult:
    """What every placement method returns for one window."""
    allocations: list[Allocation]
    status: str = "heuristic"   # "heuristic" | "optimal" | "time_limit" (inconclusive) | "error"
    seconds: float = 0.0


def objective(win: WindowInput, allocs: list[Allocation]) -> float:
    """The paper's per-window objective: sum of rho over placed requests (A13)."""
    return sum(win.rho[a.request_id] for a in allocs)


def validate(win: WindowInput, allocs: list[Allocation]) -> list[str]:
    """Return every rule an answer breaks, in plain words. An empty list means the answer is legal."""
    errors: list[str] = []
    by_id = {r.id: r for r in win.requests}
    used: dict[Edge, int] = {}
    seen: set[int] = set()
    for alloc in allocs:
        req = by_id.get(alloc.request_id)
        if req is None:
            errors.append(f"Request {alloc.request_id} is not waiting in this round.")
            continue
        if req.id in seen:
            errors.append(f"Request {req.id} was placed twice.")
        seen.add(req.id)
        if not alloc.paths:
            errors.append(f"Request {req.id} was placed with no road.")
        taken: dict[Edge, int] = {}
        total = 0
        for k, (path, pairs) in enumerate(alloc.paths, 1):
            total += pairs
            if pairs < 1:
                errors.append(f"Request {req.id}, road {k}: every road must carry at least 1 pair.")
            if not path or path[0] != req.s or path[-1] != req.d:
                errors.append(f"Request {req.id}, road {k}: must start at {req.s} and end at {req.d}.")
                continue
            if len(set(path)) != len(path):
                errors.append(f"Request {req.id}, road {k}: visits a city twice ({'-'.join(map(str, path))}).")
            if len(path) - 2 > win.max_mid[req.id]:
                errors.append(f"Request {req.id}, road {k}: {len(path) - 2} middle cities, but at most "
                              f"{win.max_mid[req.id]} keep the pair clear enough (fidelity, A5).")
            for e in path_edges(path):
                if not win.graph.has_edge(*e):
                    errors.append(f"Request {req.id}, road {k}: there is no link {e[0]}-{e[1]}.")
                    continue
                if e in taken:
                    errors.append(f"Request {req.id}: roads {taken[e]} and {k} both use link {e[0]}-{e[1]}.")
                taken[e] = k
                used[e] = used.get(e, 0) + pairs
        if total != req.n:
            errors.append(f"Request {req.id}: promised {req.n} pairs but routed {total}. All or nothing.")
    for e, load in sorted(used.items()):
        cap = win.capacity.get(e, 0)
        if load > cap:
            errors.append(f"Link {e[0]}-{e[1]} has {cap} seats this round, but {load} pairs were routed over it.")
    return errors

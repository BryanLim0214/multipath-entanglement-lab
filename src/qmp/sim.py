"""The window-by-window simulation loop (paper Algorithm 1).

Every method sees the same requests and link outcomes for a given seed (A19), and every
answer is checked by the referee before it is accepted.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable

import numpy as np

from qmp.core import Allocation, Edge, PlaceResult, WindowInput, objective, validate
from qmp.fidelity import max_intermediate
from qmp.model import eligible_windows, grid, make_requests, rho_for, sample_capacity, windows


@dataclass
class SimConfig:
    rows: int
    cols: int
    R: int
    M: int
    T: int
    tc: int
    q: float
    F: float
    f: float
    n_spec: str
    seed: int


@dataclass
class WindowRecord:
    w: int
    capacity: dict[Edge, int]
    eligible: list[int]
    allocations: list[Allocation]
    objective: float
    status: str
    seconds: float


@dataclass
class SimResult:
    records: list[WindowRecord]
    requests: list
    placed: dict[int, Allocation] = field(default_factory=dict)
    blocking_ratio: float = 0.0
    gamma: float = 0.0
    total_seconds: float = 0.0
    time_limit_windows: int = 0


def make_window_input(cfg: SimConfig, graph, w: int, capacity, pending, rho_maps, max_mid) -> WindowInput:
    """Package one window for the placer (Alg. 1 line 14)."""
    return WindowInput(
        graph=graph, capacity=capacity, requests=pending,
        rho={r.id: rho_maps[r.id][w] for r in pending},
        max_mid={r.id: max_mid for r in pending},
        seed=cfg.seed * 1000 + w,  # A19
    )


def check_legal(win: WindowInput, result: PlaceResult, w: int) -> None:
    """Stop the run on a solver error or an illegal answer; never count either as 'nothing placed'."""
    if result.status == "error":
        raise RuntimeError(f"Window {w}: the placement method reported a solver error")
    errs = validate(win, result.allocations)
    if errs:
        raise RuntimeError(f"Window {w}: illegal answer: " + "; ".join(errs))


def summarize(records, requests, placed) -> tuple[float, float]:
    """Blocking ratio and the share of placed requests that used more than one path."""
    blocking = (len(requests) - len(placed)) / len(requests) if requests else 0.0
    multi = sum(1 for a in placed.values() if len(a.paths) > 1)
    return blocking, (multi / len(placed) if placed else 0.0)


def simulate(cfg: SimConfig, placer: Callable[[WindowInput], PlaceResult], *,
             record: bool = False) -> SimResult:
    """Run Algorithm 1 for one seed and one placement method.

    `record` is kept for the trace API; records are always kept because they are small.
    """
    graph = grid(cfg.rows, cfg.cols)
    wins = windows(cfg.T, cfg.tc)
    requests = make_requests(np.random.default_rng([cfg.seed, 0]), list(graph.nodes),
                             cfg.R, cfg.T, cfg.tc, cfg.n_spec, cfg.f)
    rho_maps = {r.id: rho_for(r, wins) for r in requests}
    eligible = {r.id: set(eligible_windows(r, wins)) for r in requests}
    max_mid = max_intermediate(cfg.F, cfg.f)
    placed: dict[int, Allocation] = {}
    records = []
    for w, _, _ in wins:
        capacity = sample_capacity(np.random.default_rng([cfg.seed, 1, w]), graph, cfg.M, cfg.q)
        pending = [r for r in requests if r.id not in placed and w in eligible[r.id]]  # A25
        win = make_window_input(cfg, graph, w, capacity, pending, rho_maps, max_mid)
        result = placer(win)
        check_legal(win, result, w)
        for alloc in result.allocations:
            placed[alloc.request_id] = alloc
        records.append(WindowRecord(w, capacity, [r.id for r in pending], result.allocations,
                                    objective(win, result.allocations), result.status, result.seconds))
    blocking, gamma = summarize(records, requests, placed)
    return SimResult(records, requests, placed, blocking, gamma,
                     sum(rec.seconds for rec in records),
                     sum(1 for rec in records if rec.status == "time_limit"))


def to_trace(result: SimResult, cfg: SimConfig) -> dict:
    """JSON-ready replay: config, requests, and per window capacities, eligible, allocations, blocked."""
    windows_out = []
    for rec in result.records:
        placed_now = {a.request_id for a in rec.allocations}
        windows_out.append({
            "w": rec.w,
            "capacity": {f"{u}-{v}": c for (u, v), c in sorted(rec.capacity.items())},
            "eligible": rec.eligible,
            "allocations": [{"request": a.request_id,
                             "paths": [{"nodes": p, "pairs": g} for p, g in a.paths]}
                            for a in rec.allocations],
            "blocked": [i for i in rec.eligible if i not in placed_now],
            "status": rec.status,
        })
    return {
        "config": asdict(cfg),
        "requests": [asdict(r) for r in result.requests],
        "windows": windows_out,
        "never_placed": [r.id for r in result.requests if r.id not in result.placed],
        "blocking_ratio": result.blocking_ratio,
    }

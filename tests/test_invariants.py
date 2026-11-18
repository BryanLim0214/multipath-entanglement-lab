"""The lab's check "the heuristic never beats the ILP", made precise per window (ASSUMPTIONS.md A21).

On the same window, every heuristic answer is also feasible for the ILP with the same delta cap, so
heuristic <= ILP-delta <= ILP must hold whenever both ILPs are solved to optimality.
"""
import networkx as nx
import numpy as np
import pytest

from qmp.core import Request, WindowInput, edge, objective
from qmp.heuristic import place_heuristic, place_spf
from qmp.ilp import solve_path
from qmp.model import grid

EPS = 1e-9


def random_window(seed: int) -> WindowInput:
    rng = np.random.default_rng([seed, 7])
    g = grid(3, 3)
    caps = {edge(u, v): int(rng.integers(0, 7)) for u, v in g.edges}
    nodes = list(g.nodes)
    reqs, rho = [], {}
    for i in range(int(rng.integers(2, 9))):
        s, d = rng.choice(nodes, size=2, replace=False)
        reqs.append(Request(i, int(s), int(d), int(rng.integers(1, 5)), 1, 1, 10, 0.78))
        rho[i] = float(rng.choice([1 / 3, 1 / 2, 2 / 3, 1.0]))
    return WindowInput(g, caps, reqs, rho, {r.id: 4 for r in reqs}, seed)


def deadline_deltas(win: WindowInput) -> dict[int, int]:
    return {r.id: 1 if win.rho[r.id] == 1.0 else 2 for r in win.requests}


@pytest.mark.parametrize("seed", range(80))
def test_heuristic_le_ilp_delta_le_ilp(seed):
    win = random_window(seed)
    ilp = solve_path(win)
    ilp_d2 = solve_path(win, delta=2)
    ilp_dd = solve_path(win, delta=deadline_deltas(win))
    sp_ilp_d2 = solve_path(win, K=1, delta=2)
    for res in (ilp, ilp_d2, ilp_dd, sp_ilp_d2):
        assert res.status == "optimal", "a time-limited solve would make this window inconclusive"
    o = {name: objective(win, r.allocations) for name, r in {
        "ilp": ilp, "ilp_d2": ilp_d2, "ilp_dd": ilp_dd, "sp_ilp_d2": sp_ilp_d2,
        "mp_heu": place_heuristic(win, delta=2),
        "mp_heu_deadline": place_heuristic(win, delta=2, delta_policy="deadline"),
        "sp_heu": place_heuristic(win, multipath=False, delta=2),
        "sp_spf": place_spf(win, delta=2),
    }.items()}
    assert o["mp_heu"] <= o["ilp_d2"] + EPS
    assert o["mp_heu_deadline"] <= o["ilp_dd"] + EPS
    assert o["sp_heu"] <= o["sp_ilp_d2"] + EPS
    assert o["sp_spf"] <= o["sp_ilp_d2"] + EPS
    assert o["ilp_d2"] <= o["ilp_dd"] + EPS <= o["ilp"] + 2 * EPS

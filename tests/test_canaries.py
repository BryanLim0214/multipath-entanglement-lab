"""Canaries: deliberately broken answers and a broken solver, to show the tests would notice."""
import networkx as nx
import pytest

from qmp import ilp
from qmp.core import Allocation, PlaceResult, Request, WindowInput, edge, objective, validate


def line_window() -> WindowInput:
    """Path 1-2-3 with 1 seat per link and two requests that each want 1 pair: only one can be served."""
    g = nx.Graph([(1, 2), (2, 3)])
    caps = {edge(1, 2): 1, edge(2, 3): 1}
    reqs = [Request(1, 1, 3, 1, 1, 1, 9, 0.8), Request(2, 1, 3, 1, 1, 1, 9, 0.8)]
    return WindowInput(g, caps, reqs, {1: 1.0, 2: 1.0}, {1: 2, 2: 2})


def test_canary_a_over_capacity_is_caught():
    win = line_window()
    both = [Allocation(1, [([1, 2, 3], 1)]), Allocation(2, [([1, 2, 3], 1)])]
    assert any("seats" in e for e in validate(win, both))


def test_canary_b_edge_reuse_within_request_is_caught():
    g = nx.Graph([(1, 2), (2, 3)])
    win = WindowInput(g, {edge(1, 2): 4, edge(2, 3): 4}, [Request(1, 1, 3, 2, 1, 1, 9, 0.8)], {1: 1.0}, {1: 2})
    reuse = [Allocation(1, [([1, 2, 3], 1), ([1, 2, 3], 1)])]
    assert any("both use link" in e for e in validate(win, reuse))


@pytest.mark.parametrize("fn", [ilp.solve_path, ilp.solve_arc])
def test_canary_c_dropping_constraint_4c_is_caught(fn, monkeypatch):
    win = line_window()
    assert validate(win, fn(win).allocations) == []          # honest solver is legal
    assert objective(win, fn(win).allocations) == 1.0
    monkeypatch.setattr(ilp, "_canary_drop_capacity", True)
    broken = fn(win)
    assert objective(win, broken.allocations) == 2.0         # it now "serves" both
    assert any("seats" in e for e in validate(win, broken.allocations))


def test_canary_d_heuristic_above_ilp_is_flagged():
    win = line_window()
    best = ilp.solve_path(win)
    fake = PlaceResult([Allocation(1, [([1, 2, 3], 1)]), Allocation(2, [([1, 2, 3], 1)])], "heuristic")
    invariant_holds = objective(win, fake.allocations) <= objective(win, best.allocations) + 1e-9
    assert not invariant_holds                               # the invariant check flags the fake
    assert validate(win, fake.allocations) != []             # and the referee rejects it as illegal

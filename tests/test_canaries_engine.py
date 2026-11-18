"""Planted bugs in the engine. Each mutation must make one of our real checks fail, proving the checks have teeth."""
import numpy as np
import pytest

import qmp.heuristic as heuristic
import qmp.model as model
import qmp.sim as sim
from qmp.core import edge, objective
from qmp.ilp import solve_path
from qmp.model import load_toys
from test_fig1_example import fig1_window
from test_model import req
from test_toys import build


def fig1_matches_paper() -> bool:
    """The Fig. 1 / Fig. 1c check, as a yes/no answer."""
    win = fig1_window()
    result = heuristic.place_heuristic(win, tie_break="first")
    if result.allocations[0].paths != [([7, 8, 5, 6], 2), ([7, 1, 2, 4, 6], 2)]:
        return False
    caps = heuristic.build_caps(win)
    for path, pairs in result.allocations[0].paths:
        heuristic.use_seats(caps, path, pairs)
    residual = {edge(u, v): c for u in caps for v, c in caps[u].items()}
    fig1c = {(7, 8): 3, (5, 8): 6, (5, 6): 2, (1, 7): 2, (1, 2): 4, (2, 4): 2, (4, 6): 2}
    return all(residual.get(e, 0) == c for e, c in fig1c.items())


def test_unmutated_engine_matches_fig1():
    assert fig1_matches_paper()


def test_canary_seats_used_twice(monkeypatch):
    real = heuristic.use_seats
    monkeypatch.setattr(heuristic, "use_seats", lambda caps, path, pairs: real(caps, path, 2 * pairs))
    assert not fig1_matches_paper()


def test_canary_alpha_forgets_first_hop(monkeypatch):
    def bad_alpha(graph_caps, path, d):
        k, banned, scores = path[-1], set(path), {}
        for i in sorted(graph_caps.get(k, {})):
            if i not in banned and i != d:
                route = heuristic.best_continuation(graph_caps, i, d, banned)
                if route is not None:
                    scores[i] = heuristic.Fraction(route[1], route[0])  # mutation: ignores c(k, i)
        return scores
    monkeypatch.setattr(heuristic, "alpha_scores", bad_alpha)
    assert not fig1_matches_paper()


def test_canary_eligibility_ignores_execution_time(monkeypatch):
    real = model.eligible_windows
    monkeypatch.setattr(model, "eligible_windows",
                        lambda r, wins: real(r.__class__(r.id, r.s, r.d, r.n, r.a, 1, r.b, r.f), wins))
    assert model.eligible_windows(req(8, 4, 30), model.windows(100, 10)) != [2, 3]


def test_canary_broken_same_dice(monkeypatch):
    monkeypatch.setattr(sim, "sample_capacity",
                        lambda rng, g, M, q: model.sample_capacity(np.random.default_rng(), g, M, q))
    cfg = sim.SimConfig(3, 3, 20, 6, 50, 10, 0.6, 0.95, 0.78, "uniform:1:3", 1)
    a = sim.simulate(cfg, heuristic.place_spf)
    b = sim.simulate(cfg, heuristic.place_heuristic)
    assert any(ra.capacity != rb.capacity for ra, rb in zip(a.records, b.records))


def test_canary_heuristic_ignoring_delta_beats_ilp_delta(monkeypatch):
    win, _ = build(load_toys()["toy1"], max_mid=4)
    ilp_d2 = objective(win, solve_path(win, delta=2).allocations)
    monkeypatch.setattr(heuristic, "delta_for", lambda policy, delta, rho: 1)
    heu = objective(win, heuristic.place_heuristic(win, delta=2).allocations)
    assert heu > ilp_d2  # the invariant heu <= ILP-delta would flag this mutation

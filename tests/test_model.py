"""Direct checks of the model: windows, eligibility (A14), priority rho, request generation, same dice (A19)."""
import numpy as np
import pytest

from qmp.core import Request
from qmp.heuristic import place_heuristic, place_spf
from qmp.model import eligible_windows, grid, make_requests, rho_for, sample_capacity, windows
from qmp.sim import SimConfig, simulate


def req(a, h, b):
    return Request(0, 1, 2, 1, a, h, b, 0.78)


def test_paper_small_setup_has_ten_windows():
    wins = windows(100, 10)
    assert len(wins) == 10
    assert wins[0] == (1, 1, 10) and wins[-1] == (10, 91, 100)


@pytest.mark.parametrize("a, h, b, expected", [
    (9, 4, 14, [2]),          # cannot fit in window 1 (would end at slot 12 > 10); fits exactly in window 2
    (8, 3, 30, [1, 2, 3]),    # slots 8-10 fit window 1
    (8, 4, 30, [2, 3]),       # one more slot of execution pushes it out of window 1
    (1, 1, 100, list(range(1, 11))),
    (95, 4, 98, [10]),        # slots 95-98 fit inside window 10 (91-100) and meet the deadline exactly
    (98, 4, 103, []),         # would end at slot 101, past T = 100: no window fits
])
def test_eligibility(a, h, b, expected):
    assert eligible_windows(req(a, h, b), windows(100, 10)) == expected


def test_rho_gives_last_chance_one():
    wins = windows(100, 10)
    rho = rho_for(req(8, 3, 30), wins)
    assert rho == {1: pytest.approx(1 / 3), 2: pytest.approx(2 / 3), 3: 1.0}


def test_requests_respect_the_generation_rules():
    rng = np.random.default_rng([3, 0])
    reqs = make_requests(rng, list(grid(3, 3).nodes), 500, 100, 10, "uniform:2:4", 0.78)
    for r in reqs:
        assert r.s != r.d
        assert 2 <= r.n <= 4
        assert 1 <= r.h <= 4
        assert r.a >= 1
        assert r.a + r.h + 1 <= r.b <= 100


def test_capacity_is_binomial_range_and_seeded():
    g = grid(3, 3)
    c1 = sample_capacity(np.random.default_rng([1, 1, 4]), g, 6, 0.7)
    c2 = sample_capacity(np.random.default_rng([1, 1, 4]), g, 6, 0.7)
    assert c1 == c2
    assert all(0 <= c <= 6 for c in c1.values())


def test_same_dice_in_every_window_across_methods():
    cfg = SimConfig(3, 3, 30, 6, 100, 10, 0.6, 0.95, 0.78, "uniform:1:3", 5)
    a = simulate(cfg, place_spf)
    b = simulate(cfg, place_heuristic)
    assert len(a.records) == len(b.records) == 10
    for ra, rb in zip(a.records, b.records):
        assert ra.capacity == rb.capacity

"""Re-traces the paper's Fig. 1 example (request 7 -> 6, n=4, delta=2) with the heuristic."""
from fractions import Fraction

import pytest

from qmp.core import Request, WindowInput, edge, validate
from qmp.heuristic import alpha_scores, build_caps, place_heuristic
from qmp.model import fig1_graph


def fig1_window(seed=0):
    graph, caps = fig1_graph()
    req = Request(id=0, s=7, d=6, n=4, a=1, h=1, b=10, f=0.78)
    return WindowInput(graph, caps, [req], {0: 1.0}, {0: 4}, seed)


def test_first_tie_break_matches_fig1c():
    win = fig1_window()
    result = place_heuristic(win, tie_break="first")
    assert validate(win, result.allocations) == []
    assert result.allocations[0].paths == [([7, 8, 5, 6], 2), ([7, 1, 2, 4, 6], 2)]
    expected = dict(win.capacity)
    for u, v, c in [(7, 8, 3), (8, 5, 6), (5, 6, 2), (7, 1, 2), (1, 2, 4), (2, 4, 2), (4, 6, 2)]:
        expected[edge(u, v)] = c
    # Re-run on the shared working graph to read residuals back out.
    from qmp.heuristic import use_seats
    caps = build_caps(win)
    for path, pairs in result.allocations[0].paths:
        use_seats(caps, path, pairs)
    residual = {edge(u, v): c for u in caps for v, c in caps[u].items()}
    for e, c in expected.items():
        assert residual.get(e, 0) == c


@pytest.mark.parametrize("seed", range(20))
def test_random_tie_break_keeps_the_paper_shape(seed):
    win = fig1_window(seed)
    result = place_heuristic(win, tie_break="random")
    assert validate(win, result.allocations) == []
    paths = [p for p, _ in result.allocations[0].paths]
    assert paths[0] in ([7, 8, 5, 6], [7, 8, 9, 6])
    assert paths[1] == [7, 1, 2, 4, 6]


def test_alpha_values():
    caps = build_caps(fig1_window())
    at7 = alpha_scores(caps, [7], 6)
    assert float(at7[1]) == pytest.approx(4 / 3)
    assert at7[8] == Fraction(2)
    at8 = alpha_scores(caps, [7, 8], 6)
    assert at8[5] == 4 and at8[9] == 4
    # The paper prints alpha_3 = 4/2; the rule that reproduces the other four values gives 3/2.
    # This is a documented paper inconsistency (ASSUMPTIONS.md, inconsistency 2).
    assert float(at8[3]) == pytest.approx(1.5)

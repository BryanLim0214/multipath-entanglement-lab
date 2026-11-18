"""On 200 random 3x3 windows the path ILP must equal the arc ILP, and the ordering MP >= SP, ILP >= ILP-delta must hold."""
import networkx as nx
import numpy as np
import pytest

from qmp import ilp
from qmp.core import Request, WindowInput, edge, objective, validate

RHOS = [1 / 3, 1 / 2, 2 / 3, 1.0]


def random_window(seed: int) -> WindowInput:
    """3x3 grid, nodes 1..9 row-major, capacities 0..6, 2..6 requests, n 1..4, max_mid 4."""
    rng = np.random.default_rng(seed)
    g = nx.grid_2d_graph(3, 3)
    g = nx.relabel_nodes(g, {(r, c): 3 * r + c + 1 for r, c in g.nodes})
    g = nx.Graph(sorted(g.edges))
    caps = {edge(u, v): int(rng.integers(0, 7)) for u, v in g.edges}
    reqs, rho = [], {}
    for i in range(1, int(rng.integers(2, 7)) + 1):
        s, d = (int(v) for v in rng.choice(np.arange(1, 10), size=2, replace=False))
        reqs.append(Request(i, s, d, int(rng.integers(1, 5)), 1, 1, 9, 0.8))
        rho[i] = float(RHOS[rng.integers(0, 4)])
    return WindowInput(g, caps, reqs, rho, {r.id: 4 for r in reqs})


def value(win, res) -> float:
    assert res.status == "optimal"
    return objective(win, res.allocations)


@pytest.mark.parametrize("seed", range(200))
def test_path_equals_arc(seed):
    win = random_window(seed)
    path = ilp.solve_path(win)
    arc = ilp.solve_arc(win)
    arc_dir = ilp.solve_arc(win, directed_disjoint=True)
    assert validate(win, path.allocations) == []
    assert validate(win, arc.allocations) == []
    assert value(win, path) == pytest.approx(value(win, arc), abs=1e-6)
    assert value(win, arc_dir) >= value(win, arc) - 1e-6          # directed disjointness is looser
    assert value(win, path) >= value(win, ilp.solve_path(win, K=1)) - 1e-6    # MP >= SP
    assert value(win, path) >= value(win, ilp.solve_path(win, delta=2)) - 1e-6  # ILP >= ILP-delta


@pytest.mark.parametrize("seed", range(200))
def test_single_path_model_equals_general(seed):
    """solve_path(K=1) uses the small single-path model; it must match the general path model with K=1,
    with and without the A21 cap."""
    win = random_window(seed)
    for delta in (None, 2):
        small = ilp.solve_single_path(win, delta=delta)
        general = ilp.solve_path_general(win, K=1, delta=delta)
        assert validate(win, small.allocations) == []
        assert all(len(a.paths) == 1 for a in small.allocations)
        assert value(win, small) == pytest.approx(value(win, general), abs=1e-6)

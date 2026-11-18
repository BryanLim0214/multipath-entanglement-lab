"""Random-window checks: every heuristic answer must pass the referee."""
from functools import partial

import numpy as np

from qmp.core import Request, WindowInput, edge, objective, validate
from qmp.heuristic import place_heuristic, place_spf
from qmp.model import grid

METHODS = {
    "spf": place_spf,
    "sp_heu": partial(place_heuristic, multipath=False),
    "mp_heu": place_heuristic,
    "mp_heu_deadline": partial(place_heuristic, delta_policy="deadline"),
}


def random_window(rng, graph, seed):
    caps = {edge(u, v): int(rng.integers(0, 7)) for u, v in graph.edges}
    nodes = list(graph.nodes)
    reqs, rho = [], {}
    for i in range(int(rng.integers(2, 11))):
        s, d = rng.choice(nodes, size=2, replace=False)
        reqs.append(Request(i, int(s), int(d), int(rng.integers(1, 6)), 1, 1, 10, 0.78))
        rho[i] = float(rng.choice([1 / 3, 1 / 2, 2 / 3, 1.0]))
    return WindowInput(graph, caps, reqs, rho, {r.id: 4 for r in reqs}, seed)


def test_all_heuristics_are_legal_on_random_windows():
    rng = np.random.default_rng(123)
    graph = grid(3, 3)
    mp_beats_sp = mp_loses_to_sp = 0
    for k in range(300):
        win = random_window(rng, graph, k)
        scores = {}
        for name, method in METHODS.items():
            result = method(win)
            assert validate(win, result.allocations) == [], (name, k)
            scores[name] = objective(win, result.allocations)
            if name in ("spf", "sp_heu"):
                assert all(len(a.paths) == 1 for a in result.allocations)
        mp_beats_sp += scores["mp_heu"] > scores["sp_heu"]
        mp_loses_to_sp += scores["mp_heu"] < scores["sp_heu"]
    # Greedy gives no guarantee that MP >= SP per window, so we only record the counts.
    print(f"MP-Heu better in {mp_beats_sp} windows, worse in {mp_loses_to_sp}")

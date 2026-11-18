"""Runs the heuristic on the hand-solved toys from tests/toy_expected.md."""
import networkx as nx

from qmp.core import Request, WindowInput, edge, objective, validate
from qmp.fidelity import max_intermediate
from qmp.heuristic import place_heuristic
from qmp.model import load_toys


def toy_window(toy):
    graph = nx.Graph()
    caps = {}
    for u, v, c in toy["edges"]:
        graph.add_edge(u, v)
        caps[edge(u, v)] = c
    reqs = [Request(i, r["s"], r["d"], r["n"], 1, 1, 10, 0.5) for i, r in enumerate(toy["requests"])]
    rho = {i: r["rho"] for i, r in enumerate(toy["requests"])}
    max_mid = {i: toy["I"] for i in range(len(reqs))}
    return WindowInput(graph, caps, reqs, rho, max_mid, seed=0)


def run(toy, **kw):
    win = toy_window(toy)
    result = place_heuristic(win, **kw)
    assert validate(win, result.allocations) == []
    return objective(win, result.allocations)


def test_toy1_delta2():
    assert run(load_toys()["toy1"]) == 1.0


def test_toy1_deadline_policy():
    assert run(load_toys()["toy1"], delta_policy="deadline") == 2.0


def test_toy2_delta2():
    toy = load_toys()["toy2"]
    assert max_intermediate(toy["F"], toy["f"]) == toy["I"]
    assert run(toy) == 0.0

"""Tests for Part B (QuNetSim). Fast unit tests need no simulator: budget statistics, the closed-form
success probability against a Monte-Carlo run of the same budget logic, routing, and pair splitting.
One integration test runs a tiny chain experiment in a separate process (QuNetSim keeps one network per process).
"""
import json
import pathlib
import subprocess
import sys
from inspect import signature
from math import ceil, floor

import networkx as nx
import numpy as np
import pytest
from scipy.stats import binom

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from partB_qunetsim import analytic, routing, topologies   # noqa: E402
from partB_qunetsim.budget import Budget, dry_request       # noqa: E402


# ---------- Budget ----------
def test_budget_attempt_success_rate_matches_q():
    b = Budget([("x", "y")], M=4, q=0.6, seed=1)
    draws = []
    for w in range(2000):
        b.new_window(w)
        draws += [b.attempt("x", "y") for _ in range(4)]
    p = np.mean(draws)
    assert abs(p - 0.6) < 4 * np.sqrt(0.6 * 0.4 / len(draws))


def test_budget_hop_lands_matches_binomial():
    M, q, windows = 4, 0.5, 4000
    b = Budget([("x", "y")], M=M, q=q, seed=2)
    landed = []
    for w in range(windows):
        b.new_window(w)
        landed.append(b.hop_lands("x", "y"))
    expected = binom.sf(0, M, q)                      # P(at least one success in M attempts)
    assert abs(np.mean(landed) - expected) < 4 * np.sqrt(expected * (1 - expected) / windows)


def test_budget_runs_dry_after_M_attempts_and_refills():
    b = Budget([("x", "y")], M=3, q=0.0, seed=3)
    assert [b.attempt("y", "x") for _ in range(4)] == [False, False, False, None]
    b.new_window(1)
    assert b.attempt("x", "y") is False


def test_budget_same_seed_same_dice_and_q1_always_lands():
    edges = [("a", "b"), ("b", "c")]
    one, two = Budget(edges, 5, 0.5, seed=7), Budget(edges, 5, 0.5, seed=7)
    for b in (one, two):
        b.new_window(3)
    assert [one.attempt("a", "b") for _ in range(5)] == [two.attempt("a", "b") for _ in range(5)]
    sure = Budget(edges, 5, 1.0, seed=7)
    assert all(sure.attempt("b", "c") for _ in range(5))


# ---------- analytic vs Monte Carlo of the budget logic ----------
def monte_carlo(n, q, M, paths, windows, seed):
    graph, _ = topologies.two_branch()
    b = Budget(graph.edges, M, q, seed)
    wins = 0
    for w in range(windows):
        b.new_window(w)
        wins += dry_request(b, routing.split_pairs(n, paths))
    return wins / windows


@pytest.mark.parametrize("n", [1, 2, 3, 4])
@pytest.mark.parametrize("q", [0.5, 0.7, 0.9])
def test_analytic_matches_monte_carlo(n, q):
    a_path, b_path = ["S", "a1", "a2", "D"], ["S", "b1", "b2", "D"]
    windows = 4000
    for paths, exact in (([a_path], analytic.p_sp(n, 4, q)), ([a_path, b_path], analytic.p_mp(n, 4, q))):
        est = monte_carlo(n, q, 4, paths, windows, seed=11)
        assert abs(est - exact) < 4 * np.sqrt(exact * (1 - exact) / windows) + 1e-9


def test_analytic_pieces():
    assert analytic.p_at_least(2, 4, 0.7) == pytest.approx(binom.sf(1, 4, 0.7))
    assert analytic.p_at_least(0, 4, 0.7) == 1.0
    assert analytic.p_mp(1, 4, 0.6) == pytest.approx(analytic.p_at_least(1, 4, 0.6) ** 3)   # floor(1/2) = 0 counts as 1
    assert analytic.p_sp(1, 4, 0.6, links=2) == pytest.approx((1 - 0.4 ** 4) ** 2)
    n, q = 4, 0.8
    assert analytic.p_mp(n, 4, q) == pytest.approx(
        binom.sf(ceil(n / 2) - 1, 4, q) ** 3 * binom.sf(floor(n / 2) - 1, 4, q) ** 3)


# ---------- routing ----------
def edge_set(path):
    return {frozenset(e) for e in zip(path, path[1:])}


def test_k_disjoint_two_branch():
    g, _ = topologies.two_branch()
    paths = routing.k_disjoint_paths(g, "S", "D", 2)
    assert len(paths) == 2
    assert not edge_set(paths[0]) & edge_set(paths[1])
    assert all(p[0] == "S" and p[-1] == "D" for p in paths)
    assert routing.k_disjoint_paths(g, "S", "D", 1)[0] == paths[0]


def test_k_disjoint_grid_is_disjoint_short_and_accepts_digraph():
    g, _ = topologies.grid(3, 3)
    for graph in (g, nx.DiGraph(g)):
        for s, d in [("n00", "n22"), ("n11", "n02"), ("n01", "n21")]:
            paths = routing.k_disjoint_paths(graph, s, d, 3)
            used = [edge_set(p) for p in paths]
            assert 1 <= len(paths) <= 3
            assert all(not (used[i] & used[j]) for i in range(len(used)) for j in range(i))
            assert all(len(p) - 2 <= routing.MAX_INTERMEDIATE for p in paths)
            assert [len(p) for p in paths] == sorted(len(p) for p in paths)


def test_hop_limit_drops_long_path_and_falls_back():
    ring = nx.cycle_graph(10)             # 0-1-...-9-0: the second path from 0 to 3 has 6 intermediate nodes
    paths = routing.k_disjoint_paths(ring, 0, 3, 2)
    assert paths == [[0, 1, 2, 3]]
    long_only = nx.Graph([(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7)])
    assert routing.k_disjoint_paths(long_only, 0, 7, 2) == [list(range(8))]       # 6 intermediates: falls back


def test_dispenser_has_three_parameters_and_hands_out_in_turn():
    a, b = ["S", "a1", "a2", "D"], ["S", "b1", "b2", "D"]
    f = routing.make_dispenser([a, b])
    assert len(signature(f).parameters) == 3
    assert [f(None, "S", "D") for _ in range(3)] == [a, b, a]
    assert f.handed == [a, b, a]


@pytest.mark.parametrize("n", range(1, 10))
@pytest.mark.parametrize("k", [1, 2, 3])
def test_split_adds_up_and_is_even(n, k):
    paths = [[f"p{i}", "x"] for i in range(k)]
    loads = routing.split_pairs(n, paths)
    counts = [m for _, m in loads]
    assert sum(counts) == n
    assert max(counts) - min(counts) <= 1 and counts == sorted(counts, reverse=True)
    assert all(m > 0 for m in counts)


def test_topologies_shapes():
    c, _ = topologies.chain()
    t, _ = topologies.two_branch()
    g, _ = topologies.grid(3, 3)
    assert sorted(c.nodes) == ["A", "B", "C"] and c.number_of_edges() == 2
    assert t.number_of_nodes() == 6 and t.number_of_edges() == 6
    assert g.number_of_nodes() == 9 and g.number_of_edges() == 12
    assert "n11" in g and nx.edge_connectivity(t, "S", "D") == 2


# ---------- one small QuNetSim run, in its own process ----------
def test_chain_at_q1_with_qunetsim():
    out = subprocess.run([sys.executable, "-m", "partB_qunetsim.run_partB", "--smoke"], cwd=ROOT,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res["success_rate"] == 1.0 and res["requests"] == 3
    assert res["correlated"] == res["delivered"] == 3        # every delivered pair passed the Z/X check
    assert res["timeouts"] == 0 and res["dice_mismatches"] == 0
    assert res["run_seconds"] < 20           # the 3 requests only; EQSN process start-up is excluded

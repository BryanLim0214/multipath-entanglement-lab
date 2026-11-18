"""An independent exhaustive solver, written here, must agree with solve_path on small random graphs."""
from itertools import combinations, product

import networkx as nx
import numpy as np
import pytest

from qmp import ilp
from qmp.core import Request, WindowInput, edge, objective, validate


def simple_paths(adj, s, d, max_edges):
    """All simple s-d paths with at most max_edges edges, by plain depth-first search."""
    out, stack = [], [[s]]
    while stack:
        p = stack.pop()
        if p[-1] == d:
            out.append(p)
            continue
        if len(p) - 1 >= max_edges:
            continue
        stack += [p + [w] for w in adj[p[-1]] if w not in p]
    return out


def edge_set(p):
    return {edge(a, b) for a, b in zip(p, p[1:])}


def splits(n, parts):
    """Every way to write n as an ordered sum of `parts` integers >= 1."""
    return [c for c in product(range(1, n + 1), repeat=parts) if sum(c) == n]


def options_for(win, adj, r):
    """Every way to serve r: a set of pairwise edge-disjoint allowed paths and a split of n over them."""
    paths = [p for p in simple_paths(adj, r.s, r.d, win.max_mid[r.id] + 1)
             if all(win.capacity[e] > 0 for e in edge_set(p))]
    opts = []
    for m in range(1, r.n + 1):
        for combo in combinations(paths, m):
            sets = [edge_set(p) for p in combo]
            if any(a & b for a, b in combinations(sets, 2)):
                continue
            for split in splits(r.n, m):
                load = {}
                for es, c in zip(sets, split):
                    for e in es:
                        load[e] = load.get(e, 0) + c
                opts.append(load)
    return opts


def brute_force(win) -> float:
    """Best sum of rho over every choice of (serve with some option) or (skip) for each request."""
    adj = {v: list(win.graph[v]) for v in win.graph}
    opts = [options_for(win, adj, r) + [None] for r in win.requests]
    best = 0.0
    for choice in product(*opts):
        used = {}
        for load in choice:
            for e, c in (load or {}).items():
                used[e] = used.get(e, 0) + c
        if all(c <= win.capacity[e] for e, c in used.items()):
            best = max(best, sum(win.rho[r.id] for r, o in zip(win.requests, choice) if o is not None))
    return best


def small_window(seed: int) -> WindowInput:
    rng = np.random.default_rng(1000 + seed)
    nodes = int(rng.integers(4, 7))
    while True:
        g = nx.gnp_random_graph(nodes, 0.6, seed=int(rng.integers(0, 10**6)))
        if nx.is_connected(g):
            break
    g = nx.relabel_nodes(g, {v: v + 1 for v in g.nodes})
    caps = {edge(u, v): int(rng.integers(0, 4)) for u, v in g.edges}
    reqs, rho = [], {}
    for i in range(1, int(rng.integers(1, 4)) + 1):
        s, d = (int(v) for v in rng.choice(np.arange(1, nodes + 1), size=2, replace=False))
        reqs.append(Request(i, s, d, int(rng.integers(1, 4)), 1, 1, 9, 0.8))
        rho[i] = float(rng.choice([1 / 3, 1 / 2, 2 / 3, 1.0]))
    return WindowInput(g, caps, reqs, rho, {r.id: int(rng.integers(1, 5)) for r in reqs})


@pytest.mark.parametrize("seed", range(150))
def test_path_ilp_matches_brute_force(seed):
    win = small_window(seed)
    res = ilp.solve_path(win)
    assert res.status == "optimal"
    assert validate(win, res.allocations) == []
    assert objective(win, res.allocations) == pytest.approx(brute_force(win), abs=1e-6)

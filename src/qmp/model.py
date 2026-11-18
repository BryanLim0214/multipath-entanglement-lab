"""Network, request and capacity generators for the simulation (paper Sec. II and IV).

Builds the grid and Fig. 1 networks, the windows, random requests and per-window link capacities.
"""
from __future__ import annotations

import math
from pathlib import Path

import networkx as nx
import numpy as np
import yaml

from qmp.core import Edge, Request, edge

FIG1_CAPACITIES = {
    (1, 2): 6, (2, 4): 4, (4, 6): 4, (2, 3): 3, (4, 5): 5, (1, 3): 2, (1, 7): 4,
    (3, 5): 4, (3, 8): 3, (5, 8): 8, (5, 6): 4, (6, 9): 7, (7, 8): 5, (8, 9): 4,
}


def grid(rows: int, cols: int) -> nx.Graph:
    """Grid graph with nodes numbered 1..rows*cols in row-major order."""
    g = nx.Graph()
    g.add_nodes_from(range(1, rows * cols + 1))
    for r in range(rows):
        for c in range(cols):
            node = r * cols + c + 1
            if c + 1 < cols:
                g.add_edge(node, node + 1)
            if r + 1 < rows:
                g.add_edge(node, node + cols)
    return g


def fig1_graph() -> tuple[nx.Graph, dict[Edge, int]]:
    """The paper's Fig. 1a network and its link capacities."""
    caps = {edge(u, v): c for (u, v), c in FIG1_CAPACITIES.items()}
    g = nx.Graph()
    g.add_edges_from(caps)
    return g, caps


def load_toys(path: str = "tests/toy_expected.md") -> dict:
    """Parse the fenced yaml block of the hand-solved toys file."""
    text = Path(path).read_text(encoding="utf-8")
    start = text.index("```yaml") + len("```yaml")
    end = text.index("```", start)
    return yaml.safe_load(text[start:end])


def windows(T: int, tc: int) -> list[tuple[int, int, int]]:
    """Windows (w, A_w, B_w), numbered from 1 (A24)."""
    count = math.ceil(T / tc)
    return [(w, (w - 1) * tc + 1, min(w * tc, T)) for w in range(1, count + 1)]


def draw_pairs(rng: np.random.Generator, n_spec: str) -> int:
    """Draw n from a spec such as 'uniform:2:4', both ends inclusive (A1)."""
    kind, lo, hi = n_spec.split(":")
    if kind != "uniform":
        raise ValueError(f"Unknown n spec '{n_spec}'.")
    return int(rng.integers(int(lo), int(hi) + 1))


def make_requests(rng: np.random.Generator, nodes: list[int], R: int, T: int, tc: int,
                  n_spec: str, f: float) -> list[Request]:
    """R random requests with ids 0..R-1 (A1, A3, A15, A23, A24)."""
    nodes = sorted(nodes)
    requests = []
    for rid in range(R):
        s = nodes[int(rng.integers(len(nodes)))]  # A23: uniform over distinct pairs
        others = [v for v in nodes if v != s]
        d = others[int(rng.integers(len(others)))]
        a = max(1, int(rng.poisson(tc / 4)))  # A3, A24
        h = int(rng.integers(1, 5))  # A15
        if a + h + 1 > T:
            raise ValueError(f"Arrival {a} leaves no room for a deadline within T={T}.")
        b = int(rng.integers(a + h + 1, T + 1))  # A15
        n = draw_pairs(rng, n_spec)
        requests.append(Request(id=rid, s=s, d=d, n=n, a=a, h=h, b=b, f=f))
    return requests


def eligible_windows(req: Request, wins: list[tuple[int, int, int]]) -> list[int]:
    """Windows where the request can run entirely inside the window (A14)."""
    return [w for w, A, B in wins if max(req.a, A) + req.h - 1 <= min(req.b, B)]


def rho_for(req: Request, wins: list[tuple[int, int, int]]) -> dict[int, float]:
    """Priority i/|W_r| in the i-th eligible window (paper Sec. II)."""
    elig = sorted(eligible_windows(req, wins))
    return {w: (i + 1) / len(elig) for i, w in enumerate(elig)}


def sample_capacity(rng: np.random.Generator, graph: nx.Graph, M: int, q) -> dict[Edge, int]:
    """Binomial(M, q) capacity per edge, q a float or a per-edge dict (A6)."""
    caps = {}
    for u, v in sorted(edge(*e) for e in graph.edges):
        prob = q[(u, v)] if isinstance(q, dict) else q
        caps[(u, v)] = int(rng.binomial(M, prob))
    return caps

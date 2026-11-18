"""Backs the E4 explanation in docs/partB_vs_partA.md: on the 3x3 grid, how often is the second
disjoint path from routing.k_disjoint_paths longer than the shortest path? Pure networkx, no simulator."""
import itertools

import networkx as nx

from partB_qunetsim import routing


def grid_graph():
    """The Part B 3x3 grid (same edges as topologies.grid), nodes n00..n22, undirected."""
    g = nx.grid_2d_graph(3, 3)
    return nx.relabel_nodes(g, {(r, c): f"n{r}{c}" for r, c in g.nodes})


def test_half_of_grid_pairs_have_a_longer_second_path():
    g = grid_graph()
    longer = equal = 0
    for s, d in itertools.combinations(sorted(g.nodes), 2):
        paths = routing.k_disjoint_paths(g, s, d, 2)
        assert len(paths) == 2
        links = [{frozenset(e) for e in zip(p, p[1:])} for p in paths]
        assert not links[0] & links[1]          # no shared link, in either direction
        extra = (len(paths[1]) - 1) - nx.shortest_path_length(g, s, d)
        assert extra in (0, 2)
        longer += extra == 2
        equal += extra == 0
    assert (longer, equal) == (18, 18)

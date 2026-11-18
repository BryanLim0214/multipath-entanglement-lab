"""The three Part B networks (chain, two-branch, 3x3 grid) as networkx graphs, plus a helper that
builds the matching QuNetSim hosts. Each topology function returns (graph, build_hosts).
"""
import networkx as nx


def _graph_from_edges(edges):
    """Undirected graph with edges added in sorted order, so every process builds the same adjacency order."""
    g = nx.Graph()
    g.add_edges_from(sorted(tuple(sorted(e)) for e in edges))
    return g


def build_hosts(graphs, delay=0.0, max_ack_wait=10.0):
    """Create the singleton Network and one Host per node of every graph (graphs must not share node names).

    Returns (network, {name: Host}). Call once per process: QuNetSim keeps one global network.
    """
    from qunetsim.components import Host, Network
    net = Network.get_instance()                    # site-packages/qunetsim/components/network.py:19-23
    net.delay = delay                               # network.py:138 (setter); 0 removes the 0.1 s sleep per packet
    names = sorted({n for g in graphs for n in g.nodes})
    hosts = {n: Host(n) for n in names}
    for g in graphs:
        for a, b in sorted(g.edges):
            hosts[a].add_connection(b)              # host.py:603-611 (classical + quantum link)
            hosts[b].add_connection(a)
    net.start(names)                                # network.py:616
    net.add_hosts([hosts[n] for n in names])        # network.py:197
    for h in hosts.values():
        h.max_ack_wait = max_ack_wait               # host.py:162; the default waits forever
        h.start()                                   # host.py:1544
    return net, hosts


def _with_builder(graph):
    """Pair a graph with a function that builds only its hosts."""
    def build(delay=0.0, max_ack_wait=10.0):
        return build_hosts([graph], delay, max_ack_wait)
    return graph, build


def chain():
    """Chain A-B-C (sanity check). Returns (graph, build_hosts)."""
    return _with_builder(_graph_from_edges([("A", "B"), ("B", "C")]))


def two_branch():
    """Two disjoint branches S-a1-a2-D and S-b1-b2-D (6 nodes). Returns (graph, build_hosts)."""
    edges = [("S", "a1"), ("a1", "a2"), ("a2", "D"), ("S", "b1"), ("b1", "b2"), ("b2", "D")]
    return _with_builder(_graph_from_edges(edges))


def grid(rows=3, cols=3):
    """rows x cols grid with node names n<row><col> (for example n00, n12). Returns (graph, build_hosts)."""
    edges = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                edges.append((f"n{r}{c}", f"n{r}{c + 1}"))
            if r + 1 < rows:
                edges.append((f"n{r}{c}", f"n{r + 1}{c}"))
    return _with_builder(_graph_from_edges(edges))

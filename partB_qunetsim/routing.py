"""Routes for Part B. SP is QuNetSim's own default route. MP is up to k edge-disjoint paths found with
networkx, with a 3-argument dispenser so QuNetSim can use it as its routing function.
"""
import networkx as nx

MAX_INTERMEDIATE = 4      # task spec: at most 4 intermediate nodes per path


def sp_route(source, dest):
    """Single-path route from QuNetSim's default router: Network.get_quantum_route, which calls nx.shortest_path
    (network.py:38 default algorithm; network.py:336-346 get_quantum_route)."""
    from qunetsim.components import Network
    return list(Network.get_instance().get_quantum_route(source, dest))


def k_disjoint_paths(graph, source, dest, k):
    """Up to k edge-disjoint paths, shortest first, each with at most MAX_INTERMEDIATE intermediate nodes.

    Uses nx.edge_disjoint_paths (networkx/algorithms/connectivity/disjoint_paths.py:26) on an undirected copy,
    because QuNetSim stores each link as two directed edges. Ties are broken by the node list.
    Falls back to the single shortest path when every disjoint path is too long.
    """
    undirected = nx.Graph(graph)
    found = list(nx.edge_disjoint_paths(undirected, source, dest, cutoff=k))
    short = [p for p in found if len(p) - 2 <= MAX_INTERMEDIATE]
    short.sort(key=lambda p: (len(p), p))
    if not short:
        short = [nx.shortest_path(undirected, source, dest)]
    return [list(p) for p in short[:k]]


def make_dispenser(paths):
    """A 3-argument routing function (graph, source, dest) that hands out the given paths in turn.

    Installable as network.quantum_routing_algo (network.py:109-128 requires exactly 3 parameters).
    The list of paths it handed out is kept in dispenser.handed.
    """
    handed = []

    def dispenser(graph, source, dest):
        path = list(paths[len(handed) % len(paths)])
        handed.append(path)
        return path

    dispenser.handed = handed
    return dispenser


def split_pairs(n, paths):
    """Split n pairs as evenly as possible over the paths: the first paths get the ceil, the later ones the floor.
    Returns [(path, count), ...] and drops paths that get 0 pairs."""
    base, extra = divmod(n, len(paths))
    loads = [(path, base + (1 if i < extra else 0)) for i, path in enumerate(paths)]
    return [(p, m) for p, m in loads if m > 0]


def crosscheck_native_swap(net, hosts, paths, rounds=5):
    """Loss-free cross-check: QuNetSim's OWN entanglement swap, with our dispenser as the routing function.

    For each round, one end-to-end send_epr per path, one after another (P8). Returns a list of
    (path handed out, Z or X, correlated). Needs use_ent_swap=True (network.py:53-58, :565-575).
    """
    source, dest = paths[0][0], paths[0][-1]
    dispenser = make_dispenser(paths)
    old_algo, old_swap = net.quantum_routing_algo, net.use_ent_swap
    net.quantum_routing_algo, net.use_ent_swap = dispenser, True
    rows = []
    try:
        for i in range(rounds * len(paths)):
            q_id, ack = hosts[source].send_epr(dest, await_ack=True)
            q1 = hosts[source].get_epr(dest, q_id, wait=10)
            q2 = hosts[dest].get_epr(source, q_id, wait=10)
            basis = "Z" if (i // len(paths)) % 2 == 0 else "X"   # every path sees both bases
            ok = bool(ack) and q1 is not None and q2 is not None
            if ok:
                if basis == "X":
                    q1.H()
                    q2.H()
                ok = q1.measure() == q2.measure()
            rows.append((dispenser.handed[-1], basis, ok))
    finally:   # the setter rejects QuNetSim's own default (network.py:117-124), so restore the private field
        net._quantum_routing_algo, net.use_ent_swap = old_algo, old_swap
    return rows

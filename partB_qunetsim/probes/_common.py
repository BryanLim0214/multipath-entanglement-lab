"""Shared helpers for the QuNetSim feasibility probes (not a probe itself).
Builds a small network from an edge list, and measures both halves of an EPR pair.
Only public QuNetSim API names are used; see docs/qunetsim_feasibility.md for citations.
"""
import sys
from qunetsim.components import Host, Network
from qunetsim.objects.connections.quantum_connection import QuantumConnection

CHAIN = [("A", "B"), ("B", "C")]
# two branches: S-a1-a2-D and S-b1-b2-D (6 nodes)
TWO_BRANCH = [("S", "a1"), ("a1", "a2"), ("a2", "D"), ("S", "b1"), ("b1", "b2"), ("b2", "D")]


def grid3x3():
    """3x3 grid, nodes n00..n22, edges between horizontal/vertical neighbours."""
    edges = []
    for r in range(3):
        for c in range(3):
            if c < 2:
                edges.append((f"n{r}{c}", f"n{r}{c+1}"))
            if r < 2:
                edges.append((f"n{r}{c}", f"n{r+1}{c}"))
    return edges


def build(edges, delay=0.0, ent_swap=True, host_cls=Host, q_models=None):
    """Create the singleton Network and one host per node; classical + quantum links per edge.
    q_models: optional {(a, b): channel_model} applied to the quantum link a->b and b->a."""
    # NOTE: never call Network.reset_network(): protocols.py:7 keeps the FIRST Network instance forever,
    # so a reset makes every later request hang. One network per Python process.
    net = Network.get_instance()                 # network.py:19-23 (get_instance)
    net.delay = delay                            # network.py:138-151 (delay setter)
    net.use_ent_swap = ent_swap                  # network.py:57-58 (use_ent_swap setter)
    names = sorted({n for e in edges for n in e})
    hosts = {n: host_cls(n) for n in names}
    for a, b in edges:
        hosts[a].add_connection(b)               # host.py:603-611 (no model= argument here)
        hosts[b].add_connection(a)
    for (a, b), model in (q_models or {}).items():
        # the only way to pass a model: build QuantumConnection(..., model=) ourselves
        hosts[a].quantum_connections[b] = QuantumConnection(a, b, model=model)
        hosts[b].quantum_connections[a] = QuantumConnection(b, a, model=model)
    net.start(names)                             # network.py:616 (start)
    net.add_hosts(list(hosts.values()))          # network.py:197 (add_hosts)
    for h in hosts.values():
        h.start()                                # host.py:1544
    return net, hosts


def request_epr(src, dst, hosts, wait=5):
    """Ask src for an EPR pair with dst (blocking on the ACK).
    Returns (q_id, ack_ok, qubit_at_src, qubit_at_dst); qubits are None if missing."""
    q_id, ack = hosts[src].send_epr(dst, await_ack=True)           # host.py:844
    q1 = hosts[src].get_epr(dst, q_id, wait=wait)                  # host.py:1470
    q2 = hosts[dst].get_epr(src, q_id, wait=wait)
    return q_id, ack, q1, q2


def measure_pair(q1, q2, basis="Z"):
    """Measure both halves (X basis = Hadamard first). Returns (m1, m2)."""
    if basis == "X":
        q1.H()
        q2.H()
    return q1.measure(), q2.measure()              # qubit.py:319


def say(tag, msg):
    print(f"[{tag}] {msg}")
    sys.stdout.flush()


class MeteredHost(Host):
    """Host subclass that records every send_epr call as (sender, receiver) in MeteredHost.calls.
    No library file is edited; we only override one public method and call the parent."""
    calls = []          # every send_epr call: (sender, receiver)
    teleports = []      # every send_teleport call: (sender, receiver)  (the swap's correction messages)

    def send_epr(self, receiver_id, *args, **kwargs):
        MeteredHost.calls.append((self.host_id, receiver_id))
        return super().send_epr(receiver_id, *args, **kwargs)

    def send_teleport(self, receiver_id, *args, **kwargs):
        MeteredHost.teleports.append((self.host_id, receiver_id))
        return super().send_teleport(receiver_id, *args, **kwargs)


def link_counts(edges):
    """Split MeteredHost.calls into per-link counts (calls between neighbours) and
    'end-to-end' calls (between non-neighbours). Links are undirected, printed sorted."""
    adj = {frozenset(e) for e in edges}
    per_link, e2e = {}, []
    for s, r in MeteredHost.calls:
        if frozenset((s, r)) in adj:
            key = "-".join(sorted((s, r)))
            per_link[key] = per_link.get(key, 0) + 1
        else:
            e2e.append((s, r))
    return per_link, e2e


def run_each(script_path, arg_list, timeout=120):
    """Run `python script arg` once per arg in a fresh process (one QuNetSim network per process),
    with a hard timeout; kills the whole process tree on a hang. Returns list of return codes.
    The library prints Python tracebacks from its daemon threads when packets are dropped; we hide
    them from the console but report how many there were (stderr goes to a temp file)."""
    import subprocess, tempfile
    codes = []
    for arg in arg_list:
        with tempfile.TemporaryFile("w+") as err:
            p = subprocess.Popen([sys.executable, script_path, arg], stderr=err)
            try:
                p.wait(timeout=timeout)
                codes.append(p.returncode)
            except subprocess.TimeoutExpired:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
                say("FAIL", f"scenario '{arg}' hung (> {timeout}s) and was killed")
                codes.append(-1)
            err.seek(0)
            text = err.read()
            n_tb = text.count("Traceback (most recent call last)")
            if n_tb:
                kinds = sorted({l.strip() for l in text.splitlines() if l.startswith(("AssertionError", "AttributeError", "ValueError", "TypeError", "KeyError"))})
                say("OBSERVED", f"[{arg}] library daemon threads raised {n_tb} tracebacks (hidden); kinds: {kinds}")
    return codes

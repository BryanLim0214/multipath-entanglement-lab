"""Exact ILP placers for one window: the paper's arc formulation and a faster path formulation.

Both maximise sum(rho_r * X_r) (A13) and return core.PlaceResult. SP-ILP is K=1, and ILP-delta
(A21) adds a per-request, per-link cap. Solvers: HiGHS (default) or CBC, one thread, zero MIP gap.
"""
from __future__ import annotations

import time

import networkx as nx
import pulp

from qmp.core import Allocation, PlaceResult, WindowInput, edge, path_edges

_canary_drop_capacity = False   # test-only switch: removes constraint (4c) so the tests can prove they catch it

TIE_TOTAL = 1e-6    # total weight of the tie-break term, far below the smallest rho gap 1/2520
ABS_GAP = 1e-7      # below TIE_TOTAL and far below any real objective difference


def _make_solver(name: str, time_limit: float):
    """Build a one-thread solver with zero relative gap (distinct objectives can differ by 1/2520)."""
    if name == "highs":
        return pulp.HiGHS(msg=False, timeLimit=time_limit, gapRel=0, gapAbs=ABS_GAP, threads=1)
    if name == "cbc":
        return pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit, gapRel=0, gapAbs=ABS_GAP, threads=1)
    raise ValueError(f"unknown solver {name!r}; use 'highs' or 'cbc'")


def _tie_weights(win: WindowInput) -> dict[int, float]:
    """Tiny weights that prefer lower request ids; they add up to TIE_TOTAL."""
    ids = sorted(r.id for r in win.requests)
    total = len(ids) * (len(ids) + 1) / 2
    return {rid: TIE_TOTAL * (len(ids) - i) / total for i, rid in enumerate(ids)}


def _delta_of(delta, request_id: int):
    """delta may be None, one int for everyone, or a dict request id -> delta_r (A21)."""
    if delta is None:
        return None
    return delta[request_id] if isinstance(delta, dict) else delta


def _cap(win: WindowInput, u: int, v: int) -> int:
    return win.capacity.get(edge(u, v), 0)


def _k_for(win: WindowInput, r, K) -> int:
    """K per request defaults to min(deg s, deg d) (A2); a given K is capped by it, which loses nothing."""
    default = min(win.graph.degree(r.s), win.graph.degree(r.d))
    return default if K is None else min(K, default)


def _run(prob: pulp.LpProblem, solver: str, time_limit: float) -> str:
    """Solve and map PuLP's answer to our status. Only a proven optimum counts as 'optimal'."""
    prob.solve(_make_solver(solver, time_limit))
    if prob.sol_status == pulp.LpSolutionOptimal:
        return "optimal"
    if prob.sol_status == pulp.LpSolutionIntegerFeasible or prob.status == pulp.LpStatusNotSolved:
        return "time_limit"
    return "error"


def _usable(status: str, prob: pulp.LpProblem) -> bool:
    """Variable values can be read for an optimum or for a time-limit incumbent."""
    return status == "optimal" or (status == "time_limit" and prob.sol_status == pulp.LpSolutionIntegerFeasible)


def _on(var) -> bool:
    return var.value() is not None and var.value() > 0.5


def _int(var) -> int:
    return int(round(var.value() or 0))


# ---------------------------------------------------------------- arc formulation (paper, (2a)-(4c))

def solve_arc(win: WindowInput, *, K=None, directed_disjoint=False, delta=None,
              time_limit=60, solver="highs") -> PlaceResult:
    """The paper's formulation. Arcs of zero-capacity links are left out, which only drops 0-pair paths."""
    start = time.perf_counter()
    prob = pulp.LpProblem("arc", pulp.LpMaximize)
    tie = _tie_weights(win)
    edges = sorted(edge(u, v) for u, v in win.graph.edges if _cap(win, u, v) > 0)
    arcs_all = [a for e in edges for a in (e, (e[1], e[0]))]

    X, Xk, pi, x, beta, y = {}, {}, {}, {}, {}, {}
    ks = {}
    for r in win.requests:
        n, i_max = r.n, win.max_mid[r.id]
        ks[r.id] = range(_k_for(win, r, K))
        X[r.id] = pulp.LpVariable(f"X_{r.id}", cat="Binary")
        arcs = [(i, j) for i, j in arcs_all if j != r.s and i != r.d]   # a simple path never enters s or leaves d
        nodes = sorted({v for a in arcs for v in a} - {r.s, r.d})
        for k in ks[r.id]:
            Xk[r.id, k] = pulp.LpVariable(f"Xk_{r.id}_{k}", cat="Binary")
            pi[r.id, k] = pulp.LpVariable(f"pi_{r.id}_{k}", 0, n, cat="Integer")
            for i, j in arcs:
                x[r.id, k, i, j] = pulp.LpVariable(f"x_{r.id}_{k}_{i}_{j}", cat="Binary")
                beta[r.id, k, i, j] = pulp.LpVariable(f"b_{r.id}_{k}_{i}_{j}", 0, n, cat="Integer")
            for i in nodes:
                y[r.id, k, i] = pulp.LpVariable(f"y_{r.id}_{k}_{i}", cat="Binary")
            _add_request_constraints(prob, r, k, arcs, nodes, i_max, X, Xk, pi, x, beta, y)
        _add_request_totals(prob, r, ks[r.id], X, Xk, pi)

    _add_disjointness(prob, win, ks, edges, x, directed_disjoint)
    _add_capacity_and_delta(prob, win, ks, edges, beta, delta)
    prob += (pulp.lpSum(r_rho * X[rid] for rid, r_rho in win.rho.items() if rid in X)
             + pulp.lpSum(tie[rid] * X[rid] for rid in X))

    status = _run(prob, solver, time_limit)
    allocs = _extract_arc(win, ks, X, pi, x) if _usable(status, prob) else []
    return PlaceResult(allocs, status, time.perf_counter() - start)


def _add_request_constraints(prob, r, k, arcs, nodes, i_max, X, Xk, pi, x, beta, y) -> None:
    """Constraints (2a), (2e), (2f), (3a), (4a), (4b) for path k of request r."""
    n = r.n
    out = lambda i: pulp.lpSum(x[r.id, k, a, b] for a, b in arcs if a == i)
    inn = lambda i: pulp.lpSum(x[r.id, k, a, b] for a, b in arcs if b == i)
    prob += out(r.s) == Xk[r.id, k]                       # (2a) one unit leaves s if the path is used
    prob += inn(r.d) == Xk[r.id, k]                       # (2a) and arrives at d
    for i in nodes:
        prob += out(i) - inn(i) == 0                      # (2a) conservation elsewhere
        prob += out(i) == y[r.id, k, i]                   # (2e)
    prob += pulp.lpSum(y[r.id, k, i] for i in nodes) <= i_max   # (2f)
    prob += pi[r.id, k] <= n * Xk[r.id, k]                # (3a)
    for i, j in arcs:
        prob += beta[r.id, k, i, j] <= n * x[r.id, k, i, j]                          # (4a), A18: big-M = n
        prob += beta[r.id, k, i, j] >= pi[r.id, k] - n * (1 - x[r.id, k, i, j])      # (4b)


def _add_request_totals(prob, r, krange, X, Xk, pi) -> None:
    """Constraints (2b), (2c), (3b) and the symmetry breaking X^rk >= X^r,k+1 for request r."""
    K = len(krange)
    prob += K * X[r.id] >= pulp.lpSum(Xk[r.id, k] for k in krange)   # (2b), A18: big-M = K
    prob += X[r.id] <= pulp.lpSum(Xk[r.id, k] for k in krange)       # (2c)
    prob += pulp.lpSum(pi[r.id, k] for k in krange) == r.n * X[r.id]   # (3b)
    for k in range(K - 1):
        prob += Xk[r.id, k] >= Xk[r.id, k + 1]


def _add_disjointness(prob, win, ks, edges, x, directed: bool) -> None:
    """(2d): per directed arc as written, or per undirected link (A7)."""
    for r in win.requests:
        for u, v in edges:
            fwd = [x[r.id, k, u, v] for k in ks[r.id] if (r.id, k, u, v) in x]
            back = [x[r.id, k, v, u] for k in ks[r.id] if (r.id, k, v, u) in x]
            if directed:
                prob += pulp.lpSum(fwd) <= 1
                prob += pulp.lpSum(back) <= 1
            else:
                prob += pulp.lpSum(fwd + back) <= 1   # A7


def _add_capacity_and_delta(prob, win, ks, edges, beta, delta) -> None:
    """(4c) link capacity shared by all requests and both directions, plus the optional A21 cap."""
    for u, v in edges:
        cap = _cap(win, u, v)
        terms = []
        for r in win.requests:
            for k in ks[r.id]:
                pair = [beta[r.id, k, a, b] for a, b in ((u, v), (v, u)) if (r.id, k, a, b) in beta]
                terms += pair
                d = _delta_of(delta, r.id)
                if d is not None and pair:
                    prob += pulp.lpSum(pair) <= cap // d   # A21
        if not _canary_drop_capacity:
            prob += pulp.lpSum(terms) <= cap   # (4c)


def _extract_arc(win, ks, X, pi, x) -> list[Allocation]:
    """Walk the chosen arcs from s to d for every used path that carries at least 1 pair."""
    allocs = []
    for r in sorted(win.requests, key=lambda q: q.id):
        if not _on(X[r.id]):
            continue
        paths = []
        for k in ks[r.id]:
            pairs = _int(pi[r.id, k])
            if pairs >= 1:
                paths.append((_walk(x, r, k), pairs))
        allocs.append(Allocation(r.id, paths))
    return allocs


def _walk(x, r, k) -> list[int]:
    """Follow the unique chosen out-arc of each node from s until d is reached."""
    nxt = {i: j for (rid, kk, i, j), var in x.items() if rid == r.id and kk == k and _on(var)}
    path = [r.s]
    while path[-1] != r.d:
        path.append(nxt[path[-1]])
        if len(path) > len(nxt) + 2:
            raise RuntimeError("arc solution has a loop on the s-d walk")
    return path


# ---------------------------------------------------------------- path formulation (fast)

def _candidate_paths(win: WindowInput, r) -> list[list[int]]:
    """Simple s-d paths with at most I^r intermediate nodes that use no zero-capacity link."""
    found = nx.all_simple_paths(win.graph, r.s, r.d, cutoff=win.max_mid[r.id] + 1)
    return [p for p in found if all(_cap(win, *e) > 0 for e in path_edges(p))]


def solve_path(win: WindowInput, *, K=None, delta=None, time_limit=60, solver="highs") -> PlaceResult:
    """Same problem as solve_arc(directed_disjoint=False), with one binary per candidate path."""
    start = time.perf_counter()
    prob = pulp.LpProblem("path", pulp.LpMaximize)
    tie = _tie_weights(win)
    X = {r.id: pulp.LpVariable(f"X_{r.id}", cat="Binary") for r in win.requests}
    paths, z, pi = {}, {}, {}
    for r in win.requests:
        paths[r.id] = _candidate_paths(win, r)
        for p in range(len(paths[r.id])):
            z[r.id, p] = pulp.LpVariable(f"z_{r.id}_{p}", cat="Binary")
            pi[r.id, p] = pulp.LpVariable(f"pi_{r.id}_{p}", 0, r.n, cat="Integer")
            prob += pi[r.id, p] <= r.n * z[r.id, p]
        ids = range(len(paths[r.id]))
        prob += pulp.lpSum(pi[r.id, p] for p in ids) == r.n * X[r.id]
        prob += pulp.lpSum(z[r.id, p] for p in ids) <= _k_for(win, r, K)   # A2

    _add_path_edge_constraints(prob, win, paths, z, pi, delta)
    prob += (pulp.lpSum(win.rho[rid] * X[rid] for rid in X)
             + pulp.lpSum(tie[rid] * X[rid] for rid in X))

    status = _run(prob, solver, time_limit)
    allocs = _extract_path(win, paths, X, pi) if _usable(status, prob) else []
    return PlaceResult(allocs, status, time.perf_counter() - start)


def _add_path_edge_constraints(prob, win, paths, z, pi, delta) -> None:
    """Per request and link: one path at most (A7). Per link: capacity (4c). Optional A21 cap."""
    users: dict = {}
    for r in win.requests:
        for p, nodes in enumerate(paths[r.id]):
            for e in path_edges(nodes):
                users.setdefault(e, {}).setdefault(r.id, []).append(p)
    for e in sorted(users):
        total = []
        for rid, plist in users[e].items():
            prob += pulp.lpSum(z[rid, p] for p in plist) <= 1   # A7
            total += [pi[rid, p] for p in plist]
            d = _delta_of(delta, rid)
            if d is not None:
                prob += pulp.lpSum(pi[rid, p] for p in plist) <= win.capacity.get(e, 0) // d   # A21
        if not _canary_drop_capacity:
            prob += pulp.lpSum(total) <= win.capacity.get(e, 0)   # (4c)


def _extract_path(win, paths, X, pi) -> list[Allocation]:
    """Keep the paths that carry at least 1 pair, for each served request."""
    allocs = []
    for r in sorted(win.requests, key=lambda q: q.id):
        if not _on(X[r.id]):
            continue
        chosen = [(paths[r.id][p], _int(pi[r.id, p])) for p in range(len(paths[r.id]))]
        allocs.append(Allocation(r.id, [(nodes, c) for nodes, c in chosen if c >= 1]))
    return allocs

"""Exports the data QuantumLab shows: the Fig. 1 walk, the Rush hour instances and the fidelity limits.

It runs the real engine in src/qmp, so the browser can never disagree with the experiments.
Usage: .venv\\Scripts\\python.exe quantumlab\\tools\\export_data.py
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from qmp import fidelity, heuristic, ilp  # noqa: E402
from qmp.core import Request, WindowInput, edge, path_edges, validate  # noqa: E402
from qmp.model import fig1_graph, grid  # noqa: E402

DATA = ROOT / "quantumlab" / "data"
FIG1_REQUEST = {"s": 7, "d": 6, "n": 4, "delta": 2, "max_mid": 4, "f": 0.78}
FIDELITY_F = 0.95  # A5: fidelity of one fresh link
SLIDER_F = [round(0.50 + 0.01 * i, 2) for i in range(41)]  # the slider in chapter 4

# Rush hour: 2x3 grid, seats per link and (s, d, n) per request. Found by a seeded search
# (seed 7, seats 2..5) for instances where one road per request serves 2 of 3 requests
# and splitting serves all 3.
RUSH_INSTANCES = [
    {"seats": {(1, 2): 3, (1, 4): 5, (2, 3): 2, (2, 5): 3, (3, 6): 5, (4, 5): 5, (5, 6): 2},
     "requests": [(5, 1, 2), (6, 3, 3), (3, 1, 4)]},
    {"seats": {(1, 2): 4, (1, 4): 5, (2, 3): 4, (2, 5): 2, (3, 6): 4, (4, 5): 3, (5, 6): 5},
     "requests": [(5, 2, 4), (5, 6, 2), (3, 4, 2)]},
    {"seats": {(1, 2): 3, (1, 4): 5, (2, 3): 3, (2, 5): 2, (3, 6): 5, (4, 5): 2, (5, 6): 5},
     "requests": [(1, 4, 3), (1, 6, 4), (3, 5, 4)]},
]
SOURCE_FUNCTIONS = [heuristic.alpha_scores, heuristic.best_continuation, heuristic.greedy_walk,
                    heuristic.find_paths, heuristic.choose_split, heuristic.place_heuristic,
                    heuristic.use_seats, ilp.solve_path, fidelity.path_fidelity, fidelity.max_intermediate]


def source_sha256() -> str:
    """sha256 of the source text of every engine function this export depends on."""
    text = "\n".join(inspect.getsource(f) for f in SOURCE_FUNCTIONS)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def engine_commit() -> str:
    """Last git commit that touched src/, so unrelated commits do not change the data."""
    out = subprocess.run(["git", "log", "-1", "--format=%H", "--", "src"], cwd=ROOT,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def meta() -> dict:
    """Where the numbers came from: the engine commit and a hash of the functions used."""
    return {"engine_commit": engine_commit(), "engine_source_sha256": source_sha256()}


def candidate(caps, k: int, i: int, d: int, banned: set[int]) -> dict:
    """alpha_i as a numerator and denominator, the way the paper prints it (A9)."""
    hops, beta = heuristic.best_continuation(caps, i, d, banned)
    return {"node": i, "num": min(caps[k][i], beta), "den": hops,
            "link_seats": caps[k][i], "route_bottleneck": beta}


def trace_walk(caps, s: int, d: int, path_no: int, rng):
    """Same loop as heuristic.greedy_walk, but it records every choice (lowest-id tie-break)."""
    path, steps = [s], []
    while True:
        k = path[-1]
        if d in caps.get(k, {}):
            return path + [d], steps
        scores = heuristic.alpha_scores(caps, path, d)
        if not scores:
            steps.append({"kind": "dead_end", "path_no": path_no, "at": k, "so_far": list(path)})
            return None, steps
        cands = [candidate(caps, k, i, d, set(path)) for i in sorted(scores)]
        for c in cands:
            assert Fraction(c["num"], c["den"]) == scores[c["node"]]
        chosen = heuristic.pick_best(scores, rng, "first")
        top = max(scores.values())
        steps.append({"kind": "choose", "path_no": path_no, "at": k, "so_far": list(path),
                      "candidates": cands, "tied": sorted(i for i, a in scores.items() if a == top),
                      "chosen": chosen})
        path.append(chosen)


def trace_find_paths(caps, s: int, d: int):
    """Same loop as heuristic.find_paths with a step list. Returns (paths with bottlenecks, steps)."""
    private = copy.deepcopy(caps)
    rng = np.random.default_rng(0)
    found, steps = [], []
    while private.get(s):
        path, walk = trace_walk(private, s, d, len(found) + 1, rng)
        steps += walk
        if path is None:
            break
        bc = heuristic.bottleneck(private, path)
        found.append((path, bc))
        steps.append({"kind": "found", "path_no": len(found), "path": path, "bottleneck": bc,
                      "removed_links": [list(e) for e in path_edges(path)]})
        for u, v in path_edges(path):
            heuristic.remove_link(private, u, v)
    return found, steps


def fig1_steps() -> dict:
    """The greedy walk for request 7 to 6, step by step, plus the allocation and residual seats."""
    graph, capacity = fig1_graph()
    req = FIG1_REQUEST
    request = Request(id=0, s=req["s"], d=req["d"], n=req["n"], a=1, h=1, b=10, f=req["f"])
    win = WindowInput(graph, capacity, [request], {0: 1.0}, {0: req["max_mid"]}, 0)
    caps = heuristic.build_caps(win)
    found, steps = trace_find_paths(caps, request.s, request.d)
    found.sort(key=lambda pb: -pb[1])
    split = heuristic.choose_split(found, request.n, req["delta"], True)
    steps.append({"kind": "allocation", "delta": req["delta"], "sorted_paths":
                  [{"path": p, "bottleneck": bc, "seats_offered": bc // req["delta"]} for p, bc in found],
                  "split": [{"path": p, "pairs": n} for p, n in split]})
    before = copy.deepcopy(caps)
    for path, pairs in split:
        heuristic.use_seats(caps, path, pairs)
    touched = sorted({e for path, _ in split for e in path_edges(path)})
    residual = [{"a": a, "b": b, "before": before[a][b], "after": caps.get(a, {}).get(b, 0)}
                for a, b in touched]
    steps.append({"kind": "residual", "links": residual})
    check_against_engine(win, split)
    return {"meta": meta(), "request": req, "tie_break": "lowest id",
            "random_tie_note": "With random ties the walk may pick 9 instead of 5 at city 8; "
                               "the second path and the 2 + 2 split do not change.",
            "links": [{"a": a, "b": b, "seats": c} for (a, b), c in sorted(capacity.items())],
            "steps": steps}


def check_against_engine(win: WindowInput, split) -> None:
    """The traced answer must equal what the real heuristic returns with the same tie-break."""
    result = heuristic.place_heuristic(win, tie_break="first")
    assert validate(win, result.allocations) == []
    assert result.allocations[0].paths == [(p, n) for p, n in split]


def allocs_json(allocations) -> list[dict]:
    """Allocations as plain lists, with one entry per served request."""
    return [{"request": a.request_id, "roads": [{"nodes": p, "pairs": n} for p, n in a.paths]}
            for a in allocations]


def rush_window(inst: dict) -> WindowInput:
    """One Rush hour instance as the engine's WindowInput (all requests have priority 1)."""
    capacity = {edge(*e): c for e, c in inst["seats"].items()}
    requests = [Request(i + 1, s, d, n, 1, 1, 9, 0.78) for i, (s, d, n) in enumerate(inst["requests"])]
    return WindowInput(grid(2, 3), capacity, requests, {r.id: 1.0 for r in requests},
                       {r.id: 4 for r in requests}, 0)


def rush_solutions(win: WindowInput) -> dict:
    """ILP optimum (solve_path) and heuristic answer for the four mode and rule combinations."""
    out = {}
    for mode, k, multipath in (("single", 1, False), ("split", None, True)):
        for rule, delta in (("off", None), ("spare", 2)):
            best = ilp.solve_path(win, K=k, delta=delta)
            assert best.status == "optimal" and validate(win, best.allocations) == []
            heu = heuristic.place_heuristic(win, multipath=multipath, delta=delta or 1, tie_break="first")
            out[f"{mode}_{rule}"] = {"served": len(best.allocations), "ilp": allocs_json(best.allocations),
                                     "heuristic_served": len(heu.allocations),
                                     "heuristic": allocs_json(heu.allocations)}
    return out


def rushhour() -> dict:
    """All Rush hour instances with their solutions."""
    instances = []
    for number, inst in enumerate(RUSH_INSTANCES, 1):
        win = rush_window(inst)
        instances.append({
            "id": number, "rows": 2, "cols": 3,
            "links": [{"a": a, "b": b, "seats": c} for (a, b), c in sorted(win.capacity.items())],
            "requests": [{"id": r.id, "s": r.s, "d": r.d, "n": r.n} for r in win.requests],
            "solutions": rush_solutions(win)})
    first = instances[0]["solutions"]
    assert [first[k]["served"] for k in ("single_off", "split_off", "split_spare", "single_spare")] == [2, 3, 2, 1]
    return {"meta": meta(), "spare_seat_delta": 2, "instances": instances}


def fidelity_data() -> dict:
    """Intermediate-city limits for the chapter 4 slider, and the F_L table for L = 1..15."""
    limits = {f"{f:.2f}": fidelity.max_intermediate(FIDELITY_F, f) for f in SLIDER_F}
    table = [{"links": L, "fidelity": round(fidelity.path_fidelity(FIDELITY_F, L), 6)} for L in range(1, 16)]
    return {"meta": meta(), "link_fidelity": FIDELITY_F, "limits": limits, "table": table}


def build_all() -> dict:
    """Every exported file by name. The test re-runs this and compares with the committed files."""
    return {"fig1_steps.json": fig1_steps(), "rushhour.json": rushhour(), "fidelity.json": fidelity_data()}


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    for file_name, content in build_all().items():
        (DATA / file_name).write_text(json.dumps(content, indent=2) + "\n", encoding="utf-8")
        print("wrote", DATA / file_name)

"""Exports the data QuantumLab shows: the Fig. 1 walk, Rush hour, the fidelity limits and the Arena replays.

It runs the real engine in src/qmp (single process, heuristics only), so the browser can never disagree
with the experiments. Usage: .venv\\Scripts\\python.exe quantumlab\\tools\\export_data.py
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
import sys
from fractions import Fraction
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from experiments.common import calibrated_n_spec  # noqa: E402
from experiments.methods import METHODS  # noqa: E402
from qmp import fidelity, heuristic, ilp, model, sim, stats  # noqa: E402
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


# ---- Arena: replay data -------------------------------------------------------------------------
RESULTS = ROOT / "results"
ARENA_Q = [0.5, 0.7, 0.9]
ARENA_SEEDS = [0, 1, 2]
TRACE_METHODS = ["SP-SPF", "SP-Heu", "MP-Heu", "SP-ILP", "MP-ILP"]
SMALL = {"rows": 3, "cols": 3, "R": 60, "M": 6, "T": 100, "tc": 10, "F": FIDELITY_F, "f": 0.78}
# A5: with F = 0.95 a requirement of f = 0.6 allows 10 middle cities, and a 3x3 grid has at most 7
# (a path through all 9 cities), so the fidelity limit can never bind. This is "hop limit off".
F_HOP_OFF = 0.6
ARENA_SOURCE_FUNCTIONS = [sim.simulate, sim.to_trace, sim.check_legal, model.make_requests, model.sample_capacity,
                          model.windows, heuristic.place_heuristic, heuristic.choose_split, stats.mean_ci,
                          stats.paired_diff_ci]


def file_sha256(path: Path) -> str:
    """sha256 of one input file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def traces_sha256() -> str:
    """One hash over every Part A trace the Arena reads (names and bytes, in sorted order)."""
    digest = hashlib.sha256()
    for path in sorted((RESULTS / "traces").glob("partA_*.json")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def arena_meta() -> dict:
    """Engine stamp plus the hashes of the result files and functions the Arena data comes from."""
    source = "\n".join(inspect.getsource(f) for f in ARENA_SOURCE_FUNCTIONS)
    return {**meta(), "arena_source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "inputs": {"traces_sha256": traces_sha256(),
                       "partA_small_csv_sha256": file_sha256(RESULTS / "partA_small.csv"),
                       "paper_values_sha256": file_sha256(ROOT / "data" / "paper_values.yaml"),
                       "calibration_choice_sha256": file_sha256(RESULTS / "calibration_choice.yaml")}}


def variant_name(multipath: bool, spare: bool, hop: bool) -> str:
    """MP-Heu or SP-Heu, then -d1 when the spare-seat rule is off, then -nohop when the hop limit is off."""
    return ("MP" if multipath else "SP") + "-Heu" + ("" if spare else "-d1") + ("" if hop else "-nohop")


def heuristic_variants() -> dict[str, dict]:
    """All eight on/off combinations of splitting, the spare-seat rule and the hop limit (heuristic only)."""
    out = {}
    for multipath in (True, False):
        for spare in (True, False):
            for hop in (True, False):
                base = variant_name(multipath, spare, True)
                placer = METHODS.get(base) or partial(heuristic.place_heuristic, multipath=multipath,
                                                      delta=2 if spare else 1)  # A21: delta 2 is the spare-seat rule
                out[variant_name(multipath, spare, hop)] = {"placer": placer, "f": SMALL["f"] if hop else F_HOP_OFF}
    return out


def arena_config(q: float, seed: int, f: float) -> sim.SimConfig:
    """The Part A small-setup config, with the n_spec the experiments used."""
    return sim.SimConfig(SMALL["rows"], SMALL["cols"], SMALL["R"], SMALL["M"], SMALL["T"], SMALL["tc"], q,
                         SMALL["F"], f, calibrated_n_spec(), seed)


def committed_trace(method: str, q: float, seed: int) -> dict:
    """A Part A trace file exactly as the experiments wrote it."""
    path = RESULTS / "traces" / f"partA_{method}_q{q}_s{seed}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def simulated_trace(name: str, q: float, seed: int) -> dict:
    """Run one heuristic variant for one seed and return its trace (single process)."""
    variant = heuristic_variants()[name]
    cfg = arena_config(q, seed, variant["f"])
    return sim.to_trace(sim.simulate(cfg, variant["placer"]), cfg)


def compact_trace(trace: dict) -> dict:
    """Keep what the replay needs per window (eligible and allocations) plus the totals. Numbers are untouched."""
    return {"windows": [{"eligible": w["eligible"], "allocations": w["allocations"]} for w in trace["windows"]],
            "never_placed": trace["never_placed"], "blocking_ratio": trace["blocking_ratio"]}


def request_rows(trace: dict) -> list[list[int]]:
    """Requests as [id, s, d, n, a, h, b] rows (the fidelity requirement f is stored once in config)."""
    return [[r["id"], r["s"], r["d"], r["n"], r["a"], r["h"], r["b"]] for r in trace["requests"]]


def shared_inputs(traces: dict[str, dict]) -> tuple[list, list]:
    """Requests and per-window seats, which must be identical in every trace of one (q, seed) (A19)."""
    first = next(iter(traces.values()))
    capacity = [w["capacity"] for w in first["windows"]]
    requests = request_rows(first)
    for name, trace in traces.items():
        assert [w["capacity"] for w in trace["windows"]] == capacity, name
        assert request_rows(trace) == requests, name
    return requests, capacity


def arena_runs() -> dict:
    """Every (q, seed) run: five committed traces plus the heuristic variants, keyed "q/seed"."""
    runs = {}
    for q in ARENA_Q:
        for seed in ARENA_SEEDS:
            traces = {m: committed_trace(m, q, seed) for m in TRACE_METHODS}
            for name in heuristic_variants():
                if name not in traces:
                    traces[name] = simulated_trace(name, q, seed)
            requests, capacity = shared_inputs(traces)
            runs[f"{q}/{seed}"] = {"requests": requests, "capacity": capacity,
                                   "traces": {name: compact_trace(t) for name, t in sorted(traces.items())}}
    return runs


def arena_summary() -> dict:
    """30-seed mean and 95% CI of the blocking ratio per method and q, and paired differences (A19)."""
    table = pd.read_csv(RESULTS / "partA_small.csv").sort_values(["method", "q", "seed"])
    blocking, paired = {}, {}
    for q in sorted(table["q"].unique()):
        rows = {m: table[(table["method"] == m) & (table["q"] == q)]["blocking_ratio"].to_numpy()
                for m in TRACE_METHODS}
        blocking[str(q)] = {m: {**dict(zip(("mean", "ci"), stats.mean_ci(v))), "n": len(v)} for m, v in rows.items()}
        paired[str(q)] = {pair: dict(zip(("mean", "ci"), stats.paired_diff_ci(rows[f"SP-{pair}"], rows[f"MP-{pair}"])))
                          for pair in ("Heu", "ILP")}
    return {"blocking_ratio": blocking, "single_minus_multi": paired}


def paper_blocking() -> dict:
    """Blocking ratios the paper prints in the text for the small setup at q = 0.9 (A20)."""
    values = yaml.safe_load((ROOT / "data" / "paper_values.yaml").read_text(encoding="utf-8"))
    return values["small"]["blocking_ratio_at_q09"]


def arena_data() -> dict:
    """The whole arena.json content."""
    assert fidelity.max_intermediate(SMALL["F"], F_HOP_OFF) >= SMALL["rows"] * SMALL["cols"] - 2
    return {"meta": arena_meta(),
            "config": {**SMALL, "n_spec": calibrated_n_spec(), "f_hop_off": F_HOP_OFF, "spare_seat_delta": 2,
                       "max_middle_on": fidelity.max_intermediate(SMALL["F"], SMALL["f"]),
                       "max_middle_off": fidelity.max_intermediate(SMALL["F"], F_HOP_OFF)},
            "q_values": ARENA_Q, "seeds": ARENA_SEEDS, "trace_methods": TRACE_METHODS,
            "runs": arena_runs(), "summary": arena_summary(), "paper": paper_blocking()}


def build_all() -> dict:
    """Every exported file by name. The test re-runs this and compares with the committed files."""
    return {"fig1_steps.json": fig1_steps(), "rushhour.json": rushhour(), "fidelity.json": fidelity_data(),
            "arena.json": arena_data()}


if __name__ == "__main__":
    DATA.mkdir(exist_ok=True)
    for file_name, content in build_all().items():
        compact = file_name == "arena.json"  # the replay data is large, so it is written without indentation
        text = json.dumps(content, separators=(",", ":")) if compact else json.dumps(content, indent=2)
        (DATA / file_name).write_text(text + "\n", encoding="utf-8")
        print("wrote", DATA / file_name)

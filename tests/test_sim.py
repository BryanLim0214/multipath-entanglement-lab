"""Simulation-loop checks: bounds, determinism, fair dice (A19) and JSON replay."""
import json
from functools import partial

from qmp.heuristic import place_heuristic, place_spf
from qmp.sim import SimConfig, simulate, to_trace

CFG = SimConfig(rows=3, cols=3, R=20, M=6, T=50, tc=10, q=0.7, F=0.95, f=0.78,
                n_spec="uniform:1:3", seed=5)
METHODS = [place_spf, partial(place_heuristic, multipath=False), place_heuristic]


def strip_seconds(result):
    return [(r.w, r.capacity, r.eligible, [(a.request_id, a.paths) for a in r.allocations])
            for r in result.records]


def test_blocking_ratio_in_range():
    for method in METHODS:
        res = simulate(CFG, method)
        assert 0.0 <= res.blocking_ratio <= 1.0
        assert 0.0 <= res.gamma <= 1.0


def test_same_seed_same_result():
    a = simulate(CFG, place_heuristic)
    b = simulate(CFG, place_heuristic)
    assert strip_seconds(a) == strip_seconds(b)
    assert a.blocking_ratio == b.blocking_ratio


def test_methods_see_the_same_first_window():
    first = [simulate(CFG, m).records[0] for m in METHODS]
    assert all(r.capacity == first[0].capacity and r.eligible == first[0].eligible for r in first)


def test_no_request_placed_twice():
    res = simulate(CFG, place_heuristic)
    ids = [a.request_id for rec in res.records for a in rec.allocations]
    assert len(ids) == len(set(ids)) == len(res.placed)


def test_trace_is_json_serialisable():
    res = simulate(CFG, place_heuristic)
    text = json.dumps(to_trace(res, CFG))
    assert json.loads(text)["config"]["seed"] == 5

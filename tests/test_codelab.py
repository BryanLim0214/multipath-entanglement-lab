"""Checks the Code Lab's adapter in CPython: the same file the browser worker loads.

Single process, heuristics only, no solver and no experiments.
"""
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from qmp.core import Allocation, Request, WindowInput, validate
from qmp.model import grid

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "quantumlab"
PY = LAB / "py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adapter = load_module("codelab_adapter", PY / "codelab_adapter.py")
CODELAB = json.loads((LAB / "data" / "codelab.json").read_text(encoding="utf-8"))
N_SPEC = CODELAB["config"]["n_spec"]


def text(relative: str) -> str:
    return (PY / relative).read_text(encoding="utf-8")


def committed_trace(method: str, q: float, seed: int) -> dict:
    path = ROOT / "results" / "traces" / f"partA_{method}_q{q}_s{seed}.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("q", [0.5, 0.7, 0.9])
def test_lazy_walker_reproduces_sp_spf_exactly_on_seeds_0_to_2(q):
    for seed in range(3):
        ratio, log = adapter.player_blocking(text("templates/lazy_walker.py"), q, seed, N_SPEC)
        assert ratio == committed_trace("SP-SPF", q, seed)["blocking_ratio"], (q, seed)
        assert log.illegal == 0


def test_lazy_walker_ties_the_lazy_baseline_on_ten_paired_seeds():
    result = adapter.run_challenge(text("templates/lazy_walker.py"), "lazy", 0.5, list(range(10)), N_SPEC)
    assert result["player"] == result["baseline_values"]
    assert result["mean_diff"] == 0 and result["won"] is False


ILLEGAL = {
    "shared link": "def choose_paths(net, request):\n    r = [request.src, request.dst]\n    return [(r, 1), (r, request.n - 1)] if request.n > 1 else []\n",
    "wrong end": "def choose_paths(net, request):\n    return [([request.src, request.src], request.n)]\n",
    "too few pairs": "def choose_paths(net, request):\n    road = [request.src] + [c for c in net.neighbors(request.src)][:1]\n    return [(road, 1)]\n",
    "bad shape": "def choose_paths(net, request):\n    return 'nope'\n",
}


@pytest.mark.parametrize("name", sorted(ILLEGAL))
def test_a_deliberately_illegal_rule_is_rejected_and_blocks_everything(name):
    ratio, log = adapter.player_blocking(ILLEGAL[name], 0.5, 0, N_SPEC)
    assert ratio == 1.0
    assert log.illegal > 0 and log.served == 0
    assert log.messages


def test_referee_messages_are_the_engine_messages():
    graph = grid(3, 3)
    capacity = {(1, 2): 4, (2, 3): 4}
    req = Request(0, 1, 3, 2, 1, 1, 9, 0.78)
    win = WindowInput(graph, capacity, [req], {0: 1.0}, {0: 4}, 0)
    caps = adapter.heuristic.build_caps(win)
    shared = [([1, 2, 3], 1), ([1, 2, 3], 1)]
    assert any("both use link" in m for m in adapter.check_answer(win, caps, req, shared))
    too_many = [([1, 2, 3], 3)]
    messages = adapter.check_answer(win, caps, req, too_many)
    assert any("promised 2 pairs but routed 3" in m for m in messages)
    assert not any("spare" in m for m in messages)
    tight = {(1, 2): 2, (2, 3): 2}
    win2 = WindowInput(graph, tight, [req], {0: 1.0}, {0: 4}, 0)
    caps2 = adapter.heuristic.build_caps(win2)
    # using every seat is legal: the spare-seat rule is a strategy, not a law
    assert adapter.check_answer(win2, caps2, req, [([1, 2, 3], 2)]) == []
    assert any("seats this round" in m for m in adapter.check_answer(win2, caps2, req, [([1, 2, 3], 3)]))


def test_too_many_middle_cities_is_reported():
    graph = grid(3, 3)
    capacity = {e: 6 for e in graph.edges}
    capacity = {(min(u, v), max(u, v)): c for (u, v), c in capacity.items()}
    req = Request(0, 1, 9, 1, 1, 1, 9, 0.78)
    win = WindowInput(graph, capacity, [req], {0: 1.0}, {0: 1}, 0)
    caps = adapter.heuristic.build_caps(win)
    messages = adapter.check_answer(win, caps, req, [([1, 2, 3, 6, 9], 1)])
    assert any("middle cities" in m for m in messages)


def test_player_errors_become_plain_messages():
    with pytest.raises(adapter.PlayerCrash, match="line 2: ZeroDivisionError"):
        adapter.player_blocking("def choose_paths(net, request):\n    return 1 / 0\n", 0.5, 0, N_SPEC)
    with pytest.raises(adapter.PlayerCrash, match="cannot read your code"):
        adapter.load_player_function("def choose_paths(net, request)\n    return []\n")
    with pytest.raises(adapter.PlayerCrash, match="must define a function named choose_paths"):
        adapter.load_player_function("x = 1\n")
    assert "error" in json.loads(adapter.run_challenge_json("x = 1\n", "lazy", 0.5, "[0]", N_SPEC, False))


def test_printed_output_is_captured():
    source = "def choose_paths(net, request):\n    print('hi')\n    return []\n"
    result = adapter.run_challenge(source, "lazy", 0.5, [0], N_SPEC)
    assert "hi" in result["printed"]


def test_splitter_template_runs_and_declines_everything_legally():
    result = adapter.run_challenge(text("templates/splitter.py"), "lazy", 0.5, [0, 1], N_SPEC)
    assert result["illegal"] == 0 and result["player"] == [1.0, 1.0]


@pytest.mark.parametrize("name, baseline, zero", [("c1", "lazy", False), ("c2", "sp_heu", True), ("c3", "mp_heu", False)])
def test_each_working_solution_wins_its_challenge_at_q_0_5(name, baseline, zero):
    result = adapter.run_challenge(text(f"solutions/{name}.py"), baseline, 0.5, list(range(CODELAB["seeds"])), N_SPEC, zero)
    assert result["illegal"] == 0
    assert result["won"] is True and result["mean_diff"] + result["ci"] < 0


def test_the_adapter_loads_only_modules_that_work_without_pulp():
    worker = (LAB / "js" / "codelab-worker.js").read_text(encoding="utf-8")
    listed = set(re.search(r"ENGINE_FILES = \[(.*?)\]", worker).group(1).replace('"', "").replace(" ", "").split(","))
    assert "ilp" not in listed
    needed = set()
    for name in listed:
        source = (ROOT / "src" / "qmp" / f"{name}.py").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(import|from)\s+pulp", source, re.M), name
        needed |= set(re.findall(r"^from qmp\.(\w+) import", source, re.M)) | set(re.findall(r"^from qmp import (\w+)", source, re.M))
    adapter_source = (PY / "codelab_adapter.py").read_text(encoding="utf-8")
    needed |= set(re.findall(r"^from qmp\.(\w+) import", adapter_source, re.M)) | {"heuristic"}
    assert needed <= listed, needed - listed


def test_every_code_lab_challenge_has_files_and_hints():
    hints = json.loads((LAB / "data" / "hints.json").read_text(encoding="utf-8"))
    for name in ("c1", "c2", "c3"):
        assert (PY / "solutions" / f"{name}.py").exists() and (PY / "skeletons" / f"{name}.py").exists()
        assert len(hints[f"codelab-{name}"]["levels"]) == 5


def test_diff_module_pairs_changed_lines():
    # the diff runs in the browser, so check its plain logic by running node
    import shutil
    import subprocess
    if shutil.which("node") is None:
        pytest.skip("node is not installed")
    script = ("import { alignLines } from './quantumlab/js/codelab-diff.js';"
              "console.log(JSON.stringify(alignLines('a\\nb\\nc', 'a\\nB\\nc\\nd')));")
    done = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, capture_output=True, text=True, check=True, timeout=30)
    rows = json.loads(done.stdout)
    assert [r["mark"] for r in rows] == ["same", "change", "same", "plus"]


def test_the_referee_does_not_check_the_spare_seat_rule():
    source = "def choose_paths(net, request):\n    return []\n"
    assert "spare" not in " ".join(m.lower() for m in adapter.run_challenge(source, "lazy", 0.5, [0], N_SPEC)["messages"])
    assert "spare_problems" not in (PY / "codelab_adapter.py").read_text(encoding="utf-8")

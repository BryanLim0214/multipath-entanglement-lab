"""Checks QuantumLab's exported data, its hint text, and that its JavaScript agrees with the Python engine.

Everything here is a small single-process check: no solver pools and no experiments.
"""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from math import comb
from pathlib import Path

import pytest

from qmp.core import validate
from qmp.fidelity import max_intermediate, path_fidelity

ROOT = Path(__file__).resolve().parent.parent
LAB = ROOT / "quantumlab"
DATA = LAB / "data"


def load_module(name: str, path: Path):
    """Import a script that is not inside a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


exporter = load_module("quantumlab_export", LAB / "tools" / "export_data.py")
linter = load_module("quantumlab_lint", ROOT / "tools" / "lint_slop.py")


def read_json(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def without_commit(data: dict) -> dict:
    """The engine commit changes whenever src/ is committed; the source hash is what must match."""
    clone = json.loads(json.dumps(data))
    clone["meta"].pop("engine_commit")
    return clone


@pytest.mark.parametrize("name", ["fig1_steps.json", "rushhour.json", "fidelity.json"])
def test_committed_data_equals_a_fresh_export(name):
    fresh = exporter.build_all()[name]
    assert without_commit(read_json(name)) == without_commit(json.loads(json.dumps(fresh)))


def test_exporter_is_deterministic():
    first = json.dumps(exporter.build_all())
    second = json.dumps(exporter.build_all())
    assert first == second


def test_fig1_residuals_match_the_paper_figure_1c():
    steps = read_json("fig1_steps.json")["steps"]
    residual = {(l["a"], l["b"]): l["after"] for l in steps[-1]["links"]}
    expected = {(7, 8): 3, (5, 8): 6, (5, 6): 2, (1, 7): 2, (1, 2): 4, (2, 4): 2, (4, 6): 2}
    assert residual == expected


def test_fig1_alpha_values_and_split():
    steps = read_json("fig1_steps.json")["steps"]
    first = steps[0]
    assert [(c["node"], c["num"], c["den"]) for c in first["candidates"]] == [(1, 4, 3), (8, 4, 2)]
    at8 = steps[1]
    three = [c for c in at8["candidates"] if c["node"] == 3][0]
    assert (three["num"], three["den"]) == (3, 2)  # the paper prints 4/2
    allocation = [s for s in steps if s["kind"] == "allocation"][0]
    assert [x["pairs"] for x in allocation["split"]] == [2, 2]


def test_fidelity_limits_match_the_engine_and_study_guide():
    data = read_json("fidelity.json")
    assert data["limits"]["0.78"] == max_intermediate(0.95, 0.78) == 4
    assert data["limits"]["0.60"] == max_intermediate(0.95, 0.60) == 10


def test_rushhour_single_road_blocks_one_request_and_split_serves_all():
    for inst in read_json("rushhour.json")["instances"]:
        sol = inst["solutions"]
        assert sol["single_off"]["served"] < len(inst["requests"])
        assert sol["split_off"]["served"] == len(inst["requests"])


def js_task_ids() -> set[str]:
    """Task ids written in the JavaScript, as TASK_ID = "..." or taskId: "..."."""
    pattern = re.compile(r"TASK_ID\s*=\s*[\"']([\w-]+)[\"']|taskId:\s*[\"']([\w-]+)[\"']")
    ids = set()
    for path in (LAB / "js").rglob("*.js"):
        for first, second in pattern.findall(path.read_text(encoding="utf-8")):
            ids.add(first or second)
    return ids


def test_every_task_in_the_js_has_five_hint_levels():
    hints = read_json("hints.json")
    ids = js_task_ids()
    assert ids, "no task ids found in the JavaScript"
    assert ids == set(hints), f"JS uses {sorted(ids)} but hints.json has {sorted(hints)}"
    names = ["Nudge", "Hint", "Stronger hint", "Show me", "Do it for me"]
    for task, entry in hints.items():
        assert len(entry["levels"]) == 5, task
        for name, level in zip(names, entry["levels"]):
            assert level["kid"].strip() and level["student"].strip(), (task, name)
        assert entry["breaks"].strip(), task


def test_do_it_for_me_explains_in_two_or_three_sentences():
    for task, entry in read_json("hints.json").items():
        last = entry["levels"][4]
        sentences = re.findall(r"[.!?](?:\s|$)", last["kid"] + " " + last["student"])
        assert 2 <= len(sentences) <= 3, (task, len(sentences))


def all_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from all_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from all_strings(value)


def test_every_hint_string_passes_the_slop_lint():
    for text in all_strings(read_json("hints.json")):
        for name, rule in linter.TEXT_RULES:
            assert not rule.search(text), f"{name}: {text}"
        assert "!" not in text, text


def test_numbers_quoted_in_hints_come_from_the_engine():
    text = json.dumps(read_json("hints.json"), ensure_ascii=False)
    pmf = {k: comb(6, k) * 0.8 ** k * 0.2 ** (6 - k) for k in range(7)}
    assert f"about {pmf[5]:.2f}" in text and f"about {pmf[6]:.2f}" in text
    assert f"{path_fidelity(0.95, 5):.3f}" in text and f"{path_fidelity(0.95, 6):.3f}" in text
    assert f"gives {path_fidelity(0.95, 6):.2f}" in text


BAD_ANSWERS = [
    [{"request": 1, "roads": [{"nodes": [5, 4, 1], "pairs": 2}]}],
    [{"request": 1, "roads": [{"nodes": [4, 1], "pairs": 2}]}],
    [{"request": 1, "roads": [{"nodes": [5, 4, 5, 4, 1], "pairs": 2}]}],
    [{"request": 1, "roads": [{"nodes": [5, 3, 1], "pairs": 2}]}],
    [{"request": 1, "roads": [{"nodes": [5, 4, 1], "pairs": 1}, {"nodes": [5, 4, 1], "pairs": 1}]}],
    [{"request": 3, "roads": [{"nodes": [3, 2, 1], "pairs": 4}]}],
    [{"request": 2, "roads": [{"nodes": [6, 3], "pairs": 3}]}, {"request": 3, "roads": [{"nodes": [3, 2, 1], "pairs": 4}]}],
    [{"request": 1, "roads": [{"nodes": [5, 4, 1], "pairs": 0}]}],
    [{"request": 1, "roads": []}],
    [{"request": 1, "roads": [{"nodes": [5, 4, 1], "pairs": 2}]}, {"request": 1, "roads": [{"nodes": [5, 4, 1], "pairs": 2}]}],
    [{"request": 9, "roads": [{"nodes": [5, 4, 1], "pairs": 2}]}],
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_javascript_referee_and_formulas_match_python():
    rush = read_json("rushhour.json")["instances"][0]
    win = exporter.rush_window(exporter.RUSH_INSTANCES[0])
    answers = BAD_ANSWERS + [[{"request": a["request"], "roads": a["roads"]} for a in rush["solutions"][k]["ilp"]]
                             for k in rush["solutions"]]
    fid = [{"F": 0.95, "f": f} for f in (0.5, 0.6, 0.78, 0.9, 0.96)]
    pmf = [{"m": 6, "q": q} for q in (0.5, 0.8, 0.9)]
    payload = json.dumps({"instance": rush, "answers": answers, "fidelity": fid, "pmf": pmf})
    done = subprocess.run(["node", str(LAB / "tools" / "parity_check.mjs")], input=payload, capture_output=True,
                          text=True, check=True, timeout=60)
    js = json.loads(done.stdout)
    from qmp.core import Allocation
    for answer, messages in zip(answers, js["referee"]):
        allocs = [Allocation(a["request"], [(r["nodes"], r["pairs"]) for r in a["roads"]]) for a in answer]
        assert messages == validate(win, allocs), answer
    assert js["limits"] == [max_intermediate(0.95, f["f"]) for f in fid]
    for row, case in zip(js["pathFidelity"], fid):
        assert row == pytest.approx([path_fidelity(0.95, L) for L in (1, 2, 5, 6)])
    for bars, case in zip(js["pmf"], pmf):
        exact = [comb(6, k) * case["q"] ** k * (1 - case["q"]) ** (6 - k) for k in range(7)]
        assert bars == pytest.approx(exact)


def test_contrast_script_passes():
    contrast = load_module("quantumlab_contrast", LAB / "tools" / "check_contrast.py")
    rows, ok = contrast.report()
    assert ok, "\n".join(r for r in rows if "FAIL" in r)

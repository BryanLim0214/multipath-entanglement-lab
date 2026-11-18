"""Both ILPs must reproduce the hand-solved toy answers in toy_expected.md, with HiGHS and with CBC."""
import re
from pathlib import Path

import networkx as nx
import pytest
import yaml

from qmp import ilp
from qmp.core import Request, WindowInput, edge, objective, validate

TEXT = (Path(__file__).parent / "toy_expected.md").read_text(encoding="utf-8")
TOYS = yaml.safe_load(re.search(r"```yaml\n(.*?)```", TEXT, re.S).group(1))


def build(toy: dict, max_mid: int) -> tuple[WindowInput, dict[int, str]]:
    """Make a WindowInput from a toy; request names such as 'r1' get integer ids 1, 2, ..."""
    g = nx.Graph()
    caps = {}
    for u, v, c in toy["edges"]:
        g.add_edge(u, v)
        caps[edge(u, v)] = c
    reqs, rho, names = [], {}, {}
    for i, q in enumerate(toy["requests"], 1):
        reqs.append(Request(i, q["s"], q["d"], q["n"], 1, 1, 9, 0.8))
        rho[i], names[i] = q["rho"], q["id"]
    return WindowInput(g, caps, reqs, rho, {r.id: max_mid for r in reqs}), names


def served(res, names) -> set[str]:
    return {names[a.request_id] for a in res.allocations}


def check(win, res, expected_obj, names, expected_served=None):
    assert res.status == "optimal"
    assert validate(win, res.allocations) == []
    assert objective(win, res.allocations) == pytest.approx(expected_obj, abs=1e-9)
    if expected_served is not None:
        assert served(res, names) == set(expected_served)


@pytest.mark.parametrize("solver", ["highs", "cbc"])
@pytest.mark.parametrize("toy_name", ["toy1", "toy2"])
def test_toy_mp_and_sp(toy_name, solver):
    toy = TOYS[toy_name]
    exp = toy["expected"]
    win, names = build(toy, toy["I"])
    runs = [
        ilp.solve_path(win, solver=solver),
        ilp.solve_arc(win, solver=solver),
        ilp.solve_arc(win, directed_disjoint=True, solver=solver),
    ]
    for res in runs:
        check(win, res, exp["mp_ilp"], names, exp["mp_ilp_served"])
    sp_runs = [ilp.solve_path(win, K=1, solver=solver), ilp.solve_arc(win, K=1, solver=solver)]
    for res in sp_runs:
        check(win, res, exp["sp_ilp"], names, exp.get("sp_ilp_served"))


@pytest.mark.parametrize("solver", ["highs", "cbc"])
def test_toy2_without_hop_limit(solver):
    toy = TOYS["toy2"]
    exp = toy["expected"]
    win, names = build(toy, 99)
    for res in (ilp.solve_path(win, solver=solver), ilp.solve_arc(win, solver=solver)):
        check(win, res, exp["mp_ilp_no_hop_limit"], names, exp["mp_ilp_no_hop_limit_served"])
    assert objective(win, ilp.solve_path(win, solver=solver).allocations) == pytest.approx(1.0)

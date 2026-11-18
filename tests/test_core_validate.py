"""The referee must accept a legal answer and catch every kind of illegal one."""
import networkx as nx
import pytest

from qmp.core import Allocation, Request, WindowInput, edge, objective, validate


@pytest.fixture
def win():
    g = nx.Graph()
    caps = {(1, 2): 2, (2, 5): 2, (1, 3): 2, (3, 5): 2, (1, 4): 1, (4, 5): 1}
    g.add_edges_from(caps)
    reqs = [Request(1, 1, 5, 4, 1, 1, 9, 0.78), Request(2, 1, 5, 1, 1, 1, 9, 0.78)]
    return WindowInput(g, {edge(*e): c for e, c in caps.items()}, reqs, {1: 1.0, 2: 0.5}, {1: 4, 2: 4})


def test_legal_split_passes(win):
    allocs = [Allocation(1, [([1, 2, 5], 2), ([1, 3, 5], 2)]), Allocation(2, [([1, 4, 5], 1)])]
    assert validate(win, allocs) == []
    assert objective(win, allocs) == 1.5


@pytest.mark.parametrize("allocs, fragment", [
    ([Allocation(1, [([1, 2, 5], 4)])], "has 2 seats"),
    ([Allocation(1, [([1, 2, 5], 2), ([1, 2, 5], 2)])], "both use link"),
    ([Allocation(1, [([1, 2, 5], 2), ([1, 3, 5], 1)])], "All or nothing"),
    ([Allocation(1, [([1, 2, 3, 5], 4)])], "no link 2-3"),
    ([Allocation(1, [([2, 5], 4)])], "must start at 1"),
    ([Allocation(1, [([1, 2, 1, 2, 5], 4)])], "visits a city twice"),
    ([Allocation(9, [([1, 2, 5], 1)])], "not waiting"),
    ([Allocation(2, [([1, 4, 5], 1)]), Allocation(2, [([1, 4, 5], 1)])], "placed twice"),
    ([Allocation(2, [([1, 4, 5], 0), ([1, 2, 5], 1)])], "at least 1 pair"),
])
def test_illegal_answers_are_caught(win, allocs, fragment):
    errors = validate(win, allocs)
    assert any(fragment in e for e in errors), errors


def test_hop_limit_is_enforced(win):
    win.max_mid[2] = 0
    assert any("middle cities" in e for e in validate(win, [Allocation(2, [([1, 4, 5], 1)])]))

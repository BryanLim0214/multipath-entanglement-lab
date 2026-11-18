"""Checks the fidelity model against the paper's stated hop limits (A5)."""
import pytest

from qmp.fidelity import max_intermediate, path_fidelity


def test_paper_hop_limits():
    assert max_intermediate(0.95, 0.78) == 4
    assert max_intermediate(0.95, 0.6) == 10
    assert max_intermediate(0.95, 0.85) == 2


def test_five_link_fidelity():
    assert path_fidelity(0.95, 5) == pytest.approx(0.7812, abs=1e-4)

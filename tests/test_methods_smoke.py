"""Smoke test: every registered method runs on a tiny config and returns a sensible blocking ratio.

Also checks that every placer can be pickled, because Windows multiprocessing sends it to worker processes.
"""
import pickle
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from experiments.methods import METHODS  # noqa: E402
from qmp.sim import SimConfig, simulate  # noqa: E402

TINY = SimConfig(rows=3, cols=3, R=10, M=6, T=30, tc=10, q=0.7, F=0.95, f=0.78, n_spec="uniform:2:4", seed=0)


def test_registry_has_the_eight_methods():
    assert set(METHODS) == {"SP-SPF", "SP-Heu", "MP-Heu", "SP-ILP", "MP-ILP", "MP-Heu-d1", "MP-Heu-deadline",
                            "MP-ILP-delta"}


@pytest.mark.parametrize("name", sorted(METHODS))
def test_method_runs_on_tiny_config(name):
    res = simulate(TINY, METHODS[name])
    assert 0.0 <= res.blocking_ratio <= 1.0
    assert 0.0 <= res.gamma <= 1.0
    assert res.time_limit_windows == 0


@pytest.mark.parametrize("name", sorted(METHODS))
def test_placer_is_picklable(name):
    assert pickle.loads(pickle.dumps(METHODS[name])).keywords == METHODS[name].keywords

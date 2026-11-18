"""Registry of every placement method used in Part A and Part C.

Each entry is a functools.partial of a module-level function, so it can be pickled and sent to
Windows (spawn) worker processes. The headline ILP is the path formulation (A26).
"""
from __future__ import annotations

from functools import partial

from qmp.heuristic import place_heuristic, place_spf
from qmp.ilp import solve_path

ILP_TIME_LIMIT = 60  # seconds per window

METHODS = {
    "SP-SPF": partial(place_spf, delta=2),
    "SP-Heu": partial(place_heuristic, multipath=False, delta=2),
    "MP-Heu": partial(place_heuristic, multipath=True, delta=2),
    "SP-ILP": partial(solve_path, K=1, time_limit=ILP_TIME_LIMIT),
    "MP-ILP": partial(solve_path, time_limit=ILP_TIME_LIMIT),
    "MP-Heu-d1": partial(place_heuristic, multipath=True, delta=1),
    "MP-Heu-deadline": partial(place_heuristic, multipath=True, delta=2, delta_policy="deadline"),
    "MP-ILP-delta": partial(solve_path, delta=2, time_limit=ILP_TIME_LIMIT),
}

ILP_METHODS = {"SP-ILP", "MP-ILP", "MP-ILP-delta"}

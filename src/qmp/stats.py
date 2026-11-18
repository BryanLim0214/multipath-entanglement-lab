"""Confidence intervals for repeated simulation runs (paper: 95% CIs over runs).

Provides a t-distribution mean interval and a paired-difference interval.
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def mean_ci(values, conf: float = 0.95) -> tuple[float, float]:
    """Mean and t-distribution half-width; half-width is 0 for fewer than 2 values."""
    x = np.asarray(values, dtype=float)
    mean = float(x.mean())
    if len(x) < 2:
        return mean, 0.0
    sem = float(x.std(ddof=1)) / np.sqrt(len(x))
    return mean, float(stats.t.ppf((1 + conf) / 2, len(x) - 1) * sem)


def paired_diff_ci(a, b, conf: float = 0.95) -> tuple[float, float]:
    """Mean of a - b (paired by position) with its t half-width (A19)."""
    return mean_ci(np.asarray(a, dtype=float) - np.asarray(b, dtype=float), conf)

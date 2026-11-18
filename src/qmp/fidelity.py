"""Fidelity of an entanglement-swapped path under the Werner-state model (A5).

Used to turn the minimum end-to-end fidelity f into a limit on intermediate nodes.
"""
from __future__ import annotations


def werner_w(F: float) -> float:
    """Werner parameter of a pair with fidelity F (A5)."""
    return (4 * F - 1) / 3


def path_fidelity(F: float, links: int) -> float:
    """Fidelity after ideal swapping over `links` links of fidelity F (A5)."""
    return (3 * werner_w(F) ** links + 1) / 4


def max_intermediate(F: float, f: float) -> int:
    """Largest number of intermediate nodes whose path fidelity is still >= f (A5).

    Returns -1 if even a single link is below f.
    """
    if f <= 0.25:
        raise ValueError("Path fidelity never drops below 0.25, so the limit would be infinite.")
    if path_fidelity(F, 1) < f:
        return -1
    links = 1
    while path_fidelity(F, links + 1) >= f:
        links += 1
    return links - 1

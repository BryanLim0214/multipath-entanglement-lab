"""Closed-form success probability of one request on the two-branch network (A22, independent attempts).
A link needs at least m successes in its M attempts to carry m pairs.
"""
from math import ceil, comb, floor


def p_at_least(m, M, q):
    """P(Bin(M, q) >= m). Zero or fewer pairs needed is certain."""
    if m <= 0:
        return 1.0
    return sum(comb(M, j) * q ** j * (1 - q) ** (M - j) for j in range(m, M + 1))


def p_path(links, m, M, q):
    """Every one of `links` independent links carries m pairs."""
    return p_at_least(m, M, q) ** links


def p_sp(n, M, q, links=3):
    """Single path of `links` links carrying all n pairs: P(Bin(M,q) >= n)^links."""
    return p_path(links, n, M, q)


def p_mp(n, M, q, links=3):
    """Two disjoint paths of `links` links; the first carries ceil(n/2) pairs, the second floor(n/2)."""
    return p_path(links, ceil(n / 2), M, q) * p_path(links, floor(n / 2), M, q)

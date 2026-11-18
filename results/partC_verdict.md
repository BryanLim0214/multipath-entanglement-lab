# Part C verdict: deadline-aware delta

Rule (pre-registered in docs/scope_note.md): at q = 0.5 on the 3x3 setup, the paired mean of BR(MP-Heu) - BR(MP-Heu-deadline) must be at least 0.03 and the lower bound of its 95% CI must be above 0.

**Verdict: SUPPORTED.**

At q = 0.5, n = 30 paired seeds: mean difference 0.2278, 95% CI [0.2125, 0.2431]. Threshold 0.03.

## All q

| q | BR(MP-Heu) - BR(deadline), 95% CI | BR(MP-Heu) - BR(d1), 95% CI | gap closed, deadline | gap closed, d1 |
|---|---|---|---|---|
| 0.5 | 0.23 ± 0.02 | 0.39 ± 0.01 | 0.56 | 0.96 |
| 0.6 | 0.16 ± 0.02 | 0.25 ± 0.02 | 0.65 | 1.01 |
| 0.7 | 0.07 ± 0.02 | 0.10 ± 0.02 | 0.73 | 1.00 |
| 0.8 | 0.02 ± 0.01 | 0.02 ± 0.01 | 0.86 | 1.00 |
| 0.9 | 0.01 ± 0.00 | 0.01 ± 0.00 | 1.00 | 1.00 |

Gap closed = (BR_MP-Heu - BR_variant) / (BR_MP-Heu - BR_MP-ILP), from the means over seeds. n/a means MP-Heu is not above MP-ILP at that q.

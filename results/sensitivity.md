# Sensitivity of the blocking-ratio level (held out, after Part A)

n = uniform:2:2 (calibrated), 3x3 grid, |R| = 60, 30 seeds. Mean ± 95% CI half-width.
Paper at q = 0.9: MP-ILP 0.27, SP-ILP 0.42 (printed).

| variant | method | q = 0.5 | q = 0.9 | time-limited windows |
|---|---|---|---|---|
| baseline | SP-Heu | 0.69 ± 0.02 | 0.04 ± 0.01 | 0 |
| baseline | MP-Heu | 0.48 ± 0.02 | 0.01 ± 0.00 | 0 |
| baseline | SP-ILP | 0.12 ± 0.02 | 0.00 ± 0.00 | 0 |
| baseline | MP-ILP | 0.07 ± 0.02 | 0.00 ± 0.00 | 0 |
| gaps | SP-Heu | 0.79 ± 0.02 | 0.37 ± 0.02 | 0 |
| gaps | MP-Heu | 0.59 ± 0.02 | 0.35 ± 0.03 | 0 |
| gaps | SP-ILP | 0.39 ± 0.02 | 0.35 ± 0.03 | 0 |
| gaps | MP-ILP | 0.37 ± 0.02 | 0.35 ± 0.03 | 0 |
| per-slot | SP-Heu | 0.86 ± 0.02 | 0.73 ± 0.02 | 0 |
| per-slot | MP-Heu | 0.75 ± 0.02 | 0.48 ± 0.02 | 0 |
| per-slot | SP-ILP | 0.62 ± 0.02 | 0.35 ± 0.02 | 0 |
| per-slot | MP-ILP | 0.50 ± 0.02 | 0.19 ± 0.02 | 0 |
| gaps+per-slot | SP-Heu | 0.93 ± 0.01 | 0.83 ± 0.02 | 0 |
| gaps+per-slot | MP-Heu | 0.85 ± 0.01 | 0.65 ± 0.02 | 0 |
| gaps+per-slot | SP-ILP | 0.76 ± 0.02 | 0.57 ± 0.03 | 0 |
| gaps+per-slot | MP-ILP | 0.63 ± 0.02 | 0.41 ± 0.02 | 0 |

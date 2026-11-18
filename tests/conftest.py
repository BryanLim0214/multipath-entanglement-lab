"""Test-wide setup: one BLAS thread per process, set before numpy is imported (docs/TROUBLESHOOTING.md)."""
import os

for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

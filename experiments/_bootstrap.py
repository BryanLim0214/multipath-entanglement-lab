"""Puts the repo root and src/ on sys.path so the scripts run as `python experiments/<name>.py`.

Import this first in every script. Windows spawn workers re-import the script, so they get it too.
"""
import os
import sys
from pathlib import Path

# One BLAS thread per process: with the default 28, each worker reserved ~1.5 GB (docs/TROUBLESHOOTING.md).
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT / "src"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

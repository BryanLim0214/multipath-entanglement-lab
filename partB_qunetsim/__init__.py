"""Part B: single-path vs multipath entanglement routing in QuNetSim."""
import os

# One BLAS thread per process. QuNetSim's EQSN backend starts a process per qubit, and with the
# default 28 BLAS threads each process reserved ~1.5 GB, which exhausted memory (docs/TROUBLESHOOTING.md).
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

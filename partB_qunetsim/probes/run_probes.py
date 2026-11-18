"""Runs each probe in its own Python process with a hard timeout, so a QuNetSim hang cannot block us.
Usage:  .venv\Scripts\python.exe partB_qunetsim\probes\run_probes.py [p1 p2 ...]   (default: all)
"""
import subprocess, sys, pathlib, time

HERE = pathlib.Path(__file__).parent
TIMEOUT = {"p6": 900, "p7": 1200, "p8": 1500}          # seconds; everything else gets 240
names = sys.argv[1:] or ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8"]

for name in names:
    script = next(HERE.glob(f"{name}_*.py"))
    print(f"===== {script.name} =====", flush=True)
    t0 = time.time()
    p = subprocess.Popen([sys.executable, str(script)], cwd=HERE.parent.parent)
    try:
        p.wait(timeout=TIMEOUT.get(name, 240))
        print(f"----- exit code {p.returncode} after {time.time()-t0:.1f}s", flush=True)
    except subprocess.TimeoutExpired:
        # kill the whole process tree (QuNetSim/EQSN start child processes)
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        print(f"[FAIL] {script.name} timed out after {TIMEOUT.get(name, 240)}s (hang) - killed", flush=True)

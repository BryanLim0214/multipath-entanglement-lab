"""Check every lab requirement in tracker.yaml against real evidence.

A requirement only PASSes if its check (file exists, file contains text, command exits 0, ...)
succeeds right now. Results go to the console and to .agent/TRACKER_STATUS.md with the git SHA,
so a "PASS" can never be a word someone typed.
"""
import datetime as dt
import hashlib
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def first_commit_date(path):
    out = git("log", "--diff-filter=A", "--format=%cI", "--reverse", "--", path)
    return dt.datetime.fromisoformat(out.splitlines()[0]) if out else None


def sha256(path):
    p = ROOT / path
    if not p.is_file():
        return "-"
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def run_check(item, cfg):
    """Return (ok, detail) for one tracker item; ok is True/False/None (None = needs a human)."""
    check = item["check"]
    if "exists" in check:
        missing = [p for p in check["exists"] if not (ROOT / p).exists()]
        return (not missing, f"missing: {missing}" if missing else "all present")
    if "contains" in check:
        spec = check["contains"]
        f = ROOT / spec["file"]
        if not f.is_file():
            return False, f"{spec['file']} not found"
        text = f.read_text(encoding="utf-8", errors="replace")
        lacking = [s for s in spec.get("all", []) if s not in text]
        leftover = [s for s in spec.get("none", []) if s in text]
        ok = not lacking and not leftover
        return ok, ("ok" if ok else f"lacking {lacking} / still has {leftover}")
    if "cmd" in check:
        cmd = check["cmd"]
        if cmd.startswith("python "):
            cmd = f'"{sys.executable}" ' + cmd[len("python "):]
        r = subprocess.run(cmd, cwd=ROOT, shell=True, capture_output=True, text=True)
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
        return r.returncode == 0, f"exit {r.returncode}: {tail[0][:80]}"
    if "manual" in check:
        key = check["manual"]
        if key == "approval":
            ev = cfg["approval"]
            ok = bool(ev.get("scope_approved_on") and ev.get("evidence"))
        else:
            ok = bool(item.get("evidence"))
        return (True if ok else None), ("evidence recorded" if ok else "needs human evidence")
    if "committed_before" in check:
        spec = check["committed_before"]
        a, b = first_commit_date(spec["first"]), first_commit_date(spec["then"])
        if a is None:
            return False, f"{spec['first']} never committed"
        if b is None:
            return False, f"{spec['then']} not committed yet"
        return a <= b, f"{spec['first']} {a:%Y-%m-%d %H:%M} vs {spec['then']} {b:%Y-%m-%d %H:%M}"
    if "no_code_before_approval" in check:
        approved = cfg["approval"].get("scope_approved_on")
        for path in check["no_code_before_approval"]["paths"]:
            first = first_commit_date(path)
            if first is None:
                continue
            if not approved or first.date() < dt.date.fromisoformat(str(approved)):
                return False, f"{path} committed {first:%Y-%m-%d} before approval ({approved})"
        return True, "no project code before approval"
    return False, "unknown check type"


def main():
    cfg = yaml.safe_load((ROOT / "tracker.yaml").read_text(encoding="utf-8"))
    start = dt.date.fromisoformat(str(cfg["start_date"]))
    week_now = (dt.date.today() - start).days // 7 + 1
    rows, failures = [], 0
    for item in cfg["items"]:
        ok, detail = run_check(item, cfg)
        if ok is True:
            status = "PASS"
        elif ok is None:
            status = "MANUAL"
        elif item["week"] > week_now:
            status = "TODO"
        else:
            status = "FAIL"
            failures += 1
        artifact = item["check"].get("contains", {}).get("file", "")
        rows.append((item["id"], item["week"], status, detail, sha256(artifact) if artifact else "-"))

    sha = git("rev-parse", "--short", "HEAD") or "uncommitted"
    lines = [f"# Tracker status (week {week_now}, commit {sha}, {dt.datetime.now():%Y-%m-%d %H:%M})", "",
             "| ID | Week | Status | Evidence | sha256 |", "|---|---|---|---|---|"]
    lines += [f"| {i} | {w} | {s} | {d} | {h} |" for i, w, s, d, h in rows]
    (ROOT / ".agent").mkdir(exist_ok=True)
    (ROOT / ".agent" / "TRACKER_STATUS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for i, w, s, d, _ in rows:
        print(f"{s:7} W{w} {i:20} {d}")
    print(f"\n{failures} item(s) due by week {week_now} not yet passing. Full table: .agent/TRACKER_STATUS.md")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()

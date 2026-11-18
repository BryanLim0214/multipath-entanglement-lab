"""Check the compiled report's page count from the LaTeX log (lab: a 4-6 page report).

Usage: python tools/check_report.py report/main.log --min-pages 4 --max-pages 6
"""
import argparse
import re
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--min-pages", type=int, required=True)
    ap.add_argument("--max-pages", type=int, required=True)
    args = ap.parse_args()
    log = Path(args.log)
    if not log.is_file():
        sys.exit(f"{log} not found (compile the report first)")
    m = re.search(r"Output written on .*?\((\d+) pages?", log.read_text(encoding="latin-1", errors="replace"))
    if not m:
        sys.exit("no page count in the log")
    pages = int(m.group(1))
    print(f"report: {pages} pages")
    if not args.min_pages <= pages <= args.max_pages:
        sys.exit(f"FAIL: outside {args.min_pages}-{args.max_pages} pages")


if __name__ == "__main__":
    main()

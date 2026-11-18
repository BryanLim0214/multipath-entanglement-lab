"""Fail on "AI slop" in user-facing files: em dashes, emoji, hype words, pills, glass, opacity tricks.

Rules come from docs/DESIGN_RULES.md. A line can opt out with "slop-ok: <reason>", and the
hostile reviewer audits every waiver. Exit code 1 if anything is found.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {".venv", ".git", ".claude", ".ralphy", ".agent", "node_modules", "vendor"}
SKIP_FILES = {"docs/DESIGN_RULES.md"}
TEXT_EXT = {".md", ".tex", ".html", ".js", ".css", ".txt"}
STYLE_EXT = {".html", ".css", ".js"}

TEXT_RULES = [
    ("em dash", re.compile("—")),
    ("emoji", re.compile("[\U0001F000-\U0001FAFF☀-➿️]")),
    ("hype word", re.compile(
        r"\b(delve|seamless(ly)?|leverag(e|es|ing)|cutting-edge|game-changing|revolutionary|unlock(s|ed)?|"
        r"unleash|elevate|empower|supercharge|effortless(ly)?|harness|tapestry|realm|embark|dive into|"
        r"it's important to note|in today's world|at the end of the day|a testament to)\b", re.I)),
]
TEX_RULES = [("em dash (LaTeX ---)", re.compile(r"(?<!-)---(?!-)"))]
STYLE_RULES = [
    ("pill radius", re.compile(r"border-radius\s*:\s*(\d{3,}|[5-9]\d)px|rounded-full|9999px", re.I)),
    ("radius off-scale", re.compile(r"border-radius\s*:\s*(?!0\b|0px|2px|4px|50%)[\d.]+(px|rem|em)", re.I)),
    ("glass blur", re.compile(r"backdrop-filter", re.I)),
    ("translucent panel", re.compile(r"rgba\(\s*(255\s*,\s*255\s*,\s*255|0\s*,\s*0\s*,\s*0)\s*,\s*0?\.\d+\s*\)", re.I)),
    ("opacity hierarchy", re.compile(r"opacity\s*:\s*0?\.\d+", re.I)),
    ("gradient", re.compile(r"(linear|radial|conic)-gradient", re.I)),
    ("text glow", re.compile(r"text-shadow", re.I)),
    ("stock font", re.compile(r"font-family\s*:\s*['\"]?(Inter|Roboto|Poppins|Montserrat|Space Grotesk|Arial)\b", re.I)),
    ("idle loop", re.compile(r"animation[^;]*\binfinite\b", re.I)),
]


def files_to_check():
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if p.is_file() and p.suffix in TEXT_EXT and not (set(rel.parts) & SKIP_DIRS) \
                and rel.as_posix() not in SKIP_FILES and not rel.as_posix().startswith("requirements"):
            yield p, rel


def main():
    findings = []
    for path, rel in files_to_check():
        rules = TEXT_RULES + (STYLE_RULES if path.suffix in STYLE_EXT else []) + (TEX_RULES if path.suffix == ".tex" else [])
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if "slop-ok:" in line:
                continue
            for name, rx in rules:
                m = rx.search(line)
                if m:
                    findings.append(f"{rel.as_posix()}:{n}: {name}: ...{line[max(0, m.start() - 30):m.end() + 30].strip()}...")
    print("\n".join(findings) if findings else "No slop found.")
    sys.exit(1 if findings else 0)


if __name__ == "__main__":
    main()

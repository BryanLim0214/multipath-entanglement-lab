"""Computes WCAG contrast ratios for every token pair QuantumLab uses, in the light and dark themes.

It reads the tokens straight from css/lab.css, so the table in README.md cannot drift from the CSS.
Usage: .venv\\Scripts\\python.exe quantumlab\\tools\\check_contrast.py  (exit 1 if a pair fails)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "css" / "lab.css"
TEXT_MIN = 4.5
GRAPHIC_MIN = 3.0
TEXT_PAIRS = [("ink", "paper"), ("muted", "paper"), ("mp", "paper"), ("warn", "paper"),
              ("fail", "paper"), ("paper", "ink"), ("paper", "muted"), ("ink", "rule")]
GRAPHIC_ITEMS = ["sp", "ext", "ramp-0", "ramp-1", "ramp-2"]


def luminance(hex_color: str) -> float:
    """Relative luminance of #RRGGBB (WCAG 2.x)."""
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    """Contrast ratio between two #RRGGBB colors."""
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def tokens_in(block: str) -> dict[str, str]:
    """The --name: #hex pairs inside one CSS block."""
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9A-Fa-f]{6});", block))


def theme_tokens() -> dict[str, dict[str, str]]:
    """Light tokens from :root, dark tokens from the data-theme rule and from the media query."""
    css = CSS.read_text(encoding="utf-8")
    light = tokens_in(css.split(":root {", 1)[1].split("}", 1)[0])
    media = css.split(':root:not([data-theme="light"]) {', 1)[1].split("}", 1)[0]
    forced = css.split(':root[data-theme="dark"] {', 1)[1].split("}", 1)[0]
    if tokens_in(media) != tokens_in(forced):
        raise SystemExit("The two dark blocks in lab.css have different values.")
    return {"light": light, "dark": tokens_in(forced)}


def report() -> tuple[list[str], bool]:
    """Markdown table rows for every pair, and whether all pairs pass."""
    rows, ok = [], True
    for theme, tok in theme_tokens().items():
        for fg, bg in TEXT_PAIRS:
            r = ratio(tok[fg], tok[bg])
            passed = r >= TEXT_MIN
            ok &= passed
            rows.append(f"| {theme} | text | {fg} on {bg} | {tok[fg]} / {tok[bg]} | {r:.2f} | {'pass' if passed else 'FAIL'} |")
        for item in GRAPHIC_ITEMS:
            r = ratio(tok[item], tok["paper"])
            passed = r >= GRAPHIC_MIN
            ok &= passed
            rows.append(f"| {theme} | graphic | {item} on paper | {tok[item]} / {tok['paper']} | {r:.2f} | {'pass' if passed else 'FAIL'} |")
    return rows, ok


if __name__ == "__main__":
    table, all_ok = report()
    print("| Theme | Use | Pair | Colors | Ratio | Result |\n|---|---|---|---|---|---|")
    print("\n".join(table))
    sys.exit(0 if all_ok else 1)

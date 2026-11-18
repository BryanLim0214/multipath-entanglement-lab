"""Turn a short markdown document (headings, paragraphs, lists, bold, code) into a typeset PDF via pdflatex.

The markdown stays the single source of truth; the PDF is for people who want paper. Prints the page count
so one-page limits can be checked. Usage: python tools/md_to_pdf.py docs/scope_note.md [--max-pages 1]
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

UNICODE = {"×": r"$\times$", "≥": r"$\geq$", "≤": r"$\leq$", "ρ": r"$\rho$", "δ": r"$\delta$", "Γ": r"$\Gamma$",
           "→": r"$\to$", "−": r"$-$", "Σ": r"$\Sigma$", "α": r"$\alpha$", "π": r"$\pi$", "⌊": r"$\lfloor$",
           "⌋": r"$\rfloor$", "⟨": r"$\langle$", "⟩": r"$\rangle$", "₃": r"$_3$", "–": "--"}
PREAMBLE = r"""\documentclass[10pt]{article}
\usepackage[T1]{fontenc}
\usepackage{mathptmx}
\usepackage[margin=0.85in]{geometry}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\setlist{nosep,leftmargin=1.4em}
\setlength{\parindent}{0pt}
\setlength{\parskip}{4pt}
\newcommand{\hd}[1]{\par\vspace{5pt}{\large\bfseries #1}\par\vspace{1pt}}
\pagestyle{empty}
\begin{document}
"""


def inline(text):
    """Escape LaTeX specials, then convert **bold**, `code` and the few unicode symbols we use."""
    text = text.replace("\\", r"\textbackslash{}")
    for ch in "&%$#_{}":
        text = text.replace(ch, "\\" + ch)
    text = text.replace("~", r"\textasciitilde{}").replace("^", r"\textasciicircum{}")
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"`(.+?)`", r"\\texttt{\1}", text)
    text = re.sub(r'"(.+?)"', r"``\1''", text)
    text = re.sub(r"\b([A-Za-z])\\_([a-z])\b", r"$\1_{\2}$", text)
    for ch, tex in UNICODE.items():
        text = text.replace(ch, tex)
    return text


def convert(md):
    out, env = [PREAMBLE], None
    for line in md.splitlines():
        bullet = re.match(r"^\s*[-*] (.*)", line)
        numbered = re.match(r"^\s*\d+\. (.*)", line)
        want = "itemize" if bullet else "enumerate" if numbered else None
        if env and env != want:
            out.append(rf"\end{{{env}}}")
            env = None
        if want and env is None:
            out.append(rf"\begin{{{want}}}")
            env = want
        if want:
            out.append(r"\item " + inline((bullet or numbered).group(1)))
        elif line.startswith("# "):
            out.append(r"{\LARGE\bfseries " + inline(line[2:]) + r"}\par\vspace{4pt}")
        elif line.startswith("## "):
            out.append(r"\hd{" + inline(line[3:]) + "}")
        elif line.strip():
            out.append(inline(line))
        else:
            out.append("")
    if env:
        out.append(rf"\end{{{env}}}")
    out.append(r"\end{document}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown")
    ap.add_argument("--max-pages", type=int)
    args = ap.parse_args()
    src = Path(args.markdown).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        tex = Path(tmp) / (src.stem + ".tex")
        tex.write_text(convert(src.read_text(encoding="utf-8")), encoding="utf-8")
        r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
                           cwd=tmp, capture_output=True, text=True, timeout=180)
        log = (Path(tmp) / (src.stem + ".log")).read_text(encoding="latin-1", errors="replace")
        m = re.search(r"Output written on .*?\((\d+) pages?", log)
        if r.returncode != 0 or not m:
            print(log[-2000:])
            sys.exit("pdflatex failed")
        shutil.copy(Path(tmp) / (src.stem + ".pdf"), src.with_suffix(".pdf"))
    pages = int(m.group(1))
    print(f"{src.with_suffix('.pdf').name}: {pages} page(s)")
    if args.max_pages and pages > args.max_pages:
        sys.exit(f"over the {args.max_pages}-page limit")


if __name__ == "__main__":
    main()

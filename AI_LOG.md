# AI log

The handout requires "a short AI_LOG.md listing what you asked the AI to do and what you changed or rejected".

- Entries marked *(draft)* were pre-filled by the AI.
- **You** must confirm or edit the last column in your own words.

| Date | What I asked the AI | What it produced | What I kept / changed / rejected |
|---|---|---|---|
| 2026-11-17 | Read the handout and paper, research QuNetSim (source code), the paper's context and a 3D visualisation stack; propose a full plan | A 4-week plan, a list of paper gaps and inconsistencies, research reports | *(draft)* Kept the two-layer plan. **Rejected** the AI's first extension idea (fidelity-aware paths) after a hostile-review agent showed it was true by construction and really two extensions. Switched to deadline-aware δ. **Changed** two analogies flagged as physically misleading (photocopy → paint mixing, holding hands → matchmaker). |
| 2026-11-17 | Set up a Python 3.11 environment with pinned versions | `requirements.txt`, `requirements.lock.txt` | *(draft)* Kept; the pins were verified by an actual install. Python 3.11 was chosen because QuNetSim breaks on ≥3.12 (issue #171). |
| 2026-11-17 | Draft `ASSUMPTIONS.md`, a study guide, the paper-notes template, a toy worksheet, the tracker, and the scope-note draft | Those files | *(draft)* You still need to: write `paper_notes.md` yourself, solve the toys by hand, edit the scope note. |
| 2026-11-17 | Run the QuNetSim feasibility probes (P1–P6) | *(pending)* | |
| 2026-11-17 | Enforce a strict no-"AI slop" quality bar on every deliverable | `docs/DESIGN_RULES.md`, `tools/lint_slop.py` (canary-tested: 11 of 11 planted violations caught), `figures/qmp.mplstyle` | *(draft)* Kept. The AI's own first drafts broke the rules (emoji markers, em dashes in the study guide), so they were rewritten. |

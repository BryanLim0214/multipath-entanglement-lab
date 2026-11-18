# QuantumLab spec

QuantumLab is the interactive 3D companion to this project. It is a teaching tool and is not graded.

- **Where it runs:** in the browser, from GitHub Pages, with no install.
- **What it runs:** the same Python engine as the experiments (`src/qmp`, via Pyodide), so it can never disagree with the report.
- **Style:** it follows `docs/DESIGN_RULES.md` throughout.

## Rooms
1. **Story.** Six chapters, and each one makes you *do* something:
   - flip the coin pairs;
   - drag q and watch links form;
   - join a swap;
   - add middle nodes until the pair washes out;
   - dispatch requests by hand;
   - replay the real single-path vs multipath results.
2. **Arena.** The single-path and multipath networks replay the same real trace side by side.
   - Click any blocked request and ask "why?".
   - Switches turn off the hop limit, the spare-seat rule, or splitting.
3. **Fig. 1 Debugger.** Step through the paper's worked example, including the α₃ discrepancy.
4. **Code Lab.** You write `choose_paths(net, request)` in Python.
   - A referee checks every answer, with plain-English errors.
   - Your rule is scored on 30 seeds against the paper's methods.
   - The Code Lab has three challenges.

## Help ladder

The help ladder applies to every task in every room. Nobody gets stuck, and nobody is forced to take help.

| Level | Button | When it appears | What it does |
|---|---|---|---|
| 0 | Nudge | Automatically, after 40 s without progress or 2 wrong tries | Asks one question that points attention, e.g. "Which road has the fewest seats?" It gives no answer, can be dismissed, and nudges can be switched off. |
| 1 | Hint | On request | Names the idea in kid words, e.g. "A road can carry only as many pairs as its weakest link." |
| 2 | Stronger hint | On request, after level 1 | Gives the student-level idea plus a partial step. The relevant nodes and links are highlighted in the 3D scene. |
| 3 | Show me | On request | Animates the full solution step by step, with forward and back controls. Your attempt stays on screen for comparison. |
| 4 | Do it for me | Always available | Completes the task, explains why in 2 to 3 plain sentences, and offers "Try a similar one" with a new random seed. |

### In the Code Lab
- **Hint 1:** the concept.
- **Hint 2:** pseudocode.
- **Hint 3:** a fill-in-the-blank skeleton, inserted as comments.
- **Show me:** a side-by-side diff against a working solution.
- **Do it for me:** inserts the working code, runs it, and explains each changed line.
- **Targeted hints:** each referee error links to a hint for that mistake. For example, "Roads 1 and 2 both use B-C" links to "Remove the links of road 1 before searching for road 2."

### Progress
- Each task records one of three outcomes: **solved**, **solved with N hints**, or **done for me**.
- Progress is shown as plain text, not badges.
- It is stored only in this browser.

### Authoring
- Hints live in `quantumlab/data/hints.json`, keyed by task id.
- Each level has a kid line and a student line, plus the "where this breaks" note for any analogy.
- A test checks that every task has all five levels and that every hint passes `tools/lint_slop.py`.

### Rules
- Help never blocks the screen and never auto-opens beyond the nudge.
- Help respects reduced-motion settings.
- Press `H` for the next hint level.
- Asking for help never costs the learner a "score".

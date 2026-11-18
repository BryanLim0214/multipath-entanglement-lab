# Design rules (no slop)

Every deliverable must read and look like careful, deliberate human work. That covers the docs, the report, the slides, the figures, and QuantumLab.

These rules are enforced by `tools/lint_slop.py`, which runs in CI and in the tracker, and audited by the hostile reviewer. A rule may only be broken with a same-line waiver, `slop-ok: <reason>`, and every waiver is reviewed.

## Writing

1. **No em dashes.** Use a comma, a colon, parentheses, or a new sentence.
2. **No emoji** anywhere in a deliverable: not as icons, bullets, or decoration.
3. **No hype or filler words.** Banned: delve, seamless, leverage, cutting-edge, game-changing, revolutionary, unlock, unleash, elevate, empower, supercharge, effortless, harness, tapestry, realm, embark, "dive into", "it's important to note", "in today's world", "at the end of the day", "a testament to". Say the number instead.
4. **Specific beats vague.** Every claim carries a number, a file path, or a citation.
5. **Plain words first.** Each idea gets a kid line and a student line. Jargon and equations live only in the expert layer.
6. **Headings use sentence case.** No exclamation marks. No rhetorical "It's not X, it's Y" constructions.

## Visual: QuantumLab and slides

1. **Type.** Atkinson Hyperlegible for text and UI. The Braille Institute designed it for legibility, which matches our "easy to understand" goal. JetBrains Mono for numbers and code.
   - Both fonts are self-hosted as woff2, with no runtime font CDN.
   - Scale: 14 / 16 / 20 / 28 / 40 px.
   - Body line-height 1.5. Lines no longer than 70 characters.
2. **Color comes from tokens only.**
   - The tokens are `--ink`, `--paper`, `--rule`, `--muted`, `--sp`, `--mp`, `--ext`, `--warn` and `--fail`, defined for a light theme and a dark theme.
   - Every text/background pair is at least 4.5:1 contrast, checked rather than assumed.
   - Hierarchy comes from size, weight, and color tokens. **Never use opacity to create hierarchy.** Opacity is only 0 or 1, for show and hide.
3. **Shapes.**
   - The radius scale is 0, 2, and 4 px only.
   - Circles are used only for network nodes.
   - No pills, no chips, no rounded cards.
4. **Surfaces.**
   - Flat, solid backgrounds, separated by 1 px rules.
   - No glassmorphism: no `backdrop-filter` and no translucent panels.
   - No soft drop shadows on cards.
   - No gradients or gradient text.
   - No glow or bloom.
5. **Motion has meaning.**
   - Every animation shows a state change: a link forming, a swap, a request being blocked.
   - Durations are 120 to 400 ms, ease-out.
   - No idle loops.
   - `prefers-reduced-motion` turns off any motion that isn't essential.
6. **Icons.**
   - No decorative icons.
   - Where an icon is needed, use one consistent inline-SVG stroke set (1.5 px), never emoji.
7. **Layout.**
   - 8 px spacing grid, with left-aligned text.
   - One primary action per screen.
   - Real empty, loading, and error states.
   - Works at 360 px wide.
   - Every control is keyboard-reachable, with a visible 2 px solid focus ring.
8. **The 3D scene encodes data only.**
   - Tube thickness shows seats.
   - A single color ramp shows fidelity.
   - Nothing moves without a reason.
   - No starfields, particle backgrounds, lens flare, or floating idle objects.

## Figures (matplotlib)

1. **Always use `figures/qmp.mplstyle`.**
   - STIX serif, to match the IEEEtran report.
   - Okabe-Ito colorblind-safe colors.
   - No top or right spines, and a light grid.
2. **The same method gets the same color everywhere**, in plots, slides, and 3D:

   | Method or item | Color | Line |
   |---|---|---|
   | Multipath | blue `#0072B2` | |
   | Single-path | vermillion `#D55E00` | |
   | SP-SPF baseline | grey `#555555` | |
   | Extension | bluish green `#009E73` | |
   | ILP | | solid |
   | Heuristic | | dashed |
   | Paper values | hollow black markers | labeled "paper (approx., digitized)" |

3. **Confidence intervals are always shown**, as a band or as error bars.
   - Label lines directly when there are 4 or fewer.
   - No 3D charts, pie charts, or dual y-axes.
4. **Export:** PDF (vector) for the report, and PNG at 300 dpi for the slides and the README.

## Polish checklist (every deliverable, every time)

- No placeholder text, lorem ipsum, leftover TODOs, default page titles, or default favicons.
- **Consistency:**
  - Terms come from the glossary.
  - Units and decimal places are consistent. Blocking ratio and CI half-width get 2 decimals.
- **Numbers:** every number in the text is regenerated from `results/`, never typed by hand.
- **Screenshots:** taken at 2x, from the same window size, and cropped to content.
- **Before shipping:** spell-check it, then read it once aloud.

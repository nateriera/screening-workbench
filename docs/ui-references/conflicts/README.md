# Conflicts reference package

**Purpose:** static, synthetic-only reference for the Screening Workbench **Conflicts** tab. It uses the approved Field Notes tokens and 1280×800 Screening shell; it is not an implementation or a claim that the current Tk screen matches. No research-corpus records, abstracts, identifiers, or decisions are included.

## Files

- `reference-conflicts.html` — self-contained HTML source, fixed 1280×800 reference viewport.
- `reference-conflicts.png` — rendered 1× image (1280×800).
- `reference-conflicts@2x.png` — rendered 2× image (2560×1600).
- `reference-conflicts-annotated.png` — 1× render with numbered callouts keyed to this checklist.

Open the HTML directly in Edge. Add `?annotate` to display the numbered callouts. To re-render on Windows, use the installed headless Edge executable with `--window-size=1280,800`; capture once at device scale 1 and once at 2. Do not resize the 1× PNG to create the 2× artifact.

## Numbered must-show checklist

Score one of the three check columns per row: **0** missing · **1** partial · **2** matches. Callout numbers in the annotated image map to the corresponding rows.

| # | Must show | Check 0 | Check 1 | Check 2 | Evidence / notes |
|---:|---|:---:|:---:|:---:|---|
| 1 | Queue lists only open conflicts and selected record ID | ☐ | ☐ | ☐ |  |
| 2 | Record details use clearly synthetic content | ☐ | ☐ | ☐ |  |
| 3 | Both final decisions and timestamps are visible only in unblinded view | ☐ | ☐ | ☐ |  |
| 4 | Each synthetic exclusion reason is visible with its vote | ☐ | ☐ | ☐ |  |
| 5 | Final Include/Exclude control is explicit and mutually exclusive | ☐ | ☐ | ☐ |  |
| 6 | Resolution note is required and its empty state is visible | ☐ | ☐ | ☐ |  |
| 7 | Owner authorization and blind-off requirement are stated | ☐ | ☐ | ☐ |  |
| 8 | Blind-on locked preview conceals decisions, reasons, and identities | ☐ | ☐ | ☐ |  |
| 9 | Save action shows append-only audit semantics | ☐ | ☐ | ☐ |  |
| 10 | Keyboard focus, logical reading order, and status message are specified | ☐ | ☐ | ☐ |  |
| 11 | Text labels—not color alone—identify decisions, locks, and pending state | ☐ | ☐ | ☐ |  |
| 12 | No cross-reviewer conflict detail is available through the blind-on state | ☐ | ☐ | ☐ |  |
| 13 | κ readout visible only in unblinded view; shows value, label, agreement, n | ☐ | ☐ | ☐ |  |

## Tk feasibility notes

- Represent queue rows with a Treeview; load details only after the blind-mode authorization check succeeds.
- Render the two decision cards as labeled frames with timestamps and reasons; preserve a predictable screen-reader reading order.
- Use a ttk Combobox or paired Radiobuttons for final outcome and a Text widget with validation for the required note. Disable Save until both are valid.
- The locked-while-blind state must be enforced before widgets/data are populated—not implemented as a translucent overlay over sensitive details. Announce lock/unlock status without moving focus.
- The κ strip is one compact ttk.Frame of Labels bound to `screening.kappa_readout(conn, is_blind=...)`: render nothing (not a zero/blank row) when it returns None, and recompute on every Conflicts-tab refresh rather than caching — it is cheap (one SQL join over current votes) and must never go stale after an undo or a new vote.

## Non-negotiable gates

- All visual sample content is synthetic and visibly marked as a reference; never insert real review records into this package.
- Keyboard operation, visible focus, contrast, non-color state cues, and status announcements remain requirements even if a static image cannot demonstrate each behavior.
- Blind mode is enforced at the data/query boundary. Do not render another reviewer’s vote, reason, or decision-derived data in a blinded view. The Conflicts package includes a separate, explicitly locked blind-on state.
- A screenshot or checklist score is not evidence that the live app implements the behavior.

## Round: Directive A — Cohen's κ (2026-10-07)

Added region 13 only, per the "one region per iteration" rule; items 1-12 were not touched and their prior 24/24 (12 items × 2) approved score is unchanged.

- **Computation:** `screening_workbench.screening.cohens_kappa()` — unweighted Cohen's κ over current title/abstract votes, intersecting (not unioning) the two reviewers' decided-occurrence sets; 12 tests in `tests/test_screening.py`, including a published 3×3 worked-example fixture (turtle-rating table, N=36, κ≈0.45 — see the test docstring for the citation), exact perfect-agreement (κ=1.0) and exact chance-level (κ=0.0, by construction, not simulation) fixtures, the single-reviewer "n/a" case, exclusion of single-reviewer-decided records from n, and recomputation after an `undo_last_vote` call.
- **Blind gate:** `screening_workbench.screening.kappa_readout(conn, is_blind=...)` returns `None` unconditionally while blind (no owner/auditor exception, matching the Conflicts queue's own blind-off requirement) — covered by `test_kappa_readout_absent_while_blind`.
- **Placement:** a compact `role="status"` strip at the top of the "Review evidence" panel, below the panel header, showing κ value, Landis-Koch label, raw % agreement, and n — exactly the four items item 13 requires.
- **Self-score — item 13:** 2 (matches). Evidence: `reference-conflicts.png` / `-annotated.png`, callout 13. The strip is legible, not clipped, does not overlap the "Final title/abstract decisions" block below it, and is positioned only in the already-unblinded framing this reference renders (the page's own `Blind screening: OFF` header chip establishes that framing — the adjacent "Blind-review gate" panel's locked preview is the existing visual evidence that the whole Review Evidence panel, κ strip included, is unavailable while blind).
- **Not touched this round:** `app.py` (per Directive A's explicit sequencing: score the reference first, wire the app later); the other five tab packages (unaffected, still 12/12 each).

## Loop rules — mandatory for every iteration

- Score each numbered item **0 = missing, 1 = partial, 2 = matches**. Use exactly one score per item and record evidence in the notes column.
- Select the lowest-scoring, lowest-cost region; change **one region per iteration**, then render and re-score.
- Never accept a pass that regresses an item that previously scored 2. Cinder’s independent score is authoritative when it disagrees with the author’s self-score.
- **Accessibility and blind-review integrity are non-negotiable.** Never trade keyboard access, focus visibility, contrast, semantic announcements, required reasons, or reviewer isolation for visual similarity.
- These are static design references. The original six-reference review is complete; later UI changes require separate verification.


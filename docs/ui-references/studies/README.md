# Studies reference package

**Purpose:** static, synthetic-only reference for the Screening Workbench **Studies** tab. It uses the approved Field Notes tokens and 1280×800 Screening shell; it is not an implementation or a claim that the current Tk screen matches. No research-corpus records, abstracts, identifiers, or decisions are included.

## Files

- `reference-studies.html` — self-contained HTML source, fixed 1280×800 reference viewport.
- `reference-studies.png` — rendered 1× image (1280×800).
- `reference-studies@2x.png` — rendered 2× image (2560×1600).
- `reference-studies-annotated.png` — 1× render with numbered callouts keyed to this checklist.

Open the HTML directly in Edge. Add `?annotate` to display the numbered callouts. To re-render on Windows, use the installed headless Edge executable with `--window-size=1280,800`; capture once at device scale 1 and once at 2. Do not resize the 1× PNG to create the 2× artifact.

## Numbered must-show checklist

Score one of the three check columns per row: **0** missing · **1** partial · **2** matches. Callout numbers in the annotated image map to the corresponding rows.

| # | Must show | Check 0 | Check 1 | Check 2 | Evidence / notes |
|---:|---|:---:|:---:|:---:|---|
| 1 | Study groups and report counts are visible | ☐ | ☐ | ☐ |  |
| 2 | Reports are nested/grouped under the selected study | ☐ | ☐ | ☐ |  |
| 3 | Study and report are separate entities and counts | ☐ | ☐ | ☐ |  |
| 4 | Canonical occurrence choice is visible for selected report | ☐ | ☐ | ☐ |  |
| 5 | All linked source occurrences remain listed as provenance | ☐ | ☐ | ☐ |  |
| 6 | Selected branch/source is explicit and synthetic | ☐ | ☐ | ☐ |  |
| 7 | Study decision state and rationale requirement are shown | ☐ | ☐ | ☐ |  |
| 8 | Linking alone does not imply a study is included | ☐ | ☐ | ☐ |  |
| 9 | Pending retrieval or unresolved links remain visible | ☐ | ☐ | ☐ |  |
| 10 | Blind mode hides reviewer votes and decision-derived detail | ☐ | ☐ | ☐ |  |
| 11 | Keyboard-operable group, link, and canonical-selection controls | ☐ | ☐ | ☐ |  |
| 12 | Labels and state text remain understandable without color | ☐ | ☐ | ☐ |  |

## Tk feasibility notes

- Use a Treeview parent/child hierarchy for study → report groups, with stable study/report IDs as item IDs.
- Show source occurrences in a detail pane for the selected report; use Radiobuttons for the single canonical occurrence/branch selection.
- Study decision and report progression are separate controls and events; do not infer one from the other.
- Use accessible text labels for link/unlink and pending/conflict states. Apply blind checks before retrieving reviewer-specific fields; keep the table’s sort/search behavior stable.

## Non-negotiable gates

- All visual sample content is synthetic and visibly marked as a reference; never insert real review records into this package.
- Keyboard operation, visible focus, contrast, non-color state cues, and status announcements remain requirements even if a static image cannot demonstrate each behavior.
- Blind mode is enforced at the data/query boundary. Do not render another reviewer’s vote, reason, or decision-derived data in a blinded view. The Conflicts package includes a separate, explicitly locked blind-on state.
- A screenshot or checklist score is not evidence that the live app implements the behavior.

## Loop rules — mandatory for every iteration

- Score each numbered item **0 = missing, 1 = partial, 2 = matches**. Use exactly one score per item and record evidence in the notes column.
- Select the lowest-scoring, lowest-cost region; change **one region per iteration**, then render and re-score.
- Never accept a pass that regresses an item that previously scored 2. Cinder’s independent score is authoritative when it disagrees with the author’s self-score.
- **Accessibility and blind-review integrity are non-negotiable.** Never trade keyboard access, focus visibility, contrast, semantic announcements, required reasons, or reviewer isolation for visual similarity.
- These are static design references. The original six-reference review is complete; later UI changes require separate verification.


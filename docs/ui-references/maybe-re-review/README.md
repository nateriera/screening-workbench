# Maybe re-review reference package

**Purpose:** static, synthetic-only reference for the Screening Workbench **Maybe re-review** tab. It uses the approved Field Notes tokens and 1280×800 Screening shell; it is not an implementation or a claim that the current Tk screen matches. No research-corpus records, abstracts, identifiers, or decisions are included.

## Files

- `reference-maybe-re-review.html` — self-contained HTML source, fixed 1280×800 reference viewport.
- `reference-maybe-re-review.png` — rendered 1× image (1280×800).
- `reference-maybe-re-review@2x.png` — rendered 2× image (2560×1600).
- `reference-maybe-re-review-annotated.png` — 1× render with numbered callouts keyed to this checklist.

Open the HTML directly in Edge. Add `?annotate` to display the numbered callouts. To re-render on Windows, use the installed headless Edge executable with `--window-size=1280,800`; capture once at device scale 1 and once at 2. Do not resize the 1× PNG to create the 2× artifact.

## Numbered must-show checklist

Score one of the three check columns per row: **0** missing · **1** partial · **2** matches. Callout numbers in the annotated image map to the corresponding rows.

| # | Must show | Check 0 | Check 1 | Check 2 | Evidence / notes |
|---:|---|:---:|:---:|:---:|---|
| 1 | Queue title states that it contains the current reviewer’s own maybe-votes | ☐ | ☐ | ☐ |  |
| 2 | Only the current reviewer’s own records/votes are listed | ☐ | ☐ | ☐ |  |
| 3 | No other reviewer’s vote, reason, title, or count is exposed | ☐ | ☐ | ☐ |  |
| 4 | Selected record is clearly marked synthetic | ☐ | ☐ | ☐ |  |
| 5 | Current own Maybe decision and timestamp are visible | ☐ | ☐ | ☐ |  |
| 6 | Include/Maybe/Exclude re-decision controls are present | ☐ | ☐ | ☐ |  |
| 7 | Exclude requires one project reason before saving | ☐ | ☐ | ☐ |  |
| 8 | Final Include/Exclude removes item from current maybe queue | ☐ | ☐ | ☐ |  |
| 9 | Search, counts, and status are computed after own-vote filtering | ☐ | ☐ | ☐ |  |
| 10 | Keyboard controls, focus, and status announcement are visible | ☐ | ☐ | ☐ |  |
| 11 | All states have text labels and adequate contrast | ☐ | ☐ | ☐ |  |
| 12 | Blind isolation is presented as a non-negotiable gate | ☐ | ☐ | ☐ |  |

## Tk feasibility notes

- Query the current reviewer’s own active Maybe vote set before populating the queue, search index, badge, or status text. Do not fetch other reviewers’ vote rows for display.
- Use Treeview for the queue and a read-only Text pane for record content; stable occurrence IDs belong in item data, not row indexes.
- Reuse the Screening decision bar and reason taxonomy; validate one exclusion reason before commit. On Include/Exclude, refresh from the current reviewer’s own queue and announce the result.
- Support keyboard navigation while preventing global single-key shortcuts from firing inside editable controls. Keep the owner/blind scope visible without exposing another reviewer’s decisions.

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


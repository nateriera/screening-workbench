# PRISMA & audit reference package

**Purpose:** static, synthetic-only reference for the Screening Workbench **PRISMA & audit** tab. It uses the approved Field Notes tokens and 1280×800 Screening shell; it is not an implementation or a claim that the current Tk screen matches. No research-corpus records, abstracts, identifiers, or decisions are included.

## Files

- `reference-prisma-audit.html` — self-contained HTML source, fixed 1280×800 reference viewport.
- `reference-prisma-audit.png` — rendered 1× image (1280×800).
- `reference-prisma-audit@2x.png` — rendered 2× image (2560×1600).
- `reference-prisma-audit-annotated.png` — 1× render with numbered callouts keyed to this checklist.

Open the HTML directly in Edge. Add `?annotate` to display the numbered callouts. To re-render on Windows, use the installed headless Edge executable with `--window-size=1280,800`; capture once at device scale 1 and once at 2. Do not resize the 1× PNG to create the 2× artifact.

## Numbered must-show checklist

Score one of the three check columns per row: **0** missing · **1** partial · **2** matches. Callout numbers in the annotated image map to the corresponding rows.

| # | Must show | Check 0 | Check 1 | Check 2 | Evidence / notes |
|---:|---|:---:|:---:|:---:|---|
| 1 | View is clearly labeled synthetic and not a live project export | ☐ | ☐ | ☐ |  |
| 2 | Flow diagram is generated from one named immutable snapshot | ☐ | ☐ | ☐ |  |
| 3 | Identification/removal/screening equations reconcile exactly | ☐ | ☐ | ☐ |  |
| 4 | Report retrieval and assessment counts reconcile exactly | ☐ | ☐ | ☐ |  |
| 5 | Study and included-report counts use distinct entity IDs | ☐ | ☐ | ☐ |  |
| 6 | Append-only audit log shows sequence, actor, timestamp, and event type | ☐ | ☐ | ☐ |  |
| 7 | Audit access scope is explicit; no unauthorized reviewer votes are shown | ☐ | ☐ | ☐ |  |
| 8 | Watermark and export status are visible | ☐ | ☐ | ☐ |  |
| 9 | Counts and links remain legible in grayscale/print and at 200% zoom | ☐ | ☐ | ☐ |  |
| 10 | Diagram has title/description and text-accessible labels | ☐ | ☐ | ☐ |  |
| 11 | Keyboard access and focus remain visible in every control | ☐ | ☐ | ☐ |  |
| 12 | Incomplete/pending states would be disclosed rather than silently treated as terminal | ☐ | ☐ | ☐ |  |

## Tk feasibility notes

- Draw the flow on a scrollable Canvas or render the same snapshot to local SVG; each box must have a text label and count, not a color-coded meaning.
- Keep the audit list in a read-only Treeview sorted by sequence; expose sequence, time, actor, and event type as separate labeled columns.
- Bind diagram and log to one snapshot watermark; never calculate visual totals independently from the snapshot model.
- For blind mode, gate full audit detail by owner/auditor scope before loading rows. Ensure high-contrast/print styles preserve arrows, borders, and text.

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


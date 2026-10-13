# Duplicates reference package

**Purpose:** static, synthetic-only reference for the Screening Workbench **Duplicates** tab. It uses the approved Field Notes tokens and 1280×800 Screening shell; it is not an implementation or a claim that the current Tk screen matches. No research-corpus records, abstracts, identifiers, or decisions are included.

## Files

- `reference-duplicates.html` — self-contained HTML source, fixed 1280×800 reference viewport.
- `reference-duplicates.png` — rendered 1× image (1280×800).
- `reference-duplicates@2x.png` — rendered 2× image (2560×1600).
- `reference-duplicates-annotated.png` — 1× render with numbered callouts keyed to this checklist.

Open the HTML directly in Edge. Add `?annotate` to display the numbered callouts. To re-render on Windows, use the installed headless Edge executable with `--window-size=1280,800`; capture once at device scale 1 and once at 2. Do not resize the 1× PNG to create the 2× artifact.

## Numbered must-show checklist

Score one of the three check columns per row: **0** missing · **1** partial · **2** matches. Callout numbers in the annotated image map to the corresponding rows.

| # | Must show | Check 0 | Check 1 | Check 2 | Evidence / notes |
|---:|---|:---:|:---:|:---:|---|
| 1 | Tab/header identifies Duplicates and current queue count | ☐ | ☐ | ☐ |  |
| 2 | Open candidate pair remains active until a reviewer resolves it | ☐ | ☐ | ☐ |  |
| 3 | Two source occurrences are shown side by side with stable synthetic IDs | ☐ | ☐ | ☐ |  |
| 4 | Every differing raw field is highlighted and labeled in text | ☐ | ☐ | ☐ |  |
| 5 | Match reasons, score, rule version, and provenance are inspectable | ☐ | ☐ | ☐ |  |
| 6 | Exactly one survivor is visibly selected before merge | ☐ | ☐ | ☐ |  |
| 7 | Merge and Keep separate are distinct, explicit actions | ☐ | ☐ | ☐ |  |
| 8 | Confirmation previews survivor and affected occurrence IDs | ☐ | ☐ | ☐ |  |
| 9 | Reversibility and append-only history are stated near the action | ☐ | ☐ | ☐ |  |
| 10 | No reviewer vote or identity is shown while blind | ☐ | ☐ | ☐ |  |
| 11 | Keyboard order and focus state are visible and operable | ☐ | ☐ | ☐ |  |
| 12 | Difference and decision states are conveyed without color alone | ☐ | ☐ | ☐ |  |

## Tk feasibility notes

- Use a Treeview for the candidate queue with stable candidate IDs, not row positions.
- Use two aligned ttk Frames or a read-only Text/Canvas table for field comparison; add text labels (“Difference”) plus tint, never color only.
- Use Radiobuttons for survivor choice and a confirmation dialog listing survivor and absorbed IDs. Keep source strings in read-only widgets; tags can highlight differing rows.
- Undo/reversibility is a status/history item, not an auto-reverse timer. Keep the comparison readable at 200% zoom and ensure focus returns to the triggering control after dialog close.

## Non-negotiable gates

- All visual sample content is synthetic and visibly marked as a reference; never insert real review records into this package.
- Keyboard operation, visible focus, contrast, non-color state cues, and status announcements remain requirements even if a static image cannot demonstrate each behavior.
- Blind mode is enforced at the data/query boundary. Do not render another reviewer’s vote, reason, or decision-derived data in a blinded view. The Conflicts package includes a separate, explicitly locked blind-on state.
- A screenshot or checklist score is not evidence that the live app implements the behavior.

## Round: item 8 — render the merge-confirmation dialog (2026-10-07)

Cinder scored the package 143/144 (conditional approval), with the single
deduction on item 8: "the merge-confirmation behavior is described but the
dialog state isn't rendered." Fixed per Cinder's exact spec, one region
only — items 1-7 and 9-12 were not touched and their approved scores are
unchanged.

- **Rendered:** a modal dialog (`role="alertdialog"`, `aria-modal="true"`,
  labelled/described via `aria-labelledby`/`aria-describedby`) over a
  dimmed backdrop, title "Confirm merge", naming the survivor
  (`Occurrence A · SYN-021-A`) and the absorbed occurrence
  (`Occurrence B · SYN-021-B`) in two explicit rows, plus the existing
  reversibility sentence, and explicit `Cancel`/`Confirm merge` actions.
- **Callout 8** moved from the right-panel note text (now superseded) to
  the dialog itself, pointing at the `Confirm merge` button.
- **Not touched this round:** `app.py` (still gated on this review); items
  1-7 and 9-12 of this package; the other five tab packages.

## Loop rules — mandatory for every iteration

- Score each numbered item **0 = missing, 1 = partial, 2 = matches**. Use exactly one score per item and record evidence in the notes column.
- Select the lowest-scoring, lowest-cost region; change **one region per iteration**, then render and re-score.
- Never accept a pass that regresses an item that previously scored 2. Cinder’s independent score is authoritative when it disagrees with the author’s self-score.
- **Accessibility and blind-review integrity are non-negotiable.** Never trade keyboard access, focus visibility, contrast, semantic announcements, required reasons, or reviewer isolation for visual similarity.
- These are static design references. The original six-reference review is complete; later UI changes require separate verification.


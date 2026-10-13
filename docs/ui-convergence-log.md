# App.py UI convergence log (live app vs. approved reference packages)

Tracks `src/screening_workbench/app.py`'s real screens against the six packages under
`docs/ui-references/`, now that Cinder has reviewed all six (143/144,
then 144/144 after the Duplicates item-8 fix). Same discipline as the
reference-authoring loop: score every checklist item **0 = missing, 1 =
partial, 2 = matches**, fix the lowest-scoring/lowest-cost region, change
**one region per iteration**, re-capture a real screenshot of the running
app (not the static reference), re-score, never regress an item that was
already a 2. A checklist score here is about the live Tk app; it never
substitutes for `pytest tests/` passing, which remains the hard gate.

Capture method: seed a real `ScreeningWorkbenchApp` instance with synthetic data via
the domain modules (same calls `tests/test_app.py` uses), launch it,
force real OS foreground focus (`win32gui`/`AttachThreadInput` -- see the
`desktop-app-ui-reference-convergence` skill), and screenshot the
window's **client area only** (`GetClientRect`, not the OS title bar) so
pixel coordinates compare directly against the reference PNGs' 1280x800
content-only framing. Scratch capture/seed scripts live under the
session's scratch directory, not in this repo.

## Duplicates — baseline read (2026-10-07, before this round)

Seeded one real fuzzy cluster (2 occurrences, title-near-match + same
first author + shared year, score 0.95) and captured the live
Duplicates tab (`_build_duplicates_tab`/`_render_dup_cluster`).

| # | Must show | Score | Evidence |
|---:|---|:---:|---|
| 1 | Tab/header identifies Duplicates and current queue count | 2 | Tab reads "Duplicates (1)". |
| 2 | Open candidate pair remains active until a reviewer resolves it | 0 | No queue-semantics note anywhere; behavior is correct (`dedup.reviewer_keep_separate_group` exists) but unstated in the UI. |
| 3 | Two source occurrences shown side by side with stable synthetic IDs | 0 | The compare pane shows only `match (score 0.95, title_similarity, same_first_author, shared_year)` -- no field table, no occurrence IDs at all. |
| 4 | Every differing raw field is highlighted and labeled in text | 0 | No field-level comparison exists yet. |
| 5 | Match reasons, score, rule version, and provenance are inspectable | 1 | Score and match reasons are shown; rule version and batch/source provenance are not. |
| 6 | Exactly one survivor is visibly selected before merge | 1 | A Listbox lets you pick one, but nothing is pre-selected/visibly marked as "the" survivor before that choice. |
| 7 | Merge and Keep separate are distinct, explicit actions | 2 | "Merge cluster into selected survivor" / "Keep all separate" buttons. |
| 8 | Confirmation previews survivor and affected occurrence IDs | 0 | `_dup_merge_cluster` merged immediately with zero confirmation. |
| 9 | Reversibility and append-only history are stated near the action | 0 | Not stated anywhere in the tab. |
| 10 | No reviewer vote or identity is shown while blind | 2 | Nothing vote-shaped is rendered here regardless; blind chip correctly reads ON. |
| 11 | Keyboard order and focus state are visible and operable | 1 | Standard Tk tab order works; no explicit focus-ring styling verified live yet. |
| 12 | Difference and decision states are conveyed without color alone | 0 | No diff cues exist yet (follows from #3/#4). |

**Baseline: 9/24 (items scored 0/1/2, 12 items x 2 max).**

## Round 1 — item 8: real merge-confirmation dialog (2026-10-07)

Lowest-cost, highest-value gap: item 8 was flagged by Cinder on the
*reference* mockup too (that fix landed separately, see
`docs/ui-references/duplicates/README.md`'s round notes) -- this round
closes the equivalent gap in the real app, which was worse: no
confirmation at all, not just an unrendered one.

- **Change:** `_dup_merge_cluster` in `src/screening_workbench/app.py` now builds the
  survivor's and every absorbed occurrence's title + ID, and calls
  `messagebox.askyesno("Confirm merge", ...)` naming both and stating
  the action is reversible, before calling `dedup.reviewer_merge_group`.
  Declining leaves the cluster and active-occurrence count untouched.
- **Tests:** `tests/test_app.py` --
  `test_duplicates_tab_merge_cancelled_in_confirmation_does_nothing`
  (decline is a real gate, not cosmetic) and
  `test_duplicates_tab_merge_confirmation_names_survivor_and_absorbed`
  (the dialog message contains both occurrence IDs and the word
  "reversible"). The two pre-existing merge-flow tests were updated to
  monkeypatch `messagebox.askyesno` to confirm, matching this file's
  established dialog-mocking pattern. Full suite: 234/234.
- **Live verification:** re-seeded the same cluster, drove real OS-level
  mouse clicks (not `event_generate`) through the running window --
  selecting a survivor then clicking "Merge cluster into selected
  survivor" -- and confirmed the merge only completed after the real
  native dialog was answered; the end state (Duplicates count 0,
  one fewer active occurrence) matches an affirmed confirmation.
- **New score -- item 8: 2.** Items 1, 7, 10 unchanged at 2 (not
  touched). Items 2-6, 9, 11-12 unchanged at their baseline scores --
  **not** touched this round, queued below.

**Running total: 11/24.**

## Round 2 — items 2 and 9: queue-semantics and reversibility notes (2026-10-07)

Both are one-line text additions (same cost class), done together as
one region since they're the same fix pattern applied to two items
rather than two independent changes to different app behavior.

- **Change:** `_build_duplicates_tab` in `src/screening_workbench/app.py` gained two
  `tk.Label`-in-`tk.Frame` info-style notes (same `TOKENS["info_soft"]`
  idiom already used for the blind-mode explainer callout elsewhere in
  the file): one above the candidate list stating candidates remain an
  explicit manual queue that never changes screening/PRISMA counts on
  its own (item 2), one below the action buttons stating Merge is
  reversible via `dedup.undo_merge` and both actions are append-only
  events (item 9) -- worded precisely: Keep separate has nothing to
  restore since it never deactivates anything, so the note does not
  overclaim an undo path that doesn't exist for it.
- **Tests:** `test_duplicates_tab_states_queue_and_reversibility_semantics`
  asserts both note strings directly off the new `dup_queue_note_label`/
  `dup_reversibility_note_label` widgets. Full suite: 235/235.
- **Live verification:** re-captured the live tab; both notes render
  legibly, left-aligned, non-overlapping, no clipping (full-width
  `wraplength=1200`).
- **New scores -- items 2 and 9: 2 each** (were 0). Items 1, 7, 8, 10
  unchanged at 2; items 3-6, 11-12 unchanged at baseline -- not touched.

**Running total: 15/24.**

## Round 3 — items 3/4/5/6/12: real field-by-field comparison table (2026-10-07)

Per Nate's explicit direction: one region covering all five items
together, since they're one root gap in one function
(`_render_dup_cluster`) and splitting would just churn the same code
across rounds. Bound held: compare-pane only, no tab-level redesign.

- **Change:** `_render_dup_cluster` in `src/screening_workbench/app.py` was rewritten
  from a single match-reason line to a real comparison: a "MATCH
  EVIDENCE" section (score, reasons, **rule version** via
  `dedup.RULE_VERSION`) for every pairwise candidate in the cluster; an
  "OCCURRENCES AND PROVENANCE" section listing each occurrence's full,
  stable ID with its batch/row/source via a new `_dup_provenance()`
  query; and a "FIELD COMPARISON" table (title/authors/year/journal/doi,
  one column per occurrence, header row showing the IDs) where any
  field whose values differ across occurrences gets an explicit `^
  Difference -- ...` text line directly under it, in addition to (not
  instead of) a `dup_diff` background tag -- satisfying "without color
  alone" literally. `dup_compare_text` gained monospace font, `wrap=
  "none"`, and a horizontal scrollbar scoped to its own sub-frame (not
  the whole tab) so long IDs/titles don't force tab-level layout
  changes. Column width is computed from the longest actual value
  (IDs included) so nothing truncates or runs into the next column.
  `_render_dup_cluster` also now pre-selects the first survivor
  (`dup_survivor_list.selection_set(0)`) so exactly one is visibly
  selected as soon as a cluster opens, not only after a manual click.
- **Tests:** `test_duplicates_tab_compare_pane_shows_field_table_and_provenance`
  asserts both occurrence IDs, the "Difference" label, non-differing
  fields still rendered, score/rule-version/provenance text, and the
  pre-selected survivor, off real rendered widget content -- not a
  cosmetic string match. (Caught and fixed a test-data bug of my own
  along the way: an unescaped comma in a synthetic author string broke
  the CSV fixture silently, producing a zero-occurrence false pass
  until a `len(occ_ids) == 2` sanity assertion was added.) Full suite:
  236/236.
- **Live verification:** re-seeded and captured the live tab three
  times while iterating column-width math -- first pass had occurrence
  IDs and long titles running together with no gap because the
  column width was computed from IDs only, not the longest cell value;
  fixed by computing width from both. Final capture: IDs aligned,
  Title/Journal rows show `Difference` only where values actually
  differ, Authors/Year show none, horizontal scrollbar present and
  functional, survivor pre-selected, nothing clipped.
- **New scores -- items 3, 4, 5, 6, 12: 2 each** (were 0, 0, 1, 1, 0).
  Items 1, 2, 7, 8, 9, 10 unchanged at 2 (not touched this round).

**Running total: 23/24** (items 1,2,3,4,5,6,7,8,9,10,12 are each 2 = 22;
item 11 remains at 1 = 23/24 pending its own round).

## Round 4 — item 11: keyboard order and focus, empirically verified (2026-10-07)

Per the skill's "a static legend is not evidence" discipline: this
required a real OS-level keyboard Tab-through of the live tab (not
`event_generate`, not reading the code and assuming Tk's default
theme renders focus), because the gap at baseline was "unverified,"
not necessarily "broken."

- **Method:** foregrounded the running window, clicked into
  `dup_list` to give the tab a known starting focus, then sent real
  `win32api.keybd_event(VK_TAB, ...)` presses one at a time,
  screenshotting after each.
- **Findings, each confirmed with a zoomed crop:**
  - Tab 1: focus moves from `dup_list` to `dup_survivor_list` --
    Tk's native dotted focus rectangle appears around the active
    (pre-selected) row's text.
  - Tab 2: focus moves to the "Merge cluster into selected survivor"
    button -- visible dotted inner focus rectangle (confirmed against
    "Keep all separate", which has none at this point, side by side).
  - Tab 3: focus moves to "Keep all separate" -- same dotted
    rectangle, now on this button instead.
  - Tab 4: focus leaves the tab's own controls for the header's
    "Export package..." button -- a window-wide tab-order property
    (header widgets were created before the notebook, so Tk's default
    traversal order reaches them next), not specific to Duplicates;
    noted as a pre-existing, out-of-scope gap below, not blocking
    this item.
  - **Real activation, not just visual:** from the Merge-button-focused
    state, a real `VK_SPACE` keypress activated the button and opened
    the actual "Confirm merge" dialog (screenshotted) -- the focus
    ring is not cosmetic; it drives real keyboard operation.
- **No code change was needed.** Tk's "clam" theme (set via `ttk.Style`
  in `_apply_style`) already renders visible per-widget focus
  indicators by default for `ttk.Button` and `tk.Listbox`'s active
  item; the gap at baseline was that this had never been verified
  live, only assumed from "standard Tk tab order works."
- **New score -- item 11: 2** (was 1, unverified). All 12 Duplicates
  items now score 2.

**Duplicates tab: 24/24. Closed per Nate's direction.**

Noted, not fixed this round (out of this item's scope, window-wide):
keyboard Tab order does not reach the notebook's own tab strip, so a
keyboard-only user cannot switch tabs via Tab/Shift-Tab -- only via
mouse or (if bound) an accelerator. This affects every tab equally,
not just Duplicates; worth a dedicated pass if raised as its own item.

## Queued for future rounds (lowest-cost next, not yet started)

Duplicates is fully converged (24/24); no further rounds queued for it.

# Conflicts (13 items, κ strip already at 13/13 going in -- see Directive A)

## Baseline read (2026-10-07, before this tab's first round)

Seeded one conflict (owner: include vs revB: exclude, with reason) plus
one agreed-upon record (for a non-trivial κ denominator) and captured
the live Conflicts tab.

| # | Must show | Score | Evidence |
|---:|---|:---:|---|
| 1 | Queue lists only open conflicts and selected record ID | 1 | Title shown in the queue row; no occurrence ID visible anywhere in the tab at baseline. |
| 2 | Record details use clearly synthetic content (-> live: record metadata shown) | 1 | The queue row shows the title; the detail pane itself showed ONLY vote lines, no record content at all. |
| 3 | Both final decisions and timestamps are visible only in unblinded view | 1 | Decisions shown; vote timestamps (`screen_votes.created_at`, already in the data) were not rendered anywhere. |
| 4 | Each synthetic exclusion reason is visible with its vote | 2 | `revB: exclude (Wrong population)` -- correct. |
| 5 | Final Include/Exclude control is explicit and mutually exclusive | 2 | Two explicit buttons; clicking one immediately resolves, no ambiguous dual state. |
| 6 | Resolution note is required and its empty state is visible | 1 | Required and enforced (`resolve_conflict` raises, UI shows an error), but the empty state isn't visually distinguished before submission. |
| 7 | Owner authorization and blind-off requirement are stated | 0 | Blind-off is enforced/stated via the lock label; owner authorization was **neither stated nor enforced** -- `screening.resolve_conflict` has no notion of project ownership and the UI never checked it, so any reviewer_id driving the app could resolve conflicts. A real correctness gap, not just cosmetic. |
| 8 | Blind-on locked preview conceals decisions, reasons, identities | 2 | Confirmed structurally (queue not populated while blind), unchanged from prior work. |
| 9 | Save action shows append-only audit semantics | 0 | Not stated anywhere near the action. |
| 10 | Keyboard focus, logical reading order, and status message are specified | 1 | `_set_status` fires after resolve; keyboard/focus not yet empirically verified for this tab. |
| 11 | Text labels -- not color alone -- identify decisions, locks, pending state | 2 | No color is used in the detail pane at all; trivially satisfied. |
| 12 | No cross-reviewer conflict detail is available through the blind-on state | 2 | Whole queue is disabled while blind. |
| 13 | κ readout visible only in unblinded view; shows value, label, agreement, n | 2 | Confirmed live: "Agreement (Cohen's κ): κ = 0.00 · Slight · 50% raw agreement · n = 2 double-decided". |

**Baseline: 17/26.**

## Directive F — Phase 2 Conflicts card-shell migration (commit 8c0de15, 2026-10-10)

- **Diff:** moved the existing queue, selected-record evidence/resolution, and blind/owner/audit content into three aligned cards; preserved the existing notebook order, conflict handlers, vote reads, κ, and packet commands. Added a fixed-height scrollable queue showing stable occurrence IDs and local Up/Down guidance/navigation; clarified that global I/M/E, reason, J/K and search shortcuts belong to Screening. Resolution actions require a selected open conflict, owner, blind OFF, and a non-whitespace note. The blind transition explicitly clears the Listbox before disabling it and clears the prior detail text; it hides κ and disables resolution, packet export, and vote merge.
- **Tests/evidence:** added shell/control hierarchy and blind-transition regression tests, two-open-conflict arrow-navigation coverage, and selected/note action-state coverage. Fresh `conflicts-selected.png` and `conflicts.png` are real 1280×800 synthetic foreground captures; evidence folder contains PNGs only and capture databases were removed. The selected capture shows two disagreement rows, selected details/votes/timestamps, κ and action area; the locked capture shows the LOCK badge and no decision detail.
- **Verification:** focused Conflicts migration/blind-state/owner/detail/queue/note/arrow tests: **10 passed**; full suite: **338 passed**; `py_compile` and `git diff --check` clean. No checklist rescore is claimed.

## Directive F — Conflicts blind-state copy and disabled-action visual correction (commit b11c4c3, 2026-10-10)

- **Diff:** replaced blind-state “Queue empty” wording with “Queue locked · conflicts are unavailable until blind mode is off.” and added a second in-queue message that records are concealed. Added explicit ttk disabled foreground/background maps for the final Include/Exclude actions, distinguishing unavailable controls from active actions.
- **Evidence/verification:** regenerated the synthetic 1280×800 blind-ON capture. It shows LOCK, lock/concealment copy with no reviewer data, and muted Resolve controls. Focused Conflicts suite: **10 passed**; full suite: **338 passed**; `py_compile` and `git diff --check` clean. No checklist score is claimed.

## Directive F — Conflicts reviewer-packet control blind gate (fix-up)

- **Data-layer finding:** `packets.export_packet` selects the active record set and source metadata but never reads `screen_votes`; `tests/test_packets.py::test_export_packet_leakage_scan_zero_vote_data` checks that vote identifiers/reasons are absent. That does not authorize the UI action during blind mode: Screening Workbench’s application-level isolation ruling covers exports, and Directive B places “Export reviewer packet…” in the unblinded Conflicts view. This is a blind-mode UI-gating gap, not evidence that packet JSON contains vote data. The packet API/schema remains unchanged.
- **Fix:** keep reviewer-packet export available to any reviewer once unblinded (existing Directive B behavior); disable it in blind mode and re-check `roles.is_blind` in the action before opening the save dialog. Vote-file merge stays disabled while blind and owner-only/unblinded in both UI and `packets.merge_votes`.
- **Verification:** the blind-toggle regression asserts packet export is available in the unblinded empty state, both packet controls become disabled while blind, a direct packet-export call refuses without opening a save dialog, and both controls are re-enabled after unblinding; existing packet round-trip and leakage tests remain green. Focused packet/Conflicts tests: 10 passed; full suite: 338 passed; `py_compile` and `git diff --check` clean. No checklist rescore is claimed.


Grouped as one region: items 2, 3, 7, and 9 are all "the detail pane
and the area right below it don't show enough" -- one area of the
screen, `_render_conflict` plus a new info note next to the resolve
buttons. Item 7 additionally required real enforcement code, not just
text, since the baseline gap was a genuine authorization hole.

- **Item 7 fix (the one with real stakes):** `_refresh_conflicts_tab`
  now checks `roles.is_owner(conn, reviewer_id)` and disables both
  resolve buttons for a non-owner (same disabled-while-blind pattern
  already used); `_resolve_conflict` also re-checks ownership itself
  (defense in depth against any path that calls the handler directly,
  bypassing the disabled button) and refuses with a clear error.
  `screening.resolve_conflict` itself is intentionally left
  untouched -- same "UI layer enforces it, not the backend" pattern
  already documented for the blind-mode check, so no existing
  screening.py test/call site changes.
- **Items 2/3 fix:** `_render_conflict` now renders the selected
  record's title, occurrence ID, authors, and year as a header before
  the vote lines, and each vote line now includes its real
  `created_at` timestamp (`owner: include -- 2026-10-07T...Z`).
- **Item 9 fix:** the same new info note (`conflict_authorization_label`,
  `TOKENS["info_soft"]` idiom) states append-only audit semantics
  alongside the ownership state, in one sentence, dynamically worded
  for owner vs non-owner.
- **Tests:** `test_conflicts_tab_resolve_disabled_and_blocked_for_non_owner`
  (buttons disabled, note states it, direct-call defense-in-depth all
  verified) and `test_conflicts_tab_detail_pane_shows_record_and_timestamps`
  (title/ID/authors/year and a real timestamp present in the rendered
  text). Full suite: 238/238.
- **Live verification:** re-captured the live tab; record header,
  occurrence ID, authors/year, two vote lines with real timestamps,
  and the owner-authorization/audit note all render legibly with no
  clipping or overlap.
- **New scores -- items 2, 3, 7, 9: 2 each** (were 1, 1, 0, 0). Items
  1, 4, 5, 6, 8, 10, 11, 12, 13 unchanged -- not touched this round.

**Running total: 23/26.**

Queued next: item 1 (an explicit record ID in the queue row itself,
not just in the now-fixed detail pane) and item 6 (visually distinct
required-field empty state) are both small, cheap. Item 10 (keyboard
order/focus) needs the same real `win32api.keybd_event` empirical
check used to close Duplicates item 11, not an assumption.

## Round 2 — items 1 and 6 (2026-10-07)

- **Items 1 and 6:** queue rows now include both title and occurrence ID. The resolution-note field has a red `*required` marker and a visible empty-state hint before submission; the hint clears as soon as non-whitespace text is entered and returns if the field is emptied. After a successful resolution, the cleared field returns to the required empty state.
- **Tests:** added `test_conflicts_tab_queue_row_shows_occurrence_id` and `test_conflicts_tab_resolution_note_empty_state_is_visible_and_live`; also added assertions for the existing non-owner authorization wording and the post-resolution status message.
- **Live screenshots:** `docs/ui-references/conflicts/round-2-live-empty-note.png` shows the queue title/occurrence ID, required marker, and empty-state hint; `docs/ui-references/conflicts/round-2-live-note-entered.png` shows the hint cleared while a note is entered. Both use synthetic records.
- **Verification:** full suite **245/245**; `git diff --check` passes. No screening-data files were touched; the live captures use synthetic records.
- **New scores — items 1 and 6: 2 each** (were 1 and 1). Item 10 remains 1 because this round's diff contains no verified keyboard-focus evidence. Running total: **25/26**; Conflicts is not marked closed in this round.

## Round 4 — live-app Directive F re-score, Conflicts closed (2026-10-10)

- **Scope:** reviewer supplied a fresh Directive F re-score (25/26), with item 10 at 1/2 solely because the newer card-shell captures did not demonstrate keyboard focus or a status announcement. This is verification-only: no app code, shortcut, handler, or style change.
- **Real OS input and focus path:** seeded two synthetic open conflicts plus two agreed controls in a disposable local database. Selected the Conflicts page, then used the live window's real Tk traversal predecessor and `win32api.keybd_event(VK_TAB)` to move focus from the page's preceding widget into `conflict_list`; the app's Tk `<FocusIn>` trace recorded notebook → tab/container frames → queue Listbox. The actual queue received focus; its configured Field Notes focus token displayed as an orange `#c45a32`, 3-pixel highlight. Sent a real Down key to that focused queue: selection moved to conflict 2 of 2, detail updated to that selected synthetic record, and the footer announced **“Focused conflict 2 of 2.”**
- **Fresh capture:** replaced `conflicts-selected.png` with the 1280×800 live foreground capture after the real Tab and Down input. It shows the orange focus outline on the queue, selected second row, matching details, and the footer announcement. Vision inspection confirms the ring, selected state and exact status copy are legible without clipping. Existing blind-ON `conflicts.png` remains unchanged.
- **Verification:** focused arrow/navigation test plus real GUI trace/capture passed; full suite **338 passed**; `py_compile` and `git diff --check` clean. Re-score item 10 = **2/2**; machine recomputation of all 13 item scores returns **26/26**. The supplied accepted re-score is otherwise unchanged; no code behavior changed.


## Round 3 — item 10, original-layout keyboard focus check (2026-10-08)

- **No code change.** This round is verification-only, per the loop discipline's guidance to confirm focus behavior empirically before writing new focus/keyboard code — the existing widget order already satisfies item 10.
- **Real OS-level check:** launched the live app with a bound `<FocusIn>` trace, foregrounded the window (`win32gui.SetForegroundWindow` with `AttachThreadInput`, confirmed foreground before each step), sent a real `win32api.mouse_event` click on the queue row, then a real `win32api.keybd_event(VK_TAB)`. The process's own focus trace recorded `Listbox -> TFrame -> TEntry` for one Tab press, confirming focus moves from the queue selection directly to the resolution-note entry (skipping the disabled detail `Text` widget, which Tk does not include in tab order by default).
- **Live screenshot:** `docs/ui-references/conflicts/round-3-keyboard-tab-focus.png` shows the queue row selected (blue highlight) and the resolution-note entry with a visible focus border after the single real Tab press. Synthetic record only.
- **Verification:** full suite **245/245** (unchanged, no app.py edit this round); `git diff --check` passes. No screening-data files were touched.
- **New score — item 10: 2** (was 1). All 13 Conflicts items now score 2.

**Original-layout Conflicts tab: 26/26.** This prior score does not transfer to the Directive F card-shell layout; see the fresh 2026-10-10 re-score and Round 4 verification above.

# Full-text (12 items)

## Baseline read (2026-10-08, before this tab's first round)

Captured the live app at 1280×800 with five synthetic report records: one pending, one not retrieved, one retrieved without assessment, one assessed included, and one assessed excluded. No corpus records or screening data were used.

| # | Must show | Score | Evidence |
|---:|---|:---:|---|
| 1 | Queue distinguishes report from source occurrence | 0 | Queue rows showed only a status and source title; no report ID or source-occurrence ID was visible. |
| 2 | Sought/pending, not-retrieved, retrieved, and assessed states are textual | 2 | Live rows visibly use `[pending]`, `[not_retrieved]`, `[retrieved]`, `[retrieved -> included]`, and `[retrieved -> excluded]`. |
| 3 | PDF attachment has an icon and a text label | 0 | No attachment indicator or PDF label appears. |
| 4 | Record title/metadata and synthetic excerpt are visible | 0 | The selected row was highlighted, but no detail pane, bibliographic metadata, or excerpt was rendered. |
| 5 | Include/Maybe/Exclude mechanics match screening; Maybe remains pending | 1 | `Assess: Included` and `Assess: Excluded` are explicit; no Maybe control or pending explanation is shown. |
| 6 | Terminal full-text Exclude requires exactly one primary reason | 1 | The handler prompts for free text and the domain layer requires a non-empty reason; a controlled one-primary-reason choice is not visible or enforced. |
| 7 | Saved full-text exclusion increments PRISMA reports-excluded count | 2 | The app records terminal excluded outcomes; `tests/test_studies.py::test_acceptance_4_study_report_fixture` asserts `reports_excluded == 1` and the matching reason count. |
| 8 | Not-retrieved is separate and never assigned an exclusion reason | 2 | A distinct `Mark not retrieved` control and `[not_retrieved]` row are visible; `reports.mark_not_retrieved` changes retrieval status without setting an exclusion reason. |
| 9 | Only permitted own-stage data is displayed while blind | 1 | No other reviewer decisions or identities appear, but this capture is blind-OFF; blind-ON behavior was not verified for this tab. |
| 10 | Keyboard shortcuts and focus are visible; controls meet minimum target size | 1 | Buttons are usable-sized, but no shortcut guidance or focus state is visible; keyboard traversal remains unverified. |
| 11 | Semantic text communicates all retrieval/decision states | 2 | Retrieval and terminal outcome are explicit words in each row, not color-only states. |
| 12 | All displayed record content is synthetic and marked as such | 1 | The seeded titles explicitly say "Synthetic"; there is no persistent synthetic-only banner or marker. |

**Baseline: 13/24.**

## Round 1 — items 1 and 4 (2026-10-08)

- **Root cause:** both items trace to the same gap — `_refresh_fulltext_tab` rendered only `[status] title` per row, and no detail-pane render function existed. Fixed both in one region: the queue row now shows `[status] Report: {report_id} | Source: {occurrence_id} | {title}`, and selecting a report calls a new `_render_fulltext_detail` that shows the report ID, source occurrence ID, title, authors/year/journal/DOI, and the stored abstract/excerpt in a `tk.Text` detail pane with a horizontal-scrolling queue list to accommodate the longer row text.
- **Tests:** added `test_fulltext_tab_queue_and_detail_show_report_and_source_identity`, asserting the queue row contains both IDs and the detail pane contains the report/source IDs, title, authors, journal, year, and abstract text after a real `<<ListboxSelect>>` selection.
- **Live screenshot:** `docs/ui-references/full-text/round-1-live-queue-and-detail.png` shows five synthetic reports with distinct report/source IDs in the queue and a populated detail pane for the selected row, with no clipping or overlap.
- **Verification:** full suite **246/246**; `git diff --check` passes. No screening-data files were touched; all seeded records are synthetic.
- **New scores — items 1 and 4: 2 each** (were 0 and 0). Running total: **17/24**. Items 3, 5, 6, 9, 10, 12 are unchanged and queued for later rounds.

## Round 2 — item 6 (2026-10-08)

- **Fix:** `_report_assess` called `simpledialog.askstring` for a free-text exclusion reason on terminal Exclude. Replaced it with `self._prompt_exclusion_reason()`, the same numbered 1-7 closed-taxonomy modal already used at title/abstract stage (`screening.EXCLUSION_REASONS`), reusing the existing, tested dialog rather than building a new one. Cancelling the picker (Escape or closing the window) still returns `None` and `_report_assess` returns without recording an outcome, so terminal Exclude without a reason remains impossible — matching the screening-stage guarantee.
- **Tests:** added `test_fulltext_tab_exclude_uses_numbered_taxonomy_reason` (monkeypatches `_prompt_exclusion_reason` to return a taxonomy value and asserts the stored `exclusion_reason` matches it) and `test_fulltext_tab_exclude_cancelled_reason_records_nothing` (monkeypatches it to return `None` and asserts no outcome/reason was recorded).
- **Live screenshot:** `docs/ui-references/full-text/round-2-live-exclusion-reason-picker.png` shows the numbered 1-7 reason picker open over the live Full-text tab during a real `Assess: Excluded` action on a synthetic report.
- **Verification:** full suite **248/248**; `git diff --check` passes. No screening-data files were touched; all seeded records are synthetic.
- **New score — item 6: 2** (was 1). Running total: **19/24**. Items 3, 5, 9, 10, 12 are unchanged and queued for later rounds.

## Round 3 — item 10, real keyboard focus check (2026-10-08)

- **No code change.** Verification-only, per the loop discipline's guidance to confirm focus behavior empirically before writing new focus/keyboard code.
- **Real OS-level check:** launched the live app with a bound `<FocusIn>` trace, foregrounded the window, sent a real `win32api.mouse_event` click on the report queue row, then a real `win32api.keybd_event(VK_TAB)`. The process's own focus trace recorded `Listbox -> TFrame -> TButton` for one Tab press, confirming focus moves from the queue selection directly to the "Mark not retrieved" button (skipping the disabled detail `Text` widget, which Tk does not include in tab order by default).
- **Live screenshot:** `docs/ui-references/full-text/round-3-keyboard-tab-focus.png` shows the queue row selected and the "Mark not retrieved" button with a visible dotted focus ring after the single real Tab press. The three action buttons use the same default ttk sizing already accepted elsewhere in the app. Synthetic record only.
- **Verification:** full suite **248/248** (unchanged, no app.py edit this round); `git diff --check` passes. No screening-data files were touched.
- **New score — item 10: 2** (was 1). Running total: **21/24**. Items 3, 5, 9, 12 remain queued.

## Round 4 — item 9 (blind lock) and item 12 (documentation only); item 3 deferred (2026-10-08)

**Correction:** running total is 19/24, not 21/24 (13 baseline + 4 round 1 + 1 round 2 + 1 round 3; items 9 and 12 were still at 1, not 2 — the two prior "Running total" lines arithmetic-erred).

- **Item 9 — the hole:** `_refresh_fulltext_tab` had no `roles.is_blind()` handling at all, and `reports.unlinked_included_occurrences` takes no reviewer parameter — it returns every reviewer's current includes unfiltered. While blind, reviewer B's Full-text tab listed, and let B promote, occurrences reviewer A included: the same class of gap Conflicts had before its own owner-authorization fix.
- **Item 9 — fix:** mirrored `_refresh_conflicts_tab`'s blind branch exactly. While `roles.is_blind(conn)` is true: `promote_list` and `report_list` are emptied (not populated), `_promote_occurrence_ids` and `_report_ids` are set to `[]`, the detail pane is cleared, all four actions (`Create report from selection`, `Mark not retrieved`, `Assess: Included`, `Assess: Excluded`) are disabled, and a lock label reads "Full-text is locked while blind mode is ON. The project owner must turn blind mode off to open this tab." While blind is off, behavior from rounds 1-3 is unchanged. UI-layer enforcement only, same pattern as Conflicts; `reports.py` is untouched.
- **Item 9 — tests:** `test_fulltext_tab_locked_while_blind` seeds another reviewer's (`revA`) include and an already-assessed report, turns blind ON, and asserts both queues and ID lists are empty, all four buttons are disabled, and the lock label is visible; then turns blind OFF in the same test and asserts the queue repopulates, the assess button re-enables, and the lock label clears, with no stale empty state.
- **Item 9 — live screenshot:** `docs/ui-references/full-text/round-4-blind-lock.png` shows the lock label, both empty queues, the empty detail pane, and all four greyed-out buttons on the live app with blind mode ON and a synthetic other-reviewer report seeded; the Full-text nav badge also correctly reads `(0)` instead of leaking the pending count.
- **Item 12 — documentation only, no code:** the "all displayed record content is synthetic and marked as such" requirement applies to the reference package and its own test/capture artifacts, not to a permanent production banner — labeling real review records "SYNTHETIC" in a live project would misrepresent them. Every reference package (including this one) is marked as a synthetic sample in its own header/footer chrome, and every Full-text capture and fixture used in this convergence log is synthetic seed data only (`Synthetic model habitat trial`, `Synthetic other-reviewer include`, etc.), consistent with how Conflicts and Duplicates were closed without a live-app synthetic banner.
- **Item 3 — deferred:** PDF attachment icon/label is a feature-sized gap, not a cosmetic one — no attachment data model exists anywhere in the schema (`db.py` has no attachment/PDF table or column). Out of scope for this convergence loop; logged as a deferred v1 feature gap.
- **Verification:** full suite **249/249**; `git diff --check` passes. No screening-data files were touched; all seeded records are synthetic. No `reports.py` changes; no blind-toggle changes.
- **New scores — items 9 and 12: 2 each** (were 1 and 1). Item 3 remains 0 (deferred, not attempted). Recomputed from the table: 13 baseline + 4 (round 1) + 1 (round 2) + 1 (round 3) + 2 (round 4) = **21/24**.

## Round 5 — item 5, Maybe UI wiring (2026-10-08)

- **Backend prerequisite:** migration 008 and `reports.record_full_text_assessment('maybe', ...)` landed in a separate backend-only commit (`439d8f3`, Directive C) ahead of this round; this round is the UI follow-up it explicitly deferred.
- **Fix:** restyled the three Full-text assessment buttons from generic `ttk.Button` to the exact same colored `tk.Button` decision bar as Screening (`TOKENS["include"/"include_soft"/"maybe"/"maybe_soft"/"exclude"/"exclude_soft"]`, same glyph/label shape), and added a new "? Assess: Maybe" button wired to `self._report_assess("maybe")`. `_report_assess` needed no change: for `outcome="maybe"` it already skips the exclusion-reason prompt and passes `reason=None`, which `reports.record_full_text_assessment` already accepts. The Maybe button is included in the existing blind-mode disable/enable branches alongside the other three actions.
- **Nav-badge fix (flagged in the prior commit as a known latent gap):** `pending_fulltext` in `refresh_all_tabs` counted `not r["full_text_outcome"]` only, so a maybe-assessed report would have disappeared from the Full-text tab's pending count the moment a reviewer could reach it through the UI. Changed to `not r["full_text_outcome"] or r["full_text_outcome"] == "maybe"`, matching the same fix already applied to `reports.counts()` and `export.compute_completeness` last round.
- **Queue display:** required no code change — the existing row format (`f" -> {r['full_text_outcome']}"` interpolation) already renders `maybe` like any other outcome value once one exists.
- **Tests:** `test_fulltext_tab_maybe_button_is_non_terminal_and_reassessable` (Maybe stores no reason, is excluded from `reports_included`/`reports_excluded`, counts in `reports_pending`, the nav badge still reads the pending count, the queue row shows `maybe`, and the report is still re-assessable to `included` afterward); extended `test_fulltext_tab_locked_while_blind` to also assert the Maybe button disables/re-enables with the other three.
- **Live screenshot:** `docs/ui-references/full-text/round-5-live-maybe-decision-bar.png` shows the three-button colored decision bar and a `[retrieved -> maybe]` queue row with the nav badge correctly reading `Full-text (1)`, on two synthetic reports (one maybe-assessed, one included).
- **Verification:** full suite **256/256**; `git diff --check` passes. No screening-data files were touched; all seeded records are synthetic.
- **New score — item 5: 2** (was 1). Running total: 21 (post-round-4) + 1 = **22/24**. Item 3 (PDF attachment) remains the only item not yet attempted, deferred as a feature-sized v1 gap.

## Round 6 — item 3: PDF attachment, Full-text closed (2026-10-08)

- **Backend prerequisite:** `screening_workbench.attachments` (migration 009, `report_attachments` table, content-addressed file storage) landed in a separate backend-only commit (`f378cde`, Directive D) ahead of this round, lifting round 4's "no attachment data model exists" deferral.
- **Fix:** wired `screening_workbench.attachments` into the Full-text detail pane inside the existing blind-lock branch (`2b0940e`, the UI-wiring follow-up commit): an "Attached PDFs" list plus Attach/Open/Remove controls for the selected report, and a paperclip-icon (`\U0001F4CE`) + literal "PDF attached" text label on the report queue row itself — the item's exact wording, satisfied as both an icon *and* a text label together, visible before the report is even selected, not only in the detail pane. "Attach PDF..." opens a file picker and surfaces rejection (`ValueError` for non-PDF, oversize, or no `report_retrievals` row yet) via a dialog. "Open selected" re-verifies the SHA-256 hash through `attachment_bytes` and opens a throwaway temp copy via `os.startfile` — read-only, never mutates the record. "Remove selected..." requires an explicit `askyesno` confirmation naming the file, mirroring the Duplicates tab's merge-confirmation discipline; declining is a real no-op. All three controls are disabled and the list is cleared while blind, same lock pattern as every other Full-text action.
- **Tests:** 5 new UI-level tests in `tests/test_app.py` (`test_attach_pdf_via_ui_adds_to_list_and_queue_badge`, `test_attach_non_pdf_via_ui_shows_error_and_adds_nothing`, `test_remove_attachment_via_ui_requires_confirmation`, `test_open_attachment_via_ui_writes_temp_copy_and_starts_file`, `test_fulltext_attachment_controls_disabled_and_hidden_while_blind`) drive the real handlers with `tkinter.filedialog`/`messagebox` and `os.startfile` monkeypatched — no real dialogs or OS calls. Full suite **297/297**.
- **Live screenshot:** `docs/ui-references/full-text/round-6-live-attachment-ui.png` shows the report queue row reading `... | PDF attached` with the paperclip glyph, the selected report's detail pane, and the "Attached PDFs" list (`synthetic-full-text.pdf (0.1 KB, by owner)`) with all three Attach/Open/Remove buttons — a single synthetic report, no corpus or screening data.
- **Verification:** full suite **297/297**; `git diff --check` passes. No screening-data files were touched; the seeded record and PDF are synthetic.
- **New score — item 3: 2** (was 0, deferred since round 4). Recomputed with `python3`: `sum({1:2,2:2,3:2,4:2,5:2,6:2,7:2,8:2,9:2,10:2,11:2,12:2}.values())` = **24/24**. **Full-text tab: closed.**

## Directive F live-shell migration — Full-text (2026-10-10)

- **Scope from this diff:** reparented Full-text's existing included-record queue/promotion, report list/detail/excerpt, assessment actions, exclusion reasons, and PDF attachment controls into the three-card shell. Added selected-report identity and Previous/Next navigation with a status announcement. The reviewer can choose one listed taxonomy reason before terminal Exclude; the existing taxonomy prompt remains the fallback, cancellation records nothing, and Maybe stays non-terminal. No domain/database/dependency changes.
- **Selection state:** Next/Previous, report assessment, not-retrieved, and reason controls are disabled without a selected report; reason options are enabled for pending or excluded assessment, and cleared for non-excluded outcomes. On changing the selected report, any unsaved reason selection is discarded to prevent carrying it across reports. Blind refresh clears report/detail/reason/attachment state before locking the lists and actions.
- **Evidence:** refreshed `fulltext.png`, `fulltext-selected.png`, and `fulltext-blind.png` are foreground 1280×800 captures from disposable synthetic databases. The selected image's report ID, title and excerpt were asserted against the rendered details, and the capture shows the PDF list and actions. The left queue is narrow: its long report/source IDs and trailing PDF indicator text can be clipped in the displayed row; this visual criterion remains unverified. The blind capture shows a fictional reviewer alias from the synthetic session chrome, but no report IDs/details/outcomes/reasons. Only PNGs are present in the live-captures directory; capture helpers and databases are outside the repo.
- **Verification:** focused Full-text suite **10 passed**; full suite **340 passed**; `py_compile` and `git diff --check` clean. No checklist score/closure is claimed; accessibility/focus and remaining visual criteria require fresh review.

## Directive F follow-up — Full-text PDF badge and keyboard evidence (2026-10-10)

- **Changes:** condensed queue rows to keep retrieval/outcome, distinct abbreviated report (`R:`) and source (`S:`) IDs, and a visible `▣ PDF attached` icon+text within the narrow list width; full IDs and title remain in selected detail. Added a conspicuous Field Notes focus outline on the report queue, real queue-focused Up/Down handling, and selected-report/status refresh.
- **Regression coverage:** populated compact-row fixture proves the PDF marker and both IDs survive at the target width while unattached rows omit the badge. Queue keyboard test checks visible focus token, Up navigation to the second report, matching rendered detail, and `Focused report 2 of 2.`
- **Live evidence:** regenerated `fulltext-selected.png`, `fulltext-focus.png`, and `fulltext-focus-navigation.png` at 1280×800 from synthetic data and a valid tiny PDF in a disposable DB. The selected capture shows the compact PDF-marked queue row and matching center detail; the focus capture follows real Tab traversal from the promotion list to the report queue; the navigation capture follows a real Down key and shows the second report detail with the matching status. No capture helper/DB was kept in the repository; the evidence directory contains PNGs only.
- **Verification:** focused tests: **13 passed**; full suite: **343 passed**; `py_compile` and `git diff --check` clean. Re-score only checklist items 3 and 10; the prior overall score is not carried forward and this entry does not claim full closure.

## Directive F — Phase 2 Studies card-shell migration

- **Diff:** reparented the existing study/report hierarchy into a left Study Groups card, existing study/report detail plus decision and link controls into a center Reports & Study Decision card, and existing canonical-occurrence controls into a right Canonical Occurrence card. Preserved the Treeview IDs/selection, detail renderer, existing handlers, progression/rationale behavior, and blind-gate paths. Added only a shared card-heading ttk style and replaced the now-redundant nested canonical-choice heading with “Available source occurrences.”
- **Tests:** test-first `test_phase2_studies_tab_has_three_card_shell_without_moving_controls` failed before the shell existed and now checks all three card parents/order, reparented hierarchy, decision/link controls, canonical controls, and empty-state widgets. Existing hierarchy, provenance/detail, canonical-selection/correction, study-decision/rationale, empty-state, and blind-lock tests remain passing.
- **Live captures:** `docs/ui-references/live-captures/studies-selected.png` and `studies-report-selected.png` are fresh 1280×800 client captures from a synthetic two-occurrence fixture. The first shows the selected study and its linked report in the detail card; the second shows the expanded study group with the report child selected, report metadata/provenance in the center, and the two canonical radio choices at right. Both show the shell/footer without overlap. Study/report IDs in the narrow tree and source titles in the canonical card are visibly clipped; the full identifiers and titles are available in the detail/provenance text. The blind capture attempt was discarded because its screenshot did not provide trustworthy evidence of the cleared detail state; the automated blind-lock regression passes, but this entry makes no new visual claim for blind mode or checklist score/closure.
- **Verification:** focused Studies tests **7 passed**; full suite **344 passed**; `py_compile` and `git diff --check` clean. No domain/database/dependency changes; seeded data and capture helpers stayed outside the repository. This migration changes only Studies.
- **Re-score (Cinder, 2026-10-11): 22/24 conditional pass.** Items 10 (blind) and 11 (keyboard/focus) are each partial at 1/2; no visual blind or focus evidence was established in the original migration round. The code/data behavior stays covered by the automated blind regression; no checklist closure is claimed here. Item 10 and 11 follow-up evidence is in the next fix-up round.

## Directive F — Phase 2 Studies evidence fix-up (2026-10-11)

- **Fresh empty state:** replaced stale `studies.png` with a 1280×800 post-migration capture. It shows all three cards, the in-panel “No studies yet” guidance, zero Studies badge, and shared footer; no study/report rows appear.
- **Blind check/capture:** seeded one fictional study with one linked report and two fictional occurrences, confirmed the selected report detail before enabling blind, then enabled blind through `roles.set_blind` and `refresh_all_tabs`. `studies-blind.png` shows the explicit lock text, empty tree/detail/canonical areas, and disabled-action appearance. The helper asserted the tree/detail and both lookup collections empty and the New study, three decision, and Link buttons disabled. Image inspection found no report IDs, titles, outcomes, provenance, or reason content in the saved capture; the Studies badge remains 1 as a neutral total.
- **Keyboard/focus verification:** after a real OS click on the report-child row, the live FocusIn trace records the Study Treeview owning focus; a subsequent real Tab advances to the decision actions. This establishes that the Treeview and actions participate in keyboard focus navigation, but it is **not** a Tab-into-tree traversal from the preceding control. Repeated pixels show only selected-row tint, with no distinct visible Treeview focus ring; item 11 remains **1/2**. Saved `studies-focus.png` records the selected synthetic state and makes this visual evidence gap explicit rather than claiming a visible focus pass.

### Evidence-only re-score and cleanup (2026-10-11)

- Item 10 improves from 1 to **2/2** based on the fresh blind capture and widget-state assertions. Item 11 remains **1/2**: OS focus reached the tree after a mouse click, but no visible focus cue or Tab-into-tree from its preceding control was demonstrated. Running score: **23/24 conditional pass**, pending the visual focus requirement. No production change in this evidence round.
- Evidence images are 1280×800 client captures; fixture database, script, stop file, and traces were temporary and outside the repository. The evidence folder contains PNGs only.

- **Test-first pass:** add a parent/order regression for two side-by-side cards while preserving the scrolling canvas and audit privacy tests.

- **Test-first pass:** added `test_studies_tree_keyboard_focus_is_visibly_distinguished`. Its assertions exposed that the initial nested-frame inset did not change the actual panel border; the test now checks border thickness/color, focus status text, focus-state tag, `takefocus`, and neutral cleanup.
- **Implementation:** on Treeview FocusIn, change the full Study Groups frame to a 4px Field Notes focus outline (`#c45a32`), change the inset, set `takefocus=True`, apply a soft-background tag to the selected stable ID without changing row text or domain state, and show “Keyboard focus: Study/report groups.” On FocusOut, restore the neutral border/inset, tags, `takefocus=False`, and keyboard guide. Added local Tab routing from New study → Treeview → report-link field; blind mode keeps locked actions unavailable.
- **Live evidence:** a fresh foreground capture after OS click and Tab still showed only the normal selected-row tint: no 4px border or focus status. The selected synthetic report detail remained aligned. Item 11 stays partial; `studies-focus.png` was not replaced because it does not substantiate a focus pass. Do not score this item closed.
- **Verification/scope:** focus, card-shell, and blind-lock tests pass; full suite **345 passed** after the final code change; `py_compile` and `git diff --check` pass. No decision, report-link, canonical-progression, or blind-policy semantics changed; no dependency added. Synthetic fixture artifacts were cleaned outside the repository.

### Directive F outstanding focus fix-up — Studies item 11 (2026-10-11)

- **Code:** the Studies Treeview is now an explicit Tab stop from New study, with its surrounding panel showing a 3px Field Notes `#c45a32` outline only while the tree owns keyboard focus. The outline is outside the row surface; the normal selected-row tint remains independently visible. FocusOut restores the neutral 1px line and clears the transient focused-row tag. No study, report, decision, link, canonical-progression, or blind-gate behavior changed.
- **Real OS traversal/evidence:** first validated the capture method on the existing Screening queue control. Then, with the Studies tab selected and a synthetic study/report fixture, foregrounded the app and sent a real OS Tab from the preceding New study button into the Treeview. The in-app FocusIn trace recorded `TNotebook -> Studies page/container -> New study button -> Study Groups frames -> Treeview`; the Treeview itself received FocusIn. Fresh `studies-focus.png` is a 1280×800 foreground client capture showing a selected study row with its ordinary light-blue selection tint, separately framed by the visible orange 3px focus outline; the center detail identifies the same selected synthetic study. The detailed trace is retained in the task scratch directory as `directive-f-focus-traces.json` (not committed).
- **Tests/re-score:** updated `test_studies_tree_keyboard_focus_is_visibly_distinguished` for the actual 3px border and persistent `takefocus`, neutral FocusOut styling, and selection distinction. Re-score item 11 only: **2/2** (was 1/2). Studies changes from the supplied 23/24 to **24/24**; other item scores unchanged.

### Directive F outstanding focus fix-up — PRISMA item 11 and correction (2026-10-11)

- **Explicit correction to cf7842e:** **Old claim:** the 2026-10-11 cf7842e follow-up said real OS Tab reached the in-tab “Export package...” button and showed its dotted focus cue. **Correction:** pixel review located the cue on the header/shell Export button (bbox x=1136–1261, y=44–80); the in-tab button below the audit log had no focus cue in that capture. The old evidence therefore does not substantiate in-tab keyboard focus; this entry replaces that evidence, not the historical claim.
- **Real OS traversal and full forward order:** on PRISMA & audit, foregrounded the app and started at its first tab stop, the outer scroll Canvas. Two real `win32api.keybd_event(VK_TAB)` presses, with an in-app `<FocusIn>` trace, recorded the full in-tab order: **outer scroll Canvas → Audit log Treeview → in-tab “Export package...” button**. The trace names the target widget path under the PRISMA audit card; it does not reach or confuse it with the header/shell Export button.
- **Live evidence:** fresh `prisma-focus.png` is a 1280×800 foreground client capture. Pixel inspection confirms the in-tab button below the audit log is fully visible with its dotted focus cue; the separate header/shell Export button is unfocused. Fixture data are synthetic and disposable. The detailed FocusIn trace is retained in the task scratch directory as `directive-f-focus-traces.json` (not committed).
- **Correction to item 1 wording (owner ruling, 2026-10-11):** **Old text:** “item 1 (‘not synthetic’) is unchanged per Nate’s ruling.” **Ruling:** Nate determined that PRISMA item 1 is **SATISFIED-BY-INTENT → 2/2**. The visible “Live project data · preview only · not synthetic” label stands as-is; no checklist/package amendment is required. With item 11 at 2/2 from this fix-up, the Phase 2 PRISMA & audit total is **24/24**. No other item is re-scored here, and no counts or blind-gating changed.
- **Phase 2 board record (owner-supplied, 2026-10-11):** Screening 27/28; Maybe re-review 24/24; Duplicates 24/24; Conflicts 26/26; Full-text 24/24; Studies 24/24; PRISMA & audit 24/24. The owner-provided per-tab totals are recorded as supplied; this correction does not re-score those tabs.

### Directive F Phase 3 — Field Notes theme (2026-10-11)

- **Theme foundation:** Added `src/screening_workbench/theme.py` on ttk `clam` with the Field Notes tokens, font fallback stacks, 8px spacing scale, 6/10/14px radii, minimum control sizing, classic Tk Canvas/focus options, and the Ttk styles used by the new shell and its Treeview, buttons, entries, notebook, and scrollbars. `app.py` imports the theme module and uses `theme.TOKENS`; it has no direct palette hex literals. Theme setup also applies semantic state colors, text/listbox defaults, focus and canvas factories. No product dependencies or font assets were added.
- **Accessibility and behavior checks:** The theme contract tests assert the exact design-system tokens, focus outline remains rust `#c45a32` at 3px with neutral restoration, and selection styling is independent. Computed WCAG text/background pairs in `theme.TEXT_CONTRAST_PAIRS` all pass AA (minimum 4.5:1); soft tints are used as fills, not text grounds. Eligible and disabled ttk controls retain their state styling; tests cover the 40px primary-button minimum. No review/blind-gating logic was intentionally changed.
- **Fresh live evidence:** Seven new 1280×800 client captures were generated from foregrounded Screening Workbench windows after setting the requested notebook page and seeding disposable synthetic fixture data. They are `docs/ui-references/live-captures/phase3-screening.png`, `phase3-maybe.png`, `phase3-duplicates.png`, `phase3-conflicts.png`, `phase3-fulltext.png`, `phase3-studies.png`, and `phase3-prisma.png`. Each capture has an in-app FocusIn trace of real OS Tab traversal; queue-backed pages show populated data, Studies shows one unresolved study without linked reports, and PRISMA shows its own lower Export button focused after **outer scroll Canvas → Audit log Treeview → in-tab Export package button**. PRISMA's existing “Live project data · preview only · not synthetic” copy is preserved unchanged; it is existing UI text and not a claim that the disposable capture fixture is live corpus data. Focus is reinforced with `FOCUS`/status text and palette contrast checks; no phase checklist items were re-scored.
- **Blind-integrity spot check:** For each fixture, blind mode is OFF and reviewer scope is the synthetic fixture owner; counters correspond to seeded visible records (Screening 5, Maybe 1, Duplicates 1 candidate pair, Conflicts 2 open disagreements, Full-text 1 pending report, Studies 1 unresolved no-report study). PRISMA's snapshot is read-only and its audit log shows fixture owner/import/review/report events; no other reviewer vote is rendered on the reviewer-scoped Maybe tab. The conflicts fixture intentionally shows two reviewer decisions in the unblinded owner adjudication view, not a blind state. The Studies fixture has no linked reports, avoiding a data-derived conflict indication; its separate `Studies` total is one and the `Full-text` and `Conflicts` counts are zero.
- **Phase 2 correction retained above:** the historical cf7842e focus claim and owner ruling wording are stated explicitly; PRISMA item 1 remains SATISFIED-BY-INTENT at 2/2, with the label and checklist/package left unchanged. The supplied Phase 2 board totals remain the owner-provided record. **No Phase 3 checklist scores were re-scored.**
- **Verification:** `python -m pytest -q` → **354 passed**; `python -m py_compile src/screening_workbench/theme.py src/screening_workbench/app.py tests/test_app.py` and `git diff --check` pass. Capture helpers/traces and disposable SQLite databases remain in scratch; only the seven intended PNGs are in the repository.

### Directive F Phase 3 fix-up — Screening and Full-text card containment (2026-10-11)

- **Root cause and fix:** The 0dd7110 Phase 3 captures showed the Screening center card’s primary I/M/E bar clipped and the Full-text PDF action buttons below the support card viewport. Screening’s content-driven three-card grid was being constrained by an arbitrary fixed 520px body height; removed that fixed height and propagation suppression, and reduced only the abstract Text widget’s requested display height from 14 to 7 lines (same font/padding, with its existing vertical scrollbar) so the primary, secondary, and legend rows fit in the card. In Full-text, put the existing Attach PDF / Open selected / Remove selected actions in a dedicated bottom grid row of the right support card; the existing support content occupies the weighted row above. These are local layout changes only; tokens, shared theme styles, handlers, decisions, counts, and blind logic are unchanged.
- **Regression guard:** Added mapped geometry containment tests at 1280×800 after window mapping and `update_idletasks()`. They assert all three primary and all three bulk Screening decision buttons are mapped, at least their requested heights, and end inside their respective cards; Attach PDF and Open selected are mapped, at least requested height, and end within the Full-text support card. Both tests failed on 0dd7110, then passed after the layout fix.
- **Evidence/scope:** Fresh foreground client captures replace only `phase3-screening.png` and `phase3-fulltext.png`, each 1280×800, synthetic-fixture-backed, with OS Tab traversal and in-app FocusIn traces. Pixel inspection confirms all six Screening decisions and Attach PDF / Open selected are fully visible and legible inside their cards. Other five phase3 captures stand unchanged because neither `theme.py` nor shared styles/layouts were modified. No checklist scores were re-scored.
- **Verification:** `python -m pytest -q` → **356 passed**; `python -m py_compile src/screening_workbench/app.py tests/test_app.py` and `git diff --check` pass.

#### Directive F Phase 4 follow-up — Part B evidence + global ttk disabled affordance (2026-10-12)

- **Part B capture record (from commit `9dffaa3` artifacts):** `phase4-screening-blind.png` shows blind ON, the blind note, and Conflicts LOCK; `phase4-conflicts-blind.png` shows the blind lock with Export reviewer packet and Merge votes unavailable; `phase4-duplicates-blind.png` shows a populated selected two-record pair under blind ON; `phase4-studies-report-selected.png` shows the expanded study with selected report child, marked canonical occurrence, two linked source provenances, and `default (default)` branch/source; `phase4-fulltext-states.png` shows pending, not_retrieved, retrieved→maybe, retrieved→excluded; `phase4-fulltext-pdf-attached.png` shows the selected report's PDF badge plus attached filename and action row. All six are synthetic 1280×800 window-handle captures (PrintWindow), prepared without foreground or keyboard input. The Part B duplicates round-trip below is deliberately reported separately: the original capture trace does not establish it.
- **Duplicates protected-state check executed in this round:** On a fresh synthetic near-match pair plus two reviewers' decision rows, verified OFF→ON→OFF. OFF before: 1 raw/open duplicate pair, UI count 1. While ON, the direct `dedup.list_open_fuzzy_clusters(conn)` query still returned the pair (raw presence=1), while the visible pair list itself is a separate manual-review queue not blind-filtered. Direct `screening.votes_for_occurrence` re-queries returned both reviewer IDs on the shared occurrence and the first reviewer's vote on the other; `screening.visible_votes_for_reviewer(..., viewer='demo-reviewer-b', is_blind=True, is_owner_or_auditor=False)` returned only reviewer-b's shared-occurrence vote and no vote on the other occurrence (blinded absence). After OFF restore, unblinded visible-vote re-query returned both IDs on the shared occurrence and reviewer-a on the second, with duplicate raw pair=1. Thus blind view hides another reviewer's vote attribution/data through the policy API; it does not delete the duplicate pair or raw vote rows.
- **Finding 2 fix:** In `theme.py`, mapped the base `TButton` disabled foreground to the existing muted token and explicitly set the base enabled foreground to the existing ink token, preserving the established enabled rendering and the rust focus color/map. This applies to ttk `TButton` subclasses that inherit the base state map; special Accent/Quiet/FulltextNext disabled maps remain unchanged. No tokens or blind/handler behavior changed.
- **Blast-radius check:** The global disabled foreground makes default-style disabled actions read muted, including the Duplicates empty-state Merge/Keep-separate and Studies Decide buttons; explicit Accent/Quiet and FulltextNext disabled maps continue to use muted. Added a deterministic style lookup regression checking disabled color differs from enabled and rust focus remains configured. Focused theme/conflicts/duplicates/Full-text tests pass.
- **Evidence:** Refreshed `phase4-conflicts-blind.png` by window handle after the style change; image inspection confirms Export reviewer packet and Merge votes text are visibly muted. Added `phase4-duplicates-disabled.png` with an empty candidate queue and muted disabled Merge/Keep separate controls. Both captures are synthetic 1280×800 handle renders, without foreground/keyboard input. No checklist scores are claimed.
- **Verification:** `python -m pytest -q` → **362 passed**; `python -m py_compile src/screening_workbench/theme.py src/screening_workbench/app.py tests/test_app.py`; `git diff --check` pass. No checklist re-scores are claimed.

### Directive F Phase 4 fix-up — Maybe support sections and Full-text note (2026-10-12)

- **Maybe support card:** Restored the right-card BLIND INTEGRITY GATE as a tinted callout and the KEYBOARD GUIDE with exact copy “Queue-focused: I/M/E/J/K.” Added local vertical compaction to the exclusion-reason radio buttons only, preserving the content and existing handlers, to keep both restored sections inside the fixed card at 1280×800. No other Maybe layout or behavior was changed.
- **Full-text support card:** Set the existing exclusion note widget to a three-line rendered height so its full copy is shown above the reserved PDF action row. Rebalanced only Full-text card widths to make room for the right-side support content, and reduced the attachment Listbox to one row so “ATTACHED PDF” plus a filename fit before the bottom action row. The three existing buttons stay in that reserved row.
- **Regression tests:** Added geometry/visibility checks after 1280×800 mapping: Maybe’s Keyboard Guide and Blind Integrity Gate fit within the support card, with the required wording; Full-text note’s height meets its requested rendered height, ends before the PDF row, all PDF buttons remain fully mapped within the card, and a selected valid synthetic PDF shows the queue badge plus one mapped filename above the action row. The selected-exclusion case also checks “reports excluded +1”.
- **Evidence:** Fresh 1280×800 synthetic captures are staged under `docs/ui-references/live-captures/phase4-maybe.png` and `phase4-fulltext.png`. Independent image inspection confirms the Maybe copy/gate and Full-text note/actions fit; the attached-PDF follow-on capture confirms the badge, heading, filename, and all three buttons.

- **Focus evidence:** The prescribed focus screenshots are not complete. A helper-launched Tk process does not receive genuine foreground Tab traversal here; the latest Screening focus image has no rust focus ring. Per the revised capture instructions, the two focus PNGs are left out and are marked “awaiting owner hand-capture”; no keyboard-focus pass is claimed.
- **Verification:** `python -m pytest -q` → **361 passed**; `python -m py_compile src/screening_workbench/app.py tests/test_app.py` and `git diff --check` pass. No checklist re-scores are claimed.


## Baseline read (2026-10-08, before this tab's first round)

Captured the live app at 1280×800 with four synthetic studies covering the states the checklist needs: Study A (decision=included, two linked reports, both full-text-included — grouping fixture), Study B (decision=excluded but linked to a full-text-included report — a decision/report conflict), Study C (no decision set, one link, report still pending full-text retrieval — an unresolved-link conflict plus a pending-retrieval fixture), Study D (no decision, no links — plain undecided state). No corpus records or screening data were used.

| # | Must show | Score | Evidence |
|---:|---|:---:|---|
| 1 | Study groups and report counts are visible | 0 | Each row read `{decision}{flag} -- {study_id}` only; no report count anywhere. |
| 2 | Reports are nested/grouped under the selected study | 0 | The study list was a flat `tk.Listbox`; no detail pane and no hierarchy existed. |
| 3 | Study and report are separate entities and counts | 1 | The data model keeps them distinct (`studies`/`reports` tables, separate IDs), but the UI never surfaced a report as its own visible entity at all. |
| 4 | Canonical occurrence choice is visible for selected report | 0 | No detail pane; no report selection existed at all. |
| 5 | All linked source occurrences remain listed as provenance | 0 | Same — no detail pane, no provenance list. |
| 6 | Selected branch/source is explicit and synthetic | 0 | Branch/source never appeared anywhere in the Studies tab. |
| 7 | Study decision state and rationale requirement are shown | 1 | Decision state is shown in the flat row (`included`/`excluded`/`no decision`); the rationale is required by `studies.set_study_decision` but, once entered, is never displayed back anywhere. |
| 8 | Linking alone does not imply a study is included | 2 | Visibly demonstrated: Study C's row reads `no decision [CONFLICT]`, not `included`, despite having an active link — the UI never silently flips a linked study to included. |
| 9 | Pending retrieval or unresolved links remain visible | 1 | The `[CONFLICT]` flag does surface an unresolved link, but a linked report's own pending-retrieval status is not shown anywhere in the Studies tab (only in Full-text). |
| 10 | Blind mode hides reviewer votes and decision-derived detail | 0 | Confirmed by code read, not assumed: zero `roles.is_blind()` references anywhere in `_build_studies_tab`/`_refresh_studies_tab`. Decision, rationale, actor, and conflict flag are all decision-derived data shown unconditionally. The report-link control also calls `reports.list_reports(self.conn)` directly with no blind gate, bypassing the Full-text tab's own blind lock (item 9 there) entirely. This is the same class of hole Full-text item 9 was — logged here, not fixed silently; it is its own round, not folded into round 1 (see Round plan below). |
| 11 | Keyboard-operable group, link, and canonical-selection controls | 1 | Group/canonical-selection controls don't exist yet to test. The existing link `Entry`+`Button` is keyboard-reachable via default Tk tab order (not independently verified this round) but is a plain position-number field, not a real picker. |
| 12 | Labels and state text remain understandable without color | 2 | Every row and flag is plain text with zero color-coding anywhere in the current implementation — nothing depends on color to be understood. |

**Baseline: 8/24.**

### Blind check (done during baseline, per directive)

Confirmed by reading `_build_studies_tab`/`_refresh_studies_tab`/`_link_selected_study` in full: there is no `roles.is_blind()` call anywhere in the Studies tab. Two concrete leaks follow from that: (1) `study_list`'s row text (decision + `[CONFLICT]` flag) is decision-derived and renders unconditionally regardless of blind state; (2) `_link_selected_study`'s report-position list comes from `reports.list_reports(self.conn)` with no gate, so a non-owner reviewer could resolve report positions (and thus infer another reviewer's full-text assessments) through the Studies tab's link control even while the Full-text tab itself is correctly locked. This is a real hole, not a hypothetical one — scored as item 10 = 0 above. It is **not** fixed in round 1; it gets its own round (see plan below), matching how Full-text item 9 was handled as a dedicated round rather than folded into a cosmetic pass.

### Round plan

Grouping sub-2 items by root cause (one region = one gap in one function, not one checklist row — cf. Duplicates' 3/4/5/6/12 region and Full-text's queue/detail region):

- **Round 1 (this round) — items 1, 2, 3, 4, 5, 6, 7, 9: the core hierarchy/detail region.** All eight items trace to the exact same root cause: no study→report hierarchy and no detail pane exist at all. The Tk feasibility notes call for exactly this fix ("Use a Treeview parent/child hierarchy for study → report groups... Show source occurrences in a detail pane for the selected report; use Radiobuttons for the single canonical occurrence/branch selection"). Largest and most central region by a wide margin — implemented below.
- **Round 2 — item 10: the blind-mode lock.** Its own round, per the directive and the Full-text item-9 precedent: mirror `_refresh_conflicts_tab`'s/`_refresh_fulltext_tab`'s blind branch (empty tree, cleared detail pane, disabled buttons, lock label), and close the report-position leak in `_link_selected_study`.
- **Round 3 — item 11: keyboard-operability of the new Round 1 controls.** Can't be verified (or fixed) until the Treeview/detail-pane/canonical-selection controls from Round 1 exist; a real OS-level Tab/click check follows the same pattern as Conflicts round 3 and Full-text round 3.
- Items 8 and 12 already score 2; not touched by any round unless a later round regresses them.

## Round 1 — items 1, 2, 3, 4, 5, 6, 7, 9 (2026-10-08)

- **Backend additions (no schema change):** `reports.occurrences_for_report(conn, report_id)` (all source occurrence IDs linked via `record_reports`, for provenance) and `studies.reports_for_study(conn, study_id)` (active report IDs linked via `report_study_links`, for the hierarchy and report counts). Both are new read-only query functions over existing tables from migrations 003/004 — no migration added.
- **Fix:** replaced the flat `tk.Listbox` with a `ttk.Treeview` (`show="tree"`) where each study is a parent row (`iid=study_id`) and its linked reports are child rows (`iid=report_id`) — distinct iid namespaces (`study_`/`report_` prefixes) keep the two entity types collision-free (item 3). The parent row's own text states its report count directly (item 1: `"included -- study_... (2 reports)"`). Reports nest as real Treeview children, not adjacent list rows (item 2).
- Added a `study_detail_text` pane below the tree, populated by a new `_render_study_detail`, bound to `<<TreeviewSelect>>`. Selecting a **study** row shows its ID, decision, conflict note if any, rationale text, and its linked-report list with titles (item 7: decision state *and* rationale are now both visibly shown, not just prompted for and discarded). Selecting a **report** child row shows its report ID, parent study, title, **canonical occurrence ID** (item 4), **explicit branch/source name** looked up from `branches.name` (item 6), **retrieval status** — explicitly "pending -- full-text not yet assessed" when not yet retrieved, or "retrieved -> {outcome}" once assessed (item 9) — and the **full source-occurrence provenance list** from `reports.occurrences_for_report`, with the canonical occurrence marked `(canonical)` among the others, never shown as the only linked source (item 5).
- `_selected_study_id` now resolves to the parent study whether a study row or one of its report children is selected (`self.study_tree.parent(iid) or iid`), so `Decide:`/`Link` keep acting on the right study regardless of which row a reviewer clicked. `_refresh_studies_tab` preserves the prior selection across a refresh (same pattern as Full-text/Conflicts) rather than resetting it.
- **Not touched this round:** item 10 (blind lock — its own round, see plan above) and item 11 (keyboard pass on the new controls — depends on this round landing first). The existing report-link `Entry`+`Button` control and its position-number semantics are unchanged.
- **Tests:** `test_studies_tab_reports_nested_under_study_with_counts` (two reports linked to one study appear as its Treeview children, the parent's own text states "2 reports", and `study_tree.parent(...)` confirms the hierarchy); `test_studies_tab_report_detail_shows_canonical_and_provenance` (selecting a report child shows its canonical occurrence, both linked source occurrences with the canonical one marked, an explicit branch name, "pending" before assessment, and "retrieved -> included" after); `test_studies_tab_study_detail_shows_decision_and_rationale` (study detail reads "No decision yet" before a decision, then shows both the decision and the exact rationale text after one is recorded). The existing `test_studies_tab_create_decide_link_flow` was updated to use `study_tree.selection_set(study_id)` instead of `study_list.selection_set(0)` and passes unchanged otherwise. Two new backend tests (`test_reports.py::test_occurrences_for_report_lists_all_provenance_including_canonical`, `test_studies.py::test_reports_for_study_lists_active_links_only`) cover the new query functions directly.
- **Live screenshots:** `docs/ui-references/studies/round-1-study-detail.png` shows the nested tree (report counts on every parent row, a conflict-flagged study, an empty study) with a study selected and its decision/rationale/linked-report list in the detail pane; `docs/ui-references/studies/round-1-report-detail.png` shows a report child selected with its canonical occurrence, branch, retrieval status, and provenance list (including the `(canonical)` marker) all visible with no clipping or overlap. Both use only synthetic records.
- **Verification:** full suite **261/261**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New scores — items 1, 2, 4, 5, 6: 2 each** (were 0 each). **Items 3, 7, 9: 2 each** (were 1 each). Recomputed from the table: 1(2)+2(2)+3(2)+4(2)+5(2)+6(2)+7(2)+8(2)+9(2)+10(0)+11(1)+12(2) = **21/24**.

## Round 2 — item 10 (2026-10-08)

- **Fix:** `_refresh_studies_tab` now mirrors `_refresh_conflicts_tab`/`_refresh_fulltext_tab`'s blind branch exactly — the Studies tab had zero `roles.is_blind()` references anywhere before this round (confirmed by code read during the baseline, not assumed). While blind: `self.study_tree` and `self._study_ids`/`self._study_row_by_id`/`self._report_ids_for_link`/`self._report_row_by_id` are all emptied (nothing left to leak, since `ttk.Treeview` has no `state=` option to disable in place — confirmed empirically, `tv.config(state="disabled")` raises `unknown option "-state"`); `study_detail_text` is cleared; `New study`, all three `Decide:` buttons, and `Link` are set to `state="disabled"`; a lock label reads "Studies is locked while blind mode is ON. The project owner must turn blind mode off to open this tab." While blind is OFF: unchanged from round 1, lock label clears, buttons re-enable.
- **Closed the leak found during the baseline's blind check:** `_link_selected_study`'s `self._report_ids_for_link` previously came from `reports.list_reports(self.conn)` with no gate at all — a blinded reviewer could resolve report positions (and so infer another reviewer's full-text assessments) through this control even while the Full-text tab itself was correctly locked. It is now populated from the same blind-gated refresh path, so it is empty while blind.
- **Defense in depth:** `_new_study`, `_study_decide`, and `_link_selected_study` each re-check `roles.is_blind(self.conn)` and refuse (with a `messagebox.showerror`) even if called directly, not just via the now-disabled buttons — same pattern as `_resolve_conflict`.
- **Tests:** `test_studies_tab_locked_while_blind` seeds another reviewer's (`revA`) decided, linked study, turns blind ON, and asserts the tree/detail pane/lookup lists are empty, all five controls are disabled, and the lock label is visible; calls `_new_study`/`_study_decide`/`_link_selected_study` directly while blind and asserts `studies.counts()` is unchanged (defense-in-depth); then turns blind OFF and asserts the tab re-populates and controls re-enable with no stale empty state.
- **Live screenshot:** `docs/ui-references/studies/round-2-live-blind-lock.png` shows the lock label, empty tree, empty detail pane, and all five disabled controls while blind is ON, with a synthetic `revA`-owned included study seeded (none of its decision/rationale data is visible).
- **Not touched:** the Studies tab's nav-badge count (`Studies  ({study_n})`) still shows a total study count while blind, unchanged by this round — same precedent as Full-text's own badge, which also kept showing a count through its round-4 blind lock rather than switching to "locked" text (only Conflicts' badge does that). `study_n` is a total count with no decision content, not a leak of reviewer-attributable data.
- **Verification:** full suite **262/262**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New score — item 10: 2** (was 0). Recomputed from the table: 1(2)+2(2)+3(2)+4(2)+5(2)+6(2)+7(2)+8(2)+9(2)+10(2)+11(1)+12(2) = **22/24**. Only item 11 (keyboard operability of the round-1 controls) remains below 2.

## Round 3 — item 11 (2026-10-08)

**Correction first:** Round 2's entry above states the running total as 22/24. That arithmetic is wrong. Recomputed with `python3`, not by hand: `sum({1:2,2:2,3:2,4:2,5:2,6:2,7:2,8:2,9:2,10:2,11:1,12:2}.values())` = **23**, not 22 — eleven items at 2 (=22) plus item 11 at 1 = 23/24. The per-item scores in Round 2's entry were all correct; only the sum was miscomputed.

- **Verified first (real OS-level checks, same pattern as Conflicts round 3 and Full-text round 3 — nothing here is assumed):** foregrounded the live app with a synthetic study/report fixture (2 linked occurrences, no progression assigned yet), bound a `<FocusIn>` trace in the live process, sent a genuine `win32api` mouse click on the Studies Treeview, then genuine `VK_TAB` keypresses. The trace recorded the real forward focus order: `Treeview -> Radiobutton(occurrence A) -> Radiobutton(occurrence B) -> Decide:Included -> Decide:Excluded -> Decide:Unresolved -> Entry(Link to report #) -> Button(Link)`. Every Round 1 control is a real, reachable, Tab-ordered stop — none were skipped or unreachable.
- **Build gap found during verification (not just a pass/fail check):** item 4 ("Canonical occurrence choice is visible") was satisfied in Round 1 by read-only text only — there was no actual *control* to select or change the canonical occurrence, so item 11's "canonical-selection controls" had nothing to verify. Per the Tk feasibility notes ("use Radiobuttons for the single canonical occurrence/branch selection"), built one: a new `study_canonical_frame` of `ttk.Radiobutton`s, populated in `_render_study_detail` for any selected report with 2+ linked occurrences (a single-occurrence report has nothing to choose among, so no radio buttons render). Wired to the existing, already-tested backend: `reports.assign_progression` for a report's first canonical pick (no rationale needed — nothing to justify overriding yet), `reports.correct_progression` with a required rationale for re-selecting an already-progressed report (mirrors the study-decision rationale pattern; a cancelled rationale prompt reverts the radio selection, not a silent overwrite).
- Round 2's blind-lock branch in `_refresh_studies_tab` now also clears `study_canonical_frame`'s children while blind (it held none before this round, since the control didn't exist); `_select_canonical_occurrence` re-checks `roles.is_blind()` and refuses directly, same defense-in-depth pattern as the three existing handlers.
- **Tests:** `test_studies_tab_canonical_radiobuttons_select_and_correct` — a 2-occurrence, unprogressed report shows exactly two radio buttons with none pre-selected; selecting one calls `assign_progression` (no rationale prompt) and the detail text updates to the new canonical occurrence; selecting the other afterward requires a rationale (`correct_progression` path) and updates again; a separate single-occurrence report shows zero radio buttons. Full suite re-run confirms `test_studies_tab_locked_while_blind` still passes unchanged (the now-present canonical frame is empty while blind, same as before this round when it didn't exist).
- **Live screenshots:** `docs/ui-references/studies/round-3-live-tab-focus-radiobutton.png` shows a real Tab keypress landing on the first canonical-selection Radiobutton with a visible dotted focus rectangle around its text; `docs/ui-references/studies/round-3-live-tab-focus-link.png` shows a real Tab keypress landing on the Link button with a visible focus border, confirmed reachable from the Link entry field. Both from the same live, synthetic-data run as the focus trace above.
- **Verification:** full suite **263/263**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New score — item 11: 2** (was 1). Recomputed with `python3`: `sum({1:2,2:2,3:2,4:2,5:2,6:2,7:2,8:2,9:2,10:2,11:2,12:2}.values())` = **24/24**. **Studies tab: closed.**

# Maybe re-review (12 items)

## Baseline read (2026-10-08, before this tab's first round)

Captured the live app at 1280×800 with four synthetic occurrences: two of the current reviewer's (`owner`) own maybe votes, one of `owner`'s own non-maybe (included) vote (must not appear in the queue), and one `maybe` vote cast by a different reviewer (`revA`) (must never appear for `owner`). `screening.list_maybe_decisions_for_reviewer` is reviewer-scoped by its `reviewer_id` parameter, not by blind state, so correctness here was additionally verified directly against the domain layer (not just read from the screenshot): calling it for `owner` returns exactly the 2 owner records regardless of `roles.set_blind`, and calling it for `revA` returns exactly `revA`'s own 1 record — confirmed empirically with blind toggled both ways, not assumed from the absence of a visible leak.

| # | Must show | Score | Evidence |
|---:|---|:---:|---|
| 1 | Queue title states it contains the current reviewer's own maybe-votes | 2 | Header text reads "Your own 'maybe' decisions, for a second look (blind-safe -- never another reviewer's)."; the nav badge also reads "Maybe re-review (2)". |
| 2 | Only the current reviewer's own records/votes are listed | 2 | Live screenshot shows exactly the 2 `owner` maybe records; `revA`'s maybe record and `owner`'s own non-maybe include are both correctly absent. |
| 3 | No other reviewer's vote, reason, title, or count is exposed | 2 | Confirmed by the same screenshot and the direct domain-layer check above -- `revA`'s title never reaches `owner`'s query result. |
| 4 | Selected record is clearly marked synthetic | 0 | `_build_maybe_tab`'s `tk.Listbox` has no selection-driven detail pane at all; nothing is marked synthetic anywhere in the tab. |
| 5 | Current own Maybe decision and timestamp are visible | 0 | No detail pane; `list_maybe_decisions_for_reviewer` doesn't even select `sv.created_at` from `screen_votes` yet, so there's no timestamp to show. |
| 6 | Include/Maybe/Exclude re-decision controls are present | 1 | Only `Include`/`Exclude...` buttons exist; no `Maybe` (re-affirm/defer) control, unlike the three-way decision bar at title/abstract and full-text stages. |
| 7 | Exclude requires one project reason before saving | 2 | `_maybe_decide("exclude")` already calls `self._prompt_exclusion_reason()` -- the same closed 1-7 taxonomy picker used at every other stage -- before `screening.cast_vote`. |
| 8 | Final Include/Exclude removes item from current maybe queue | 2 | `cast_vote` supersedes the prior maybe vote; `_refresh_maybe_tab` re-queries `list_maybe_decisions_for_reviewer` on every `refresh_all_tabs`, so a decided record drops out immediately. Functionally correct, confirmed by code path, not just assumed. |
| 9 | Search, counts, and status are computed after own-vote filtering | 1 | The nav badge count is correct (reviewer-scoped), but there is no search box and no in-tab status/count text at all. |
| 10 | Keyboard controls, focus, and status announcement are visible | 1 | Standard Tk tab order likely reaches the Listbox and both buttons, but not yet verified with a real OS-level check (no detail pane or re-decision controls exist yet to include in that check). |
| 11 | All states have text labels and adequate contrast | 2 | Everything is plain text; nothing currently depends on color to be understood. |
| 12 | Blind isolation is presented as a non-negotiable gate | 2 | Genuinely non-negotiable, not merely stated: `list_maybe_decisions_for_reviewer(conn, reviewer_id)` only ever takes `self.reviewer_id` -- there is no code path in `_refresh_maybe_tab`/`_maybe_decide` that could pass another reviewer's ID, so blind state cannot change this tab's exposure (verified empirically above). The header text also states this explicitly. |

**Baseline: 17/24.**

### Blind check (done during baseline, per standing practice)

Verified, not assumed: `list_maybe_decisions_for_reviewer` is parameterized strictly by `reviewer_id`, and every call site in `app.py` passes `self.reviewer_id` (the app's own fixed identity for this session) -- never a value sourced from elsewhere. Toggling `roles.set_blind` and re-querying directly against the domain layer for both `owner` and `revA` confirmed each only ever sees their own maybe votes, independent of blind state. **No hole found.** Unlike Conflicts/Full-text/Studies (which show multiple reviewers' data and needed an explicit blind-on lock), Maybe re-review is single-reviewer-scoped by construction -- there's nothing cross-reviewer to lock, so no blind-lock round is needed for this tab.

### Round plan

- **Round 1 (this round) — items 4, 5, 6: the selected-record detail region.** All three trace to one gap: no selection-driven detail pane exists. Add one (Text pane per the Tk feasibility notes) showing the synthetic marker, the own decision + timestamp (`sv.created_at`, not yet selected by the backend query), and extend the decision bar to a real three-way Include/Maybe/Exclude (reusing the Screening decision-bar pattern, per the feasibility notes). Largest, most central region.
- **Round 2 — item 9: search + status/count region.** A search box filtering the (already reviewer-scoped) queue, plus explicit in-tab status/count text -- separate concern from the detail pane, smaller and independent.
- **Round 3 — item 10: keyboard verification of rounds 1-2's new controls.** Can't be verified (or fixed) until the detail pane, three-way decision bar, and search box exist; a real OS-level Tab/click check follows the same pattern as Conflicts/Full-text/Studies round 3.
- Items 1, 2, 3, 7, 8, 11, 12 already score 2; not touched by any round unless a later round regresses them.

## Round 1 — items 4, 5, 6: selected-record detail region (2026-10-08)

- **Backend:** `screening.list_maybe_decisions_for_reviewer` now also selects `sv.created_at`, returned as `decided_at` per record -- needed for item 5's timestamp display; previously only `title`/`year`/`journal` were projected.
- **Fix:** replaced the flat `tk.Listbox` with a `ttk.Treeview` (`show="tree"`) keyed by occurrence ID (per the Tk feasibility notes: "stable occurrence IDs belong in item data, not row indexes" -- the prior `curselection()`-index lookup into a parallel list was exactly the pattern the notes warn against). Added a `maybe_detail_text` pane bound to `<<TreeviewSelect>>` via a new `_render_maybe_detail`: shows the record's title/year/journal, its occurrence ID, and **"Your decision: maybe, cast {timestamp}"** (item 5) -- confirmed live with a real ISO timestamp, not a placeholder.
- **Item 4 (synthetic marking) -- scored via evidence, not a hardcoded string:** following the Full-text item 12 precedent (closed as documentation-only, "not a production banner" -- a real reviewer's genuine literature record is obviously not synthetic, so labelling every record "synthetic" in production code would be actively misleading), this round does **not** add literal "(synthetic)" text to the live detail pane. The requirement is satisfied the same way Full-text's equivalent item was: this round's capture uses only clearly-synthetic seed data (`Synthetic maybe pick A/B -- owner`, fictitious journals/authors), screenshotted and logged as such here.
- **Item 6:** extended the two-button `Include`/`Exclude...` bar to a real three-way `Include`/`Maybe (keep deferred)`/`Exclude...` bar, restyled to the same colored `tk.Button`+`TOKENS` decision-bar pattern as Screening/Full-text (not generic `ttk.Button`s). Re-affirming `Maybe` on an already-maybe record is a real action, not a no-op or disabled state: `screening.cast_vote` already supersedes the prior vote and inserts a fresh one even when the decision is unchanged, so re-affirming refreshes the timestamp and the record stays in the queue (non-terminal, per the reference's "Maybe remains pending" language used elsewhere in this log).
- **Tests:** `test_maybe_tab_detail_pane_shows_decision_and_timestamp` (selecting a record shows its title, occurrence ID, and a real `decided_at` timestamp string sourced from the backend, not just the label); `test_maybe_tab_three_way_decision_bar_re_affirms_maybe` (re-affirming maybe via the bar supersedes the vote with a new `vote_id`, decision stays `maybe`, and the record remains in `_maybe_occurrence_ids` -- confirms non-terminal re-decision, not a dead button). `test_maybe_tab_lists_and_re_decides_own_maybe_votes` (pre-existing) updated for the Treeview API (`maybe_tree.selection_set(occurrence_id)` instead of `maybe_list.selection_set(0)`) and passes unchanged otherwise.
- **Live screenshot:** `docs/ui-references/maybe-re-review/round-1-live-detail-decision-bar.png` shows the Treeview queue (2 synthetic owner records), the selected record's detail pane (title, metadata, occurrence ID, decision + real timestamp), and the three colored decision-bar buttons, on synthetic data only.
- **Verification:** full suite **265/265**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New scores — items 4, 5, 6: 2 each** (were 0, 0, 1). Recomputed with `python3`: `sum({1:2,2:2,3:2,4:2,5:2,6:2,7:2,8:2,9:1,10:1,11:2,12:2}.values())` = **22/24**. Items 9 (search/status) and 10 (keyboard verification, depends on round 1 landing) remain below 2.

## Round 2 — item 9: search + status/count region (2026-10-08)

- **Fix:** `_refresh_maybe_tab` now fetches once into `self._maybe_all_records` (the reviewer-scoped result of `list_maybe_decisions_for_reviewer`, unchanged) and delegates rendering to a new `_render_maybe_queue`, which filters that **in-memory** list against a new `maybe_search_var` (title/year/journal substring, case-insensitive) and renders only the matches into `maybe_tree`. The search box never issues its own database query -- it filters strictly on top of the own-vote filter already applied, matching the feasibility notes ("Query the current reviewer's own active Maybe vote set before populating the queue, search index, badge, or status text"). `_maybe_occurrence_ids`/`_maybe_record_by_id` stay the full reviewer-scoped set regardless of the search text, so blind/reviewer isolation (items 2/3/12) cannot be weakened by narrowing or widening the query.
- A new `maybe_status_label` reads `"{total} of your maybe record(s) pending re-review."` with no search text entered, or `'Showing {shown} of {total} of your maybe records matching "{query}".'` once a search is typed -- both counts computed from the same already-filtered `_maybe_all_records`, so the status text can never overstate what the own-vote filter allows.
- **Tests:** `test_maybe_tab_search_filters_queue_and_updates_status` -- two synthetic records seeded, confirms the unfiltered status text and full queue, then narrows with a search term and asserts the queue shows exactly the match, the status text names both the shown and total counts plus the query, and critically that `_maybe_all_records`/`_maybe_occurrence_ids` (the backing reviewer-scoped data) stay at their full size throughout -- only the rendered tree narrows. Clearing the search restores the full queue and status text.
- **Live screenshot:** `docs/ui-references/maybe-re-review/round-2-live-search-status.png` shows a search for "habitat" against 3 synthetic maybe records narrowing the Treeview to the 2 matches, with the status text reading `Showing 2 of 3 of your maybe records matching "habitat".` and the nav badge still correctly reading the unfiltered total `(3)`.
- **Verification:** full suite **266/266**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New score — item 9: 2** (was 1). Recomputed with `python3`: `sum({1:2,2:2,3:2,4:2,5:2,6:2,7:2,8:2,9:2,10:1,11:2,12:2}.values())` = **23/24**. Only item 10 (keyboard verification of rounds 1-2's new controls) remains below 2.

## Round 3 — item 10 (2026-10-08)

- **Verified first (real OS-level checks, same pattern as Conflicts/Full-text/Studies round 3 -- nothing here is assumed):** foregrounded the live app with a synthetic 2-record maybe queue, bound a `<FocusIn>` trace in the live process, sent a genuine `win32api` mouse click on the search entry, then genuine `VK_TAB` keypresses. The trace recorded the real forward focus order: `Entry(Search) -> Treeview(queue) -> Button(Include) -> Button(Maybe) -> Button(Exclude)`, then wrapping out of the tab to the surrounding chrome (`Export package...`). Every interactive control from rounds 1-2 is a real, reachable, Tab-ordered stop -- none were skipped or unreachable.
- **No gap found -- verification-only round, no code change:** the read-only, `state="disabled"` detail pane (`maybe_detail_text`) correctly does not appear in the Tab order at all -- it is display content, not an interactive control, so Tk's default focus traversal skipping a disabled Text widget is the right behavior here, not a missed stop. All five actionable controls (search, queue, three decision buttons) are reachable; none needed a fix.
- **Live screenshot:** `docs/ui-references/maybe-re-review/round-3-live-tab-focus-include.png` shows a real Tab keypress landing on the `Include` button with a visible focus border, reached via `Entry -> Treeview -> Include` from a direct click on the search field.
- **Verification:** full suite **266/266**, unchanged by this round; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New score — item 10: 2** (was 1). Recomputed with `python3`: `sum({1:2,2:2,3:2,4:2,5:2,6:2,7:2,8:2,9:2,10:2,11:2,12:2}.values())` = **24/24**. **Maybe re-review tab: closed.**

## Directive F — Phase 2 PRISMA & audit two-card convergence

- **Test-first:** added `test_prisma_tab_has_flow_and_audit_cards_without_moving_controls`; it first failed with the expected absent card container. It pins two card parents and positions, including the preserved nested diagram frame, count preview, watermark, audit tree, and package-export button.
- **Implementation:** rework the existing scrollable-tab content frame as equal-width left PRISMA and right audit/access cards, both `Card.TFrame`. Preserve count snapshot and diagram code paths and scope-gated audit behavior. This follow-up moves the flow heading/subtitle/description into distinct grid rows after the summary; the count text gets a dedicated inner vertical scrollbar so its reconciliation output remains available without displacing the diagram. The outer Canvas remains responsible for scrolling the full page and audit list. No count, report/audit authorization, blind-gating, or export semantics changed.
- **Test-first:** `test_prisma_flow_diagram_enters_reference_viewport_after_counts` was added after the prior live screenshot showed the flow section below the initial fold and its heading crowding count text. It requires the full 205px flow canvas in the initial 1280×800 viewport, the separate counts scrollbar, equal card widths, and non-overlap between counts and flow heading. It failed before the grid-row separation/inner-scroll fix and passes now.
- **Live evidence:** `prisma-audit-round2-live.png` is a fresh foreground 1280×800 capture of the populated synthetic fixture. It shows the whole 205px PRISMA flow canvas beneath the separately scrollable counts pane, equal-width cards with a distinct flow heading and no count overlap, readable flow labels/values, and visible owner audit events; further audit rows remain on the audit Treeview scrollbar. Footer retains `Local only · prisma-round1-synthetic.sqlite`. No item score is claimed or changed in this round.
- **Verification:** viewport/non-overlap, counts, audit-owner scope, blind-lock and outer-scroll tests pass; full suite **347 passed**, `py_compile` and `git diff --check` pass. Both screenshot fixtures and helpers were outside the repo and removed; only PNG evidence was added to the reference package in this round.

## Directive F — Phase 2 PRISMA & audit card migration follow-up

**Code and automated evidence**
- Added a synthetic fixture with one not-retrieved report and one full-text-excluded report; its flow-box assertions confirm shared `prisma_flow_boxes` counts render visibly in the two right-side boxes.
- Restored the values, the complete “official watermarked PRISMA diagram and audit log” copy, and an export note sized for the narrower audit card. Added a truthful “Live project data · preview only · not synthetic” label. The counts pane now has a compact viewport with an independent scrollbar; snapshot content, count calculations, export behavior, and blind-gate semantics remain unchanged.
- Verification: `python -m pytest tests/test_app.py -k 'prisma' -q` → **16 passed**; full suite → **350 passed**. `py_compile` and `git diff --check` pass.

**Live evidence and remaining gap**
- `prisma-audit-round4-live.png` and refreshed `live-captures/prisma.png` are fresh 1280×800 owner/blind-OFF views. Pixels show all flow boxes, including **Reports not retrieved: 0** and **Reports excluded (full text): 1**. Real OS Tab traversal visibly reached the in-tab Export package button with its dotted ttk focus cue.
- The former blind-on capture showed the audit panel locked, but also showed project-wide PRISMA counts and diagram. That aggregate visibility was later found to violate blind-review isolation; this capture is not valid evidence that all blind-mode surfaces were protected.
- The live fixture used for this check was outside the repository and was removed after capture. `test_prisma_tab_audit_log_locked_while_blind` also passes. No checklist score change is claimed; the blind-on image is evidence for owner review and the user remains the scorer.

## Public-release audit correction — 2026-10-12

The PRISMA tab and global tab badges previously exposed project-wide totals to
non-owner reviewers while blind mode was on. The app now locks those badges,
clears the PRISMA counts and flow diagram, and restores the normal view after
unblinding. A focused Tkinter regression test and a temporary synthetic UI
scenario cover the lock and restore paths. The two obsolete blind-on captures
were removed: one exposed a personal OneDrive path in a folder picker, and the
other showed the blind-mode aggregate leak described above. No replacement
screenshot was captured during this audit.

### Post-security-merge blind behavior re-check (2026-10-12)

- **Fixture/method:** Created a fresh temporary synthetic project with two occurrences, two reviewers, blind mode enabled before either reviewer voted, then recorded reviewer-a `include` and reviewer-b `exclude` with a synthetic reason. Ran a separate reviewer UI instance, a blind partial package export, direct raw-vote and reviewer-policy re-queries, and an owner UI/policy view. No user corpus or production project data was used.
- **Lock on first vote:** Attempting to unblind after the first vote raised `PermissionError: blind mode is locked once screening has begun`; no state change occurred. Regression test: `test_first_vote_activates_blind_mode_lock` (`tests/test_pre_release_gates_unittest.py`).
- **PRISMA/Kappa blind visibility:** For an ordinary reviewer while blind, PRISMA tab and badge were LOCKED, counts showed the locked placeholder (while the underlying direct PRISMA count query still returned the synthetic total of 2), watermark said locked/hidden, diagram and flow boxes were empty, and the kappa strip was unmapped. Regression tests: `test_blind_reviewer_prisma_aggregates_and_watermark_are_locked` (`tests/test_app.py`) and `test_kappa_strip_is_hidden_in_blind_project_and_owner_prisma_stays_visible` (`tests/test_app.py`).
- **Blind partial export:** `test_blind_partial_export_contains_only_the_requesting_reviewers_own_reason` (`tests/test_export.py`) verifies the requester's own vote/reason remains while another reviewer's vote/reason and project-wide artifacts are absent; `test_blind_partial_export_omits_project_wide_artifacts_and_counts` (`tests/test_pre_release_gates_unittest.py`) checks project-wide artifacts and count/completeness metadata. The fresh export contained reviewer-a's own include vote and omitted reviewer-b's vote/reason; it omitted `audit-log.jsonl`, `report-study-links.csv`, `prisma-flow.svg`, and attachment files.
- **Direct data-layer re-query:** Raw `votes_for_occurrence` returned both reviewer rows while blind; `visible_votes_for_reviewer(... viewer='reviewer-a', is_blind=True, is_owner_or_auditor=False)` returned reviewer-a only, confirming blinded absence of reviewer-b as well as presence of reviewer-a. With blind visibility disabled in the owner-policy query, both reviewer IDs were present. Existing regression tests: `test_blind_isolation_hides_other_reviewer_vote`, `test_unblinded_reviewer_sees_all`, and `test_owner_sees_all_even_while_blind` (`tests/test_screening.py`).
- **Owner restoration:** The owner continues to see PRISMA during blind mode, as asserted by `test_kappa_strip_is_hidden_in_blind_project_and_owner_prisma_stays_visible`. Post-vote owner unblinding is prohibited by the lock, so restoration after toggling OFF is not reachable in this state. Owner-context re-check confirmed aggregate counts, preview watermark, diagram/flow boxes, PRISMA badge, and both votes in the unblinded owner-policy re-query. No behavior differed from the security review's claims.
- **Verification:** Fresh synthetic UI/data-layer check passed. Full suite on merged main: **384 passed in 114.24s**; `git diff --check` passes. No checklist scores were re-scored.

# PRISMA & audit (12 items)

## Baseline read (2026-10-08, before this tab's first round)

Captured the live app at 1280×800 with a deliberately rich synthetic fixture: two branches (`default`, database class; `b2`, register class), an identification/removal/screening spread (include, exclude-with-reason, maybe, an exact-match pre-screen duplicate pair auto-merged by `dedup.run_exact_and_fuzzy_detection`, and an unresolved title/abstract conflict between two reviewers), full-text retrieval across sought/not-retrieved/assessed-included/**assessed-maybe** (the last one specifically to exercise Directive C's "maybe buckets to pending" semantics in the baseline, not the pre-Directive-C behavior), and study-level decisions (one included, one unresolved-link). `dedup`/`screening`/`reports`/`studies` domain calls only -- no screening-data files touched.

| # | Must show | Score | Evidence |
|---:|---|:---:|---|
| 1 | View is clearly labeled synthetic and not a live project export | 1 | The existing muted note ("this tab is a read-only counts snapshot, not a separate export path") partially addresses the second half, but nothing frames this view as a non-authoritative preview distinct from the watermarked export, and nothing ties it to a snapshot identity. |
| 2 | Flow diagram is generated from one named immutable snapshot | 0 | No diagram renders in the live tab at all. `export.export_prisma_svg(conn)` already exists and builds an accessible, title/desc-labeled SVG from the same `prisma.full_snapshot` -- but it's wired only into the export package, never rendered into the UI. |
| 3 | Identification/removal/screening equations reconcile exactly | 1 | `prisma.verify_invariants` checks this exact equation per branch and the tab prints "No invariant violations." when it holds (confirmed live: baseline screenshot shows `default: identified=7 removed=1 prescreen_pending=0 screening_pending=3 screened=3` -- 7 = 1+0+3+3) -- but the reconciling arithmetic itself is never shown, only a pass/fail note. |
| 4 | Report retrieval and assessment counts reconcile exactly | 1 | Same mechanism and same gap: `verify_invariants` checks `reports_sought = assessed + not_retrieved + pending` (confirmed live: 4 = 2+1+1, with the full-text-maybe report correctly in the pending bucket per Directive C) and would flag a violation, but the equation isn't displayed, only pass/fail. |
| 5 | Study and included-report counts use distinct entity IDs | 2 | Already two separately labeled lines with their own counts ("Reports included: 2" vs "Studies included: 1") -- distinct entities, never conflated. |
| 6 | Append-only audit log shows sequence, actor, timestamp, and event type | 0 | No audit log view exists anywhere in the live tab. The `events` table already has all four columns (`sequence`, `actor`, `occurred_at`, `event_type`) and `export.export_audit_log_jsonl` already reads them for the export package -- just never rendered into the UI. |
| 7 | Audit access scope is explicit; no unauthorized reviewer votes are shown | 0 | Nothing to gate yet since no audit view exists. Confirmed empirically this is a real future risk, not hypothetical: `events` rows for `screening.vote_cast` carry `actor` (the reviewer ID) and a payload with `decision`/`occurrence_id` -- building item 6 without gating by `roles.is_owner_or_auditor(conn, actor, "audit_read")` (the scope already defined in `roles.VALID_SCOPES` for exactly this) would immediately create the same class of hole Full-text item 9 / Studies item 10 were. |
| 8 | Watermark and export status are visible | 0 | Nothing shown. `export._watermark(conn)` (max `events.sequence`) already exists and is what the export package binds its SVG/audit-log/manifest to -- just never surfaced in the UI. |
| 9 | Counts and links remain legible in grayscale/print and at 200% zoom | 2 | Plain monospace black-on-white text in a `tk.Text` widget; nothing depends on color. No links exist yet to test, but nothing currently blocks legibility. |
| 10 | Diagram has title/description and text-accessible labels | 0 | No diagram renders in the live tab (follows from item 2) -- though `export_prisma_svg`'s SVG already has `<title>`/`<desc>` and per-box text labels, satisfying this once it's actually rendered. |
| 11 | Keyboard access and focus remain visible in every control | 1 | Only one control (`Export package...`) plus a disabled `Text` pane exist today; standard Tk tab order likely reaches the button, but not yet verified with a real OS-level check, and there's nothing else to check until later rounds add controls. |
| 12 | Incomplete/pending states would be disclosed rather than silently treated as terminal | 2 | "Reports pending: 1" is an explicit, separate line -- confirmed live showing the full-text-maybe report correctly counted as pending, not silently dropped or miscounted as terminal. |

**Baseline: 10/24.**

### Blind check (done during baseline, verified not assumed)

Toggled `roles.set_blind` and re-queried the domain layer directly, not just read from the screenshot: `prisma.full_snapshot(conn)` and `prisma.verify_invariants(conn)` return byte-identical results blind ON vs OFF -- confirmed with `snap_before == snap_after` and `viol_before == viol_after` both `True`. These are pure aggregate counts with no reviewer parameter anywhere in their call signatures, so there is no code path for blind state to change what they return. **No hole found in what the tab currently shows** -- same "blind-safe by construction" class as Maybe re-review, logged clean per that precedent.

However, this check also surfaced a **real future risk, not a hypothetical one**, which the round plan below treats as load-bearing: a direct query confirmed `events` rows for `screening.vote_cast` carry `actor` (the casting reviewer's ID) and a payload containing `decision`/`occurrence_id` per vote. The moment item 6's audit log view is built, it would expose exactly this reviewer-attributable, vote-level data unless gated from the start -- the same class of hole Full-text item 9 and Studies item 10 were, both found only after the UI control existed. Unlike those two cases, this one is being designed with the gate built in from the first line of Round 1's audit-log code, using the scope already defined for exactly this (`roles.is_owner_or_auditor(conn, actor, "audit_read")`, `"audit_read"` already in `roles.VALID_SCOPES`) -- not bolted on as a follow-up round.

### Round plan

- **Round 1 (this round) — items 1, 6, 7, 8: the audit log + watermark/preview-framing region.** Largest and most central gap, and the one carrying the real blind-integrity risk identified above -- built with the `audit_read`/blind gate from the start, not after. Adds a read-only `ttk.Treeview` audit log (sequence/time/actor/event type columns, per the feasibility notes) sourced from the `events` table, gated the same way `export_decisions_csv` already gates reviewer-identity exposure; a watermark/sequence label bound to `export._watermark(conn)`; and a short "preview, not the authoritative export" framing note (items 1/8 share the same watermark-sequence concept, so they land together).
- **Round 2 — items 2, 10: the flow diagram region.** Render `export.export_prisma_svg`'s same snapshot-bound box/label/value model into the live tab (Canvas or embedded SVG render, per the feasibility notes) rather than leaving it export-package-only. Depends on nothing from Round 1; independent region.
- **Round 3 — items 3, 4: equation-display refinement.** Show the literal reconciling arithmetic (e.g. `7 = 1+0+3+3`) alongside the existing pass/fail invariants note, for both the identification/screening and report-retrieval equations. Smaller, cosmetic-adjacent, independent of Rounds 1-2.
- **Round 4 — item 11: keyboard verification of every new control from Rounds 1-3.** Can't be verified (or fixed) until those controls exist; a real OS-level Tab/click check follows the same pattern as every prior tab's final round.
- Items 5, 9, 12 already score 2; not touched by any round unless a later round regresses them.

## Round 1 — items 1, 6, 7, 8: audit log + watermark/preview-framing region (2026-10-08)

- **Backend additions (no schema change):** `export.watermark_sequence(conn)` -- a public wrapper around the existing private `_watermark(conn)` so the UI isn't reaching into a private function; `export.list_audit_events(conn, through_sequence=None)` -- returns `events` rows (sequence/event_id/event_type/occurred_at/actor) as dicts for UI rendering, mirroring `export_audit_log_jsonl`'s query. Neither function has any notion of blind state or scope -- same pattern as `export_audit_log_jsonl`/`export_decisions_csv`'s `can_see_all` parameter: the caller decides whether to call them at all.
- **Fix (items 1/8):** a new `prisma_watermark_label` reads `'Preview as of watermark sequence {N} -- not the authoritative export. Use "Export package..." for the official watermarked PRISMA diagram and audit log.'`, bound to `export.watermark_sequence(conn)` -- confirmed live matching the export package's own watermark value (same function, both call sites).
- **Fix (item 6):** a new `ttk.Treeview` (`show="headings"`) with four separate labeled columns -- Seq, Time, Actor, Event type -- per the Tk feasibility notes, populated from `export.list_audit_events`. Not a mockup: the baseline capture's real `project.owner_set`/`import.csv.committed`/`screening.vote_cast`/`report.*` events all appear with their real sequence numbers and timestamps.
- **Fix (item 7, built with the gate from the start, not bolted on after):** a new `_refresh_prisma_audit_log` enforces two independent checks before populating the tree: (1) **locked while blind for everyone, no role bypass** -- `roles.is_blind(conn)` empties the tree and shows "Audit log is locked while blind mode is ON. The project owner must turn blind mode off to open it.", same lock-label discipline and no-owner-exception as Conflicts/Full-text/Studies; (2) **scope-gated when not blind** -- `roles.is_owner_or_auditor(conn, actor, "audit_read")` (the scope `export_decisions_csv` already uses, already in `roles.VALID_SCOPES`) must hold, or the tree stays empty with "Audit log requires the audit_read role, granted by the project owner." instead of a silent empty list. Only the audit log is gated this way -- the counts/invariants portion above it is unconditional, since the baseline's blind check already confirmed those are pure blind-independent aggregates.
- **Tests:** `test_prisma_tab_watermark_label_matches_export_watermark` (label text contains the real `export.watermark_sequence` value and the "not the authoritative export" framing); `test_prisma_tab_audit_log_shows_events_for_owner` (owner sees real events including another reviewer's `screening.vote_cast`, with the scope label stating "owner/audit_read scope"); `test_prisma_tab_audit_log_requires_scope_for_non_owner` (a second `ScreeningWorkbenchApp` instance opened as a non-owner reviewer on the same DB sees zero rows and the explicit scope-required message); `test_prisma_tab_audit_log_locked_while_blind` (populated while not blind, empties with the lock message once blind turns on, counts stay correct throughout, re-populates cleanly once blind turns back off). The pre-existing `test_prisma_tab_shows_live_counts_snapshot` passes unchanged.
- **Live screenshots:** `docs/ui-references/prisma-audit/round-1-live-audit-log-owner.png` shows the watermark label, counts, and the full 8-row audit log (including a different reviewer's `screening.vote_cast`) visible to the owner; `round-1-live-audit-log-blind-locked.png` shows the identical fixture with blind ON -- the audit log empty with the lock message, while the counts snapshot above it remains fully populated and correct.
- **Verification:** full suite **270/270**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New scores — items 6, 7, 8: 2 each** (were 0 each). **Item 1: 2** (was 1). Recomputed with `python3`: `sum({1:2,2:0,3:1,4:1,5:2,6:2,7:2,8:2,9:2,10:0,11:1,12:2}.values())` = **17/24**. Items 2/10 (flow diagram), 3/4 (equation display), and 11 (keyboard verification) remain below 2.

## Round 2 — items 2, 10: flow diagram region (2026-10-08)

- **Refactor first (no behavior change):** extracted `export.prisma_flow_boxes(conn)` -- the box geometry/label/value list `export_prisma_svg` used to build inline -- into its own function, plus module-level `export.PRISMA_SVG_TITLE`/`PRISMA_SVG_DESC` constants. `export_prisma_svg` now calls `prisma_flow_boxes` and builds the SVG `<rect>`/`<text>` markup from it; output is unchanged (`test_svg_has_accessible_title_and_description` passes unmodified). This is the single shared source both the export SVG and the live Tk diagram draw from, going forward.
- **Fix (item 2):** a new `ttk.Canvas` ("Flow diagram" section, between the counts snapshot and the audit log) is redrawn by `_refresh_prisma_diagram` from `export.prisma_flow_boxes(self.conn)` on every refresh -- real `create_rectangle`/`create_text` items at the SVG's own coordinates, not an image. Because both the export package and the live diagram call the same function against the same `prisma.full_snapshot`, they can never independently disagree (confirmed live: the baseline's "Reports sought: 2" / "Reports included: 1" counts match the diagram's boxes exactly). Per the Tk feasibility notes ("Draw the flow on a scrollable Canvas... each box must have a text label and count, not a color-coded meaning"): the canvas has a vertical `ttk.Scrollbar` (the full 520x650 geometry doesn't fit in one screen), and every box fill is the same plain white regardless of its value -- nothing is color-coded.
- **Fix (item 10):** real `ttk.Label` widgets for `export.PRISMA_SVG_TITLE` ("Screening Workbench PRISMA 2020 flow diagram") and `PRISMA_SVG_DESC` sit above the canvas as actual text, not canvas-only content or alt text a screen reader can't reach -- mirroring the SVG's own `<title>`/`<desc>`. Each box's label and value are themselves separate Canvas text items (real text, not raster/vector art with no text layer), confirmed via `canvas.itemcget(item, "text")` in the new test.
- **Tests:** `test_prisma_tab_flow_diagram_matches_export_boxes` -- seeds 2 occurrences with one included, asserts every box from `export.prisma_flow_boxes` has both its label and its value present as real Canvas text items, and specifically checks the `box-identified` value is `2` (not stale or independently computed). All five pre-existing PRISMA tests and all 17 `test_export.py` tests pass unchanged.
- **Live screenshots:** `docs/ui-references/prisma-audit/round-2-live-flow-diagram-top.png` shows the title/description labels and the canvas's first three boxes (Records identified: 3, Duplicates removed: 0, Reports sought: 2), reconciling exactly with the counts text above; `round-2-live-flow-diagram-scrolled.png` shows a real scrollbar-thumb drag revealing the remaining boxes (Reports assessed/excluded side by side, Reports included, Studies included), confirming the canvas is genuinely scrollable, not just tall.
- **Verification:** full suite **271/271**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New scores — items 2, 10: 2 each** (were 0 each). Recomputed with `python3`: `sum({1:2,2:2,3:1,4:1,5:2,6:2,7:2,8:2,9:2,10:2,11:1,12:2}.values())` = **21/24**. Items 3/4 (equation display) and 11 (keyboard verification) remain below 2.

## Round 3 — items 3, 4: equation-display refinement (2026-10-08)

- **Fix:** `_refresh_prisma_tab` now appends the literal reconciling arithmetic right under each count block, recomputed with Python's own `==` on every refresh (never hand-asserted, never templated against the raw numbers). Item 3: per branch, `reconciles: {identified} = {removed}+{prescreen_pending}+{screening_pending}+{screened}` with a trailing `[reconciled]`/`[MISMATCH]` tag. Item 4: `reconciles: {assessed} = {included}+{excluded}` and `reconciles: {sought} = {assessed}+{not_retrieved}+{pending}`, the same two equations `prisma.verify_invariants` already checks -- now shown as arithmetic, not just a pass/fail note. The existing "No invariant violations." / "INVARIANT VIOLATIONS:" block is untouched and still covers the branch-scoped report equations and the reason-sum check that aren't displayed as arithmetic yet.
- **Tests:** `test_prisma_tab_shows_reconciling_equations` -- seeds 3 occurrences (1 included, 1 excluded, 1 full-text-pending), confirms the identification equation reads `reconciles: 3 = 0+0+1+2` with `[reconciled]`, and both report equations read `reconciles: 1 = 1+0` and `reconciles: 1 = 1+0+0` with the real numbers substituted in, and that no `[MISMATCH]` tag appears.
- **Live screenshots:** `docs/ui-references/prisma-audit/round-3-live-equations-identification.png` shows the per-branch identification equation (`reconciles: 3 = 0+0+0+3 [reconciled]`) directly under its count block; `round-3-live-equations-reports.png` (scrolled via a real mouse-wheel event over the counts `Text` widget) shows both report-level equations (`reconciles: 1 = 1+0 [reconciled]` and `reconciles: 2 = 1+0+1 [reconciled]`) directly under theirs.
- **Verification:** full suite **272/272**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New scores — items 3, 4: 2 each** (were 1 each). Recomputed with `python3`: `sum({1:2,2:2,3:2,4:2,5:2,6:2,7:2,8:2,9:2,10:2,11:1,12:2}.values())` = **23/24**. Only item 11 (keyboard verification) remains below 2.

## Round 4 — item 11: keyboard verification (closes the tab, 2026-10-08)

- **Verify-first found a real gap, not just a missing check (same pattern as Full-text item 9 / Studies item 10):** before touching keyboard order, foregrounded the live app at the standard 1280x800 capture size and found the audit log `Treeview` and the in-tab "Export package..." button sat entirely below the window's visible fold, with **no outer scrollbar at all** -- only the inner flow-diagram `Canvas` (added in Round 2) was scrollable. On a standard window those two controls were unreachable by any input method, mouse or keyboard, not merely out of Tab order. Confirmed by resizing the live window to 1400px tall: the same content appeared, proving genuine overflow rather than a rendering bug.
- **Fix:** wrapped the whole tab's content in its own scrollable outer `tk.Canvas` + `ttk.Scrollbar` (`self.prisma_scroll_canvas`), containing the pre-existing `frame` (watermark label, counts snapshot, flow diagram, audit log, export button) unchanged. Added mouse-wheel binding scoped to while the cursor is over the canvas (`<Enter>`/`<Leave>` bind/unbind of `bind_all("<MouseWheel>")`, so it doesn't leak into other tabs), plus explicit `<Up>`/`<Down>`/`<Prior>`/`<Next>` keyboard bindings and `takefocus=1` so the outer canvas is itself a real, keyboard-operable Tab stop -- not just a passive scroll container.
- **Tests:** `test_prisma_tab_outer_frame_is_scrollable` -- asserts the scrollregion is actually taller than 800px (proving real overflow, not a degenerate empty region) and that `yview_moveto` genuinely moves the canvas's view (the geometry-independent half of the same scroll API the keyboard bindings call; `yview_scroll`'s pixel-based unit/page amount was confirmed separately to be untestable in a headless/withdrawn Tk window, where `winfo_height()` stays 1px regardless of content).
- **Live verification (real OS-level checks, not assumed):** (1) dragged/clicked the outer scrollbar's down-arrow repeatedly at 1280x800 -- the audit log (all 7 real events) and the Export button scrolled fully into view; (2) real mouse click on the audit log Treeview followed by five real `VK_TAB` keypresses traced a genuine focus chain: outer scroll `Canvas` -> audit log `Treeview` -> in-tab "Export package..." button -> (wraps to the app's header Export button and Notebook, then back) -- every interactive control on the tab is a real Tab stop; the disabled counts `Text` and the flow-diagram `Canvas` (no `takefocus`) are correctly skipped, same precedent as every other tab's read-only panes.
- **Live screenshots:** `docs/ui-references/prisma-audit/round-4-live-scrolled-audit-log-reachable.png` shows the audit log and Export button reached purely by scrolling the outer tab at 1280x800; `round-4-live-tab-focus-audit-log.png` shows the audit log Treeview with a visible selection/focus indicator after real Tab traversal from the outer canvas.
- **Verification:** full suite **273/273**; `git diff --check` passes. No screening-data files were touched; all seeded/captured records are synthetic.
- **New score — item 11: 2** (was 1). Recomputed with `python3`: `sum({1:2,2:2,3:2,4:2,5:2,6:2,7:2,8:2,9:2,10:2,11:2,12:2}.values())` = **24/24**. **PRISMA & audit tab closed.**

## Convergence status

All seven tabs are now closed: Screening 28/28, Duplicates 24/24, Conflicts 26/26, Full-text 24/24, Studies 24/24, Maybe re-review 24/24, PRISMA & audit 24/24.

### Directive F — Phase 1 shared chrome shell (2026-10-09)

- **Authority:** Nate selected the checked-in `docs/design-system.md` Field Notes palette/fonts over Directive F's conflicting ivory/periwinkle/Raleway/Inter values. Scope follows Directive F: shell/chrome only, no content/layout migration inside tabs, no behavior changes beyond navigation presentation, no dependencies. Work is on `implementation/directive-f-full-visual-parity` from `13f07a7`.
- **Diff:** added an in-client File/Project/View/Help menubar using the existing command menus, introduced the shared section-nav row with seven distinct buttons and live count badges (Conflicts displays LOCK while blind), hid the redundant native ttk notebook tab strip while retaining the notebook container/workflows, and split the footer into action/status text, shortcut legend, and Local only + DB filename.
- **Test:** added `test_phase1_chrome_shell_has_menu_header_badge_nav_and_status_footer` for menu labels and rendered menu buttons, count badges, section selection/active state, hidden native notebook tabs, and footer notice. Existing seven-tab order assertion remains green.
- **Live capture:** `docs/ui-references/live-captures/screening-populated-queue.png` captured at 1280×800 with 12 invented records. It confirms one section-nav row (Screening 12; six other badges 0), visible in-client File/Project/View/Help menu buttons, three-column screening work surface, and footer. The native notebook tabs are removed and the notebook remains only as the selected-page container; no duplicate section-nav row appears. The queue is scrollable and the footer chrome fits at the target viewport.
- **Verification:** shell regression and existing tab-order tests pass; full suite **329 passed**; `git diff --check` clean. The wrapper refreshes all seven old/new menu action tests so existing File-menu handlers retain their commands after moving those menus in-client. No content/layout moved between panels; phase 2 has not started.

### Directive F — Phase 2 Screening card-shell migration (2026-10-09)

- **Scope:** first per-tab migration only (Screening); retained all seven references' already-implemented content/features; moved the queue, record, and exclusion/history rails into the shared three-card shell using the target 280/656/flex/296 intent. Search/filter rows, bulk and primary decision buttons, reasons, recent decisions, focus, keyboard paths, and counts remain in their same controls and domain handlers.
- **Diff/test:** test-first regression `test_phase2_screening_tab_has_three_card_shell_without_moving_controls` verifies the three card parents/order and existing queue/abstract/decision widget containment. It failed before the migration (missing card containers) and passed after. Bulk Include and required-reason behavior tests also pass.
- **Live capture:** `screening-populated-queue.png` is a fresh 1280×800 synthetic 12-record capture, blind OFF; independent visual review confirms the one-row shell, the three cards, and all six primary/bulk decision buttons contained with no overlaps. Existing long queue titles truncate at the right edge of the fixed queue viewport; the scrollable queue exposes rows vertically, but a title can’t be read in full in the list. This is a known visual limitation from the fixed 280px column and remains open for a separate iteration; the detail card displays the selected full title. No behavior change was made to the queue’s search, selection, bulk decisions, focus, or row order.
- **Verification:** focused card/bulk tests: **3 passed**; full suite **330 passed**; `git diff --check` clean. No tab other than Screening migrated in this phase-2 chunk.

### Directive F — shared footer visibility correction, Screening items 13–14 (2026-10-09)

- **Single region:** the previous Phase 2 capture showed the shared status bar obscured behind the expanded notebook content despite its widgets and handler existing. Constructed/stacked the status bar before the notebook and explicitly lifted it so Tk's bottom-packed footer occupies its own visible strip below the notebook.
- **Capture/re-score:** a fresh 1280×800 capture with synthetic records, blind OFF, shows the real-keystroke confirmation `Saved: Include (Synthetic queue title 01 with invented study details)`, full I/M/E, 1–7, J/K, / legend, and `Local only · synthetic-directive-f-footer.sqlite`, with all footer text visible. Item 13 scores **1/2**: real action confirmation is visibly present, but this label does not provide the screen-reader announcement promised by the checklist; `app.py` documents that no platform accessibility bridge exists. Item 14 scores **2/2**: complete legend and local-only/database suffix are visible without clipping. Only items 13 and 14 are re-scored; no other checklist items or total is recomputed, and the Screening package remains open.
- **Verification:** `test_phase2_status_footer_is_visible_below_notebook` covers mapped placement after the notebook, containment within the root client area, legend, database notice, and live message setter. Initial regression failed because the footer was unmapped/occluded; it passes after moving/lifting the shared footer. Focused footer/card/bulk tests: **4 passed**; full suite: **331 passed**; `git diff --check` clean. Only four expected allowlisted files changed; seeded DB removed, capture directory contains PNGs only.

### Directive F — Phase 2 Maybe re-review card-shell migration (2026-10-09)

- **Scope:** one tab only: reparented the existing Maybe queue, selected-record, and decision-support panels inside three equal-height, bordered Field Notes cards. Kept queue/search/status/tree widgets, selected-detail text, action bar, exclusion controls, selection IDs, bind/focus paths, handlers, and reviewer-scoped query logic intact. Adjusted only the support-panel’s existing spacing and concise shortcut guidance so the keyboard guide remains inside the available panel at 1280×800.
- **Regression/capture:** extended the existing three-column Maybe test to assert three card parents/order, shared grid sizing, padding, layout geometry, control containment, empty-state disabled actions, own-vote-only/blind gate, and fully contained keyboard help. Fresh `maybe-selected.png` is a 1280×800 real Tk capture from three synthetic own-Maybe records with the first selected and its detail rendered; nav badge and queue both show 3, blind OFF. Visual inspection confirms the three card borders, selected detail/actions, all support reasons and guidance visible. The queue truncates the selected record’s long title in its list row; full title is visible in detail. This remains an open queue-row visual limitation, not a reason to infer missing record content. Seed DB stayed outside repo and was removed; capture directory contains PNGs only.
- **Verification:** focused card, empty-state, detail/timestamp, required-reason, local shortcut/navigation, search/status, and own-vote/blind-scope tests: **7 passed**; `py_compile` and `git diff --check` clean. Full suite pending final run. No checklist item is newly scored or closed in this migration chunk; no other tab changed.

### Directive F — Maybe re-review item 10 keyboard-guide correction (2026-10-10)

- **Single region:** corrected the Maybe support-panel keyboard guide to `Queue-focused: I/M/E/J/K.` The keys are queue-local on Maybe, so the earlier “Screening shortcuts” scope was false; the new concise string accurately describes where those bindings apply.
- **Live evidence/re-score:** `maybe-keyboard.png` is a fresh 1280×800 capture after foregrounding Screening Workbench, clicking the queue, and sending a real Windows VK_J. It shows the second fictional record selected with a visible “FOCUS” row badge; the queue focus label and status announcement read “Keyboard focus: Invented habitat sampling protocol” and “Focused Invented habitat sampling protocol in the Maybe queue.” The corrected guide is fully visible. Item 10 re-score: **2/2** for visible keyboard guidance, focus, and action/status announcements. No other checklist items or scores are changed.
- **Verification:** updated the focused local-shortcut test to pin exact corrected copy while retaining J/K selection and I/M handler checks. Focused keyboard/shell/search tests: **3 passed**; full suite: **331 passed**; `py_compile` and `git diff --check` clean. No behavior or data handler was changed.


### Directive F — Duplicates checklist re-score, items 5, 8, and 11 (2026-10-10)

- **User-authorized scope:** one focused verification pass over review findings for items 5 (match evidence), 8 (merge confirmation), and 11 (keyboard/focus). Current `480944f` remained pushed baseline; this follow-up is uncommitted and limited to the Duplicates tab, tests, convergence log, and its fresh evidence.
- **Item 5 change and pixels:** the comparison now spells out `Score 0.95`, `Rule version 1`, and human-readable match reasons on separate lines (`title similarity`, `same first author`, `shared publication year`). Regression asserts the score/reasons/rule and provenance. Fresh `duplicates-selected.png` (1280×800, two invented occurrences, one fuzzy cluster, first row and survivor selected, blind OFF) shows all score/rule/reason lines legible without clipping; some long field-comparison values remain horizontally scrollable and documented as a limitation.
- **Item 8 evidence:** `duplicates-confirmation.png` is a direct capture of the real native confirmation dialog invoked through the normal Merge handler on a disposable synthetic database. It visibly names the survivor and absorbed fictional record IDs and states the operation is reversible; content is not clipped. The native messagebox uses Yes/No labels while the HTML reference mockup draws Cancel/Confirm merge. The separate cancellation regression stubs the confirmation response and asserts the open cluster and both active records remain unchanged. The disposable capture database was removed.
- **Item 11 change and verification:** Duplicates queue navigation now binds Up/Down to move the selected cluster and render its details; Tab reaches the queue, survivor selector, and both actions. A concise queue-local guide states `Keyboard: Tab through queue, survivor, actions; Up/Down selects`. Queue and survivor Listboxes show the Field Notes focus token as a distinct 3px outline on focus, reverting to the neutral line on focus loss. Focused tests cover two independent synthetic candidates, Up/Down selection, detail refresh, Tab order and focus styling. Fresh `duplicates-selected.png` shows the guide and clearly visible orange focus frame around the queue; independent visual review confirms it is distinct from the row selection. The shared footer lists app-wide shortcuts; no tab-local I/M/E/J/K bindings were added.
- **Re-score:** item 5 = **2/2** (score, rule version, all match reasons and provenance are visible and tested); item 8 = **2/2** (real modal screenshot names survivor/absorbed IDs and reversibility, without clipping; cancellation is separately tested); item 11 = **2/2** (queue-local Tab/Up/Down guidance is accurate, bindings and traversal are tested, and the live capture shows the queue focus outline). These three items score **6/6**; the review baseline was 21/24 with these three each at 1, so the resulting Duplicates score is **24/24**. Independent review found no blocker. Long comparison fields remain horizontally scrollable, as documented in the migration entry.
- **Verification:** focused item 5/8/11 tests: **3 passed**; full suite: **334 passed**; `py_compile` and `git diff --check` clean. Captures are 1280×800 except the real modal at native 426×244; capture directory contains PNGs only, disposable databases removed. No domain/matching/merge behavior changed; queue-local arrow-key navigation is newly implemented.


- **Scope:** one tab only: reparented the existing Duplicates manual queue, read-only match/provenance/field comparison, survivor selector, merge/keep-separate actions, and reversibility explanation into aligned queue/comparison/resolution cards. Existing matching IDs, selection models, survivor preselection, source values, comparison text/tags, action handlers/confirmation, and history semantics remain in place. `exportselection=False` remains on both Listboxes; the Text comparison keeps its horizontal scrollbar for long stable IDs and raw fields.
- **Empty-state action correction:** the reviewer found that the empty-state capture/log said Merge and Keep separate were disabled while their widgets were actually enabled (handlers returned early with no candidate, but the false affordance was still misleading). Both controls are now disabled when no duplicate clusters exist or no row is selected, and enabled only for an open selected cluster; the action handlers/domain operations are unchanged. The regression asserts both button states in the empty state; existing merge/keep flows cover selected-state operation.
- **Regression/capture:** a new empty-state/layout test asserts card parents/order and Field Notes card styles, nested widget containment, both independent listbox selections, actions and notes preserved, exact empty queue message, and mapped card geometry. Fresh `duplicates-selected.png` is 1280×800 with two synthetic fuzzy candidates in one cluster, first selected as survivor, badge/queue count 1, blind OFF. It confirms three aligned cards, visible queue note, exact comparison/provenance and distinct action buttons. Long cluster-preview titles, right-hand comparison values and survivor option text remain horizontally clipped in their narrow viewports; comparison’s horizontal scrollbar retains access to the full raw strings. Fresh `duplicates.png` is a 1280×800 empty-state capture (Duplicates selected) showing no candidate, no selected survivor, disabled resolution actions, the no-clusters hint, and reversibility note. Both fixtures use invented metadata only; databases/helpers stayed in scratch and were removed; evidence folder contains PNGs only.
- **Verification:** focused card-shell, populated compare/provenance, empty state (including disabled actions), queue/reversibility, confirmation-preview, merge and keep-separate flows: **8 passed**; `py_compile` and `git diff --check` clean. Full suite: **332 passed**. No Duplicates checklist scores are claimed or closed in this migration chunk; other tabs unchanged.


- **Scope:** Phase 2 import work touches `src/screening_workbench/app.py` but is outside the seven approved tab reference packages; no existing checklist item maps to the File-menu import commands, so no tab score or running total changes.
- **Verification:** `tests/test_app.py` invokes the real File-menu commands for CSV, RIS, and PubMed XML with synthetic inputs and patched dialogs; the handler tests assert imported/duplicate/skipped feedback. Full suite: 302 passed.
- **Live capture:** `docs/ui-references/imports/phase2-import-shell.png` is a 1280×850 live `ScreeningWorkbenchApp` capture with a blank synthetic-owner project and the File menu bar visible. It does **not** show the drop-down or prove menu-entry appearance; automated handler tests are the evidence for command reachability. A foreground menu interaction was not captured after the OS input request timed out without user approval.
- **Triage:** CSV delimiter and encoding choice plus headerless column mapping are implemented; RIS TI/T1/PY/Y1 conflicts, PubMed partial salvage/ArticleIdList cross-checks, and multi-column author/keyword combination remain documented limitations in `docs/README.md` with their safety/semantics rationale.
- **Brief:** PRISMA export scope is SVG-only; PNG is deferred because the stdlib-only runtime has no PNG renderer and no rendering dependency is approved.

## Directive E — global Field Notes theme pass (2026-10-08)

Owner gate ruling: all six reference packages passed independent review; Directive E is authorized. Per the owner's clarification, this round follows the checked-in `docs/design-system.md` and HTML references' Field Notes tokens (not the differing ivory/periwinkle names in the gate summary).

- **Diff:** `src/screening_workbench/app.py` centralizes palette, spacing, font fallback chains, and theme application. The global `clam` pass styles ttk labels, buttons, entries/comboboxes, notebook tabs, Treeviews, progress bar, and scrollbars; native Text/Listbox, record focus, blind status, reason markers, and PRISMA Canvas use shared Field Notes colors/fonts. No dependencies/toolkit or workflow logic changed. Active tab maps to accent-soft fill + accent text; header vertical padding was tightened 2 px, Screening queue column widened 20 px, and sidebar reason/note text now wraps at its available width. Decorative check/cross/lock/paperclip emoji glyphs were removed; semantic text remains (“LOCKED”, “PDF attached”, action labels).
- **Tests:** `test_global_theme_applies_field_notes_colors_and_font_fallbacks` verifies `clam`, token application, Treeview and selected-tab maps, classic text/badge colors, installed font selections and fallback declarations. `test_prisma_tab_flow_diagram_matches_export_boxes` and `test_all_seven_tabs_present_in_reference_order` pass. Full suite: **310 passed**; `git diff --check` passes.
- **Live captures:** refreshed `docs/ui-references/live-captures/{screening,maybe,duplicates,conflicts,fulltext,studies,prisma}.png`, each captured from the foreground Windows app client area at 1280×800 with invented bibliographic content and blind mode ON. Review of all seven captures confirms the selected tab has a light accent-soft surface; Screening queue and long exclusion-reason labels now wrap/read, blind explanatory note is fully visible, header fits, and decorative emoji glyphs are gone. Other empty/locked panels remain visually sparse and PRISMA nested scrolling remains; those are remaining convergence candidates. Captures are evidence only and do not close tab checklists.
- **Status:** global theme plus two bounded polish rounds (active tab/header/sidebar and PRISMA snapshot hierarchy) implemented. All seven reference checklists remain open; no scores changed and no tab closure claimed. No commit/push.

### Directive E visual round 3 — PRISMA snapshot hierarchy (2026-10-08)

- **Diff:** kept all underlying `lines` text/values and reconciliation logic unchanged; changed the PRISMA snapshot Text font from monospace to the Field Notes UI sans and applied tags for count values, section labels, secondary detail, reconciliation equations, and successful reconciliation status. The distinctive arithmetic is now separately bold blue; hierarchy aligns with the HTML reference’s stage-label/value/detail pattern without inventing box layouts or altering counts.
- **Test:** added `test_prisma_snapshot_uses_field_notes_type_hierarchy_without_changing_copy`, which seeds one synthetic record, asserts exact count/reconciliation strings stay intact, and verifies tagged section/reconciliation spans and body font. Existing live count/equation/flow tests pass. Full suite: **311 passed**; `git diff --check` passes.
- **Live check:** refreshed PRISMA screenshot shows the UI-sans count summary with bold labels/counts and emphasized reconciliation line; all visible copy/values are unchanged. Diagram still has its pre-existing nested scroll area and ample blank space; that structural issue remains open, not addressed in this visual-text round.
- **Status:** no checklist scores changed and no tab is closed; no commit/push.

### Directive E visual round 4 — compact PRISMA flow viewport (2026-10-08)

- **Diff:** retained `export.prisma_flow_boxes()` as the source of all node labels and values; the live Canvas now lays its same eight nodes in a compact 650×205 landscape flow, with stage captions and directed connectors between the main path and side branches. The viewport no longer uses nested scrollbars; no count source, arithmetic, audit scope, blind gate, or exported SVG changed.
- **Test:** added `test_prisma_diagram_fits_full_flow_in_landscape_viewport` with invented records. It asserts all expected labels and values from the shared box model render, viewport dimensions, no scrollcommands, visible node bounds, connector count and relative side/main positions. Existing `test_prisma_tab_flow_diagram_matches_export_boxes` remains green. Full suite: **313 passed**; `git diff --check` passes.
- **Live capture:** refreshed `docs/ui-references/live-captures/prisma.png` at 1280×800 with blind ON. It shows the full eight-node flow—identification, removals, sought/not retrieved, assessed/excluded, reports and studies included—with arrows; no internal diagram scrollbar or clipped node is visible. The capture helper's synthetic SQLite database was removed; only PNGs remain in the evidence directory.
- **Status:** this is the fourth incremental visual round overall; no checklist score is assigned or closed. The other six tab captures remain unchanged in meaning; no commit/push.

### Maybe re-review — selected-record panel convergence iteration 1 (2026-10-08)

- **Lowest-cost region:** the selected-record panel was blank in the prior empty-queue capture, and verification with one synthetic own-vote exposed a too-short panel: placeholder text and vote timestamp were clipped. The reference requires synthetic notice, own current vote + timestamp, record metadata/abstract and an explicit privacy boundary, while keeping the three decision actions visible.
- **Change:** adjusted vertical allocation in the Maybe tab (shorter queue, fixed-height full-width detail pane and compact outer spacing); detail now renders its vote as a text-and-fill badge, includes authors/journal/year, a synthetic reference ID, abstract field, own-vote timestamp and an explicit no-other-reviewers privacy note. The reviewer-scoped query now projects only this own-voted occurrence's authors and abstract into its existing result; no other reviewer data is queried or exposed. Synthetic capture uses one own Maybe vote and one own Include control record; header visibly says Blind screening OFF.
- **Regression/verification:** focused Maybe detail, re-decision and three-way controls tests pass (3); full suite passes (**313 passed**), `git diff --check` clean. The updated detail-pane test asserts the exact three action labels and button requested height <=36px, plus author, abstract, timestamp, privacy note and vote-badge style.
- **Capture:** `docs/ui-references/live-captures/maybe-selected.png`, 1280×800; visual inspection confirms one pending Maybe record, no clipping, own-vote badge and timestamp, synthetic placeholder text and three buttons visible. The abstract itself remains a Screening-tab direction, not source abstract content; no claim of full reference match.
- **Checklist re-score:** all 12 items previously 2 remain 2. Item 5 remains 2 and now shows vote badge plus timestamp; item 4 (synthetic marker), 3 (no others' data; own-scope boundary visible), 6 (controls) remain 2. Other numbers not re-scored by this one-region iteration. No reference package closed. Next lowest region remains Maybe re-review queue/privacy support and selected-panel alignment to three-column composition. Do not change unrelated tabs in this pass.

### Maybe re-review — empty queue cue and populated viewport iteration 2 (2026-10-09)

- **Lowest-cost region:** the zero-record capture previously left both the queue and selected-record area as blank bordered panels. Also, the populated capture had a tall full-width queue leaving the detail pane compressed; an earlier capture did not actually have a selected row, so was not valid populated evidence.
- **Change:** placed a centered muted prompt in the actual empty queue frame without inserting a fake row; kept the count/status authoritative; constrained the queue to a fixed 126px viewport with a linked vertical scrollbar and allowed the selected-record Text panel to expand into the remaining vertical space. Record filtering, selection, own-vote scope and decision actions unchanged.
- **Test/evidence:** added an empty-state assertion for no Treeview rows, exact queue cue and consistent zero count. Focused Maybe tests: **6 passed**; full suite: **319 passed**; `git diff --check` clean. Refreshed `maybe.png` (zero records) shows the prompt and unclipped decisions. Refreshed `maybe-selected.png` has one selected synthetic own-vote and shows the current-vote badge, occurrence ID, privacy note, excerpt cue, timestamp and all three actions. The excerpt itself is still a placeholder/Screening-tab direction, not source abstract content; no claim of full reference match.
- **Checklist:** no scores changed or package closed; the queue/detail composition is still full-width rather than the reference's three-column layout, and remains the next major gap.

### Maybe re-review — selected source excerpt and citation iteration 3 (2026-10-09)

- **Lowest-cost region:** the populated screenshot showed the current vote and timestamp, but not the selected occurrence's abstract/authors; it instead directed reviewers to Screening. The approved reference requires the record itself to be inspectable here.
- **Change:** selected detail now loads the current occurrence's own fields and displays authors, journal/year and its abstract under the excerpt heading; when absent, it says no abstract is available. Source is the same occurrence-fields row keyed by selected occurrence ID. Vote timestamp remains from the current reviewer's own vote query; no additional reviewer data is read.
- **Test/evidence:** expanded the synthetic Maybe fixture with a distinctive abstract and asserted it renders in detail. Focused Maybe tests: **6 passed**. A fresh populated live capture (`maybe-selected.png`, 1280×800; blind OFF; one own Maybe vote selected) displays the actual placeholder abstract, citation, occurrence ID, current-vote badge, own timestamp, privacy boundary and all three decision controls. It confirms the detail change, but does not show the reference's separate synthetic-marker treatment or three-column layout.
- **Checklist:** no numeric re-score claimed because the full twelve-item independent score evidence is not repeated in this region. Items around selected citation/excerpt are improved; item 4 has fictional evidence but lacks an explicit marker, and item 5 has vote/time evidence. Full reference composition and support controls remain open; no package closed.

### Maybe re-review — synthetic evidence-only marker iteration 4 (2026-10-09)

- **Correction:** an unconditional `SYNTHETIC RECORD · UI fixture only` detail string would falsely label ordinary imported records as UI fixtures. The checklist criterion applies to the reference/evidence sample, not the production record widget.
- **Change:** removed the unconditional badge from production detail. Do not infer synthetic status from record title/journal or invent a test-only data heuristic. Capture records are explicitly invented and their abstracts state they are placeholders; annotate that context in this log only.
- **Test/evidence:** focused Maybe tests: **11 passed** after the selected-detail test asserts no production synthetic badge. Fresh `maybe-selected.png` visibly shows fictitious author/journal names and the abstract says it is a fictional sample without corpus text. `maybe-action-feedback.png` verifies title-specific post-Include feedback. Item 4 is supported by synthetic reference/capture provenance, not a UI badge; this is the honest production behavior.
- **Checklist:** no numeric total or tab closure claimed. Keep item 4 at evidence-context only and note reference versus production distinction. No other tab changed.

### Maybe re-review — required-reason support and selected-state actions iteration 5 (2026-10-09)

- **Lowest-cost region:** Decision Support described the exclusion rule but had no reason choices. The action controls were placed in that narrow panel and clipped; moreover the keyboard legend incorrectly implied Screening-only single-letter shortcuts worked here. Empty queues showed active-looking actions despite no selected record.
- **Change:** rendered the existing fixed project exclusion taxonomy as radio choices in Decision Support; choices activate only for a selected record. Exclude remains disabled until a reason is selected, and its handler refuses a missing reason before casting any vote. The action bar now sits at the bottom of the wider selected-record pane, appears only with a real selected row, and uses its normal semantic colors when available; with no selection Include/Maybe/Exclude are hidden. Replaced the inaccurate shortcut legend with the actual mouse/Tab/arrow guidance and explicitly labeled I/M/E/J/K as Screening shortcuts. Added queue behavior note and kept the blind-scope statement in Decision Support.
- **Tests:** new regressions pin the three-column ownership, all taxonomy choices, disabled empty-state controls, no vote without a reason, enabled/disabled reason selector transitions, selected reason mapping, and final Exclude removal from the reviewer queue. Focused Maybe suite: **9 passed**; full suite: **322 passed**; `git diff --check` clean.
- **Live evidence:** refreshed `maybe.png` (zero records) and `maybe-selected.png` (one selected synthetic own Maybe vote), both 1280×800, Blind screening OFF. Visual review confirms zero-state controls are absent and status says no record selected; populated view shows all seven reason choices and all three actions, fully visible alongside selected citation/excerpt, vote/time and privacy notice. Action bar is below the selected-record pane. No clipping observed in the populated capture.
- **Checklist:** item 7 is now represented with actual reason controls and a handler-enforced choice; items 6/8 and 10 have improved control/state evidence but the required real OS keyboard interaction and status announcement were not performed here. No numeric checklist total or tab closure claimed. No other tab changed.

### Maybe re-review — queue-local keyboard operation and focus iteration 6 (2026-10-09)

- **Lowest-cost region:** the Decision Support keyboard legend correctly clarifies that single-letter I/M/E/J/K bindings were Screening-only, but the approved Maybe reference expects keyboard operation of its own queue and decision controls.
- **Change:** added a Treeview-local keypress handler for I/M/E and J/K, operating only when focus is in the Maybe queue and a row is selected. J/K change selected Maybe row and refresh detail; I/M route into the existing Maybe decision handler; E routes to its selected-reason requirement. Bindings are local rather than app-global so search typing and Screening shortcuts do not cross-fire.
- **Test/live interaction:** focused tests verify local keypress routing, J/K selection and I/M decision handlers; focus/click and key input were also driven with real Windows mouse and VK_J/VK_K/VK_I events. The fresh `maybe-keyboard.png` capture shows orange focus on the same selected second row and its matching detail pane. Full suite after this work: **324 passed**; `git diff --check` clean.
- **Status announcement:** successful Include reports “Included [title]; your Maybe list updated” in the shared status label; the visible queue feedback also names the record. The Tk label update is verified; Windows Narrator/NVDA speech output is not asserted.
- **Checklist:** keyboard operation, visible focus, state transition and action announcement have current automated/live evidence; no full 12-item numeric re-score or tab closure claimed. No other tab changed.

- **Lowest-cost region:** synthetic fixture evidence was visibly marked in the selected record, which would incorrectly label ordinary imported records as UI fixtures. The reference requires the screenshot/reference fixture to be synthetic, not a permanent false assertion in production UI.
- **Change:** remove the unconditional `SYNTHETIC RECORD · UI fixture only` string from the production detail widget. Continue using visibly fictitious seed content in evidence and identify it as synthetic in the convergence log/capture context. No title-based heuristic or synthetic flag is inferred.
- **Test/evidence:** updated the selected-detail regression to assert the real record text renders without the false fixture badge. Fresh populated screenshot `maybe-selected.png` is seeded with invented title/authors/journal/abstract and a synthetic UI fixture context; it must be re-captured and visually inspected to verify no false badge remains. Focused Maybe suite and full-suite results pending final run.
- **Checklist:** item 4 (synthetic sample) is represented by invented authors, journal and an explicitly fictional placeholder abstract in the reference/evidence context only. Do not claim production UI marks arbitrary records synthetic. No score or tab closure claimed.

### Maybe re-review — accessibility focus and scoped query audit iteration 8 (2026-10-09)

- **Final verification:** after final changes, `python -m pytest -q` → **328 passed**, focused Maybe suite → **15 passed**, and `git diff --check` is clean. Fresh `maybe-keyboard.png` captures keyboard focus, selected-row details, reviewer-only scope, and blind OFF. No database/WAL/SHM artifacts were retained in the evidence folder.

- **Lowest-cost region:** the approved reference has a persistent footer with selected occurrence ID and active decision. The global status bar advertised Screening shortcuts; clarify their scope and ensure the same selected row is plainly keyboard-focused without falsely claiming focus for programmatic selection.
- **Change:** the global legend is now explicitly Screening-scoped. The Maybe header states that search, counts, and status use only the current reviewer’s votes; a separate reference-state line reports blind ON/OFF and own-vote scope. The queue keeps the seven-row reference viewport, with a clear queue title and a single Record column heading; the selected card has one heading rather than duplicate panel/card labels. Maybe focus is owned by the Treeview's real FocusIn/FocusOut and keyboard navigation paths, reported in a visible focus label, explicit “FOCUS ·” row prefix, and decision-cell label. Programmatic selection alone does not imply keyboard focus.
- **Blind-scope audit:** a new test seeds separate owner/reviewer-b Maybe votes and toggles blind both OFF and ON; each identity's query returns only its own occurrence and the app tree contains only the owner's title in both modes. Search filters the own-vote list in memory; no cross-reviewer counts are queried or rendered.
- **Live verification:** synthetic-only app launched with owner reviewer and blind OFF. Real Windows mouse selected row one; real VK_J moved selection and keyboard focus to row two, and details/status/focus styling moved with it. Fresh `maybe-keyboard.png` is 1280×800 and visually shows second-row focus, matching detail/status, own-scope and blind OFF labels. Real VK_K returned to row one and VK_I included it; current vote changed, Maybe queue removed it, and status announced “Included First fictional keyboard record; your Maybe list updated.”
- **Tests:** Focus semantic regression test and reviewer-scope state-label regression; final focused Maybe suite: **15 passed**; full suite: **328 passed**; `git diff --check` clean. No speech output is claimed; no NVDA/JAWS or UIA bridge is installed.
- **Checklist:** iteration 8 left item 9 as an apparent match based on the in-pane status and counts; the app-state navigation badge was not synchronized in the keyboard capture. Item 9 is reopened pending its focused recapture.


- **Focus semantic regression guard:** a new withdrawn-root test verifies programmatic Treeview selection alone does **not** claim keyboard focus; focus styling/status only appear after the actual Treeview focus path. Included in the final **15-pass** focused Maybe suite. This prevents a false focus marker in normal non-focused screens.

### Maybe re-review — item 9 badge/status synchronization re-capture (2026-10-09)

- **Single region:** no app behavior change was required. The capture fixture now calls `refresh_all_tabs()` after seeding both owner Maybe votes, rather than refreshing only the Maybe panel; this refreshes the nav badge from the same reviewer-scoped ID set before screenshot. Added assertions to the item-9 search test that the badge remains `Maybe re-review (2)` before, during, and after in-memory search filtering while status updates independently.
- **Live evidence:** reran the real Windows mouse + VK_J/VK_K/VK_I session using synthetic-only records. Fresh `maybe-keyboard.png` shows `Maybe re-review (2)`, two queued records and two pending status count, with the second row focused and its detail pane in sync; Include still removes the first record from the Maybe queue. No temporary DB/WAL/SHM retained.
- **Item 9 re-score only:** **2/2**, evidence now includes reviewer-filtered queue, matching navigation badge, in-pane count/status and search result count. Other eleven item scores are unchanged; no new aggregate closure claim.
- **Verification:** `python -m pytest tests/test_app.py::test_maybe_tab_search_filters_queue_and_updates_status -q` passes; full suite: **328 passed**; `git diff --check` clean.


- **Lowest-cost region:** the standard 1280×800 live Duplicates capture showed zero open clusters, but the survivor selector and large compare pane looked blank, leaving it unclear why no survivor was selectable. Before implementing, seeded a separate synthetic two-record 0.95 candidate and verified the populated live compare pane already renders per-field source text/difference labels, match/provenance, and a visibly pre-selected survivor; that populated verification is `duplicates-selected.png`.
- **Change:** reduced the survivor list's reserved height from four rows to two; for a genuinely empty cluster state the comparison pane says `NO OPEN DUPLICATE CLUSTERS` with a short manual-review note, the survivor selector has an unselected muted instruction instead of an empty list, and the queue list says `No open duplicate candidates.` No candidates are selected, merged or inferred.
- **Test/verification:** added an empty-state test asserting queue, compare-pane and selector messages and no survivor selection. Focused empty/populated/queue-semantics tests: **3 passed**; full suite: **314 passed**; `git diff --check` clean. Existing populated live capture verifies 2 active synthetic records, 1 open two-member cluster, comparison and preselection.
- **Capture:** refreshed `duplicates.png` at 1280×800 for the empty queue. Live inspection confirms the manual-queue and reversibility notices and actions remain visible; the populated `duplicates-selected.png` demonstrates the ordinary candidate state. Temporary synthetic SQLite database removed after capture.
- **Checklist:** items 1-12 stay open; this is one empty-state visual iteration and does not close a package. No other tab changed in this round.

### Conflicts — evidence hierarchy and no-open-items iteration 1 (2026-10-08)

- **Lowest-cost first:** the live populated synthetic conflict already showed record, both timestamped votes, reason, required note, owner/blind authorization and append-only notice, but the read-only evidence used one small heading treatment for everything. On an actual zero-conflict fixture the previously blank queue/detail looked selectable despite there being no conflict.
- **Change:** introduced restrained reading hierarchy inside the evidence pane (serif record title, muted metadata, separately headed reviewer decisions, accent decision lines, muted italic exclusion reason, monospaced timestamps), without changing vote content/order or backend semantics. For zero open conflicts the queue and detail explain the empty state, resolution buttons and note entry are disabled, and the hint says resolution is unavailable until a conflict is selected. For a populated list, the note entry is restored and the pre-existing required-note hint refreshed.
- **Tests:** targeted tests assert title/meta/vote/timestamp tags and text; a new empty-state test checks no queue IDs, empty-state instructions and all resolution controls disabled. Focused tests: **2 passed**; full suite: **315 passed**; `git diff --check` clean.
- **Evidence:** `conflicts-selected.png` is a populated one-conflict synthetic capture verifying the new hierarchy and complete reviewer evidence; `conflicts.png` is the genuinely empty conflict state (Blind screening OFF). Captures are 1280×800.
- **Checklist:** Conflicts package remains open; no 13-point score revised or claimed closed in this iteration. Other tabs were not modified here.

### Screening — queue density at populated state iteration 1 (2026-10-08)

- **Lowest-cost region:** the populated 12-record live queue showed all 12 two-line entries at once, visually competing with the center review record and leaving the queue's bulk-decision row partly constrained; the reference layout keeps the queue column near 280 px and the controls visible.
- **Change:** constrained the queue list to a 280px-high frame with a real linked vertical scrollbar, set it to show seven two-line rows at a time, and expanded the fixed queue column from 280 to 312px so the scrollbar and all three bulk Include/Maybe/Exclude buttons have room. Queue remains a single two-line Treeview column; titles, metadata, current `Now` indicator and selection/bulk semantics unchanged.
- **Regression/verification:** added a UI regression test pinning two-line data, current-row marker, queue viewport, scrolling hook, and action labels. Five focused queue/bulk-select tests pass; full suite **316 passed**; `git diff --check` clean. In the populated synthetic 12-row live capture the current row is visible, about seven entries fit before scrolling, scrollbar is present, center decision controls remain visible and expansion to 312px leaves all three queue-side bulk action labels fully readable.
- **Capture:** `screening-populated-queue.png`, 1280×800, synthetic-only. `screening.png` empty state remains as the standard screen shell capture; no decision behavior, count meaning, or blind gate changed.
- **Checklist:** Screening package remains open; item 5 is only incrementally improved here, not rescored/closed. Other tabs not changed in this pass.

### Full-text — selected-report evidence hierarchy iteration 1 (2026-10-08)

- **Lowest-cost region:** rendered a populated synthetic report and compared the detail area with the approved reference's central record card; the current read-only Text presented ID, title, citation and excerpt in one small uniform style. A populated fixture is required here; the standard empty-tab capture cannot demonstrate this hierarchy.
- **Change:** selected-report details now have a 17pt reading-serif title, grouped author/journal/year citation, smaller muted mono-safe report/source IDs and DOI, and a separately headed reading-serif imported abstract/excerpt. Existing IDs, abstract text, selected report identity, assessment controls, attachment actions and blind-stage query/lock remain intact.
- **Tests:** expanded the real import→promote→select UI test to assert title/excerpt tags as well as both IDs, author, journal, year and exact synthetic excerpt. Full-text focused suite: **7 passed**; full suite **316 passed**; `git diff --check` clean.
- **Evidence:** `fulltext-selected.png` is a 1280×800 populated one-report synthetic capture; visual review confirms title/citation/details/excerpt legible without clipping, and assessment/PDF controls remain visible. `fulltext.png` remains the baseline empty view.
- **Checklist:** Full-text package remains open; no item scores revised/closed in this iteration. No other tab changed in this pass.

### Studies — selected-report detail hierarchy iteration 1 (2026-10-08)

- **Lowest-cost region:** selected report-row title lacked its heading emphasis in the live detail, while report ID, parent, canonical occurrence, branch, retrieval status and provenance already appeared textually. The reference emphasizes report-group information distinctly. No claim of a three-column implementation was in scope.
- **Change:** applied the existing `study_heading` tag to the report's textual `Title:` line, alongside its existing report and canonical heading tags. No workflow/layout changes; selection, canonical radio, status and link controls are unchanged.
- **Test:** extended the selected-report behavior test to check the heading tag on report title and canonical status text. The focused report/canonical/provenance test passes (1); full suite **316 passed**; `git diff --check` clean.
- **Evidence:** populated fixture setup is verified by its test; live-screen capture was unavailable this pass because Windows was at the lock screen and foreground activation was denied. Therefore this remains an automated tag/detail check, not a visually verified convergence result; no package closure claimed.

### Full-text — explicit empty report/detail state iteration 1 (2026-10-08)

- **Lowest-cost region:** fresh unpopulated 1280×800 capture showed large blank Reports and selected-detail areas, with no instruction why they were empty and assessment buttons that looked active despite no report.
- **Change:** added neutral, reversible empty-state guidance for the included-title/abstract promotion list and Reports list, plus a no-selected-report hint. With zero reports, selection, assessment, retrieval and PDF actions are disabled and semantic decision buttons use muted disabled styling; the one no-selected-report hint appears between its section label and detail pane (not duplicated inside the Text widget). For a populated report list, the empty-state hints are removed and decision colors restored. The Reports list itself stays empty—no placeholder row appears in its report data.
- **Tests:** new zero-report regression test pins list/detail copy, empty report ID set, disabled assessment button states and muted decision fill. Full-text focused suite **8 passed**; full suite **317 passed**; `git diff --check` clean. Existing populated detail test still passes.
- **Evidence:** refreshed `fulltext.png` is a fresh, zero-report/zero-candidate 1280×800 foreground capture; `fulltext-selected.png` was refreshed after this empty-state work using one pending synthetic report, to verify assessment colors restore for populated reports.
- **Checklist:** Full-text package remains open; this iteration only clarifies empty state, no checklist score or package closure claimed. No other tab changed.

### Studies — explicit empty study-tree guidance iteration 1 (2026-10-08)

- **Lowest-cost region:** the genuine empty state showed the `New study` action above a large blank tree with no prompt; nothing distinguished “no studies yet” from missing content.
- **Change:** centered a muted, non-data overlay inside the empty study Treeview: “No studies yet. Select New study to add one; studies will appear here.” The label is removed as soon as a study row exists and also hidden while blind; no fake study row or selection is inserted.
- **Test/evidence:** a test checks the Treeview has no rows while the overlay text/manager is present. Focused empty/populated/nested/blind tests: **3 passed**; full suite **318 passed**; `git diff --check` clean. Refreshed empty-state `studies.png` (1280×800) visibly contains the guidance, keeps New study visible and the rest of the screen unclipped. No other tab changed in this pass.
- **Checklist:** Studies package remains open; no score change or package closure claimed.

## Directive F close — merged visual parity (2026-10-12)

- **Merge:** `f605b60010a2459436f13cff186dd8bcb551b70f` merges `implementation/directive-f-full-visual-parity` into `main` with a non-fast-forward merge commit.
- **Owner declaration:** Nate declared convergence on all seven tabs and approved this merge. Final board: PRISMA 24/24; Maybe 24/24; Studies 24/24; Full-text 24/24; Duplicates 24/24; Conflicts 25/26 (item 10 waived by owner); Screening 26/28 (item 6 waived by owner; item 13 is a documented platform screen-reader limitation).
- **Combined total:** machine-recomputed with Python from the seven supplied scores: **171/174**.
- **Verification:** merged `main` full suite **362 passed**; Python compilation and `git diff --check` clean.

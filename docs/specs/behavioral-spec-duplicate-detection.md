# Screening Workbench duplicate-detection behavioral specification

**Status:** Clean-room behavioral specification; testable product requirements, not implementation.  
**Source cutoff / access date:** 2026-10-06.  
**Scope:** Bibliographic *records* imported into a local systematic-review screening project. This specification does not equate duplicate records with multiple publications about one study.  
**Compatibility baseline:** Preserve reversible, auditable exact/fuzzy deduplication and PRISMA duplicate counts, with the 2026-10-07 rule amendment in §3.1 superseding the supplied old DOI-only behavior: a DOI match only silently merges when normalized titles also agree; DOI/title conflicts or missing titles go to human review.

## 1. Provenance and interpretation

This is a clean-room specification based on public methodological standards and documentation plus explicit first-principles product decisions. No incumbent app was inspected, accessed, signed up for, scraped, or used as a source; no incumbent wording, labels, UI, or assets are reproduced. The compatibility baseline above is supplied project context, not a public-source claim.

Cochrane describes the risks on both sides of deduplication: leaving duplicates costs screening effort and may distort reported counts, while overly aggressive removal can lose unique records. Its technical supplement notes there is no universally optimal method and that combined automated and visual review is commonly used.[S2] A peer-reviewed comparison operationalizes false positives and false negatives and cautions against batch-removing uncertain matches without checking them.[S3] Therefore, this spec reserves silent merges for the supplied exact-match conditions and routes approximate matches to human review. The numeric fuzzy threshold and other detailed policy choices below are **first-principles proposals**, not behaviors established by a public standard or attributed to any other product.

- **Source-occurrence record:** one bibliographic citation row as imported from a specific batch/source. Its identity and provenance persist even if it is later marked duplicate.
- **Canonical representative:** the source-occurrence record selected as the active survivor of a confirmed duplicate group. It is not a replacement row; original occurrence IDs, votes, and provenance remain addressable.
- **Record:** a source-occurrence record unless a requirement explicitly says canonical representative.
- **Bibliographic duplicate:** two or more records that represent the same bibliographic item, despite differences in citation metadata. A conference abstract and later full paper, or distinct reports from one study, are not automatically the same bibliographic record.[S3][S4]
- **Pre-screening duplicate removal:** a source-occurrence record committed as duplicate before it receives a screening vote. A duplicate confirmed after any screening vote remains counted in the historical screened record count and is annotated as a post-screen correction; it is not reclassified as removed before screening.

## 2. Scope and non-goals

### In scope

1. Normalize imported title, publication-year, DOI, and author fields for deterministic comparisons while retaining source values unchanged.
2. Detect exact duplicate groups and apply a reversible, logged automatic merge.
3. Detect fuzzy candidate pairs/groups and put them in a manual resolution queue.
4. Support reviewer merge/keep-separate decisions, survivor selection, difference inspection, undo, and audit history.
5. Keep active-record, duplicate, and PRISMA counts consistent across import, decisions, undo, and re-import.
6. Operate locally and continue core deduplication without internet access.

### Out of scope

- Deciding whether two different records report the same underlying study, trial, cohort, or data set. Those links require evidence and review; they must not be inferred from bibliographic similarity alone.[S4]
- Automatically searching DOI registries or full text, deciding eligibility, or making screening decisions.
- Treating a similarity score as proof, deleting source records permanently, or silently overwriting conflicting metadata.
- Selecting a single universally optimal fuzzy threshold. The proposed threshold below must be validated against representative Screening Workbench datasets before being treated as empirically optimal.[S2][S3]

## 3. Detection policy

### 3.1 Exact matching: automatic, silent, auditable

For every newly imported batch, Screening Workbench MUST compare new records with one another and with existing active records in the same review project. A pair is eligible for silent exact merge only when the records have both a corroborating identifier/signature and agreeing normalized titles:

1. **DOI + title condition:** Both records have the same normalized DOI and both have non-empty normalized titles that agree exactly; or
2. **Title/year condition:** Both records have the same non-empty normalized title and at least one shared normalized publication year.

**DOI conflict rule (amended 2026-10-07):** A DOI match alone MUST NOT trigger silent merge. If DOI matches but normalized titles materially differ, or either title is missing, Screening Workbench MUST leave both records active and create a manual-review candidate in the existing dedup review queue, tagged `doi_match_title_mismatch`. When evidence is incomplete or contradictory, default to human review. The conservative rule avoids treating an identifier collision or incomplete metadata as sufficient evidence for automatic merging.

A single DOI is a persistent identifier; DOI names are case-insensitive.[S5] Crossref exposes deposited bibliographic metadata through a public REST API, but network lookup is not required or part of this deterministic local matching rule.[S6]

**Normalization contract (proposed, deterministic):**
- Preserve original imported values and their source fields unchanged. Normalized values are additional comparison keys, never display replacements.
- **DOI:** Trim surrounding whitespace; remove a leading `doi:` label or `http(s)://(dx.)doi.org/` resolver prefix (case-insensitive); trim trailing citation punctuation and whitespace; compare the remaining identifier case-insensitively. Do not remove or rewrite interior characters. If the input contains multiple conflicting DOI identifiers or cannot be parsed unambiguously, it is not an exact DOI key; retain it as raw metadata and do not use it to auto-merge.
- **Title:** Apply Unicode NFKC, Unicode case-folding, convert punctuation/symbol runs and whitespace runs to one ASCII space, trim leading/trailing spaces. Do not remove words, reorder tokens, stem, translate, strip diacritics, or delete subtitles. Empty normalized titles never match.
- **Year:** Extract four-digit year(s) only from fields explicitly mapped as publication/issued/online/print date by the import format. Do not use import date, accession date, database deposit date, copyright year, or the current year. A partial date contributes its explicit year. If multiple publication dates conflict, retain all extracted years; title/year exact matching requires a shared year. Missing year means no title/year exact match.
- **First author:** Normalize the first listed author’s family/surname component using Unicode NFKC and case-folding; trim and collapse whitespace; preserve diacritics and internal characters. If the import does not identify a first author/family name reliably, do not use first-author fuzzy matching.

**Exact-group policy:**
- Exactness is evaluated on record pairs. A connected exact-match component is one exact group; an incoming record that bridges existing groups joins them into one transaction and one audit event with all source members recorded.
- For each exact group, choose a stable survivor deterministically: oldest `created_at`; ties broken by lexicographically smallest immutable record ID. The user is not interrupted for exact matches.
- Keep the survivor's user-edited/curated fields. For fields without a user edit, retain its existing value; if empty, fill from the earliest imported non-empty source value (then record ID as tie-breaker). Never discard a conflicting value: store every raw value with source and record provenance and expose it in history/details.
- The absorbed records remain recoverable and are marked duplicate; no underlying record row or raw source payload is hard-deleted.
If records share DOI but have conflicting titles, years, or authors, exact DOI remains the matching condition for compatibility. The system MUST preserve and expose those conflicts rather than silently overwrite them. This policy is explicitly a first-principles compatibility choice; public DOI documentation establishes identifier persistence/case behavior, not that every malformed or reused DOI in imported data is error-free.[S5]

### 3.1.1 Screening state and post-screening correction

Screening votes remain attached to immutable source-occurrence record IDs. At merge time, classify **each absorbed occurrence row independently**: if that occurrence itself has no screening vote, it contributes one pre-screen duplicate removal; if it has a prior vote, preserve its vote/reason/history, retain it in the historical screened count, and count it once as a post-screen duplicate correction. A mixed group can therefore contain both kinds of absorbed rows; do not classify all rows as post-screen merely because another member was screened. Count absorbed rows, not merge events or groups, in the PRISMA removal/correction totals. Resolve any conflict on the canonical representative before advancing its single report flow; retain every `RecordReport` source link and explicitly log canonical occurrence/branch assignment. Undo restores projections without deleting events; replay must yield identical source and report counts. This operationalizes Nate's 2026-10-06 ruling.


### 3.2 Fuzzy matching: review only

Fuzzy detection creates candidates; it MUST NOT merge, hide from the active set, or affect PRISMA counts until a reviewer confirms a merge.

A pair is a fuzzy candidate only if all of the following hold:
1. No exact condition in §3.1 is met.
2. Both normalized titles are non-empty.
3. Both records have at least one shared normalized publication year.
4. Both have a reliable normalized first-author family name and those names are equal.
5. Normalized-title similarity is **at least 0.90**, measured as `1 - LevenshteinDistance(titleA, titleB) / max(characterCount(titleA), characterCount(titleB))`; empty titles are excluded. The score is computed on normalized title strings from §3.1 and rounded only for display, never before threshold comparison.

The 0.90 threshold is a **proposed conservative starting point, unverifiable as an externally established Screening Workbench behavior**. It is explicit so tests are repeatable, not a claim that it is optimal. Do not use external network metadata to raise a fuzzy candidate to an automatic match. Do not use an abstract-only, author-only, year-only, or title-only similarity as a merge trigger.

**Candidate grouping:** Construct candidate pairs first. Display a connected candidate component as a group, with its pairwise candidate links available to the reviewer. A component can contain a chain where not every pair qualifies; therefore, a reviewer merge may absorb only members explicitly selected as duplicates of the chosen survivor and each selected member must have a candidate link to that survivor. `Keep separate` resolves only the selected candidate pair as separate; it must not suppress other candidate links in the component.

Candidate queue entries MUST capture the comparison rule/version, normalized comparison values, similarity score, and candidate record IDs as generated. If source metadata changes, invalidate/recompute affected open candidates and retain their prior decision/history; do not silently transfer a `keep separate` decision to materially changed metadata.

### 3.3 Not candidates / dangerous similarities

The following MUST NOT cause an automatic merge or fuzzy candidate without meeting §3.2: identical first author and year alone; identical title with no shared year; title similarity with different known first authors; missing or malformed metadata; shared journal, volume, page range, or abstract alone; records that merely represent separate reports or versions. Different DOIs do not prove records are distinct, but also do not independently prove they are duplicates. These cases can be reviewed manually through ordinary screening or a future separately specified workflow.

## 4. Import and resolution behavior

### 4.1 Import transaction

1. Parse and validate the import into a staging batch. Keep each source record distinct, including repeated rows in the same input.
2. Preserve the original file/source identity, source row/order, raw fields, and import time.
3. Compute normalized comparison values and exact/fuzzy matches using the policy version active at import.
4. Commit all staged source-record occurrences, exact merges, audit events, open fuzzy candidates, and count deltas atomically. A retry of the same uncommitted operation is idempotent and cannot create a second partial import. A deliberate import of an already committed identical file is a new occurrence and must be explicitly started as a new import operation; it creates a new batch and fresh source-record IDs.
5. Present the import result with counts for source records received, exact records absorbed, fuzzy candidate pairs/groups queued, and net active records. Exact matches are not confirmation prompts; fuzzy matches stay unresolved and available to the reviewer.

No public standard dictates an import UI, transaction design, or these exact counters. They are first-principles requirements. PRISMA requires transparent selection-process reporting and distinguishes duplicates removed before screening.[S1] Database transaction atomicity is a useful implementation-level integrity model, not a requirement to use a particular database.[S7]

### 4.2 Fuzzy queue and decisions

For each open candidate group, Screening Workbench MUST provide, in an accessible representation:
- The candidate records side-by-side (or in an equivalent comparison layout), with record ID/source, title, authors, year/date, DOI, and other available bibliographic fields.
- Every field with unequal raw values visibly highlighted, and the actual values preserved verbatim. Missing versus present is a difference. Normalized equality with different raw formatting may be identified separately but must not be falsely presented as an identical raw value.
- The matching reason(s), the normalized title score, and enough metadata to verify why the pair was suggested.
- A way to inspect source values and prior deduplication history.
- Two explicit decisions: **merge** or **keep separate**. These action names describe behavior, not a mandated visual label or incumbent UI.

**Merge:** Reviewer chooses exactly one survivor and checks which linked candidate record(s) to absorb. Show a final confirmation naming the survivor and all affected records before committing. On commit, atomically mark selected records as duplicates of the survivor, preserve all original metadata and screening/audit history, resolve the relevant candidate links, record one merge event, and update counts. Unselected records remain active. If a selected record already belongs to another active duplicate cluster, resolve to the current survivor and reject cycles.

**Keep separate:** Mark that candidate pair as a reviewer-confirmed non-duplicate for the current record versions. Leave both records active; do not change screening status or PRISMA counts. Store actor, timestamp, candidate version/fingerprint, and decision. If matching-relevant metadata later changes, reopen/re-evaluate the pair and show the prior decision; never auto-merge it.

**No decision / defer:** Leaving or closing the queue does not change record state, active counts, or PRISMA counts. Open candidates remain findable and are not presented as confirmed duplicates. Screening may proceed with open fuzzy candidates; their existence and unresolved status remain visible in review-level deduplication status. This is a first-principles workflow choice, not established by a standard.

### 4.3 Undo and re-merge

Every automatic or reviewer merge MUST be reversible. Undo MUST:
- Restore the exact pre-merge active/duplicate relationships, field values, source provenance, and counts without deleting the original merge event.
- Append a separate undo event linked to the merge event, with actor, timestamp, and reason if provided.
- Leave prior screening decisions intact and restore records to their exact prior screening states.
- Reopen any still-applicable candidate links or recompute them from current values; never automatically re-merge a just-undone pair in the same transaction.

If a merge is undone after later edits, merges, or screening actions depend on it, Screening Workbench MUST detect the dependency and either perform a validated compensating undo that preserves later events or block the undo with an explanation and safe next action. It MUST NOT silently orphan records, create duplicate active survivors, erase history, or fabricate a successful undo. Exact behavior for complex concurrent/conflicting history is **not established by public sources**; this safe conflict rule is proposed from first principles.

## 5. Data-model sketch (logical; not code)

| Entity | Required attributes / invariants |
|---|---|
| `ReviewProject` | Immutable `project_id`; dedup policy/version; screening lifecycle state; project-local record namespace. No cross-project deduplication. |
| `ImportBatch` | Immutable `batch_id`, project, source name/type, source fingerprint, imported-at timestamp, import status, input-row count, committed record count, policy version. A repeated identical source can be detected, but importing it again must not duplicate records unless the user explicitly requests a new import occurrence. |
| `Record` | Immutable `record_id`, project, active/duplicate state, `duplicate_of_record_id` nullable, created-at, current screening state, optional survivor/user-edit metadata. Duplicate pointers resolve to one active root; no cycles; a survivor cannot point to itself. |
| `RecordValue` | Record ID, field name, raw value, source/batch/row provenance, optional normalized value, and edit status (imported vs user-curated). Multiple conflicting values are retained. Raw values are immutable source evidence; edits append/version rather than destroy imported values. |
| `DedupCandidate` | Candidate/group ID, project, pair endpoints, generated-at, algorithm/policy version, score/reasons, metadata fingerprint, state (`open`, `merged`, `kept_separate`, `stale`), optional superseding candidate. One pair can have only one current decision for a given metadata version. |
| `DedupEvent` | Append-only event ID; event kind (`exact_merge`, `reviewer_merge`, `keep_separate`, `undo`, `recompute`); RFC 3339 timestamp with UTC offset; actor ID or explicit `system` actor; affected records; chosen survivor; before/after state references; rule/version/reason; reversible event link. Never update or delete an event to make history disappear.[S8] |
| `ScreeningEvent` | Append-only decision history by record/reviewer/time. A record is counted as removed **before screening** only if it had no screening decision before the merge event. |
| `ProjectCounts` (derived) | Computed from record and event state, not independently editable counters: source records imported; current active records; currently absorbed duplicate records; pre-screening duplicate removals; post-screening merges; open fuzzy pairs/groups. |

**Data integrity invariants:**
- Every record, candidate, event, and merge relationship belongs to exactly one project.
- Every absorbed record resolves transitively to exactly one active survivor; no cycles; exact/reviewer merges preserve all member IDs and values.
- Original record/source values and event history survive merge, undo, and application restart.
- A merge event is all-or-nothing across relationship changes, survivor selection, candidate resolution, and derived counts.
- Current active-record count equals imported source records in the project minus currently absorbed records, subject to explicitly documented non-record exclusions; deduplication itself never permanently deletes a record.
- Replaying the same committed event stream from its initial state produces the same current duplicate relationships and PRISMA counts.
- A reviewer decision must record the acting account; automated exact action must identify a system actor and rule/version. Timestamps are unambiguous RFC 3339 date-times with an explicit offset (prefer UTC `Z`).[S8]

## 6. Counts and PRISMA behavior

PRISMA 2020 includes duplicate records removed among pre-screen removals.[S1] Count **absorbed source-occurrence rows**, not groups or merge events. For each absorbed row, examine its own vote history immediately before the merge:

- No prior vote: count once in `duplicates_removed_before_screening`.
- Prior vote: preserve its historical screened count and count once in `duplicates_merged_after_screening`.

A mixed group may contribute rows to both categories. Do not classify every member as post-screen merely because another member has a vote. The duplicate specification uses the same row-level rule; group events/correction events are recorded separately from row counts. Selected canonical occurrence determines downstream report branch; preserve all source occurrence IDs, votes, and originating branches. A row already counted as absorbed cannot contribute a second removal on a later survivor change; undo reverses the affected current projection and remerge creates the applicable row-count contribution once, based on state immediately before remerge.

Maintain separate derived values:
- `active_records`: active records currently available to screening;
- `duplicates_removed_before_screening`: absorbed rows with no prior vote immediately before merge;
- `duplicates_merged_after_screening`: absorbed rows with prior votes (historical screened count retained);
- `open_fuzzy_pairs` and `open_fuzzy_groups`: unresolved suggestions, not removals.

The report states snapshot/counting point and avoids double-counting across survivor changes. Undo adjusts current derived counts but retains audit history. Never imply this count alone fills every PRISMA field.

## 7. Edge-case acceptance requirements

| Case | Expected result |
|---|---|
| Same DOI, case differs; one value has resolver prefix; normalized titles agree | Normalize to same DOI; exact silent merge; retain raw DOI values and provenance. |
| Same DOI, punctuation outside DOI differs; normalized titles agree | Strip only allowed resolver/trailing citation punctuation; exact merge if identifier remains unambiguous and titles agree. |
| Same DOI but normalized titles materially differ, or either title is missing | No silent merge; retain both active and create manual-review candidate tagged `doi_match_title_mismatch`. |
| DOI absent on one or both; exact normalized title and shared publication year | Exact silent merge. |
| Identical title, years both missing | No exact merge; no fuzzy candidate without a year. |
| Identical title but known years do not overlap | No exact title/year merge; no fuzzy candidate. |
| Title capitalization, Unicode compatibility form, punctuation, or whitespace varies; shared year | Same normalized title; exact merge. |
| Diacritics differ in titles | Not normalized away; may qualify only under fuzzy threshold plus same first author/year. Preserve both raw forms. |
| Same first author/year and score exactly 0.90 | Fuzzy candidate, not automatic merge. |
| Same first author/year and score below 0.90 | No candidate under this version. |
| Same DOI and normalized titles agree, but year/author/other metadata conflicts | Merge automatically on DOI+title; preserve all values, flag differences in record details/history; no value is silently overwritten. |
| Similar title, different known first author | No fuzzy candidate under this version. |
| Two reports have similar titles but different DOIs and represent different publication types | Do not exact-merge on DOI; fuzzy candidate only if every §3.2 rule passes; reviewer can keep separate. Different bibliographic records are not automatically duplicates just because they report one study.[S3][S4] |
| Fuzzy component A–B and B–C, but A–C does not qualify | Present component/pair links; merging A with C is unavailable unless their direct pair qualifies. |
| Import contains two or more exact matches and a fuzzy candidate | Apply only exact merges meeting §3.1; queue DOI/title conflicts for review, and queue still-valid fuzzy pairs among current active records. |
| Import is retried after a committed batch | Idempotency/source-identity policy prevents accidental duplicate import; explicit new occurrence remains auditable. |
| Crash/error during merge/undo | On restart, state is entirely pre-operation or post-operation; no partial relationship or count update. |
| Same input imported from distinct sources with different raw citation formatting | Distinct provenance retained; exact or fuzzy policy applies to records; source occurrences remain traceable. |
| User edits title/author/year after a keep-separate decision | Prior decision retained against old fingerprint; re-evaluate and visibly reopen if pair now qualifies. |

## 8. Performance, local-first, and offline requirements

These are **first-principles acceptance targets**, not externally established Screening Workbench performance claims. Validate on a documented reference machine and a fixture with realistic metadata and candidate density; record machine, OS, dataset, policy version, elapsed time, and peak memory in the test report.

- On a reference desktop with 4 logical CPU cores and 8 GB RAM, processing a batch of 10,000 records against a 100,000-record project MUST finish exact-key indexing and exact grouping within 30 seconds; fuzzy candidate generation MUST finish within 120 seconds, excluding user review. Peak additional memory MUST stay below 1 GB. Targets may be revised only through an explicit versioned product decision and rerun benchmarks.
- Exact detection MUST use keyed/indexed comparisons, not all-pairs comparison over every project record. Fuzzy candidate generation SHOULD block comparisons by shared publication year and normalized first-author key before applying title distance; it must return every pair meeting the specified rule, with no approximate-search cutoff that silently omits qualifying candidates. If practical constraints require a cap, the import MUST surface the incomplete scan and never claim it completed deduplication.
The current proposal for an approximate candidate-density guard is: if a matching block exceeds 50,000 pair comparisons, complete all exact matching, but do not truncate fuzzy results silently. Show an explicit “fuzzy pass incomplete” state and queue generation for narrower/manual review; the user may raise the limit and rerun. The UI must not report deduplication as complete while any fuzzy block is unfinished. This is a first-principles performance safeguard pending benchmark validation.
- After a successful commit, the active count and queue state are available immediately; opening a candidate must not require network access.
- Exact and fuzzy detection, review, merge, undo, audit inspection, count derivation, and project reopen MUST work with networking disabled. No DOI registry query, telemetry, cloud processing, account, or external service is a prerequisite. Any later optional enrichment must be separately consented, explicitly online, and must not change a local dedup decision without a visible re-reviewable event.
- Records and deduplication history remain on the user's device under the local-first model. Backup/export and protection against local disk failure are product responsibilities outside the specific dedup algorithm; a local database alone is not a backup.

## 9. Keyboard and assistive-technology requirements

WCAG 2.2 requires keyboard-operable functionality, visible keyboard focus, and programmatically available status messages for markup-based interfaces.[S9][S10][S11] The specific interaction behavior below applies those principles to this feature; it does not prescribe a visual style or copy exact UI wording.

- Every import, candidate inspection, survivor choice, member selection, merge confirmation, keep-separate decision, undo, and history action MUST be operable using a keyboard without a pointer and without timing-dependent key sequences.[S9]
- Tab/Shift+Tab move through controls in a logical order. Native control behavior (Space/Enter to activate buttons or checkboxes; arrow keys for radio groups where used) MUST work. Do not introduce keyboard traps; provide a keyboard route into and out of comparison details and dialogs.[S9]
- Focus MUST remain visibly identifiable whenever moved by keyboard and MUST not become entirely hidden behind fixed or overlay content.[S10][S12]
- When import, merge, undo, or candidate resolution changes counts/status without moving focus, expose a programmatically determinable status announcement without forcing focus to the message.[S11]
- Side-by-side comparison must have a meaningful reading order and accessible field names/values. Difference indication cannot rely on color alone; include a text/semantic indication. The chosen survivor and records to be absorbed must be identifiable to assistive technology before confirmation.
- Keyboard acceptance test: complete import, inspect a fuzzy pair, choose a survivor, select one record, confirm merge, inspect updated counts, undo, and verify restored state using only keyboard; verify visible focus and that success/failure status is announced.

## 10. Verification plan / release gates

The feature is conformant only when all required tests below pass against a clean project and against a populated project. Tests must assert database-visible state and user-visible behavior; screenshots alone are insufficient.

1. **Normalization unit fixtures:** Test each DOI/title/year/author rule in §3.1, including malformed/multiple DOI, missing metadata, punctuation, Unicode compatibility characters, case, diacritics, partial dates, conflicting dates, and prohibited date sources.
2. **Exact-match integration fixtures:** DOI+normalized-title, title+year-only, within-batch, across-batch, three-record groups, bridge groups, conflicting metadata, and deterministic survivor tie-breaks. Assert silent behavior only where §3.1 permits; DOI/title conflicts and missing-title DOI matches remain active in manual review, with all values preserved and exact candidate/active counts asserted.
3. **Fuzzy boundary fixtures:** Scores below, exactly at, and above 0.90; equal/different/missing first author; shared/non-shared/missing year; exact-vs-fuzzy priority; and chain components. Assert candidate list, score, reasons, no pre-decision record removal, and no count effect.
4. **Reviewer workflow fixtures:** Merge with each possible survivor, partial selection within a group, keep one pair separate while another remains open, defer, stale candidate after edit, and a record already absorbed elsewhere. Assert no cycles, no silent propagation, visible differences, decision provenance, and transactional count updates.
5. **Undo/history fixtures:** Undo automatic and reviewer merges; repeated undo; re-merge after undo; undo with later dependent edits/screening/merges; actor/timestamp presence; preserved raw metadata and screening events; and restart/replay. Assert safe refusal or validated compensation on dependency conflicts.
6. **PRISMA/count fixtures:** Groups of size 1/2/n, exact and fuzzy merge before screening, merge after screening, partial-screened group, undo/re-merge, and multiple survivor changes. Assert counts are record counts, pre-screening and post-screening are separated, unresolved candidates are excluded, and no double count occurs.[S1]
7. **Reliability fixtures:** Inject failure before/during/after import, merge, undo, and persistence. After restart assert each operation is all-or-nothing and history/counts reconcile.[S7]
8. **Offline and scale fixtures:** Run the complete required workflow with network interfaces disabled; verify no network dependency. Benchmark §8 dataset sizes and record the required environment/results. Simulate cancellation and assert no partial commit.
9. **Accessibility fixtures:** Keyboard-only workflow in §9, logical focus sequence, no trap, visible/unobscured focus, semantic difference cues, and non-focus-stealing status announcement.[S9][S10][S11][S12]
10. **Error accounting:** Against a manually adjudicated, versioned test corpus, report false positives (unique records marked duplicates) and false negatives (duplicates retained) separately, plus precision/recall or equivalent rates. Any confirmed false positive in an exact auto-merge fixture blocks release; fuzzy candidate errors must never silently remove records. Public evaluation shows both error types occur and highlights the cost of removing unique records, so reporting only aggregate accuracy is insufficient.[S3]

## 11. Decisions that remain unverified

No public standard defines Screening Workbench's exact normalization function, fuzzy threshold, candidate grouping, survivor tie-break, UI layout, keyboard shortcuts, offline architecture, performance targets, merge conflict policy, or data schema. This document specifies those from first principles and labels the numeric/interaction choices as proposals. The 0.90 threshold and performance envelope require product-owner approval and empirical validation on representative review exports before release. Public guidance supports transparent counts and cautious review, not the claim that this particular algorithm is best for every dataset.[S1][S2][S3]

## 12. Public sources

All sources below are public standards, documentation, or scholarly sources. Accessed 2026-10-06.

- **[S1] PRISMA statement, “PRISMA 2020 flow diagram.”** Public templates and explanatory page; duplicate records are shown under records removed before screening. Page undated; PRISMA 2020 statement published in 2021. https://prisma-statement.org/prisma-2020-flow-diagram
- **[S2] Cochrane Handbook, Chapter 4 Technical Supplement, “Searching for and selecting studies,” §4.3 “De-duplicating references.”** Cited edition: version 6.5, supplement last updated September 2024; the page discusses risks, methods, lack of consensus on a universally optimal method, and visual verification. https://www.cochrane.org/authors/handbooks-and-manuals/handbook/chapter04-tech-supplonlinepdfv65270924
- **[S3] McKeown S, Mir ZM. “Considerations for conducting systematic reviews: evaluating the performance of different methods for de-duplicating references.” _Systematic Reviews_ 10, article 38 (published 2021-01-23). DOI: 10.1186/s13643-021-01583-y. https://link.springer.com/article/10.1186/s13643-021-01583-y
- **[S4] Cochrane Handbook, Chapter 4, “Searching for and selecting studies,” §4.6.2 “Identifying multiple reports from the same study.”** Current public online chapter; page version date not established in retrieved page. https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04
- **[S5] DataCite Support, “DataCite DOI Display Guidelines.”** Public DOI display documentation; accessed 2026-10-06 (page metadata showed update 2026-08-07). DOI names are not case-sensitive. https://support.datacite.org/docs/datacite-doi-display-guidelines
- **[S6] Crossref, “REST API.”** Public documentation for scholarly metadata endpoints and retrieval; page undated, accessed 2026-10-06. https://www.crossref.org/documentation/retrieve-metadata/rest-api/
- **[S7] SQLite, “Transactional.”** Public technical documentation describing atomic/consistent/isolated/durable transactions; accessed 2026-10-06. Used only as an example of the all-or-nothing integrity model, not as a mandated Screening Workbench technology. https://sqlite.org/transactional.html
- **[S8] IETF RFC 3339, “Date and Time on the Internet: Timestamps.”** July 2002. Defines unambiguous date-time syntax with stated UTC relationship. https://www.rfc-editor.org/rfc/rfc3339.html
- **[S9] W3C, “Understanding Success Criterion 2.1.1: Keyboard,” WCAG 2.2.** WCAG 2.2 Recommendation dated 2024-12-12; criterion requires functionality operable through a keyboard interface. https://www.w3.org/WAI/WCAG22/Understanding/keyboard.html
- **[S10] W3C, “Understanding Success Criterion 2.4.7: Focus Visible,” WCAG 2.2.** WCAG 2.2 Recommendation dated 2024-12-12. https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html
- **[S11] W3C, “Understanding Success Criterion 4.1.3: Status Messages,” WCAG 2.2.** WCAG 2.2 Recommendation dated 2024-12-12. https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html
- **[S12] W3C, “Understanding Success Criterion 2.4.11: Focus Not Obscured (Minimum),” WCAG 2.2.** WCAG 2.2 Recommendation dated 2024-12-12. https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html

# Screening Workbench v1 — PRISMA Counts and Export Behavioral Specification

> Local-first, deterministic behavior and data contract for PRISMA 2020 count/export support. Informed by public reporting guidance; no PRISMA artwork/template or incumbent UI is copied. Access date for cited sources: 2026-10-06. Requirements here define Screening Workbench, not software behavior prescribed by PRISMA.

## 1. Scope and normative language

Covers imported-source identification, dedup disposition, title/abstract screening, retrieval/full-text eligibility, explicit study/report association, derived counts, audit, and local exports. Excludes search execution, appraisal, synthesis, and prior-review carry-forward except configured metadata. **MUST**, **MUST NOT**, **SHOULD**, **MAY** express requirements. Counts are derived non-negative integers, not manually edited summaries.

## 2. Behavioral requirements

### 2.1 Import and identification

1. Each import operation has a stable ID; retrying an uncommitted operation commits once. A deliberate re-import creates a new batch and occurrence IDs.
2. Each occurrence links to one batch/source; retain raw/mapped values, source class, branch, locator, and provenance.
3. Each source has one class: `database`, `register`, or `other_method`. Occurrences inherit class and configured branch, and count once by source class.
4. Each batch has one source and branch. Preview requires explicit classification before commit; no implicit default. Split or explicitly group mixed files. Classification is immutable; corrections and prospective configuration changes are audited/versioned.
5. Occurrence, canonical progression occurrence, report, and study are distinct. V1 has explicit user-managed `Study` entities and many-to-many `ReportStudy` links; never infer studies from reports or similarity.

### 2.2 Duplicate handling and screening

1. Dedup creates audited relationships with one canonical member; never delete source occurrences.
2. Classify each absorbed row using its own pre-merge vote history: no vote counts once as pre-screen removal; prior vote retains historical screened count and counts once as post-screen correction. Mixed groups can contribute to both; count merge events separately.
3. Preserve occurrence votes; canonical outcome is separate. Partial/conflicting votes or post-screen corrections require adjudication before report progression.
4. Votes are include/maybe/exclude keyed by occurrence, review, stage, reviewer. Exclude requires one stage-specific reason; maybe/conflict remains pending.
5. Blind mode isolates another reviewer’s decisions through app-controlled views, queries, search, ranking, diagnostics, logs, and exports. Audit/replay may retain votes.

### 2.3 Report progression


1. Preserve `RecordReport` occurrence-to-report provenance. Assign each distinct report exactly one explicit `ReportProgression` with selected canonical occurrence and source branch; report flow advances once only.
2. For occurrences from multiple source branches linked to one report, the progression decision selects one canonical occurrence/branch. Log the decision and retain every source occurrence and its historical screening/removal state.
3. Retrieval attempts are explicit. A sought report without a final retrieval result is pending. Not-retrieved reports have no full-text exclusion reason.
4. Each assessed report has one terminal full-text result. Every excluded report has exactly one primary full-text reason; title/abstract vote reasons remain separate.

### 2.4 Required study/report association

1. Each `Study` has an explicit audited decision: `included`, `excluded`, or `unresolved`, with actor, timestamp, rationale, and event ID. A report link alone does not include a study; only an explicit authorized `included` decision contributes to `studies_included`.
2. Users create/select studies and explicitly link included reports. Associations are many-to-many; never infer links from bibliographic similarity.
3. A complete export requires every included report to link to at least one explicitly included study; every counted study links to at least one included report. Unresolved/missing eligible links block complete export. An explicitly confirmed incomplete export discloses missing links and unresolved decisions.
4. Derive `reports_of_included_studies` and `studies_included` from distinct entity IDs, not link rows; neither count is assumed to bound the other.
5. Link add/correction/removal and study decision/correction are append-only events with actor, timestamp, IDs, rationale, and sequence. Replay updates current projections; earlier snapshots remain unchanged.
### 2.5 Study/report conflict resolution

A conflict exists when a study is included with no terminal included report, a study is excluded despite an included linked report, or the study decision is unresolved/competing. A study can have multiple reports with mixed outcomes if at least one is included; other excluded/not-retrieved reports do not alone negate inclusion. If all linked reports are excluded/not-retrieved while the study is included, this is a conflict that blocks complete export. Pending linked reports also keep the project incomplete. Resolve using an authorized replacement decision with rationale; a third reviewer may be assigned as tie-breaker. Append corrections, never overwrite. Unresolved decisions appear in incomplete export and are excluded from `studies_included`.
### 2.6 Snapshot, authorization, and completeness

1. All package artifacts share one immutable snapshot: project/review IDs, `as_of`, event watermark, source configuration, completeness, and derived counts.
2. A complete export is blocked by failed invariants or unresolved pending items. Incomplete export requires explicit confirmation and lists all unresolved categories/counts.
3. All exports are user-triggered and local; unresolved work is disclosed, never terminal.
4. Every export attempt is audited. Export event follows its snapshot watermark and appears in a subsequent audit export.
5. The project owner is fixed at project creation. Only the owner may grant/revoke a local `auditor` role with `audit_read` and/or `full_export` scope. Each grant/revocation requires owner confirmation and records actor, target, scope, timestamp, and reason in append-only audit history. Reviewers cannot grant themselves roles. Revocation denies subsequent access/exports immediately; prior exports remain immutable and audited.
6. While blind, reviewers may export only their own permitted decisions; this subset is partial and cannot be labeled complete. Only the owner or current auditor with `full_export` may export all votes/full audit. Test UI/API/diagnostic/log authorization, grant/revoke, self-grant denial and post-revocation denial.

## 3. Count model

### 3.1 Identification and screening

Count imported source occurrences by originating source class before pre-screen removals:

```text
identified_database    = occurrences from database sources
identified_register    = occurrences from register sources
identified_other       = occurrences from other-method sources
identified_db_register = identified_database + identified_register
identified_total       = identified_db_register + identified_other
removed_before_screen  = removed_duplicate_before_screen + removed_automation + removed_other
identified_b           = imported source occurrences in branch b

identified_b = removed_before_screen_b + prescreen_pending_b
             + screening_pending_b + records_screened_b
```

`records_screened_b` is the historical number of source occurrences with terminal title/abstract votes; later duplicate correction never erases or reduces it. Per absorbed row, `removed_duplicate_before_screen` counts rows without a prior vote; `post_screen_duplicate_corrections` separately counts absorbed rows with a prior vote. Mixed groups can contribute to both. A complete project has no pending terms. `canonical_outcomes_b` separately counts selected canonical occurrences used to progress.

### 3.2 Report retrieval and full-text

`reports_sought` counts distinct reports selected to progress beyond screening, not occurrences or study reports. Each report chooses one canonical occurrence/branch progression. One report advances once despite cross-branch duplicate records; ambiguous branch ownership is resolved explicitly before advancement.

`reports_not_retrieved`, `reports_assessed`, `reports_excluded`, and `reports_included` count distinct progressed reports. `reports_pending` is separate; pending is never silently treated as exclusion.

```text
reports_assessed = reports_included + reports_excluded
reports_sought   = reports_assessed + reports_not_retrieved + reports_pending
```

### 3.3 Included reports and studies

An included report has an explicit included full-text outcome. `reports_of_included_studies` counts distinct included reports linked to at least one explicitly included study; `studies_included` counts distinct explicitly included studies linked to at least one included report. A link alone never sets inclusion.

One included and one excluded linked report may coexist with an included study. All linked reports excluded while study included is a conflict; an authorized, rationale-bearing audited correction is required before complete export. Unlinked studies do not contribute to included-study count or complete export.

```text
reports_of_included_studies = distinct included reports linked to >=1 included study
studies_included            = distinct included studies linked to >=1 included report
```

Once all sought reports resolve: `reports_included = reports_sought - reports_not_retrieved - reports_excluded`.

### 3.4 Invariants

1. `removed_before_screen_b = removed_duplicate_before_screen_b + removed_automation_b + removed_other_b`.
2. Pending, removed, and screened occurrence sets reconcile to identified records without overlap. Each absorbed duplicate row is assigned exactly once by its own vote history at absorption.
3. Each distinct report has at most one progression/branch; it advances once from the selected canonical occurrence.
4. Each screened occurrence has one terminal vote state; pending/conflicts have none.
5. Each sought report is not-retrieved, assessed, or pending. Assessed reports are included or excluded; each excluded report has one primary reason.
6. Reports and studies are distinct; links are many-to-many and counts use distinct IDs. The conflict rule in §2.5 applies.
7. Relevant decisions, duplicate changes, reasons, progression/outcomes, study decisions/links, and undo invalidate/recompute snapshots.
8. Empty-log replay reconstructs occurrences, votes, dispositions, progression, reports, studies, links, counts, and snapshots.

```text
reports_sought_b         = distinct reports with explicit retrieval attempt
reports_not_retrieved_b  = sought reports marked not_retrieved
reports_sought_pending_b = sought reports without final retrieval result
reports_assessed_b       = sought reports with completed full-text assessment
reports_excluded_b       = assessed reports with outcome excluded_full_text
reports_included_b       = assessed reports with outcome included
reports_assessed_b       = reports_excluded_b + reports_included_b
sum(full_text_reason_count_b[r]) = reports_excluded_b
reports_sought_b = reports_not_retrieved_b + reports_assessed_b + reports_sought_pending_b
```

Each report appears once at each stage in its one `ReportProgression.branch_id`. A cross-branch duplicate report uses the logged canonical progression; occurrences in all source branches remain in provenance and source-level identification accounting.
## 4. Logical data-model sketch

The logical entities define identities and relationships; storage may vary if behavior is preserved.

| Entity | Required behavior |
|---|---|
| `Source` / `Branch` | Immutable IDs/class (`database`, `register`, `other_method`); each source maps to one branch. Occurrences inherit both; corrections are audited. |
| `ImportBatch` / `Record` | Retry-safe batch with one source/branch; immutable occurrence ID, provenance and raw/mapped values. |
| `DuplicateGroup` | Canonical occurrence, absorbed rows, matching provenance. |
| `ScreenVote` / `ScreenResolution` | Per-occurrence votes; separate canonical outcome. |
| `PreScreenDisposition` / `PostScreenCorrection` | Per-row classification from own vote history; auditable and reversible. |
| `Report` / `RecordReport` | Distinct report and occurrence provenance. |
| `ReportProgression` | One selected canonical occurrence/branch per progressing report. |
| `FullTextAssessment` / `ReportExclusion` | Terminal report outcome and one primary reason if excluded. |
| `Study` / `StudyDecision` | Distinct study; explicit included/excluded/unresolved decision with rationale/event. |
| `ReportStudy` | Audited many-to-many association; does not imply study inclusion. |
| `AuditEvent` / `ExportSnapshot` | Versioned replay and immutable watermarked export/count snapshot. |

## 5. Export contract

A complete local package contains:
- `prisma-flow.svg` from one validated snapshot with original Screening Workbench artwork. V1 does not export PNG; optional PNG requires a separate owner scope decision and dependency audit.
- `decisions.csv` with occurrence provenance, votes/reasons, resolution, report progression/outcome, study decision and link IDs.
- `report-study-links.csv` with normalized links, actor/time/event ID.
- `audit-log.jsonl` through the watermark.
- `manifest.json` with IDs, timestamp, watermark, completeness, counts, format versions and package hashes.

The SVG presents occurrence, report and study grains, relevant PRISMA stages/reasons and pending/conflict states. Incomplete exports disclose status/unresolved counts. It provides accessible title/description and searchable numbers.

CSVs are UTF-8, stable/versioned and RFC 4180 compatible; provide lossless machine and labeled spreadsheet-safe variants, test formula-leading values, and distinguish null from pending/not-applicable.

Audit events cover imports/mappings, duplicate actions/undo, votes/reasons, unblind, conflict/study decisions, report progression/retrieval/full-text, links/corrections, exports. Events contain actor, time, IDs, schema version, sequence, replay payload. Export's own event occurs after its watermark, appears in later audit export, and authorization follows §2.6.




## 6. Acceptance tests

1. Import retry is idempotent; deliberate re-import creates new occurrence IDs. Verify occurrence balance, exclusive removals, pending, and mixed-group correction: one voted plus one unscreened absorbed row yields one pre-screen removal and one post-screen correction; preserve the vote.
2. Cross-branch fixture links duplicate occurrences to one report; select one canonical occurrence/branch. It advances once; replay/correction/undo restore expected counts.
3. Retrieval fixture: four sought reports, one pending, one not retrieved, one assessed included, one assessed excluded with reason X. Assert sought=4, pending=1, not_retrieved=1, assessed=2, included=1, excluded=1, reason total=1, and both retrieval equations.
4. Study/report fixture: three reports, two studies, four links. R1 included, R2 excluded (reason X), R3 not retrieved; S1 included linked to R1/R2; S2 excluded linked to R2/R3; include a repeated link-add/correction event that leaves the active relationship set at three distinct pairs but four link-history rows. Assert active study count uses distinct IDs and does not change with the duplicate history event. Assert sought=3, not_retrieved=1, assessed=2, included=1, excluded=1, reason-X=1, included-study reports=1, studies included=1, links=4. Correct S2 to included; its linked reports are excluded/not-retrieved, so conflict blocks complete export. Correct back to excluded with rationale; assert count 1 and replayable audit.
5. Study conflict fixture: all linked reports excluded while study included blocks complete export; one included plus one excluded report may support an included study. Test unresolved/competing decisions, authorized resolution/rationale, correction/undo and replay.
6. Source/branch fixture: create x1(database/A, screened include), x2(database/A, screened maybe), x3(register/B, screened include), and x4(database/A, unscreened), all linked to one report R1. Before any merges assert identified-stage equations: branch A 3=removed 0+prescreen pending 0+screening pending 0+screened 3; branch B 1=removed 0+prescreen pending 0+screening pending 0+screened 1; source-class totals database=3/register=1. Merge x4 into x1 before it is screened: x4 contributes one pre-screen removal; A then reconciles 3=removed 1+pending 0+screened 2. Then discover x2’s duplicate with conflicting vote and merge after screening: preserve its historical vote, count one post-screen correction (not a second pre-screen removal), and adjudicate before progression. Select canonical x1/A: R1 advances once in A; x3 remains provenance and source identification but does not advance again in B. Repeat a fresh fixture selecting x3/B and assert R1 advances once in B, without changing source-class totals. Replay/undo reproduces counts.
7. Export authorization while blind: reviewer export excludes others’ votes and is partial; owner/auditor can export full package. Probe UI/API/diagnostic/log routes; test grant/revoke, unauthorized self-grant denial, post-revocation denial.
8. Watermark: package contains all events through watermark; export event appears in a later export; prior files unchanged.
9. Cold offline: invalid replay, unresolved conflicts, missing links or local-write failure prevents complete package and preserves prior artifacts. Verify SVG flow generation; PNG is explicitly out of v1.

### 6.1 Known v1 implementation limitations (2026-10-07)

These remain product-scope gaps, not claims of test coverage:

- `removed_automation` and `removed_other` are specified PRISMA removal subcategories but have no v1 action/classification paths. Only duplicate-based `removed_before_screen` is implemented; the other terms remain zero. The full equation is not independently exercised for those categories.
- Invariant 8's empty-log event replay is not implemented. Events are appended and applied to live projections, but there is no generic replayer that reconstructs the complete state from an empty database. Acceptance fixture 9's invalid-replay scenario therefore remains untestable until replay exists.

## 7. Sources

- **[S1]** Page MJ, McKenzie JE, Bossuyt PM, et al. “The PRISMA 2020 statement: an updated guideline for reporting systematic reviews.” *BMJ* 2021;372:n71. https://pmc.ncbi.nlm.nih.gov/articles/PMC8005924/ ; DOI https://doi.org/10.1136/bmj.n71
- **[S2]** Page MJ, Moher D, Bossuyt PM, et al. “PRISMA 2020 explanation and elaboration: updated guidance and exemplars for reporting systematic reviews.” *BMJ* 2021;372:n160. https://pmc.ncbi.nlm.nih.gov/articles/PMC8005925/ ; DOI https://doi.org/10.1136/bmj.n160
- **[S3]** PRISMA Executive. “PRISMA 2020 flow diagram.” https://www.prisma-statement.org/prisma-2020-flow-diagram
- **[S4]** PRISMA Executive. “PRISMA 2020 checklist.” https://www.prisma-statement.org/prisma-2020-checklist



# PRISMA count equation → test mapping (priority 2 closure audit)

Produced 2026-10-07 per Cinder's instruction: "for each equation in the
9-fixture acceptance spec ... name the test file and test that exercises
it." Source: `docs/specs/behavioral-spec-prisma-counts-export.md` §3
(Count model) and §6 (Acceptance tests). The original equation audit ran
201 tests; the October 2026 validation pass added coverage for pending
maybe-votes. The historical 204/204 result below is not current suite
status; run the test suite against the checkout being assessed.

## §3.1 Identification and screening

| Equation | Test file :: test | Note |
|---|---|---|
| `identified_database` | `test_prisma_counts.py::test_identified_other_method_source_class_and_totals` (also `test_acceptance_6_source_branch_fixture`) | |
| `identified_register` | same | |
| `identified_other` | `test_prisma_counts.py::test_identified_other_method_source_class_and_totals` | **Gap found and closed this round** — zero coverage anywhere before this test; every prior fixture only used `database`/`register` source classes. |
| `identified_db_register = identified_database + identified_register` | same | **Gap found and closed this round.** |
| `identified_total = identified_db_register + identified_other` | same | **Gap found and closed this round.** |
| `removed_before_screen = removed_duplicate_before_screen + removed_automation + removed_other` | `test_prisma_counts.py::test_acceptance_6_source_branch_fixture`, `test_mixed_vote_duplicate_counted_as_post_screen_correction` | **Partial, named not silently passed:** only `removed_duplicate_before_screen` exists as an implemented classification in v1 — `removed_automation` and `removed_other` are not features of this version (no automation-tool or other removal path exists), so those two terms are always 0 and the 3-term equation is never exercised with non-zero values for them. The equation trivially holds in every test because of this, not because all three terms were tested independently. |
| `identified_b = removed_before_screen_b + prescreen_pending_b + screening_pending_b + records_screened_b` | `test_acceptance_6_source_branch_fixture` (explicit per-branch equation assertions before/after merge) + `prisma.verify_invariants()` in the listed test suites | `prescreen_pending_b` is a documented v1 simplification fixed at 0 (fuzzy candidates don't block screening eligibility yet). Dogfood exposed that a `maybe` vote was incorrectly counted as terminally screened; `_branch_breakdown` now counts only final include/exclude votes (and resolved outcomes), while `maybe`, unresolved conflicts, and no-vote rows remain screening-pending. The fixture now pins this behavior. |

## §3.2 Report retrieval and full-text

| Equation | Test file :: test |
|---|---|
| `reports_assessed = reports_included + reports_excluded` | `test_reports.py::test_retrieval_fixture_four_reports` (acceptance fixture 3), `prisma.verify_invariants()` |
| `reports_sought = reports_assessed + reports_not_retrieved + reports_pending` | same |

## §3.3 Included reports and studies

| Equation | Test file :: test |
|---|---|
| `reports_of_included_studies = distinct included reports linked to >=1 included study` | `test_studies.py::test_acceptance_4_study_report_fixture` |
| `studies_included = distinct included studies linked to >=1 included report` | same, plus `test_app.py` (UI-level) |
| `reports_included = reports_sought - reports_not_retrieved - reports_excluded` (once all sought reports resolve) | `test_reports.py::test_retrieval_fixture_four_reports` exercises the additive form (`reports_assessed = included + excluded`); the subtractive restatement isn't asserted as a separate expression, but it's algebraically identical to the additive form already covered — not treated as an independent gap. |

## §3.4 Invariants

| Invariant / equation | Test file :: test |
|---|---|
| 1. `removed_before_screen_b = removed_duplicate_before_screen_b + removed_automation_b + removed_other_b` | Same partial-coverage note as the non-branch-scoped version above. |
| 2. Pending/removed/screened reconcile without overlap; each absorbed row assigned once by its own vote history | `test_dedup.py::test_mixed_group_classification_vote_preserved`, `test_prisma_counts.py::test_mixed_vote_duplicate_counted_as_post_screen_correction` |
| 3. Each report has at most one progression/branch; advances once | `test_reports.py::test_report_advances_once_second_assignment_rejected`, `test_cross_branch_fixture_advances_once`; `test_prisma_counts.py::test_acceptance_2_progression_correction_switches_canonical_branch` (correction path) |
| 4. Each screened occurrence has one terminal vote state | `test_screening.py` (vote supersession tests), `prisma.verify_invariants()` |
| 5. Each sought report is not-retrieved/assessed/pending; assessed are included/excluded; one primary reason each | `test_reports.py::test_retrieval_fixture_four_reports`, `test_excluded_requires_reason`, `test_included_must_not_carry_reason` |
| 6. Reports/studies distinct; links many-to-many, distinct IDs; §2.5 conflict rule | `test_studies.py::test_acceptance_4_study_report_fixture`, `test_acceptance_5_study_conflict_fixture` |
| 7. Relevant decisions/corrections/undo invalidate+recompute snapshots | `test_screening.py::test_undo_last_vote_restores_undecided`, `test_dedup.py::test_undo_merge_restores_active_state`, `test_prisma_counts.py`'s correction tests — all recompute via fresh function calls, not cached state, so this holds by construction rather than a dedicated snapshot-invalidation test. |
| 8. Empty-log replay reconstructs full state | **Named gap, not silently passed:** no generic event replayer exists in this codebase yet (confirmed via code search for `replay_all`/`def replay`, zero real matches beyond docstring mentions). `test_dedup.py::test_replay_reproduces_same_dedup_state` uses a "behavioral replay proxy" (re-running the same operations against a fresh DB) rather than true log replay, by its own docstring's admission. This cannot be closed by a test alone — it needs the replay feature built first. |
| `reports_sought_b`, `reports_not_retrieved_b`, `reports_sought_pending_b`, `reports_assessed_b`, `reports_excluded_b`, `reports_included_b`, `sum(full_text_reason_count_b[r]) = reports_excluded_b` | `test_reports.py::test_counts_by_branch_sums_to_global_totals`, `prisma.py::verify_invariants` (new per-branch checks) | **Gap found and closed this round:** `reports.counts()` had no branch dimension at all, even though every equation in this block is explicitly per-branch (`_b` suffix) and invariant 6 requires each report be attributable to exactly one branch at each stage. Added `reports.counts_by_branch()` and wired corresponding checks into `prisma.verify_invariants()`. |

## §6 Acceptance tests (fixture-level)

| # | Fixture | Test file :: test |
|---|---|---|
| 1 | Import retry idempotent; deliberate re-import creates new IDs; mixed-group correction | `test_db.py::test_operation_idempotency_ledger`, `test_import_csv.py::test_im18_retry_same_operation_is_idempotent`, `test_prisma_counts.py::test_deliberate_re_import_creates_new_batch_and_occurrence_ids` (**gap closed this round** — only the same-operation-id retry half was previously tested), `test_dedup.py::test_mixed_group_classification_vote_preserved` |
| 2 | Cross-branch report progression; advances once; replay/correction/undo restore counts | `test_reports.py::test_cross_branch_fixture_advances_once`; `test_prisma_counts.py::test_acceptance_2_progression_correction_switches_canonical_branch` + 3 edge-case tests (**closed last round**) |
| 3 | Retrieval tri-state (4 reports: pending/not-retrieved/included/excluded) | `test_reports.py::test_retrieval_fixture_four_reports` |
| 4 | Study/report fixture (3 reports, 2 studies, 4 links + 1 repeat) | `test_studies.py::test_acceptance_4_study_report_fixture` |
| 5 | Study conflict fixture | `test_studies.py::test_acceptance_5_study_conflict_fixture` |
| 6 | Source/branch fixture (full merge/correction/canonical-selection sequence) | `test_prisma_counts.py::test_acceptance_6_source_branch_fixture`, `test_acceptance_6_canonical_selection_branch_a`, `_branch_b` |
| 7 | Export authorization while blind | `test_export.py::test_blind_reviewer_export_excludes_others_votes`, `test_owner_export_while_blind_sees_everything`, `test_auditor_with_full_export_scope_sees_everything`, `test_unblinded_project_reviewer_sees_everything`, `test_post_revocation_export_denied_full_access`; `test_roles.py::test_owner_can_grant_and_revoke_auditor_scope`, `test_non_owner_cannot_self_grant`, `test_grant_requires_reason` |
| 8 | Watermark | `test_export.py::test_watermark_export_event_appears_in_later_audit`, `test_prior_export_files_unchanged_by_later_export` |
| 9 | Cold offline: invalid replay / unresolved conflicts / missing links / local-write failure | `test_export.py::test_write_package_to_folder_*` (3 tests, **closed last round**), `test_unresolved_screening_conflict_blocks_completeness` + `test_resolving_the_screening_conflict_clears_that_issue` (**closed last round**), `test_included_but_unpromoted_occurrence_blocks_completeness` (missing links). "Invalid replay" stays named-untested — same reason as invariant 8 above: no generic replayer exists to feed an invalid log into. SVG generation: `test_svg_has_accessible_title_and_description`. |

## Summary

Every equation and every acceptance fixture in the spec maps to at least
one real test, **except two items that are genuine feature gaps, not
test gaps**, named explicitly rather than silently passed:

1. `removed_automation` / `removed_other` sub-categories of
   `removed_before_screen` — not implemented in v1 (only
   duplicate-based pre-screen removal exists). The 3-term equation
   trivially holds in every test because the other two terms are
   always 0, not because they were independently exercised.
2. Invariant 8 (empty-log replay reconstructs full state) and fixture
   9's "invalid replay" clause — no generic event replayer exists in
   this codebase yet. The append-only event log and per-write
   `apply_fn` pattern give replay-like properties at write time, but
   there is no `replay_all(conn)`-style function that rebuilds
   projections from an empty database, so there is nothing to point a
   test at. Closing this requires building the replay feature first.

Four implementation or test-coverage gaps were found and closed during
the equation audit (not just missing tests — product code gaps were
present):
- `identified_other`/`identified_db_register`/`identified_total` had
  zero coverage.
- "Deliberate re-import creates new occurrence IDs" (the second half
  of acceptance fixture 1's first sentence) was untested.
- `reports.counts()` had no branch dimension at all, despite §3.4's
  equations being explicitly branch-scoped and invariant 6 requiring
  it. Added `reports.counts_by_branch()` and wired it into
  `prisma.verify_invariants()`.
- `maybe` decisions were counted as terminally screened. PRISMA now
  counts them in `screening_pending`, blocks
  completeness while screening is pending, and the source-branch fixture
  asserts the corrected reconciliation.

**Priority 2 is closed**, with the two named feature-gap exceptions
above carried forward explicitly (not silently dropped) — they are
scope decisions for a future round, not missed test coverage.

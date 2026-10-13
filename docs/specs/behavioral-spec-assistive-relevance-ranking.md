# Behavioral spec: assistive relevance ranking (clean-room artifact 04)

> **Status:** Future-scope specification, explicitly deferred from Screening Workbench v1 by owner ruling on 2026-10-07. It is not part of the v1 implementation contract; no ranking UI, model, dependency, or quality claim may ship in v1.

Derived from the product brief, the screening-workflow spec, and public research sources only. This is a behavioral specification, not an implementation, a promise of model quality, or a claim that ranking reduces screening workload. No incumbent application, website, UI, or source code was inspected.

## 1. Purpose and boundary

The ranking feature optionally reorders a reviewer's undecided records to bring records the model estimates as more relevant earlier in that reviewer's queue. It is a navigation aid for title/abstract screening, not a screening decision, substitute reviewer, eligibility classifier, or completeness guarantee. Active-learning literature describes iterative feedback in which a human labels records and a model reprioritizes the remaining collection; reported results vary by dataset and evaluation design.[1][2]

The existing screening workflow's decision set remains **include / maybe / exclude**, with an exclusion reason required for exclude. The ranking feature must not add a fourth decision state or change those semantics. Ranking is optional and starts disabled unless the reviewer explicitly enables it. [Derived from screening-workflow spec]

**Non-goals:** automatic include/exclude/maybe decisions; automatic removal, hiding, filtering, or suppression of records; a stopping rule, completion estimate, or recommendation to stop; recommendations to exclude, reject, discard, or deprioritize-as-ineligible; model explanations presented as evidence; cross-reviewer learning; cloud inference; and claims of recall, accuracy, completeness, or time saved absent the validation described below.

## 2. Normative requirements

“Must” denotes a testable product requirement. Requirements in this section define v1 behavior.

### 2.1 Enablement, ordering, and control

- **ARR-001 — Explicit opt-in.** Ranking is off by default for each reviewer profile, review, and screening stage. It becomes active only after that reviewer explicitly enables it. The setting is personal; one reviewer's toggle does not change another's.
- **ARR-002 — Advisory only.** A model score or rank must never create, edit, confirm, or imply a screening decision or exclusion reason. Only an explicit reviewer action can change a decision, using the existing workflow.
- **ARR-003 — No gatekeeping.** Every undecided record remains available through ordinary navigation and filters whether ranking is on, off, warming up, or unavailable. The system never stops, auto-advances past an unseen record because of its score, or suggests excluding/stopping on the basis of ranking.
- **ARR-004 — Stable off behavior.** With ranking disabled, screening uses the pre-existing non-model order and controls. No model fit, score, or ranking request is required to display or screen records.
- **ARR-005 — Ranked queue.** With ranking enabled and a usable model, order eligible undecided records by descending estimated relevance score. Preserve all records exactly once. Resolve equal scores by the pre-existing stable queue order, then stable record identifier, so refreshes do not arbitrarily reshuffle ties.
- **ARR-006 — Scope.** Ranking is scoped to the active review, current reviewer identity, and current stage. Only records eligible for that stage and undecided by the active reviewer are candidates. Do not expose another reviewer's decisions through queue membership, ranking, counts, scores, state, or errors.
- **ARR-007 — No eligible labels / model failure.** If the active reviewer has not supplied at least one usable include and one usable exclude label for this stage, or fitting/scoring fails, retain the complete non-ranked queue, keep all actions available, and show a neutral status such as “Ranking unavailable; continuing in standard order.” Do not synthesize seed labels or silently reuse another profile's model.
- **ARR-008 — Visible mode.** The reviewer can determine whether ranking is on, off, warming up, or unavailable. The state must not disclose other reviewers' labels or progress. No score, color, badge, or rank may be worded or styled as a decision or confidence that a record should be excluded.
- **ARR-009 — Reversibility.** The reviewer can turn ranking off at any time without changing decisions, deleting records, or losing queue access. Turning it off restores the standard order. Re-enabling may recompute ranking from the same eligible personal labels.
- **ARR-010 — Label-change response.** After the active reviewer changes a screening decision, update the eligible training set and refresh the ranking before the next ranked batch is presented, or explicitly mark the ranking as stale and provide an explicit refresh action. Do not apply another reviewer's newly recorded label to the active model.
- **ARR-011 — Blindness.** Ranking respects the screening workflow's blindness boundary. Before unblinding, the active reviewer's ranking inputs and outputs are derived solely from that reviewer's eligible labels. Ranking must not make another reviewer's decisions, disagreement, or decision timing inferable. Opening conflict resolution remains governed by the screening-workflow spec and requires blind mode off.
- **ARR-012 — Accessibility.** Toggle, state, and ranked/standard navigation are keyboard operable with visible focus and screen-reader-announced state changes, consistent with the screening workflow's accessibility requirements.

### 2.2 Locality, persistence, and provenance

- **ARR-013 — Local inference.** Feature extraction, fitting, scoring, and sorting execute on the local device. The ranking path makes no network request, including analytics, telemetry, crash reporting, update checks, hosted model calls, or third-party API calls.
- **ARR-014 — Cold-offline operation.** Ranking can be enabled, fitted, refreshed, disabled, and used when the device has no network connectivity. An explicit network-triggered import elsewhere in the application does not authorize network access from ranking.
- **ARR-015 — Reviewer isolation.** The training-label query is keyed by active reviewer identity as well as review and stage. No other reviewer's labels, decisions, resolutions, or aggregates may influence features derived from labels, fitting, tuning, score calibration, ranking, fallback, or model state. Identity changes invalidate the in-memory model and scores before showing ranked order for the newly active profile.
- **ARR-016 — No decision persistence.** Model scores, inferred labels, and model ranks are never stored in decision fields, audit decision events, exports represented as reviewer decisions, or reviewer-facing decision history. V1 should keep fitted model and per-record scores ephemeral in memory; they are discarded on disable, profile/review/stage change, and application exit. Recompute locally when re-enabled. Existing human decisions and the screening audit log remain authoritative and unchanged.
- **ARR-017 — No external retention.** Ranking must not upload or persist row-level text, reviewer labels, model artifacts, feature vectors, or scores outside local project storage. V1 must not create an independent persistent model cache. Any future change to persistence requires a separate reviewed spec and explicit disclosure.

## 3. Behavioral data and model sketch (proposal, not a measured design)

This section proposes a small, auditable local baseline; it does not assert superior quality or prescribe a library dependency. The active-learning cycle and text-feature/classifier decomposition are established research patterns; model performance depends on the collection and choices of feature extraction, classifier, and query strategy.[1][2][3]

1. **Candidate text:** for each record, form text from the canonical title and abstract for the current stage. Normalize missing values to empty text. Do not use another reviewer's decisions, decision reasons, reviewer identity, conflict status, or decision timestamps as features. Do not use excluded/full-text-only fields outside the active stage.
2. **Training rows:** use only the active reviewer's own finalized `include` and `exclude` decisions for the same review and stage. Exclude `maybe`, undecided, withdrawn, and conflict-resolved decisions not personally authored by the active reviewer. A `maybe` becomes eligible only if that reviewer later makes their own include/exclude decision under the existing workflow. Preserve the source human decision as a decision; this spec defines no copying or relabeling.
3. **Feature representation:** proposed baseline is local word unigram/bigram TF-IDF over candidate title + abstract. Fit the vocabulary and inverse-document-frequency statistics on the current review's text corpus, without labels, and keep them in memory. Empty or unusable text receives a deterministic lowest-priority tie-group position in the ranked queue but remains fully accessible; this rule must not be interpreted as exclusion.
4. **Classifier and score:** proposed initial experiment is regularized logistic regression using the active reviewer's eligible labels, producing a score in [0,1] for ordering only. No probability calibration or meaning as a calibrated probability is claimed. If only one label class exists, fitting is unsupported and ARR-007 applies. Candidate hyperparameters must be fixed before test evaluation; do not tune on held-out evaluation labels.
5. **Refresh and queue:** score only the active stage's undecided records; sort descending with ARR-005 tie rules. Refit or refresh after the active reviewer changes labels, subject to the performance target in Section 6. Do not reorder already decided records in a way that alters history. Standard ordering remains available at all times.
6. **Lifecycle:** keep features, coefficients, and scores in process memory only. Clear them on profile/review/stage change, opt-out, and process exit. Underlying canonical records and human decisions remain the sole persisted source of truth.
7. **Provenance for validation:** experimental runs may record aggregate metrics, model/configuration version, dataset identifier, split/seed, and evaluation date in a local validation report. Do not place corpus records, abstracts, labels, row-level scores, or decision derivatives in the repository. Use public benchmark data or synthetic fixtures; any local private corpus evaluation stays local and reports aggregate counts only.

## 4. Reviewer isolation and threat cases

The ranking capability is in a sensitive position because ordering can influence what a reviewer sees first. Isolation is a storage/query invariant, not merely a UI convention.

- Query training labels with all three keys: review, stage, reviewer. Reject a missing or ambiguous reviewer identity rather than broadening the query.
- Use a separate in-memory model instance per active reviewer/review/stage tuple. Never share fitted label-dependent state between identities, including through a global cache or singleton.
- On reviewer switch, clear scores before rendering the new profile's queue; do not briefly display the preceding reviewer's order.
- Do not serialize ranking scores into shared records, audit events, exports, aggregate badges, logs, crash payloads, or telemetry. Diagnostics must not include row-level text or label payloads.
- Blind mode must not permit a reviewer to infer another person's decisions by probing rank changes. Only that active reviewer's own newly recorded labels may change their order. Changes in shared records' metadata can affect text features only if that metadata is part of the canonical record itself and not derived from a concealed reviewer decision.
- If isolation cannot be established or a query fails, fail closed to standard ordering and leave all records accessible.

## 5. Acceptance tests (required before release)

Tests must use synthetic fixtures with multiple local reviewer profiles. Do not commit or transmit private corpus records or row-level derivatives.

- **AT-01 Default/off:** create a review with no ranking preference. Verify ranking is off, the existing order is unchanged, and no model is fitted. Toggle off after enabling and verify the standard order and all decisions are exactly unchanged.
- **AT-02 Toggle isolation:** enable ranking for reviewer A. Verify reviewer B's setting and queue do not change. Toggle A off and verify B is unaffected.
- **AT-03 Own-label influence:** create a fixture where A and B have different include/exclude labels for identical records. Compute A's ranking, change only B's labels, and verify A's model inputs, scores, and order are byte-for-byte/equivalently unchanged. Change A's own eligible label and verify a refresh occurs and is scoped to A.
- **AT-04 Cold start/failure:** with no labels, include-only labels, exclude-only labels, empty text, and injected fit/scoring failure, verify a complete standard-order queue, a neutral unavailable state where appropriate, no hidden records, and no fabricated decision.
- **AT-05 Label semantics:** verify maybe/undecided rows are not training labels; the active reviewer's later own finalized include/exclude is eligible; another reviewer's conflict resolution or label is never eligible for A.
- **AT-06 Completeness and order:** with ranking active, verify every eligible undecided record occurs once, no decided record is treated as undecided, descending scores sort correctly, and ties follow ARR-005 deterministic ordering. Verify a low-scored record remains reachable via standard navigation.
- **AT-07 Blindness:** while blind, vary another reviewer's decisions and timestamps. Verify A cannot observe those values and A's ranking and status do not change. Verify conflict access remains blocked under the existing spec until unblinded.
- **AT-08 Identity switch:** rank as A, switch to B, and verify no A-specific score/order is rendered or reused before B's state loads; switching back also cannot resurrect stale scores after invalidation.
- **AT-09 Persistence and audit:** inspect persisted project data, audit events, decision history, and decision export after enable/fit/refresh/disable/restart. Verify no score, inferred label, rank, or model artifact is stored as a decision or persisted in v1; human decision history remains unchanged.
- **AT-10 Network denial:** run enable, fit, refresh, profile switch, disable, and restart with outbound networking blocked at the OS/test harness. Verify all supported actions work locally and zero connection attempts are made. Static inspection of the ranking path must find no network client, telemetry event, hosted service, or remote model reference.
- **AT-11 Keyboard/accessibility:** operate the control and queue without a mouse; verify focus visibility and screen-reader announcement of on/off/unavailable status. Confirm rank styling does not communicate a decision.
- **AT-12 Data edge cases:** test duplicate/empty titles, missing abstracts, Unicode, long text, identical scores, and 10,000-record synthetic fixture; ensure stable complete ordering and no crash or record loss.

## 6. Performance and validation proposals (not established results)

### 6.1 Performance targets — proposed for product review

These are candidate acceptance targets, not measured performance claims. Benchmark on a documented mid-range laptop with a fixed synthetic/public fixture and disclose hardware, runtime, record/text-size distribution, and cold/warm timing. The screening-workflow spec has an interaction target under 100 ms at 10,000 records; ranking should not regress ordinary decisions or navigation against that budget.

- Proposed target: off-mode toggle and ordinary decision interaction add no measurable model work and remain within the existing <100 ms screening interaction target at 10,000 records.
- Proposed target: for 10,000 records with a documented representative title/abstract size, scoring and sorting a refreshed queue completes within 1 second at the 95th percentile after fitting; full local fit completes within 5 seconds at the 95th percentile. These targets require benchmarking and may be revised before implementation.
- Report p50/p95/p99 and peak memory for cold fit, incremental label refresh, full refresh, and queue sort, at 1k/10k/50k records. Defer model fitting off the synchronous keypress/decision path if it cannot meet the interaction budget. Never drop records to meet performance targets.

### 6.2 Quality/validity study — proposed gate before any quality claim

No quality or workload-reduction claim is approved by this specification. Active-learning simulation studies report substantial but dataset-dependent effects, and measures such as recall and work saved depend on cutoffs and assumptions.[2][3] The ranking-only feature must not use those findings as a guarantee for an individual review.

Before making any public or in-product quality claim, conduct and publish an appropriately reviewed, reproducible validation with:

1. **Pre-registration:** define scope, inclusion criteria, target populations, comparator (existing standard order/random order), model/configuration, stopping point for evaluation only, primary metrics, missing-data rules, and analysis before examining test results.
2. **Leakage-resistant data:** use fully labeled historical review collections with permission and documented provenance. Split by review/dataset, not random rows, to prevent near-duplicate or same-review leakage. Keep all fitting, vocabulary selection, and tuning inside each training fold. Test on held-out reviews and, where feasible, a later-time or external collection. Keep restricted records local; publish aggregate results only.
3. **Interactive simulation:** replay each reviewer's own prior decisions as labels and rank only remaining records at each step. Do not train on other reviewers' decisions. Evaluate ranking separately per reviewer and stage; do not treat simulated ranking as a prospective human study.
4. **Metrics:** report recall/Relevant Records Found at prespecified review fractions (e.g. 5%, 10%, 25%, 50%, 100%); area under the recall curve or average time-to-discovery; work saved over sampling only with its target recall and assumptions explicit; relevant-record rank distribution; and 100% manual-screening coverage as the comparison endpoint. Report denominators, class prevalence, uncertainty intervals across reviews, and per-review variation. Do not report accuracy alone on imbalanced data.
5. **Baselines and ablations:** compare standard order and repeated random order; include a non-personal/global-label ablation only in a quarantined offline study to verify it is not used in product. Assess cold-start/random fallback, sparse labels, one-class labels, no abstract/title-only records, language/content subgroups, and mislabeled/noisy prior decisions.
6. **Human factors and safety:** conduct a separately approved prospective usability study to test comprehension that ranking is advisory, confirmation that low-ranked records remain findable, reviewer behavior under misleading rankings, and whether the aid increases over-reliance or hidden-record assumptions. Obtain any required ethics review/consent. The model may not substitute for the study's human decisions.
7. **Decision gate:** a quality statement must name the validated model version, population, dataset counts, metric and cutoff, uncertainty, limitations, and date; approval is required from the product/research owner. If validation is absent, inconclusive, or not representative, make no quality claim and retain ranking as an optional ordering aid only.

## 7. Source list (public; accessed 2026-10-06)

Sources were located through public web search. Access date is the date this specification was drafted. Research results support the rationale for human-in-the-loop prioritization and evaluation design; they do not establish Screening Workbench's model, implementation, or performance.

1. ASReview LAB documentation, “Introduction” — describes interactive text screening in which a human supplies labels and an active-learning model selects/ranks records; explains prior knowledge terminology. https://asreview.readthedocs.io/en/latest/lab/about.html
2. Ferdinands et al., “Performance of active learning models for screening prioritization in systematic reviews: a simulation study into the Average Time to Discover relevant records,” *Systematic Reviews* (2023). Reports simulation methods, recall/WSS/average-time-to-discover measures, and dataset variability. https://pmc.ncbi.nlm.nih.gov/articles/PMC10280866/
3. van de Schoot et al., “An open source machine learning framework for efficient and transparent systematic reviews,” *Nature Machine Intelligence* (2021). Describes ASReview active-learning workflow, simulation, and the need for careful evaluation. https://www.nature.com/articles/s42256-020-00287-7
4. scikit-learn documentation, “Feature extraction” — reference for text feature representations and TF-IDF. This source informs only the proposed model sketch, not a selected dependency. https://scikit-learn.org/stable/modules/feature_extraction.html
5. NIST, “AI RMF Core” — voluntary risk-management guidance including documentation, human oversight, validation, measurement, and privacy considerations. Used as general evaluation-design guidance, not a compliance claim. https://airc.nist.gov/airmf-resources/airmf/5-sec-core/
6. Wallace et al., “SWIFT-Active Screener: Accelerated document screening through active learning and integrated recall estimation,” *Systematic Reviews* (2021). Describes active prioritization and discusses limits of workload/recall estimation. https://pmc.ncbi.nlm.nih.gov/articles/PMC8082972/
7. Shemilt et al., “Machine learning reduced workload with minimal risk of missing studies: development and evaluation of a randomized controlled trial classifier for Cochrane Reviews,” *Research Synthesis Methods* (2020). Illustrates use-specific recall thresholds, calibration, and validation; its classifier's results must not be generalized to Screening Workbench. https://pmc.ncbi.nlm.nih.gov/articles/PMC8168828/

## 8. Decisions and open proposals

- V1 behavior is specified as optional, local, reviewer-isolated ordering assistance only.
- The TF-IDF + regularized logistic-regression sketch, timing thresholds, and validation protocol are proposals pending implementation planning and product/research approval. They are not claims of validated performance or committed dependency choices.
- No decision is made here to persist a model, retain scores, support cross-reviewer training, automatically stop screening, or exclude records. Any such scope change requires a new reviewed behavioral spec.

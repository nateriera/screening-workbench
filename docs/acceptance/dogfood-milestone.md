# Dogfood milestone: acceptance criteria

Private reference data may include screening labels without verified report retrieval, full-text, or study/link outcomes. Keep any real-data reconciliation local and limited to owner-confirmed fields. Validate complete report/study PRISMA behavior with synthetic fixtures whose expected outcomes, decisions, links, and derived counts are specified in acceptance tests; do not manufacture reference values.


The v1 build is accepted when it carries a review end-to-end and reconciles against owner-verified reference labels. Corpus identity, source format details, row counts, and label totals are private and are not reproduced in this repository.

- Private dogfood data does not provide verified downstream full-text or study outcomes. Real-data acceptance therefore covers only owner-confirmed labels; do not fabricate downstream labels.
- Full report/study PRISMA flow is verified separately with deterministic synthetic fixtures, including explicit study decisions and expected totals. A real-corpus export may only be called complete if all included reports have owner-confirmed study associations and study-inclusion decisions; otherwise label it incomplete and state why.




## Runbooks

- **Private labeled-data run:** import, deduplicate, blind screen, unblind/resolve, and reconcile source-occurrence labels locally. Do not invent report retrieval/full-text decisions, study identities/inclusion, or report-study links. A PRISMA snapshot must be `incomplete` wherever verified inputs are absent.
- **Synthetic complete PRISMA run:** use deterministic fixtures specifying source classes, decisions, retrieval/full-text outcomes, study decisions and report-study associations; assert exact expected study/report counts and complete package outputs.


## Pass criteria
1. **Blind-integrity probe:** While blind, reviewer B cannot retrieve/infer reviewer A’s decisions through application-controlled views, queries, search, exports, diagnostics, or logs; ranking is deferred from v1. Owner/auditor full-export access follows the authorization matrix in the PRISMA spec.
2. **Labeled-data run:** source-occurrence labels reconcile against the private owner-approved reference. Use `data-readiness.md`; stop on mixed-label groups. Preserve provenance; distinguish pre-screen removal from post-screen correction. Keep private counts and records outside Git.
3. **Synthetic PRISMA run:** occurrence, report progression, retrieval/full-text, exclusion-reason, study decision/link, distinct-count, replay, and snapshot invariants pass.
4. **Package contract:** Complete synthetic export contains SVG only, decisions CSV, normalized study/report CSV, audit JSONL, and manifest from one watermark; replay/current totals agree. PNG is out of v1. Corpus export with unverified flow annotations is incomplete.
5. **Cold offline run:** labeled and synthetic checks pass without networking. No corpus rows, abstracts, or generated records enter Git or external services.






## Data handling
Private research data and derived records stay in the local project database and local test outputs. Never add source rows, abstracts, private counts, or exports to Git or send them to agents, online services, or external systems. Document the test procedure without exposing dataset identity or contents.

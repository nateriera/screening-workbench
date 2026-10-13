# Dogfood data handling and readiness note

## Local reference data

The private reference dataset and its derived row-level labels are excluded from this repository. Its location, identity, source details, and observed values are intentionally omitted. Use synthetic fixtures for reproducible public acceptance tests.

## Reconciliation rules

- Compare each source occurrence against the owner-confirmed reference label without substituting a separate activity/status field.
- For an exact duplicate group with a consistent reference label, preserve source-occurrence accounting while reconciling the canonical screening target.
- If a confirmed duplicate group has conflicting reference labels, stop reconciliation for that group and report the conflict for owner review. Never choose or average a label silently.
- Preserve provenance and distinguish pre-screen removals from post-screen corrections. Previously recorded votes and audit history remain intact.
- Validate report retrieval, full-text outcomes, study decisions, and report/study links with deterministic synthetic fixtures when those inputs are not present in the private reference data.

## To complete before dogfood

1. Run the approved end-to-end workflow locally; keep databases and exports outside Git.
2. Inspect reviewer isolation at the application access boundary and retain redacted test evidence.
3. Record import, skipped, deduplication, reconciliation, PRISMA, replay, and network-disabled results without exposing source records or private dataset details.

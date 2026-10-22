# Changelog — Screening Workbench

Notable changes, newest first. The project was developed privately as "Cull"
and renamed to Screening Workbench in October 2026, before its first public
release.

## [Unreleased]

### In progress
- Preparing a macOS ARM64 packaging candidate under the expected version label
  1.1.0. The candidate workflow is integrated on `platform/macos-package`;
  workflow artifacts and validation evidence remain run-specific. This is not a
  published release.

## [1.0.0] — 2026-10-21

First public release (Windows 11 x64 package on the releases page).

### Added
- Full screening pipeline in the free core: keyboard-first title/abstract
  queue (I/M/E/J/K), Maybe re-review, fuzzy duplicate detection with a
  manual-review queue, conflict resolution, full-text assessment, study/report
  linking, and PRISMA 2020 flow-diagram plus audit-trail export. No accounts,
  no telemetry; everything stays in a local SQLite project file.
- Blind-review integrity: blind mode locks on the first vote; blinded
  reviewers see only their own votes; blind exports omit project-wide counts,
  audit data, report links, PRISMA output, and attachments.
- Two-computer blind collaboration: reviewer packet export/import, vote file
  merge (newest-wins), reviewer-identity locking.
- Importers for CSV, RIS, and PubMed XML with field mapping, resource caps
  (file/record/field/nesting limits), and XXE-hardened XML parsing.
- Duplicate detection with a fail-closed pair-comparison budget.
- CSV formula neutralization on exports; strict schema validation for packet
  and vote JSON, with malformed-row quarantine.
- Field Notes design system across all seven tabs (SQLite + Tkinter, standard
  library only, no network calls).
- SECURITY.md documenting the trust model and accepted limitations.

### Fixed
- Pre-release security review (7 findings): unbounded RIS/CSV parsing, blind
  PRISMA aggregate exposure, unsigned-handoff documentation, and related
  hardening. Details in SECURITY.md.

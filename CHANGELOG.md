# Changelog — Screening Workbench

Notable changes, newest first. The project was developed privately as "Cull"
and renamed to Screening Workbench in October 2026, before its first public
release.

## [Unreleased]

## [2.0.0] — 2026-10-22

### Added
- Card Catalogue visual direction 02: drawer chrome, card-stock surfaces,
  highlighter accent for "now" / "needs you", and a redesigned Screening
  record card with a call-number progress strip.
- Bundled typefaces — Newsreader, Atkinson Hyperlegible Next and Mono
  (SIL OFL 1.1) — loaded privately by the app; nothing is installed
  system-wide. License audit, SBOM, and notices cover the fonts.
- Night Stacks dark palette with View → Theme (Light / Night / follow
  Windows), saved between launches.
- Decision stamp animation on Screening decisions, with View → Reduce
  motion (also honours the Windows animation setting and
  `SW_REDUCE_MOTION`).
- Keycap decision buttons on Maybe re-review and Full-text, matching
  Screening; Exclude visibly arms the reason list while the picker is open.
- PRISMA flow diagram graph-paper backdrop (hidden in high contrast).

### Changed
- R6 polish: card surfaces, PRISMA flow rebuilt on a measured lattice,
  shell chrome, and a wrapping Duplicates field comparison.

### Fixed
- Recent decisions now break tied timestamps by insertion order, matching
  undo (was: lexical vote-ID order).
- A chosen full-text exclusion reason is no longer cleared when the same
  report re-renders.
- Duplicates provenance prints the import locator once (e.g. "row 2").
- Tk variables carry explicit masters (Aqua Tk correctness; no Windows
  behaviour change).

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

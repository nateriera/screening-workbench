# Behavioral spec: screening workflow (clean-room artifact 01)

Derived from public sources only — see Source list. Describes behavior, never copies
incumbent UI, code, or assets.

## 1. Project setup
- A project holds one review. Setup steps, in order: (a) name the review; (b) load the
criteria document (PDF/text) which the tool parses into a structured exclusion-reason
taxonomy the owner can edit; (c) invite reviewers (v1: reviewer identities are local
profiles, no accounts); (d) choose blinded or open screening before anyone starts —
the blind toggle locks once screening begins and only the project owner can change it.
- Rationale (public): Rayyan's own help docs prescribe defining criteria first, enabling
blind mode before the team begins (owner-only toggle), and agreeing exclusion reasons
in advance for an accurate PRISMA flow.

## 2. Import
- Accepted v1 formats: RIS, CSV, PubMed XML. BibTeX was listed in an earlier artifact but is excluded from v1 per the product brief; see `behavioral-spec-import-field-mapping.md` for the scope note. On import the tool shows source-to-canonical field mapping, counts records read and skipped with reasons, and lists unmapped fields.
- Canonical record fields: title, authors, journal/source, year, volume, issue, pages,
DOI, PMID, abstract, keywords, language, URL, import batch, raw source line (for audit).
- Re-imports append as new batches; batch identity is preserved for the PRISMA
"records identified" counts.

## 3. Deduplication
- Automatic pass on import: exact-match groups (normalized title + year, DOI match) are detected and logged. Unscreened absorbed occurrences may merge silently; if any absorbed occurrence has a screening vote, retain its vote/history, classify it as a post-screen correction, and require adjudication before report progression. Fuzzy-match groups (near-identical titles, same first author + year) go to a manual resolution queue; they do not merge until a reviewer confirms. See `behavioral-spec-duplicate-detection.md` and the PRISMA spec for row-level count rules.
- Resolution actions per group: merge (pick surviving record, others marked duplicates),
keep separate. Every merge is reversible and logged with timestamp and actor.
- Pre-screen unscreened absorbed occurrences feed PRISMA records removed before screening. Already-screened absorbed occurrences remain in historical screened totals and appear separately as post-screen corrections; see the duplicate and PRISMA specs.

## 4. Title/abstract screening
- Decision set per record per reviewer: **include / maybe / exclude**.
- Each reviewer-authored title/abstract **exclude** decision requires exactly one reason from the project taxonomy (agreed in setup). This is an internal screening/audit requirement; it does not make title/abstract reasons full-text PRISMA exclusion reasons. Preserve reviewer-specific reasons in decision history.
- Blind mode is **application-level isolation**: while on, a reviewer can retrieve only their own decisions and decision-derived data through the UI, searches/filters, reviewer-specific derived data, exports, diagnostics, and app logs. Aggregate counts may show only safe totals/undecided status and must not reveal another reviewer's calls or allow them to be inferred. The shared local project store may retain all decisions for audit replay and later unblinding; no promise is made that another reviewer's raw bytes are physically absent from the database. The project owner is fixed at creation. Only the owner may grant/revoke a local `auditor` role, choosing `audit_read` and/or `full_export` scope; each change requires confirmation and appends actor, target, scope, timestamp, reason to audit history. Reviewers cannot grant themselves roles. Revocation denies subsequent requests/exports immediately; prior authorized exports remain immutable and audited. While blind, reviewer APIs/views expose only own decisions and safe aggregates; owner/current auditor access follows assigned scope. Turning blind off reveals per-reviewer decisions and populates the conflict queue.
- Ergonomics (behavioral requirement): single-keystroke decisions (one key each for
include / maybe / exclude), no mouse required; auto-advance to next undecided record;
an "undecided only" filter is the default screening view with a live remaining counter;
bulk select + bulk decide for obvious batches; text search and facet filters (year,
journal, import batch, decision state).
- "Maybe" is a first-class state: maybes get a dedicated re-review queue, and a maybe
that survives to conflict resolution must be converted to include or exclude.
- Assistive relevance ranking is deferred from v1. No model, score, or ranking output is included; any later ranking requires separate scope, validation, and license decisions.

## 5. Conflict resolution
- A conflict = the two reviewers' final decisions disagree (include vs exclude; maybe
counts as disagreeing with anything). Opening the conflict queue requires blind mode off.
- Each conflict shows: the record, both reviewers' decisions with timestamps, their
exclusion reasons, and a resolution control: final decision (include/exclude) +
required resolution note. Optionally a third reviewer profile casts the tiebreak.
- Resolved conflicts are immutable except by the owner, and every resolution is logged.

## 6. Full-text stage (the incumbent gap)
- Documented incumbent behavior: Rayyan cannot move through screening phases in a single
review — included records must be exported and re-imported into a new review for
full-text screening (Northwestern library guide).
- Our behavior: one project, two stages. Records included at title/abstract flow into a
full-text queue in the same project. Full-text screening repeats the same decide/resolve
mechanics; each full-text **report** excluded at this stage requires exactly one primary
reason for PRISMA. The reason taxonomy for title/abstract reviewer votes is separate from
full-text report-exclusion reasons. PDF attachment per report is supported locally.

## 7. PRISMA 2020 export
- PRISMA 2020 source-level and report-level counts are derived from immutable event history; study inclusion is an explicit audited decision, and studies/reports are distinct linked entities.
  The project PRISMA specification defines the exact equations, incomplete-export policy, study decision semantics, and normalized link export.


- Exports: PRISMA diagram as original SVG (PNG deferred from v1), occurrence-level decisions CSV plus normalized study/report-link CSV, full audit log, and manifest from one snapshot. While blind, reviewers may export only their own decisions; the project owner or explicitly authorized auditor can export the complete package. Export-event watermark semantics are defined in the PRISMA specification.


## 8. Non-functional requirements
- Local-first: all data in a local database file; works fully offline; no accounts, no
telemetry, no network calls except explicit user-triggered imports.
- Performance: screening interactions stay under 100ms at 10k records; import + auto-dedup
of a 2k-record RIS file completes in under 60 seconds on a mid-range laptop.
- Accessibility: full keyboard operation; visible focus states; decisions announced to
screen readers.

## Source list (public)
- Rayyan help center, "How to Screen References in Rayyan" (help.rayyan.ai) — recommended
screening workflow: criteria first, blind mode before team begins, agreed exclusion
reasons, undecided filter, resolve conflicts before advancing.
- Northwestern GalterGuides, "Full-Text Screen: Specific Considerations - Rayyan" —
documents the export/reimport phase gap.
- PRISMA 2020 statement (published standard) — flow diagram stages.
- ASReview GitHub repo (public) — background reading only; no dependency selected.
- Paperguide.ai systematic-review software comparison (Oct 2026) — feature/pricing table.

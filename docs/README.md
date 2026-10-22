# Documentation

Start with the repository [`README.md`](../README.md) for installation
and the quickstart. This index covers the rest.

## Using and understanding the app

- [`docs/packets.md`](packets.md) — the reviewer packet and votes file
  formats used for two-computer blind review, including the versioned
  format identifiers and merge rules.
- [`docs/ui-references/`](ui-references/) — per-tab screen references
  and live captures.
- [`docs/design-system.md`](design-system.md) — the Field Notes visual
  system and its accessibility gates.

## Behavior specifications (clean room)

The app is implemented from public-source behavioral specifications:

- [`docs/specs/`](specs/) — screening workflow, import field mapping,
  duplicate detection, PRISMA counts and export; plus a deferred
  future-scope spec for assistive relevance ranking (not in v1).
- [`docs/acceptance/`](acceptance/) — acceptance procedures and the
  dogfood milestone definition. Public evidence uses synthetic
  fixtures; reference-corpus data is never committed.
- [`docs/decisions.md`](decisions.md) — the project's decision record.

## Building and packaging

- [`docs/packaging.md`](packaging.md) — the verified, reproducible
  Windows build procedure (PyInstaller onedir), including the Tcl/Tk
  workaround for CPython 3.14.7.

## Licensing and release records

- [`docs/license-audit.md`](license-audit.md) — dependency licensing
  review and verdict.
- [`docs/license-review.md`](license-review.md) — release-artifact
  licensing review for the shipped package.
- [`docs/sbom.cdx.json`](sbom.cdx.json) — CycloneDX SBOM for the
  release package.
- [`docs/notices/`](notices/) — third-party license texts bundled in
  the package.
- [`docs/release-gate-1.0.0.md`](release-gate-1.0.0.md) — the v1.0.0
  release gate record: artifact identity, provenance review,
  entitlement attestation, and publication.

Working papers from the October 2026 implementation (the product brief,
process notes, and the UI convergence log) are kept in the project's
private build repository; the specifications and records above are the
public trail.

---

## Archive — historical inventory (October 2026)

The inventory below is preserved as recorded during the October 2026
implementation. It is not a live status report; file references to the
working papers named above resolve in the private build repository.

## Available at kickoff

- `docs/briefs/product-brief.md` — supplied product brief.
- `docs/specs/behavioral-spec-screening-workflow.md` — supplied clean-room artifact 01.
- `docs/acceptance/dogfood-milestone.md` — acceptance procedure and target totals.
- Historical prompt inputs referenced during kickoff: the orchestrator and three agent prompts. Their working copies were removed from this public repository; canonical copies remain private.
- `docs/design-system.md` — original owner-authorized Screening Workbench visual system.
- `docs/specs/behavioral-spec-assistive-relevance-ranking.md` — retained as future-scope specification only; ranking/model behavior is deferred from v1 and must not ship.

## Current project status

**Current as of 2026-10-12.** v1.0.0 shipped (Windows 11 x64 packaged build). Directives C/D and the v2 UI convergence merged to `main` (`ef821c62`); Directive F — full visual parity — completed all four phases and merged to `main` (`f605b60`): all seven tabs re-verified in the new Field Notes-themed card shell (theme module `src/screening_workbench/theme.py`), final convergence 171/174 across the seven reference checklists, full suite 362 passed. The visual authority is `docs/design-system.md` (Field Notes — owner carve-out Oct 9 2026; never an unrelated project’s brand tokens). Per-tab UI evidence lives under `docs/ui-references/`; the review record is `docs/ui-convergence-log.md`.

Earlier stack/toolchain rulings still stand: Python + Tkinter + SQLite, stdlib-only (no third-party Python dependencies), CSV/RIS/PubMed XML import, SVG-only PRISMA, ranking deferral, Windows 11 x64, PyInstaller onedir packaging. See `docs/license-audit.md` for the full licensing evidence trail and verdict. Final release SBOM/attribution notices and any future third-party dependency still require separate review; no publish/deploy without further authorization.

## Implementation status (2026-10-07)

V1 was integrated onto `main` by creating `main` at the `implementation/v1` head, commit `fe0ce85`; because the target was created from the source head, there is no separate merge commit. The working follow-up branch is `implementation/v2`. The Python package is `src/screening_workbench/`; after the name/package migration, the full test suite passed 204/204. The owner-side GitHub rename is complete; local `origin` points to `https://github.com/nateriera/screening-workbench.git` (fetch verified 2026-10-07). Directive A (inter-rater κ) and Directive B (reviewer packets) have since landed on `implementation/v2`; full suite is now 227/227.

Implemented and tested: event-sourced SQLite core with replay-safe projections (`db.py`); CSV/RIS/PubMed XML import with field mapping, normalization, and XXE/entity-bomb-hardened XML parsing (`importers/`); exact + fuzzy deduplication with row-level pre/post-screen classification (`dedup.py`); screening votes, blind-mode isolation, conflict detection/resolution, and inter-rater Cohen's κ (`screening.py` — Directive A); report progression, retrieval, and full-text assessment (`reports.py`); study entities, decisions, and report-study linking/conflict detection (`studies.py`); PRISMA 2020 identification/screening count derivation with invariant checking (`prisma.py`); owner/auditor role grants and blind-mode settings (`roles.py`); two-computer blind-review reviewer packets — packet export/import, votes export/merge, reviewer-identity locking, newest-wins merge, vote quarantine (`packets.py` — Directive B, see `docs/packets.md`); the full local export package -- SVG flow diagram, decisions CSV, report-study-links CSV, audit-log JSONL, manifest.json, with blind-export authorization (`export.py`); and a functional Tkinter shell with CSV, RIS, and PubMed XML imports plus keyboard-first (i/m/e) screening wired in `app.py`.

Tests map directly to the PRISMA spec's 9 acceptance-test fixtures (`tests/test_prisma_counts.py`, `test_reports.py`, `test_studies.py`, `test_export.py`) and many of the import-field-mapping spec's IM-* fixtures (`tests/test_import_csv.py`, `test_import_ris.py`, `test_import_pubmed_xml.py`).

**Historical implementation notes (snapshot dated 2026-10-07):** Known feature gaps at that checkpoint included multi-column author/keyword combination, RIS TI/T1 and PY/Y1 conflict flagging, PubMed XML partial salvage and ArticleIdList cross-checks, full-text re-assessment, and broader accessibility/performance verification. Later packet wiring and UI convergence are recorded in `docs/decisions.md` and `docs/ui-convergence-log.md`; do not treat the old test counts or queued-work notes in this page as current status.

### Phase 2 importer triage (2026-10-08)

- **Fixed — CSV delimiter selection and explicit encoding fallback:** the CSV UI offers comma/tab/semicolon/pipe, defaults decoding to strict UTF-8, and asks for cp1252 or latin-1 only when UTF-8 decoding fails; explicit choices avoid silent dialect or replacement-character guesses.
- **Fixed — headerless CSV positional mapping:** users explicitly identify whether the first row is a header and map each data column to a canonical field or leave it blank; no field meaning is inferred from sample values.
- **Documented — RIS TI/T1 and PY/Y1 conflict flagging:** left unresolved because silently selecting a competing tag violates the spec's no-first-wins rule; safe resolution needs a per-record conflict-choice workflow, not just importer wiring.
- **Documented — PubMed XML partial salvage and ArticleIdList cross-checks:** retained conservative whole-document rejection and current ELocationID/PMID mapping because malformed XML may not have safe record boundaries and cross-source identifier conflicts need explicit mapping resolution.
- **Documented — multi-column author/keyword combination:** left out because current canonical storage and commit mapping support one input column per canonical field; combining columns would change importer mapping semantics beyond this triage.

## Dogfood corpus boundary

Private reference data, corpus identity, and all derived counts remain local-only and are intentionally omitted from this repository. Public acceptance evidence uses synthetic fixtures; local dogfood evidence must be redacted before sharing. Never send source records, abstracts, or row-level decisions to agents, online services, or external systems.

5. **Original visual direction:** Use `docs/design-system.md`, the owner-authorized original Screening Workbench first-pass system. It is not an external brand design system. Preserve independent visual identity/accessibility; this prerequisite is satisfied.

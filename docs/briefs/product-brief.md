# Product brief: free systematic-review screening workbench

Product name: **Screening Workbench** (owner ruling 2026-10-07; prior working name is recorded in `docs/decisions.md`). One-page brief, originally drafted Oct 6 2026.

## The user
The individual researcher who can't expense the incumbent: grad students, solo researchers, small labs, unaffiliated reviewers. Same underserved-user pattern as the dashboard-builder. An initial private screening workflow informed the import, criteria-document, and blind-review requirements; the researcher's identity and corpus details are intentionally omitted.

## Market context

This is a product hypothesis, not a current competitor comparison. Pricing,
feature limits, and service terms change and have not been verified for
publication. Screening Workbench's product direction is to make local, small-team screening
and review bookkeeping available without per-reviewer application limits.
No claim about a competitor's pricing, feature set, terms, or legal restrictions
is made here.

## The undercut
Screening Workbench's intended value:
1. **No per-review or per-reviewer limit in the current app.**
2. **Local-first.** Core workflows operate on local project data. Data leaves
   the machine only when the user exports a packet or other project artifact;
   those files need to be handled as sensitive data.
- **Full pipeline direction.** Screening Workbench aims to grow from screening into fuller review workflows over time. V1 includes import, deduplication, criteria/reason setup, blind screening, conflict resolution, full-text decisions, PDF attachment, explicit study/report association, audit, and PRISMA export. Data-extraction forms and risk-of-bias assessment remain future scope. This is product direction only; current acceptance requires the separate labeled-corpus and synthetic complete-PRISMA runs in `docs/acceptance/dogfood-milestone.md`.



Supporting wedge: blind-review integrity as a first-class feature (dual-reviewer blinding, conflict resolution queue, full audit trail).

## Clean-room competitive protocol
Learn everything, steal nothing. This is the standing rule for this project:
1. **Sources are public only.** Marketing pages, pricing pages, public help docs, published papers (e.g., Ouzzani et al. 2016 on Rayyan), conference demos, app-store screenshots, the PRISMA 2020 statement (a published standard). Never create trial or paid accounts for teardown; never touch their code, copy, UI text, or assets.
2. **Behavioral specs, not screenshots.** The spec writer documents *what the workflow does*: import → dedupe → screen → resolve → PRISMA; the data model; screening ergonomics (keyboard-first, bulk actions); export formats. No verbatim copy, no captured UI in the spec.
3. **Visual direction:** Follow `docs/design-system.md`, the owner-authorized original Screening Workbench first-pass system, rather than the unavailable Klaro design system. Preserve distinct identity and accessibility gates.
4. **OSS integration with a license audit.** No third-party runtime packages currently selected. Keep the app runtime standard-library-only; any future dependency requires exact version/tree and license audit before integration. No GPL-family code in the shipped bundle without a further explicit owner ruling.
5. **Paper trail.** Keep the spec docs and source list so the lineage is defensible.

## Stack and dependency decision (owner-approved)

- Desktop: Python + Tkinter + SQLite; core workflows local/offline.
- Import: Python standard-library CSV/XML support plus original narrow RIS parsing; no third-party parser unless separately approved and audited.
- PRISMA export: SVG only in v1; PNG is deferred because the stdlib-only runtime has no PNG renderer, and no rendering dependency is approved.
- Assistive relevance ranking is deferred from v1. ASReview/scikit-learn and model-performance claims are future, separately reviewed scope.
- Owner selected Windows 11 x64, CPython 3.14.7 from python.org, and PyInstaller 6.21.0 onedir packaging. Python stdlib remains the only selected application runtime. The installer/hash smoke review is historical evidence, not an audit of the current Screening Workbench package; verify the exact application build, collected runtime components, final SBOM, and attribution before distributing a binary. No installer is planned for the initial build.

## Scope: v1
1. Import: RIS, CSV, PubMed XML (Zotero-friendly CSV dialect).
2. Dedup: automatic exact matching plus reviewed fuzzy candidates.
3. Criteria document to structured exclusion-reason taxonomy.
4. Blind dual-reviewer screening, adjudicated conflicts, full-text report decisions, and explicit study/report linking.
5. Progress dashboard, replayable audit trail, and validated PRISMA 2020 flow export (**SVG only; PNG deferred**) including distinct study and report counts.
6. Decisions CSV plus normalized study/report-link CSV, audit log, and manifest from one snapshot.
7. Optional assistive relevance ranking is deferred from v1; see stack/dependency decision. No ASReview, scikit-learn, or ranking-quality claim in this release.


## Product positioning (future direction)

Screening Workbench aims to grow from screening toward broader review workflows. This is roadmap positioning, not a claim that v1 includes data-extraction forms or risk-of-bias assessment.


## First milestone / acceptance basis

V1 must pass two linked acceptance tracks: (a) locally reconcile an owner-approved private screening workflow; (b) independently pass synthetic full-text, explicit study/report linking, and complete PRISMA export fixtures. Private inputs do not supply verified downstream study/retrieval values, so never invent them. If the app cannot handle the next real screening workflow and the synthetic complete PRISMA flow, it is not ready.



## Risks (honest)
- Current vendor prices, product limits, and contract terms are not verified in this brief and should not be used for launch claims.
- Screening speed UX is a product goal: keyboard-first include/maybe/exclude and clear workflow progress.
- Assistive ranking remains future scope and requires separately approved validation and licensing before consideration.

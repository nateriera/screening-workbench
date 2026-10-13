# Build coordination and operating rules

This document records project-specific constraints for contributors. Product behavior is defined by approved behavioral specs under `docs/specs/`, not by inspection of incumbent apps.

## Authority and clean-room rules
- Use the supplied product brief, approved behavioral specs, and acceptance criteria as source of truth.
- Do not access incumbent apps or create accounts to learn behavior. Public sources listed in specs are permitted; describe behavior abstractly and preserve source URLs/dates.
- Keep implementations, UI copy, artwork, and assets original. Apply the Field Notes design system per `docs/design-system.md` (the owner-authorized visual system for Screening Workbench; Oct 9 2026 carve-out: Screening Workbench uses Field Notes, never the Klaro brand tokens). Do not invent a substitute brand system; record the blocker.
- Do not integrate a third-party dependency before its exact release/commit, actual license, and relevant transitive licenses are recorded in `docs/license-audit.md`.

## Data and external-state safety
- All screening data stays in local project files. Never add the Julia corpus, abstracts, PDFs, screening decisions, or row-level derivatives to this repository.
- Do not send local research data to subagents, web services, Slack, GitHub issues, or other external systems.
- Use synthetic fixtures for committed tests. For dogfood, load the reference corpus from its existing local location, record aggregate counts only, and keep generated databases/exports outside Git.
- Networking is disabled for cold-offline verification. Only explicitly user-triggered import flows may use network access.
- No publication, merge, release, repository visibility change, or other external side effect without Nate's explicit direction.

## Build gates
1. Complete and review all behavioral specs and license audit before integrating dependencies or implementation.
2. Keep deviations explicit, with a rationale and owner ruling when scope/data model changes.
3. Test local persistence, immutable audit sequencing, blindness as a storage-level information boundary, import mapping, dedup reversibility, conflict resolution, PRISMA invariants, keyboard use, and offline behavior.
4. Run the full dogfood milestone and preserve a redacted evidence log with totals only.

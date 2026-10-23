# Contributing to Screening Workbench

Thanks for your interest. Screening Workbench is a clean-room,
local-first desktop app (Python + Tkinter + SQLite, standard library
only). Contributions are welcome under the constraints below — they are
the project's identity, not red tape.

## Development setup

Windows 11 x64 is the release target; development on other platforms
works for most of the suite (a few GUI tests assert display geometry
calibrated to the reference machine and are deselected in CI).

```powershell
git clone https://github.com/nateriera/screening-workbench.git
cd screening-workbench
# Python 3.12+ (developed on CPython 3.14) with Tkinter — both ship in
# the standard python.org Windows installer. No third-party runtime
# dependencies.
$env:PYTHONPATH = "src"
python -m screening_workbench.app   # run the app
python -m pytest tests/ -q          # run the test suite (pytest is the only dev dependency)
```

## Ground rules

- **Clean room.** Behavior is defined by the behavioral specifications
  in `docs/specs/`, written from public sources only. Do not access
  incumbent screening applications (accounts, trials, or inspection) to
  learn behavior, and do not copy proprietary UI text, labels, layouts,
  or assets. New behavior starts as a spec change.
- **No third-party runtime dependencies** without a license audit entry
  in `docs/license-audit.md` (exact release, actual license, transitive
  licenses) and maintainer approval. GPL/AGPL dependencies are not used.
- **Local-first is a boundary.** No accounts, telemetry, cloud sync, or
  network calls in core workflows. Never commit real screening data —
  records, abstracts, PDFs, project databases, or reviewer packets.
  Tests use synthetic fixtures only.
- **Blind-review integrity is a correctness boundary**, as are audit
  sequencing and PRISMA count reconciliation. Changes touching them
  need tests demonstrating the boundary holds.
- **Design.** UI work follows the Card Catalogue visual direction (direction 02) in
  `docs/design-system.md`, including its accessibility gates.

## Pull requests

- Test-first for behavior changes; the full suite must pass.
- Keep deviations from the specs explicit in the PR description, with a
  rationale.
- Scope, licensing exceptions, and releases are maintainer decisions.

## Reporting bugs

Open an issue with the app version (or commit), your Windows version,
and minimal synthetic steps to reproduce. Do not attach real project
databases, packets, vote files, or PDFs. For security reports, see
`SECURITY.md`.

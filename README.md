# Screening Workbench

**Free, local-first systematic-review screening.**

[![CI](https://github.com/nateriera/screening-workbench/actions/workflows/ci.yml/badge.svg)](https://github.com/nateriera/screening-workbench/actions/workflows/ci.yml) [![Latest release](https://img.shields.io/github/v/release/nateriera/screening-workbench)](https://github.com/nateriera/screening-workbench/releases/latest)

Screening Workbench is a free, local-first workbench for systematic-review title/abstract and full-text screening. It has no account, cloud sync, or telemetry. Records stay in the local project unless you explicitly export them; reviewer packets contain record data and must be handled as sensitive files.

## Who it's for

The individual researcher, grad student, or small lab. Screening Workbench runs on your own computer against a local SQLite project file and attachment folder: import references, screen them blinded or unblinded with a second reviewer, resolve conflicts, and export an auditable PRISMA package. The current application has no per-seat or per-review limit.

## Screenshots

**Screening queue** — keyboard-first include/maybe/exclude (`I` / `M` / `E`), search and year/journal/batch filters, a live recent-decisions panel:

![Screening queue](docs/ui-references/live-captures/screening-workbench-screening.png)

**PRISMA 2020 flow diagram** — generated from one immutable watermarked snapshot, rendered live in-app and in the exported SVG from the same shared data:

![PRISMA flow diagram](docs/ui-references/live-captures/screening-workbench-prisma.png)

More screens (Duplicates, Conflicts, Full-text, Studies, Maybe re-review) are captured throughout `docs/ui-references/`.

## Install

Windows 11 x64.

**Download the latest release:** [v1.0.0](https://github.com/nateriera/screening-workbench/releases/tag/v1.0.0) — `Screening-Workbench-1.0.0-windows-x64.zip` (16,702,642 bytes; SHA-256 `3288d64ff81929a72d2f8e6859114cc0c9c2aa83b250578ff91ae6e222ddff5c`). Unzip and run `ScreeningWorkbench.exe` — no installer.

The build is not code-signed yet, so Windows SmartScreen may show "Windows protected your PC" on first launch. Choose **More info → Run anyway**, and verify your download against the SHA-256 above. Code signing is planned for a future release; the release's full verification record is `docs/release-gate-1.0.0.md`.

### macOS ARM64 candidate

A macOS ARM64 candidate is built by the [`macOS ARM64 candidate package` workflow](.github/workflows/macos-package.yml) on pushes to `platform/macos-package`. Download the `Screening-Workbench-1.1.0-macos-arm64-candidate` artifact from a completed workflow run and inspect its validation evidence and run result before use; a failed run can retain an artifact for diagnosis. Version 1.1.0 is the candidate label, not a published release. See [`docs/packaging.md`](docs/packaging.md) for install, build, and Gatekeeper instructions.

**Run from source** (Windows 11 x64):

```powershell
git clone https://github.com/nateriera/screening-workbench.git
cd screening-workbench
# Requires Python 3.12+ (tested on CPython 3.14) with Tkinter, both
# included in the standard python.org Windows installer. No third-party
# dependencies to install.
$env:PYTHONPATH = "src"
python -m screening_workbench.app
```

**Run from source** (macOS, Apple silicon): use Python 3.12+ with Tkinter. The workflow uses the official Python.org 3.12.10 installer, which includes Tk. Homebrew installs Tkinter separately; install the matching formula for your Python minor version (for example, `brew install python@3.12 python-tk@3.12`), then verify that `python3.12 -c 'import tkinter'` succeeds.

```sh
git clone https://github.com/nateriera/screening-workbench.git
cd screening-workbench
PYTHONPATH=src python3.12 -m screening_workbench.app
```

The default project is `%USERPROFILE%\screening-workbench-project.sqlite`. PDF attachments are stored beside the database under `attachments\<sha256>.pdf`; copy that folder with the database when moving a project. Reviewer packet and vote files are separate exports and do not move the original database.

## 5-minute quickstart

1. Launch the app (double-click `ScreeningWorkbench.exe`, or `python -m screening_workbench.app` if running from source).
2. **File → Import CSV...** and pick a CSV with a header row (at minimum a `title` column — `authors`, `year`, `journal`, `doi`, and `abstract` are also recognized). A handful of test rows works fine for a first look.
3. Screen each record: press **I** to Include, **M** for Maybe, or **E** then a numbered reason to Exclude. The queue auto-advances to the next undecided record.
4. Click the **PRISMA & audit** tab. The counts snapshot and flow diagram update live from the same records you just screened — no separate "calculate" step. ("Preview as of watermark sequence N" just means this on-screen view isn't the frozen, audit-stamped copy yet — that's what step 5 produces.)
5. **File → Export package...** to write the official watermarked PRISMA SVG, decisions/audit/report-study-link CSVs, and a manifest to a folder of your choice.

The quickstart describes the current workflow; check the release notes and acceptance records for the exact build and verification status.

## Clean-room build

Screening Workbench is built from public, self-authored behavioral specifications only — see `docs/specs/`. No incumbent screening application's accounts, code, UI text, labels, or assets were accessed or copied during development; specs cite only public documentation (RFCs, format references, public vendor docs) with access dates, never incumbent-product behavior. Third-party licensing (the Python/Tkinter/SQLite runtime and packaging toolchain; the application itself has no third-party Python dependencies) is reviewed in `docs/license-audit.md`.

## License

MIT — see [`LICENSE`](LICENSE).

## Known import limitations

- RIS: conflicting TI/T1 (or PY/Y1) values are not flagged; the first value wins.
- PubMed XML: a malformed file is rejected whole rather than salvaging intact records.

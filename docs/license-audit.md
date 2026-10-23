# License audit: v1 candidates and package gate

**Access date:** 2026-10-07  
**Historical evidence note:** The build observations below describe a disposable, isolated smoke test, not a release build or package approval.

**Scope:** Engineering review of the owner-selected v1 application runtime and Windows distribution plan, not legal advice. The application runtime is intended to have no third-party Python dependencies. Before a packaged release, review the exact CPython distribution/runtime, PyInstaller build dependencies, collected Python libraries (including Tcl/Tk, SQLite, OpenSSL, zlib, expat and VC runtime as actually bundled), bootloader and package artifacts. The complete resolved tree and redistributable notices/SBOM must match the application build that is actually distributed.

## Owner-selected v1 shape

- Windows 11 x64 only (owner-selected).
- CPython 3.14.7 x64 from python.org selected by owner as the target runtime. The Windows x64 installer hash and official SBOM were checked on 2026-10-07; component license texts still need citation in release notices.
- Python + Tkinter + SQLite; core runtime built from Python standard library.
- RIS parser is original/narrow; CSV/XML parsing uses stdlib.
- Native SVG output only; no PNG renderer.
- Ranking deferred; no ASReview, scikit-learn, RapidFuzz or other v1 application dependency selected.

## Current candidate evidence

| Component | Current evidence | v1 status |
|---|---|---|
| CPython | **Verified 2026-10-07**: downloaded the official `python-3.14.7-amd64.exe`; local SHA-256 matches the published hash exactly (`9d9eb270...ae9649`). Official SPDX SBOM (34 packages) confirms CPython itself is PSF-2.0; bundled runtime components relevant to a frozen app (Tcl 9.0.4.0, Tk 9.0.4.1, SQLite 3.50.4.0, OpenSSL 3.5.7, zlib-ng 2.2.4, expat 2.8.2, libffi 3.4.4, bzip2 1.0.8, xz 5.2.5) are present in the SBOM; their licenses are well-established permissive/public-domain terms (Tcl/Tk license, public domain, Apache-2.0, zlib license, MIT, BSD-style) but the SBOM itself marks them `NOASSERTION` (no formal auto-assertion) -- file-level license text should still be pulled before final release notices. | **CLEARED for hash/provenance; license text citation pending for release notices.** |
| PyInstaller | Candidate 6.21.0; GPLv2-or-later with bootloader exception. **Confirmed 2026-10-07** by reading the actual wheel's `COPYING.txt`: bootloader/loader files are explicitly exception-covered and may be embedded in generated non-free apps; `rthooks`/`isolated` subdirs are separately Apache-2.0/MIT. | **CLEARED for use as a build tool** under its own exception; does not itself clear bundled third-party deps. |
| `pyinstaller-hooks-contrib` | Required by PyInstaller metadata (`>=2026.6`); wheel 2026.8 inspected locally: 688 standard hooks (GPL-2.0-or-later, `stdhooks/`) + 15 runtime hooks (Apache-2.0, `rthooks/`). **Empirically tested 2026-10-07**: ran a real PyInstaller 6.21.0 onedir build of a stdlib-only smoke script (`tkinter`, `sqlite3`, `csv`, `xml.etree.ElementTree`, `json`, `uuid`, `datetime`) in an isolated throwaway venv. The Analysis log shows every hook that fired (`hook-tkinter.py`, `hook-sqlite3.py`, `hook-xml.py`, `hook-platform.py`, `hook-sysconfig.py`, `hook-_ctypes.py`, `hook-encodings.py`, `hook-pickle.py`, `hook-math.py`, `hook-difflib.py`, `hook-heapq.py`) came from PyInstaller's own built-in `PyInstaller\hooks` directory -- **none** came from `_pyinstaller_hooks_contrib`. No contrib-sourced hook path appears anywhere in the build log or warnings file. | **CLEARED for a stdlib-only app**: hooks-contrib's GPL-2.0-or-later files are not collected/executed when the frozen app imports only stdlib modules. Must be re-verified if any future import changes the module set. |
| Standard-library app runtime | No third-party application runtime package selected; empirically confirmed no third-party hook or package is pulled in by a stdlib-only smoke build. | **CLEARED.** |

### Real build evidence (2026-10-07, isolated throwaway venv/scratch only -- nothing installed into the project)

Downloaded `python-3.14.7-amd64.exe` and its official `.spdx.json` SBOM to a temporary location and verified the SHA-256 hash matches the published value. Installed PyInstaller 6.21.0 and its six resolved build dependencies into a disposable virtual environment built from downloaded wheels (not installed into the project or a shared environment). Ran `pyinstaller --onedir` against a throwaway stdlib-only script exercising `tkinter`, `sqlite3`, `csv`, `xml.etree.ElementTree`, `json`, `uuid`, and `datetime`. Build succeeded; its analysis log showed only PyInstaller's built-in hooks firing, with no hooks-contrib files touched. The frozen smoke app itself did not run in that sandbox because its Tcl data-directory path was unavailable. This was a toolchain smoke test, not an application build or release verification.

### Observed, non-locked PyInstaller resolution

A no-install pip dry run using pip 26.2.1 on CPython 3.14.7/Windows x64 resolved: `altgraph==0.17.5`, `packaging==26.3`, `pefile==2024.8.26`, `pyinstaller==6.21.0`, `pyinstaller-hooks-contrib==2026.8`, `pywin32-ctypes==0.2.3`, and `setuptools==84.0.0`. PyInstaller metadata has conditional `macholib` for macOS and `importlib-metadata` for Python below 3.10; neither was selected on this Windows 3.14 dry run. This is evidence only, not a lock or clearance. The resolution report is a local scratch artifact, not a project lockfile.

Direct BuildPyInstaller requirements have open ranges. Before making a reproducible build, pin all exact wheels and hashes, inspect each actual license and transitive tree, verify PyInstaller `COPYING.txt`/bootloader exception, enumerate hooks and files actually copied, then compare against final package. Do not treat the generated app license exception as clearing included dependencies.

The CPython 3.14.7 Windows x64 installer at `https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe` has been downloaded and its SHA-256 verified to match the published hash exactly (`9d9eb2709ef81bf5cd30db3c2096bdbc4ea10087c22e62f27d356b36f6ae9649`). The official SPDX SBOM was reviewed; CPython itself is PSF-2.0 and bundled components use well-known permissive/public-domain licenses, though the SBOM does not auto-assert them formally -- cite exact license text per component before producing final release attribution notices.


## Blocking decisions/tasks

1. **DONE** -- CPython 3.14.7 Windows x64 installer hash verified locally against the published SHA-256 (`9d9eb2709ef81bf5cd30db3c2096bdbc4ea10087c22e62f27d356b36f6ae9649`); SBOM reviewed; component license text citation for release notices still to be compiled (not blocking for implementation start).
2. **DONE** -- PyInstaller 6.21.0's actual Windows wheel/bootloader/`COPYING.txt` inspected; bootloader exception confirmed applicable to the generated app.
3. **DONE** -- `pyinstaller-hooks-contrib==2026.8` inspected and empirically tested: its GPL files are not collected for a stdlib-only app.
4. Use PyInstaller onedir first for inspectability; no installer in initial build (owner-confirmed). Any later installer requires a separate audit and owner approval.
5. Re-run the hook/Analysis check against the actual Screening Workbench application on the target CPython environment; if its imports collect third-party packages or hooks, review those exact components. Generate final SBOM/attribution notices and audit the exact release distribution before any merge/publish/deploy -- still requires separate authorization.

**Historical verdict (2026-10-07): conditionally cleared to begin implementation.** CPython 3.14.7, PyInstaller 6.21.0 onedir, and their resolved build-tool dependency tree were checked with a representative stdlib-only smoke build. This did not audit the current Screening Workbench application package. Its final SBOM/attribution notices, actual collected components, and exact distribution still require review before release. Merge, publish, and deployment also require separate authorization under the project guardrails.


## Bundled typefaces (direction 02, owner ruling 2026-10-21)

**Ruling:** Nate approved adding three SIL Open Font License 1.1 typeface families as bundled, unmodified data files (2026-10-21, in the Phase B session). They are not code dependencies and add no Python package.

**Evidence (accessed 2026-10-21):** each file was downloaded from its upstream repository at a pinned commit, its git blob hash matched the GitHub contents API for that path and commit, and its SHA-256 is recorded below and pinned by `tests/test_app.py::test_r1_bundled_fonts_are_exactly_the_audited_files`. Each family's `OFL.txt` was taken from the same commit and is shipped verbatim in `docs/notices/`. None of the three license headers declares a Reserved Font Name; the files are shipped unmodified (no subsetting or renaming), so the Reserved Font Name clause does not apply. `Newsreader` is a registered trademark of Production Systems SAS (upstream `trademarks.md`); the app uses the name only to identify the bundled font.

**Use:** loaded for the app process only with `AddFontResourceExW(..., FR_PRIVATE)` (`src/screening_workbench/typefaces.py`); nothing is installed on the user's machine. OFL 1.1 permits bundling and redistribution with software provided each copy carries the copyright notice and license, and the fonts are not sold by themselves.

| File | Family / version | Source | SHA-256 |
|---|---|---|---|
| `Newsreader16pt-Regular.ttf` | Newsreader (16pt static cuts) 1.003 | `productiontype/NewsReader@cfcb4f7` `fonts/static/ttf/` | `0636887c9f72f77ce188f0b31029be58e65adae5a47e6d2887ad5020c2c75036` |
| `Newsreader16pt-Italic.ttf` | Newsreader (16pt static cuts) 1.003 | `productiontype/NewsReader@cfcb4f7` `fonts/static/ttf/` | `292646cbb948153511e308fa80def59959746d70114bd0936ba0a7f67a33181d` |
| `Newsreader16pt-Medium.ttf` | Newsreader (16pt static cuts) 1.003 | `productiontype/NewsReader@cfcb4f7` `fonts/static/ttf/` | `ee2f66ee4c6c313acf211c952211f8c6c0c0d9fa6a17cd0ec0ceba13418b1aed` |
| `Newsreader16pt-Bold.ttf` | Newsreader (16pt static cuts) 1.003 | `productiontype/NewsReader@cfcb4f7` `fonts/static/ttf/` | `9e3d485293bb2f86d22f1a9bfb8d7213cff188270fa240b5084e27290746aea7` |
| `AtkinsonHyperlegibleNext-Regular.ttf` | Atkinson Hyperlegible Next 2.001 | `googlefonts/atkinson-hyperlegible-next@7925f50` `fonts/ttf/` | `88ed5c31a71584c7772963b02d04bef1eb7e3d2e9c8b9cb204339b1f82cf432c` |
| `AtkinsonHyperlegibleNext-Bold.ttf` | Atkinson Hyperlegible Next 2.001 | `googlefonts/atkinson-hyperlegible-next@7925f50` `fonts/ttf/` | `994414047df66bb4998d01c1cb1eeb4a2ddc4622d1aa56bbb8adbeca7645b041` |
| `AtkinsonHyperlegibleNext-Italic.ttf` | Atkinson Hyperlegible Next 2.001 | `googlefonts/atkinson-hyperlegible-next@7925f50` `fonts/ttf/` | `b7f8f03ceb28ebadb2de2332b2e869a00e8dbfb5c8e00fdbb06385770c8227e7` |
| `AtkinsonHyperlegibleMono-Regular.ttf` | Atkinson Hyperlegible Mono 2.001 | `googlefonts/atkinson-hyperlegible-next-mono@154d503` `fonts/ttf/` | `2c9a7b9fabebd5c746a808d8a1ef2f52e618850caad6ec4fd9f5c48f56e1c1af` |
| `AtkinsonHyperlegibleMono-Bold.ttf` | Atkinson Hyperlegible Mono 2.001 | `googlefonts/atkinson-hyperlegible-next-mono@154d503` `fonts/ttf/` | `51ad68fafd7ec68051f64983c9c23182a7084268b5cdb0a154dbd53ade079da6` |
| `AtkinsonHyperlegibleMono-Italic.ttf` | Atkinson Hyperlegible Mono 2.001 | `googlefonts/atkinson-hyperlegible-next-mono@154d503` `fonts/ttf/` | `356060ab70ae62e4460dd824ec1b734af24e5c3355a8302700151d35d1382dd4` |

**Status: CLEARED** for bundling with the notices above. Re-audit if a file is replaced, subset, or renamed.

## Future-scope candidate evidence (not selected for v1)

The following prior research is retained for possible future consideration only; it does not authorize or clear any component for the owner-selected v1 runtime or package.

### Candidate recommendations

Prefer **no third-party dependency** for the proposed RIS/XML use cases: implement only the required RIS field handling and use Python's standard-library XML parser. This avoids importing rispy's GPLv2 obligations; PubMed Entrez API access is not required for parsing XML. If fuzzy matching is needed, RapidFuzz is the clearest reviewed candidate; if SVG manipulation is needed, svg.js is clear at its root package manifest level. For rendering, defer resvg-js pending the native dependency inventory. Defer ASReview pending an exact lock/resolution and review of all immediate runtime dependency licenses, especially its declared rispy GPL dependency.

**Not selected for v1:** ASReview, scikit-learn, RapidFuzz, svg.js, resvg-js, rispy and other third-party app dependencies. V1 uses Python standard library parsing and original SVG generation; ranking and PNG output are deferred. This is not dependency clearance for any future version. The exact Python runtime/toolchain/installer artifacts and every component bundled into the Windows distribution still require separate version pins and license review.

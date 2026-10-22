---
title: Screening Workbench 1.0.0 Runtime License Review
date: 2026-10-13
type: release-review
product: Screening Workbench
version: 1.0.0
source-commit: f93a88b12dbd32272c7e9dc5bf8544478df9f160
confidence: medium
---

# License review — Screening Workbench 1.0.0 Windows runtime

## For future reviewers

This is an engineering review of the compiled Windows x64 onedir artifact, not legal advice. It records what was observable in the exact frozen tree, official CPython 3.14.7 distribution SBOM, source archives, Tcl/Tk license files, PE imports, and PyInstaller build logs. The app imports only Python standard-library modules; the bundle includes CPython/Tcl/Tk and additional standard-library implementation components. The tree indicates no application GPL/LGPL component, but component version/provenance discrepancies and omitted license notices prevent an unconditional redistribution clearance.

## Artifact scope

- Source commit: `f93a88b12dbd32272c7e9dc5bf8544478df9f160`.
- Build: CPython 3.14.7 x64, PyInstaller 6.21.0, Windows 11 x64, PyInstaller onedir/windowed.
- ZIP: `Screening-Workbench-1.0.0-windows-x64.zip`, 16,702,642 bytes, SHA-256 `3288d64ff81929a72d2f8e6859114cc0c9c2aa83b250578ff91ae6e222ddff5c`; 1,013 ZIP entries and `ZipFile.testzip()` returned no corrupt member. **Amendment, 2026-10-21:** the package was rebuilt from source commit `f93a88b` following `docs/packaging.md`, with the 14 `docs/notices/` files included, after the 2026-10-13 artifact could not be located on the build PC (it had been kept in a prune-prone scratch folder; the rebuild is stored durably). Superseded identities, retained as history: the 2026-10-13 notices rebuild (15,895,056 bytes, SHA-256 `349414995b6cb00c81ffbcbf0e83c0d721726a03aff7647c22a82acc8933e36c`, 1,012 entries) and the first build (15,870,858 bytes, SHA-256 `5865219df1ba9efcefdb9e5e8868e5cf46aedecfec2fa498c4842066e45502e2`, 999 entries). The figures above are the release identity. See `docs/release-gate-1.0.0.md`.
- Tree: `ScreeningWorkbench.exe` plus `_internal/` with 68 native PE files (52 DLLs, 16 Python extension modules), Tcl and Tk script trees (839 Tcl files, 90 Tk files), and no site-packages/dist-info/vendor package files. Only Tcl/Tk license files were found in the frozen output.
- The official CPython 3.14.7 Windows x64 archive checksum is `ac1a727a71738e11de80b76e975f9b8a258aea6412bfc31696b929d59c6aafd0`, matching the official Windows release manifest and its official SPDX SBOM. The SBOM has 34 packages and records most bundled component license fields as `NOASSERTION`; that value is not itself a license conclusion.

## Runtime component inventory and license evidence

| Component | Runtime version evidence | License and evidence | Notice in frozen output? |
|---|---|---|---|
| Screening Workbench | 1.0.0, `pyproject.toml` | Project `LICENSE` is MIT. App source imports standard-library modules only; compiled PYZ contains the application plus Python stdlib. | `notices/Screening-Workbench-LICENSE.txt`. |
| CPython | 3.14.7; official Windows manifest, source archive checksum and PE version resources | PSF-2.0 for CPython, verified in official SBOM and CPython `LICENSE.txt`. | `notices/CPython-LICENSE.txt` (complete upstream LICENSE.txt). |
| Tcl | 9.0.4; `tcl90.dll` version resource. Hash matches CPython's Tcl/Tk support MSI payload. | Tcl/Tk permissive license terms. | `_internal/_tcl_data/license.terms`; duplicate `notices/Tcl-license.terms`. |
| Tk | 9.0.4; `tcl9tk90.dll` version resource. Hash matches CPython's Tcl/Tk support MSI payload. | Tcl/Tk permissive license terms. | `_internal/_tk_data/license.terms`; duplicate `notices/Tk-license.terms`. |
| LibTomMath | 1.3.0, Tcl 9.0.4 source `libtommath/CMakeLists.txt`; `tommath.h` uses `SPDX-License-Identifier: Unlicense`; bundled DLL matches MSI payload | Unlicense/public-domain dedication. | `notices/LibTomMath-LICENSE.txt`. |
| OpenSSL | `libcrypto-3-x64.dll` and `libssl-3-x64.dll` PE version resources both report **3.5.8**. Official CPython 3.14.7 SBOM and hash-verified source archive report **3.5.7**. We fetched the official OpenSSL 3.5.8 source tarball (SHA-256 `a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2`), but did not match its native binaries to the bundle. | OpenSSL 3.x license is Apache-2.0. | `notices/OpenSSL-LICENSE.txt` (OpenSSL 3.5.8 source archive). |
| SQLite | `sqlite3.dll` PE version resource reports **3.53.1.0**. Official CPython 3.14.7 SBOM and source hash identify **3.50.4.0**. | SQLite public domain / blessing; source-version difference unresolved. | `notices/SQLite-NOTICE.txt` records upstream public-domain dedication and blessing; cited source `sqlite.org/copyright.html`. |
| zlib / zlib-ng | `zlib1.dll` PE resource reports **1.3.2**. Official CPython SBOM says **zlib-ng 2.2.4**. | Permissive zlib license. Exact binary provenance/version map not resolved. | `notices/zlib-LICENSE.md` (zlib-ng 2.2.4 upstream source dependency archive). |
| Expat | `pyexpat.pyd` contains `expat_2.8.2`, consistent with official SBOM **2.8.2**. | MIT license. | `notices/Expat-COPYING.txt` (Expat 2.8.2 source). |
| libffi | `_ctypes.pyd` and `libffi-8.dll`; official CPython SBOM reports **3.4.4**, artifact-to-source hash not established. | MIT-style upstream license; exact binary source remains unverified. | `notices/libffi-LICENSE.txt` (libffi 3.4.4 source dependency archive). |
| bzip2 | `_bz2.pyd` present; official SBOM reports **1.0.8**; no binary source hash match. | bzip2 permissive license. | `notices/bzip2-LICENSE.txt` (bzip2 1.0.8 source dependency archive). |
| XZ/liblzma | `_lzma.pyd` present; official SBOM reports **XZ 5.2.5**; exact extension provenance was not hash-matched. | XZ `COPYING` states liblzma is public domain; LGPL/GPL applies to other XZ files/tools, not found in the observed bundle. | `notices/XZ-COPYING.txt` (upstream XZ 5.2.5 `COPYING`, which documents liblzma's public-domain status). |
| Zstandard | `_zstd.pyd` embeds `1.5.7`, consistent with official SBOM; exact binary provenance not hash-matched. | Zstandard BSD license for the library. Although the distribution archive also includes GPL-2.0 `COPYING`, that separate text is for optional GPL-licensed `programs` sources. The frozen runtime contains `_zstd.pyd`, not CLI programs; compiled-extension source-level license mapping remains unverified. | `notices/Zstandard-LICENSE.txt` (upstream BSD library license). |
| VC runtime / Windows API-set DLLs | `VCRUNTIME140.dll` and `_1` version resources: **14.44.35211.0**; UCRT/API-set DLLs are included by PyInstaller from this Windows host and bear Windows build resources. | Microsoft Learn Visual Studio 2022 Redistribution says that unmodified files within `[VisualStudioFolder]\VC\redist` may be redistributed with the program, subject to the Visual Studio License Terms; it also says distribution of the standalone redist package / individual binaries is limited to licensed Visual Studio users. This means redistribution is allowed only if the distributor has a valid applicable Visual Studio license and the included files are the unmodified listed redist files. We found Visual Studio 2022 Community installed but have not established the licensee/terms accepted, nor proven that every API-set/UCRT DLL in the frozen tree is on Microsoft's REDIST list. | No standalone Microsoft license text is bundled; rights are conditional on applicable VS license and Microsoft's current list. |



## Third-party dependency and GPL/LGPL check

- Source-level imports and PyInstaller's archive listing show `screening_workbench` plus Python standard-library modules; no `site-packages`, `dist-info`, or application-level third-party Python package was found in the frozen directory or PYZ.
- The frozen PE files were enumerated (68 `.dll`/`.pyd`/`.exe` files); import-table review found only the identified Python/Tcl/OpenSSL/SQLite/other bundled runtime libraries and Windows system DLLs. It did not reveal another unrecognized third-party DLL.
- PyInstaller 6.21.0 and `pyinstaller-hooks-contrib` 2026.8 are build-time tools and are not present in the frozen output. For the actual application build, the tkinter/sqlite3/XML/platform hooks that fired came from PyInstaller's built-in hook directory; no hook-contrib hook fired/was collected. The contrib package's GPL hooks are therefore not evidence of GPL code in this app artifact. PyInstaller's actual `COPYING.txt` confirms its bootloader exception, but that exception does not cover the application's other included components.
- **No GPL/LGPL component was identified in the final runtime tree from the inspected source, PE imports, and collected module listing.** The XZ source package includes GPL/LGPL command-line/docs/build files, but the observed frozen output contains `_lzma.pyd` and no XZ CLI/library DLL. This is a negative finding from available binary/archive evidence, not a formal proof that no GPL/LGPL-licensed source fragment exists in any compiled binary.

## Verdict

**Conditionally cleared for notice inclusion; still not ready for unconditional public distribution.** The bundle's third-party notices are now collected at `docs/notices/` for inclusion in the ZIP. The application itself is MIT and stdlib-only; Tcl/Tk are permissively licensed, and the binary review did not identify a GPL/LGPL component in the bundled runtime. However, the final tree's OpenSSL, SQLite and zlib version resources still disagree with the official CPython SBOM; OpenSSL 3.5.8 source has been located but the shipped binaries have not been matched to it. Microsoft runtime redistribution is permitted under the applicable Visual Studio license only for unmodified files on the REDIST list; the entitlement and the full API-set/UCRT file list are not yet confirmed. Therefore this package is a documentation/build artifact, not legal approval to publish. Reconcile the exact binary provenance and confirm Microsoft's redistribution entitlement before public release.


## Primary evidence

- Official CPython 3.14.7 x64 Windows archive: `https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.zip` (SHA-256 `ac1a727a71738e11de80b76e975f9b8a258aea6412bfc31696b929d59c6aafd0`).
- Official CPython Windows manifest: `https://www.python.org/ftp/python/3.14.7/windows-3.14.7.json`; Windows x64 archive entry records the above SHA-256.
- Official Python 3.14.7 SPDX SBOM: `https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.zip.spdx.json` (34 package entries; most third-party licenses `NOASSERTION`).
- Official Tcl/Tk 9.0.4 source dependency: `https://github.com/python/cpython-source-deps/archive/refs/tags/tcl-9.0.4.0.tar.gz` (SHA-256 `3ac2acd65ddaaac0b2b8df321b558419d21da20bf67ab39149b8248c85f0d214`); contains `library/license.terms` and `libtommath/LICENSE`.
- OpenSSL source dependency for the official CPython 3.14.7 baseline: `https://github.com/python/cpython-source-deps/archive/refs/tags/openssl-3.5.7.tar.gz` (SHA-256 `ca94e7c6c223d9caf77bb51aac5949186379608ea2a0cad3aa8bdf31856912e9`); its `LICENSE.txt` is Apache-2.0. It does not establish provenance for the artifact's 3.5.8 binaries.
- Visual Studio 2022 Community is installed on the build host. Microsoft's current Visual Studio 2022 Redistribution page states that unmodified files within `[VisualStudioFolder]\\VC\\redist` may be copied/distributed with the program subject to the Visual Studio License Terms, and that distribution of the standalone VC Redistributable package/individual binaries is limited to licensed Visual Studio users. This confirms the governing redistribution basis, not this publisher's entitlement: verify the applicable account/license and verify each bundled CRT/UCRT/API-set file is on the REDIST list. Sources: `https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution` and `https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170`.
- SQLite copyright/licensing: `https://www.sqlite.org/copyright.html` (SQLite code and docs dedicated to public domain; blessing is published there).
- Official upstream notice source archives used for repository notices: CPython Tcl/Tk 9.0.4 dependency archive (Tcl/Tk `license.terms`, LibTomMath `LICENSE`); OpenSSL 3.5.8 source archive (Apache-2.0 `LICENSE.txt`, SHA-256 `a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2`); Expat 2.8.2 `COPYING`; zlib-ng 2.2.4 `LICENSE.md`; libffi 3.4.4 `LICENSE`; bzip2 1.0.8 `LICENSE`; XZ 5.2.5 `COPYING`; Zstandard 1.5.7 `LICENSE` (BSD license for the library).

All artifact-level findings above are dated 2026-10-13 and apply to this recorded ZIP only; they do not automatically clear later builds or runtime changes.

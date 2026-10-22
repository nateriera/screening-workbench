---
title: Screening Workbench 1.0.0 — Launch-Tail Gate Report
date: 2026-10-21
type: release-gate
product: Screening Workbench
version: 1.0.0
prepared-by: Cinder
status: Gate closed on paper. Signing and the publish call remain the owner's.
---

# Launch-tail gate report — Screening Workbench v1.0.0

This report closes the four remaining v1.0.0 release-tail items, in order, with the
evidence behind each answer. It is an engineering record, not legal advice.

Method note: the release artifact itself resides on the Windows build PC (the
2026-10-13 build tree); it is not present in the environment this report was
prepared from. Every artifact-level fact below is therefore cited to the frozen
2026-10-13 record — `docs/license-review.md` and `docs/sbom.cdx.json`, both
committed in this repository — and the one physical verification that still
requires the artifact (re-hashing the ZIP on the build PC) is carried as step 1
of the pre-signing checklist in item 4, not silently assumed.

Release identity (used throughout):

- Artifact: `Screening-Workbench-1.0.0-windows-x64.zip`
- Size: 15,895,056 bytes
- SHA-256: `349414995b6cb00c81ffbcbf0e83c0d721726a03aff7647c22a82acc8933e36c`
- Source commit: `f93a88b12dbd32272c7e9dc5bf8544478df9f160`
- Build: CPython 3.14.7 x64, PyInstaller 6.21.0 onedir/windowed, Windows 11 x64

## Item 1 — License-review size and hash citation: CORRECTED

`docs/license-review.md` ("Artifact scope") cited the superseded first build:
15,870,858 bytes, SHA-256
`5865219df1ba9efcefdb9e5e8868e5cf46aedecfec2fa498c4842066e45502e2` (999 entries,
`ZipFile.testzip()` clean). The shippable package is the 2026-10-13 rebuild that
adds the 14 `docs/notices/` files; its identity is the release identity above,
recorded in `docs/sbom.cdx.json` (metadata properties `release.archive`,
`release.archive.size.bytes`, `release.archive.sha256`).

The correction has been applied to `docs/license-review.md` in both repositories
(public `nateriera/screening-workbench` and private `nateriera/cull`, whose copies
were byte-identical, blob `b0933b90`). The superseded figures are preserved inside
the corrected line as dated history, so the change is reviewable and nothing was
silently overwritten.

Verification basis: the committed SBOM record, cross-checked against the
2026-10-13 rebuild record. Caveat: the artifact was not re-hashed from this
environment (see method note); re-hashing is pre-signing checklist step 1.

## Item 2 — OpenSSL / SQLite / zlib provenance: EVIDENCED, one limit recorded

Shipped-versus-official inventory. "Shipped" = the PE version resources recorded
in the frozen tree by the 2026-10-13 license review. "Official baseline" = the
official CPython 3.14.7 distribution SBOM and hash-verified source archives.

| Library | Shipped (frozen tree) | Official CPython 3.14.7 baseline | License |
|---|---|---|---|
| OpenSSL (`libcrypto-3-x64.dll`, `libssl-3-x64.dll`) | **3.5.8** | 3.5.7 | Apache-2.0 |
| SQLite (`sqlite3.dll`) | **3.53.1.0** | 3.50.4.0 | Public domain |
| zlib (`zlib1.dll`) | **1.3.2** (version resource) | zlib-ng 2.2.4 (source dependency) | zlib license |

What the evidence establishes:

- **All three shipped versions are genuine official upstream releases** —
  verified fresh on 2026-10-21 against upstream records:
  - OpenSSL 3.5.8 is an official security patch release (25 Aug 2026), per the
    OpenSSL 3.5 series release notes (openssl-library.org). The license review had
    already fetched the official 3.5.8 source tarball, SHA-256
    `a8f84a39918ec6415ce765d9b429d313ba97b8143169c172e734b9514464f5b2`, and the
    bundled notice is that archive's Apache-2.0 `LICENSE.txt` — the notice
    matches the shipped version.
  - SQLite 3.53.1 is an official release (2026-05-05), per sqlite.org's release
    history and release notes (SQLITE_SOURCE_ID
    `2026-05-05 10:34:17 c88b22011a54b4f6fbd149e9f8e4de77658ce58143a1af0e3785e4e6475127e9`;
    SHA3-256 of `sqlite3.c`
    `414432ae5719f6cdc485f3927e12c7ad107e2b8c6b434e5df2eadb5312bfabb5`). SQLite is
    public domain, so the version delta carries no license consequence; the
    bundled notice is the upstream public-domain dedication/blessing.
  - zlib 1.3.2 is an official release (17 Feb 2026), per zlib.net/NVD records.
    The SBOM names zlib-ng 2.2.4 as the CPython source dependency; the shipped
    DLL's version resource reads 1.3.2, and the exact resource-to-source version
    map remains the one unresolved detail in this row. Both candidate sources
    carry the same permissive zlib license; the bundled notice is the zlib-ng
    2.2.4 `LICENSE.md`.
- The SBOM additionally records SHA-256 hashes for the two shipped OpenSSL DLLs
  (`6dadf2c701b8c991935222133ae0c789e2afeb444132aee79156591101c46d86`,
  `27cbeebacf0889dc91c69e17105415606a3c12f2bb9c1d9053b434b36d3bcdab`), pinning the
  exact binaries this gate covers.
- Pattern: all three deltas are *newer* than the CPython 3.14.7 embeddable
  baseline and all three are real upstream releases — consistent with the build
  host's CPython installation having been assembled from newer component builds
  than the embeddable-zip SBOM baseline. The frozen tree's version resources are
  the ground truth of what ships, and they are what this gate records.

What remains unproven, recorded plainly: no byte-level match of the three shipped
binaries against their upstream source trees has been established (CPython
publishes no per-DLL reference hashes for these components — unlike the Tcl/Tk
DLLs, which *were* hash-matched to the CPython MSI payload in the review). This
is accepted as a tradeoff for v1.0.0: the licenses are permissive and
version-independent (Apache-2.0 / public domain / zlib), the notices match the
shipped versions, and no GPL/LGPL component was identified anywhere in the
runtime tree.

## Item 3 — Visual Studio / Windows runtime redistribution: BASIS CONFIRMED, one owner attestation remains

Documentary findings (from the 2026-10-13 redistribution memo, checked against
Microsoft's published documentation; sources: Microsoft Learn, Visual Studio
2022 Redistribution page and the Universal CRT deployment documentation):

- The bundled VC runtime files — `VCRUNTIME140.dll` and `VCRUNTIME140_1.dll`,
  version 14.44.35211.0 — are on the Visual Studio 2022 REDIST list. Unmodified
  listed files may be redistributed with a program, subject to the Visual Studio
  License Terms.
- The UCRT set (`ucrtbase.dll` plus the `api-ms-win-crt-*` forwarder DLLs) is
  **not** on the VS REDIST list; it is covered by a second list — the Windows
  SDK's `Windows Kits\10\Redist\ucrt\DLLs` folder — and Microsoft documents
  app-local deployment of that set as supported.
- The remaining `api-ms-win-core-*` / other non-CRT API-set forwarders are on
  neither list. They are Windows OS components, inert on Windows 10/11 (the OS's
  own copies always win over app-local copies), and bundled by PyInstaller by
  default. **Decision recorded: keep them as bundled.** Stripping them would
  alter the frozen, verified build for no functional benefit on the target OS;
  the clean alternative (excluding them) is noted for any future rebuild.
- One mechanical check remains and is carried into item 4's checklist: the
  name-by-name enumeration of the bundle's `api-ms-win-*.dll` files against the
  SDK redist folder listing on the build host. It requires the artifact and
  cannot be done from the documents alone.

Entitlement: the redistribution *basis* is confirmed above. What no document
can confirm is the licensee side — that the build host's Visual Studio 2022
Community installation stands under a license accepted by the publisher. That
attestation is the owner's, and it is the single residual owner confirmation in
this gate; it is taken together with the signing and publish decisions in
item 4.

## Item 4 — SignPath-ready final ZIP: IDENTITY PINNED, physical steps on the build PC

Ready now:

- Package identity is pinned (top of this report) and the release documents now
  agree with it: `docs/license-review.md` (corrected, item 1) and
  `docs/sbom.cdx.json` cite the same size and SHA-256.
- License notices are in the package: the rebuild includes the 14 files of
  `docs/notices/` (application MIT license, CPython, Tcl, Tk, LibTomMath,
  OpenSSL 3.5.8, SQLite, zlib, Expat, libffi, bzip2, XZ, Zstandard, and the
  notices README).

Remaining physical steps — on the Windows build PC, where the artifact lives
(paste-ready brief delivered with this report):

1. Locate the rebuilt ZIP (2026-10-13 build tree) and verify size 15,895,056
   bytes and SHA-256 `349414995b…` before touching anything. If no local file
   matches, stop — do not sign or ship any other build under this gate.
2. Confirm the ZIP listing contains the `notices/` files (14).
3. Enumerate the bundle's `api-ms-win-*.dll` names against the Windows SDK
   `Redist\ucrt\DLLs\x64` listing (item 3's remaining check); file the result
   with this report.
4. Produce the handoff copy under a new filename —
   `Screening-Workbench-1.0.0-windows-x64-final.zip` — as a byte-identical copy,
   and re-verify its SHA-256 equals `349414995b…`.
5. Hand to the owner.

Owner steps, unchanged by this gate: the Visual Studio entitlement attestation
(item 3), SignPath signing, and the publish call (tag, GitHub release, ZIP
upload). Nothing in this report publishes anything.

## Gate verdict

The v1.0.0 publish tail is closed on paper: citation corrected (item 1),
provenance evidenced with its one limit recorded as an accepted tradeoff
(item 2), redistribution basis confirmed with the licensee attestation reserved
to the owner (item 3), and the package identity pinned with a short pre-signing
checklist for the build PC (item 4). The release is handed back to the owner for
the attestation, signing, and the publish call.

## Addendum — 2026-10-21 rebuild (supersedes the package identity above)

The 2026-10-13 artifact could not be located on the build PC (it had been stored
in a prune-prone Hermes scratch folder), so the package was rebuilt from source
commit `f93a88b` following `docs/packaging.md`, with the 14 `docs/notices/`
files included, into a durable location
(`C:\Users\nater\Documents\Chaff\release-1.0.0\`).

New release identity: `Screening-Workbench-1.0.0-windows-x64.zip` —
**16,702,642 bytes** — SHA-256
`3288d64ff81929a72d2f8e6859114cc0c9c2aa83b250578ff91ae6e222ddff5c` — 1,013
entries.

Build verification (builder report, 2026-10-21): CPython 3.14.7 x64 and
PyInstaller 6.21.0; the CPython archive and Tcl/Tk MSI hashes matched
`docs/packaging.md`; 929 Tcl/Tk data entries collected (839 Tcl and 90 Tk files
in the tree, matching the verified fix); ZIP integrity check passed; smoke
test — window titled "Screening Workbench -- systematic review screening",
clean exit code 0; the 14 notice files are byte-for-byte equal to
`docs/notices/`.

Item 3 completion: the rebuilt bundle's API-set enumeration is now on record —
`ucrtbase.dll` plus 40 `api-ms-win-*.dll` forwarders: 14 `api-ms-win-crt-*`
(the Windows SDK UCRT redist family) and 26 `api-ms-win-core-*` (on neither
redistribution list; the "keep" disposition in item 3 stands). The
name-matching check left open in item 3 is closed.

Carry-over note: item 2's component inventory stands for the rebuilt package
by construction (same pinned, hash-verified sources). The per-DLL hashes in
`docs/sbom.cdx.json` were measured on the 2026-10-13 tree.

`docs/license-review.md` and `docs/sbom.cdx.json` have been amended to the new
identity. Remaining owner steps are unchanged: the `-final.zip` handoff copy,
the Visual Studio entitlement attestation, SignPath signing, and the publish
call.

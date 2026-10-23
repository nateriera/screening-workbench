---
title: Screening Workbench 2.0.0 Release Gate
date: 2026-10-22
type: release-gate
product: Screening Workbench
version: 2.0.0
artifact-name: Screening-Workbench-2.0.0-windows-x64.zip
artifact-size-bytes: 17398639
artifact-sha256: 15a30f396e00f7367485181f140601899cb1b8ba5ff074ee52db64c9243f49a7
build-commit: 5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7
prepared-by: Codex (builder/gate agent)
reviewer: Cinder
status: GATE PASSED (2026-10-23)
---

# Screening Workbench 2.0.0 release gate

## Release identity

- Branch: `implementation/v2-release-2.0.0`, cut from `v2` at `8b7e3cb`.
- Package source build commit: `5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7`.
- Artifact: `Screening-Workbench-2.0.0-windows-x64.zip`.
- Size: 17,398,639 bytes.
- SHA-256: `15a30f396e00f7367485181f140601899cb1b8ba5ff074ee52db64c9243f49a7`.
- Build: Windows x64, CPython 3.14.7, Tk 9.0.4, PyInstaller 6.21.0, onedir/windowed.
- Package contents: 1,029 ZIP entries; ZIP integrity check passed. All five required Tcl/Tk runtime paths were present, all ten bundled TTF hashes matched `docs/license-audit.md`, and all 16 staged notice files matched `docs/notices/`.

This is an engineering release record, not legal advice or distribution approval. No versioned release, merge to `v2`, or signing was performed. Signing was not approved. Branch commits in this record document gate evidence and do not imply release approval.

## Automated verification

The full suite passed **437/437 tests** on each builder runtime:

- CPython 3.14.2 / Tk 8.6.15.
- CPython 3.14.7 / Tk 9.0.4.

Both runs exited successfully; the previously observed Tcl `invalid command name "...quit"` timer callback appeared as nonfatal output. Independent Haiku gate: pending when this report was prepared; record the final result here before any release commit or push.

## Build procedure deviations

- LessMSI was unavailable on the build host; the matching Tcl/Tk MSI was extracted with `msiexec /a`.
- The relative PyInstaller font `--add-data` source failed because the external `--specpath` caused it to resolve from the spec directory. The successful build used the absolute font source under `SWB_ROOT`.
- The output package, ZIP payload, font hashes, runtime paths, and notice copies were verified.

## Packaged application smoke test: BLOCKED

The application window became visible and one synthetic CSV row was imported, but the packaged process was not running under a verified disposable Windows profile. Although a temporary settings path was set, `SW_SETTINGS_PATH` does not control the project database location; the app derives its default project path from the Windows user home. The synthetic import was followed by a change to the user-profile database WAL sidecar. The main database file size and timestamp were unchanged at the time checked.

No database, WAL, or SHM contents were read. No recovery, deletion, restore, or other database alteration was performed. The owner explicitly instructed that the database remain untouched. Data impact is undetermined. No further app interaction or smoke capture was done.

The following required checks therefore remain incomplete:

- Verify the packaged app starts from a fresh isolated profile with `USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `APPDATA`, `LOCALAPPDATA`, and `SW_SETTINGS_PATH` redirected and confirm the project database path before importing.
- Create/open a synthetic project and complete Screening, PRISMA, Full-text, and attach/open PDF workflows.
- Capture the Screening view in both Light and Night themes from that isolated synthetic project.
- Reconfirm no user-profile database path is used.

`docs/packaging.md` now documents the isolation precondition. Existing screenshots from the failed attempt do not count as release evidence.

## License and packaging review

`docs/license-review.md` identifies the exact 2.0.0 package and distinguishes it from the historical 1.0.0 binary review. Package notices and fonts were verified. The exact-package runtime comparison is now recorded below; its material delta and the CRT version-record discrepancy remain unresolved. Microsoft Visual C++ redistribution entitlement has not been cleared for this exact package.

## Decision

**Not release-ready.** Do not commit or push this candidate, merge it into `v2`, tag it, or publish it until an isolated package smoke test and the independent gate pass and the exact-package redistribution review is resolved. The existing `release-1.0.0/` directory was not modified.

## Gate update after independent run (2026-10-22)

The independent detached-worktree run passed the complete suite on both runtimes: CPython 3.14.2 / Tk 8.6.15 passed 437 tests in 668.21 seconds, and CPython 3.14.7 / Tk 9.0.4 passed 437 tests in 714.07 seconds. Both exited successfully; the known Tcl quit-callback message was nonfatal. The independent ZIP inspection confirmed the recorded 17,398,639-byte artifact and SHA-256, 1,029 clean entries, all ten font hashes, five required Tcl/Tk files, and sixteen byte-identical notice files.

The extracted package was also started with a fresh disposable profile at C:\Users\nater\Documents\Codex\Screening-Workbench-v2.0.0-smoke-20261022\profile-light. Python home resolved to that profile and the app created its project database there. The visible initial window opened. No synthetic project import, tab workflow, or PDF attach/open workflow was completed, and no accepted Light or Night package screenshots were captured. Per the owner's direction, the existing user-profile database and sidecars were not accessed after the initial WAL change.

The independent runner inspected source commit 5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7, before the current working-copy documentation updates. It reported stale v1.0.0 identity in that detached copy and did not find the untracked release-gate report there. The current working-copy release docs identify the exact 2.0.0 package. The SBOM root component, dependency reference, and archive identity now use 2.0.0; its separately labeled historical v1.0.0 note remains as provenance history. At the time of this entry, these documentation updates had not yet been re-reviewed in the detached copy. The 2.0.0 runtime review still says per-binary provenance and Microsoft Visual C++ redistribution entitlement have not been cleared for this ZIP.

Gate remains blocked. The full tests and package-content checks pass, but the extracted-application Screening, PRISMA, Full-text, and synthetic PDF workflows and both-palette screenshots remain incomplete. Exact-package runtime provenance and redistribution entitlement also remain unresolved. Do not commit or push, merge into v2, tag, sign, or publish while these gates are open.

## Current working-copy documentation review (2026-10-22)

A later read-only static review confirmed that the current packaging, runtime license review, SBOM, gate report, and convergence log consistently identify the exact 2.0.0 ZIP. The SBOM parses, and its root identity, dependency reference, ZIP size, hash, entry count, and ten nested font hashes match the package. The review caught a stale remote placeholder and theme value in the packaging instructions; these now use the configured private repository URL and supported light/night values. Whitespace and SBOM checks passed.

This documentation review did not run tests or launch the application. It does not close the packaged workflow, palette capture, runtime provenance, or Microsoft redistribution gates.

## Runtime provenance comparison — STOP / review required (2026-10-22)

**Exact package identity:** `Screening-Workbench-2.0.0-windows-x64.zip` — 17,398,639 bytes; SHA-256 `15a30f396e00f7367485181f140601899cb1b8ba5ff074ee52db64c9243f49a7`; source build commit `5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7`.

The comparison was made against the preserved shipped 1.0.0 ZIP named in `docs/release-gate-1.0.0.md`, and the exact 2.0.0 ZIP named above. Every archived file was read from each ZIP and compared by member path, uncompressed size, and SHA-256. The runtime set is every `.dll` and `.pyd` anywhere in the archive plus every file under `_internal/`. The v1 gate records broad native-runtime counts, but does not enumerate every path, so this comparison reconstructs the v1 file inventory directly from its preserved ZIP. The complete 2.0.0 file manifest is below; every runtime row carries its comparison result.

| Runtime delta | File count | Result |
|---|---:|---|
| Identical path, size, and SHA-256 | 956 | Listed as `identical` in the complete package manifest |
| Added | 13 | 10 expected font files and 3 unexpected API-set DLLs |
| Removed | 0 | None |
| Modified at the same path | 42 | Details below |

### Added runtime files

| ZIP path | Size (bytes) | SHA-256 |
|---|---:|---|
| `ScreeningWorkbench/_internal/api-ms-win-core-fibers-l1-1-1.dll` | 22872 | `5ef70308bcca628ce6b0e2856b15b1c7ae340c3f9bbbc4c1071d8c191a34a5c3` |
| `ScreeningWorkbench/_internal/api-ms-win-core-kernel32-legacy-l1-1-1.dll` | 22888 | `5200b16cb2ddc61cfc07373a9a84aa85a3ab50806ca96c879c883275832944c1` |
| `ScreeningWorkbench/_internal/api-ms-win-core-sysinfo-l1-2-0.dll` | 22912 | `8a0900788859d0eb51c2f48f50cc6ed376a120b518100fa20e11d7702ccde260` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleMono-Bold.ttf` | 53544 | `51ad68fafd7ec68051f64983c9c23182a7084268b5cdb0a154dbd53ade079da6` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleMono-Italic.ttf` | 54248 | `356060ab70ae62e4460dd824ec1b734af24e5c3355a8302700151d35d1382dd4` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleMono-Regular.ttf` | 52020 | `2c9a7b9fabebd5c746a808d8a1ef2f52e618850caad6ec4fd9f5c48f56e1c1af` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleNext-Bold.ttf` | 66792 | `994414047df66bb4998d01c1cb1eeb4a2ddc4622d1aa56bbb8adbeca7645b041` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleNext-Italic.ttf` | 69812 | `b7f8f03ceb28ebadb2de2332b2e869a00e8dbfb5c8e00fdbb06385770c8227e7` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleNext-Regular.ttf` | 65068 | `88ed5c31a71584c7772963b02d04bef1eb7e3d2e9c8b9cb204339b1f82cf432c` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/Newsreader16pt-Bold.ttf` | 134632 | `9e3d485293bb2f86d22f1a9bfb8d7213cff188270fa240b5084e27290746aea7` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/Newsreader16pt-Italic.ttf` | 131332 | `292646cbb948153511e308fa80def59959746d70114bd0936ba0a7f67a33181d` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/Newsreader16pt-Medium.ttf` | 136428 | `ee2f66ee4c6c313acf211c952211f8c6c0c0d9fa6a17cd0ec0ceba13418b1aed` |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/Newsreader16pt-Regular.ttf` | 121824 | `0636887c9f72f77ce188f0b31029be58e65adae5a47e6d2887ad5020c2c75036` |

### Removed runtime files

None.

### Modified runtime files

| ZIP path | v1 size (bytes) | v2 size (bytes) | v1 SHA-256 | v2 SHA-256 |
|---|---:|---:|---|---|
| `ScreeningWorkbench/_internal/api-ms-win-core-console-l1-1-0.dll` | 22896 | 22872 | `27954e62e12d115bb1540db4bb9de6e2c852d914aea61cba3c203595138537b2` | `015bd08815c7b934a8952c3a7578e9ce59f21136e8a880d42bbd414bec2c6058` |
| `ScreeningWorkbench/_internal/api-ms-win-core-datetime-l1-1-0.dll` | 22896 | 22896 | `6f22ff5bf9d53b7f2c3fcd553d9b8664ef5401912194b8e599e4dbd8f3105405` | `5534812cdbdae94ba45cb216e5eb9af686b853948df54365103555abbbaf9d9a` |
| `ScreeningWorkbench/_internal/api-ms-win-core-debug-l1-1-0.dll` | 22896 | 22872 | `c5dc0df2fcc456c2b08392ea7d539d43549d04d14ed83d69cd46f79b9e34902a` | `837d2b1b2cd03e03fc6ccb050698b6b5763af17c201304872342a5eae9e0a2d2` |
| `ScreeningWorkbench/_internal/api-ms-win-core-errorhandling-l1-1-0.dll` | 22872 | 22872 | `9ff8300ecf0ebd4c8130800b5b8857b6ddf21902264af42fb1ac15c794115864` | `de43b165f568c276c00e95acd454e3092f352a18e95874595f4f4658c06d2ec7` |
| `ScreeningWorkbench/_internal/api-ms-win-core-fibers-l1-1-0.dll` | 22872 | 22872 | `39174763da266b4b955e27eecaef15d8283bb77f9eca94fe925d4928f37a4fa1` | `3cebc45bf479ad74cfabf2c6bfd4994d7ad639ed1221025981d19cedf9ce0416` |
| `ScreeningWorkbench/_internal/api-ms-win-core-file-l1-1-0.dll` | 27008 | 27008 | `a9660f0e3ab6032bba0b75e1d02ce0bc57c9043bca423477843a7a3af1b1c200` | `250ac829f2617bcac1c6e5b8c4f630462e20765863ba573526a3e11bbfb94a9a` |
| `ScreeningWorkbench/_internal/api-ms-win-core-file-l1-2-0.dll` | 22896 | 22888 | `445a2c24c8565834e1e41e4c617d2f9cf5def8e4a477e55e2f18583845b24c1d` | `ae14079a114733f60ce87b92cba42acd8083c2cd67594e53bc37dc0b97a4b465` |
| `ScreeningWorkbench/_internal/api-ms-win-core-file-l2-1-0.dll` | 20960 | 22912 | `f957a4c261506484b53534a9be8931c02ec1a349b3f431a858f8215cecfec3f7` | `914bf26a298713119477ea0a8e7bd43171b91344ebe24fb47ad77c49686e3d87` |
| `ScreeningWorkbench/_internal/api-ms-win-core-handle-l1-1-0.dll` | 22896 | 22896 | `94f7611fa4568f4577deba250c1254a3c83ffc7b4fd2f00243f3bfac5a993fd8` | `ab5489955e371b15f77906c08ec3c7affe2c7a46a08c514ca628768b4478974b` |
| `ScreeningWorkbench/_internal/api-ms-win-core-heap-l1-1-0.dll` | 22888 | 22872 | `d655a217f4c17982b4c5ecb406290885c74afba361dd840c4245c0b28e07c192` | `c70f9644d8377fa39c5b71f2e9734c1400d7598904fdeb772e8502099982dcb7` |
| `ScreeningWorkbench/_internal/api-ms-win-core-interlocked-l1-1-0.dll` | 22896 | 22888 | `69b0f1e099dac7ffbbf1260eb4818abeacd2b9cf105b742b16e6bd5dda3bf035` | `f8129710188e407bb0e6f46d30aeba277d67b947ece5fe09e883fde2323f3ae6` |
| `ScreeningWorkbench/_internal/api-ms-win-core-libraryloader-l1-1-0.dll` | 22872 | 22872 | `87622d07bb5c9fa5ccd9f74ac70a1e2ae0cdf54462f90f365178a15a814bf3c4` | `48786fb88b001dcd1f63acea903d3ca9cc0b3060d5a325e3f2f3cbc3bfd53166` |
| `ScreeningWorkbench/_internal/api-ms-win-core-localization-l1-2-0.dll` | 22912 | 22872 | `79ec668286cb900c66e1caf8a47309d986c9dc4d37a5d2dcedb2ff2a973896d9` | `9ec3898f7eba91faa28b51616c211a2689e3a13aeef8de6e13cb674e49d689eb` |
| `ScreeningWorkbench/_internal/api-ms-win-core-memory-l1-1-0.dll` | 22888 | 22896 | `7f12e6eb9a992ea199bcfc755eea488a8889cd2642dba00e49fb06a14bec8408` | `3a6cbc524c99e1cd80d5368f5601402a37ad602528b1ab628093573ef638eb3b` |
| `ScreeningWorkbench/_internal/api-ms-win-core-namedpipe-l1-1-0.dll` | 22912 | 22888 | `daf13af507230a92191c348611e8b31bc384055ea5b9a6d18057646d93bfe4f7` | `97145ef89c44949fcf0f04ac834a8bc7d687ef49ee73ae9fc32f3c11136b7201` |
| `ScreeningWorkbench/_internal/api-ms-win-core-processenvironment-l1-1-0.dll` | 22896 | 22872 | `74d809270a418e4bc1d3b94348094f00463635cedfbadd97d29686a6d037d2da` | `8bc7c10b1851aea644e9c9f381cdb935e091fee6b0be3d3aedc6fffaac96adb7` |
| `ScreeningWorkbench/_internal/api-ms-win-core-processthreads-l1-1-0.dll` | 22896 | 22912 | `6620a7962adb6a25a51e13add907189763b76d0816a356465d135eeeed1065a0` | `d8030b777617c71f0f94564607699dbf7561487d779db9756aed378c5675213f` |
| `ScreeningWorkbench/_internal/api-ms-win-core-processthreads-l1-1-1.dll` | 22872 | 22872 | `82850eb2e7d100938ebd419440e4575750999bc9e349cd074019e413673d02c8` | `f5e676713340f73a03a3d41a6ec9883b431da7d16c7f07bd0a920fb80e6c0753` |
| `ScreeningWorkbench/_internal/api-ms-win-core-profile-l1-1-0.dll` | 22872 | 22872 | `b43119bdfc7c562bf07c26e01b7b862aa8dc9d5e795798fe93969111244ed2da` | `f023d47e44d3eea6b0743580f57e8c6ba81e79d5ebfa7da26250076c647b980e` |
| `ScreeningWorkbench/_internal/api-ms-win-core-rtlsupport-l1-1-0.dll` | 22912 | 22888 | `bd0cff402e3f64baaf2bfb17d86b2c4c7d03584ea2601ca5c55de147a769a32a` | `9746d8930704153578a628c010638a5f818ffe5a927e25591b108e256dc6afca` |
| `ScreeningWorkbench/_internal/api-ms-win-core-string-l1-1-0.dll` | 22896 | 22896 | `1985000499475faf541b17c8acbce788bcdba6dddd3b8910b6730238f1c18862` | `7c53ae24c982d16ffd1bf7f918d115b11b7f30e57bc7feaa18cb9781e4abb926` |
| `ScreeningWorkbench/_internal/api-ms-win-core-synch-l1-1-0.dll` | 22896 | 22896 | `055544d562ca50d49443926bca396de985735f7451806ff2565486e406809d25` | `56d9d62ca5dba79a6581b8d574a7d8b2a64a5ecb71e47dcf06ed0285708b1859` |
| `ScreeningWorkbench/_internal/api-ms-win-core-synch-l1-2-0.dll` | 22912 | 22888 | `0d8f2f7d031f143110c9bf5bdd4f75b24e8b41319fa2e20f78068c084e0d7603` | `f6482bbec5612c39ecb4822787a333f2b7570f7a5f922a4059be41ba957bb372` |
| `ScreeningWorkbench/_internal/api-ms-win-core-sysinfo-l1-1-0.dll` | 22872 | 22896 | `8010d006df2d62839c933d3b5998abc7a7830ffe32ca68b17c76f3292f5e56ec` | `272d02765fdd3582618236c2d309abba069642f9bc1062ede069d0c144e17007` |
| `ScreeningWorkbench/_internal/api-ms-win-core-timezone-l1-1-0.dll` | 22912 | 22896 | `1789f5e749cf3a5d419e3b835bd9d78a077ee77f3e761f0fbf3609e38ace6f40` | `ff35de6c03812b332e140f17dade25c5dd4775156da9eeb1eaae3fddd27236ec` |
| `ScreeningWorkbench/_internal/api-ms-win-core-util-l1-1-0.dll` | 22872 | 22896 | `c893a59c4d1fa86fb50d486ebf3a873244b910efec5b00690d4a20afb7ce0761` | `191ef3e98641a57296f19d572d8eb62489470ff1ef6030d136af170c2f835173` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-conio-l1-1-0.dll` | 22888 | 22872 | `9e466e76079b73bd9b0114004d040d193dc982e4150eee1241a902d16c2bda38` | `54ee5ec719a051496ff60aa00dbeaa94b9a7d2cdac27fe9b7317f1a666b6a2aa` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-convert-l1-1-0.dll` | 26968 | 26992 | `64c48b1280e4540c205ee7798b7da200afd95898d520ece1d56bf8a8a351fc3e` | `8b94662429171019fcd63c70bbf2095a075170599704a5e7dcdbe3da13f3a429` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-environment-l1-1-0.dll` | 22872 | 22912 | `1a513c0601c5b628018c003d8598586d4a48fd1acf51372f6783dc23b0a27756` | `39e5929593709e8af3bc9e0a75ec1155778d6f4a247f4cdfc58928ad6db88434` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-filesystem-l1-1-0.dll` | 22888 | 22872 | `89bb192dd079784d9ba716a2e45a1ee6af75c67e9151fde77eb8ec32cb014182` | `5a8ecebac32edf4e1f3c5c6c1c8ea1a1add6cda4f9c9cb26f752fb295bea6865` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-heap-l1-1-0.dll` | 22896 | 22872 | `e5a0c8d551e36e5fd394a45a5e9229f592b46d8e80897f25e7f0ca449abb6b00` | `c71080cbcb43bf1f8f3e391deb12a582eb0abefc80946f340675a2c616e4feb4` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-locale-l1-1-0.dll` | 22912 | 22896 | `f13dc1d6895f21fe2f7fd4b7ada78828b5a819013f751aa32eb1704beb4dc469` | `6c68648e524187e03c4ad9aaa4a99113c6ee9f29fb39cc0ed93f951975138e63` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-math-l1-1-0.dll` | 31088 | 31064 | `a13aed9e8d7f4f53826cedd6acbc7b75dba51aeecd7f030b0f0d7b7c66e1a042` | `d4fbcccbe29371cbce431e43b2eb4f7ba9a6f04a3d740a071f02457a505e9dc8` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-private-l1-1-0.dll` | 76144 | 76120 | `a573c8d83476655ed863aca9bc97c806b82bbcac03ce518906fa2458476de5f7` | `29bf3d90617d3781d19b332d6ceb9f20ba5ce082ec74bf6c34d5d4aee56e48a1` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-process-l1-1-0.dll` | 22912 | 22896 | `90d0c8e9ea6a4e82efcdc7ba522da3989316397218f3d1320eed1bab491c0938` | `47c1935942e3ac0812e4dcf18c0e265e565f0194a3349111c299712f5565f7ac` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-runtime-l1-1-0.dll` | 26992 | 26968 | `d893a0f2c1bf6247fb94393728c6293570090028d4dd30dcea01a01b0460b0c4` | `72adc1b3677e0814d9c4ebf0964000e84bb2acf67336c8963061665e44f78029` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-stdio-l1-1-0.dll` | 26992 | 26968 | `456adaf7d2116f3e9410a0c1acd19f54bc9decc8e75b02f82c4a7d56c980e71f` | `900afc3989673c9bb1a687ed38c192f46db9e6ba6d11a668898a539e7fc23798` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-string-l1-1-0.dll` | 26992 | 26968 | `8d360f373b21726d005df5d6e1e5d55f5aa83f6d9d6a055f4dc0331965671dba` | `fcf12466cc12fd3b73611fc0763a5a1f9d44e90349513c34a0c83b0f36421793` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-time-l1-1-0.dll` | 22872 | 22912 | `c674ee45208477eec3669db64abb586df50d4fa38aa5b47ed2012d4bc5d9ec4e` | `886e57c4a6adb299b38f02945369f590a67da4e79a798359fc60aaa067212d7c` |
| `ScreeningWorkbench/_internal/api-ms-win-crt-utility-l1-1-0.dll` | 22912 | 22912 | `7c31b21496d4783456d9093d0742e1727fe77e1ccb27d717c327039859561438` | `5f8f26b216ade615b67a41f6fbbb910972fc6153315a65bb8f09912be50215b1` |
| `ScreeningWorkbench/_internal/base_library.zip` | 1394319 | 1394319 | `5103d86a8267761ca9301618a3b89c0af88f5bc5ab635ccc14d68e66f332550d` | `53669003995016e7bfce744cda410e476a809b06c6744f0dc6e44259d6b6b574` |
| `ScreeningWorkbench/_internal/ucrtbase.dll` | 1122768 | 1362264 | `c04daeba7e7c4b711d33993ab4c51a2e087f98f4211aea0dcb3a216656ba0ab7` | `3239227d27667ba20d10a880751924e5719de0078f9fce232d149d383f7681f6` |

### Microsoft CRT version comparison

FileVersion and ProductVersion were read from both DLLs extracted separately from the exact v1 and v2 ZIPs. SHA-256 values below are from those extracted files.

| DLL | v1 gate record (item 3) | v1 exact ZIP | v2 exact ZIP | SHA-256 (same in both ZIPs) |
|---|---|---|---|---|
| `VCRUNTIME140.dll` | 14.44.35211.0 | 14.51.36247.0 | **14.51.36247.0** | `d1f4225df2cd877dbf130d5668a021dce3f94118455ff5ec952061c30afc9ce7` |
| `VCRUNTIME140_1.dll` | 14.44.35211.0 | 14.51.36247.0 | **14.51.36247.0** | `a7146c08f89fe5b04541ab507cdb59ff7b44534d4ba3c668a426c6450a03434e` |

**Record discrepancy:** the v1 gate's item 3 states 14.44.35211.0 for this pair, but both exact ZIP payloads contain byte-identical 14.51.36247.0 DLLs. The source gate record and preserved v1 artifact therefore disagree and need owner review.

**Entitlement carry-over:** not cleared. The comparison found three additional runtime DLLs and 42 modified runtime files; the CRT version recorded by the v1 gate also does not match the preserved v1 ZIP. The conditional carry-over statement is intentionally not applied. This delta is for Nate and Cinder to review; no entitlement conclusion is made here.

## Exact-package smoke completion — STOP / not run

The required runtime comparison condition failed. Per the gate instruction, the application was not launched, no fresh smoke extraction was used, and no smoke interaction was attempted. Each requested step remains unverified; this is a gate stop, not an observed application failure. No project database, WAL, or SHM was inspected or changed during this comparison.

| Requested step | Result | Observation |
|---|---|---|
| Extract final ZIP fresh for disposable-profile smoke | NOT RUN — STOP | Stopped before smoke after runtime comparison failed |
| Launch app under disposable profile | NOT RUN — STOP | App not launched |
| Create a project | NOT RUN — STOP | No interaction |
| Import synthetic CSV | NOT RUN — STOP | No interaction |
| Screening: Include vote | NOT RUN — STOP | No interaction |
| Screening: Maybe vote | NOT RUN — STOP | No interaction |
| Screening: Exclude with reason | NOT RUN — STOP | No interaction |
| Open PRISMA | NOT RUN — STOP | No interaction |
| Run PRISMA export | NOT RUN — STOP | No interaction |
| Full-text: decide with a reason | NOT RUN — STOP | No interaction |
| Attach a PDF | NOT RUN — STOP | No interaction |
| Open the attached PDF | NOT RUN — STOP | No interaction |
| View → Theme: switch to Night | NOT RUN — STOP | No interaction |
| View → Theme: switch back to Light | NOT RUN — STOP | No interaction |
| Toggle Reduce motion | NOT RUN — STOP | No interaction |
| Capture Screening in Light at README capture size (`package-screening-light.png`) | NOT CAPTURED — STOP | File not created |
| Capture Screening in Night at README capture size (`package-screening-night.png`) | NOT CAPTURED — STOP | File not created |

## Artifact identity cross-check and whitespace gate

The final ZIP values above were checked against all requested release records:

| File | Identity check |
|---|---|
| `docs/packaging.md` | Exact ZIP name, 17,398,639-byte size, SHA-256, and build commit match |
| `docs/license-review.md` | Exact ZIP name, size, SHA-256, and build commit match |
| `docs/sbom.cdx.json` | Parses with 2.0.0 root/dependency identity; ZIP name, size, SHA-256, and build commit match |

`git diff --check`: PASS (clean). The untracked gate report was also checked for trailing whitespace.

## Complete 2.0.0 ZIP file manifest

The ZIP contains 1,029 central-directory entries: 1,028 files listed below and one directory entry (`ScreeningWorkbench/`). Sizes are uncompressed file sizes. Runtime status is `identical`, `added`, or `modified`; `package-only` means outside the runtime-set definition above.

<details>
<summary>All 1,028 files in the final 2.0.0 ZIP, with size and runtime delta</summary>

| ZIP path | Size (bytes) | Runtime delta |
|---|---:|---|
| `ScreeningWorkbench/_internal/_bz2.pyd` | 88288 | identical |
| `ScreeningWorkbench/_internal/_ctypes.pyd` | 142560 | identical |
| `ScreeningWorkbench/_internal/_decimal.pyd` | 291552 | identical |
| `ScreeningWorkbench/_internal/_elementtree.pyd` | 138976 | identical |
| `ScreeningWorkbench/_internal/_hashlib.pyd` | 69344 | identical |
| `ScreeningWorkbench/_internal/_lzma.pyd` | 160992 | identical |
| `ScreeningWorkbench/_internal/_socket.pyd` | 87776 | identical |
| `ScreeningWorkbench/_internal/_sqlite3.pyd` | 132832 | identical |
| `ScreeningWorkbench/_internal/_ssl.pyd` | 190688 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/auto.tcl` | 23641 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/clock.tcl` | 63107 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/cookiejar/cookiejar.tcl` | 22076 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/cookiejar/idna.tcl` | 7745 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/cookiejar/pkgIndex.tcl` | 217 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/cookiejar/public_suffix_list.dat.gz` | 70835 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/ascii.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/big5.enc` | 94389 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cns11643.enc` | 98634 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1250.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1251.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1252.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1253.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1254.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1255.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1256.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1257.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp1258.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp165.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp437.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp737.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp775.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp850.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp852.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp855.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp857.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp860.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp861.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp862.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp863.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp864.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp865.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp866.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp869.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp874.enc` | 1110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp932.enc` | 49008 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp936.enc` | 134671 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp949.enc` | 132551 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/cp950.enc` | 93330 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/dingbats.enc` | 1113 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/ebcdic.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/euc-cn.enc` | 86971 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/euc-jp.enc` | 83890 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/euc-kr.enc` | 95451 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/gb12345.enc` | 88033 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/gb1988.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/gb2312-raw.enc` | 85912 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/gb2312.enc` | 86971 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso2022-jp.enc` | 204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso2022-kr.enc` | 122 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso2022.enc` | 240 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-1.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-10.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-11.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-13.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-14.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-15.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-16.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-2.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-3.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-4.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-5.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-6.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-7.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-8.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/iso8859-9.enc` | 1114 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/jis0201.enc` | 1112 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/jis0208.enc` | 81772 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/jis0212.enc` | 72133 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/koi8-r.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/koi8-ru.enc` | 1112 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/koi8-t.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/koi8-u.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/ksc5601.enc` | 94393 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macCentEuro.enc` | 1116 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macCroatian.enc` | 1116 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macCyrillic.enc` | 1116 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macDingbats.enc` | 1116 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macGreek.enc` | 1113 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macIceland.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macJapan.enc` | 48813 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macRoman.enc` | 1113 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macRomania.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macThai.enc` | 1112 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macTurkish.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/macUkraine.enc` | 1115 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/shiftjis.enc` | 42552 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/symbol.enc` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/encoding/tis-620.enc` | 1112 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/foreachline.tcl` | 633 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/history.tcl` | 8234 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/http/http.tcl` | 185694 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/http/pkgIndex.tcl` | 282 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/icu.tcl` | 4006 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/init.tcl` | 24346 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/install.tcl` | 7586 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/license.terms` | 2295 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgcat/msgcat.tcl` | 38756 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgcat/pkgIndex.tcl` | 153 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/af.msg` | 1038 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/af_za.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ar.msg` | 1394 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ar_in.msg` | 265 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ar_jo.msg` | 1063 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ar_lb.msg` | 1063 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ar_sy.msg` | 1063 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/be.msg` | 1397 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/bg.msg` | 1319 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/bn.msg` | 1594 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/bn_in.msg` | 265 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ca.msg` | 1144 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/cs.msg` | 1266 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/da.msg` | 1192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/de.msg` | 1272 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/de_at.msg` | 831 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/de_be.msg` | 1268 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/el.msg` | 1448 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_au.msg` | 307 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_be.msg` | 312 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_bw.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_ca.msg` | 295 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_gb.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_hk.msg` | 329 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_ie.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_in.msg` | 318 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_nz.msg` | 307 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_ph.msg` | 329 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_sg.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_za.msg` | 251 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/en_zw.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/eo.msg` | 1261 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es.msg` | 1216 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_ar.msg` | 248 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_bo.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_cl.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_co.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_cr.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_do.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_ec.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_gt.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_hn.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_mx.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_ni.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_pa.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_pe.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_pr.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_py.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_sv.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_uy.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/es_ve.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/et.msg` | 1222 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/eu.msg` | 1032 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/eu_es.msg` | 294 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fa.msg` | 1109 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fa_in.msg` | 1383 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fa_ir.msg` | 390 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fi.msg` | 1179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fo.msg` | 997 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fo_fo.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fr.msg` | 1233 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fr_be.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fr_ca.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/fr_ch.msg` | 288 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ga.msg` | 1076 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ga_ie.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/gl.msg` | 973 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/gl_es.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/gv.msg` | 1084 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/gv_gb.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/he.msg` | 1340 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/hi.msg` | 1231 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/hi_in.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/hr.msg` | 1147 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/hu.msg` | 1301 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/id.msg` | 961 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/id_id.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/is.msg` | 1197 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/it.msg` | 1274 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/it_ch.msg` | 250 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ja.msg` | 1470 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/kl.msg` | 1025 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/kl_gl.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ko.msg` | 1423 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ko_kr.msg` | 339 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/kok.msg` | 1343 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/kok_in.msg` | 260 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/kw.msg` | 1013 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/kw_gb.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/lt.msg` | 1255 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/lv.msg` | 1227 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/mk.msg` | 1413 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/mr.msg` | 1267 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/mr_in.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ms.msg` | 957 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ms_my.msg` | 265 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/mt.msg` | 701 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/nb.msg` | 1193 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/nl.msg` | 1129 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/nl_be.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/nn.msg` | 1192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/pl.msg` | 1219 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/pt.msg` | 1161 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/pt_br.msg` | 286 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ro.msg` | 1200 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ru.msg` | 1375 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ru_ua.msg` | 248 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/sh.msg` | 1204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/sk.msg` | 1203 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/sl.msg` | 1204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/sq.msg` | 1281 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/sr.msg` | 1375 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/sv.msg` | 1195 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/sw.msg` | 1040 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ta.msg` | 1280 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/ta_in.msg` | 257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/te.msg` | 1471 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/te_in.msg` | 371 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/th.msg` | 1732 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/tr.msg` | 1131 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/uk.msg` | 1401 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/vi.msg` | 1271 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/zh.msg` | 2311 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/zh_cn.msg` | 310 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/zh_hk.msg` | 705 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/zh_sg.msg` | 335 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/msgs/zh_tw.msg` | 339 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/opt/optparse.tcl` | 31473 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/opt/pkgIndex.tcl` | 637 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/package.tcl` | 24857 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/parray.tcl` | 842 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/pkgIndex.tcl` | 721 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/platform/pkgIndex.tcl` | 261 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/platform/platform.tcl` | 11494 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/platform/shell.tcl` | 6216 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/readfile.tcl` | 622 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/safe.tcl` | 48454 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tclIndex` | 9977 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tcltest/pkgIndex.tcl` | 640 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tcltest/tcltest.tcl` | 108817 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tm.tcl` | 12282 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Abidjan` | 147 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Accra` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Addis_Ababa` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Algiers` | 1080 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Asmara` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Asmera` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Bamako` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Bangui` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Banjul` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Bissau` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Blantyre` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Brazzaville` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Bujumbura` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Cairo` | 8472 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Casablanca` | 5926 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Ceuta` | 7536 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Conakry` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Dakar` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Dar_es_Salaam` | 191 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Djibouti` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Douala` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/El_Aaiun` | 5607 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Freetown` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Gaborone` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Harare` | 181 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Johannesburg` | 309 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Juba` | 1127 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Kampala` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Khartoum` | 1131 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Kigali` | 181 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Kinshasa` | 180 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Lagos` | 235 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Libreville` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Lome` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Luanda` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Lubumbashi` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Lusaka` | 181 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Malabo` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Maputo` | 149 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Maseru` | 199 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Mbabane` | 200 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Mogadishu` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Monrovia` | 208 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Nairobi` | 277 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Ndjamena` | 208 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Niamey` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Nouakchott` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Ouagadougou` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Porto-Novo` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Sao_Tome` | 234 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Timbuktu` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Tripoli` | 954 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Tunis` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Africa/Windhoek` | 1649 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Adak` | 8447 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Anchorage` | 8685 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Anguilla` | 202 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Antigua` | 201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Araguaina` | 1892 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Buenos_Aires` | 2170 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Catamarca` | 2201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/ComodRivadavia` | 242 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Cordoba` | 2165 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Jujuy` | 2163 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/La_Rioja` | 2232 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Mendoza` | 2201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Rio_Gallegos` | 2204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Salta` | 2131 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/San_Juan` | 2232 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/San_Luis` | 2205 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Tucuman` | 2231 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Argentina/Ushuaia` | 2199 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Aruba` | 199 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Asuncion` | 3533 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Atikokan` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Atka` | 177 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Bahia` | 2138 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Bahia_Banderas` | 2042 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Barbados` | 648 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Belem` | 1091 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Belize` | 3284 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Blanc-Sablon` | 206 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Boa_Vista` | 1269 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Bogota` | 252 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Boise` | 8605 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Buenos_Aires` | 239 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Cambridge_Bay` | 8154 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Campo_Grande` | 3100 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Cancun` | 1442 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Caracas` | 288 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Catamarca` | 227 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Cayenne` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Cayman` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Chicago` | 11372 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Chihuahua` | 2040 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Ciudad_Juarez` | 6880 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Coral_Harbour` | 192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Cordoba` | 219 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Costa_Rica` | 431 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Coyhaique` | 4484 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Creston` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Cuiaba` | 3094 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Curacao` | 201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Danmarkshavn` | 1194 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Dawson` | 3028 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Dawson_Creek` | 1940 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Denver` | 8920 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Detroit` | 8430 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Dominica` | 202 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Edmonton` | 8600 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Eirunepe` | 1302 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/El_Salvador` | 279 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Ensenada` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Fort_Nelson` | 4578 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Fort_Wayne` | 231 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Fortaleza` | 1509 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Glace_Bay` | 8372 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Godthab` | 180 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Goose_Bay` | 10353 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Grand_Turk` | 7522 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Grenada` | 201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Guadeloupe` | 204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Guatemala` | 399 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Guayaquil` | 255 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Guyana` | 254 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Halifax` | 11124 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Havana` | 8729 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Hermosillo` | 589 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indiana/Indianapolis` | 7230 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indiana/Knox` | 8755 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indiana/Marengo` | 7273 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indiana/Petersburg` | 7611 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indiana/Tell_City` | 7100 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indiana/Vevay` | 6563 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indiana/Vincennes` | 7226 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indiana/Winamac` | 7410 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Indianapolis` | 233 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Inuvik` | 8053 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Iqaluit` | 8086 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Jamaica` | 847 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Jujuy` | 211 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Juneau` | 8682 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Kentucky/Louisville` | 9553 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Kentucky/Monticello` | 8558 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Knox_IN` | 204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Kralendijk` | 204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/La_Paz` | 220 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Lima` | 480 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Los_Angeles` | 9726 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Louisville` | 228 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Lower_Princes` | 207 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Maceio` | 1633 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Managua` | 611 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Manaus` | 1234 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Marigot` | 201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Martinique` | 251 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Matamoros` | 6745 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Mazatlan` | 2036 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Mendoza` | 219 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Menominee` | 8410 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Merida` | 1877 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Metlakatla` | 6705 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Mexico_City` | 2261 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Miquelon` | 7536 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Moncton` | 10507 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Monterrey` | 2100 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Montevideo` | 3070 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Montreal` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Montserrat` | 204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Nassau` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/New_York` | 11373 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Nipigon` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Nome` | 8680 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Noronha` | 1483 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/North_Dakota/Beulah` | 8557 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/North_Dakota/Center` | 8557 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/North_Dakota/New_Salem` | 8560 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Nuuk` | 7834 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Ojinaga` | 6874 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Panama` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Pangnirtung` | 193 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Paramaribo` | 255 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Phoenix` | 496 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Port-au-Prince` | 6613 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Port_of_Spain` | 207 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Porto_Acre` | 201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Porto_Velho` | 1111 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Puerto_Rico` | 283 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Punta_Arenas` | 3959 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Rainy_River` | 196 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Rankin_Inlet` | 8029 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Recife` | 1506 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Regina` | 1781 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Resolute` | 8025 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Rio_Branco` | 1176 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Rosario` | 219 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Santa_Isabel` | 194 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Santarem` | 1141 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Santiago` | 9433 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Santo_Domingo` | 616 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Sao_Paulo` | 3084 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Scoresbysund` | 7625 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Shiprock` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Sitka` | 8651 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/St_Barthelemy` | 207 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/St_Johns` | 11289 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/St_Kitts` | 202 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/St_Lucia` | 202 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/St_Thomas` | 203 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/St_Vincent` | 204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Swift_Current` | 874 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Tegucigalpa` | 341 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Thule` | 6890 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Thunder_Bay` | 193 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Tijuana` | 9845 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Toronto` | 11248 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Tortola` | 201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Vancouver` | 5320 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Virgin` | 200 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Whitehorse` | 3033 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Winnipeg` | 9695 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Yakutat` | 8683 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/America/Yellowknife` | 196 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Casey` | 662 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Davis` | 336 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/DumontDUrville` | 214 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Macquarie` | 8447 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Mawson` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/McMurdo` | 195 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Palmer` | 2777 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Rothera` | 153 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/South_Pole` | 198 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Syowa` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Troll` | 5370 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Antarctica/Vostok` | 240 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Arctic/Longyearbyen` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Aden` | 171 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Almaty` | 1773 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Amman` | 2684 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Anadyr` | 2220 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Aqtau` | 1771 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Aqtobe` | 1772 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Ashgabat` | 930 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Ashkhabad` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Atyrau` | 1772 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Baghdad` | 1808 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Bahrain` | 171 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Baku` | 2287 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Bangkok` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Barnaul` | 2253 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Beirut` | 8024 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Bishkek` | 1775 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Brunei` | 176 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Calcutta` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Chita` | 2220 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Choibalsan` | 192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Chongqing` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Chungking` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Colombo` | 373 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Dacca` | 169 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Damascus` | 3694 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Dhaka` | 372 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Dili` | 243 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Dubai` | 150 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Dushanbe` | 868 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Famagusta` | 7599 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Gaza` | 10227 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Harbin` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Hebron` | 10202 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Ho_Chi_Minh` | 411 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Hong_Kong` | 2226 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Hovd` | 1683 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Irkutsk` | 2221 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Istanbul` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Jakarta` | 374 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Jayapura` | 215 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Jerusalem` | 8135 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Kabul` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Kamchatka` | 2192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Karachi` | 459 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Kashgar` | 174 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Kathmandu` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Katmandu` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Khandyga` | 2255 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Kolkata` | 336 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Krasnoyarsk` | 2194 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Kuala_Lumpur` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Kuching` | 703 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Kuwait` | 173 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Macao` | 169 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Macau` | 2227 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Magadan` | 2222 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Makassar` | 247 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Manila` | 539 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Muscat` | 170 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Nicosia` | 7625 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Novokuznetsk` | 2195 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Novosibirsk` | 2257 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Omsk` | 2187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Oral` | 1770 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Phnom_Penh` | 180 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Pontianak` | 373 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Pyongyang` | 273 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Qatar` | 180 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Qostanay` | 1806 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Qyzylorda` | 1776 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Rangoon` | 174 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Riyadh` | 150 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Saigon` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Sakhalin` | 2253 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Samarkand` | 931 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Seoul` | 985 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Shanghai` | 981 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Singapore` | 378 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Srednekolymsk` | 2196 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Taipei` | 1344 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Tashkent` | 930 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Tbilisi` | 1837 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Tehran` | 2360 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Tel_Aviv` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Thimbu` | 176 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Thimphu` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Tokyo` | 388 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Tomsk` | 2252 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Ujung_Pandang` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Ulaanbaatar` | 1690 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Ulan_Bator` | 192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Urumqi` | 151 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Ust-Nera` | 2190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Vientiane` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Vladivostok` | 2194 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Yakutsk` | 2190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Yangon` | 246 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Yekaterinburg` | 2227 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Asia/Yerevan` | 2159 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Azores` | 10531 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Bermuda` | 8784 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Canary` | 6858 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Cape_Verde` | 254 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Faeroe` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Faroe` | 6796 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Jan_Mayen` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Madeira` | 9810 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Reykjavik` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/South_Georgia` | 162 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/St_Helena` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Atlantic/Stanley` | 2394 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/ACT` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Adelaide` | 8372 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Brisbane` | 674 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Broken_Hill` | 8437 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Canberra` | 195 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Currie` | 193 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Darwin` | 437 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Eucla` | 759 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Hobart` | 8734 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/LHI` | 199 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Lindeman` | 824 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Lord_Howe` | 7764 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Melbourne` | 8341 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/North` | 192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/NSW` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Perth` | 739 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Queensland` | 203 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/South` | 198 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Sydney` | 8338 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Tasmania` | 195 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Victoria` | 204 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/West` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Australia/Yancowinna` | 212 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Brazil/Acre` | 194 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Brazil/DeNoronha` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Brazil/East` | 191 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Brazil/West` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Canada/Atlantic` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Canada/Central` | 191 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Canada/Eastern` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Canada/Mountain` | 192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Canada/Newfoundland` | 196 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Canada/Pacific` | 194 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Canada/Saskatchewan` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Canada/Yukon` | 195 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/CET` | 177 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Chile/Continental` | 194 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Chile/EasterIsland` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/CST6CDT` | 181 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Cuba` | 175 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/EET` | 171 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Egypt` | 170 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Eire` | 172 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/EST` | 174 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/EST5EDT` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT` | 110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+0` | 159 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+1` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+10` | 120 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+11` | 120 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+12` | 120 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+2` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+3` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+4` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+5` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+6` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+7` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+8` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT+9` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-0` | 159 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-1` | 117 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-10` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-11` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-12` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-13` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-14` | 119 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-2` | 117 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-3` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-4` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-5` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-6` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-7` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-8` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT-9` | 118 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/GMT0` | 158 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/Greenwich` | 163 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/UCT` | 157 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/Universal` | 163 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/UTC` | 110 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Etc/Zulu` | 158 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Amsterdam` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Andorra` | 6927 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Astrakhan` | 2195 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Athens` | 7954 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Belfast` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Belgrade` | 7309 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Berlin` | 8020 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Bratislava` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Brussels` | 9223 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Bucharest` | 7974 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Budapest` | 8287 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Busingen` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Chisinau` | 8125 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Copenhagen` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Dublin` | 9810 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Gibraltar` | 9509 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Guernsey` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Helsinki` | 7368 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Isle_of_Man` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Istanbul` | 3693 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Jersey` | 181 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Kaliningrad` | 2514 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Kiev` | 173 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Kirov` | 2067 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Kyiv` | 7455 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Lisbon` | 9958 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Ljubljana` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/London` | 10211 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Luxembourg` | 191 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Madrid` | 8517 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Malta` | 8724 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Mariehamn` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Minsk` | 2179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Monaco` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Moscow` | 2430 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Nicosia` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Oslo` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Paris` | 9152 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Podgorica` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Prague` | 8038 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Riga` | 7658 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Rome` | 8813 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Samara` | 2254 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/San_Marino` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Sarajevo` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Saratov` | 2193 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Simferopol` | 2389 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Skopje` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Sofia` | 7654 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Stockholm` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Tallinn` | 7549 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Tirane` | 7675 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Tiraspol` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Ulyanovsk` | 2255 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Uzhgorod` | 177 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Vaduz` | 180 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Vatican` | 176 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Vienna` | 7930 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Vilnius` | 7485 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Volgograd` | 2161 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Warsaw` | 8662 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Zagreb` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Zaporozhye` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Europe/Zurich` | 7305 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/GB` | 170 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/GB-Eire` | 175 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/GMT` | 153 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/GMT+0` | 155 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/GMT-0` | 155 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/GMT0` | 154 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Greenwich` | 159 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Hongkong` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/HST` | 180 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Iceland` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Antananarivo` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Chagos` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Christmas` | 181 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Cocos` | 174 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Comoro` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Kerguelen` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Mahe` | 170 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Maldives` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Mauritius` | 282 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Mayotte` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Indian/Reunion` | 173 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Iran` | 166 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Israel` | 177 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Jamaica` | 181 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Japan` | 164 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Kwajalein` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Libya` | 176 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/MET` | 177 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Mexico/BajaNorte` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Mexico/BajaSur` | 191 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Mexico/General` | 200 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/MST` | 177 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/MST7MDT` | 178 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Navajo` | 177 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/NZ` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/NZ-CHAT` | 181 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Apia` | 957 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Auckland` | 8772 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Bougainville` | 288 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Chatham` | 8165 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Chuuk` | 202 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Easter` | 8727 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Efate` | 835 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Enderbury` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Fakaofo` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Fiji` | 1044 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Funafuti` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Galapagos` | 255 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Gambier` | 157 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Guadalcanal` | 159 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Guam` | 735 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Honolulu` | 344 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Johnston` | 193 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Kanton` | 214 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Kiritimati` | 223 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Kosrae` | 410 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Kwajalein` | 316 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Majuro` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Marquesas` | 159 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Midway` | 194 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Nauru` | 248 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Niue` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Norfolk` | 5465 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Noumea` | 340 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Pago_Pago` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Palau` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Pitcairn` | 190 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Pohnpei` | 201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Ponape` | 200 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Port_Moresby` | 192 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Rarotonga` | 1021 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Saipan` | 179 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Samoa` | 193 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Tahiti` | 156 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Tarawa` | 154 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Tongatapu` | 471 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Truk` | 201 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Wake` | 183 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Wallis` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Pacific/Yap` | 200 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Poland` | 174 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Portugal` | 176 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/PRC` | 171 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/PST8PDT` | 193 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/ROC` | 165 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/ROK` | 162 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Singapore` | 180 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Turkey` | 180 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/UCT` | 153 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Universal` | 159 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Alaska` | 189 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Aleutian` | 176 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Arizona` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Central` | 184 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/East-Indiana` | 228 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Eastern` | 187 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Hawaii` | 186 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Indiana-Starke` | 206 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Michigan` | 185 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Mountain` | 182 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Pacific` | 196 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/US/Samoa` | 188 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/UTC` | 153 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/W-SU` | 172 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/WET` | 171 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/tzdata/Zulu` | 154 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/word.tcl` | 4919 | identical |
| `ScreeningWorkbench/_internal/_tcl_data/writefile.tcl` | 948 | identical |
| `ScreeningWorkbench/_internal/_tk_data/bgerror.tcl` | 9206 | identical |
| `ScreeningWorkbench/_internal/_tk_data/button.tcl` | 21616 | identical |
| `ScreeningWorkbench/_internal/_tk_data/choosedir.tcl` | 9991 | identical |
| `ScreeningWorkbench/_internal/_tk_data/clrpick.tcl` | 22246 | identical |
| `ScreeningWorkbench/_internal/_tk_data/comdlg.tcl` | 8677 | identical |
| `ScreeningWorkbench/_internal/_tk_data/console.tcl` | 33232 | identical |
| `ScreeningWorkbench/_internal/_tk_data/dialog.tcl` | 5975 | identical |
| `ScreeningWorkbench/_internal/_tk_data/entry.tcl` | 19380 | identical |
| `ScreeningWorkbench/_internal/_tk_data/focus.tcl` | 5034 | identical |
| `ScreeningWorkbench/_internal/_tk_data/fontchooser.tcl` | 16160 | identical |
| `ScreeningWorkbench/_internal/_tk_data/iconbadges.tcl` | 13299 | identical |
| `ScreeningWorkbench/_internal/_tk_data/iconlist.tcl` | 17108 | identical |
| `ScreeningWorkbench/_internal/_tk_data/icons.tcl` | 2434 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/logo.eps` | 34982 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/logo100.gif` | 2341 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/logo64.gif` | 1670 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/logoLarge.gif` | 11000 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/logoMed.gif` | 3889 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/pwrdLogo.eps` | 29697 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/pwrdLogo100.gif` | 1615 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/pwrdLogo150.gif` | 2489 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/pwrdLogo175.gif` | 2981 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/pwrdLogo200.gif` | 3491 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/pwrdLogo75.gif` | 1171 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/README` | 329 | identical |
| `ScreeningWorkbench/_internal/_tk_data/images/tai-ku.gif` | 5473 | identical |
| `ScreeningWorkbench/_internal/_tk_data/license.terms` | 2307 | identical |
| `ScreeningWorkbench/_internal/_tk_data/listbox.tcl` | 14293 | identical |
| `ScreeningWorkbench/_internal/_tk_data/megawidget.tcl` | 9867 | identical |
| `ScreeningWorkbench/_internal/_tk_data/menu.tcl` | 39575 | identical |
| `ScreeningWorkbench/_internal/_tk_data/mkpsenc.tcl` | 30840 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgbox.tcl` | 17703 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/cs.msg` | 4726 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/da.msg` | 4699 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/de.msg` | 5604 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/el.msg` | 6352 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/en.msg` | 3992 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/en_gb.msg` | 66 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/eo.msg` | 4736 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/es.msg` | 4704 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/fi.msg` | 5763 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/fr.msg` | 4580 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/hu.msg` | 4966 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/it.msg` | 4513 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/nl.msg` | 5304 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/pl.msg` | 5527 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/pt.msg` | 4669 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/ru.msg` | 6371 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/sv.msg` | 4564 | identical |
| `ScreeningWorkbench/_internal/_tk_data/msgs/zh_cn.msg` | 6030 | identical |
| `ScreeningWorkbench/_internal/_tk_data/optMenu.tcl` | 1623 | identical |
| `ScreeningWorkbench/_internal/_tk_data/palette.tcl` | 9774 | identical |
| `ScreeningWorkbench/_internal/_tk_data/panedwindow.tcl` | 5356 | identical |
| `ScreeningWorkbench/_internal/_tk_data/print.tcl` | 43996 | identical |
| `ScreeningWorkbench/_internal/_tk_data/safetk.tcl` | 7634 | identical |
| `ScreeningWorkbench/_internal/_tk_data/scale.tcl` | 8227 | identical |
| `ScreeningWorkbench/_internal/_tk_data/scaling.tcl` | 6728 | identical |
| `ScreeningWorkbench/_internal/_tk_data/scrlbar.tcl` | 14788 | identical |
| `ScreeningWorkbench/_internal/_tk_data/spinbox.tcl` | 16619 | identical |
| `ScreeningWorkbench/_internal/_tk_data/systray.tcl` | 14972 | identical |
| `ScreeningWorkbench/_internal/_tk_data/tclIndex` | 20394 | identical |
| `ScreeningWorkbench/_internal/_tk_data/tearoff.tcl` | 4594 | identical |
| `ScreeningWorkbench/_internal/_tk_data/text.tcl` | 37445 | identical |
| `ScreeningWorkbench/_internal/_tk_data/tk.tcl` | 27570 | identical |
| `ScreeningWorkbench/_internal/_tk_data/tkfbox.tcl` | 38577 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/altTheme.tcl` | 5776 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/aquaTheme.tcl` | 8391 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/button.tcl` | 2999 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/clamTheme.tcl` | 6992 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/classicTheme.tcl` | 5450 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/combobox.tcl` | 16043 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/cursors.tcl` | 4644 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/defaults.tcl` | 8275 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/entry.tcl` | 18712 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/fonts.tcl` | 5183 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/menubutton.tcl` | 6439 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/notebook.tcl` | 7725 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/panedwindow.tcl` | 2117 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/progress.tcl` | 1273 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/scale.tcl` | 2674 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/scrollbar.tcl` | 3075 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/sizegrip.tcl` | 2455 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/spinbox.tcl` | 5513 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/treeview.tcl` | 12362 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/ttk.tcl` | 6628 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/utils.tcl` | 7610 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/vistaTheme.tcl` | 9751 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/winTheme.tcl` | 4177 | identical |
| `ScreeningWorkbench/_internal/_tk_data/ttk/xpTheme.tcl` | 3398 | identical |
| `ScreeningWorkbench/_internal/_tk_data/xmfbox.tcl` | 26837 | identical |
| `ScreeningWorkbench/_internal/_tkinter.pyd` | 70880 | identical |
| `ScreeningWorkbench/_internal/_uuid.pyd` | 28384 | identical |
| `ScreeningWorkbench/_internal/_wmi.pyd` | 40160 | identical |
| `ScreeningWorkbench/_internal/_zstd.pyd` | 503520 | identical |
| `ScreeningWorkbench/_internal/api-ms-win-core-console-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-datetime-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-debug-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-errorhandling-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-fibers-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-fibers-l1-1-1.dll` | 22872 | added |
| `ScreeningWorkbench/_internal/api-ms-win-core-file-l1-1-0.dll` | 27008 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-file-l1-2-0.dll` | 22888 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-file-l2-1-0.dll` | 22912 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-handle-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-heap-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-interlocked-l1-1-0.dll` | 22888 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-kernel32-legacy-l1-1-1.dll` | 22888 | added |
| `ScreeningWorkbench/_internal/api-ms-win-core-libraryloader-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-localization-l1-2-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-memory-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-namedpipe-l1-1-0.dll` | 22888 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-processenvironment-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-processthreads-l1-1-0.dll` | 22912 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-processthreads-l1-1-1.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-profile-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-rtlsupport-l1-1-0.dll` | 22888 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-string-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-synch-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-synch-l1-2-0.dll` | 22888 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-sysinfo-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-sysinfo-l1-2-0.dll` | 22912 | added |
| `ScreeningWorkbench/_internal/api-ms-win-core-timezone-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-core-util-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-conio-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-convert-l1-1-0.dll` | 26992 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-environment-l1-1-0.dll` | 22912 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-filesystem-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-heap-l1-1-0.dll` | 22872 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-locale-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-math-l1-1-0.dll` | 31064 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-private-l1-1-0.dll` | 76120 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-process-l1-1-0.dll` | 22896 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-runtime-l1-1-0.dll` | 26968 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-stdio-l1-1-0.dll` | 26968 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-string-l1-1-0.dll` | 26968 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-time-l1-1-0.dll` | 22912 | modified |
| `ScreeningWorkbench/_internal/api-ms-win-crt-utility-l1-1-0.dll` | 22912 | modified |
| `ScreeningWorkbench/_internal/base_library.zip` | 1394319 | modified |
| `ScreeningWorkbench/_internal/libcrypto-3.dll` | 6242552 | identical |
| `ScreeningWorkbench/_internal/libffi-8.dll` | 39696 | identical |
| `ScreeningWorkbench/_internal/libssl-3.dll` | 1329912 | identical |
| `ScreeningWorkbench/_internal/libtommath.dll` | 81408 | identical |
| `ScreeningWorkbench/_internal/pyexpat.pyd` | 222944 | identical |
| `ScreeningWorkbench/_internal/python314.dll` | 6785760 | identical |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleMono-Bold.ttf` | 53544 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleMono-Italic.ttf` | 54248 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleMono-Regular.ttf` | 52020 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleNext-Bold.ttf` | 66792 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleNext-Italic.ttf` | 69812 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/AtkinsonHyperlegibleNext-Regular.ttf` | 65068 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/Newsreader16pt-Bold.ttf` | 134632 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/Newsreader16pt-Italic.ttf` | 131332 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/Newsreader16pt-Medium.ttf` | 136428 | added |
| `ScreeningWorkbench/_internal/screening_workbench/fonts/Newsreader16pt-Regular.ttf` | 121824 | added |
| `ScreeningWorkbench/_internal/select.pyd` | 33504 | identical |
| `ScreeningWorkbench/_internal/sqlite3.dll` | 1584864 | identical |
| `ScreeningWorkbench/_internal/tcl90.dll` | 3369299 | identical |
| `ScreeningWorkbench/_internal/tcl9tk90.dll` | 2138360 | identical |
| `ScreeningWorkbench/_internal/ucrtbase.dll` | 1362264 | modified |
| `ScreeningWorkbench/_internal/unicodedata.pyd` | 759008 | identical |
| `ScreeningWorkbench/_internal/VCRUNTIME140.dll` | 178616 | identical |
| `ScreeningWorkbench/_internal/VCRUNTIME140_1.dll` | 50112 | identical |
| `ScreeningWorkbench/_internal/zlib1.dll` | 116960 | identical |
| `ScreeningWorkbench/notices/AtkinsonHyperlegibleMono-OFL.txt` | 4529 | package-only |
| `ScreeningWorkbench/notices/AtkinsonHyperlegibleNext-OFL.txt` | 4524 | package-only |
| `ScreeningWorkbench/notices/bzip2-LICENSE.txt` | 1938 | package-only |
| `ScreeningWorkbench/notices/CPython-LICENSE.txt` | 35500 | package-only |
| `ScreeningWorkbench/notices/Expat-COPYING.txt` | 1165 | package-only |
| `ScreeningWorkbench/notices/libffi-LICENSE.txt` | 1153 | package-only |
| `ScreeningWorkbench/notices/LibTomMath-LICENSE.txt` | 1283 | package-only |
| `ScreeningWorkbench/notices/Newsreader-OFL.txt` | 4486 | package-only |
| `ScreeningWorkbench/notices/OpenSSL-LICENSE.txt` | 10352 | package-only |
| `ScreeningWorkbench/notices/Screening-Workbench-LICENSE.txt` | 1088 | package-only |
| `ScreeningWorkbench/notices/SQLite-NOTICE.txt` | 420 | package-only |
| `ScreeningWorkbench/notices/Tcl-license.terms` | 2295 | package-only |
| `ScreeningWorkbench/notices/Tk-license.terms` | 2307 | package-only |
| `ScreeningWorkbench/notices/XZ-COPYING.txt` | 2840 | package-only |
| `ScreeningWorkbench/notices/zlib-LICENSE.md` | 886 | package-only |
| `ScreeningWorkbench/notices/Zstandard-LICENSE.txt` | 1579 | package-only |
| `ScreeningWorkbench/ScreeningWorkbench.exe` | 2656436 | package-only |

</details>

## Owner ruling follow-through — Step 0 WAL fact-find (2026-10-22)

Only the database and sidecar copies were opened. The source originals were not opened by SQLite or the application. The app source resolves its default project database as `%USERPROFILE%\screening-workbench-project.sqlite`.

The three source files were copied to the fresh scratch folder `C:\Users\nater\Documents\Codex\phase1-wal-fact-find-20261022-ebe6e81a2c2d41669a27e692e2ccd4f7`. The source file sizes and UTC timestamps were unchanged during copying and remained unchanged after inspection:

| Source file | Size before and after (bytes) | LastWriteTimeUtc before and after |
|---|---:|---|
| `C:\Users\nater\screening-workbench-project.sqlite` | 4,096 | `2026-10-12T23:58:09.7793153Z` |
| `C:\Users\nater\screening-workbench-project.sqlite-wal` | 741,632 | `2026-10-22T23:55:50.4983760Z` |
| `C:\Users\nater\screening-workbench-project.sqlite-shm` | 32,768 | `2026-10-22T23:26:47.5141939Z` |

SQLite opened only the scratch copy, with `query_only=ON`. It reported WAL journal mode and `integrity_check: ok`. The date-filtered import inspection found exactly one batch for 2026-10-22: source `synthetic-smoke.csv`, imported at `2026-10-22T23:55:50.494833Z`, `records_read=1`, `records_skipped=0`, and one occurrence. This matches the expected one-record synthetic import. The row title is **Synthetic smoke screen record**; occurrence ID is `occ_9ae01857f3174b9898f1b4f32ff7bfaf` (locator `row 1`).

No remediation, cleanup, or write to the original database or sidecars was performed, and the app was not opened against the real profile. Per the explicit Step 0 instruction to report and stop, Steps 1–3 have not been performed in this follow-through. No commit or push was made.

## Data-incident remediation attempt — stopped before original-file changes (2026-10-22)

### A1 — scratch-copy before inventory

Inventory was taken from the existing Step 0 scratch copy only. Full-text decisions are counted as `report_retrievals` rows with a non-null `full_text_outcome`.

| Inventory item | Before count |
|---|---:|
| Import batches — `synthetic-smoke.csv` | 1 |
| Total import batches | 1 |
| Occurrences | 1 |
| Studies | 0 |
| Screening votes | 0 |
| Full-text decisions | 0 |

The single batch has `records_read=1`, `records_skipped=0`; its occurrence is `occ_9ae01857f3174b9898f1b4f32ff7bfaf`, titled **Synthetic smoke screen record**.

### App-closed precondition

The required host-process confirmation could not be established in this execution environment. `Get-CimInstance Win32_Process` was denied access, `tasklist` failed with an authentication error, and the available `Get-Process` view exposed only three sandbox-visible processes with no Screening Workbench process name or window title. Since that view is not a reliable inventory of the host desktop, app closure remains unconfirmed. No backup or operation against the originals was attempted.

### A3 — copy-only deletion pre-checks

| Check | Result | Evidence |
|---|---|---|
| (a) Exactly one batch named `synthetic-smoke.csv` | PASS | One batch; `records_read=1`, `records_skipped=0` |
| (b) Exactly one occurrence, with the expected ID | PASS | One occurrence: `occ_9ae01857f3174b9898f1b4f32ff7bfaf` |
| (c) Zero screening votes and full-text decisions; zero other references | **FAIL** | Votes: 0; full-text decisions: 0. One `events.payload_json` row also references the occurrence: event `evt_62f46c57d34748388eedc832d3d551a7`, type `import.csv.committed`, at `2026-10-22T23:55:50.494833Z`. The expected `occurrence_fields` child row is present. No other foreign-key references to the occurrence were found. |
| (d) Linked study has no other occurrences | N/A — no study linked | The scratch database contains 0 studies and no reports or study links for the occurrence. |

All A3 conditions must hold before remediation. Because (c) failed, no deletion was authorized by the stated pre-check gate. The event-log reference remains in the scratch copy and requires Nate's ruling on whether the pre-check can be amended and what treatment is permitted.

### A2, A4, A5 and Part B — not performed

The requested backup directory `C:\Users\nater\Documents\Chaff\backups\profile-db-pre-remediation-20221022\` was not created. The original database, WAL, and SHM were not opened by SQLite, altered, deleted, moved, or copied in this attempt. No delete transaction, checkpoint, post-delete inventory, or isolated-package smoke was run. The Step 1 record corrections, gate-passed status, commit, and push were not performed. No commit or push was made.


## Owner-ruling close-out — data incident and provenance (2026-10-22)

The owner rulings in the latest follow-through supersede earlier blocked-attempt
notes in this report. Prepared by Codex as builder/gate agent; Cinder is the
reviewer. The application was confirmed closed by Nate; no process check was
required.

### Part A — profile data incident

- **A1 baseline inventory (scratch copy):** one import batch from
  `synthetic-smoke.csv` (`batch_8d53698d9e224ee586058d4e8794bfb0`, one record
  read, zero skipped); one occurrence,
  `occ_9ae01857f3174b9898f1b4f32ff7bfaf`, title “Synthetic smoke screen
  record,” locator row 1; zero studies, zero screening votes, zero full-text
  decisions, and two event-log rows.
- **A2 backup:** before changing the original database, byte-for-byte copies
  were written to
  `C:\Users\nater\Documents\Chaff\backups\profile-db-pre-remediation-20261022\`.
  Each copied file's size and SHA-256 matched its source at backup time:

  | File | Bytes | SHA-256 |
  |---|---:|---|
  | `screening-workbench-project.sqlite` | 4,096 | `0ab48b25cba617ed3a4acca0161813b314c095ef63544bb4af60769eb1012977` |
  | `screening-workbench-project.sqlite-wal` | 741,632 | `00c87449d6eb9caa8c3441278358e2bdfbd68767c9552e56a58eb1269d6f69c5` |
  | `screening-workbench-project.sqlite-shm` | 32,768 | `623de7023820cb1565030070b4eb190fd14c472200ebb995c7a2799f5c633ad2` |

- **A3 pre-checks under the amended owner ruling:** the only batch was
  `synthetic-smoke.csv`, with exactly one occurrence having the expected ID;
  no study row existed; there were no votes, full-text decisions, or other
  relational references. The `import.csv.committed` event
  `evt_62f46c57d34748388eedc832d3d551a7` was retained as audit history and,
  by owner ruling, did not block deletion.
- **A4 transaction:** with the app closed and after backup verification, one
  transaction against the original database deleted the occurrence's one
  `occurrence_fields` child row, the occurrence, and its import batch. No
  study row existed. No event-log row was modified, deleted, or scrubbed.
  `PRAGMA wal_checkpoint(TRUNCATE)` returned `(0, 0, 0)` and
  `PRAGMA integrity_check` returned `ok`; the foreign-key check was clean.
- **A5 post-check:** batches 0 (one fewer), occurrences 0 (one fewer), studies
  0, votes 0, and full-text decisions 0; event-log count remained 2 and the
  retained import event remained present. Integrity check returned `ok` and
  the foreign-key check was clean. The real database is 262,144 bytes; after
  checkpoint and close, the WAL and SHM files are absent (0 bytes). These
  values are the post-remediation baseline for the later isolated smoke
  comparison. The database was not opened through the GUI app.

### Part B — owner correction to runtime entitlement record

The shipped 1.0.0 and exact 2.0.0 ZIPs contain byte-identical CRT files:
`VCRUNTIME140.dll` version 14.51.36247.0, SHA-256
`d1f4225df2cd877dbf130d5668a021dce3f94118455ff5ec952061c30afc9ce7`, and
`VCRUNTIME140_1.dll` version 14.51.36247.0, SHA-256
`a7146c08f89fe5b04541ab507cdb59ff7b44534d4ba3c668a426c6450a03434e`.
The 14.44.35211.0 value recorded in the earlier v1 attestation is corrected
by the dated addendum in `docs/release-gate-1.0.0.md`.

Microsoft redistribution entitlement carries from the v1.0.0 gate (item 3,
closed 2026-10-21; VS Community 2022 17.14.36 attestation): the
entitlement-bearing file set is unchanged.

The remaining runtime delta is 42 modified and 3 added files: API-set
`api-ms-win-*` forwarders, `ucrtbase.dll`, and `base_library.zip`. Per the
owner ruling, this is build-host Windows SDK/UCRT variance; UCRT redistribution
rests on the Windows SDK basis recorded in the v1 provenance memo. There is no
other runtime change. The full per-file delta and package manifest remain in
the runtime provenance section above.


## Exact ZIP smoke attempt after profile remediation (2026-10-22)

The exact ZIP was freshly extracted outside the repository to
C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\extracted.
Its identity was rechecked before extraction: 17,398,639 bytes, SHA-256
15a30f396e00f7367485181f140601899cb1b8ba5ff074ee52db64c9243f49a7. Only
synthetic fixtures were created in the scratch directory:
fixtures\synthetic-smoke.csv and fixtures\synthetic-smoke.pdf.

| Smoke step | Result | Observation |
|---|---|---|
| Fresh extraction of exact ZIP | PASS | Extracted to the scratch path above; the packaged EXE was present. |
| Light profile path precheck before import | PASS | os.path.expanduser("~") resolved to ...\profiles\light; expected project DB was ...\profiles\light\screening-workbench-project.sqlite; settings were ...\profiles\light\AppData\Roaming\Screening Workbench\settings.json. All are inside the disposable profile. |
| Light packaged-app launch | FAIL | Start-Process returned PID 43156, but the process had exited by the follow-up check. Computer Use listed no Screening Workbench window. No project DB or settings file was created and no startup diagnostic was surfaced. |
| Night profile path precheck before import | PASS | os.path.expanduser("~") resolved to ...\profiles\night; expected project DB was ...\profiles\night\screening-workbench-project.sqlite; settings were ...\profiles\night\AppData\Roaming\Screening Workbench\settings.json. All are inside the separate disposable profile. |
| Night packaged-app launch | FAIL | Start-Process returned PID 6340, but the process had exited by the follow-up check. Computer Use listed no Screening Workbench window. No project DB or settings file was created and no startup diagnostic was surfaced. |
| Create project and import synthetic CSV | NOT RUN | Blocked by the failed application launches; no import was attempted. |
| Screening Include, Maybe, and Exclude-with-reason votes | NOT RUN | Blocked by the failed application launches. |
| PRISMA open and export | NOT RUN | Blocked by the failed application launches. |
| Full-text Include/promote, decision with reason, attach and open synthetic PDF | NOT RUN | Blocked by the failed application launches. |
| View Theme Night/back to Light and Reduce motion toggle | NOT RUN | Blocked by the failed application launches. |
| Light/Night Screening screenshots at 1296 x 839 | NOT CAPTURED | No accepted screenshots were produced; package-screening-light.png and package-screening-night.png are absent. |
| Real-profile DB/WAL/SHM metadata after attempted smoke | PASS | Compared with the post-remediation baseline. DB remains 262,144 bytes with timestamp 2026-10-23T01:50:13.4073668Z; WAL and SHM remain absent. All three metadata comparisons are unchanged. |

The smoke stopped at the failed application launch in each disposable profile.
No code was changed to address the launch failure, no synthetic import was
attempted, and the GUI was never opened against the real profile. The real
profile database and sidecars remain at the post-remediation state described
above.

### Current gate disposition

**BLOCKED; not release-ready.** The owner ruling closes the CRT entitlement
carry-over record, and the independent full-suite results remain 437/437 on
both runtimes, but the exact-ZIP application smoke and required screenshots
did not pass. Do not represent this candidate as gate-passed, merge to v2,
mirror it, tag it, or publish it. Nate's latest direct instruction authorizes
committing and pushing this blocked branch for Cinder's post-push review; that
does not close the smoke gate or authorize any of those later release actions.


## Packaged launch diagnosis (2026-10-22)

**Scope:** exact candidate ZIP 17,398,639 bytes, SHA-256
`15a30f396e00f7367485181f140601899cb1b8ba5ff074ee52db64c9243f49a7`;
build commit `5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7`. This is a
diagnosis-only record. No application code or build artifact changed, and the
gate status remains **BLOCKED**.

### D1 — launch setup comparison

| Aspect | Earlier successful launch | Post-remediation failed launch |
|---|---|---|
| Candidate path | `C:\Users\nater\Documents\Codex\Screening-Workbench-v2.0.0-smoke-20261022\extracted\ScreeningWorkbench\ScreeningWorkbench.exe` | `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\extracted\ScreeningWorkbench\ScreeningWorkbench.exe`; the extracted ZIP was verified at the identity above. |
| Disposable profile | `C:\Users\nater\Documents\Codex\Screening-Workbench-v2.0.0-smoke-20261022\profile-light` | Separate `...\r3\profiles\light` and `...\r3\profiles\night` profiles. The earlier run tested Light only; the later run tested Light and Night. |
| `USERPROFILE` | `C:\Users\nater\Documents\Codex\Screening-Workbench-v2.0.0-smoke-20261022\profile-light` | Light: `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\light`<br>Night: `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\night` |
| `HOMEDRIVE` / `HOMEPATH` | `C:` / `\Users\nater\Documents\Codex\Screening-Workbench-v2.0.0-smoke-20261022\profile-light` | Light: `C:` / `\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\light`<br>Night: `C:` / `\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\night` |
| `APPDATA` | `C:\Users\nater\Documents\Codex\Screening-Workbench-v2.0.0-smoke-20261022\profile-light\AppData\Roaming` | Light: `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\light\AppData\Roaming`<br>Night: `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\night\AppData\Roaming` |
| `LOCALAPPDATA` | `C:\Users\nater\Documents\Codex\Screening-Workbench-v2.0.0-smoke-20261022\profile-light\AppData\Local` | Light: `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\light\AppData\Local`<br>Night: `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\night\AppData\Local` |
| `SW_SETTINGS_PATH` | `C:\Users\nater\Documents\Codex\Screening-Workbench-v2.0.0-smoke-20261022\profile-light\AppData\Roaming\Screening Workbench\settings.json` | Light: `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\light\AppData\Roaming\Screening Workbench\settings.json`<br>Night: `C:\Users\nater\Documents\Codex\SWB-2.0.0-smoke-exact-20261022-r3\profiles\night\AppData\Roaming\Screening Workbench\settings.json` |
| Theme / motion | `SW_THEME=light`; `SW_REDUCE_MOTION=1`. | `SW_THEME=light` or `night`; the launch command did not explicitly assign `SW_REDUCE_MOTION` (the inherited value was not recorded). |
| `TEMP` / `TMP` | Not assigned by the launch command; inherited from that PowerShell session. Exact values were not recorded. | Also not assigned; inherited values were not recorded. |
| Launch and observation | `Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -PassThru`; the same PowerShell command polled up to 30 times at 100 ms intervals for a main-window handle, then recorded the title, resolved home, and database existence. | The same `Start-Process` pattern returned the PID and ended the command. A separate follow-up check found the PID gone. No in-command wait or window poll was recorded. |
| Observed result | Window title `Screening Workbench -- systematic review screening`; Python home resolved to the disposable profile and the project database existed there. The profile now contains the 4,096-byte database and SQLite `-shm` / `-wal` sidecars; the launch record does not report a settings file. | PIDs 43156 and 6340 were absent by follow-up; no window, database, settings file, or startup diagnostic was reported. |

The setup differences are the different disposable path values, the extra
Night run, the `SW_THEME` value in that run, the earlier explicit
`SW_REDUCE_MOTION=1`, and, most materially, waiting/polling within the launch
command versus returning immediately and checking later. Neither launch
command explicitly changed `TEMP` or `TMP`.

### D2 — direct executable console runs

The exact extracted executable was launched directly from PowerShell with
`.NET System.Diagnostics.Process.Start` (not `Start-Process`), with stdout and
stderr captured. The PowerShell process waited eight seconds. In both runs the
window appeared and remained alive; `CloseMainWindow()` then closed it, and
the process exited with code **0**. No natural early exit was observed.

| Run | Redirects | Console stdout / stderr | Window and files | Exit code |
|---|---|---|---|---:|
| D2(a) | Full home and AppData redirects; `SW_SETTINGS_PATH` omitted. `SW_THEME=light`; session `TEMP` / `TMP` inherited. | Both empty. | Window title `Screening Workbench -- systematic review screening`; disposable project database plus SQLite `-shm` and `-wal` files created. | `0` after `CloseMainWindow()` |
| D2(b) | Full six-variable redirect set including `SW_SETTINGS_PATH`. `SW_THEME=light`; session `TEMP` / `TMP` inherited. | Both empty. | Same visible title and disposable database/sidecars created. | `0` after `CloseMainWindow()` |

### D3 — Windows evidence

Read-only checks covered the Application log from 2026-10-22 18:30 PDT
through 20:52:08 PDT, including the failed-launch interval and these
diagnostic runs. No matching Application Error, Windows Error Reporting, or
SideBySide event named `ScreeningWorkbench.exe` or a bundled CRT/UCRT/API-set
module. `Get-MpThreatDetection` returned no detection or quarantine matching
the executable or `_internal` files. These checks found no OS-reported crash
or Defender action; absence of a matching record does not explain the
process disappearance.

### D4 — source comparison

The final direct console command was run from the repository root with
`PYTHONPATH=src` and `.venv\Scripts\python.exe -m screening_workbench.app`,
under the six-variable disposable redirect set. Its only printed line was:

~~~text
PRELAUNCH PYTHONPATH=src PYTHONHOME=C:\Users\nater\Documents\Codex\SWB-launch-diagnosis-20261022-m\source USERPROFILE=C:\Users\nater\Documents\Codex\SWB-launch-diagnosis-20261022-m\source SW_SETTINGS_PATH=C:\Users\nater\Documents\Codex\SWB-launch-diagnosis-20261022-m\source\AppData\Roaming\Screening Workbench\settings.json
~~~

It printed no traceback or other application output. The process remained
running for at least ten seconds and created the disposable 4,096-byte
database plus 32,768-byte `-shm` and 650,992-byte `-wal` files. The available
app inventory exposed no native window, so the console session was
interrupted with Ctrl+C; the outer PowerShell command returned 1, and the
application's own exit code was not obtained.

A second source launch used `Start-Process` with the same source module,
`PYTHONPATH`, and disposable redirects. It remained alive after six seconds
and created the database and sidecars. Its process main-window title was the
Python executable path, not the Screening Workbench title. Stdout and stderr
files were empty. `CloseMainWindow()` was sent to that process window, no
forced kill was used, and the process exited with `-1073741510`
(`0xC000013A`, console close). This did not verify a visible Tk window or a
normal application-window close.

An initial helper probe had incorrectly replaced session `TEMP` / `TMP` with
`C:\Windows\Temp`; it emitted `warning: Failed to set cwd to temp dir`.
That probe was not treated as D4 evidence. The reported D2 and corrected D5
runs preserve session defaults except where D5(b) explicitly sets a
disposable temp directory.

### D5 — environment bisection

Each Start-Process probe used a fresh disposable profile and stayed in the
same PowerShell command while checking the window. No synthetic import was
performed.

| Variant | Change from full redirect set | Result |
|---|---|---|
| D5(a) | Remove `SW_SETTINGS_PATH`; leave `APPDATA` and `LOCALAPPDATA` redirected. Settings therefore use the `%APPDATA%` fallback. | **Launch pass.** Visible Screening Workbench title; remained alive through the four-second observation; closed via `CloseMainWindow()`; exit code `0`. Created a 4,096-byte database and SQLite sidecars only in `...\SWB-launch-diagnosis-20261022-f\D5A`. |
| D5(b) | Full redirect set plus `TEMP` and `TMP` set to the pre-created `...\SWB-launch-diagnosis-20261022-f\D5B\Temp` directory. | **Launch pass.** Same visible title and orderly close, exit code `0`; database and sidecars only in the D5B profile. |
| D5(c) | Redirect `APPDATA`, `LOCALAPPDATA`, and `SW_SETTINGS_PATH`; do not reassign the home variables for this variant. | **Launch pass.** Same visible title and orderly close, exit code `0`; database and sidecars only in the D5C profile. To keep this test disposable, the diagnostic PowerShell session's inherited home defaults were seeded to D5C before the variant; this does not test the actual desktop user's real home defaults. |
| Supplemental motion check | Full redirect set with `SW_REDUCE_MOTION=1`, matching the earlier successful run's explicit motion setting. | **Launch pass.** Same visible title and orderly close, exit code `0`; database and sidecars only in the D5D profile. |

D5 profiles are under
`C:\Users\nater\Documents\Codex\SWB-launch-diagnosis-20261022-f`,
`...\20261022-g`, and `...\20261022-h`. All reported paths resolved inside
those disposable roots. No launch used the real profile or its database.

### D6 — assessment and proposed fix path

**Root cause not established.** The best-supported candidate is a launch
harness/process-lifetime issue: the failed commands returned immediately
after `Start-Process`, then checked the PID in another command; the earlier
successful run polled for a window and database before its PowerShell command
ended. In this pass, the exact ZIP opened and stayed alive when launched
directly or via `Start-Process` while the same PowerShell command waited.
D5(a), D5(b), and D5(c) all opened under their tested environments, with and
without an explicit settings path and with session or disposable `TEMP` /
`TMP`. A separate no-wait reproduction returned PID 21532, then a new
PowerShell check found no process, database, or settings file. The available
evidence is consistent with the command-session boundary ending the child
before initialization, but the original PIDs have no captured exit codes and
the OS termination mechanism was not recorded. D4 also did not establish a
visible source window, so it cannot provide a conclusive source-versus-package
comparison.

Proposed next path: repeat the exact-ZIP smoke from one persistent interactive
PowerShell session; keep the launcher session alive while polling for a real
main window and database, then perform the synthetic workflows before
returning from that session. Capture a process exit code and stdout/stderr
only if it exits before window readiness. Update the packaging procedure to
keep launch and readiness checks in the same session. No application-code fix
is justified by this diagnosis alone.

Gate status remains **BLOCKED**. This section does not close the exact-ZIP
smoke or screenshot requirements and does not authorize a merge or release.

## Exact ZIP smoke rerun — BLOCKED (2026-10-22)

**Artifact:** `Screening-Workbench-2.0.0-windows-x64.zip`, 17,398,639 bytes, SHA-256 `15a30f396e00f7367485181f140601899cb1b8ba5ff074ee52db64c9243f49a7`; source build commit `5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7`. The archive was freshly extracted to `C:\Users\nater\Documents\Codex\SWB-exact-zip-smoke-rerun-20261022-c6d27eb5e57940d7a7878d19039499bc\extracted\ScreeningWorkbench`.

The earlier failed attempt launched with `Start-Process`, returned from the launching command, then checked the PID from a later command. This rerun kept one persistent PowerShell session per disposable profile for launch, readiness polling, UI workflows, capture, and close. It used the full six-variable redirect set (`USERPROFILE`, `HOMEDRIVE`, `HOMEPATH`, `APPDATA`, `LOCALAPPDATA`, `SW_SETTINGS_PATH`), profile-local `TEMP` / `TMP`, and `SW_REDUCE_MOTION=1`; `SW_THEME=light` and `SW_THEME=night` were set for the respective profiles. The project database and settings paths were confirmed inside each disposable profile before any import. This matches the launch/readiness harness that passed D2/D5. The Night launcher remained open to await app exit; the window close input later failed, so its exit code was not obtained.

### Light profile

Disposable root: `C:\Users\nater\Documents\Codex\SWB-exact-zip-smoke-rerun-20261022-c6d27eb5e57940d7a7878d19039499bc\profiles\light-rerun`. Resolved project database: `...\profiles\light-rerun\screening-workbench-project.sqlite` (confirmed inside the profile before import).

| Step | Result | Observation |
|---|---|---|
| Launch and readiness | PASS | Exact window title `Screening Workbench -- systematic review screening`; disposable database created under the profile. |
| Create project and import synthetic CSV | PASS | Three synthetic rows read, zero duplicates merged, one candidate for review. |
| Screening Include / Maybe / Exclude with reason | PASS | All three synthetic records received the requested votes; Exclude used `Wrong population`. |
| PRISMA open and export | PASS | PRISMA opened and export completed in the disposable profile. |
| Full-text decision with reason | PASS | Full-text Exclude saved with `Wrong population`. |
| Attach synthetic PDF | PASS | 599-byte synthetic PDF attached. |
| Open attached PDF | FAIL | `Open selected` did not surface a viewer after two attempts; the app stayed on Full-text. |
| Theme round-trip | PASS | Light → Night Stacks → Light menu changes completed. |
| Reduce motion toggle | PASS | Toggled from enabled to disabled. |
| Screening capture | PASS | `release-2.0.0/evidence/package-screening-light.png`, 1296 × 839 pixels; synthetic data only. |
| Close and process exit | PASS | Closed via the app window; persistent launcher returned exit code `0`; captured executable stdout/stderr were empty. |

### Night profile

Disposable root: `C:\Users\nater\Documents\Codex\SWB-exact-zip-smoke-rerun-20261022-c6d27eb5e57940d7a7878d19039499bc\profiles\night-rerun`. Resolved project database: `...\profiles\night-rerun\screening-workbench-project.sqlite`; settings path was under `...\profiles\night-rerun\AppData\Roaming\Screening Workbench\settings.json`. Both paths were confirmed inside the profile before import.

| Step | Result | Observation |
|---|---|---|
| Launch and readiness | PASS | Exact window title `Screening Workbench -- systematic review screening`; database existed at the confirmed disposable path. |
| Create project and import synthetic CSV | PASS | Project `smoke rerun night`; three synthetic rows read, zero duplicates merged, one candidate for review, zero skipped. |
| Screening Include / Maybe / Exclude with reason | PASS | All three synthetic records received the requested votes; Exclude used `Wrong population`. |
| PRISMA open | PASS | PRISMA opened; graph-paper preview was visible. |
| PRISMA export | PASS after retry | First destination selection ended at `C:\Users`; export reported permission denied for `manifest.json.screening-workbench-export-tmp` and said no files there changed. Retried to the Night disposable profile root; export completed and wrote five files. |
| Full-text decision with reason | PASS | Created a full-text report from the included synthetic Screening record; saved Exclude with `Wrong population`. |
| Attach synthetic PDF | PASS | `swb-smoke-rerun-synthetic.pdf` (599 bytes) appeared in Attached PDF. |
| Open attached PDF | FAIL | `Open selected` produced no viewer window; the app remained on the Full-text screen. |
| Theme round-trip | PASS | Night Stacks → Card Catalogue (light) → Night Stacks; the status bar confirmed each menu selection and noted restart is needed for the palette to apply to existing widgets. |
| Reduce motion toggle | PASS | The checked View → Reduce motion item was toggled off. |
| Screening capture | FAIL | No acceptable Night Screening capture was produced. After restoring the window, the capture/input state was clipped; the computer-use API returned `foreground window did not report a process id` for follow-up input. No Night screenshot was staged. |
| Close and process exit | FAIL | At the close attempt the app window remained listed. `Alt+F4` returned `foreground window did not report a process id`; the persistent launcher was still waiting, and no exit code was available. A later process snapshot (2026-10-23 05:31 UTC) found no process named Screening Workbench and no top-level app window, but launcher session 82807 still had not returned an exit code. |

### Real-profile metadata check

After both profile runs, read-only file metadata matched the post-remediation baseline: `C:\Users\nater\screening-workbench-project.sqlite` was 262,144 bytes; `-wal` and `-shm` were absent. The metadata check was at 2026-10-22 18:50:13 PDT (2026-10-23 01:50:13 UTC). No GUI app was opened against the real profile.

### Gate decision

The gate remains **BLOCKED**. The synthetic workflows completed except for opening the attached PDF in both profiles; Night has no accepted Screening capture and did not close, so its process exit code remains unknown. The Light capture is the only current accepted palette capture. Do not mark gate-passed. The documentation commit and push for this record do not clear the launch diagnosis, PDF-open, Night-capture, or independent review gates.

## Final smoke completion pass — BLOCKED (2026-10-23)

**Artifact:** `Screening-Workbench-2.0.0-windows-x64.zip`, 17,398,639 bytes, SHA-256 `15a30f396e00f7367485181f140601899cb1b8ba5ff074ee52db64c9243f49a7`; build commit `5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7`. The same extracted executable was used from `C:\Users\nater\Documents\Codex\SWB-exact-zip-smoke-rerun-20261022-c6d27eb5e57940d7a7878d19039499bc\extracted\ScreeningWorkbench`. Both runs used fresh disposable profiles under `C:\Users\nater\Documents\Codex\SWB-final-smoke-20261023-2dd9b550`; no real profile or database was opened.

### Part 1 — PDF-open probe

The disposable `pdf-probe` profile was configured before launch with the full six-variable redirect set, profile-local `TEMP` / `TMP`, `SW_THEME=light`, and `SW_REDUCE_MOTION=1`. The project database resolved to `...\profiles\pdf-probe\screening-workbench-project.sqlite`; settings resolved to `...\profiles\pdf-probe\AppData\Roaming\Screening Workbench\settings.json`; Python `os.path.expanduser('~')` resolved to the profile. All were confirmed before any import. The persistent PowerShell launch session reported PID 27000, exact title `Screening Workbench -- systematic review screening`, and a 4,096-byte disposable database.

| Step | Result | Observation |
|---|---|---|
| Snapshot process names before launch | PASS | `conhost, Idle, powershell, pwsh`. |
| Import synthetic fixture; create one Full-text report; attach PDF | NOT RUN | The computer-use input surface rejected menu input before a project could be created or a fixture imported. |
| Click `Open selected` and snapshot process/window changes | NOT RUN | The button was not reached. Initial Project-menu click failed with `foreground window did not report a process id`; after refreshing the target window and activation, the retry click returned the same error. A fresh window capture followed by `Alt+P` also returned the same error. No app-button before/after process snapshot exists. |
| Independent Python `os.startfile()` on the synthetic fixture PDF | PASS (call returned) | `.venv\\Scripts\\python.exe -c "import os; os.startfile(r'C:\\Users\\nater\\Documents\\Chaff\\release-2.0.0\\evidence\\synthetic-smoke.pdf')"` returned exit code `0` and empty stdout. |
| Direct-probe process-name difference | NO CHANGE | Before: `conhost, Idle, powershell, pwsh, ScreeningWorkbench`. After: `conhost, Idle, powershell, pwsh, ScreeningWorkbench`. Added: `[]`; removed: `[]`. The PowerShell window snapshot before and after contained only PID 27000 / the Screening Workbench title. The Computer Use top-level window IDs before and after were unchanged; no new top-level window was listed. |

The attachment handler in source (`src/screening_workbench/app.py`, line 3536) calls `os.startfile(tmp_path)` after writing the attachment to a temporary file, but the app's `Open selected` callback was not exercised in this run. The independent direct fixture call returned successfully but produced no observable process or top-level-window change. **The evidence does not establish that `Open selected` spawned a viewer process; that step remains failed/unverified and is not passed.**

### Part 2 — Night tail

The fresh `night-tail` profile used the full six-variable redirect set, profile-local `TEMP` / `TMP`, `SW_THEME=night`, and `SW_REDUCE_MOTION=1`. Before import, `os.path.expanduser('~')`, the project database `...\profiles\night-tail\screening-workbench-project.sqlite`, and the settings path `...\profiles\night-tail\AppData\Roaming\Screening Workbench\settings.json` were confirmed inside the disposable profile. Launch readiness passed: PID 21272, exact main-window title, database size 4,096 bytes, and target window handle 272961604.

| Step | Result | Observation |
|---|---|---|
| Launch/readiness and pre-import path confirmation | PASS | All resolved paths were inside the new Night profile. |
| Import synthetic fixture and complete three Screening votes | NOT RUN | The window was listed, but `get_window_state` returned `foreground window did not report a process id` before any UI action. |
| Recovery after UI surface failure | FAIL | Waited 2 seconds, refreshed `list_windows`, reselected the unique Night handle, and retried state capture; the same error returned. |
| Night Screening capture at 1296 × 839 | NOT CAPTURED | No fixture was imported and no valid queue screen could be captured; `package-screening-night.png` was not created or replaced. |
| Close through the Night app window and process exit | FAIL / UNKNOWN | After the wait, the one Alt+F4 close retry returned `foreground window did not report a process id`. A refreshed window list still contained both packaged app windows (IDs 9504954 and 272961604). The launch session remained waiting and no process exit code was returned. |

No code or build artifact was changed. The final smoke remains **BLOCKED**: the app's PDF-open callback did not run, its viewer-process outcome is unverified, and the Night import/votes/capture/close could not be completed because the Computer Use input/state surface failed. Do not mark the release gate gate-passed. This record does not authorize merge, mirror, tag, or publish.

## Owner desktop close-out and profile cleanup — GATE PASSED (2026-10-23)

### Gate disposition

Cinder rules the 2.0.0 gate **GATE PASSED (2026-10-23)** on the combined automated, source-inspection, and owner-desktop evidence below. The packaged artifact remains the exact ZIP identified in this report. This gate disposition does not authorize merging to `v2`, the public mirror, tagging, or publishing.

### Owner desktop attestation

On 2026-10-23, the owner ran the packaged build on his own desktop against the real profile. **Open selected** opened the attached synthetic PDF in the Chrome PDF viewer (the machine default); the owner captured the Screening screen in Night Stacks; and the app closed normally.

This completes the evidence chain with:

| Evidence | Recorded source | Contribution |
|---|---|---|
| Automated Light full pass, exit code 0 | Commit `9ae3b77` (`Document exact ZIP smoke rerun`) | Full Light workflow and clean close on the exact package. |
| Packaged launch diagnosis D1–D6 | Commit `11a97d6` (`docs: record v2.0.0 packaged launch diagnosis`) | Identified the persistent-session launch requirement and recorded environment tests. |
| Open-selected handler source read | `src/screening_workbench/app.py`, approximately lines 3512–3538 | Verified attachment bytes into a temporary copy, calls `os.startfile`, and shows a modal on `OSError`. |
| Computer Use surface failure | Commit `3e350e2` (`Record final smoke completion attempt`) | Recorded the automation surface limitation for PDF-window and Night-tail interaction. |
| Owner desktop check | Owner attestation dated 2026-10-23 | Confirmed the default Chrome PDF viewer opened, Night Screening was captured, and the app closed normally. |

The owner capture was present in the repository evidence directory as `release-2.0.0/evidence/Screenshot 2026-10-23 093315.png`; the requested `package-screening-night.png` target did not yet exist. The timestamped image shows the Night Stacks Screening window and synthetic project content. It was copied unchanged to `release-2.0.0/evidence/package-screening-night.png`.

| Capture | Dimensions | Bytes | SHA-256 |
|---|---:|---:|---|
| `release-2.0.0/evidence/package-screening-light.png` | 1296 × 839 | 401,696 | Existing accepted Light capture (see exact-ZIP smoke rerun entry above). |
| `release-2.0.0/evidence/package-screening-night.png` | 1283 × 829 | 73,753 | `7c0124b765bcd19e5cdae89941cc048c87de9c7a40c6310d2d1c0a12056cef30` |

### Real-profile gate-check cleanup

The owner confirmed that the application was closed. A process scan found no Screening Workbench process, and exclusive-open checks passed for the database and its existing sidecars before backup. Inventory was read-only. It identified one `synthetic-smoke.csv` batch (`batch_404613beddbb4eefb63c30e432d5d3aa`), four occurrences, four `occurrence_fields` rows, four screening votes, one report, one pending retrieval row, one attachment metadata row, and one import idempotency row. There were no studies. The report retrieval was `pending` with `full_text_outcome` NULL, so there was no persisted full-text outcome before cleanup; the report and its retrieval state were removed together.

| Profile table/count | Before | After |
|---|---:|---:|
| Import batches | 1 | 0 |
| Occurrences | 4 | 0 |
| Occurrence fields | 4 | 0 |
| Screening votes | 4 | 0 |
| Studies | 0 | 0 |
| Reports | 1 | 0 |
| Report retrieval rows | 1 | 0 |
| Persisted full-text outcomes | 0 | 0 |
| Report attachment rows | 1 | 0 |
| Import idempotency operations | 1 | 0 |
| Report/occurrence links | 1 | 0 |
| Report progressions | 1 | 0 |
| Event-log rows | 12 | 12 |

Before changing the database, the database and both existing sidecars were copied byte-for-byte to `C:\Users\nater\Documents\Chaff\backups\profile-db-pre-gatecheck-cleanup-20261023\`. Each copy matched its source in both size and SHA-256:

| Backup file | Bytes | SHA-256 |
|---|---:|---|
| `screening-workbench-project.sqlite` | 262,144 | `fff15de5c3c939b850c74326443758cdfea02699117ce5cf353e411bfddeaf61` |
| `screening-workbench-project.sqlite-wal` | 317,272 | `097c21784ed57e4c4b08111a77a85fd686ae6961eca34394b44bdecdab2d0ecb` |
| `screening-workbench-project.sqlite-shm` | 32,768 | `ce9616e912545d36c169439803ef2720c44b7997777466d041cf58451e6de5a3` |

The first delete attempt encountered a foreign-key constraint while the report retrieval still had its attachment child. That transaction was rolled back; no rows were committed or removed. SQLite then checkpointed the pre-existing WAL on connection close. After correcting the child-delete order, the effective cleanup completed in one committed SQLite transaction: attachment, report links/progression/retrieval, votes and occurrence fields, report, occurrences, batch, and its matching import idempotency row were deleted. No event-log row was updated, deleted, or scrubbed. The event rows' SHA-256 remained `3f0a6b5eb8899e009e8bf7c89016610515e9500b10e6cb62287972d63283e4f0` before and after cleanup.

The attachment file `C:\Users\nater\attachments\d3ae41c965a328a6034ddbe9c0f839fff6c7c51170ec990dd2947ee5153e2956.pdf` was 599 bytes and matched the attachment row's recorded SHA-256. After deleting the row, zero attachment rows referenced that hash, so the synthetic PDF file was deleted. The audit event describing its attachment remains in the event log.

`PRAGMA wal_checkpoint(TRUNCATE)` returned `(0, 0, 0)` and `PRAGMA integrity_check` returned `ok`. Final profile files: database 274,432 bytes; WAL absent; SHM absent. The post-cleanup counts match the post-remediation baseline for batches, occurrences, studies, screening votes, and full-text decisions; event-log count is 12. The backup remains at the path above and is not part of this commit.

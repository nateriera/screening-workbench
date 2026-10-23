# Windows packaging: Screening Workbench 2.0.0

This is the verified Windows 11 x64 PyInstaller onedir procedure for Screening Workbench. It documents the Tcl/Tk zipfs workaround required for CPython 3.14.7 + PyInstaller 6.21.0. Build from a fresh checkout; keep all generated files outside it. This procedure builds only; it does not sign, publish, or create an installer.

**Reference artifact:** source commit `5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7`; `Screening-Workbench-2.0.0-windows-x64.zip`, 17,398,639 bytes, SHA-256 `15a30f396e00f7367485181f140601899cb1b8ba5ff074ee52db64c9243f49a7`. See `docs/release-gate-2.0.0.md`.

The recorded ZIP was built from private build-repository commit `5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7`. The public repository has a separate Git history; this procedure builds the mirrored source on public `main` and does not claim to reproduce that ZIP byte-for-byte.

## Requirements

- Windows 11 x64, PowerShell, Git, and CPython 3.14.7 x64 from python.org.
- `tcltk.msi` from the same CPython release and architecture, plus LessMSI (or equivalent MSI extractor). Independently pin and verify the LessMSI release hash before use; the extractor is a build prerequisite, not supplied by this project.
- PyInstaller 6.21.0 and the observed Windows toolchain versions: `altgraph==0.17.5`, `packaging==26.3`, `pefile==2024.8.26`, `pyinstaller-hooks-contrib==2026.8`, `pywin32-ctypes==0.2.3`, `setuptools==84.0.0`.

The official CPython 3.14.7 x64 archive checksum is `ac1a727a71738e11de80b76e975f9b8a258aea6412bfc31696b929d59c6aafd0`. This authenticates the downloaded Python distribution, but does not reconcile every native library's PE resource version with CPython's published source SBOM. The native version differences and the limit of the available provenance evidence are recorded in `license-review.md` and the release SBOM.

## Fresh checkout and isolated build toolchain

Set unique scratch paths outside the repository. Example:

```powershell
$env:SWB_ROOT = 'C:\work\screening-workbench'
$env:SWB_BUILD = 'C:\work\swb-release-build'
$env:SWB_SUPPORT = 'C:\work\swb-release-inputs'
git clone https://github.com/nateriera/screening-workbench.git $env:SWB_ROOT
Set-Location $env:SWB_ROOT
git checkout main
New-Item -ItemType Directory -Force -Path $env:SWB_BUILD, $env:SWB_SUPPORT | Out-Null
```

Fetch official Python and its matching Tcl/Tk support MSI; verify hashes before using either. Extract the MSI with the independently verified `$LESSMSI` CLI; the expected output is `tcltk\SourceDir\DLLs` and `tcltk\SourceDir\tcl` beneath the current working directory:

```powershell
$pythonZip = "$env:SWB_SUPPORT\python-3.14.7-amd64.zip"
$msi = "$env:SWB_SUPPORT\tcltk.msi"
Invoke-WebRequest 'https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.zip' -OutFile $pythonZip
if ((Get-FileHash $pythonZip -Algorithm SHA256).Hash.ToLower() -ne 'ac1a727a71738e11de80b76e975f9b8a258aea6412bfc31696b929d59c6aafd0') { throw 'CPython ZIP hash mismatch' }
Invoke-WebRequest 'https://www.python.org/ftp/python/3.14.7/amd64/tcltk.msi' -OutFile $msi
if ((Get-FileHash $msi -Algorithm SHA256).Hash.ToLower() -ne '4ae542ab046b3a1b2f10e6c1ee91a215cb4d0638aae373d6e0687472eb7170bd') { throw 'Tcl/Tk MSI hash mismatch' }
Push-Location $env:SWB_SUPPORT
& $LESSMSI x $msi
Pop-Location
$env:SWB_TCLTK = "$env:SWB_SUPPORT\tcltk\SourceDir"
$pythonHome = "$env:SWB_BUILD\python314"
Expand-Archive -Force $pythonZip $pythonHome
```

The verified matching inputs were: Tcl/Tk MSI SHA-256 `4ae542ab046b3a1b2f10e6c1ee91a215cb4d0638aae373d6e0687472eb7170bd`; Tcl archive SHA-256 `8201f2d61a95fd725d6eac46a57813389f5096967a00969663160020d848104a`; Tk archive SHA-256 `d99bc63cfa4f6c93f98808ec54f17be706b67e315968c1c9d82cf974828a8b70`.

Create filesystem Tcl/Tk script directories and stage the native files from that *same matching* support MSI into the extracted Python home before making the build venv. CPython 3.14 mounts its Tcl/Tk ZIP files with zipfs; PyInstaller 6.21.0 sees virtual `//zipfs:` paths and `os.path.isdir()` returns false. Its tkinter hook can therefore fire yet collect no scripts (`datas=[]`), with a runtime failure for missing `_tcl_data` / `_tk_data`. The workaround below makes real paths visible to the hook. Tcl's `init.tcl` must be directly within `TCL_LIBRARY`; Tk's `tk_library` contents must be copied to `tk9.0`, with `tk.tcl` directly at `TK_LIBRARY`.

```powershell
New-Item -ItemType Directory -Force -Path "$pythonHome\tcl", "$pythonHome\tcl\tk9.0" | Out-Null
Copy-Item "$env:SWB_TCLTK\DLLs\tcl90.dll", "$env:SWB_TCLTK\DLLs\tcl9tk90.dll", "$env:SWB_TCLTK\DLLs\libtommath.dll" "$pythonHome\DLLs\"
Copy-Item "$env:SWB_TCLTK\tcl\libtcl9.0.4.zip", "$env:SWB_TCLTK\tcl\libtk9.0.4.zip" "$pythonHome\tcl\"
Expand-Archive -Force "$pythonHome\tcl\libtcl9.0.4.zip" "$pythonHome\tcl"
Expand-Archive -Force "$pythonHome\tcl\libtk9.0.4.zip" "$pythonHome\tcl"
Copy-Item -Recurse -Force "$pythonHome\tcl\tk_library\*" "$pythonHome\tcl\tk9.0\"
$env:TCL_LIBRARY = "$pythonHome\tcl\tcl_library"
$env:TK_LIBRARY = "$pythonHome\tcl\tk9.0"

& "$pythonHome\python.exe" -m venv "$env:SWB_BUILD\venv"
$python = "$env:SWB_BUILD\venv\Scripts\python.exe"
& $python -m pip install altgraph==0.17.5 packaging==26.3 pefile==2024.8.26 pyinstaller==6.21.0 pyinstaller-hooks-contrib==2026.8 pywin32-ctypes==0.2.3 setuptools==84.0.0
New-Item -ItemType Directory -Force -Path "$env:SWB_BUILD\spec", "$env:SWB_BUILD\build", "$env:SWB_BUILD\dist" | Out-Null
```

Fail closed unless PyInstaller's hook sees Tcl/Tk files before running the full build:

```powershell
& $python -c 'from PyInstaller.utils.hooks.tcl_tk import tcltk_info; print("Tcl", tcltk_info.tcl_data_dir, "Tk", tcltk_info.tk_data_dir, "collected", len(tcltk_info.data_files)); assert len(tcltk_info.data_files) == 929'
```

The verified setup reported 929 Tcl/Tk hook data entries; the resulting onedir tree contained 839 Tcl files and 90 Tk files. The build log must not warn that Tcl/Tk data directories are missing. Do not continue if hook detection returns zero or the missing-directory warnings appear.

The Python/PyInstaller versions are pinned, but the pip command does not pin wheel hashes. A truly controlled rebuild should retain approved wheel files and add their SHA-256 digests to a requirements lock used with `pip install --require-hashes`. The release build must also record the verified LessMSI tool hash.

## Exact PyInstaller build command

Run from the checkout root with the environment variables above still set:

```powershell
Set-Location $env:SWB_ROOT
& $python -m PyInstaller --clean --noconfirm --onedir --windowed --name ScreeningWorkbench --paths src --specpath "$env:SWB_BUILD\spec" --workpath "$env:SWB_BUILD\build" --distpath "$env:SWB_BUILD\dist" --add-data "$env:SWB_ROOT\src\screening_workbench\fonts;screening_workbench/fonts" src\screening_workbench\app.py
```

`--add-data` bundles the ten OFL typeface files from `$env:SWB_ROOT\src\screening_workbench\fonts` to `_internal/screening_workbench/fonts`, where `typefaces.FONT_DIR` resolves inside the frozen app. This leaves the `.spec`, `build`, and `dist` outside the source tree. The expected executable is `$env:SWB_BUILD\dist\ScreeningWorkbench\ScreeningWorkbench.exe`.

## Required smoke test and package

### Disposable profile isolation (mandatory before launch)

The project database path is derived from `os.path.expanduser("~")`; settings use `SW_SETTINGS_PATH` or `%APPDATA%`. Isolate both before launching the packaged executable. Use a new disposable directory outside the repository and run the EXE from the same PowerShell process so it inherits these values:

```powershell
$env:SWB_TEST_PROFILE = Join-Path $env:TEMP ("ScreeningWorkbench-Smoke-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $env:SWB_TEST_PROFILE | Out-Null
$env:USERPROFILE = $env:SWB_TEST_PROFILE
$env:HOMEDRIVE = [IO.Path]::GetPathRoot($env:SWB_TEST_PROFILE).TrimEnd('\')
$env:HOMEPATH = $env:SWB_TEST_PROFILE.Substring($env:HOMEDRIVE.Length)
$env:APPDATA = Join-Path $env:SWB_TEST_PROFILE 'AppData\Roaming'
$env:LOCALAPPDATA = Join-Path $env:SWB_TEST_PROFILE 'AppData\Local'
$env:SW_SETTINGS_PATH = Join-Path $env:APPDATA 'Screening Workbench\settings.json'
$expectedProject = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE 'screening-workbench-project.sqlite'))
$expectedSettings = [IO.Path]::GetFullPath($env:SW_SETTINGS_PATH)
$profileRoot = [IO.Path]::GetFullPath($env:SWB_TEST_PROFILE).TrimEnd('\') + '\'
if (!$expectedProject.StartsWith($profileRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Project database path is outside the disposable profile' }
if (!$expectedSettings.StartsWith($profileRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Settings path is outside the disposable profile' }
$resolvedHome = (& $python -c "import os; print(os.path.expanduser('~'))").Trim()
if ([IO.Path]::GetFullPath($resolvedHome).TrimEnd('\') -ne [IO.Path]::GetFullPath($env:USERPROFILE).TrimEnd('\')) { throw 'Python home does not resolve to the disposable profile' }
if ((Test-Path -LiteralPath $expectedProject) -or (Test-Path -LiteralPath $expectedSettings)) { throw 'Disposable profile unexpectedly contains an existing database or settings file' }
Write-Host "Verified synthetic project database path: $expectedProject"
Write-Host "Verified disposable settings path: $expectedSettings"
```

Before importing any fixture, verify that the app uses the disposable database path under `SWB_TEST_PROFILE`. Use synthetic records only. Stop if the database or settings path resolves outside the disposable profile. Never reuse a profile containing user projects.

**Keep one persistent PowerShell session per profile for the entire smoke run.** Launch the extracted executable, poll for the exact main-window title and disposable database, perform every UI workflow and capture, then close the app window and wait for that process to exit before the PowerShell session returns. Do not let a launch command return and check its PID from a later shell. If the app exits before window readiness, record its exit code and captured stdout/stderr in that same session and stop the run. Use a fresh session and profile for the other theme.

Before packaging:

1. Read `$env:SWB_BUILD\build\ScreeningWorkbench\warn-ScreeningWorkbench.txt`. Conditional platform-only warnings (for example `posix`, `pwd`, `grp`, `fcntl`, `readline`, `java.lang`, `vms_lib`, `_scproxy`, `resource`) are normal. Tcl/Tk missing-directory warnings are a failure. Keep `TCL_LIBRARY` and `TK_LIBRARY` from the earlier setup exported into this PowerShell process when invoking PyInstaller; if a new shell was opened, set both explicitly again to the extracted filesystem directories before building.
2. Confirm these exist under `dist\ScreeningWorkbench\_internal`: `_tcl_data\init.tcl`, `_tk_data\tk.tcl`, `tcl90.dll`, `tcl9tk90.dll`, `libtommath.dll`. Also confirm `screening_workbench\fonts` contains exactly the ten `.ttf` files listed in `docs/license-audit.md`, with matching SHA-256 hashes. Fail the build if the Tcl/Tk warning appears or if `_tcl_data` / `_tk_data` is missing.
3. Launch the built EXE itself. Verify the visible window title is `Screening Workbench -- systematic review screening`, the window remains usable, and no Tcl/Tk traceback or missing-data error appears. Close it cleanly. A running process alone does not pass this test.
4. Copy the audited, version-controlled notice files into the onedir bundle. Keep both source and staged copies byte-for-byte identical; fail if any required notice is missing:

```powershell
$noticeFiles = @(
  'Screening-Workbench-LICENSE.txt', 'CPython-LICENSE.txt',
  'Tcl-license.terms', 'Tk-license.terms', 'LibTomMath-LICENSE.txt',
  'OpenSSL-LICENSE.txt', 'SQLite-NOTICE.txt', 'zlib-LICENSE.md',
  'Expat-COPYING.txt', 'libffi-LICENSE.txt', 'bzip2-LICENSE.txt',
  'XZ-COPYING.txt', 'Zstandard-LICENSE.txt',
  'Newsreader-OFL.txt', 'AtkinsonHyperlegibleNext-OFL.txt', 'AtkinsonHyperlegibleMono-OFL.txt'
)
$sourceNotices = Join-Path $env:SWB_ROOT 'docs\notices'
$bundleNotices = Join-Path $env:SWB_BUILD 'dist\ScreeningWorkbench\notices'
New-Item -ItemType Directory -Force -Path $bundleNotices | Out-Null
foreach ($name in $noticeFiles) {
  $source = Join-Path $sourceNotices $name
  if (!(Test-Path $source)) { throw "Missing required notice: $source" }
  Copy-Item -Force $source $bundleNotices
  $a = (Get-FileHash $source -Algorithm SHA256).Hash
  $b = (Get-FileHash (Join-Path $bundleNotices $name) -Algorithm SHA256).Hash
  if ($a -ne $b) { throw "Notice checksum mismatch: $name" }
}
```

This list includes the app's MIT text, CPython's complete distribution license, Tcl/Tk terms (as separate Tcl and Tk copies), LibTomMath's Unlicense, Apache-2.0 OpenSSL terms, SQLite's public-domain notice, the upstream notices for zlib-ng, Expat, libffi, bzip2, liblzma, and Zstandard, and the SIL Open Font License texts for the three bundled typeface families (Newsreader, Atkinson Hyperlegible Next, Atkinson Hyperlegible Mono). The official SQLite source does not ship a separate license file; the notice records its public-domain dedication and blessing, sourced at sqlite.org/copyright.html. The Visual C++ runtime is from the build host and is subject to Microsoft's Visual Studio redistribution terms; it is not an open-source license text and the right to redistribute is conditional on the publisher's valid Visual Studio license and the listed unmodified files. Confirm that entitlement before publishing.

5. Only after smoke test and notice staging succeed, create and verify the ZIP:

```powershell
$zip = "$env:SWB_BUILD\dist\Screening-Workbench-2.0.0-windows-x64.zip"
Compress-Archive -Path "$env:SWB_BUILD\dist\ScreeningWorkbench" -DestinationPath $zip -Force
Get-FileHash $zip -Algorithm SHA256
```

Confirm the ZIP contains every `notices/` file above and run:

```powershell
& $python -c 'import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); bad=z.testzip(); print("entries",len(z.namelist()),"bad",bad); assert bad is None; required={"ScreeningWorkbench/notices/"+x for x in sys.argv[2:]}; missing=required-set(z.namelist()); print("missing notices",missing); assert not missing' $zip $noticeFiles
```

Update the release-archive properties in `docs/sbom.cdx.json` only after recording the ZIP hash, size, entry count, and integrity result. See `docs/release-gate-2.0.0.md`.

The recorded ZIP was built from private build-repository commit `5ce1a30a40bb87f2a4b0488e250a31e3e80f4bb7`. The public repository has a separate Git history; this procedure builds the mirrored source on public `main` and does not claim to reproduce that ZIP byte-for-byte. Keep the SBOM outside the archive it describes to avoid a self-referential hash.

For the 2.0.0 candidate, relative font `--add-data` failed with external `--specpath`; the successful build used the absolute `SWB_ROOT` font source above. LessMSI was unavailable, so `msiexec /a` extracted the matching Tcl/Tk MSI.

## Exact ZIP smoke test

This gate is separate from the onedir build smoke above. After the ZIP passes its integrity and payload checks, extract that exact ZIP to a new directory outside the repository and build output. Run the executable from the extracted package, not from the onedir build tree. Keep the extracted path and ZIP hash in the gate record.

Repeat the test with a new disposable profile for each theme. Apply the disposable-profile isolation block above before launching, set SW_THEME to light or night, and confirm Python home, the project database path, and settings path resolve inside that profile before importing. Use synthetic records and a synthetic PDF only.

For each profile, verify the extracted app opens and remains usable; complete a synthetic project import and the Screening view; open PRISMA; complete the Full-text workflow including Include, promote, attach the synthetic PDF, and open it. Stop if a database or settings path escapes the disposable profile, if any workflow fails, or if any user data appears.

Capture package-only Screening screenshots from the synthetic project in both palettes. Save the accepted captures as release-2.0.0/evidence/package-screening-light.png and release-2.0.0/evidence/package-screening-night.png. Do not use empty-project startup screens, build-tree captures, or images containing other windows as gate evidence. If the extracted package cannot be driven through these workflows or both clean captures cannot be obtained, record the gate as blocked.

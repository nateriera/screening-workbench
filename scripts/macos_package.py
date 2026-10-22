#!/usr/bin/env python3
"""Collect macOS candidate evidence and create a validated app ZIP.

The output is an inspectable Actions candidate artifact. This script does not
sign with a Developer ID, notarize, publish, or change the application version.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from datetime import datetime, timezone
from pathlib import Path


PRODUCT_VERSION_LABEL = "1.1.0"
REQUIRED_NOTICE_FILES = (
    "Screening-Workbench-LICENSE.txt",
    "CPython-LICENSE.txt",
    "Tcl-license.terms",
    "Tk-license.terms",
    "LibTomMath-LICENSE.txt",
    "OpenSSL-LICENSE.txt",
    "SQLite-NOTICE.txt",
    "zlib-LICENSE.md",
    "Expat-COPYING.txt",
    "libffi-LICENSE.txt",
    "bzip2-LICENSE.txt",
    "XZ-COPYING.txt",
    "Zstandard-LICENSE.txt",
)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def license_file_name(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith(("license", "licence", "copying", "notice", "copyright")) or name in {
        "license.terms",
        "licence.terms",
    }


def copy_dist_license_files(distribution: metadata.Distribution, destination: Path) -> list[str]:
    copied: list[str] = []
    files = distribution.files or ()
    package_name = distribution.metadata.get("Name", "unknown").replace("/", "_")
    for item in files:
        relative = Path(str(item))
        if not license_file_name(relative):
            continue
        source = Path(distribution.locate_file(item))
        if not source.is_file():
            continue
        target = destination / package_name / relative.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target.relative_to(destination).as_posix())
    return sorted(set(copied))


def runtime_license_candidates(prefix: Path) -> list[Path]:
    candidates = [
        prefix / "LICENSE.txt",
        prefix / "LICENSE",
        prefix / "License.rtf",
        prefix / "Resources" / "License.rtf",
        prefix / "Resources" / "LICENSE.txt",
        prefix / "Resources" / "LICENSE",
    ]
    library = prefix / "lib"
    if library.is_dir():
        for pattern in ("tcl*/license.terms", "tk*/license.terms"):
            candidates.extend(library.glob(pattern))
    return [path for path in candidates if path.is_file()]


def command_text(command: list[str]) -> tuple[int | None, str, str]:
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "", f"{type(exc).__name__}: {exc}"


def capture_evidence(output: Path, app: Path | None) -> None:
    output.mkdir(parents=True, exist_ok=True)
    packages: list[dict[str, object]] = []
    package_license_root = output / "build-tool-license-texts"
    for distribution in sorted(metadata.distributions(), key=lambda item: (item.metadata.get("Name", "").casefold(), item.version)):
        name = distribution.metadata.get("Name") or "unknown"
        license_files = copy_dist_license_files(distribution, package_license_root)
        classifiers = [
            value.removeprefix("License :: ")
            for value in distribution.metadata.get_all("Classifier", ())
            if value.startswith("License :: ")
        ]
        packages.append(
            {
                "name": name,
                "version": distribution.version,
                "license_expression": distribution.metadata.get("License-Expression"),
                "license_metadata": distribution.metadata.get("License"),
                "license_classifiers": classifiers,
                "license_files_copied": license_files,
                "license_file_text_copied": bool(license_files),
            }
        )

    freeze = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        text=True,
        capture_output=True,
        check=False,
    )
    (output / "pip-freeze.txt").write_text(freeze.stdout, encoding="utf-8")
    freeze_status = {
        "command": [sys.executable, "-m", "pip", "freeze", "--all"],
        "exit_code": freeze.returncode,
        "stderr": freeze.stderr.strip(),
    }

    runtime_root = output / "python-runtime-license-texts"
    runtime_files: list[str] = []
    for source in runtime_license_candidates(Path(sys.base_prefix)):
        target = runtime_root / source.name
        suffix = 2
        while target.exists():
            target = runtime_root / f"{source.stem}-{suffix}{source.suffix}"
            suffix += 1
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        runtime_files.append(target.relative_to(output).as_posix())

    app_details: dict[str, object] | None = None
    if app is not None:
        info_path = app / "Contents" / "Info.plist"
        if not info_path.is_file():
            raise SystemExit(f"App bundle lacks Info.plist: {info_path}")
        with info_path.open("rb") as stream:
            plist = plistlib.load(stream)
        executable_name = plist.get("CFBundleExecutable")
        executable = app / "Contents" / "MacOS" / str(executable_name or "")
        architectures = command_text(["/usr/bin/lipo", "-archs", str(executable)])
        signature = command_text(["/usr/bin/codesign", "-dv", "--verbose=4", str(app)])
        app_details = {
            "path": str(app.resolve()),
            "bundle_identifier": plist.get("CFBundleIdentifier"),
            "bundle_version": plist.get("CFBundleVersion"),
            "bundle_short_version": plist.get("CFBundleShortVersionString"),
            "executable": str(executable),
            "architectures": architectures[1],
            "architecture_check_exit_code": architectures[0],
            "codesign_display_exit_code": signature[0],
            "codesign_display_stdout": signature[1],
            "codesign_display_stderr": signature[2],
            "signing_identity": "none supplied by workflow",
            "notarized": False,
            "note": "PyInstaller may add an ad-hoc signature; this is not Developer ID signing.",
        }
        (output / "codesign-inspection.txt").write_text(
            "\n".join(part for part in (signature[1], signature[2]) if part) + "\n",
            encoding="utf-8",
        )

    project = tomllib.loads((Path.cwd() / "pyproject.toml").read_text(encoding="utf-8"))
    module_source = Path.cwd() / "src" / "screening_workbench" / "__init__.py"
    module_version_match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        module_source.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    evidence = {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "candidate_label": PRODUCT_VERSION_LABEL,
        "project_metadata_version": project.get("project", {}).get("version"),
        "source_module_version": module_version_match.group(1) if module_version_match else None,
        "version_note": "The 1.1.0 value labels this candidate artifact; project/app version metadata was not changed.",
        "python_installer": {
            "source": f"https://www.python.org/ftp/python/{os.environ.get('PYTHON_VERSION', '3.12.10')}/python-{os.environ.get('PYTHON_VERSION', '3.12.10')}-macos11.pkg",
            "verification": "pkgutil --check-signature output and downloaded file SHA-256 are retained in this evidence directory.",
        },
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "prefix": sys.prefix,
            "base_prefix": sys.base_prefix,
            "architecture": platform.machine(),
            "platform": platform.platform(),
            "tcl_tk_patchlevel": None,
            "runtime_license_files_copied": runtime_files,
        },
        "app": app_details,
        "application_runtime_dependencies": "Python standard library only, per source declaration; PyInstaller is a build tool.",
        "pip_freeze": freeze_status,
        "resolved_python_distributions": packages,
        "license_evidence_note": (
            "Package metadata and any license-like text files present in installed distribution metadata are recorded. "
            "This build inventory does not establish legal clearance for redistribution."
        ),
    }
    try:
        import tkinter

        root = tkinter.Tk()
        root.withdraw()
        evidence["python"]["tcl_tk_patchlevel"] = str(root.tk.call("info", "patchlevel"))
        root.destroy()
    except Exception as exc:  # preserve missing Tk as evidence instead of hiding it
        evidence["python"]["tcl_tk_error"] = f"{type(exc).__name__}: {exc}"
    write_json(output / "build-environment-and-licenses.json", evidence)
    if freeze.returncode != 0:
        raise SystemExit(f"pip freeze failed: {freeze.stderr}")


def create_package(app: Path, repo_root: Path, output: Path, candidate_label: str, evidence_dir: Path) -> None:
    if candidate_label != PRODUCT_VERSION_LABEL:
        raise SystemExit(f"Candidate label must remain {PRODUCT_VERSION_LABEL}; received {candidate_label}")
    app = app.resolve()
    repo_root = repo_root.resolve()
    output = output.resolve()
    evidence_dir = evidence_dir.resolve()
    if not app.is_dir() or app.suffix != ".app":
        raise SystemExit(f"Expected a built .app bundle: {app}")
    notice_source = repo_root / "docs" / "notices"
    missing = [name for name in REQUIRED_NOTICE_FILES if not (notice_source / name).is_file()]
    if missing:
        raise SystemExit("Missing required repository notices: " + ", ".join(missing))
    if not (repo_root / "LICENSE").is_file():
        raise SystemExit("Project LICENSE file is missing")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="swb-package-") as temp_name:
        package_root = Path(temp_name) / "ScreeningWorkbench"
        package_root.mkdir(parents=True)
        destination_app = package_root / app.name
        shutil.copytree(app, destination_app, symlinks=True)
        notices = package_root / "notices"
        notices.mkdir()
        for name in REQUIRED_NOTICE_FILES:
            shutil.copy2(notice_source / name, notices / name)
        shutil.copy2(repo_root / "LICENSE", notices / "Screening-Workbench-LICENSE.txt")
        (notices / "MACOS-CANDIDATE-SCOPE.txt").write_text(
            "These are the project's available upstream license and notice texts for the candidate bundle.\n"
            "The accompanying Windows license review is not a macOS binary audit or redistribution clearance.\n"
            "The build evidence records the exact Python.org runtime and installed build-package metadata.\n"
            "Review exact macOS collected files and their provenance before any public distribution.\n",
            encoding="utf-8",
        )
        runtime_texts = evidence_dir / "python-runtime-license-texts"
        if runtime_texts.is_dir():
            shutil.copytree(runtime_texts, notices / "python-runtime-license-texts")
        package_env = evidence_dir / "build-environment-and-licenses.json"
        pip_freeze = evidence_dir / "pip-freeze.txt"
        if package_env.is_file():
            shutil.copy2(package_env, package_root / "build-environment-and-licenses.json")
        if pip_freeze.is_file():
            shutil.copy2(pip_freeze, package_root / "pip-freeze.txt")
        candidate_evidence = package_root / "candidate-evidence"
        test_results = evidence_dir / "test-results.json"
        smoke_results = evidence_dir / "smoke" / "evidence.json"
        if test_results.is_file():
            candidate_evidence.mkdir()
            shutil.copy2(test_results, candidate_evidence / "test-results.json")
        if smoke_results.is_file():
            candidate_evidence.mkdir(exist_ok=True)
            shutil.copy2(smoke_results, candidate_evidence / "macos-smoke-evidence.json")
        (package_root / "CANDIDATE-EVIDENCE.txt").write_text(
            f"Screening Workbench {candidate_label} macOS ARM64 candidate package.\n"
            "This ZIP is a build candidate retained as a GitHub Actions artifact.\n"
            "It is not a signed/notarized public release. Review candidate-evidence and the separate Actions evidence artifact.\n"
            "The candidate label does not change the application metadata version.\n",
            encoding="utf-8",
        )

        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            output.unlink()
        result = subprocess.run(
            ["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", str(package_root), str(output)],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit(f"ditto ZIP creation failed: {result.stderr.strip()}")

    with zipfile.ZipFile(output) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise SystemExit(f"ZIP CRC check failed for {bad_member}")
        names = set(archive.namelist())
        prefix = ""
        required_members = {
            prefix + f"notices/{name}" for name in REQUIRED_NOTICE_FILES
        } | {
            prefix + "notices/Screening-Workbench-LICENSE.txt",
            prefix + "notices/MACOS-CANDIDATE-SCOPE.txt",
            prefix + f"{app.name}/Contents/Info.plist",
            prefix + "build-environment-and-licenses.json",
            prefix + "pip-freeze.txt",
            prefix + "candidate-evidence/test-results.json",
            prefix + "candidate-evidence/macos-smoke-evidence.json",
            prefix + "CANDIDATE-EVIDENCE.txt",
        }
        missing_members = sorted(required_members - names)
        if missing_members:
            raise SystemExit("ZIP is missing required files: " + ", ".join(missing_members))
        entry_count = len(archive.infolist())
        uncompressed_bytes = sum(entry.file_size for entry in archive.infolist())

    validation = {
        "schema_version": 1,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_label": candidate_label,
        "zip_path": str(output),
        "zip_bytes": output.stat().st_size,
        "zip_sha256": sha256_file(output),
        "zip_entry_count": entry_count,
        "zip_uncompressed_bytes": uncompressed_bytes,
        "zip_crc_check": "passed",
        "required_app_and_notice_entries": "present",
        "signing": "No Developer ID identity supplied; PyInstaller may have applied an ad-hoc signature.",
        "notarization": "not performed",
        "distribution": "GitHub Actions candidate artifact only; not a GitHub Release.",
    }
    write_json(evidence_dir / "zip-validation.json", validation)
    print(json.dumps(validation, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    capture = subparsers.add_parser("capture", help="record interpreter, app, package, and license evidence")
    capture.add_argument("--output", type=Path, required=True)
    capture.add_argument("--app", type=Path)
    package = subparsers.add_parser("package", help="create a ZIP candidate and validate its CRC and contents")
    package.add_argument("--app", type=Path, required=True)
    package.add_argument("--repo-root", type=Path, required=True)
    package.add_argument("--output", type=Path, required=True)
    package.add_argument("--candidate-label", default=PRODUCT_VERSION_LABEL)
    package.add_argument("--evidence-dir", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "capture":
        capture_evidence(args.output.expanduser().resolve(), args.app.expanduser().resolve() if args.app else None)
    elif args.command == "package":
        create_package(
            args.app.expanduser(),
            args.repo_root.expanduser(),
            args.output.expanduser(),
            args.candidate_label,
            args.evidence_dir.expanduser(),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

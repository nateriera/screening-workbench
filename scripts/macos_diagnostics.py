#!/usr/bin/env python3
"""Run isolated and ordered macOS Tk regression diagnostics with hard timeouts."""
from __future__ import annotations

import argparse
import json
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

HANG = "tests/test_app.py::test_fulltext_tab_queue_and_detail_show_report_and_source_identity"
CASES = [
    ("isolated-hang", [HANG], False, {}),
    ("isolated-hang-select-fulltext", [HANG], False, {"SWB_DIAG_SELECT_FULLTEXT": "1"}),
    ("isolated-hang-deiconify", [HANG], False, {"SWB_DIAG_DEICONIFY": "1"}),
    ("isolated-hang-select-fulltext-deiconify", [HANG], False,
     {"SWB_DIAG_SELECT_FULLTEXT": "1", "SWB_DIAG_DEICONIFY": "1"}),
    ("isolated-hang-inline-selection", [HANG], False, {"SWB_DIAG_INLINE_SELECTION": "1"}),
    ("isolated-hang-update-idletasks", [HANG], False, {"SWB_DIAG_UPDATE_IDLE": "1"}),
]


def _command_output(command: list[str], timeout: int = 15) -> dict:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        return {"command": command, "returncode": result.returncode,
                "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except Exception as exc:
        return {"command": command, "error": repr(exc)}


def collect_environment(output: Path) -> None:
    info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "python_executable": sys.executable,
        "macos_sw_vers": _command_output(["sw_vers"]),
        "cpu_brand": _command_output(["sysctl", "-n", "machdep.cpu.brand_string"]),
    }
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        info["tk_display"] = {
            "windowing_system": root.tk.call("tk", "windowingsystem"),
            "screen_width": root.winfo_screenwidth(),
            "screen_height": root.winfo_screenheight(),
            "tcl_version": root.tk.call("info", "patchlevel"),
            "tk_version": root.tk.call("package", "provide", "Tk"),
        }
        root.destroy()
    except Exception as exc:
        info["tk_display_error"] = repr(exc)
    (output / "environment.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    rows.append({"unparsed": line.rstrip()})
    return rows


def _screenshot(path: Path) -> dict:
    try:
        result = subprocess.run(["screencapture", "-x", str(path)], capture_output=True, text=True,
                                timeout=8, check=False)
        return {"path": str(path), "returncode": result.returncode,
                "stderr": result.stderr.strip()}
    except Exception as exc:
        return {"path": str(path), "error": repr(exc)}


def _sample_process(pid: int, path: Path) -> dict:
    command = ["/usr/bin/sample", str(pid), "3", "-file", str(path)]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=12, check=False)
        size_bytes = path.stat().st_size if path.is_file() else 0
        truncated = False
        if size_bytes > 8 * 1024 * 1024:
            marker = b"\n[Diagnostic sample truncated at 8 MiB to bound artifact size.]\n"
            with path.open("rb+") as stream:
                stream.truncate(8 * 1024 * 1024 - len(marker))
                stream.seek(0, os.SEEK_END)
                stream.write(marker)
            size_bytes = path.stat().st_size
            truncated = True
        return {"command": command, "returncode": result.returncode,
                "path": str(path), "file_exists": path.is_file(),
                "size_bytes": size_bytes, "truncated_at_8_mib": truncated,
                "stdout": result.stdout.strip(), "stderr": result.stderr.strip()}
    except Exception as exc:
        return {"command": command, "path": str(path), "error": repr(exc)}

def run_case(output: Path, name: str, nodeids: list[str], cleanup: bool,
             controls: dict[str, str], timeout: int) -> dict:
    case_dir = output / name
    case_dir.mkdir(parents=True, exist_ok=True)
    junit = case_dir / "pytest-junit.xml"
    command = [
        sys.executable, "-m", "pytest", *nodeids, "-vv", "-s",
        f"--junitxml={junit}", "-o", "faulthandler_timeout=15",
        "-p", "scripts.macos_pytest_evidence",
        "-p", "scripts.macos_gui_diagnostic_plugin",
    ]
    env = os.environ.copy()
    env.update({
        "PYTHONUNBUFFERED": "1",
        "SWB_TEST_EVIDENCE_DIR": str(case_dir),
        "SWB_DIAGNOSTIC_DIR": str(case_dir),
        "SWB_CLEANUP_TK_ROOTS": "1" if cleanup else "0",
        "SWB_DIAG_SELECT_FULLTEXT": controls.get("SWB_DIAG_SELECT_FULLTEXT", "0"),
        "SWB_DIAG_DEICONIFY": controls.get("SWB_DIAG_DEICONIFY", "0"),
        "SWB_DIAG_INLINE_SELECTION": controls.get("SWB_DIAG_INLINE_SELECTION", "0"),
        "SWB_DIAG_UPDATE_IDLE": controls.get("SWB_DIAG_UPDATE_IDLE", "0"),
    })
    start = time.monotonic()
    timed_out = False
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        cwd=Path(__file__).resolve().parents[1], env=env, start_new_session=True,
    )
    screenshots = None
    native_sample = None
    try:
        output_bytes, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        # Capture before terminating the child so a previously leaked,
        # deiconified Tk root is still visible in the screenshot.
        screenshots = _screenshot(case_dir / "timeout-screen.png")
        native_sample = _sample_process(process.pid, case_dir / "native-process.sample.txt")
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            output_bytes, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            output_bytes, _ = process.communicate()
    log_path = case_dir / "pytest.log"
    log_path.write_bytes(output_bytes or b"")

    tests = _read_jsonl(case_dir / "pytest-tests.jsonl")
    phases = _read_jsonl(case_dir / "pytest-phases.jsonl")
    counts = {state: sum(row.get("status") == state for row in tests)
              for state in ("passed", "failed", "skipped", "other")}
    failed = [row for row in tests if row.get("status") == "failed"]
    active_path = case_dir / "active-node.json"
    active = json.loads(active_path.read_text(encoding="utf-8")).get("nodeid") if active_path.is_file() else None
    result = {
        "case": name,
        "command": command,
        "cleanup_control": cleanup,
        "runtime_controls": controls,
        "timeout_seconds": timeout,
        "timed_out": timed_out,
        "exit_code": 124 if timed_out else int(process.returncode or 0),
        "duration_seconds": round(time.monotonic() - start, 3),
        "completed_test_counts": counts,
        "completed_test_count": len(tests),
        "failed_tests": failed,
        "active_node_at_end": active,
        "phase_record_count": len(phases),
        "log": str(log_path),
        "junit_xml": str(junit),
        "gui_events": str(case_dir / "gui-events.jsonl"),
        "screenshot": screenshots,
        "native_sample": native_sample,
        "case_status": "timed_out" if timed_out else ("passed" if process.returncode == 0 else "failed"),
    }
    (case_dir / "case-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{name}: {result['case_status']} after {result['duration_seconds']}s; "
          f"completed={len(tests)} counts={counts} active={active}", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=45)
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be positive")
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    collect_environment(output)
    results = []
    for name, nodeids, cleanup, controls in CASES:
        print(f"Starting {name}: {nodeids}", flush=True)
        try:
            results.append(run_case(output, name, nodeids, cleanup, controls, args.timeout))
        except Exception as exc:
            results.append({"case": name, "nodeids": nodeids, "cleanup_control": cleanup,
                            "runtime_controls": controls,
                            "case_status": "harness_error", "error": repr(exc)})
    summary = {
        "case_count": len(results),
        "timeout_seconds_per_case": args.timeout,
        "cases": results,
        "diagnostic_only": True,
        "test_failures_or_timeouts_do_not_fail_harness": True,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

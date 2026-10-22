#!/usr/bin/env python3
"""Compare packaged-app AppleScript and Core Graphics clicks with retained evidence.

This diagnostic launches the supplied existing .app twice against separate
copies of the retained synthetic project. It does not alter app code, request
privacy permissions, or treat a successful input API call as UI acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Points are anchored to the previous source-runner screenshot and the Tk
# origin fallback (window frame at 40,26; Tk content origin at 40,53). The
# report/PDF/action points are approximate visible centers from those images.
FRAME_POSITION = (40, 26)
FRAME_RELATIVE_POINTS = {
    "fulltext_tab": (520, 140),
    "report_first_row": (50, 389),
    "attachment_pdf_row": (860, 493),
    "open_selected_button": (935, 556),
}
SOURCE_CALIBRATION = {
    "screenshot_screen_points": {
        "fulltext_tab": [560, 166],
        "report_first_row": [90, 415],
        "attachment_pdf_row": [900, 519],
        "open_selected_button": [975, 582],
    },
    "fallback_window_frame_position": list(FRAME_POSITION),
    "source_tk_to_ax_frame_offset": [0, 27],
}

SWIFT_HELPER = r'''import ApplicationServices
import CoreGraphics
import Darwin
import Foundation

func jsonLine(_ value: [String: Any]) {
    if let data = try? JSONSerialization.data(withJSONObject: value, options: [.sortedKeys]),
       let text = String(data: data, encoding: .utf8) { print(text) }
}

let args = CommandLine.arguments
let canPost = CGPreflightPostEventAccess()
let axTrusted = AXIsProcessTrusted()
if args.count == 2 && args[1] == "--access" {
    jsonLine(["cg_preflight_post_event_access": canPost,
              "ax_is_process_trusted": axTrusted,
              "prompt_requested": false])
    exit(0)
}
guard args.count == 5, args[1] == "--click",
      let pid = pid_t(args[2]), let x = Double(args[3]), let y = Double(args[4]) else {
    fputs("usage: helper --access | --click PID X Y\n", stderr)
    exit(2)
}
let point = CGPoint(x: x, y: y)
guard let move = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved,
                         mouseCursorPosition: point, mouseButton: .left),
      let down = CGEvent(mouseEventSource: nil, mouseType: .leftMouseDown,
                         mouseCursorPosition: point, mouseButton: .left),
      let up = CGEvent(mouseEventSource: nil, mouseType: .leftMouseUp,
                       mouseCursorPosition: point, mouseButton: .left) else {
    jsonLine(["posted": false, "reason": "CGEvent construction failed",
              "cg_preflight_post_event_access": canPost, "ax_is_process_trusted": axTrusted])
    exit(3)
}
move.postToPid(pid)
Thread.sleep(forTimeInterval: 0.04)
down.postToPid(pid)
Thread.sleep(forTimeInterval: 0.06)
up.postToPid(pid)
jsonLine(["posted": true, "delivery": "CGEvent.postToPid",
          "pid": Int(pid), "x": x, "y": y,
          "cg_preflight_post_event_access": canPost,
          "ax_is_process_trusted": axTrusted,
          "permission_prompt_requested": false])
'''


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _run(command: list[str], timeout: float, *, text: bool = True) -> dict:
    try:
        result = subprocess.run(command, capture_output=True, text=text, timeout=timeout, check=False)
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": (result.stdout if text else result.stdout.decode("utf-8", "replace"))[-12000:],
            "stderr": (result.stderr if text else result.stderr.decode("utf-8", "replace"))[-12000:],
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "error": f"{type(exc).__name__}: {exc}"}


def _bounded(deadline: float, maximum: float) -> float:
    return max(0.1, min(maximum, deadline - time.monotonic()))


def _capture(path: Path, deadline: float) -> dict:
    result = _run(["/usr/sbin/screencapture", "-x", str(path)], _bounded(deadline, 6))
    result["path"] = str(path)
    result["file_exists"] = path.is_file()
    if path.is_file():
        result["size_bytes"] = path.stat().st_size
        result["sha256"] = _sha256(path)
    return result


def _screen_bounds(deadline: float) -> dict:
    import tkinter as tk
    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        return {"method": "Tk logical screen dimensions", "width": root.winfo_screenwidth(),
                "height": root.winfo_screenheight()}
    except tk.TclError as exc:
        return {"error": repr(exc)}
    finally:
        if root is not None:
            root.destroy()


def _window_setup(pid: int, deadline: float) -> dict:
    script = f'''tell application "System Events"
    set p to first process whose unix id is {pid}
    set frontmost of p to true
    delay 0.3
    set win to window 1 of p
    set position of win to {{{FRAME_POSITION[0]}, {FRAME_POSITION[1]}}}
    delay 0.2
    set ppos to position of win
    set wsz to size of win
    return ((item 1 of ppos) as text) & tab & ((item 2 of ppos) as text) & tab & ((item 1 of wsz) as text) & tab & ((item 2 of wsz) as text)
end tell'''
    result = _run(["osascript", "-e", script], _bounded(deadline, 6))
    result["script"] = script
    try:
        values = [int(value) for value in result.get("stdout", "").split()]
        if result.get("returncode") == 0 and len(values) >= 4:
            result["position"] = {"x": values[0], "y": values[1]}
            result["size"] = {"width": values[2], "height": values[3]}
    except ValueError:
        pass
    return result


def _system_click(pid: int, point: tuple[int, int], deadline: float) -> dict:
    script = f'''tell application "System Events"
    set p to first process whose unix id is {pid}
    set frontmost of p to true
    click at {{{point[0]}, {point[1]}}}
    return "CLICK_SENT"
end tell'''
    result = _run(["osascript", "-e", script], _bounded(deadline, 6))
    result["script"] = script
    return result


def _preview_state(deadline: float) -> dict:
    pids = _run(["/usr/bin/pgrep", "-x", "Preview"], _bounded(deadline, 4))
    script = '''tell application "System Events"
    set p to first process whose name is "Preview"
    set docs to ""
    repeat with w in windows of p
        try
            set docs to docs & (value of attribute "AXDocument" of w as text) & linefeed
        end try
    end repeat
    return docs
end tell'''
    docs = _run(["osascript", "-e", script], _bounded(deadline, 5))
    return {"pids": pids, "documents": docs, "script": script}


def _copy_seed(evidence_root: Path, case_home: Path) -> dict:
    smoke = evidence_root / "smoke" if (evidence_root / "smoke").is_dir() else evidence_root
    source = smoke / "synthetic-source-run"
    source_db = source / "project.sqlite"
    source_attachments = source / "attachments"
    expected_pdf = source / "synthetic-attachment.pdf"
    if not source_db.is_file() or not source_attachments.is_dir() or not expected_pdf.is_file():
        raise FileNotFoundError(f"expected retained source DB, attachment, and PDF under {source}")
    target_db = case_home / "screening-workbench-project.sqlite"
    shutil.copy2(source_db, target_db)
    target_attachments = case_home / "attachments"
    shutil.copytree(source_attachments, target_attachments)
    copied = sorted((str(p.relative_to(case_home)), p.stat().st_size, _sha256(p))
                    for p in [target_db, *target_attachments.rglob("*")] if p.is_file())
    return {
        "source_db": str(source_db),
        "source_attachments": str(source_attachments),
        "expected_pdf": str(expected_pdf),
        "expected_pdf_sha256": _sha256(expected_pdf),
        "target_db": str(target_db),
        "target_attachments": str(target_attachments),
        "copied_files": [{"path": row[0], "size_bytes": row[1], "sha256": row[2]} for row in copied],
    }


def _new_temp_pdfs(before: set[str], expected_pdf: bytes) -> list[dict]:
    root = Path(tempfile.gettempdir())
    records = []
    for directory in root.glob("screening-workbench-attachment-*"):
        if not directory.is_dir() or str(directory.resolve()) in before:
            continue
        candidate = directory / "synthetic-attachment.pdf"
        if candidate.is_file():
            data = candidate.read_bytes()
            records.append({"path": str(candidate.resolve()), "size_bytes": len(data),
                            "sha256": hashlib.sha256(data).hexdigest(),
                            "exact_synthetic_bytes_match": data == expected_pdf})
    return records


def _temp_dirs() -> set[str]:
    return {str(path.resolve()) for path in Path(tempfile.gettempdir()).glob("screening-workbench-attachment-*")
            if path.is_dir()}


def _run_case(method: str, executable: Path, info: dict, evidence_root: Path,
              output: Path, bounds: dict, swift_helper: Path | None,
              deadline: float) -> dict:
    case_dir = output / method
    home = case_dir / "home"
    case_dir.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    record: dict = {
        "method": method,
        "app_executable": str(executable),
        "bundle_identifier": info.get("CFBundleIdentifier"),
        "bundle_short_version": info.get("CFBundleShortVersionString"),
        "input_method": "System Events click-at" if method == "system-events" else "Core Graphics CGEvent.postToPid",
        "source_calibration": SOURCE_CALIBRATION,
        "screen_bounds": bounds,
        "stage_screenshots": [],
        "actions": [],
        "status": "running",
        "acceptance": "requires new byte-identical PDF temp copy and matching Preview AXDocument path",
    }
    proc = None
    stdout_path = case_dir / "app.stdout.log"
    stderr_path = case_dir / "app.stderr.log"
    before_dirs = _temp_dirs()
    record["preview_before"] = _preview_state(deadline)
    stdout_file = stderr_file = None
    try:
        record["seed"] = _copy_seed(evidence_root, home)
        expected_pdf = Path(record["seed"]["expected_pdf"]).read_bytes()
        env = os.environ.copy()
        env["HOME"] = str(home)
        env["SCREENING_WORKBENCH_REVIEWER_ID"] = "smoke-reviewer"
        stdout_file = stdout_path.open("wb")
        stderr_file = stderr_path.open("wb")
        proc = subprocess.Popen([str(executable)], env=env, cwd=str(case_dir),
                                stdout=stdout_file, stderr=stderr_file, start_new_session=True)
        record["pid"] = proc.pid
        record["launch_time_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        time.sleep(min(3, max(0, deadline - time.monotonic())))
        record["exit_code_after_launch_wait"] = proc.poll()
        if proc.poll() is not None:
            record["status"] = "app_exited"
            return record
        record["window_setup"] = _window_setup(proc.pid, deadline)
        pos = record["window_setup"].get("position")
        if not pos:
            record["status"] = "window_position_unavailable"
            return record
        record["coordinate_origin"] = {
            "kind": "live packaged AX window frame position",
            "position": pos,
            "requested_frame_position": list(FRAME_POSITION),
            "window_setup_success": record["window_setup"].get("returncode") == 0,
            "matches_requested_frame_position": pos == {"x": FRAME_POSITION[0], "y": FRAME_POSITION[1]},
        }
        screen_width, screen_height = bounds.get("width", 0), bounds.get("height", 0)
        targets = {}
        for name, (dx, dy) in FRAME_RELATIVE_POINTS.items():
            targets[name] = (pos["x"] + dx, pos["y"] + dy)
        record["computed_click_points"] = {
            name: {
                "screen": {"x": point[0], "y": point[1]},
                "window_frame_relative": {"x": FRAME_RELATIVE_POINTS[name][0], "y": FRAME_RELATIVE_POINTS[name][1]},
                "within_visible_screen_bounds": 0 <= point[0] < screen_width and 0 <= point[1] < screen_height,
            }
            for name, point in targets.items()
        }
        before_screenshot = {"stage": "before-input", **_capture(case_dir / "00-before-input.png", deadline)}
        record["stage_screenshots"].append(before_screenshot)
        stages = ["fulltext_tab", "report_first_row", "attachment_pdf_row", "open_selected_button"]
        for index, name in enumerate(stages, 1):
            if time.monotonic() >= deadline:
                record["status"] = "harness_timeout"
                break
            point = targets[name]
            target = record["computed_click_points"][name]
            if not target["within_visible_screen_bounds"]:
                record["actions"].append({"stage": name, "status": "outside_visible_screen", **target})
                record["status"] = "coordinate_out_of_bounds"
                break
            if method == "system-events":
                action = _system_click(proc.pid, point, deadline)
            elif swift_helper and swift_helper.is_file():
                action = _run([str(swift_helper), "--click", str(proc.pid), str(point[0]), str(point[1])],
                              _bounded(deadline, 6))
                try:
                    action["event_post_result"] = json.loads(action.get("stdout", "").strip())
                except json.JSONDecodeError:
                    pass
            else:
                action = {"error": "Swift Core Graphics helper was not compiled"}
            action_record = {
                "stage": name, "coordinate": target, "action": action,
                "api_call_completed": action.get("returncode") == 0 and "error" not in action,
                "before_screenshot": before_screenshot.get("path"),
            }
            record["actions"].append(action_record)
            time.sleep(min(0.7, max(0, deadline - time.monotonic())))
            after_screenshot = {
                "stage": f"after-{index}-{name}",
                **_capture(case_dir / f"{index:02d}-after-{name}.png", deadline),
            }
            record["stage_screenshots"].append(after_screenshot)
            action_record["after_screenshot"] = after_screenshot.get("path")
            before_screenshot = after_screenshot
            if proc.poll() is not None:
                record["status"] = "app_exited_during_input"
                break
        record["exit_code_after_input"] = proc.poll()
        record["new_attachment_temp_pdfs"] = _new_temp_pdfs(before_dirs, expected_pdf)
        record["exact_synthetic_temp_pdf_paths"] = [
            item["path"] for item in record["new_attachment_temp_pdfs"]
            if item["exact_synthetic_bytes_match"]
        ]
        record["preview_after"] = _preview_state(deadline)
        record["preview_ax_matches_new_temp_pdf"] = any(
            Path(pdf).parent.name in record["preview_after"]["documents"].get("stdout", "")
            and Path(pdf).name in record["preview_after"]["documents"].get("stdout", "")
            for pdf in record["exact_synthetic_temp_pdf_paths"]
        )
        if record["exact_synthetic_temp_pdf_paths"] and record["preview_ax_matches_new_temp_pdf"]:
            record["status"] = "passed_evidence"
        elif record["status"] == "running":
            record["status"] = "input_attempt_unverified"
        record["diagnostic_result"] = {
            "app_open_callback_evidenced": bool(record["exact_synthetic_temp_pdf_paths"]),
            "matching_preview_document_evidenced": record["preview_ax_matches_new_temp_pdf"],
            "human_visual_acceptance": "not assessed",
        }
        return record
    except Exception as exc:
        record["status"] = "harness_error"
        record["error"] = f"{type(exc).__name__}: {exc}"
        return record
    finally:
        if proc is not None and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=4)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=3)
                except (OSError, subprocess.TimeoutExpired):
                    pass
        for name, path in (("stdout_log", stdout_path), ("stderr_log", stderr_path)):
            if path.exists():
                record[name] = str(path)
                record[name + "_size_bytes"] = path.stat().st_size
        for stream in (stdout_file, stderr_file):
            if stream is not None:
                stream.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path, help="existing ScreeningWorkbench.app bundle")
    parser.add_argument("--evidence-root", required=True, type=Path,
                        help="retained package evidence root containing smoke/synthetic-source-run")
    parser.add_argument("--output", required=True, type=Path, help="diagnostic evidence output directory")
    parser.add_argument("--timeout", type=int, default=120, help="overall diagnostic timeout in seconds")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + max(1, args.timeout)
    evidence: dict = {
        "diagnostic_only": True,
        "no_privacy_prompt_or_permission_database_change": True,
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "source_calibration": SOURCE_CALIBRATION,
        "cases": [],
    }
    if sys.platform != "darwin" or platform.machine() != "arm64":
        evidence["status"] = "unsupported_runner"
        evidence["reason"] = "requires an Apple silicon macOS runner"
        (output / "summary.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": evidence["status"], "summary": str(output / "summary.json")}))
        return 0
    app = args.app.expanduser().resolve()
    info_path = app / "Contents" / "Info.plist"
    if not app.is_dir() or app.suffix != ".app" or not info_path.is_file():
        evidence["status"] = "invalid_app_bundle"
        evidence["reason"] = "--app must be an existing .app with Contents/Info.plist"
        (output / "summary.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        return 0
    with info_path.open("rb") as stream:
        info = plistlib.load(stream)
    executable = app / "Contents" / "MacOS" / str(info.get("CFBundleExecutable") or "")
    evidence["app_identity"] = {
        "bundle_path": str(app),
        "bundle_id": info.get("CFBundleIdentifier"),
        "short_version": info.get("CFBundleShortVersionString"),
        "build_version": info.get("CFBundleVersion"),
        "info_plist_sha256": _sha256(info_path),
        "executable_path": str(executable),
        "executable_sha256": _sha256(executable) if executable.is_file() else None,
    }
    evidence["screen_bounds"] = _screen_bounds(deadline)
    evidence["runner_preflight"] = {"uname": _run(["/usr/bin/uname", "-a"], _bounded(deadline, 5))}
    swift_source = output / "cg_event_click.swift"
    swift_binary = output / "cg_event_click"
    swift_source.write_text(SWIFT_HELPER, encoding="utf-8")
    compiler = _run(["/usr/bin/xcrun", "swiftc", str(swift_source), "-o", str(swift_binary)],
                    _bounded(deadline, 30))
    evidence["swift_helper_compile"] = compiler
    cg_helper = swift_binary if compiler.get("returncode") == 0 and swift_binary.is_file() else None
    if cg_helper:
        access = _run([str(cg_helper), "--access"], _bounded(deadline, 5))
        try:
            access["permissions"] = json.loads(access.get("stdout", "").strip())
        except json.JSONDecodeError:
            pass
        evidence["cg_event_preflight"] = access
    evidence_root = args.evidence_root.expanduser().resolve()
    for method in ("system-events", "cg-event"):
        if time.monotonic() >= deadline:
            evidence["cases"].append({"method": method, "status": "overall_timeout_before_case"})
            continue
        evidence["cases"].append(_run_case(method, executable, info, evidence_root, output,
                                           evidence["screen_bounds"], cg_helper, deadline))
    evidence["finished_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    evidence["status"] = "diagnostics_complete"
    evidence["interpretation_note"] = (
        "Only new extracted synthetic PDF bytes plus a matching Preview AXDocument path count as callback evidence; "
        "a posted click or changed screenshot alone does not establish PDF-open success."
    )
    (output / "summary.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "summary": str(output / "summary.json"),
                      "cases": [{"method": c.get("method"), "status": c.get("status")} for c in evidence["cases"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

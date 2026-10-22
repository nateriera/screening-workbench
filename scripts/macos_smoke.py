#!/usr/bin/env python3
"""Run a synthetic, callback-driven Tk smoke on macOS and write evidence.

This exercises the source app's real action callbacks. It does not claim
human visual acceptance or a complete manual usability review.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path


def minimal_pdf() -> bytes:
    """Return a small valid one-page PDF using only the standard library."""
    content = b"BT /F1 18 Tf 36 95 Td (Synthetic smoke attachment) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 160] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode("ascii"))
        data.extend(body)
        data.extend(b"\nendobj\n")
    xref_offset = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    data.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    data.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return bytes(data)


def capture_screenshot(path: Path, evidence: dict) -> None:
    if sys.platform != "darwin":
        evidence["screenshot"] = {"status": "skipped", "reason": "screencapture is macOS-only"}
        return
    result = subprocess.run(
        ["screencapture", "-x", str(path)], capture_output=True, text=True, check=False
    )
    if result.returncode == 0 and path.is_file() and path.stat().st_size:
        evidence["screenshot"] = {"status": "captured", "path": str(path)}
    else:
        evidence["screenshot"] = {
            "status": "unavailable",
            "returncode": result.returncode,
            "stderr": result.stderr.strip(),
        }


def _widget_status(widget) -> str | None:
    try:
        value = widget.cget("state")
        if isinstance(value, (tuple, list)):
            return " ".join(map(str, value))
        return str(value)
    except Exception:
        return None


def _focus_steps(start, target, limit: int = 200) -> dict:
    """Count enabled, viewable Tk focus-traversal steps between widgets."""
    current = start
    visited = {str(start)}
    path = []
    steps = 0
    for _ in range(limit):
        try:
            candidate = current.tk_focusNext()
        except Exception as exc:
            return {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}", "widgets": path}
        if candidate is None or str(candidate) in visited:
            break
        visited.add(str(candidate))
        try:
            viewable = bool(candidate.winfo_viewable())
        except Exception:
            viewable = False
        state = _widget_status(candidate)
        enabled = state != "disabled" and "disabled" not in (state or "").split()
        path.append({
            "widget": str(candidate),
            "class": candidate.winfo_class(),
            "viewable": viewable,
            "state": state,
            "focus_step": steps + (1 if viewable and enabled else 0),
        })
        if viewable and enabled:
            steps += 1
            if candidate == target:
                return {"status": "captured", "tab_presses": steps, "widgets": path}
        current = candidate
    return {"status": "target_not_reached", "tab_presses": steps, "widgets": path}


def capture_packaged_ui_calibration(root, app) -> dict:
    """Capture source Tk content-relative click points and focus traversal."""
    root.update_idletasks()
    root_x, root_y = root.winfo_rootx(), root.winfo_rooty()
    nav = app.section_nav_buttons["fulltext"]
    report = app.report_list
    attachment = app.attachment_listbox
    open_button = app.open_attachment_btn
    nav_point = (
        nav.winfo_rootx() - root_x + nav.winfo_width() / 2,
        nav.winfo_rooty() - root_y + nav.winfo_height() / 2,
    )
    report_point = (
        report.winfo_rootx() - root_x + min(20, max(8, report.winfo_width() / 4)),
        report.winfo_rooty() - root_y + min(10, max(5, report.winfo_height() / 16)),
    )
    first_to_attachment = _focus_steps(report, attachment)
    attachment_to_open = _focus_steps(attachment, open_button)
    fulltext_screen_point = (root_x + nav_point[0], root_y + nav_point[1])
    report_screen_point = (root_x + report_point[0], root_y + report_point[1])
    screen_width, screen_height = root.winfo_screenwidth(), root.winfo_screenheight()
    points_within_screen = all(
        0 <= point[0] < screen_width and 0 <= point[1] < screen_height
        for point in (fulltext_screen_point, report_screen_point)
    )
    result = {
        "status": "captured",
        "screen": {"width": screen_width, "height": screen_height},
        "tk_root_screen_origin": {"x": root_x, "y": root_y},
        "fulltext_nav_content_point": {"x": round(nav_point[0]), "y": round(nav_point[1])},
        "report_first_row_content_point": {"x": round(report_point[0]), "y": round(report_point[1])},
        "fulltext_nav_screen_point": {"x": round(fulltext_screen_point[0]), "y": round(fulltext_screen_point[1])},
        "report_first_row_screen_point": {"x": round(report_screen_point[0]), "y": round(report_screen_point[1])},
        "click_points_within_screen": points_within_screen,
        "report_list": {
            "viewable": bool(report.winfo_viewable()),
            "size": {"width": report.winfo_width(), "height": report.winfo_height()},
        },
        "attachment_listbox": {
            "viewable": bool(attachment.winfo_viewable()),
            "state": _widget_status(attachment),
        },
        "open_attachment_button": {
            "viewable": bool(open_button.winfo_viewable()),
            "state": _widget_status(open_button),
        },
        "focus_report_to_attachment": first_to_attachment,
        "focus_attachment_to_open_button": attachment_to_open,
    }
    if sys.platform != "darwin":
        result["window_calibration"] = {"status": "unavailable", "reason": "System Events is macOS-only"}
        result["status"] = "incomplete"
        return result
    ax_script = f'''tell application "System Events"
    set p to first process whose unix id is {os.getpid()}
    set frontmost of p to true
    set w to window 1 of p
    set ppos to position of w
    set wsz to size of w
    return ((item 1 of ppos) as text) & tab & ((item 2 of ppos) as text) & tab & ((item 1 of wsz) as text) & tab & ((item 2 of wsz) as text)
end tell'''
    try:
        result_ax = subprocess.run(
            ["osascript", "-e", ax_script], capture_output=True, text=True, check=False, timeout=5,
        )
        coords = [int(v) for v in re.findall(r"-?\d+", result_ax.stdout)]
        if result_ax.returncode == 0 and len(coords) >= 4:
            ax_x, ax_y, width, height = coords[:4]
            result["window_calibration"] = {
                "status": "captured",
                "ax_window_position": {"x": ax_x, "y": ax_y},
                "ax_window_size": {"width": width, "height": height},
                "root_content_offset_from_ax_window": {"x": root_x - ax_x, "y": root_y - ax_y},
                "script": ax_script,
            }
        else:
            result["window_calibration"] = {
                "status": "unavailable",
                "returncode": result_ax.returncode,
                "stdout": result_ax.stdout.strip(),
                "stderr": result_ax.stderr.strip(),
                "script": ax_script,
            }
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["window_calibration"] = {
            "status": "unavailable", "reason": f"{type(exc).__name__}: {exc}", "script": ax_script,
        }
    # On the supported macOS 15 runner, Tk reported a root origin 27 px below
    # the Aqua window frame (x aligned). Keep this as an explicitly labeled
    # fallback when System Events cannot expose the source process window.
    if result["window_calibration"]["status"] != "captured":
        ax_lookup = result["window_calibration"]
        result["window_calibration"] = {
            "status": "fallback",
            "reason": "source process AX window unavailable; runner-observed macOS 15 title-bar offset used for attempt only",
            "ax_lookup": ax_lookup,
            "root_content_offset_from_ax_window": {"x": 0, "y": 27},
            "window_position_from_source_tk_origin": {
                "x": root_x, "y": root_y - 27,
            },
            "source_tk_root_screen_origin": {"x": root_x, "y": root_y},
            "human_or_independent_acceptance_required": True,
        }
    if (
        result["window_calibration"]["status"] not in {"captured", "fallback"}
        or first_to_attachment.get("status") != "captured"
        or attachment_to_open.get("status") != "captured"
        or not points_within_screen
        or not result["report_list"]["viewable"]
        or not result["attachment_listbox"]["viewable"]
        or result["attachment_listbox"]["state"] == "disabled"
        or not result["open_attachment_button"]["viewable"]
        or result["open_attachment_button"]["state"] == "disabled"
    ):
        result["status"] = "incomplete"
    return result


def packaged_launch(app_path: Path, output: Path, evidence: dict) -> None:
    """Seed and launch a .app, then best-effort click Open selected by AppleScript."""
    item: dict = {
        "path": str(app_path),
        "scope": "synthetic packaged launch plus calibrated mouse and keyboard attempt to invoke Open selected",
        "workflow_acceptance": "pending packaged UI attempt",
        "human_visual_acceptance": "not assessed",
    }
    if sys.platform != "darwin":
        item["status"] = "skipped"
        item["reason"] = "packaged launch requires macOS"
        evidence["packaged_app"] = item
        return
    info_path = app_path / "Contents" / "Info.plist"
    if not app_path.is_dir() or app_path.suffix != ".app" or not info_path.is_file():
        item["status"] = "failed"
        item["reason"] = "--packaged-app must point to a .app bundle with Contents/Info.plist"
        evidence["packaged_app"] = item
        return
    import plistlib

    try:
        with info_path.open("rb") as fh:
            info = plistlib.load(fh)
    except Exception as exc:
        item["status"] = "failed"
        item["reason"] = f"could not read app Info.plist: {type(exc).__name__}: {exc}"
        evidence["packaged_app"] = item
        return
    executable_name = info.get("CFBundleExecutable")
    executable = app_path / "Contents" / "MacOS" / str(executable_name or "")
    if not executable_name or not executable.is_file():
        item["status"] = "failed"
        item["reason"] = "CFBundleExecutable is missing from the app bundle"
        evidence["packaged_app"] = item
        return
    isolated_home = output / "packaged-home"
    isolated_home.mkdir(parents=True, exist_ok=True)
    source_app = evidence.get("source_app", {})
    source_db_value = next(
        (entry.get("db_path") for entry in source_app.get("callbacks", []) if entry.get("name") == "project initialization"),
        None,
    )
    source_db = Path(source_db_value) if source_db_value else None
    if source_app.get("status") != "passed" or source_db is None or not source_db.is_file():
        item["status"] = "failed"
        item["reason"] = "source smoke did not leave a verified synthetic database to seed packaged mode"
        item["manual_pending"] = ["Open the packaged app against a disposable project, select the attached PDF, and click Open selected."]
        evidence["packaged_app"] = item
        return
    packaged_db = isolated_home / "screening-workbench-project.sqlite"
    source_attachments = source_db.parent / "attachments"
    packaged_attachments = isolated_home / "attachments"
    try:
        shutil.copy2(source_db, packaged_db)
        if source_attachments.is_dir():
            shutil.copytree(source_attachments, packaged_attachments, dirs_exist_ok=True)
        else:
            raise FileNotFoundError(f"synthetic attachment folder is missing: {source_attachments}")
    except OSError as exc:
        item["status"] = "failed"
        item["reason"] = f"could not seed isolated synthetic project: {type(exc).__name__}: {exc}"
        item["manual_pending"] = ["Open the packaged app against a disposable project, select the attached PDF, and click Open selected."]
        evidence["packaged_app"] = item
        return
    item["seeded_database"] = str(packaged_db)
    item["seeded_attachments"] = str(packaged_attachments)
    env = os.environ.copy()
    env["HOME"] = str(isolated_home)
    env["SCREENING_WORKBENCH_REVIEWER_ID"] = "smoke-reviewer"
    item["executable"] = str(executable)
    item["isolated_home"] = str(isolated_home)
    item["reviewer_id"] = env["SCREENING_WORKBENCH_REVIEWER_ID"]
    calibration = source_app.get("packaged_ui_calibration", {})
    if calibration.get("status") != "captured":
        item["status"] = "failed"
        item["reason"] = "source Tk geometry or focus-chain calibration is incomplete"
        item["source_calibration"] = calibration
        item["manual_pending"] = ["Open Full-text, select the report and attachment, and click Open selected in the packaged app."]
        evidence["packaged_app"] = item
        return
    try:
        focus_to_attachment = calibration["focus_report_to_attachment"]["tab_presses"]
        focus_to_open = calibration["focus_attachment_to_open_button"]["tab_presses"]
        fulltext_point = calibration["fulltext_nav_content_point"]
        report_point = calibration["report_first_row_content_point"]
        content_offset = calibration["window_calibration"]["root_content_offset_from_ax_window"]
        fallback_window_position = calibration["window_calibration"].get("window_position_from_source_tk_origin")
        item["source_calibration"] = calibration
        item["focus_to_attachment_tab_presses"] = focus_to_attachment
        item["focus_to_open_button_tab_presses"] = focus_to_open
    except (KeyError, TypeError) as exc:
        item["status"] = "failed"
        item["reason"] = f"source UI calibration is incomplete: {type(exc).__name__}: {exc}"
        item["manual_pending"] = ["Open Full-text, select the report and attachment, and click Open selected in the packaged app."]
        evidence["packaged_app"] = item
        return
    if focus_to_attachment < 1 or focus_to_open < 1:
        item["status"] = "failed"
        item["reason"] = "calibrated focus traversal did not reach the attachment and Open selected controls"
        item["manual_pending"] = ["Open Full-text, select the report and attachment, and click Open selected in the packaged app."]
        evidence["packaged_app"] = item
        return
    if calibration["window_calibration"]["status"] == "fallback" and not fallback_window_position:
        item["status"] = "failed"
        item["reason"] = "fallback source Tk window position is unavailable"
        item["manual_pending"] = ["Open Full-text, select the report and attachment, and click Open selected in the packaged app."]
        evidence["packaged_app"] = item
        return
    stdout_path = output / "packaged-app.stdout.log"
    stderr_path = output / "packaged-app.stderr.log"
    stdout_file = stdout_path.open("wb")
    stderr_file = stderr_path.open("wb")
    proc = None
    try:
        proc = subprocess.Popen(
            [str(executable)], env=env, cwd=str(output),
            stdout=stdout_file, stderr=stderr_file,
        )
        item["pid"] = proc.pid
        time.sleep(3)
        item["returncode_before_cleanup"] = proc.poll()
        if proc.poll() is None:
            inventory_script = f'''tell application "System Events"
    set p to first process whose unix id is {proc.pid}
    set frontmost of p to true
    delay 0.5
    set win to window 1 of p
    set inventory to name of win & linefeed
    set elements to entire contents of win
    repeat with elementRef in elements
        try
            set inventory to inventory & (role of elementRef as text) & tab & (name of elementRef as text) & linefeed
        end try
    end repeat
    return inventory
end tell'''
            try:
                inventory = subprocess.run(
                    ["osascript", "-e", inventory_script],
                    capture_output=True, text=True, check=False, timeout=5,
                )
                item["accessibility_inventory"] = {
                    "returncode": inventory.returncode,
                    "stdout": inventory.stdout.strip()[:12000],
                    "stderr": inventory.stderr.strip(),
                    "script": inventory_script,
                }
            except (OSError, subprocess.TimeoutExpired) as exc:
                item["accessibility_inventory"] = {
                    "status": "unavailable", "reason": f"{type(exc).__name__}: {exc}",
                    "script": inventory_script,
                }
            capture_screenshot(output / "packaged-app.png", item)
            # Tk exposes Aqua window chrome but not its child controls to
            # System Events. Use source-calibrated clicks and focus traversal.
            ui_script = f'''tell application "System Events"
    set p to first process whose unix id is {proc.pid}
    set frontmost of p to true
    delay 0.5
    set win to window 1 of p
    {f'set position of win to {{{fallback_window_position["x"]}, {fallback_window_position["y"]}}}' if fallback_window_position else ''}
    delay 0.3
    set wpos to position of win
    set navX to (item 1 of wpos) + {content_offset["x"]} + {fulltext_point["x"]}
    set navY to (item 2 of wpos) + {content_offset["y"]} + {fulltext_point["y"]}
    set reportX to (item 1 of wpos) + {content_offset["x"]} + {report_point["x"]}
    set reportY to (item 2 of wpos) + {content_offset["y"]} + {report_point["y"]}
    click at {{navX, navY}}
    delay 0.5
    click at {{reportX, reportY}}
    delay 0.5
    repeat {focus_to_attachment} times
        key code 48
    end repeat
    key code 125
    repeat {focus_to_open} times
        key code 48
    end repeat
    key code 49
    return "OPEN_SELECTED_CLICKED"
end tell'''
            temp_root = Path(tempfile.gettempdir())
            attachment_dirs_before = {
                str(path.resolve())
                for path in temp_root.glob("screening-workbench-attachment-*")
                if path.is_dir()
            }
            preview_before = subprocess.run(
                ["pgrep", "-x", "Preview"], capture_output=True, text=True, check=False,
            )
            try:
                ui_result = subprocess.run(
                    ["osascript", "-e", ui_script],
                    capture_output=True, text=True, check=False, timeout=5,
                )
                item["open_selected_ui_attempt"] = {
                    "returncode": ui_result.returncode,
                    "stdout": ui_result.stdout.strip(),
                    "stderr": ui_result.stderr.strip(),
                    "script": ui_script,
                }
                action_clicked = ui_result.returncode == 0 and "OPEN_SELECTED_CLICKED" in ui_result.stdout
            except (OSError, subprocess.TimeoutExpired) as exc:
                item["open_selected_ui_attempt"] = {
                    "status": "unavailable", "reason": f"{type(exc).__name__}: {exc}", "script": ui_script,
                }
                action_clicked = False
            if action_clicked:
                time.sleep(2)
                extracted_pdfs = []
                for candidate_dir in temp_root.glob("screening-workbench-attachment-*"):
                    if not candidate_dir.is_dir() or str(candidate_dir.resolve()) in attachment_dirs_before:
                        continue
                    candidate_pdf = candidate_dir / "synthetic-attachment.pdf"
                    try:
                        if candidate_pdf.is_file() and candidate_pdf.read_bytes() == minimal_pdf():
                            extracted_pdfs.append(str(candidate_pdf.resolve()))
                    except OSError:
                        continue
                item["attachment_extraction_check"] = {
                    "new_matching_pdf_paths": extracted_pdfs,
                    "exact_synthetic_pdf_bytes_found": bool(extracted_pdfs),
                    "evidence_scope": "new temp directory created during packaged UI attempt contains byte-identical synthetic PDF",
                }
                capture_screenshot(output / "packaged-open-selected.png", item)
                preview_after = subprocess.run(
                    ["pgrep", "-x", "Preview"], capture_output=True, text=True, check=False,
                )
                item["pdf_viewer_process_check"] = {
                    "before_returncode": preview_before.returncode,
                    "before_pids": preview_before.stdout.strip(),
                    "after_returncode": preview_after.returncode,
                    "after_pids": preview_after.stdout.strip(),
                    "after_stderr": preview_after.stderr.strip(),
                    "viewer_process_exists_after_attempt": preview_after.returncode == 0,
                }
                preview_window_script = '''tell application "System Events"
    set p to first process whose name is "Preview"
    return name of every window of p as text
end tell'''
                try:
                    preview_windows = subprocess.run(
                        ["osascript", "-e", preview_window_script],
                        capture_output=True, text=True, check=False, timeout=5,
                    )
                    item["preview_window_check"] = {
                        "returncode": preview_windows.returncode,
                        "stdout": preview_windows.stdout.strip(),
                        "stderr": preview_windows.stderr.strip(),
                        "synthetic_filename_visible": "synthetic-attachment.pdf" in preview_windows.stdout,
                    }
                except (OSError, subprocess.TimeoutExpired) as exc:
                    item["preview_window_check"] = {
                        "status": "unavailable", "reason": f"{type(exc).__name__}: {exc}",
                        "script": preview_window_script,
                    }
                preview_document_script = '''tell application "System Events"
    set p to first process whose name is "Preview"
    set docs to ""
    repeat with w in windows of p
        try
            set docs to docs & (value of attribute "AXDocument" of w as text) & linefeed
        end try
    end repeat
    return docs
end tell'''
                try:
                    preview_documents = subprocess.run(
                        ["osascript", "-e", preview_document_script],
                        capture_output=True, text=True, check=False, timeout=5,
                    )
                    exact_doc_visible = any(
                        Path(pdf_path).parent.name in preview_documents.stdout
                        and Path(pdf_path).name in preview_documents.stdout
                        for pdf_path in extracted_pdfs
                    )
                    item["preview_document_path_check"] = {
                        "returncode": preview_documents.returncode,
                        "stdout": preview_documents.stdout.strip(),
                        "stderr": preview_documents.stderr.strip(),
                        "synthetic_temp_document_visible": exact_doc_visible,
                        "evidence_scope": "Preview AXDocument contains the unique new temp-folder name and synthetic filename",
                    }
                except (OSError, subprocess.TimeoutExpired) as exc:
                    exact_doc_visible = False
                    item["preview_document_path_check"] = {
                        "status": "unavailable", "reason": f"{type(exc).__name__}: {exc}",
                        "script": preview_document_script,
                    }
                app_windows_script = f'''tell application "System Events"
    set p to first process whose unix id is {proc.pid}
    return name of every window of p as text
end tell'''
                try:
                    app_windows = subprocess.run(
                        ["osascript", "-e", app_windows_script],
                        capture_output=True, text=True, check=False, timeout=5,
                    )
                    item["app_window_check"] = {
                        "returncode": app_windows.returncode,
                        "stdout": app_windows.stdout.strip(),
                        "stderr": app_windows.stderr.strip(),
                        "open_failed_window_seen": "Open failed" in app_windows.stdout,
                    }
                except (OSError, subprocess.TimeoutExpired) as exc:
                    item["app_window_check"] = {"status": "unavailable", "reason": f"{type(exc).__name__}: {exc}"}
                passed_evidence = (
                    bool(extracted_pdfs)
                    and preview_after.returncode == 0
                    and exact_doc_visible
                    and not item.get("app_window_check", {}).get("open_failed_window_seen", False)
                )
                item["verification_scope"] = (
                    "app click, byte-identical PDF extraction to a new temp path, Preview process, and matching AXDocument path; not proof of rendered page or human visual acceptance"
                )
                if passed_evidence:
                    item["status"] = "passed"
                    item["manual_pending"] = ["Human visual acceptance of the packaged app and rendered PDF remains pending."]
                else:
                    item["status"] = "failed"
                    item["reason"] = "packaged UI click was not corroborated by a new exact temp PDF, a running Preview process, and a matching Preview AXDocument path"
                    item["manual_pending"] = ["Open the synthetic attachment in the packaged app and confirm the PDF opens and renders in its viewer."]
            else:
                item["status"] = "failed"
                item["reason"] = "AppleScript could not verify that Full-text > Open selected was invoked"
                item["manual_pending"] = ["Open Full-text, select the synthetic report and attached PDF, then click Open selected in the packaged app."]
        else:
            item["status"] = "failed"
            item["reason"] = f"packaged executable exited during launch with status {proc.returncode}"
            item["manual_pending"] = ["Open the packaged app against the seeded synthetic project and open the attached PDF."]
    except Exception as exc:  # evidence should preserve the failure detail
        item["status"] = "failed"
        item["reason"] = f"{type(exc).__name__}: {exc}"
        item.setdefault("manual_pending", ["Open the packaged app against the seeded synthetic project and open the attached PDF."])
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                item["returncode_after_cleanup"] = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                item["returncode_after_cleanup"] = proc.wait(timeout=5)
        stdout_file.close()
        stderr_file.close()
        item["stdout_log"] = str(stdout_path)
        item["stderr_log"] = str(stderr_path)
        if stdout_path.stat().st_size:
            item["stdout_excerpt"] = stdout_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        if stderr_path.stat().st_size:
            item["stderr_excerpt"] = stderr_path.read_text(encoding="utf-8", errors="replace")[-2000:]
    evidence["packaged_app"] = item


def run_source_smoke(output: Path, evidence: dict) -> bool:
    if sys.platform != "darwin":
        evidence["source_app"] = {
            "status": "failed", "reason": "source smoke is intended for a macOS runner"
        }
        return False

    repo_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo_root / "src"))
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, simpledialog
        from screening_workbench import app as app_module
        from screening_workbench import attachments, screening
    except Exception as exc:
        evidence["source_app"] = {"status": "failed", "reason": f"import failed: {exc}"}
        return False

    work = output / "synthetic-source-run"
    work.mkdir(parents=True, exist_ok=True)
    db_path = work / "project.sqlite"
    csv_path = work / "synthetic-records.csv"
    pdf_path = work / "synthetic-attachment.pdf"
    export_path = work / "export"
    export_path.mkdir(exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["title", "authors", "year", "journal", "abstract"])
        writer.writeheader()
        writer.writerows([
            {"title": "Synthetic I decision study", "authors": "Smoke Author", "year": "2024", "journal": "Smoke Journal", "abstract": "Synthetic abstract for include."},
            {"title": "Synthetic M decision study", "authors": "Smoke Author", "year": "2023", "journal": "Smoke Journal", "abstract": "Synthetic abstract for maybe."},
            {"title": "Synthetic E decision study", "authors": "Smoke Author", "year": "2022", "journal": "Smoke Journal", "abstract": "Synthetic abstract for exclude."},
        ])
    pdf_path.write_bytes(minimal_pdf())

    details: dict = {
        "status": "running",
        "evidence_scope": "source callbacks exercised in a live Tk root with synthetic data and dialog selections injected",
        "human_visual_acceptance": "not assessed",
        "callbacks": [],
        "decisions": [],
        "errors": [],
        "processes": [],
    }
    app = None
    root = None
    message_log: list[tuple[str, str]] = []
    original_dialogs = {
        "askopenfilename": filedialog.askopenfilename,
        "askdirectory": filedialog.askdirectory,
        "askstring": simpledialog.askstring,
        "askyesnocancel": messagebox.askyesnocancel,
        "showinfo": messagebox.showinfo,
        "showerror": messagebox.showerror,
        "popen": subprocess.Popen,
    }
    dialogs = {"open_path": str(csv_path)}

    def askopenfilename(**_kwargs):
        return dialogs["open_path"]

    def askdirectory(**_kwargs):
        return str(export_path)

    def askstring(title, _prompt, **_kwargs):
        return "comma" if title == "CSV delimiter" else None

    def askyesnocancel(*_args, **_kwargs):
        return True

    def showinfo(title, message, **_kwargs):
        message_log.append(("info", f"{title}: {message}"))

    def showerror(title, message, **_kwargs):
        message_log.append(("error", f"{title}: {message}"))
        details["errors"].append(f"{title}: {message}")

    def observed_popen(args, *pargs, **kwargs):
        proc = original_dialogs["popen"](args, *pargs, **kwargs)
        try:
            argv = [os.fspath(arg) for arg in args]
        except TypeError:
            argv = [str(args)]
        details["processes"].append({"argv": argv, "pid": proc.pid})
        return proc

    try:
        filedialog.askopenfilename = askopenfilename
        filedialog.askdirectory = askdirectory
        simpledialog.askstring = askstring
        messagebox.askyesnocancel = askyesnocancel
        messagebox.showinfo = showinfo
        messagebox.showerror = showerror
        subprocess.Popen = observed_popen

        root = tk.Tk()
        root.geometry("1280x800+40+40")
        app = app_module.ScreeningWorkbenchApp(root, str(db_path), reviewer_id="smoke-reviewer")
        root.update()
        details["callbacks"].append({"name": "project initialization", "method": "ScreeningWorkbenchApp.__init__", "db_path": str(db_path)})

        app._prompt_csv_mapping = lambda preview: {
            index: field for index, field in enumerate(preview.header_fields)
            if field in {"title", "authors", "year", "journal", "abstract"}
        }
        app.action_import_csv()
        root.update()
        details["callbacks"].append({"name": "CSV import", "method": "action_import_csv", "messages": list(message_log)})
        message_log.clear()

        occurrence_rows = app.conn.execute(
            "SELECT occurrence_id FROM occurrences ORDER BY rowid"
        ).fetchall()
        if len(occurrence_rows) != 3:
            raise RuntimeError(f"expected 3 synthetic occurrences after import, found {len(occurrence_rows)}")

        app._prompt_exclusion_reason = lambda: screening.EXCLUSION_REASONS[0]
        for expected, key, decision in (("I", "i", "include"), ("M", "m", "maybe"), ("E", "e", "exclude")):
            occurrence_id = app.current_occurrence_id
            if occurrence_id is None:
                raise RuntimeError(f"no current occurrence before {expected} decision")
            app.abstract_text.focus_set()
            root.update()
            root.event_generate(f"<KeyPress-{key}>")
            root.update()
            saved = app.conn.execute(
                "SELECT decision FROM screen_votes WHERE occurrence_id=? AND reviewer_id=? AND superseded_at IS NULL",
                (occurrence_id, app.reviewer_id),
            ).fetchone()
            input_method = "tk event_generate"
            if saved is None:
                app._decide(decision)
                saved = app.conn.execute(
                    "SELECT decision FROM screen_votes WHERE occurrence_id=? AND reviewer_id=? AND superseded_at IS NULL",
                    (occurrence_id, app.reviewer_id),
                ).fetchone()
                input_method = "app._decide callback fallback"
            if saved is None or saved["decision"] != decision:
                raise RuntimeError(f"{expected} decision did not persist as {decision}")
            details["decisions"].append({"key": expected, "decision": decision, "occurrence_id": occurrence_id, "input_method": input_method})

        # Promote the included occurrence through the visible Full-text action.
        app._select_section("fulltext")
        root.update()
        app.promote_list.selection_set(0)
        app.promote_list.activate(0)
        app._promote_selected()
        root.update()
        details["callbacks"].append({"name": "promote included record to report", "method": "_promote_selected"})
        if not app._report_ids:
            raise RuntimeError("report promotion produced no report")

        dialogs["open_path"] = str(pdf_path)
        app.report_list.selection_set(0)
        app.report_list.activate(0)
        app._attach_pdf()
        root.update()
        detail = app._report_rows[0]
        attached = attachments.list_attachments(app.conn, detail["report_id"])
        if not attached:
            raise RuntimeError("PDF attachment callback produced no attachment")
        app.attachment_listbox.selection_set(0)
        app.attachment_listbox.activate(0)
        root.update()
        details["packaged_ui_calibration"] = capture_packaged_ui_calibration(root, app)
        calibration_screenshot: dict = {}
        capture_screenshot(output / "source-fulltext-calibration.png", calibration_screenshot)
        details["packaged_ui_calibration"]["screenshot"] = calibration_screenshot.get("screenshot")
        app._open_selected_attachment()
        root.update()
        details["callbacks"].append({
            "name": "attach and open PDF",
            "methods": ["_attach_pdf", "_open_selected_attachment"],
            "attachment_id": attached[0]["attachment_id"],
            "open_processes": [p for p in details["processes"] if p["argv"] and Path(p["argv"][0]).name == "open"],
        })
        if not any(p["argv"] and Path(p["argv"][0]).name == "open" for p in details["processes"]):
            details["errors"].append("attachment open action did not launch a recorded macOS open subprocess")

        app._select_section("prisma")
        root.update()
        app.action_export()
        root.update()
        files = sorted(p.name for p in export_path.iterdir() if p.is_file())
        details["callbacks"].append({"name": "PRISMA export package", "method": "action_export", "files": files})
        if not files:
            raise RuntimeError("export callback wrote no package files")

        root.deiconify()
        root.lift()
        root.focus_force()
        root.update()
        capture_screenshot(output / "source-app.png", details)
        details["message_log"] = message_log
        details["status"] = "passed" if not details["errors"] else "failed"
    except Exception as exc:
        details["status"] = "failed"
        details["reason"] = f"{type(exc).__name__}: {exc}"
        details["traceback"] = traceback.format_exc()
    finally:
        for name, value in original_dialogs.items():
            if name == "popen":
                subprocess.Popen = value
            elif hasattr(filedialog, name):
                setattr(filedialog, name, value)
            elif hasattr(simpledialog, name):
                setattr(simpledialog, name, value)
            elif hasattr(messagebox, name):
                setattr(messagebox, name, value)
        if app is not None:
            try:
                app.conn.close()
            except Exception:
                pass
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass
    evidence["source_app"] = details
    return details["status"] == "passed"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="directory for JSON evidence and screenshots")
    parser.add_argument("--packaged-app", type=Path, help="optional macOS .app bundle launch smoke")
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "platform": sys.platform,
        "python": sys.version,
        "output_dir": str(output),
        "overall_status": "running",
        "limitations": [
            "Tk callbacks run in an automated smoke; human visual acceptance is not implied.",
            "The optional packaged-app path seeds isolated synthetic data and uses source-calibrated mouse and keyboard input; it does not re-import source callbacks from the packaged bundle.",
            "A successful packaged Open selected action plus temp PDF and Preview process evidence is not human visual acceptance of the rendered PDF.",
        ],
    }
    source_ok = run_source_smoke(output, evidence)
    if args.packaged_app:
        packaged_launch(args.packaged_app.expanduser().resolve(), output, evidence)
    packaged_ok = (
        not args.packaged_app
        or evidence.get("packaged_app", {}).get("status") in {"passed", "skipped"}
    )
    evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
    evidence["overall_status"] = "passed" if source_ok and packaged_ok else "failed"
    evidence_path = output / "evidence.json"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"overall_status": evidence["overall_status"], "evidence": str(evidence_path)}, indent=2))
    return 0 if source_ok and packaged_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

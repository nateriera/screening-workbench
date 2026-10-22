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


def packaged_launch(app_path: Path, output: Path, evidence: dict) -> None:
    """Seed and launch a .app, then best-effort click Open selected by AppleScript."""
    item: dict = {
        "path": str(app_path),
        "scope": "synthetic packaged launch plus AppleScript attempt to invoke Full-text > Open selected",
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
            screenshot = output / "packaged-app.png"
            capture_screenshot(screenshot, item)
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
            # Use the app's View menu, then best-effort accessibility clicks
            # on the one synthetic report, its one PDF, and Open selected.
            ui_script = f'''tell application "System Events"
    set p to first process whose unix id is {proc.pid}
    set frontmost of p to true
    delay 0.5
    tell menu bar 1 of p
        click menu bar item "View"
        delay 0.2
        click menu item "Full-text" of menu 1 of menu bar item "View"
    end tell
    delay 1
    set win to window 1 of p
    set reportAndAttachmentLists to every list box of win
    if (count of reportAndAttachmentLists) < 3 then error "Expected promote, report, and attachment list boxes; found " & (count of reportAndAttachmentLists)
    set reportList to item 2 of reportAndAttachmentLists
    set xy to position of reportList
    click at {{(item 1 of xy) + 20, (item 2 of xy) + 10}}
    delay 0.5
    set reportAndAttachmentLists to every list box of win
    set attachmentList to item 3 of reportAndAttachmentLists
    set xy to position of attachmentList
    click at {{(item 1 of xy) + 20, (item 2 of xy) + 8}}
    delay 0.2
    click button "Open selected" of win
    return "OPEN_SELECTED_CLICKED"
end tell'''
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
                capture_screenshot(output / "packaged-open-selected.png", item)
                preview = subprocess.run(
                    ["pgrep", "-fl", "Preview"], capture_output=True, text=True, check=False,
                )
                item["pdf_viewer_process_check"] = {
                    "returncode": preview.returncode,
                    "stdout": preview.stdout.strip(),
                    "stderr": preview.stderr.strip(),
                }
                item["status"] = "passed"
                item["manual_pending"] = ["Human visual acceptance of the packaged app and rendered PDF remains pending."]
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
            "The optional packaged-app path seeds isolated synthetic data and attempts the Full-text > Open selected UI action with AppleScript; the source callbacks are not re-imported from the packaged bundle.",
            "A successful packaged AppleScript click is UI-action evidence, not human visual acceptance of the PDF rendering.",
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

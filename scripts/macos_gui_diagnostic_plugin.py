"""Diagnostic-only Tk root, interpreter, event-loop, and cleanup telemetry."""
from __future__ import annotations

import json
import os
import sys
import time
import tkinter as tk
from pathlib import Path

import pytest

_source_dir = str(Path(__file__).resolve().parents[1] / "src")
if _source_dir not in sys.path:
    sys.path.insert(0, _source_dir)

_directory = Path(os.environ.get("SWB_DIAGNOSTIC_DIR", "artifacts/diagnostics"))
_events_path = _directory / "gui-events.jsonl"
_roots: list[tk.Tk] = []
_apps = []
_configure_counts: dict[int, int] = {}


def _write(event: str, **data) -> None:
    _directory.mkdir(parents=True, exist_ok=True)
    with _events_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": event, "monotonic": time.monotonic(), **data}, ensure_ascii=False) + "\n")
        stream.flush()


def _root_info(root):
    try:
        return {
            "root_id": id(root),
            "tk_id": id(root.tk),
            "exists": bool(int(root.tk.call("winfo", "exists", "."))),
            "state": root.state(),
            "geometry": root.geometry(),
            "actual_size": [root.winfo_width(), root.winfo_height()],
            "screen_size": [root.winfo_screenwidth(), root.winfo_screenheight()],
            "configure_count": _configure_counts.get(id(root.tk), 0),
        }
    except Exception as exc:
        return {"root_id": id(root), "tk_id": id(getattr(root, "tk", None)), "error": repr(exc)}


_original_tk_init = tk.Tk.__init__


def _tracked_tk_init(self, *args, **kwargs):
    _original_tk_init(self, *args, **kwargs)
    _roots.append(self)
    _configure_counts[id(self.tk)] = 0

    def configure_counter(event):
        key = id(self.tk)
        _configure_counts[key] = _configure_counts.get(key, 0) + 1
        count = _configure_counts[key]
        if count == 1 or count % 25 == 0:
            _write("configure", root_id=id(self), tk_id=key, count=count,
                   widget=str(getattr(event, "widget", "")), size=[getattr(event, "width", None), getattr(event, "height", None)])

    try:
        self.bind_all("<Configure>", configure_counter, add="+")
    except Exception as exc:
        _write("configure_binding_error", root_id=id(self), error=repr(exc))
    _write("tk_root_created", default_root_id=id(tk._default_root) if tk._default_root else None,
           roots=[_root_info(root) for root in _roots])


tk.Tk.__init__ = _tracked_tk_init
_original_update = tk.Misc.update


def _tracked_update(self, *args, **kwargs):
    root = self._root()
    start = time.monotonic()
    _write("update_begin", widget=str(self), root_id=id(root), tk_id=id(root.tk),
           default_root_id=id(tk._default_root) if tk._default_root else None,
           configure_count=_configure_counts.get(id(root.tk), 0), roots=[_root_info(item) for item in _roots])
    try:
        return _original_update(self, *args, **kwargs)
    finally:
        _write("update_end", widget=str(self), root_id=id(root), tk_id=id(root.tk),
               elapsed_seconds=round(time.monotonic() - start, 6),
               configure_count=_configure_counts.get(id(root.tk), 0))


tk.Misc.update = _tracked_update

try:
    from screening_workbench.app import ScreeningWorkbenchApp

    _original_app_init = ScreeningWorkbenchApp.__init__

    def _tracked_app_init(self, *args, **kwargs):
        _original_app_init(self, *args, **kwargs)
        _apps.append(self)
        variables = []
        for name, value in vars(self).items():
            if isinstance(value, tk.Variable):
                variables.append({
                    "attribute": name,
                    "variable_name": value._name,
                    "tk_id": id(value._tk),
                    "tk_matches_app_root": value._tk is self.root.tk,
                })
        _write("app_created", app_id=id(self), root_id=id(self.root), tk_id=id(self.root.tk),
               default_root_id=id(tk._default_root) if tk._default_root else None,
               default_root_matches_app_root=tk._default_root is self.root,
               variables=variables)

    ScreeningWorkbenchApp.__init__ = _tracked_app_init
except Exception as exc:
    _write("app_instrumentation_error", error=repr(exc))


def pytest_runtest_logreport(report):
    if not report.failed:
        return
    snapshots = [_root_info(root) for root in _roots]
    apps = []
    for app in _apps:
        item = {"app_id": id(app), "root_id": id(app.root), "tk_id": id(app.root.tk)}
        item["fonts"] = {key: getattr(app, key, None) for key in ("font_ui", "font_reading", "font_mono")}
        try:
            item["duplicate_grid_cells"] = [app.dup_columns.grid_bbox(column, 0, column, 0) for column in range(3)]
        except Exception as exc:
            item["duplicate_grid_cells_error"] = repr(exc)
        for attr in ("dup_queue_card", "dup_compare_card", "dup_resolution_card", "dup_columns", "notebook"):
            widget = getattr(app, attr, None)
            if widget is not None:
                try:
                    item[attr] = {"width": widget.winfo_width(), "height": widget.winfo_height(),
                                  "geometry": widget.winfo_geometry(), "manager": widget.winfo_manager()}
                except Exception as exc:
                    item[attr] = {"error": repr(exc)}
        apps.append(item)
    _write("test_phase_failed", nodeid=report.nodeid, phase=report.when,
           failure=report.longreprtext, roots=snapshots, apps=apps,
           default_root_id=id(tk._default_root) if tk._default_root else None)


@pytest.hookimpl(trylast=True)
def pytest_runtest_logfinish(nodeid, location):
    cleanup = os.environ.get("SWB_CLEANUP_TK_ROOTS") == "1"
    existing = [_root_info(root) for root in _roots]
    _write("test_finished", nodeid=nodeid, cleanup_control=cleanup,
           default_root_id=id(tk._default_root) if tk._default_root else None, roots=existing)
    if cleanup:
        for root in reversed(_roots):
            try:
                root.destroy()
            except Exception as exc:
                _write("cleanup_destroy_error", nodeid=nodeid, root_id=id(root), error=repr(exc))
        _write("cleanup_control_applied", nodeid=nodeid,
               default_root_id=id(tk._default_root) if tk._default_root else None,
               roots=[_root_info(root) for root in _roots])

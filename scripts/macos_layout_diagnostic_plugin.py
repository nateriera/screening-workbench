"""Runtime-only layout controls and measurements; no application patch."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from tkinter import font as tkfont, ttk

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from screening_workbench.app import ScreeningWorkbenchApp

DIRECTORY = Path(os.environ["SWB_LAYOUT_DIR"])
CONTROL = os.environ.get("SWB_LAYOUT_CONTROL", "baseline")
APPS = []
LAST = {}


def widget_info(widget):
    info = {"path": str(widget), "class": widget.winfo_class(),
            "size": [widget.winfo_width(), widget.winfo_height()],
            "requested": [widget.winfo_reqwidth(), widget.winfo_reqheight()],
            "root_xy": [widget.winfo_rootx(), widget.winfo_rooty()],
            "mapped": bool(widget.winfo_ismapped()), "manager": widget.winfo_manager()}
    for key in ("text", "font", "padding", "width", "height", "wraplength", "style"):
        if key in widget.keys():
            info[key] = str(widget.cget(key))[:160]
    if info["manager"] == "pack":
        info["pack"] = {key: str(value) for key, value in widget.pack_info().items()}
    elif info["manager"] == "grid":
        info["grid"] = {key: str(value) for key, value in widget.grid_info().items()}
    return info


def snapshot(app):
    root = app.root
    data = {"control": CONTROL, "root": widget_info(root), "geometry": root.geometry(),
            "state": root.state(), "minimum": root.minsize(), "maximum": root.maxsize(),
            "screen": [root.winfo_screenwidth(), root.winfo_screenheight()],
            "scaling": root.tk.call("tk", "scaling"), "pixels_per_inch": root.winfo_fpixels("1i"),
            "font_ui": app.font_ui, "named": {}, "tree": []}
    font = tkfont.Font(root=root, font=ttk.Style(root).lookup("TButton", "font"))
    data["button_font"] = {"actual": font.actual(), "metrics": font.metrics(),
                           "padding": str(ttk.Style(root).lookup("TButton", "padding"))}
    for name in ("notebook", "maybe_columns", "maybe_queue_card", "maybe_detail_card",
                 "maybe_support_card", "maybe_keyboard_help", "prisma_scroll_canvas",
                 "prisma_flow_card", "prisma_counts_frame", "prisma_flow_heading",
                 "prisma_diagram_canvas", "screen_body", "screen_queue_card",
                 "screen_record_card", "primary_decision_bar"):
        widget = getattr(app, name, None)
        if widget is not None:
            data["named"][name] = widget_info(widget)
    data["maybe_grid_cells"] = [app.maybe_columns.grid_bbox(i, 0) for i in range(3)]

    def walk(widget):
        data["tree"].append(widget_info(widget))
        for child in widget.winfo_children():
            walk(child)
    walk(root)
    return data


ORIGINAL_INIT = ScreeningWorkbenchApp.__init__


def tracked_init(self, *args, **kwargs):
    if CONTROL == "scaling-1.5":
        args[0].tk.call("tk", "scaling", 1.5)
    ORIGINAL_INIT(self, *args, **kwargs)
    APPS.append(self)
    if CONTROL == "maxsize-1280":
        self.root.maxsize(1920, 1200)
        self.root.geometry("1280x800+0+0")
    elif CONTROL == "minsize-1280":
        self.root.maxsize(1920, 1200)
        self.root.minsize(1280, 800)
        self.root.geometry("1280x800+0+0")
    elif CONTROL == "borderless-1280":
        self.root.overrideredirect(True)
        self.root.geometry("1280x800+0+0")
    elif CONTROL == "button-padding-plus2":
        ttk.Style(self.root).configure("TButton", padding=(12, 11))


ScreeningWorkbenchApp.__init__ = tracked_init


def record(root):
    node = os.environ.get("PYTEST_CURRENT_TEST", "unknown").split(" ")[0]
    for app in APPS:
        if root.tk is app.root.tk:
            try:
                data = snapshot(app)
                LAST[node] = data
                path = DIRECTORY / (node.split("::")[-1] + ".json")
                path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            except tk.TclError:
                pass


def wrap_update(original):
    def updated(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        record(self._root())
        return result
    return updated


tk.Misc.update = wrap_update(tk.Misc.update)
tk.Misc.update_idletasks = wrap_update(tk.Misc.update_idletasks)


def pytest_runtest_logreport(report):
    if report.when != "call":
        return
    data = {"nodeid": report.nodeid, "outcome": report.outcome,
            "failure": report.longreprtext if report.failed else None}
    with (DIRECTORY / "outcomes.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(data) + "\n")
    if report.failed and sys.platform == "darwin":
        subprocess.run(["screencapture", "-x", str(DIRECTORY / (report.nodeid.split("::")[-1] + ".png"))],
                       timeout=8, check=False, capture_output=True)

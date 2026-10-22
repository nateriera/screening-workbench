"""Portability regressions without launching external applications."""
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from screening_workbench import app as app_module, theme


def attachment_app(monkeypatch, tmp_path):
    app = app_module.ScreeningWorkbenchApp.__new__(app_module.ScreeningWorkbenchApp)
    app.conn = object()
    app._selected_report_id = lambda: "report"
    app._selected_attachment_id = lambda: "attachment"
    monkeypatch.setattr(app_module.attachments, "list_attachments", lambda *a: [
        {"attachment_id": "attachment", "filename": "file with spaces.pdf"},
    ])
    monkeypatch.setattr(app_module.attachments, "attachment_bytes", lambda *a: b"%PDF-synthetic")
    monkeypatch.setattr(app_module.tempfile, "mkdtemp", lambda **kw: str(tmp_path))
    return app


@pytest.mark.parametrize("platform,opener", [("win32", None), ("darwin", "open"), ("linux", "xdg-open")])
def test_attachment_open_preserves_bytes_and_uses_native_opener(monkeypatch, tmp_path, platform, opener):
    app = attachment_app(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "sys", SimpleNamespace(platform=platform), raising=False)
    opened = []
    monkeypatch.setattr(os, "startfile", lambda path: opened.append(path), raising=False)
    monkeypatch.setattr(app_module, "subprocess", SimpleNamespace(
        run=lambda args, **kw: opened.append((args, kw)),
        SubprocessError=subprocess.SubprocessError,
    ), raising=False)
    app._open_selected_attachment()
    path = str(tmp_path / "file with spaces.pdf")
    assert Path(path).read_bytes() == b"%PDF-synthetic"
    assert opened == ([path] if opener is None else [([opener, path], {"check": True})])


@pytest.mark.parametrize("platform,error", [
    ("win32", OSError("access denied")),
    ("win32", AttributeError("opener unavailable")),
    ("darwin", FileNotFoundError("open unavailable")),
    ("darwin", subprocess.CalledProcessError(1, ["open"])),
    ("linux", subprocess.CalledProcessError(2, ["xdg-open"])),
])
def test_attachment_open_failures_show_existing_dialog(monkeypatch, tmp_path, platform, error):
    app = attachment_app(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module, "sys", SimpleNamespace(platform=platform), raising=False)
    def fail(*a, **kw):
        raise error
    monkeypatch.setattr(os, "startfile", fail, raising=False)
    monkeypatch.setattr(app_module, "subprocess", SimpleNamespace(
        run=fail, SubprocessError=subprocess.SubprocessError,
    ), raising=False)
    dialogs = []
    monkeypatch.setattr(app_module.messagebox, "showerror", lambda *args: dialogs.append(args))
    app._open_selected_attachment()
    assert dialogs == [("Open failed", f"Could not open file with spaces.pdf: {error}")]


@pytest.mark.parametrize("platform,available,expected", [
    ("win32", ("Segoe UI", "Helvetica Neue"), "Segoe UI"),
    ("linux", ("Segoe UI", "Helvetica Neue"), "Segoe UI"),
    ("darwin", ("Segoe UI", "Helvetica Neue"), "Helvetica Neue"),
    ("darwin", ("-apple-system", "Helvetica Neue"), "-apple-system"),
    ("darwin", (), "TkDefaultFont"),
])
def test_ui_font_uses_platform_chain(monkeypatch, platform, available, expected):
    monkeypatch.setattr(theme, "sys", SimpleNamespace(platform=platform), raising=False)
    monkeypatch.setattr(theme.tkfont, "families", lambda root: available)
    assert theme.resolve_font(None, theme.FONT_UI) == expected


@pytest.mark.parametrize("platform,delta,expected", [
    ("win32", 120, -1), ("win32", -240, 2),
    ("darwin", 1, -1), ("darwin", -2, 2), ("darwin", 0, 0),
    ("linux", 120, -1),
])
def test_prisma_wheel_preserves_small_macos_deltas(monkeypatch, platform, delta, expected):
    monkeypatch.setattr(app_module, "sys", SimpleNamespace(platform=platform), raising=False)
    assert app_module._mousewheel_units(delta) == expected

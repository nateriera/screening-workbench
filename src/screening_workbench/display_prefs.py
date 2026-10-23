"""Display preferences the UI honours: theme, reduced motion, high contrast.

The theme (palette) is decided, in order, by the ``SW_THEME`` environment
variable ("light" or "night"), the choice saved from View > Theme, and
Windows' app light/dark mode. It is read once at start-up; a new choice
applies on the next start.

Reduced motion is decided, in order, by the saved View > Reduce motion
choice, the ``SW_REDUCE_MOTION`` environment variable ("1" reduces), and
Windows' "Show animations in Windows" setting. The in-app choice applies
immediately and is saved in the local settings file. High contrast follows
Windows' high-contrast mode. Off Windows these default to the light,
full-motion design.

Settings are a small local JSON file (``SW_SETTINGS_PATH``, or
``%APPDATA%\\Screening Workbench\\settings.json``); nothing leaves the machine.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
from pathlib import Path

SPI_GETHIGHCONTRAST = 0x0042
SPI_GETCLIENTAREAANIMATION = 0x1042
HCF_HIGHCONTRASTON = 0x1
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19

THEME_CHOICES = ("system", "light", "night")

_motion_override: bool | None = None


class _HighContrast(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwFlags", ctypes.c_ulong), ("lpszDefaultScheme", ctypes.c_wchar_p)]


def _windows_animations_enabled() -> bool:
    if sys.platform != "win32":
        return True
    enabled = ctypes.c_int(1)
    if not ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0):
        return True
    return bool(enabled.value)


def _windows_high_contrast() -> bool:
    if sys.platform != "win32":
        return False
    info = _HighContrast(ctypes.sizeof(_HighContrast), 0, None)
    if not ctypes.windll.user32.SystemParametersInfoW(SPI_GETHIGHCONTRAST, info.cbSize, ctypes.byref(info), 0):
        return False
    return bool(info.dwFlags & HCF_HIGHCONTRASTON)


def _windows_prefers_dark() -> bool:
    """Windows' "Choose your default app mode" setting (AppsUseLightTheme = 0)."""
    if sys.platform != "win32":
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
    except OSError:
        return False
    return value == 0


def set_reduced_motion(value: bool | None) -> None:
    """Temporary in-process override; ``None`` returns to saved/environment settings."""
    global _motion_override
    _motion_override = value


def saved_reduced_motion() -> bool | None:
    """The saved View > Reduce motion choice, or ``None`` for system behavior."""
    choice = _load_settings().get("reduce_motion")
    return choice if isinstance(choice, bool) else None


def _write_settings(settings: dict) -> bool:
    path = settings_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        return False
    return True


def save_reduced_motion(value: bool | None) -> bool:
    """Save the View choice and apply it now; ``None`` clears the saved choice."""
    if value is not None and type(value) is not bool:
        raise ValueError(f"Reduced motion must be True, False, or None: {value!r}")
    settings = _load_settings()
    if value is None:
        settings.pop("reduce_motion", None)
    else:
        settings["reduce_motion"] = value
    saved = _write_settings(settings)
    set_reduced_motion(value)
    return saved


def reduced_motion() -> bool:
    if _motion_override is not None:
        return _motion_override
    saved = saved_reduced_motion()
    if saved is not None:
        return saved
    env = os.environ.get("SW_REDUCE_MOTION")
    if env is not None:
        return env == "1"
    return not _windows_animations_enabled()


def high_contrast() -> bool:
    return _windows_high_contrast()


def settings_path() -> Path:
    override = os.environ.get("SW_SETTINGS_PATH")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "Screening Workbench" / "settings.json"


def _load_settings() -> dict:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def saved_theme() -> str:
    """The choice saved from View > Theme: "system", "light" or "night"."""
    choice = _load_settings().get("theme")
    return choice if choice in THEME_CHOICES else "system"


def save_theme(choice: str) -> bool:
    """Save a View > Theme choice; returns False if the file can't be written."""
    if choice not in THEME_CHOICES:
        raise ValueError(f"Unknown theme choice: {choice!r}")
    settings = _load_settings()
    settings["theme"] = choice
    return _write_settings(settings)


def palette() -> str:
    """The palette to build the UI with: "light" or "night"."""
    env = os.environ.get("SW_THEME")
    if env in ("light", "night"):
        return env
    saved = saved_theme()
    if saved in ("light", "night"):
        return saved
    return "night" if _windows_prefers_dark() else "light"


def set_dark_title_bar(window, dark: bool) -> None:
    """Ask Windows to draw the window's title bar dark (or light) to match.
    Best effort: older Windows builds ignore it."""
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id()) or window.winfo_id()
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                return
    except (OSError, AttributeError):
        return

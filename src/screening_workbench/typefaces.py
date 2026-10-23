"""Load the bundled Card Catalogue typefaces for this process only.

The TTFs in ``fonts/`` are unmodified SIL OFL 1.1 static cuts (provenance and
hashes in docs/license-audit.md). ``AddFontResourceExW`` with ``FR_PRIVATE``
makes them visible to this process without installing anything; Tk sees them
in ``font families`` like any installed face. Loading must happen before the
first Tk font lookup. Off Windows, or if a file is refused, the theme's font
stacks fall back to the direction 01 fonts.
"""
from __future__ import annotations

import ctypes
import sys
from pathlib import Path

FONT_DIR = Path(__file__).with_name("fonts")
FR_PRIVATE = 0x10

_loaded: list[str] | None = None


def load_bundled_fonts() -> list[str]:
    """Return the file names GDI accepted; empty off Windows or with no fonts.

    Idempotent per process: private fonts stay loaded until the process exits.
    """
    global _loaded
    if _loaded is not None:
        return _loaded
    if sys.platform != "win32" or not FONT_DIR.is_dir():
        _loaded = []
        return _loaded
    add_font = ctypes.windll.gdi32.AddFontResourceExW
    _loaded = [path.name for path in sorted(FONT_DIR.glob("*.ttf")) if add_font(str(path), FR_PRIVATE, 0)]
    return _loaded

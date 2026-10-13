"""Field Notes theme tokens and ttk clam styling for Screening Workbench.

Keep semantic colors, typography, spacing, geometry, and ttk definitions in
this module. Classic Tk widgets consume the same tokens and option factories.
"""
from __future__ import annotations

import tkinter.font as tkfont
from tkinter import ttk

TTK_BASE_THEME = "clam"

TOKENS = {
    "canvas": "#f5f6f2",
    "surface": "#ffffff",
    "surface_raised": "#fbfcf9",
    "ink": "#1f2a25",
    "muted": "#66736b",
    "line": "#dce3dc",
    "line_strong": "#bdc9bf",
    "accent": "#23634d",
    "accent_hover": "#1c513f",
    "accent_soft": "#e7f0eb",
    "accent_focus": "#174b39",
    "include": "#276149",
    "maybe": "#80540f",
    "exclude": "#a4443e",
    "info": "#3d6476",
    "focus": "#c45a32",
    "include_soft": "#e8f1ec",
    "maybe_soft": "#f6eedf",
    "exclude_soft": "#f7e8e6",
    "info_soft": "#e6eef1",
}

SPACING = {"xs": 4, "base": 8, "sm": 8, "md": 12, "lg": 16, "xl": 24, "padding": 12}
RADII = {"control": 6, "card": 10, "dialog": 14}
CONTROL_MIN_HEIGHT = 40
FOCUS_OUTLINE_WIDTH = 3
CONTROL_BUTTON_PADDING = (SPACING["md"], 9)
CONTROL_COMPACT_PADDING = (10, 9)
CONTROL_FLAT_PADDING = (SPACING["sm"], 8)
ENTRY_PADDING = (SPACING["sm"], 9)
NOTEBOOK_TAB_PADDING = (SPACING["base"], SPACING["base"])
TREE_ROW_HEIGHT = 30
TREE_HEADING_PADDING = (SPACING["sm"], 9)
TREE_QUEUE_ROW_HEIGHT = 36

FONT_UI = "Segoe UI"
FONT_READING = "Iowan Old Style"
FONT_MONO = "Cascadia Code"
FONT_FALLBACKS = {
    FONT_UI: ("Segoe UI", "Aptos", "TkDefaultFont"),
    FONT_READING: ("Iowan Old Style", "Palatino Linotype", "Georgia", "TkTextFont"),
    FONT_MONO: ("Cascadia Code", "Consolas", "TkFixedFont"),
}


def resolve_font(root, family: str) -> str:
    """Return the first installed font from a named Field Notes stack."""
    available = {name.casefold() for name in tkfont.families(root)}
    return next(
        (name for name in FONT_FALLBACKS[family] if name.casefold() in available),
        FONT_FALLBACKS[family][-1],
    )


def focus_outline_options(active: bool) -> dict:
    """Keep tree/list focus visible, distinct from any selected-row fill."""
    if active:
        return {
            "highlightthickness": FOCUS_OUTLINE_WIDTH,
            "highlightbackground": TOKENS["focus"],
            "highlightcolor": TOKENS["focus"],
        }
    return {
        "highlightthickness": 1,
        "highlightbackground": TOKENS["line"],
        "highlightcolor": TOKENS["line"],
    }


def canvas_options(role: str = "page") -> dict:
    """Options for classic Canvas surfaces (page chrome or diagrams)."""
    if role == "page":
        return {"background": TOKENS["canvas"]}
    if role == "diagram":
        return {
            "background": TOKENS["surface"],
            "highlightthickness": 1,
            "highlightbackground": TOKENS["line"],
        }
    raise ValueError(f"Unknown themed Canvas role: {role}")


def diagram_style(root) -> dict:
    """PRISMA vector text uses the same theme tokens/font stack as the shell."""
    ui = resolve_font(root, FONT_UI)
    return {
        "fill": TOKENS["surface"],
        "outline": TOKENS["ink"],
        "outline_width": 2,
        "label_font": (ui, 9),
        "value_font": (ui, 13, "bold"),
        "text_fill": TOKENS["ink"],
    }


def _configure_styles(style: ttk.Style) -> ttk.Style:
    """Configure all clam styles used by app.py in one place."""
    ui = resolve_font(style.master, FONT_UI)
    reading = resolve_font(style.master, FONT_READING)
    style.theme_use(TTK_BASE_THEME)

    style.configure("TFrame", background=TOKENS["canvas"])
    style.configure("TLabel", background=TOKENS["canvas"], foreground=TOKENS["ink"], font=(ui, 10))
    style.configure("TCheckbutton", background=TOKENS["canvas"], foreground=TOKENS["ink"], font=(ui, 10), padding=(8, 9))
    style.configure("TRadiobutton", background=TOKENS["canvas"], foreground=TOKENS["ink"], font=(ui, 10), padding=(8, 9))
    style.configure("TButton", foreground=TOKENS["ink"], padding=CONTROL_BUTTON_PADDING, font=(ui, 10), relief="flat")
    style.map(
        "TButton",
        background=[("pressed", TOKENS["accent"]), ("active", TOKENS["accent_soft"])],
        foreground=[("disabled", TOKENS["muted"]), ("pressed", TOKENS["surface"]), ("active", TOKENS["accent"])],
        focuscolor=[("focus", TOKENS["focus"])],
    )
    style.configure("Primary.TButton", background=TOKENS["accent"], foreground=TOKENS["surface"])
    style.configure(
        "FulltextNext.TButton", background=TOKENS["accent"], foreground=TOKENS["surface"],
        padding=CONTROL_COMPACT_PADDING, font=(ui, 9, "bold"), relief="flat",
    )
    style.map(
        "FulltextNext.TButton",
        background=[("disabled", TOKENS["surface_raised"]), ("active", TOKENS["accent"]), ("!disabled", TOKENS["accent"])],
        foreground=[("disabled", TOKENS["muted"]), ("!disabled", TOKENS["surface"])],
    )
    style.configure(
        "Accent.TButton", background=TOKENS["accent"], foreground=TOKENS["surface"],
        padding=(12, 9), font=(ui, 10, "bold"), relief="flat",
    )
    style.map(
        "Accent.TButton",
        background=[("disabled", TOKENS["surface_raised"]), ("pressed", TOKENS["accent"]), ("active", TOKENS["accent"])],
        foreground=[("disabled", TOKENS["muted"]), ("!disabled", TOKENS["surface"])],
    )
    style.configure(
        "Quiet.TButton", background=TOKENS["surface_raised"], foreground=TOKENS["ink"],
        padding=(12, 9), font=(ui, 10, "bold"), relief="flat",
    )
    style.map(
        "Quiet.TButton",
        background=[("disabled", TOKENS["surface_raised"]), ("active", TOKENS["surface_raised"])],
        foreground=[("disabled", TOKENS["muted"]), ("!disabled", TOKENS["ink"])],
    )
    style.configure("TEntry", fieldbackground=TOKENS["surface"], foreground=TOKENS["ink"], padding=ENTRY_PADDING)
    style.configure("TCombobox", fieldbackground=TOKENS["surface"], foreground=TOKENS["ink"], padding=ENTRY_PADDING)
    style.map("TCombobox", fieldbackground=[("readonly", TOKENS["surface"])], selectbackground=[("readonly", TOKENS["accent"])])
    style.configure("TNotebook", background=TOKENS["canvas"], borderwidth=0, tabmargins=(SPACING["sm"], 0, SPACING["sm"], 0))
    style.configure("TNotebook.Tab", background=TOKENS["surface_raised"], foreground=TOKENS["muted"], padding=NOTEBOOK_TAB_PADDING, font=(ui, 10))
    style.map("TNotebook.Tab", background=[("selected", TOKENS["accent_soft"])], foreground=[("selected", TOKENS["accent"])], expand=[("selected", (0, 0, 0, 2))])
    style.configure("Section.TButton", background=TOKENS["surface"], foreground=TOKENS["muted"], padding=CONTROL_FLAT_PADDING, relief="flat", borderwidth=0)
    style.map("Section.TButton", background=[("active", TOKENS["accent_soft"])], foreground=[("active", TOKENS["accent"])])
    style.configure("SectionHeading.TLabel", background=TOKENS["surface"], foreground=TOKENS["muted"], font=(ui, 9, "bold"))
    style.configure("ActiveSection.TButton", background=TOKENS["surface"], foreground=TOKENS["accent"], padding=CONTROL_FLAT_PADDING, relief="flat", borderwidth=0)
    style.map("ActiveSection.TButton", foreground=[("active", TOKENS["accent"])])
    style.configure("CountBadge.TLabel", background=TOKENS["surface_raised"], foreground=TOKENS["muted"], font=(ui, 9, "bold"))
    style.configure("ChromeMenu.TMenubutton", background=TOKENS["surface_raised"], foreground=TOKENS["ink"], padding=(8, 9), relief="flat")
    style.map("ChromeMenu.TMenubutton", background=[("active", TOKENS["accent_soft"])], foreground=[("active", TOKENS["accent"])])
    style.layout("Shell.TNotebook.Tab", [])
    style.configure("Shell.TNotebook", background=TOKENS["canvas"], borderwidth=0)
    style.configure("Header.TFrame", background=TOKENS["surface"], padding=(16, 8))
    style.configure("Card.TFrame", background=TOKENS["surface"], relief="solid", borderwidth=1)
    style.configure("Header.TLabel", background=TOKENS["surface"], foreground=TOKENS["ink"], font=(ui, 10))
    style.configure("Wordmark.TLabel", background=TOKENS["surface"], foreground=TOKENS["ink"], font=(reading, 16, "bold"))
    style.configure("Status.TFrame", background=TOKENS["surface"])
    style.configure("Status.TLabel", background=TOKENS["surface"], foreground=TOKENS["muted"], font=(ui, 9))
    style.configure("Treeview", background=TOKENS["surface"], fieldbackground=TOKENS["surface"], foreground=TOKENS["ink"], rowheight=TREE_ROW_HEIGHT, bordercolor=TOKENS["line"], font=(ui, 10))
    style.configure("Treeview.Heading", background=TOKENS["surface_raised"], foreground=TOKENS["muted"], font=(ui, 9, "bold"), relief="flat", padding=TREE_HEADING_PADDING)
    style.map("Treeview", background=[("selected", TOKENS["accent_soft"])], foreground=[("selected", TOKENS["accent"])])
    style.configure("Queue.Treeview", rowheight=TREE_QUEUE_ROW_HEIGHT, font=(ui, 10), background=TOKENS["surface"], fieldbackground=TOKENS["surface"])
    style.map("Queue.Treeview", background=[("selected", TOKENS["accent_soft"])], foreground=[("selected", TOKENS["accent"])])
    style.configure("Horizontal.TProgressbar", troughcolor=TOKENS["surface_raised"], background=TOKENS["accent"], bordercolor=TOKENS["line"], lightcolor=TOKENS["accent"], darkcolor=TOKENS["accent"])
    style.configure("Vertical.TScrollbar", background=TOKENS["surface_raised"], troughcolor=TOKENS["canvas"], bordercolor=TOKENS["line"], arrowcolor=TOKENS["muted"])
    style.configure("Horizontal.TScrollbar", background=TOKENS["surface_raised"], troughcolor=TOKENS["canvas"], bordercolor=TOKENS["line"], arrowcolor=TOKENS["muted"])
    style.configure("Canvas.TFrame", background=TOKENS["canvas"])
    return style


def apply_theme(root) -> ttk.Style:
    """Apply theme settings to root options and all clam ttk styles."""
    root.configure(background=TOKENS["canvas"])
    root.option_add("*Text.background", TOKENS["surface"])
    root.option_add("*Text.foreground", TOKENS["ink"])
    root.option_add("*Text.insertBackground", TOKENS["ink"])
    root.option_add("*Text.selectBackground", TOKENS["accent_soft"])
    root.option_add("*Text.selectForeground", TOKENS["ink"])
    root.option_add("*Entry.background", TOKENS["surface"])
    root.option_add("*Entry.foreground", TOKENS["ink"])
    root.option_add("*Listbox.background", TOKENS["surface"])
    root.option_add("*Listbox.foreground", TOKENS["ink"])
    return _configure_styles(ttk.Style(root))


def configure_toplevel(root) -> ttk.Style:
    """Apply ttk styles on newly-created Toplevels using the existing clam theme."""
    return _configure_styles(ttk.Style(root))


# Explicit foreground/background combinations used by the UI. Each listed text
# pair is WCAG AA or better. Soft fills are never used as text grounds; focus
# rust is outline-only and paired with text/selection semantics.
def _linear_channel(value: int) -> float:
    channel = value / 255
    return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4


def contrast_ratio(foreground: str, background: str) -> float:
    """Return WCAG 2.x contrast ratio for two ``#rrggbb`` colors."""
    def luminance(color: str) -> float:
        channels = tuple(_linear_channel(int(color[index:index + 2], 16)) for index in (1, 3, 5))
        return sum(channel * weight for channel, weight in zip(channels, (0.2126, 0.7152, 0.0722)))

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


_CONTRAST_TOKEN_PAIRS = (
    ("ink", "canvas"), ("ink", "surface"), ("ink", "surface_raised"),
    ("muted", "canvas"), ("muted", "surface"), ("muted", "surface_raised"),
    ("accent", "surface"), ("accent", "accent_soft"),
    ("surface", "accent_focus"),
    ("include", "include_soft"), ("maybe", "maybe_soft"),
    ("exclude", "exclude_soft"), ("info", "info_soft"),
)
TEXT_CONTRAST_PAIRS = {
    f"{foreground}.{background}": contrast_ratio(TOKENS[foreground], TOKENS[background])
    for foreground, background in _CONTRAST_TOKEN_PAIRS
}
assert all(value >= 4.5 for value in TEXT_CONTRAST_PAIRS.values())

"""Card Catalogue (direction 02) theme tokens and ttk clam styling for Screening Workbench.

Keep semantic colors, typography, spacing, geometry, and ttk definitions in
this module. Classic Tk widgets consume the same tokens and option factories.

Two palettes share one set of token names: Card Catalogue (light) and Night
Stacks (dark). ``use_palette`` swaps ``TOKENS`` in place; it must run before
any widget is built, because widgets read their colors when created.
"""
from __future__ import annotations

import tkinter.font as tkfont
from tkinter import ttk

TTK_BASE_THEME = "clam"

LIGHT_TOKENS = {
    # Drawer: window chrome (menus, header, section rail, status bar).
    "drawer": "#1d3a32",
    "drawer_raised": "#28493f",
    "drawer_ink": "#f2f0e6",
    "drawer_muted": "#a9bfb4",
    # Highlighter: "now" and "needs you" only; never a decision, never text.
    "signal": "#e8d44d",
    "signal_soft": "#f7efb5",
    "canvas": "#dce2d9",
    "surface": "#fffefa",
    "surface_raised": "#fbfcf9",
    "ink": "#1f2a25",
    "muted": "#55625a",
    "line": "#cbd5cb",
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
    # Decision-button and keycap borders (derived tints, not new hues).
    "include_border": "#a9c8b6",
    "maybe_border": "#dcc39a",
    "exclude_border": "#dfb0ab",
    # PRISMA live-preview graph paper (8px minor, 40px major); never text.
    "grid_minor": "#eef1ea",
    "grid_major": "#dfe5dc",
    # Roles whose light values happen to equal another token but must differ
    # in the dark palette: text on the highlighter, the header's inverse
    # button, and the call-number rule's progress segment.
    "on_signal": "#1f2a25",
    "inverse_bg": "#fffefa",
    "inverse_fg": "#1d3a32",
    "rule_ink": "#1d3a32",
    # Neutral controls (button fill, 3D bevels, troughs). Light values are
    # clam's own defaults, so naming them changes nothing in the light theme.
    "control": "#dcdad5",
    "control_light": "#eeebe7",
    "control_dark": "#cfcdc8",
    "control_border": "#9e9a91",
    "trough": "#bab5ab",
}

# Night Stacks: the catalogue room after hours. Same roles, same contrast
# floor (every pair in _CONTRAST_TOKEN_PAIRS >= 4.5:1, asserted below).
NIGHT_TOKENS = {
    "drawer": "#0f221c",
    "drawer_raised": "#1d3a32",
    "drawer_ink": "#f2f0e6",
    "drawer_muted": "#9fb5aa",
    "signal": "#e8d44d",
    "signal_soft": "#4a4521",
    "canvas": "#141b18",
    "surface": "#1d2622",
    "surface_raised": "#242f2a",
    "ink": "#e4eae3",
    "muted": "#a2b1a8",
    "line": "#34423b",
    "line_strong": "#4b5c53",
    "accent": "#74c7a3",
    "accent_hover": "#8fd5b6",
    "accent_soft": "#22392f",
    "accent_focus": "#a7e0c6",
    "include": "#7fcb9f",
    "maybe": "#e3b65f",
    "exclude": "#f1918a",
    "info": "#90c0d6",
    "focus": "#f0905c",
    "include_soft": "#1e3328",
    "maybe_soft": "#382e18",
    "exclude_soft": "#3b2523",
    "info_soft": "#1d2f37",
    "include_border": "#3f6b52",
    "maybe_border": "#7a5f2a",
    "exclude_border": "#7f4640",
    "grid_minor": "#212b27",
    "grid_major": "#2a3631",
    "on_signal": "#1b1d10",
    "inverse_bg": "#f2f0e6",
    "inverse_fg": "#0f221c",
    "rule_ink": "#74c7a3",
    "control": "#2c3833",
    "control_light": "#36443e",
    "control_dark": "#222c28",
    "control_border": "#4b5c53",
    "trough": "#1a221f",
}

PALETTES = {"light": LIGHT_TOKENS, "night": NIGHT_TOKENS}
PALETTE_LABELS = {"light": "Card Catalogue (light)", "night": "Night Stacks (dark)"}

TOKENS = dict(LIGHT_TOKENS)
CURRENT_PALETTE = "light"


def use_palette(name: str) -> None:
    """Swap every token to the named palette, keeping the same dict object
    so modules holding ``theme.TOKENS`` see the change."""
    global CURRENT_PALETTE
    TOKENS.clear()
    TOKENS.update(PALETTES[name])
    CURRENT_PALETTE = name

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

# Bundled faces first (typefaces.load_bundled_fonts), then the direction 01
# stacks, so a failed private load degrades to the previous look.
FONT_UI = "Atkinson Hyperlegible Next"
FONT_READING = "Newsreader 16pt"
FONT_TITLE = "Newsreader 16pt Medium"
FONT_MONO = "Atkinson Hyperlegible Mono"
FONT_FALLBACKS = {
    FONT_UI: ("Atkinson Hyperlegible Next", "Segoe UI", "Aptos", "TkDefaultFont"),
    FONT_READING: ("Newsreader 16pt", "Iowan Old Style", "Palatino Linotype", "Georgia", "TkTextFont"),
    FONT_TITLE: ("Newsreader 16pt Medium", "Newsreader 16pt", "Iowan Old Style", "Palatino Linotype", "TkTextFont"),
    FONT_MONO: ("Atkinson Hyperlegible Mono", "Cascadia Code", "Consolas", "TkFixedFont"),
}


def resolve_font(root, family: str) -> str:
    """Return the first available font from a named stack (bundled faces first)."""
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
    title = resolve_font(style.master, FONT_TITLE)
    mono = resolve_font(style.master, FONT_MONO)
    style.theme_use(TTK_BASE_THEME)

    # Root defaults for every ttk element clam would otherwise paint with its
    # own light greys (button fill, bevels, troughs, entry selection).
    style.configure(
        ".", background=TOKENS["control"], foreground=TOKENS["ink"], bordercolor=TOKENS["control_border"],
        lightcolor=TOKENS["control_light"], darkcolor=TOKENS["control_dark"], troughcolor=TOKENS["trough"],
        fieldbackground=TOKENS["surface"], selectbackground=TOKENS["accent_soft"], selectforeground=TOKENS["ink"],
        insertcolor=TOKENS["ink"], arrowcolor=TOKENS["ink"],
    )
    # clam's own state map paints disabled and hovered elements light grey
    # (and disabled text #999999); route those states through the tokens.
    style.map(
        ".", background=[("disabled", TOKENS["control"]), ("active", TOKENS["control_light"])],
        foreground=[("disabled", TOKENS["muted"])], fieldbackground=[("disabled", TOKENS["control"])],
    )
    style.configure("TFrame", background=TOKENS["canvas"])
    style.configure("TLabel", background=TOKENS["canvas"], foreground=TOKENS["ink"], font=(ui, 10))
    style.configure("TCheckbutton", background=TOKENS["canvas"], foreground=TOKENS["ink"], font=(ui, 10), padding=(8, 9))
    style.configure("TRadiobutton", background=TOKENS["canvas"], foreground=TOKENS["ink"], font=(ui, 10), padding=(8, 9))
    # clam paints disabled/hovered toggles with its own greys; keep them on
    # the surface they sit on, with the accent tint for hover.
    for toggle in ("TCheckbutton", "TRadiobutton"):
        style.map(toggle, background=[("disabled", TOKENS["canvas"]), ("active", TOKENS["accent_soft"])])
        style.configure(toggle, indicatorbackground=TOKENS["surface"], indicatorforeground=TOKENS["ink"],
                        upperbordercolor=TOKENS["control_border"], lowerbordercolor=TOKENS["control_border"])
        style.map(toggle, indicatorbackground=[("pressed", TOKENS["control"]), ("disabled", TOKENS["control"])])
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
    style.map(
        "TCombobox", fieldbackground=[("readonly", TOKENS["surface"])], selectbackground=[("readonly", TOKENS["accent"])],
        background=[("pressed", TOKENS["control_light"]), ("active", TOKENS["control_light"])],
    )
    style.configure("TNotebook", background=TOKENS["canvas"], borderwidth=0, tabmargins=(SPACING["sm"], 0, SPACING["sm"], 0))
    style.configure("TNotebook.Tab", background=TOKENS["surface_raised"], foreground=TOKENS["muted"], padding=NOTEBOOK_TAB_PADDING, font=(ui, 10))
    style.map("TNotebook.Tab", background=[("selected", TOKENS["accent_soft"])], foreground=[("selected", TOKENS["accent"])], expand=[("selected", (0, 0, 0, 2))])
    style.configure("Section.TButton", background=TOKENS["drawer"], foreground=TOKENS["drawer_muted"], padding=CONTROL_FLAT_PADDING, relief="flat", borderwidth=0, font=(ui, 10))
    style.map("Section.TButton", background=[("active", TOKENS["drawer_raised"])], foreground=[("active", TOKENS["drawer_ink"])])
    style.configure("SectionHeading.TLabel", background=TOKENS["surface"], foreground=TOKENS["muted"], font=(ui, 9, "bold"))
    style.configure("ActiveSection.TButton", background=TOKENS["drawer"], foreground=TOKENS["drawer_ink"], padding=CONTROL_FLAT_PADDING, relief="flat", borderwidth=0, font=(ui, 10, "bold"))
    style.map("ActiveSection.TButton", background=[("active", TOKENS["drawer_raised"])], foreground=[("active", TOKENS["drawer_ink"])])
    # Count badges: zero is quiet text, nonzero a raised chip, and queues
    # that need a person (Conflicts, Duplicates) the highlighter.
    style.configure("CountBadge.TLabel", background=TOKENS["drawer_raised"], foreground=TOKENS["drawer_ink"], font=(mono, 9, "bold"))
    style.configure("CountBadgeZero.TLabel", background=TOKENS["drawer"], foreground=TOKENS["drawer_muted"], font=(mono, 9))
    style.configure("CountBadgeAttention.TLabel", background=TOKENS["signal"], foreground=TOKENS["on_signal"], font=(mono, 9, "bold"))
    # Menus are words, not dropdown fields: drop clam's indicator element
    # and its 11-character minimum width, but keep the focus element.
    style.layout("ChromeMenu.TMenubutton", [("Menubutton.border", {"sticky": "nswe", "children": [
        ("Menubutton.focus", {"sticky": "nswe", "children": [
            ("Menubutton.padding", {"sticky": "we", "children": [("Menubutton.label", {"sticky": ""})]}),
        ]}),
    ]})])
    style.configure("ChromeMenu.TMenubutton", background=TOKENS["drawer"], foreground=TOKENS["drawer_ink"], padding=(10, 6), relief="flat", width=0, font=(ui, 10))
    style.map("ChromeMenu.TMenubutton", background=[("active", TOKENS["drawer_raised"])], foreground=[("active", TOKENS["drawer_ink"])])
    style.layout("Shell.TNotebook.Tab", [])
    style.configure("Shell.TNotebook", background=TOKENS["canvas"], borderwidth=0)
    style.configure("Header.TFrame", background=TOKENS["drawer"], padding=(16, 8))
    style.configure("Drawer.TFrame", background=TOKENS["drawer"])
    style.configure("Card.TFrame", background=TOKENS["surface"], relief="solid", borderwidth=1)
    style.configure("Header.TLabel", background=TOKENS["drawer"], foreground=TOKENS["drawer_ink"], font=(ui, 10))
    style.configure("Wordmark.TLabel", background=TOKENS["drawer"], foreground=TOKENS["drawer_ink"], font=(title, 17))
    style.configure("Status.TFrame", background=TOKENS["drawer"])
    style.configure("Status.TLabel", background=TOKENS["drawer"], foreground=TOKENS["drawer_muted"], font=(ui, 9))
    style.configure("Drawer.TSeparator", background=TOKENS["drawer_raised"])
    # The header's primary action: an inverse button (light on the dark
    # drawer in both palettes), because evergreen on the drawer would vanish.
    style.configure(
        "Inverse.TButton", background=TOKENS["inverse_bg"], foreground=TOKENS["inverse_fg"],
        padding=(14, 9), font=(ui, 10, "bold"), relief="flat",
    )
    style.map(
        "Inverse.TButton",
        background=[("pressed", TOKENS["signal"]), ("active", TOKENS["signal"])],
        foreground=[("disabled", TOKENS["muted"]), ("active", TOKENS["on_signal"]),
                    ("pressed", TOKENS["on_signal"]), ("!disabled", TOKENS["inverse_fg"])],
    )
    style.configure("Treeview", background=TOKENS["surface"], fieldbackground=TOKENS["surface"], foreground=TOKENS["ink"], rowheight=TREE_ROW_HEIGHT, bordercolor=TOKENS["line"], font=(ui, 10))
    style.configure("Treeview.Heading", background=TOKENS["surface_raised"], foreground=TOKENS["muted"], font=(ui, 9, "bold"), relief="flat", padding=TREE_HEADING_PADDING)
    style.map("Treeview", background=[("selected", TOKENS["accent_soft"])], foreground=[("selected", TOKENS["accent"])])
    style.configure("Queue.Treeview", rowheight=TREE_QUEUE_ROW_HEIGHT, font=(ui, 10), background=TOKENS["surface"], fieldbackground=TOKENS["surface"])
    style.map("Queue.Treeview", background=[("selected", TOKENS["accent_soft"])], foreground=[("selected", TOKENS["accent"])])
    style.configure("Horizontal.TProgressbar", troughcolor=TOKENS["surface_raised"], background=TOKENS["accent"], bordercolor=TOKENS["line"], lightcolor=TOKENS["accent"], darkcolor=TOKENS["accent"])
    style.configure("Vertical.TScrollbar", background=TOKENS["surface_raised"], troughcolor=TOKENS["canvas"], bordercolor=TOKENS["line"], arrowcolor=TOKENS["muted"])
    style.configure("Horizontal.TScrollbar", background=TOKENS["surface_raised"], troughcolor=TOKENS["canvas"], bordercolor=TOKENS["line"], arrowcolor=TOKENS["muted"])
    style.configure("Canvas.TFrame", background=TOKENS["canvas"])
    # Columns that sit flat on the desk beside the one raised record card.
    style.configure("Desk.TFrame", background=TOKENS["canvas"], relief="flat", borderwidth=0)
    # Exclusion reasons while E is pending: the list the next key picks from.
    style.configure("ArmedReason.TFrame", background=TOKENS["exclude_soft"])
    style.configure("ArmedReason.TLabel", background=TOKENS["exclude_soft"], foreground=TOKENS["ink"])
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
    root.option_add("*Listbox.selectBackground", TOKENS["accent_soft"])
    root.option_add("*Listbox.selectForeground", TOKENS["ink"])
    # Classic widgets created without explicit colors (dialog windows, plain
    # frames and labels) would otherwise take Windows' light system colors.
    root.option_add("*Toplevel.background", TOKENS["canvas"])
    root.option_add("*Frame.background", TOKENS["canvas"])
    root.option_add("*Label.background", TOKENS["canvas"])
    root.option_add("*Label.foreground", TOKENS["ink"])
    root.option_add("*Canvas.background", TOKENS["canvas"])
    root.option_add("*highlightBackground", TOKENS["canvas"])
    root.option_add("*Entry.insertBackground", TOKENS["ink"])
    root.option_add("*TCombobox*Listbox.background", TOKENS["surface"])
    root.option_add("*TCombobox*Listbox.foreground", TOKENS["ink"])
    root.option_add("*TCombobox*Listbox.selectBackground", TOKENS["accent_soft"])
    root.option_add("*TCombobox*Listbox.selectForeground", TOKENS["ink"])
    root.option_add("*Menu.background", TOKENS["surface"])
    root.option_add("*Menu.foreground", TOKENS["ink"])
    root.option_add("*Menu.activeBackground", TOKENS["accent_soft"])
    root.option_add("*Menu.activeForeground", TOKENS["accent"])
    root.option_add("*Menu.relief", "flat")
    return _configure_styles(ttk.Style(root))


_SURFACE_MATCHED_CLASSES = ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton")


def _painted_background(style: ttk.Style, widget) -> str:
    if isinstance(widget, ttk.Widget):
        if "background" in widget.keys() and str(widget.cget("background")):
            return str(widget.cget("background"))
        return style.lookup(widget.cget("style") or widget.winfo_class(), "background")
    try:
        return str(widget.cget("background"))
    except Exception:
        return ""


def match_surface_backgrounds(root) -> None:
    """Plain ttk frames, labels and toggles sitting on a surface (cards,
    header, record) paint that surface too, so no canvas-colored band or
    tinted middle panel shows inside a white card. Each restyled widget
    gets a ``Surface.``-prefixed child of its own style, keeping its font,
    padding and foreground. (Not ``Card.``: ``Card.TFrame`` is the
    bordered card itself.)"""
    style = ttk.Style(root)
    surface = TOKENS["surface"]
    pending = [root]
    while pending:
        widget = pending.pop()
        on_surface = _painted_background(style, widget) == surface
        for child in widget.winfo_children():
            if (
                on_surface
                and isinstance(child, ttk.Widget)
                and child.winfo_class() in _SURFACE_MATCHED_CLASSES
                and _painted_background(style, child) != surface
            ):
                current = child.cget("style") or child.winfo_class()
                surface_style = current if current.startswith("Surface.") else f"Surface.{current}"
                style.configure(surface_style, background=surface)
                if child.winfo_class() in ("TCheckbutton", "TRadiobutton"):
                    style.map(surface_style, background=[("disabled", surface), ("active", TOKENS["accent_soft"])])
                child.configure(style=surface_style)
            pending.append(child)


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
    ("surface", "accent_focus"), ("surface", "accent"),
    ("drawer_ink", "drawer"), ("drawer_muted", "drawer"),
    ("drawer_ink", "drawer_raised"), ("drawer_muted", "drawer_raised"),
    ("inverse_fg", "inverse_bg"), ("on_signal", "signal"), ("ink", "signal_soft"),
    ("include", "include_soft"), ("maybe", "maybe_soft"),
    ("exclude", "exclude_soft"), ("info", "info_soft"),
    ("include", "surface"), ("maybe", "surface"), ("exclude", "surface"), ("info", "surface"),
    ("ink", "control"), ("ink", "accent_soft"), ("ink", "exclude_soft"),
)
PALETTE_CONTRAST = {
    name: {
        f"{foreground}.{background}": contrast_ratio(palette[foreground], palette[background])
        for foreground, background in _CONTRAST_TOKEN_PAIRS
    }
    for name, palette in PALETTES.items()
}
TEXT_CONTRAST_PAIRS = PALETTE_CONTRAST["light"]
assert set(LIGHT_TOKENS) == set(NIGHT_TOKENS)
assert all(value >= 4.5 for ratios in PALETTE_CONTRAST.values() for value in ratios.values())

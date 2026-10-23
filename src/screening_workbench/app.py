"""Screening Workbench v1 desktop shell: Tkinter UI wiring the domain modules together.

Keyboard-first screening per screening-workflow spec §4: single-keystroke
decisions (i=include, m=maybe, e=exclude -> a numbered 1-7 taxonomy
picker), auto-advance to next undecided. A tabbed notebook covers the v1
workflow end to end: Screening, Duplicates, Conflicts, Full-text, Studies.
The Screening tab also implements most of docs/ui-reference-screening.md:
search + year/journal/batch facets, an "undecided only" toggle (on by
default), a visible keyboard focus ring on the record pane, and a
blind-safe "your recent decisions" panel. A persistent status bar always
shows the project's current blind-mode state. See the "Known v1 UI gaps"
note at the bottom for what remains intentionally unimplemented (bulk
actions, accessibility pass beyond the focus ring, the reference's
section-nav/queue-list/status-bar chrome). Those are documented gaps,
not silently dropped behavior.
"""
from __future__ import annotations

import datetime
import json
import math
import os
import shutil
import sqlite3
import tempfile
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk

from screening_workbench import (
    attachments, db, dedup, display_prefs, export, packets, prisma, reports, roles, screening, studies, theme, typefaces,
)
from screening_workbench.importers import CANONICAL_FIELDS
from screening_workbench.importers.csv_importer import commit_csv_import, preview_csv
from screening_workbench.importers.limits import ImportLimitError, read_limited_bytes, read_limited_text
from screening_workbench.importers.pubmed_xml_importer import commit_pubmed_xml_import, parse_pubmed_xml
from screening_workbench.importers.ris_importer import commit_ris_import, parse_ris

REVIEWER_ID_ENV = "SCREENING_WORKBENCH_REVIEWER_ID"
CSV_MAPPING_FIELDS = ("title", "authors", "year", "journal", "doi", "abstract", "keywords")
CSV_MAPPING_CHOICES = ("— skip —", *CSV_MAPPING_FIELDS)


def validate_csv_mapping(mapping: dict[int, str]) -> str | None:
    """Return a user-facing validation error, or None for a usable map."""
    values = list(mapping.values())
    if "title" not in values:
        return "Map a column to title before importing."
    if len(values) != len(set(values)):
        return "More than one column maps to the same canonical field. Choose one column per field or skip the extra column."
    invalid = set(values) - set(CSV_MAPPING_FIELDS)
    if invalid:
        return f"Unsupported field mapping: {', '.join(sorted(invalid))}."
    return None


class _CallNumberRule(tk.Canvas):
    """The record card's catalogue double rule, doubling as its progress bar.

    Keeps ttk.Progressbar's ``maximum``/``value`` interface. The label above
    states the same position in text, so the rule is a second cue, never
    the only one."""

    def __init__(self, master):
        super().__init__(master, height=6, highlightthickness=0, borderwidth=0, background=theme.TOKENS["surface"])
        self._maximum = 1.0
        self._value = 0.0
        self._shown = 0.0  # fraction currently drawn; trails the value while tweening
        self._tween_job = None
        self.bind("<Configure>", lambda _event: self._redraw())
        self.bind("<Destroy>", lambda _event: self._cancel_tween(), add="+")

    def _cancel_tween(self) -> None:
        if self._tween_job is not None:
            try:
                self.after_cancel(self._tween_job)
            except tk.TclError:
                pass
            self._tween_job = None

    def configure(self, cnf=None, **kw):
        moved = "maximum" in kw or "value" in kw
        if "maximum" in kw:
            self._maximum = max(float(kw.pop("maximum")), 1.0)
        if "value" in kw:
            self._value = float(kw.pop("value"))
        result = super().configure(cnf, **kw) if (cnf or kw) else None
        if moved:
            self._move_to(min(self._value / self._maximum, 1.0))
        else:
            self._redraw()
        return result

    _TWEEN_STEPS = 9  # ~140 ms at 16 ms per frame

    def _move_to(self, target: float) -> None:
        """Ease the dark segment to its new length (ease-out, ~140 ms).
        Jumps straight there under reduced motion or while hidden."""
        self._cancel_tween()
        if display_prefs.reduced_motion() or not self.winfo_ismapped():
            self._shown = target
            self._redraw()
            return
        start = self._shown

        def step(n: int = 1) -> None:
            try:
                eased = 1 - (1 - n / self._TWEEN_STEPS) ** 3
                self._shown = start + (target - start) * eased
                self._redraw()
                self._tween_job = self.after(16, step, n + 1) if n < self._TWEEN_STEPS else None
            except tk.TclError:  # widget destroyed mid-tween
                self._tween_job = None

        step()

    config = configure

    def __getitem__(self, key):
        if key == "maximum":
            return self._maximum
        if key == "value":
            return self._value
        return super().__getitem__(key)

    def _redraw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 1)
        filled = round(width * self._shown)
        self.create_rectangle(0, 0, width, 2, fill=theme.TOKENS["line"], width=0)
        self.create_rectangle(0, 0, filled, 2, fill=theme.TOKENS["rule_ink"], width=0, tags="progress")
        self.create_rectangle(0, 5, width, 6, fill=theme.TOKENS["line"], width=0)


class _KeycapButton(tk.Frame):
    """A decision button drawn as a keycap beside its word.

    Keeps the parts of tk.Button the app relies on: ``invoke()``,
    ``cget("text")`` (key and word together), activation with Space or
    Return while focused, and a visible focus ring. It is built from
    labels rather than an image so the keycap scales with the font at any
    Tk zoom level."""

    def __init__(
        self, master, *, key: str, word: str, decision: str, command,
        font_ui: str, font_mono: str, font_size: int = 10,
        vertical_padding: int = 10, keycap_padx: int = 6,
    ):
        soft = theme.TOKENS[f"{decision}_soft"]
        ink = theme.TOKENS[decision]
        self._decision = decision
        self._border = theme.TOKENS[f"{decision}_border"]
        self._enabled = True
        super().__init__(master, background=soft, takefocus=1, cursor="hand2", relief="solid", borderwidth=1)
        self._command = command
        self._text = f"{key}  {word}"
        self._focused = False
        self._armed = False
        inner = tk.Frame(self, background=soft)
        self._inner = inner
        inner.pack(expand=True, pady=vertical_padding)
        self.keycap = tk.Label(
            inner, text=key, font=(font_mono, font_size, "bold"), background=theme.TOKENS["surface"], foreground=ink,
            padx=keycap_padx, pady=0, highlightthickness=1, highlightbackground=self._border, highlightcolor=self._border,
        )
        self.keycap.pack(side="left")
        self.label = tk.Label(inner, text=word, font=(font_ui, font_size, "bold"), background=soft, foreground=ink)
        self.label.pack(side="left", padx=(8, 0))
        for widget in (self, inner, self.keycap, self.label):
            widget.bind("<Button-1>", lambda _event: self.invoke())
        for sequence in ("<Key-space>", "<Return>"):
            self.bind(sequence, self._on_activate_key)
        self.bind("<FocusIn>", lambda _event: self._set_focused(True))
        self.bind("<FocusOut>", lambda _event: self._set_focused(False))
        self._draw_ring()

    def invoke(self):
        if self._enabled:
            return self._command()
        return None

    def cget(self, key):
        if key == "text":
            return self._text
        if key == "state":
            return "normal" if self._enabled else "disabled"
        if key in ("fg", "foreground"):
            return self.label.cget("foreground")
        if key in ("bg", "background"):
            return super().cget("background")
        return super().cget(key)

    __getitem__ = cget

    def set_enabled(self, enabled: bool) -> None:
        """Apply the palette's enabled or disabled decision-button colors."""
        self._enabled = bool(enabled)
        if not self._enabled:
            self._focused = False
            self._armed = False
        background = theme.TOKENS[f"{self._decision}_soft"] if self._enabled else theme.TOKENS["surface_raised"]
        foreground = theme.TOKENS[self._decision] if self._enabled else theme.TOKENS["muted"]
        self._border = theme.TOKENS[f"{self._decision}_border"] if self._enabled else theme.TOKENS["line"]
        self.configure(
            background=background, cursor="hand2" if self._enabled else "arrow",
            takefocus=1 if self._enabled else 0,
            relief="solid" if self._enabled else "flat",
        )
        self._inner.configure(background=background)
        self.keycap.configure(
            background=theme.TOKENS["surface"], foreground=foreground,
            highlightbackground=self._border, highlightcolor=self._border,
        )
        self.label.configure(background=background, foreground=foreground)
        self._draw_ring()

    def set_armed(self, armed: bool) -> None:
        """Ring the button while its follow-up choice (a reason) is pending."""
        self._armed = bool(armed and self._enabled)
        self._draw_ring()

    def _on_activate_key(self, _event):
        self.invoke()
        return "break"

    def _set_focused(self, focused: bool) -> None:
        self._focused = focused
        self._draw_ring()

    def _draw_ring(self) -> None:
        active = self._enabled and (self._focused or self._armed)
        ring = theme.TOKENS["focus"] if active else self._border
        self.configure(
            highlightthickness=theme.FOCUS_OUTLINE_WIDTH if active else 1,
            highlightbackground=ring, highlightcolor=ring,
        )


class ScreeningWorkbenchApp:
    """Owns the Tk root and all widgets. Business logic always goes
    through the screening_workbench.* modules -- this class never touches SQL or the
    event log directly."""

    def __init__(self, root: tk.Tk, db_path: str, reviewer_id: str = "reviewer1"):
        self.root = root
        self.reviewer_id = reviewer_id
        self.db_path = db_path
        self.conn = db.connect(db_path)
        if roles.get_owner(self.conn) is None:
            roles.set_owner(self.conn, reviewer_id)

        self.root.title("Screening Workbench -- systematic review screening")
        self.root.geometry("1280x800")
        # Pick the palette before any widget exists: widgets read their
        # colors when they are created.
        theme.use_palette(display_prefs.palette())
        typefaces.load_bundled_fonts()
        self.font_ui = theme.resolve_font(self.root, theme.FONT_UI)
        self.font_reading = theme.resolve_font(self.root, theme.FONT_READING)
        self.font_title = theme.resolve_font(self.root, theme.FONT_TITLE)
        self.font_mono = theme.resolve_font(self.root, theme.FONT_MONO)
        # Decision stamp state: a decision's queue advance can wait behind
        # its 170 ms stamp; anything that acts on the record flushes it first.
        self._pending_advance = None
        self._stamp = None
        self._stamp_settle_job = None
        # Closing mid-stamp must not leave timers that fire into a dead window.
        self.root.bind("<Destroy>", self._cancel_motion_on_close, add="+")
        self._apply_style()

        self._build_menu()
        self._build_menubar_chrome()
        self._build_header()
        self._build_status_bar()

        self.section_nav = ttk.Frame(self.root, padding=(8, 0), style="Drawer.TFrame")
        self.section_nav.pack(fill="x", side="top")
        self.notebook = ttk.Notebook(self.root, style="Shell.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        self._build_screening_tab()
        self._build_maybe_tab()
        self._build_duplicates_tab()
        self._build_conflicts_tab()
        self._build_fulltext_tab()
        self._build_studies_tab()
        self._build_prisma_tab()
        self._tab_ids = ["screening", "maybe", "duplicates", "conflicts", "fulltext", "studies", "prisma"]

        self._build_section_nav()

        self._bind_keys()
        self.refresh_all_tabs()
        display_prefs.set_dark_title_bar(self.root, theme.CURRENT_PALETTE == "night")

    def _apply_style(self) -> None:
        """Apply docs/design-system.md tokens to ttk widgets. Tk's theme
        engine is limited (no per-state gradients, limited radius), so
        this covers flat fills/borders/fonts per the reference's Tk
        feasibility notes -- not a pixel-exact CSS port."""
        theme.apply_theme(self.root)

    # ---- header bar (UI reference target §1-2) ----

    def _build_header(self) -> None:
        self.header_frame = ttk.Frame(self.root, style="Header.TFrame", padding=(16, 8))
        self.header_frame.pack(fill="x", side="top")

        left = ttk.Frame(self.header_frame, style="Header.TFrame")
        left.pack(side="left")
        ttk.Label(left, text="Screening Workbench", style="Wordmark.TLabel", font=(self.font_title, 17)).pack(side="left")
        ttk.Separator(left, orient="vertical", style="Drawer.TSeparator").pack(side="left", fill="y", padx=10)
        name_box = ttk.Frame(left, style="Header.TFrame")
        name_box.pack(side="left")
        self.project_name_label = ttk.Label(name_box, text="", style="Header.TLabel", font=(self.font_ui, 11, "bold"))
        self.project_name_label.pack(anchor="w")
        self.project_stage_label = ttk.Label(name_box, text="", style="Status.TLabel")
        self.project_stage_label.pack(anchor="w")

        right = ttk.Frame(self.header_frame, style="Header.TFrame")
        right.pack(side="right")
        self.export_button = ttk.Button(right, text="Export package...", command=self.action_export, style="Inverse.TButton")
        self.export_button.pack(side="right", padx=(12, 0))
        reviewer_box = ttk.Frame(right, style="Header.TFrame")
        reviewer_box.pack(side="right", padx=(12, 0))
        role = "Project owner" if roles.is_owner(self.conn, self.reviewer_id) else "Reviewer"
        ttk.Label(reviewer_box, text=f"Reviewer {self.reviewer_id}", style="Header.TLabel").pack(anchor="e")
        ttk.Label(reviewer_box, text=role, style="Status.TLabel").pack(anchor="e")
        self.blind_chip_label = tk.Label(
            right, text="", font=(self.font_ui, 9, "bold"), padx=10, pady=4, relief="flat", borderwidth=0,
            background=theme.TOKENS["drawer"], foreground=theme.TOKENS["drawer_muted"], highlightthickness=1,
            highlightbackground=theme.TOKENS["drawer_muted"], highlightcolor=theme.TOKENS["drawer_muted"],
        )
        self.blind_chip_label.pack(side="right")

    def _refresh_header(self) -> None:
        info = roles.get_project_name(self.conn)
        self.project_name_label.config(text=info["name"] or "(unnamed project)")
        n_batches = len(screening.list_active_batches(self.conn))
        batch_note = f"{n_batches} import batch{'es' if n_batches != 1 else ''}"
        stage = info["review_type"] or "Review"
        self.project_stage_label.config(text=f"{stage} \u00b7 Title/abstract stage \u00b7 {batch_note}")

        # On the drawer: ON is outlined with the highlighter (it changes what
        # the reviewer may see); OFF is quiet. Neither borrows decision colors.
        if roles.is_blind(self.conn):
            self.blind_chip_label.config(
                text="Blind screening: ON · others' decisions hidden",
                background=theme.TOKENS["drawer"], foreground=theme.TOKENS["drawer_ink"],
                highlightbackground=theme.TOKENS["signal"], highlightcolor=theme.TOKENS["signal"],
            )
        else:
            self.blind_chip_label.config(
                text="Blind screening: OFF",
                background=theme.TOKENS["drawer"], foreground=theme.TOKENS["drawer_muted"],
                highlightbackground=theme.TOKENS["drawer_muted"], highlightcolor=theme.TOKENS["drawer_muted"],
            )

    # ---- status bar (UI reference target §13-14) ----

    def _build_status_bar(self) -> None:
        self.status_bar = ttk.Frame(self.root, style="Status.TFrame", padding=(12, 5))
        self.status_bar.pack(fill="x", side="bottom")
        self.status_bar.lift()
        self.status_message_label = ttk.Label(self.status_bar, text="", style="Status.TLabel")
        self.status_message_label.pack(side="left", fill="x", expand=True)
        self.status_notice_label = ttk.Label(
            self.status_bar, text=f"Local only · {os.path.basename(self.db_path)}", style="Status.TLabel",
        )
        self.status_notice_label.pack(side="right", padx=(12, 0))
        self.status_legend_label = ttk.Label(
            self.status_bar,
            text="Screening shortcuts: I/M/E · 1–7 reason · J/K · / search",
            style="Status.TLabel",
        )
        self.status_legend_label.pack(side="right")

    def _set_status(self, text: str) -> None:
        """Live confirmation of the last action (UI reference target
        §13). In Tkinter there is no ARIA live-region API; updating this
        label's text is the practical screen-reader-adjacent signal
        available (spec §8 "decisions announced to screen readers") --
        a real NVDA/JAWS announcement would need a platform-specific
        accessibility bridge not attempted here. Documented honestly in
        the gap list rather than claimed as done."""
        self.status_message_label.config(text=text)

    def refresh_all_tabs(self) -> None:
        self._flush_pending_advance()
        self._refresh_header()
        self._refresh_batch_combo()
        self._refresh_facet_options()
        self._load_next_undecided()
        self._refresh_recent_decisions()
        self._refresh_blind_note()
        self._refresh_queue_list()
        self._refresh_maybe_tab()
        self._refresh_duplicates_tab()
        self._refresh_conflicts_tab()
        self._refresh_fulltext_tab()
        self._refresh_studies_tab()
        self._refresh_prisma_tab()
        self._refresh_nav_badges()
        # Refreshes can add widgets (empty-state hints, reason rows);
        # restyle any that landed on a card with the canvas background.
        theme.match_surface_backgrounds(self.root)

    def _refresh_nav_badges(self) -> None:
        """Section-nav tab labels carry a live count (UI reference
        target §3): the Conflicts tab shows a lock glyph instead of a
        count while blind, since the queue itself is hidden then."""
        undecided_n = screening.count_undecided(self.conn, self.reviewer_id)
        self.notebook.tab(0, text=f"Screening  ({undecided_n})")

        maybe_n = len(self._maybe_occurrence_ids)
        self.notebook.tab(1, text=f"Maybe re-review  ({maybe_n})")

        blind = roles.is_blind(self.conn)
        dup_n = len(dedup.list_open_fuzzy_candidates(self.conn)) if not blind else "LOCKED"
        self.notebook.tab(2, text=f"Duplicates  ({dup_n})" if dup_n != "LOCKED" else "Duplicates  · LOCKED")

        conflict_n = len(screening.list_conflicts(self.conn)) if not blind else 0
        pending_fulltext = sum(
            1 for r in reports.list_reports(self.conn)
            if not r["full_text_outcome"] or r["full_text_outcome"] == "maybe"
        ) if not blind else "LOCKED"
        study_n = len(studies.list_studies(self.conn)) if not blind else "LOCKED"
        can_view_prisma = not blind or roles.is_owner_or_auditor(
            self.conn, self.reviewer_id, "full_export",
        )
        snapshot_issues = len(prisma.verify_invariants(self.conn)) if can_view_prisma else "LOCKED"
        badge_values = {
            "screening": undecided_n, "maybe": maybe_n, "duplicates": dup_n,
            "conflicts": "LOCKED" if blind else conflict_n,
            "fulltext": pending_fulltext, "studies": study_n,
            "prisma": snapshot_issues if can_view_prisma else "LOCKED",
        }
        for index, key in enumerate(self._tab_ids):
            count = badge_values[key]
            if count == 0:
                badge_style = "CountBadgeZero.TLabel"
            elif key in ("conflicts", "duplicates") and count != "LOCKED":
                badge_style = "CountBadgeAttention.TLabel"
            else:
                badge_style = "CountBadge.TLabel"
            self.section_nav_badges[key].configure(
                text=count if count != "LOCKED" else "LOCK", style=badge_style,
            )
            base_title = self.section_nav_buttons[key].cget("text")
            self.notebook.tab(index, text=f"{base_title}  ({count})" if count != "LOCKED" else f"{base_title}  · LOCKED")

    # ---- menu / top-level actions ----

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root, tearoff=0)
        self.menubar = menubar
        self.root.config(menu=menubar)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Import CSV...", command=self.action_import_csv)
        file_menu.add_command(label="Import RIS...", command=self.action_import_ris)
        file_menu.add_command(label="Import PubMed XML...", command=self.action_import_pubmed_xml)
        file_menu.add_separator()
        file_menu.add_command(label="Export package...", command=self.action_export)
        file_menu.add_separator()
        file_menu.add_command(label="Reset project...", command=self.action_reset_project)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        project_menu = tk.Menu(menubar, tearoff=0)
        project_menu.add_command(label="Set project name...", command=self.action_set_project_name)
        project_menu.add_separator()
        project_menu.add_command(label="Toggle blind mode (owner only)", command=self.action_toggle_blind)
        project_menu.add_command(label="Grant auditor role...", command=self.action_grant_auditor)
        project_menu.add_command(label="Revoke auditor role...", command=self.action_revoke_auditor)
        project_menu.add_separator()
        project_menu.add_command(label="Import reviewer packet...", command=self.action_import_reviewer_packet)
        project_menu.add_command(label="Export votes file...", command=self.action_export_votes_file)
        menubar.add_cascade(label="Project", menu=project_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Screening", command=lambda: self._select_section("screening"))
        view_menu.add_command(label="Maybe re-review", command=lambda: self._select_section("maybe"))
        view_menu.add_command(label="Duplicates", command=lambda: self._select_section("duplicates"))
        view_menu.add_command(label="Conflicts", command=lambda: self._select_section("conflicts"))
        view_menu.add_command(label="Full-text", command=lambda: self._select_section("fulltext"))
        view_menu.add_command(label="Studies", command=lambda: self._select_section("studies"))
        view_menu.add_command(label="PRISMA & audit", command=lambda: self._select_section("prisma"))
        view_menu.add_separator()
        self.reduce_motion_var = tk.BooleanVar(master=self.root, value=display_prefs.reduced_motion())
        view_menu.add_checkbutton(
            label="Reduce motion", variable=self.reduce_motion_var,
            command=lambda: display_prefs.save_reduced_motion(self.reduce_motion_var.get()),
        )
        theme_menu = tk.Menu(view_menu, tearoff=0)
        self.theme_choice_var = tk.StringVar(master=self.root, value=display_prefs.saved_theme())
        for value, label in (
            ("system", "Match Windows"),
            ("light", theme.PALETTE_LABELS["light"]),
            ("night", theme.PALETTE_LABELS["night"]),
        ):
            theme_menu.add_radiobutton(
                label=label, value=value, variable=self.theme_choice_var, command=self._save_theme_choice,
            )
        view_menu.add_cascade(label="Theme", menu=theme_menu)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Keyboard shortcuts", command=self._show_keyboard_shortcuts)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)
        self.menubar = menubar

    def _build_menubar_chrome(self) -> None:
        self.menubar_frame = ttk.Frame(self.root, padding=(8, 4, 8, 0), style="Drawer.TFrame")
        self.menubar_frame.pack(fill="x", side="top")
        self.menubar_buttons = []
        last_index = self.menubar.index("end")
        if last_index is None:
            return
        for index in range(last_index + 1):
            label = self.menubar.entrycget(index, "label")
            cascade_menu = self.root.nametowidget(self.menubar.entrycget(index, "menu"))
            button = ttk.Menubutton(self.menubar_frame, text=label, style="ChromeMenu.TMenubutton")
            button.configure(menu=cascade_menu)
            button.pack(side="left", padx=(0, 8))
            self.menubar_buttons.append(button)
        self.root.config(menu="")

    def _build_section_nav(self) -> None:
        """Render seven reference-shell section buttons and live count badges."""
        self.section_nav_buttons: dict[str, ttk.Button] = {}
        self.section_nav_badges: dict[str, ttk.Label] = {}
        self.section_nav_underlines: dict[str, tk.Frame] = {}
        for key, title in zip(self._tab_ids, (
            "Screening", "Maybe re-review", "Duplicates", "Conflicts",
            "Full-text", "Studies", "PRISMA & audit",
        )):
            item = ttk.Frame(self.section_nav, padding=(2, 2, 2, 0), style="Drawer.TFrame")
            item.pack(side="left", padx=(0, 4))
            row = ttk.Frame(item, style="Drawer.TFrame")
            row.pack(side="top")
            button = ttk.Button(
                row, text=title, style="Section.TButton",
                command=lambda section=key: self._select_section(section),
            )
            button.pack(side="left")
            self.section_nav_buttons[key] = button
            badge = ttk.Label(row, text="0", style="CountBadgeZero.TLabel", padding=(5, 2))
            badge.pack(side="left", padx=(2, 4))
            self.section_nav_badges[key] = badge
            # The active section is marked by a highlighter rule, not a fill.
            underline = tk.Frame(item, height=3, background=theme.TOKENS["drawer"], borderwidth=0)
            underline.pack(side="top", fill="x")
            self.section_nav_underlines[key] = underline
        self.notebook.bind("<<NotebookTabChanged>>", self._sync_section_nav)
        self._sync_section_nav()

    def _select_section(self, section: str) -> None:
        self.notebook.select(self._tab_ids.index(section))
        self._sync_section_nav()

    def _sync_section_nav(self, _event=None) -> None:
        if not hasattr(self, "section_nav_buttons"):
            return
        self._flush_pending_advance()
        current = self.notebook.index("current")
        for index, key in enumerate(self._tab_ids):
            self.section_nav_buttons[key].configure(
                style="ActiveSection.TButton" if index == current else "Section.TButton"
            )
            self.section_nav_underlines[key].configure(
                background=theme.TOKENS["signal"] if index == current else theme.TOKENS["drawer"]
            )

    def _save_theme_choice(self) -> None:
        """Save View > Theme. Widgets take their colors when built, so the
        new palette applies on the next start rather than mid-session."""
        choice = self.theme_choice_var.get()
        label = "Match Windows" if choice == "system" else theme.PALETTE_LABELS[choice]
        if display_prefs.save_theme(choice):
            self._set_status(f"Theme set to {label}. Restart Screening Workbench to apply it.")
        else:
            self._set_status("Could not save the theme setting; the current theme stays.")

    def _show_keyboard_shortcuts(self) -> None:
        messagebox.showinfo(
            "Keyboard shortcuts",
            "Screening: I include · M maybe · E exclude · 1–7 reason · J/K next/previous · / search · Ctrl+Z undo.\n"
            "Maybe re-review: I/M/E decide · J/K navigate.",
        )

    def _prompt_csv_mapping(self, preview) -> dict[int, str] | None:
        """Show sampled source columns and let the user confirm/edit mappings."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Map CSV columns")
        dialog.transient(self.root)
        dialog.grab_set()
        result: dict[str, dict[int, str] | None] = {"mapping": None}
        ttk.Label(
            dialog,
            text="Match each CSV column to a field. Samples are shown to help identify unfamiliar headers.",
            wraplength=760,
        ).grid(row=0, column=0, columnspan=3, sticky="w", padx=12, pady=(12, 8))
        ttk.Label(dialog, text="CSV column", font=(self.font_ui, 9, "bold")).grid(row=1, column=0, sticky="w", padx=12)
        ttk.Label(dialog, text="Sample values", font=(self.font_ui, 9, "bold")).grid(row=1, column=1, sticky="w", padx=8)
        ttk.Label(dialog, text="Map to", font=(self.font_ui, 9, "bold")).grid(row=1, column=2, sticky="w", padx=8)
        variables: list[tk.StringVar] = []
        for i, proposal in enumerate(preview.mapping_proposals):
            row = i + 2
            ttk.Label(dialog, text=proposal.source_field, wraplength=210).grid(
                row=row, column=0, sticky="w", padx=12, pady=3,
            )
            samples = " · ".join(proposal.sample_values) or "(no sample values)"
            ttk.Label(dialog, text=samples, wraplength=420).grid(
                row=row, column=1, sticky="w", padx=8, pady=3,
            )
            proposal_value = proposal.canonical_field if proposal.canonical_field in CSV_MAPPING_FIELDS else ""
            variable = tk.StringVar(master=dialog, value=proposal_value or CSV_MAPPING_CHOICES[0])
            variables.append(variable)
            ttk.Combobox(
                dialog, textvariable=variable, values=CSV_MAPPING_CHOICES,
                state="readonly", width=16,
            ).grid(row=row, column=2, sticky="ew", padx=8, pady=3)

        warning = tk.StringVar(master=dialog, value="")
        warning_label = ttk.Label(dialog, textvariable=warning, foreground=theme.TOKENS["exclude"], wraplength=760)
        warning_label.grid(row=len(variables) + 2, column=0, columnspan=3, sticky="w", padx=12, pady=(8, 0))

        def update_warning(*_args) -> None:
            assignments = [v.get() for v in variables if v.get() != CSV_MAPPING_CHOICES[0]]
            duplicates = sorted({field for field in assignments if assignments.count(field) > 1})
            notes = []
            if not any(v.get() == "title" for v in variables):
                notes.append("Title must be mapped before this import can continue.")
            if duplicates:
                notes.append("More than one column is mapped to: " + ", ".join(duplicates) + ". Choose only one column for each field.")
            warning.set(" ".join(notes))

        for variable in variables:
            variable.trace_add("write", update_warning)
        update_warning()

        buttons = ttk.Frame(dialog)
        buttons.grid(row=len(variables) + 3, column=0, columnspan=3, sticky="e", padx=12, pady=12)

        def commit_mapping() -> None:
            mapping = {
                i: variable.get()
                for i, variable in enumerate(variables)
                if variable.get() != CSV_MAPPING_CHOICES[0]
            }
            error = validate_csv_mapping(mapping)
            if error:
                warning.set(error)
                return
            result["mapping"] = mapping
            dialog.destroy()

        ttk.Button(buttons, text="Cancel", command=dialog.destroy, style="Quiet.TButton").pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Import", command=commit_mapping, style="Accent.TButton").pack(side="right")
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self.root.wait_window(dialog)
        return result["mapping"]

    def action_reset_project(self) -> None:
        """Destructively recreate the project database after explicit confirmation."""
        confirmation = simpledialog.askstring(
            "Reset project",
            "This permanently deletes all records, votes, imports, and audit history.\n"
            "Type RESET to continue:",
        )
        if confirmation != "RESET":
            return
        if not messagebox.askyesno(
            "Confirm project reset",
            "This cannot be undone. Delete all project data and start fresh?",
            icon="warning",
        ):
            return
        db_path = self.db_path
        current = self.conn.execute("PRAGMA database_list").fetchone()
        live_db_path = current["file"] if current and current["file"] else db_path
        db_path = live_db_path
        attach_dir = attachments.resolve_attachments_dir(self.conn)
        self.conn.close()
        try:
            for suffix in ("", "-wal", "-shm"):
                path = db_path + suffix
                if os.path.exists(path):
                    os.remove(path)
            if os.path.isdir(attach_dir):
                shutil.rmtree(attach_dir)
            self.conn = db.connect(db_path)
            roles.set_owner(self.conn, self.reviewer_id)
        except (OSError, sqlite3.Error, ValueError) as exc:
            messagebox.showerror("Reset failed", f"Could not reset the project database: {exc}")
            return
        self.refresh_all_tabs()
        self._set_status("Project reset. All review data and audit history were cleared.")
        messagebox.showinfo("Project reset", "The project is empty and ready for a new import.")

    def action_set_project_name(self) -> None:
        name = simpledialog.askstring("Project name", "Name this review:")
        if not name:
            return
        review_type = simpledialog.askstring("Review type", "Review type (e.g. Scoping review):")
        try:
            roles.set_project_name(self.conn, self.reviewer_id, name, review_type=review_type)
        except PermissionError as exc:
            messagebox.showerror("Not permitted", str(exc))
            return
        except ValueError as exc:
            messagebox.showerror("Invalid name", str(exc))
            return
        self._refresh_header()
        self._set_status(f"Project renamed to \u201c{name}\u201d.")

    def _import_common(self, result, batch_label: str) -> None:
        try:
            dedup_result = dedup.run_exact_and_fuzzy_detection(self.conn, "system", batch_id=result.batch_id)
        except dedup.PairComparisonLimitError as exc:
            self.refresh_all_tabs()
            self._set_status(str(exc))
            messagebox.showerror("Duplicate detection limit", str(exc))
            return
        summary = (
            f"read {result.records_read} record(s), "
            f"{dedup_result.exact_merges} duplicate(s) merged, "
            f"{dedup_result.fuzzy_candidates_created + dedup_result.doi_conflict_candidates_created} candidate(s) for review, "
            f"skipped {result.records_skipped}."
        )
        self._set_status(f"Imported {batch_label}: {summary}")
        messagebox.showinfo("Import complete", f"{batch_label}: {summary}")
        self.refresh_all_tabs()

    def action_import_csv(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        try:
            raw = read_limited_bytes(path)
        except (OSError, ImportLimitError) as exc:
            messagebox.showerror("Import failed", f"Could not read CSV file: {exc}")
            return
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            encoding = simpledialog.askstring(
                "CSV encoding", "File is not valid UTF-8. Choose cp1252 or latin-1:", initialvalue="cp1252"
            )
            if not encoding:
                return
            if encoding.casefold() not in {"cp1252", "latin-1"}:
                messagebox.showerror("Invalid encoding", "Choose cp1252 or latin-1.")
                return
            try:
                text = raw.decode(encoding, errors="strict")
            except UnicodeDecodeError as exc:
                messagebox.showerror("Import failed", f"Could not decode CSV file as {encoding}: {exc}")
                return

        delimiter_choice = simpledialog.askstring(
            "CSV delimiter", "Choose comma, tab, semicolon, or pipe:", initialvalue="comma"
        )
        if delimiter_choice is None:
            return
        delimiters = {"comma": ",", "tab": "\t", "semicolon": ";", "pipe": "|", ",": ",", ";": ";", "|": "|"}
        delimiter = delimiters.get(delimiter_choice.strip().casefold())
        if delimiter is None:
            messagebox.showerror("Invalid delimiter", "Choose comma, tab, semicolon, or pipe.")
            return

        has_header = messagebox.askyesnocancel(
            "CSV header", "Does the first row contain column headers? Choose No for headerless CSV."
        )
        if has_header is None:
            return
        try:
            preview = preview_csv(text, delimiter=delimiter, has_header=has_header)
        except ImportLimitError as exc:
            messagebox.showerror("Import failed", f"Could not preview CSV file: {exc}")
            return
        if has_header:
            mapping = self._prompt_csv_mapping(preview)
            if mapping is None:
                return
        else:
            fields = ", ".join(CANONICAL_FIELDS)
            selection = simpledialog.askstring(
                "Map headerless CSV columns",
                f"Enter one canonical field per column, comma-separated; leave blank to skip.\n"
                f"Allowed fields: {fields}",
            )
            if selection is None:
                return
            choices = [part.strip() for part in selection.split(",")]
            if len(choices) != len(preview.header_fields) or any(
                value and value not in CANONICAL_FIELDS for value in choices
            ):
                messagebox.showerror(
                    "Invalid column mapping",
                    f"Enter exactly {len(preview.header_fields)} comma-separated positions using canonical field names or blanks.",
                )
                return
            mapping = {i: value for i, value in enumerate(choices) if value}
            error = validate_csv_mapping(mapping)
            if error:
                messagebox.showerror("Invalid column mapping", error)
                return

        if self.conn.execute("SELECT 1 FROM sources LIMIT 1").fetchone() is None:
            try:
                dedup.ensure_pair_comparison_budget(self.conn, preview.rows_readable)
            except dedup.PairComparisonLimitError as exc:
                messagebox.showerror("Duplicate detection limit", str(exc))
                return

        try:
            source_id, branch_id = self._ensure_default_source()
            result = commit_csv_import(
                self.conn, text, mapping, source_id=source_id, branch_id=branch_id,
                operation_id=f"ui-import-{os.path.basename(path)}-{len(raw)}",
                actor=self.reviewer_id, source_name=os.path.basename(path),
                delimiter=delimiter, has_header=has_header,
            )
        except dedup.PairComparisonLimitError as exc:
            messagebox.showerror("Duplicate detection limit", str(exc))
            return
        except ImportLimitError as exc:
            messagebox.showerror("Import failed", f"Could not import CSV file: {exc}")
            return
        self._import_common(result, "CSV")

    def action_import_ris(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("RIS files", "*.ris"), ("All files", "*.*")])
        if not path:
            return
        try:
            text = read_limited_text(path)
            if self.conn.execute("SELECT 1 FROM sources LIMIT 1").fetchone() is None:
                dedup.ensure_pair_comparison_budget(self.conn, len(parse_ris(text).records))
        except dedup.PairComparisonLimitError as exc:
            messagebox.showerror("Duplicate detection limit", str(exc))
            return
        except (OSError, UnicodeError, ImportLimitError) as exc:
            messagebox.showerror("Import failed", f"Could not import RIS file: {exc}")
            return
        try:
            source_id, branch_id = self._ensure_default_source()
            result = commit_ris_import(
                self.conn, text, source_id=source_id, branch_id=branch_id,
                operation_id=f"ui-import-{os.path.basename(path)}-{len(text)}",
                actor=self.reviewer_id, source_name=os.path.basename(path),
            )
        except dedup.PairComparisonLimitError as exc:
            messagebox.showerror("Duplicate detection limit", str(exc))
            return
        except (OSError, UnicodeError, ImportLimitError) as exc:
            messagebox.showerror("Import failed", f"Could not import RIS file: {exc}")
            return
        self._import_common(result, "RIS")

    def action_import_pubmed_xml(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("XML files", "*.xml"), ("All files", "*.*")])
        if not path:
            return
        try:
            text = read_limited_text(path)
            if self.conn.execute("SELECT 1 FROM sources LIMIT 1").fetchone() is None:
                dedup.ensure_pair_comparison_budget(self.conn, len(parse_pubmed_xml(text).records))
        except dedup.PairComparisonLimitError as exc:
            messagebox.showerror("Duplicate detection limit", str(exc))
            return
        except (OSError, UnicodeError, ImportLimitError) as exc:
            messagebox.showerror("Import failed", f"Could not import PubMed XML file: {exc}")
            return
        try:
            source_id, branch_id = self._ensure_default_source()
            result = commit_pubmed_xml_import(
                self.conn, text, source_id=source_id, branch_id=branch_id,
                operation_id=f"ui-import-{os.path.basename(path)}-{len(text)}",
                actor=self.reviewer_id, source_name=os.path.basename(path),
            )
        except dedup.PairComparisonLimitError as exc:
            messagebox.showerror("Duplicate detection limit", str(exc))
            return
        except (OSError, UnicodeError, ImportLimitError) as exc:
            messagebox.showerror("Import failed", f"Could not import PubMed XML file: {exc}")
            return
        self._import_common(result, "PubMed XML")

    def _ensure_default_source(self) -> tuple[str, str]:
        row = self.conn.execute("SELECT source_id, branch_id FROM sources LIMIT 1").fetchone()
        if row:
            return row["source_id"], row["branch_id"]
        self.conn.execute(
            "INSERT INTO branches (branch_id, name, created_at) VALUES ('default','default',datetime('now'))"
        )
        self.conn.execute(
            "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
            " VALUES ('default','default','database','default',datetime('now'))"
        )
        self.conn.commit()
        return "default", "default"

    def action_export(self) -> None:
        folder = filedialog.askdirectory()
        if not folder:
            return
        is_blind = roles.is_blind(self.conn)
        package = export.export_package(self.conn, self.reviewer_id, is_blind=is_blind)
        try:
            export.write_package_to_folder(package, folder)
        except OSError as exc:
            self._set_status("Export failed -- local write error; prior files in that folder are untouched.")
            messagebox.showerror(
                "Export failed",
                f"Could not write the export package: {exc}\n\nNo files in {folder} were changed.",
            )
            return
        self._set_status(f"Exported {len(package)} files to {folder}.")
        messagebox.showinfo("Export complete", f"Wrote {len(package)} files to {folder}.")

    def action_toggle_blind(self) -> None:
        try:
            roles.set_blind(self.conn, self.reviewer_id, not roles.is_blind(self.conn))
        except PermissionError as exc:
            messagebox.showerror("Not permitted", str(exc))
            return
        self.refresh_all_tabs()
        self._set_status(f"Blind mode is now {'ON' if roles.is_blind(self.conn) else 'OFF'}.")

    def action_grant_auditor(self) -> None:
        target = simpledialog.askstring("Grant auditor role", "Reviewer ID to grant:")
        if not target:
            return
        scope = simpledialog.askstring("Scope", "Scope (audit_read or full_export):")
        if scope not in ("audit_read", "full_export"):
            messagebox.showerror("Invalid scope", "Scope must be audit_read or full_export.")
            return
        reason = simpledialog.askstring("Reason", "Reason for this grant:")
        if not reason:
            return
        try:
            roles.grant_auditor_role(self.conn, actor=self.reviewer_id, target=target, scope=scope, reason=reason)
        except PermissionError as exc:
            messagebox.showerror("Not permitted", str(exc))
            return
        messagebox.showinfo("Granted", f"Granted {scope} to {target}.")

    def action_revoke_auditor(self) -> None:
        target = simpledialog.askstring("Revoke auditor role", "Reviewer ID to revoke:")
        if not target:
            return
        scope = simpledialog.askstring("Scope", "Scope (audit_read or full_export):")
        if scope not in ("audit_read", "full_export"):
            messagebox.showerror("Invalid scope", "Scope must be audit_read or full_export.")
            return
        reason = simpledialog.askstring("Reason", "Reason for this revocation:")
        if not reason:
            return
        try:
            roles.revoke_auditor_role(self.conn, actor=self.reviewer_id, target=target, scope=scope, reason=reason)
        except PermissionError as exc:
            messagebox.showerror("Not permitted", str(exc))
            return
        messagebox.showinfo("Revoked", f"Revoked {scope} from {target}.")

    # ---- Directive B: two-computer blind review (reviewer packets) ----
    # Project-level actions: import a packet into a fresh install (reviewer
    # B's side) and export this reviewer's votes file. Host-side packet
    # export and votes merge live in the Conflicts tab (§below), since
    # merge is owner-only and requires blind mode off there per spec.

    def action_import_reviewer_packet(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Screening Workbench reviewer packet", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            result = packets.import_packet(self.conn, path, reviewer_id=self.reviewer_id, actor=self.reviewer_id)
        except ValueError as exc:
            messagebox.showerror("Import failed", str(exc))
            return
        self._set_status(f"Imported reviewer packet: {result['record_count']} record(s), locked to {self.reviewer_id}.")
        messagebox.showinfo(
            "Packet imported",
            f"Imported {result['record_count']} record(s) from the packet.\n"
            f"This database is now locked to reviewer \u201c{self.reviewer_id}\u201d.",
        )
        self.refresh_all_tabs()

    def action_export_votes_file(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Screening Workbench votes export", "*.json")],
        )
        if not path:
            return
        try:
            result = packets.export_votes(self.conn, path, reviewer_id=self.reviewer_id, actor=self.reviewer_id)
        except PermissionError as exc:
            messagebox.showerror("Not permitted", str(exc))
            return
        self._set_status(f"Exported {result['vote_count']} vote(s) to {os.path.basename(path)}.")
        messagebox.showinfo("Votes exported", f"Exported {result['vote_count']} vote(s) to:\n{path}")

    # ---- screening tab ----

    def _build_screening_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Screening")

        filter_row1 = ttk.Frame(frame)
        filter_row1.pack(fill="x")
        ttk.Label(filter_row1, text="Search (title/abstract/journal):").pack(side="left")
        self.screen_search_entry = ttk.Entry(filter_row1, width=24)
        self.screen_search_entry.pack(side="left", padx=(4, 4))
        ttk.Label(
            filter_row1, text="( / )", font=(self.font_ui, 9), foreground=theme.TOKENS["muted"],
        ).pack(side="left", padx=(0, 8))
        ttk.Label(filter_row1, text="Year:").pack(side="left")
        self.screen_year_entry = ttk.Combobox(filter_row1, width=8)
        self.screen_year_entry.pack(side="left", padx=(4, 12))
        ttk.Label(filter_row1, text="Journal:").pack(side="left")
        self.screen_journal_entry = ttk.Combobox(filter_row1, width=20)
        self.screen_journal_entry.pack(side="left", padx=(4, 12))

        filter_row2 = ttk.Frame(frame)
        filter_row2.pack(fill="x", pady=(4, 8))
        ttk.Label(filter_row2, text="Batch:").pack(side="left")
        self.screen_batch_combo = ttk.Combobox(filter_row2, width=24, state="readonly")
        self.screen_batch_combo.pack(side="left", padx=(4, 12))
        self._screen_batch_ids: list[str | None] = [None]  # index 0 = "All batches"

        self.screen_undecided_only_var = tk.BooleanVar(master=self.root, value=True)
        ttk.Checkbutton(
            filter_row2, text="Undecided only (default)", variable=self.screen_undecided_only_var,
            command=self._apply_screening_filter,
        ).pack(side="left", padx=(0, 12))
        ttk.Button(filter_row2, text="Apply filter", command=self._apply_screening_filter).pack(side="left", padx=4)
        ttk.Button(filter_row2, text="Clear filter", command=self._clear_screening_filter).pack(side="left", padx=4)
        self.screen_search_entry.bind("<Return>", lambda e: self._apply_screening_filter())
        self.screen_year_entry.bind("<Return>", lambda e: self._apply_screening_filter())
        self.screen_journal_entry.bind("<Return>", lambda e: self._apply_screening_filter())

        self.remaining_label = ttk.Label(frame, text="Remaining: 0", font=(self.font_ui, 10))
        self.remaining_label.pack(anchor="w")

        self.screen_body = ttk.Frame(frame)
        self.screen_body.pack(fill="both", expand=True, pady=(8, 0))
        for column, weight, minimum in ((0, 280, 280), (1, 656, 420), (2, 296, 260)):
            self.screen_body.columnconfigure(column, weight=weight, minsize=minimum, uniform="screen-cards")
        self.screen_body.rowconfigure(0, weight=1)
        # Direction 02: the record card is the one raised object; the queue
        # and support columns sit flat on the desk beside it.
        self.screen_queue_card = ttk.Frame(self.screen_body, padding=(0, 12, 4, 12), style="Desk.TFrame")
        self.screen_queue_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.screen_record_card = ttk.Frame(self.screen_body, padding=12, style="Card.TFrame")
        self.screen_record_card.grid(row=0, column=1, sticky="nsew", padx=4)
        self.screen_support_card = ttk.Frame(self.screen_body, padding=(4, 12, 0, 12), style="Desk.TFrame")
        self.screen_support_card.grid(row=0, column=2, sticky="nsew", padx=(8, 0))

        # Left column: upcoming-queue list (UI reference target §5) +
        # bulk select/decide (screening-workflow spec §4: "bulk select +
        # bulk decide for obvious batches").
        queue_col = self.queue_col = ttk.Frame(self.screen_queue_card, width=280)
        queue_col.pack(fill="both", expand=True)
        queue_col.pack_propagate(False)
        self.queue_header_label = ttk.Label(queue_col, text="QUEUE", font=(self.font_ui, 9, "bold"))
        self.queue_header_label.pack(anchor="w")
        # ttk.Treeview, single tree column, two-line cell text (UI
        # reference target §5): title on line 1, "year · journal · #N"
        # on line 2, left-aligned. Confirmed empirically on Windows that
        # ttk.Treeview DOES wrap an embedded "\n" in #0 column text into
        # a real second visual line once rowheight is tall enough (the
        # earlier "Tk can't do this" assumption from the column-swap
        # round was wrong -- verified with a throwaway script before
        # relying on it here). Right-alignment of "Now"/"#N" on line 2
        # is NOT chased per this round's explicit instruction -- mixed
        # per-line alignment within one cell isn't a clean Tk affordance
        # and the information architecture is what's required, not the
        # decoration. The occurrence_id is used directly as each row's
        # iid.
        queue_list_frame = ttk.Frame(queue_col, height=280)
        queue_list_frame.pack(fill="x", pady=(4, 6))
        queue_list_frame.pack_propagate(False)
        self.queue_list = ttk.Treeview(
            queue_list_frame, show="tree", height=7, selectmode="extended",
            style="Queue.Treeview",
        )
        self.queue_list.column("#0", width=254, anchor="w")
        # "Now" is the highlighter; selection keeps accent-soft, so the two stay distinct.
        self.queue_list.tag_configure("current", background=theme.TOKENS["signal_soft"], foreground=theme.TOKENS["ink"])
        queue_scrollbar = ttk.Scrollbar(queue_list_frame, orient="vertical", command=self.queue_list.yview)
        self.queue_list.configure(yscrollcommand=queue_scrollbar.set)
        self.queue_list.pack(side="left", fill="both", expand=True)
        queue_scrollbar.pack(side="right", fill="y")
        self.queue_list.bind("<Double-Button-1>", self._on_queue_double_click)
        self._queue_occurrence_ids: list[str] = []

        bulk_frame = ttk.Frame(queue_col)
        bulk_frame.pack(fill="x")
        ttk.Label(bulk_frame, text="Decide selected:", font=(self.font_ui, 9)).pack(anchor="w")
        bulk_btns = ttk.Frame(queue_col)
        bulk_btns.pack(fill="x", pady=(2, 0))
        ttk.Button(bulk_btns, text="Include", width=7, command=lambda: self._bulk_decide("include")).pack(side="left", padx=(0, 1))
        ttk.Button(bulk_btns, text="Maybe", width=7, command=lambda: self._bulk_decide("maybe")).pack(side="left", padx=1)
        ttk.Button(bulk_btns, text="Exclude...", width=8, command=lambda: self._bulk_decide("exclude")).pack(side="left", padx=(1, 0))

        # Record pane, wrapped so a visible focus ring (UI reference
        # target §6) can be toggled around it: 2px highlight border that
        # switches to the theme focus token while the pane holds keyboard
        # focus, and back to a neutral color when it doesn't.
        self.record_frame = tk.Frame(
            self.screen_record_card, **theme.focus_outline_options(False), bd=0,
            background=theme.TOKENS["surface"],
        )
        self.record_frame.pack(fill="both", expand=True)

        record_inner = ttk.Frame(self.record_frame, padding=12)
        record_inner.pack(fill="both", expand=True)

        # Call-number strip: record/batch position in mono over the card's
        # double rule, whose dark segment is the progress through the queue.
        self.position_label = ttk.Label(record_inner, text="", font=(self.font_mono, 9), foreground=theme.TOKENS["muted"])
        self.position_label.pack(anchor="w")

        self.position_progress = _CallNumberRule(record_inner)
        self.position_progress.pack(fill="x", pady=(6, 0))

        self.title_label = ttk.Label(record_inner, text="", font=(self.font_title, 16), wraplength=560)
        self.title_label.pack(anchor="w", pady=(12, 4))

        self.meta_label = ttk.Label(record_inner, text="", font=(self.font_ui, 10), foreground=theme.TOKENS["muted"])
        self.meta_label.pack(anchor="w")

        abstract_frame = ttk.Frame(record_inner)
        abstract_frame.pack(fill="both", expand=True, pady=(8, 8))
        # The abstract reads on the card itself: no inner box, open leading.
        self.abstract_text = tk.Text(
            abstract_frame, height=7, wrap="word", font=(self.font_reading, 12),
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"], insertbackground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
            highlightthickness=0, relief="flat", borderwidth=0, spacing2=4, spacing3=8,
        )
        abstract_scrollbar = ttk.Scrollbar(abstract_frame, orient="vertical", command=self.abstract_text.yview)
        self.abstract_text.config(yscrollcommand=abstract_scrollbar.set)
        self.abstract_text.pack(side="left", fill="both", expand=True)
        abstract_scrollbar.pack(side="right", fill="y")
        # UI reference target §8: structured-abstract section headers
        # (BACKGROUND/METHODS/RESULTS/CONCLUSIONS) rendered bold, not
        # plain text indistinguishable from the body.
        self.abstract_text.tag_configure("section-header", font=(self.font_reading, 12, "bold"))
        # Search matches get the highlighter, the way a screener marks a PDF.
        self.abstract_text.tag_configure("hit", background=theme.TOKENS["signal"], foreground=theme.TOKENS["on_signal"])
        self.abstract_text.config(state="disabled")
        # The record pane's focus ring tracks this Text widget's focus,
        # since it's the natural tab-stop inside the pane.
        self.abstract_text.bind("<FocusIn>", self._on_record_focus_in)
        self.abstract_text.bind("<FocusOut>", self._on_record_focus_out)

        # Decision bar (UI reference target §9): clickable buttons in
        # addition to the i/m/e keyboard shortcuts, each on a soft
        # semantic fill so color is never the only signal (label text
        # carries the meaning too).
        self.primary_decision_bar = ttk.Frame(record_inner)
        # Each decision shows its key as a keycap beside the word; the soft
        # fill, border and word keep the semantic color, never color alone.
        decision_fonts = {"font_ui": self.font_ui, "font_mono": self.font_mono}
        self.include_button = _KeycapButton(
            self.primary_decision_bar, key="I", word="Include", decision="include",
            command=lambda: self._decide("include"), **decision_fonts,
        )
        self.include_button.grid(row=0, column=0, sticky="ew")
        self.maybe_button = _KeycapButton(
            self.primary_decision_bar, key="M", word="Maybe", decision="maybe",
            command=lambda: self._decide("maybe"), **decision_fonts,
        )
        self.maybe_button.grid(row=0, column=2, sticky="ew")
        self.exclude_button = _KeycapButton(
            self.primary_decision_bar, key="E", word="Exclude...", decision="exclude",
            command=lambda: self._decide("exclude"), **decision_fonts,
        )
        self.exclude_button.grid(row=0, column=4, sticky="ew")
        # Equal widths whatever each word measures; the gaps are fixed spacer
        # columns so the outer buttons stay flush with the card edges.
        for column in (0, 2, 4):
            self.primary_decision_bar.columnconfigure(column, weight=1, uniform="decision")
        for column in (1, 3):
            self.primary_decision_bar.columnconfigure(column, minsize=8)

        secondary_bar = ttk.Frame(record_inner)
        self.undo_button = ttk.Button(
            secondary_bar, text="Undo  Ctrl+Z", command=self._undo_last_decision, style="Quiet.TButton",
        )
        self.undo_button.pack(side="left")
        self.skip_button = ttk.Button(
            secondary_bar, text="Skip  J", command=self._skip_current, style="Quiet.TButton",
        )
        self.skip_button.pack(side="left", padx=(6, 0))

        legend = self.screen_key_legend = ttk.Label(
            record_inner,
            text="I = Include   M = Maybe   E = Exclude, then 1-7 for a reason   J = Skip   K = Prev   Ctrl+Z = Undo",
            font=(self.font_ui, 9),
        )
        # Decision row, quiet actions and key legend are packed against the
        # card's bottom edge ahead of the abstract, so a long abstract (or
        # the taller bundled faces) shrinks the reading area, never the
        # controls.
        legend.pack(side="bottom", anchor="w", before=abstract_frame)
        secondary_bar.pack(side="bottom", fill="x", pady=(0, 2), before=abstract_frame)
        self.primary_decision_bar.pack(side="bottom", fill="x", pady=(0, 2), before=abstract_frame)

        # Right column: always-visible exclusion-reasons reference (UI
        # reference target §10) above the recent-decisions panel (§11).
        side_panel = self.side_panel = ttk.Frame(self.screen_support_card, width=296)
        side_panel.pack(fill="both", expand=True)
        ttk.Label(side_panel, text="EXCLUSION REASONS", font=(self.font_ui, 9, "bold")).pack(anchor="w")
        ttk.Label(side_panel, text="E, then 1-7", font=(self.font_ui, 9), foreground=theme.TOKENS["muted"]).pack(anchor="w")
        self.reason_keycaps: list[tk.Label] = []
        self.reason_rows: list[ttk.Frame] = []
        self.reason_labels: list[ttk.Label] = []
        self.exclusion_reasons_armed = False
        for i, reason_text in enumerate(screening.EXCLUSION_REASONS, start=1):
            row = ttk.Frame(side_panel)
            row.pack(fill="x", pady=1)
            self.reason_rows.append(row)
            keycap = tk.Label(
                row, text=str(i), width=2, relief="flat", borderwidth=0, font=(self.font_mono, 9, "bold"),
                bg=theme.TOKENS["surface"], fg=theme.TOKENS["ink"], highlightthickness=1,
                highlightbackground=theme.TOKENS["line_strong"], highlightcolor=theme.TOKENS["line_strong"],
            )
            keycap.pack(side="left")
            self.reason_keycaps.append(keycap)
            reason_label = ttk.Label(row, text=reason_text, font=(self.font_ui, 9), wraplength=164, justify="left")
            reason_label.pack(side="left", padx=(6, 0), fill="x", expand=True)
            self.reason_labels.append(reason_label)

        ttk.Separator(side_panel, orient="horizontal").pack(fill="x", pady=8)

        # Blind-mode explainer callout (UI reference target §12): only
        # shown while blind is ON, directly above recent decisions.
        self.blind_note_frame = tk.Frame(side_panel, bg=theme.TOKENS["info_soft"], padx=8, pady=6)
        self.blind_note_label = tk.Label(
            self.blind_note_frame, text="", bg=theme.TOKENS["info_soft"], fg=theme.TOKENS["info"],
            font=(self.font_ui, 9), wraplength=175, justify="left", anchor="w",
        )
        self.blind_note_label.pack(anchor="w")
        # Not packed here -- _refresh_blind_note() packs/unpacks it based
        # on roles.is_blind(), so it only takes up space while relevant.

        self.recent_decisions_header_label = ttk.Label(
            side_panel, text="YOUR RECENT DECISIONS", font=(self.font_ui, 9, "bold"),
        )
        self.recent_decisions_header_label.pack(anchor="w", pady=(8, 0))
        self.recent_decisions_text = tk.Text(
            side_panel, width=34, height=12, wrap="word",
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.recent_decisions_text.pack(fill="y", expand=True, pady=(4, 0))
        self.recent_decisions_text.config(state="disabled")
        self.current_occurrence_id: str | None = None
        self._screen_search: str | None = None
        self._screen_year: str | None = None
        self._screen_journal: str | None = None
        self._screen_batch_id: str | None = None

    def _refresh_blind_note(self) -> None:
        """UI reference target §12 -- only occupies space while blind."""
        if roles.is_blind(self.conn):
            self.blind_note_label.config(
                text="Blind mode: you see only your own decisions."
                " Conflicts open after the owner turns blind mode off.",
            )
            self.blind_note_frame.pack(fill="x", pady=(0, 8), before=self.recent_decisions_header_label)
        else:
            self.blind_note_frame.pack_forget()

    def _on_record_focus_in(self, event=None) -> None:
        self.record_frame.configure(**theme.focus_outline_options(True))

    def _on_record_focus_out(self, event=None) -> None:
        self.record_frame.configure(**theme.focus_outline_options(False))

    def _refresh_batch_combo(self) -> None:
        batches = screening.list_active_batches(self.conn)
        labels = ["All batches"] + [f"{b['source_name']} ({b['count']})" for b in batches]
        batch_ids: list[str | None] = [None] + [b["batch_id"] for b in batches]
        self._screen_batch_ids = batch_ids
        current = self.screen_batch_combo.current()
        self.screen_batch_combo.config(values=labels)
        if current < 0 or current >= len(labels):
            self.screen_batch_combo.current(0)

    def _refresh_facet_options(self) -> None:
        """Populate the year/journal dropdowns from the reviewer's own
        active occurrences (UI reference target §4). Editable comboboxes,
        not readonly, so a value outside the current list can still be
        typed and applied."""
        years = screening.list_distinct_years(self.conn, self.reviewer_id)
        self.screen_year_entry.config(values=years)
        journals = screening.list_distinct_journals(self.conn, self.reviewer_id)
        self.screen_journal_entry.config(values=journals)

    def _apply_screening_filter(self) -> None:
        self._flush_pending_advance()
        self._screen_search = self.screen_search_entry.get().strip() or None
        self._screen_year = self.screen_year_entry.get().strip() or None
        self._screen_journal = self.screen_journal_entry.get().strip() or None
        idx = self.screen_batch_combo.current()
        self._screen_batch_id = self._screen_batch_ids[idx] if idx >= 0 else None
        self._load_next_undecided()

    def _clear_screening_filter(self) -> None:
        self._flush_pending_advance()
        self.screen_search_entry.delete(0, "end")
        self.screen_year_entry.delete(0, "end")
        self.screen_journal_entry.delete(0, "end")
        self.screen_batch_combo.current(0)
        self.screen_undecided_only_var.set(True)
        self._screen_search = None
        self._screen_year = None
        self._screen_journal = None
        self._screen_batch_id = None
        self._load_next_undecided()

    def _bind_keys(self) -> None:
        def unless_typing(action):
            # event.widget is the widget the keystroke was delivered to, so the
            # guard never depends on querying OS keyboard focus afterwards.
            return lambda event: None if self._is_typing_in_a_text_field(getattr(event, "widget", None)) else action(event)

        self._shortcut_handlers = {
            "<Key-i>": unless_typing(lambda _event: self._decide("include")),
            "<Key-m>": unless_typing(lambda _event: self._decide("maybe")),
            "<Key-e>": unless_typing(lambda _event: self._decide("exclude")),
            "<Key-j>": unless_typing(self._skip_current),
            "<Key-k>": unless_typing(self._navigate_previous),
            "<Key-slash>": self._focus_search,
        }
        for sequence, handler in self._shortcut_handlers.items():
            self.root.bind(sequence, handler)
        self.root.bind("<Control-z>", self._undo_last_decision)

    _TEXT_INPUT_CLASSES = ("Entry", "TEntry", "TCombobox", "Text", "Spinbox")

    def _is_typing_in_a_text_field(self, widget=None) -> bool:
        """Guard for every single-key screening shortcut (i/m/e/j/k and /):
        without this, typing a search term like "intervention" into any
        Entry/Combobox/Text widget would ALSO fire _decide("include")
        via toplevel keypress propagation, since Tk only stops a bound
        key at the toplevel if the widget's own binding returns "break"
        -- which ttk.Entry/Combobox/tk.Text's internal self-insert
        handling does not. A stray screening decision while typing a
        filter is a real data-integrity risk, not a cosmetic bug.

        The record pane's abstract_text is itself a tk.Text widget, but
        it's read-only (state="disabled") and exists specifically as the
        keyboard-focus target for the shortcuts (spec: a visible focus
        ring while the shortcuts are live) -- it must NOT count as "a
        text field the user is typing into", or the shortcuts would stop
        working in their primary intended context.

        ``widget`` is the widget a keystroke was delivered to (a key event's
        ``event.widget``, possibly as a Tk path name); without one, the
        current keyboard focus is used."""
        if isinstance(widget, str):
            try:
                widget = self.root.nametowidget(widget)
            except KeyError:
                widget = None
        if widget is None:
            widget = self.root.focus_get()
        if widget is None:
            return False
        if widget is self.abstract_text:
            return False
        return widget.winfo_class() in self._TEXT_INPUT_CLASSES

    def _focus_search(self, event=None) -> str | None:
        """'/' jumps to the search field (UI reference target §4) --
        but only when focus isn't already in a text field, so typing a
        literal '/' into an existing search term still works normally."""
        if self._is_typing_in_a_text_field(getattr(event, "widget", None)):
            return None
        self.screen_search_entry.focus_set()
        return "break"

    def _load_next_undecided(self) -> None:
        undecided_only = self.screen_undecided_only_var.get()
        occurrence_id = screening.find_next_undecided(
            self.conn, self.reviewer_id, search=self._screen_search, year=self._screen_year,
            journal=self._screen_journal, batch_id=self._screen_batch_id, undecided_only=undecided_only,
        )
        remaining = screening.count_undecided(
            self.conn, self.reviewer_id, search=self._screen_search, year=self._screen_year,
            journal=self._screen_journal, batch_id=self._screen_batch_id, undecided_only=undecided_only,
        )
        filter_note = ""
        if self._screen_search or self._screen_year or self._screen_journal or self._screen_batch_id:
            filter_note = " (filtered)"
        label = "Remaining" if undecided_only else "Matching"
        self.remaining_label.config(text=f"{label}: {remaining}{filter_note}")
        total_matching = screening.count_undecided(
            self.conn, self.reviewer_id, search=self._screen_search, year=self._screen_year,
            journal=self._screen_journal, batch_id=self._screen_batch_id, undecided_only=False,
        )
        self.queue_header_label.config(text=f"QUEUE  {remaining} of {total_matching}{filter_note}")

        if occurrence_id is None:
            self.current_occurrence_id = None
            self.title_label.config(text="No records match." if filter_note else "No undecided records.")
            self.meta_label.config(text="")
            self.position_label.config(text="")
            self.position_progress.config(value=0)
            self._set_abstract("")
            return

        self.current_occurrence_id = occurrence_id
        own_decided = total_matching - remaining
        position = total_matching - remaining + 1
        # "Undecided" here is always the true undecided count regardless
        # of the undecided_only toggle (UI reference target §6) -- when
        # that toggle is off, `remaining` above means something
        # different (matching rows, decided or not), so it is not reused
        # for this line.
        true_undecided = screening.count_undecided(
            self.conn, self.reviewer_id, search=self._screen_search, year=self._screen_year,
            journal=self._screen_journal, batch_id=self._screen_batch_id, undecided_only=True,
        )
        batch_info = screening.batch_info_for_occurrence(self.conn, occurrence_id)
        batch_str = (
            f"Batch {batch_info['ordinal']} ({batch_info['source_format']}, {batch_info['source_name']})"
            if batch_info else ""
        )
        self.position_label.config(
            text=(
                f"Record {position:,} of {total_matching:,}"
                + (f"  \u00b7  {batch_str}" if batch_str else "") + "\n"
                f"{true_undecided:,} undecided  \u00b7  {own_decided:,} decided by you"
            ),
        )
        self.position_progress.config(maximum=max(total_matching, 1), value=position)
        self._render_occurrence(occurrence_id)

    def _refresh_queue_list(self) -> None:
        """Upcoming-records list (UI reference target §5). Reused as the
        bulk-decide selection source (screening-workflow spec §4)."""
        undecided_only = self.screen_undecided_only_var.get()
        queue = screening.list_undecided(
            self.conn, self.reviewer_id, search=self._screen_search, year=self._screen_year,
            journal=self._screen_journal, batch_id=self._screen_batch_id, undecided_only=undecided_only,
            limit=200,
        )
        self._queue_occurrence_ids = [q["occurrence_id"] for q in queue]
        self.queue_list.delete(*self.queue_list.get_children())
        for i, q in enumerate(queue):
            title = q["title"] or "(no title)"
            # UI reference target §5: "year · journal · record#" as a
            # distinct field per row -- "#N" here is this record's
            # 1-based position in the current filtered queue, the
            # nearest stable meaning available without a separate
            # global record-numbering scheme.
            meta_parts = [x for x in [q.get("year"), q.get("journal")] if x]
            meta_parts.append(f"#{i + 1}")
            meta = " \u00b7 ".join(meta_parts)
            is_current = q["occurrence_id"] == self.current_occurrence_id
            # UI reference target §5: an explicit "Now" marker on the
            # current row, since the accent-soft fill alone (--accent-soft
            # the soft accent fill from the theme is too close to white to read reliably -- color is
            # never the only signal here either.
            prefix = "\u25b8 Now  " if is_current else ""
            self.queue_list.insert(
                "", "end", iid=q["occurrence_id"],
                text=f"{prefix}{title}\n{meta}",
                tags=("current",) if is_current else (),
            )

    def _on_queue_double_click(self, event) -> None:
        """Jump directly to a clicked queue entry instead of only the
        next-undecided record (UI reference target §5: a browsable
        upcoming list, not just bulk-select scaffolding)."""
        self._flush_pending_advance()
        occurrence_id = self.queue_list.identify_row(event.y)
        if not occurrence_id or occurrence_id not in self._queue_occurrence_ids:
            return
        self._jump_to_queue_index(self._queue_occurrence_ids.index(occurrence_id))

    def _jump_to_queue_index(self, idx: int) -> None:
        """Shared navigation core for the queue list double-click and the
        J/K (next/prev, UI reference target §14) keyboard shortcuts."""
        if idx < 0 or idx >= len(self._queue_occurrence_ids):
            return
        occurrence_id = self._queue_occurrence_ids[idx]
        self.current_occurrence_id = occurrence_id
        total = len(self._queue_occurrence_ids)
        true_undecided = screening.count_undecided(self.conn, self.reviewer_id, undecided_only=True)
        own_decided = screening.count_undecided(self.conn, self.reviewer_id, undecided_only=False) - true_undecided
        batch_info = screening.batch_info_for_occurrence(self.conn, occurrence_id)
        batch_str = (
            f"Batch {batch_info['ordinal']} ({batch_info['source_format']}, {batch_info['source_name']})"
            if batch_info else ""
        )
        self.position_label.config(
            text=(
                f"Record {idx + 1:,} of {total:,}"
                + (f"  \u00b7  {batch_str}" if batch_str else "") + "\n"
                f"{true_undecided:,} undecided  \u00b7  {own_decided:,} decided by you"
            ),
        )
        self.position_progress.config(maximum=max(total, 1), value=idx + 1)
        self._render_occurrence(occurrence_id)
        self._refresh_queue_list()

    def _skip_current(self, _event=None) -> None:
        """J: move to the next record in the queue without casting a
        vote (UI reference target §9/§14). Does not reorder or hide the
        skipped record -- it is simply not the current one anymore."""
        self._flush_pending_advance()
        if self.current_occurrence_id not in self._queue_occurrence_ids:
            return
        idx = self._queue_occurrence_ids.index(self.current_occurrence_id)
        self._jump_to_queue_index(idx + 1)

    def _navigate_previous(self, _event=None) -> None:
        """K: move to the previous record in the queue (UI reference
        target §14)."""
        self._flush_pending_advance()
        if self.current_occurrence_id not in self._queue_occurrence_ids:
            return
        idx = self._queue_occurrence_ids.index(self.current_occurrence_id)
        self._jump_to_queue_index(idx - 1)

    def _bulk_decide(self, decision: str) -> None:
        self._flush_pending_advance()
        sel = self.queue_list.selection()
        if not sel:
            messagebox.showerror("Nothing selected", "Select one or more records in the queue first.")
            return
        occurrence_ids = list(sel)
        reason = None
        if decision == "exclude":
            reason = self._prompt_exclusion_reason()
            if not reason:
                return
        n = screening.bulk_cast_vote(
            self.conn, occurrence_ids=occurrence_ids, reviewer_id=self.reviewer_id,
            decision=decision, reason=reason,
        )
        self._set_status(f"Bulk {decision}d {n} record(s).")
        self.refresh_all_tabs()

    def _render_occurrence(self, occurrence_id: str) -> None:
        fields = self._load_fields(occurrence_id)
        self.title_label.config(text=fields.get("title") or "(no title)")
        authors = ", ".join(fields.get("authors") or [])
        meta_parts = [authors, fields.get("journal"), fields.get("year")]
        doi = fields.get("doi")
        if doi:
            meta_parts.append(f"DOI: {doi}")
        meta = " \u00b7 ".join(x for x in meta_parts if x)
        self.meta_label.config(text=meta)
        self._set_abstract(fields.get("abstract") or "")

    # UI reference target §8: a structured abstract's section headers
    # (case-insensitive label, optional trailing colon, start of line).
    _ABSTRACT_SECTION_HEADERS = ("BACKGROUND", "METHODS", "RESULTS", "CONCLUSIONS")

    def _set_abstract(self, text: str) -> None:
        self.abstract_text.config(state="normal")
        self.abstract_text.delete("1.0", "end")
        self.abstract_text.insert("1.0", text)
        term = getattr(self, "_screen_search", None)
        if term:
            # Display-only highlight of the active "/" search; changes no data.
            count = tk.IntVar(master=self.abstract_text)  # this root's interpreter, not tk's default root
            start = "1.0"
            while True:
                start = self.abstract_text.search(term, start, stopindex="end", nocase=True, count=count)
                if not start or not count.get():
                    break
                end = f"{start}+{count.get()}c"
                self.abstract_text.tag_add("hit", start, end)
                start = end
        for lineno, line in enumerate(text.split("\n"), start=1):
            stripped = line.strip().rstrip(":").upper()
            if stripped in self._ABSTRACT_SECTION_HEADERS:
                self.abstract_text.tag_add("section-header", f"{lineno}.0", f"{lineno}.end")
        self.abstract_text.config(state="disabled")

    def _refresh_recent_decisions(self) -> None:
        """UI reference target §11 -- the reviewer's own last decisions
        only; blind-safe because recent_decisions_for_reviewer never
        reads another reviewer's votes."""
        recent = screening.recent_decisions_for_reviewer(self.conn, self.reviewer_id)
        if recent:
            self.recent_decisions_header_label.config(
                text=f"YOUR RECENT DECISIONS   Ctrl+Z undoes #{recent[0]['number']}",
            )
        else:
            self.recent_decisions_header_label.config(text="YOUR RECENT DECISIONS")
        self.recent_decisions_text.config(state="normal")
        self.recent_decisions_text.delete("1.0", "end")
        if not recent:
            self.recent_decisions_text.insert("1.0", "No decisions yet.")
        else:
            glyphs = {"include": "Include", "maybe": "? Maybe", "exclude": "Exclude"}
            lines = []
            for d in recent:
                label = glyphs.get(d["decision"], d["decision"])
                reason = f" -- {d['reason']}" if d["reason"] else ""
                lines.append(f"#{d['number']}  {label}{reason}\n{d['title'] or d['occurrence_id']}")
            self.recent_decisions_text.insert("1.0", "\n\n".join(lines))
        self.recent_decisions_text.config(state="disabled")

    def _undo_last_decision(self, _event=None) -> str | None:
        """Ctrl+Z: retract this reviewer's most recent decision (UI
        reference target §9/§11). Never touches another reviewer's
        votes -- undo_last_vote is scoped to self.reviewer_id."""
        if self._is_typing_in_a_text_field(getattr(_event, "widget", None)):
            return None
        self._flush_pending_advance()
        undone = screening.undo_last_vote(self.conn, self.reviewer_id)
        if undone is None:
            self._set_status("Nothing to undo.")
            return "break"
        fields = self._load_fields(undone["occurrence_id"])
        title = fields.get("title") or undone["occurrence_id"]
        self._set_status(f"Undone: {undone['decision'].capitalize()} (#{undone['n']} {title})")
        self._load_next_undecided()
        self._refresh_recent_decisions()
        self._refresh_queue_list()
        self._refresh_conflicts_tab()
        self._refresh_fulltext_tab()
        self._refresh_prisma_tab()
        self._refresh_nav_badges()
        return "break"

    def _set_exclusion_armed(self, armed: bool) -> None:
        """While an Exclude waits for its reason, the side-panel reason list
        is the thing the next key (1-7) picks from: tint it, color its keys
        with the exclude hue, and ring the Exclude button. Display only."""
        self.exclusion_reasons_armed = armed
        row_style, label_style = ("ArmedReason.TFrame", "ArmedReason.TLabel") if armed else ("TFrame", "TLabel")
        key_color = theme.TOKENS["exclude"] if armed else theme.TOKENS["ink"]
        key_border = theme.TOKENS["exclude_border"] if armed else theme.TOKENS["line_strong"]
        for row, label, keycap in zip(self.reason_rows, self.reason_labels, self.reason_keycaps):
            row.configure(style=row_style)
            label.configure(style=label_style)
            keycap.configure(foreground=key_color, highlightbackground=key_border, highlightcolor=key_border)
        self.exclude_button.set_armed(armed)

    def _prompt_exclusion_reason(self) -> str | None:
        """Numbered 1-7 exclusion-reason picker (UI reference target
        §10): a closed project taxonomy instead of free text. A
        reviewer can still cancel (Escape or closing the window), which
        records no vote -- exclude without a reason remains impossible.
        Split out as its own method (rather than inlined in `_decide`)
        so tests can monkeypatch it instead of driving a real modal."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Exclusion reason")
        dialog.transient(self.root)
        dialog.grab_set()
        result: dict[str, str | None] = {"reason": None}

        ttk.Label(
            dialog, text="E, then 1-7 -- pick an exclusion reason:", font=(self.font_ui, 10, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 6))
        for i, reason_text in enumerate(screening.EXCLUSION_REASONS, start=1):
            row = ttk.Frame(dialog)
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(
                row, text=str(i), width=2, relief="flat", borderwidth=0, font=(self.font_mono, 9, "bold"),
                bg=theme.TOKENS["surface"], fg=theme.TOKENS["exclude"], highlightthickness=1,
                highlightbackground=theme.TOKENS["exclude_border"], highlightcolor=theme.TOKENS["exclude_border"],
            ).pack(side="left")
            ttk.Label(row, text=reason_text, wraplength=650).pack(side="left", padx=(8, 0), fill="x", expand=True)

        def pick(n: int) -> None:
            if 1 <= n <= len(screening.EXCLUSION_REASONS):
                result["reason"] = screening.EXCLUSION_REASONS[n - 1]
                dialog.destroy()

        # Number keys are bound only on this dialog, which exists only
        # while an exclude decision is pending -- so 1-7 never fires
        # accidentally outside the exclude flow (Tk feasibility note).
        for i in range(1, len(screening.EXCLUSION_REASONS) + 1):
            dialog.bind(str(i), lambda e, n=i: pick(n))
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        dialog.focus_set()
        self.root.wait_window(dialog)
        return result["reason"]

    def _decide(self, decision: str) -> None:
        # A key pressed under the previous stamp first finishes that advance,
        # so this decision lands on the record now on screen, never the last one.
        self._flush_pending_advance()
        if self.current_occurrence_id is None:
            return
        reason = None
        if decision == "exclude":
            self._set_exclusion_armed(True)
            try:
                reason = self._prompt_exclusion_reason()
            finally:
                self._set_exclusion_armed(False)
            if not reason:
                return  # cancelled; do not record a reasonless exclude
        fields = self._load_fields(self.current_occurrence_id)
        screening.cast_vote(
            self.conn, occurrence_id=self.current_occurrence_id,
            reviewer_id=self.reviewer_id, decision=decision, reason=reason,
        )
        decision_word = decision.capitalize()
        reason_note = f" -- {reason}" if reason else ""
        title = fields.get("title") or self.current_occurrence_id
        self._set_status(f"Saved: {decision_word}{reason_note} ({title})")
        # The vote is already written. The stamp is decoration on top of it.
        # The stamp belongs to the Screening tab; anywhere else, or under
        # reduced motion, the queue advances at once.
        on_screening = self.notebook.index("current") == self._tab_ids.index("screening")
        if display_prefs.reduced_motion() or not on_screening:
            self._finish_decision()
            return
        self._show_decision_stamp(decision, reason)
        self._pending_advance = self.root.after(self._STAMP_MS, self._finish_decision)

    def _finish_decision(self) -> None:
        """Advance past a saved decision and refresh what depends on it."""
        self._pending_advance = None
        self._clear_decision_stamp()
        self._load_next_undecided()
        self._refresh_recent_decisions()
        self._refresh_queue_list()
        self._refresh_conflicts_tab()
        self._refresh_fulltext_tab()
        self._refresh_prisma_tab()
        self._refresh_nav_badges()

    def _flush_pending_advance(self) -> None:
        """Finish a decision still showing its stamp, right now."""
        if getattr(self, "_pending_advance", None) is None:
            return
        self.root.after_cancel(self._pending_advance)
        self._finish_decision()

    # ---- decision stamp (direction 02, R4) ----

    _STAMP_MS = 170
    _STAMP_WORDS = {"include": "INCLUDED", "maybe": "MAYBE", "exclude": "EXCLUDED"}

    def _show_decision_stamp(self, decision: str, reason: str | None) -> None:
        """A date-due style stamp over the record card: lands large and pale,
        settles at full color 16 ms later, and is removed when the queue
        advances. It only ever shows this reviewer's own decision."""
        self._clear_decision_stamp()
        canvas = tk.Canvas(
            self.screen_record_card, width=280, height=104, background=theme.TOKENS["surface"],
            highlightthickness=0, borderwidth=0,
        )
        canvas.place(relx=0.5, rely=0.45, anchor="center")
        self._stamp = canvas
        word = self._STAMP_WORDS[decision]
        detail = reason.upper() if reason else None
        self._draw_stamp(canvas, word, detail, theme.TOKENS[f"{decision}_border"], 23)
        self._stamp_settle_job = self.root.after(
            16, lambda: self._draw_stamp(canvas, word, detail, theme.TOKENS[decision], 20),
        )

    def _draw_stamp(self, canvas: tk.Canvas, word: str, detail: str | None, color: str, size: int) -> None:
        self._stamp_settle_job = None
        if self._stamp is not canvas or not canvas.winfo_exists():
            return
        canvas.delete("all")
        cx, cy = 140, 52
        cos, sin = math.cos(math.radians(7)), math.sin(math.radians(7))

        def rotated(points):
            # Tk's y axis points down: this turns the box 7 degrees counter-clockwise.
            return [c for x, y in points for c in (cx + x * cos + y * sin, cy - x * sin + y * cos)]

        half_w, half_h = 120, (32 if detail else 24)
        for inset, width in ((0, 3), (6, 1)):
            w, h = half_w - inset, half_h - inset
            canvas.create_polygon(rotated([(-w, -h), (w, -h), (w, h), (-w, h)]), outline=color, fill="", width=width)
        word_x, word_y = rotated([(0, -8 if detail else 0)])
        canvas.create_text(word_x, word_y, text=word, angle=7, fill=color, font=(self.font_mono, size, "bold"))
        if detail:
            detail_x, detail_y = rotated([(0, 17)])
            canvas.create_text(detail_x, detail_y, text=detail, angle=7, fill=color, font=(self.font_mono, 8, "bold"))

    def _cancel_motion_on_close(self, event) -> None:
        if event.widget is not self.root:
            return
        for job in (self._pending_advance, self._stamp_settle_job):
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except tk.TclError:
                    pass
        self._pending_advance = None
        self._stamp_settle_job = None
        self._stamp = None

    def _clear_decision_stamp(self) -> None:
        if self._stamp_settle_job is not None:
            self.root.after_cancel(self._stamp_settle_job)
            self._stamp_settle_job = None
        if self._stamp is not None:
            self._stamp.destroy()
            self._stamp = None

    # ---- maybe re-review tab (this reviewer's own 'maybe' decisions) ----

    def _build_maybe_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=(16, 10))
        self.notebook.add(frame, text="Maybe re-review")

        self.maybe_reference_state = tk.StringVar(master=self.root, value="")
        ttk.Label(
            frame, textvariable=self.maybe_reference_state, style="SectionHeading.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text="Your own 'maybe' decisions, for a second look (blind-safe -- never another reviewer's). Search, counts, and status use only your own votes.",
            style="SectionHint.TLabel",
        ).pack(anchor="w")

        self.maybe_columns = ttk.Frame(frame)
        self.maybe_columns.pack(fill="both", expand=True, pady=(8, 0))
        self.maybe_columns.grid_columnconfigure(0, weight=25, minsize=250, uniform="maybe-cards")
        self.maybe_columns.grid_columnconfigure(1, weight=48, minsize=420, uniform="maybe-cards")
        self.maybe_columns.grid_columnconfigure(2, weight=28, minsize=280, uniform="maybe-cards")
        self.maybe_columns.rowconfigure(0, weight=1)
        self.maybe_queue_card = ttk.Frame(self.maybe_columns, padding=12, style="Card.TFrame")
        self.maybe_queue_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.maybe_detail_card = ttk.Frame(self.maybe_columns, padding=12, style="Card.TFrame")
        self.maybe_detail_card.grid(row=0, column=1, sticky="nsew", padx=6)
        self.maybe_support_card = ttk.Frame(self.maybe_columns, padding=12, style="Card.TFrame")
        self.maybe_support_card.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.maybe_queue_panel = ttk.Frame(self.maybe_queue_card)
        self.maybe_queue_panel.pack(fill="both", expand=True)
        self.maybe_detail_panel = ttk.Frame(self.maybe_detail_card, width=416)
        self.maybe_detail_panel.pack(fill="both", expand=True)
        self.maybe_support_panel = ttk.Frame(self.maybe_support_card)
        self.maybe_support_panel.pack(fill="both", expand=True)

        # Item 9: search operates strictly on top of the own-vote
        # filter already applied by `list_maybe_decisions_for_reviewer`
        # -- it never queries the database directly, so it cannot
        # widen exposure beyond the reviewer-scoped set.
        ttk.Label(self.maybe_queue_panel, text="Your maybe-vote queue", style="SectionHeading.TLabel").pack(anchor="w")
        self.maybe_queue_count_label = ttk.Label(self.maybe_queue_panel, text="0 in this reviewer's queue.", foreground=theme.TOKENS["muted"])
        self.maybe_queue_count_label.pack(anchor="w", pady=(2, 6))
        ttk.Label(self.maybe_queue_panel, text="Current reviewer only  ·  Blind-safe", foreground=theme.TOKENS["accent"]).pack(anchor="w", pady=(0, 6))
        search_frame = ttk.Frame(self.maybe_queue_panel)
        search_frame.pack(fill="x", pady=(0, 4))
        ttk.Label(search_frame, text="Search:").pack(side="left")
        self.maybe_search_var = tk.StringVar(master=self.root)
        self.maybe_search_var.trace_add("write", lambda *a: self._on_maybe_search_changed())
        self.maybe_search_entry = ttk.Entry(search_frame, textvariable=self.maybe_search_var)
        self.maybe_search_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))

        self.maybe_status_label = ttk.Label(self.maybe_queue_panel, text="", foreground=theme.TOKENS["muted"], wraplength=220)
        self.maybe_status_label.pack(anchor="w", pady=(0, 6))
        self.maybe_focus_label = ttk.Label(
            self.maybe_queue_panel, text="Keyboard focus is on the Maybe queue", foreground=theme.TOKENS["muted"], wraplength=220,
        )
        self.maybe_focus_label.pack(anchor="w", pady=(0, 6))
        self.maybe_feedback_label = ttk.Label(self.maybe_queue_panel, text="", foreground=theme.TOKENS["accent"], wraplength=220)
        self.maybe_feedback_label.pack(anchor="w", pady=(0, 6))

        # Tk feasibility notes: Treeview for the queue with stable
        # occurrence IDs as item IDs (not row indexes, which the prior
        # Listbox+curselection design relied on).
        self.maybe_queue_frame = ttk.Frame(self.maybe_queue_panel)
        self.maybe_queue_frame.pack(fill="both", expand=True, pady=(0, 6))
        self.maybe_tree = ttk.Treeview(self.maybe_queue_frame, columns=("meta",), show="tree headings", height=12, style="MaybeQueue.Treeview", selectmode="browse")
        maybe_queue_style = ttk.Style(self.root)
        maybe_queue_style.configure("MaybeQueue.Treeview", background=theme.TOKENS["surface"], fieldbackground=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"])
        maybe_queue_style.map(
            "MaybeQueue.Treeview",
            background=[("selected", theme.TOKENS["accent_soft"])],
            foreground=[("selected", theme.TOKENS["ink"])],
        )
        self.maybe_tree.bind("<Button-1>", lambda event: self._maybe_mouse_focus(event), add="+")
        self.maybe_tree.heading("#0", text="Record")
        self.maybe_tree.column("#0", width=220, minwidth=140, stretch=True)
        self.maybe_tree.tag_configure("maybe-row", foreground=theme.TOKENS["maybe"])
        self.maybe_tree.tag_configure("maybe-selected", background=theme.TOKENS["accent_soft"], foreground=theme.TOKENS["ink"])
        self.maybe_tree.tag_configure("maybe-keyboard-focus", background=theme.TOKENS["accent"], foreground=theme.TOKENS["surface"])
        self.maybe_tree.tag_configure("maybe-normal", background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"])
        self.maybe_queue_scroll = ttk.Scrollbar(self.maybe_queue_frame, orient="vertical", command=self.maybe_tree.yview)
        self.maybe_tree.configure(yscrollcommand=self.maybe_queue_scroll.set)
        self.maybe_tree.pack(side="left", fill="both", expand=True)
        self.maybe_queue_scroll.pack(side="right", fill="y")
        self.maybe_tree.bind("<ButtonRelease-1>", lambda event: self._maybe_mouse_select(event), add="+")
        self.maybe_tree.bind("<Double-1>", self._maybe_jump_to_click, add="+")
        self.maybe_queue_empty_label = ttk.Label(
            self.maybe_queue_frame, text="No maybe records are pending re-review.", foreground=theme.TOKENS["muted"],
            wraplength=210, justify="center",
        )
        self.maybe_queue_empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.maybe_tree.bind("<<TreeviewSelect>>", lambda e: self._render_maybe_detail())
        self.maybe_tree.bind("<KeyPress>", self._maybe_tree_keypress, add="+")
        self.maybe_tree.bind("<FocusIn>", lambda event: self._set_maybe_queue_focus(True), add="+")
        self.maybe_tree.bind("<FocusOut>", lambda event: self._set_maybe_queue_focus(False), add="+")

        ttk.Label(self.maybe_detail_panel, text="RE-REVIEW RECORD", style="SectionHeading.TLabel").pack(anchor="w")
        self.maybe_detail_text = tk.Text(
            self.maybe_detail_panel, height=12, wrap="word", font=(self.font_ui, 10),
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.maybe_detail_text.tag_configure("maybe_heading", font=(self.font_title, 15), foreground=theme.TOKENS["ink"])
        self.maybe_detail_text.tag_configure("maybe-panel-heading", font=(self.font_ui, 9, "bold"), foreground=theme.TOKENS["muted"])
        self.maybe_detail_text.tag_configure("maybe_meta", font=(self.font_ui, 10), foreground=theme.TOKENS["muted"])
        self.maybe_detail_text.tag_configure("maybe_vote", font=(self.font_ui, 10, "bold"), foreground=theme.TOKENS["accent"])
        self.maybe_detail_text.tag_configure("maybe_vote_badge", font=(self.font_ui, 10, "bold"), foreground=theme.TOKENS["accent"], background=theme.TOKENS["accent_soft"])
        self.maybe_detail_text.tag_configure("maybe-meta", font=(self.font_ui, 9), foreground=theme.TOKENS["muted"])
        self.maybe_detail_text.tag_configure("maybe-placeholder", font=(self.font_ui, 10), foreground=theme.TOKENS["muted"])
        self.maybe_detail_text.config(state="disabled")
        self.maybe_detail_text.pack(fill="both", expand=True, pady=(6, 0))

        # Item 6: a real three-way Include/Maybe/Exclude re-decision
        # bar, reusing the Screening decision-bar styling (same
        # TOKENS fills, same tk.Button-not-ttk pattern) rather than
        # the generic two-button bar this tab had before.
        ttk.Label(self.maybe_support_panel, text="DECISION SUPPORT", style="SectionHeading.TLabel").pack(anchor="w")
        ttk.Label(self.maybe_support_panel, text="OWN VOTE ONLY · BLIND-SAFE", style="SectionHint.TLabel").pack(anchor="w", pady=(2, 4))
        ttk.Label(self.maybe_support_panel, text="EXCLUSION REASONS", style="SectionHint.TLabel").pack(anchor="w")
        ttk.Label(
            self.maybe_support_panel,
            text="Choosing Exclude requires exactly one project reason.",
            wraplength=255, justify="left",
        ).pack(anchor="w", pady=(2, 4))
        ttk.Label(
            self.maybe_support_panel,
            text="Use Exclude… to choose the required reason before saving.",
            wraplength=255, justify="left", foreground=theme.TOKENS["muted"],
        ).pack(anchor="w", pady=(0, 4))
        self.maybe_reason_var = tk.IntVar(master=self.root, value=0)
        self.maybe_reason_buttons = []
        # Atkinson Hyperlegible lines run ~2px taller than Segoe UI at 9pt;
        # zero vertical padding keeps all seven reasons and the keyboard
        # guide inside the support card at 1280x800.
        ttk.Style(self.root).configure("MaybeReason.TRadiobutton", padding=(4, 0))
        for index, reason_text in enumerate(screening.EXCLUSION_REASONS, start=1):
            button = ttk.Radiobutton(
                self.maybe_support_panel, text=reason_text,
                variable=self.maybe_reason_var, value=index,
                command=self._update_maybe_exclude_availability, style="MaybeReason.TRadiobutton",
            )
            button.state(["disabled"])
            button.pack(anchor="w", fill="x", pady=0)
            self.maybe_reason_buttons.append(button)
        ttk.Label(self.maybe_support_panel, text="QUEUE BEHAVIOR", style="SectionHint.TLabel").pack(anchor="w", pady=(4, 0))
        ttk.Label(
            self.maybe_support_panel,
            text="Re-deciding updates your vote history. A final Include/Exclude removes the record from this queue.",
            wraplength=255, justify="left", foreground=theme.TOKENS["muted"],
        ).pack(anchor="w", pady=(2, 4))
        self.maybe_blind_gate_frame = tk.Frame(
            self.maybe_support_panel, bg=theme.TOKENS["info_soft"], padx=8, pady=6,
        )
        ttk.Label(self.maybe_blind_gate_frame, text="BLIND INTEGRITY GATE", style="SectionHeading.TLabel").pack(anchor="w")
        self.maybe_blind_gate_label = tk.Label(
            self.maybe_blind_gate_frame,
            text="Your active Maybe votes are listed here; no other reviewer’s titles or decisions appear.",
            bg=theme.TOKENS["info_soft"], fg=theme.TOKENS["info"], font=(self.font_ui, 9),
            wraplength=255, justify="left", anchor="w",
        )
        self.maybe_blind_gate_label.pack(anchor="w", pady=(2, 0))
        self.maybe_blind_gate_frame.pack(fill="x", pady=(4, 2))
        self.maybe_keyboard_heading = ttk.Label(self.maybe_support_panel, text="KEYBOARD GUIDE · TAB / ARROWS", style="SectionHint.TLabel")
        self.maybe_keyboard_heading.pack(anchor="w", pady=(2, 0))
        self.maybe_keyboard_help = ttk.Label(
            self.maybe_support_panel, text="Queue-focused: I/M/E/J/K.",
            wraplength=255, justify="left",
        )
        self.maybe_keyboard_help.pack(anchor="w", pady=(2, 0))
        self.maybe_decision_bar = ttk.Frame(self.maybe_detail_panel)
        self.maybe_decision_bar.pack(fill="x", side="bottom", pady=(10, 0))
        self.maybe_include_btn = _KeycapButton(
            self.maybe_decision_bar, key="I", word="Include", decision="include",
            command=lambda: self._maybe_decide("include"), font_ui=self.font_ui, font_mono=self.font_mono,
            font_size=9, vertical_padding=3, keycap_padx=4,
        )
        self.maybe_include_btn.pack(fill="x", side="left", expand=True, padx=(0, 4))
        self.maybe_maybe_btn = _KeycapButton(
            self.maybe_decision_bar, key="M", word="Maybe (keep deferred)", decision="maybe",
            command=lambda: self._maybe_decide("maybe"), font_ui=self.font_ui, font_mono=self.font_mono,
            font_size=9, vertical_padding=3, keycap_padx=4,
        )
        self.maybe_maybe_btn.pack(fill="x", side="left", expand=True, padx=4)
        self.maybe_exclude_btn = _KeycapButton(
            self.maybe_decision_bar, key="E", word="Exclude...", decision="exclude",
            command=lambda: self._maybe_decide("exclude"), font_ui=self.font_ui, font_mono=self.font_mono,
            font_size=9, vertical_padding=3, keycap_padx=4,
        )
        self.maybe_exclude_btn.pack(fill="x", side="left", expand=True, padx=(4, 0))
        self.maybe_exclude_btn.set_enabled(False)
        self.maybe_footer_label = ttk.Label(self.maybe_detail_panel, text="No record selected", foreground=theme.TOKENS["muted"], wraplength=600)
        self.maybe_footer_label.pack(anchor="w", side="bottom", pady=(4, 2))
        self._set_maybe_actions_available(False)
        self._maybe_occurrence_ids: list[str] = []
        self._maybe_record_by_id: dict[str, dict] = {}
        self._maybe_all_records: list[dict] = []

    def _refresh_maybe_tab(self) -> None:
        blind_state = "ON" if roles.is_blind(self.conn) else "OFF"
        self.maybe_reference_state.set(
            f"Blind screening: {blind_state} · own votes only"
        )
        selected = self.maybe_tree.selection()
        selected_iid = selected[0] if selected else None

        records = screening.list_maybe_decisions_for_reviewer(self.conn, self.reviewer_id)
        self._maybe_occurrence_ids = [r["occurrence_id"] for r in records]
        self._maybe_record_by_id = {r["occurrence_id"]: r for r in records}
        self._maybe_all_records = records

        self._render_maybe_queue(preserve_selection=selected_iid)

    def _on_maybe_search_changed(self) -> None:
        self.maybe_feedback_label.config(text="")
        self._render_maybe_queue()

    def _set_maybe_queue_focus(self, focused: bool) -> None:
        if focused and self.maybe_tree.selection():
            item = self.maybe_tree.selection()[0]
            title = self._maybe_record_by_id.get(item, {}).get("title") or "selected record"
            for row_id in self.maybe_tree.get_children(""):
                values = self.maybe_tree.item(row_id, "values")
                if values and str(values[0]).startswith(("Keyboard focus ·", "FOCUS · Keyboard focus ·")):
                    values = ("Maybe",)
                self.maybe_tree.item(row_id, values=values, tags=("maybe-normal",))
            self.maybe_tree.item(item, values=("FOCUS · Keyboard focus · Maybe",), tags=("maybe-keyboard-focus",))
            self.maybe_focus_label.config(text=f"Keyboard focus: {title}  ·  FOCUS", foreground=theme.TOKENS["ink"])
        else:
            for row_id in self.maybe_tree.get_children(""):
                values = self.maybe_tree.item(row_id, "values")
                if values and str(values[0]).startswith(("Keyboard focus ·", "FOCUS · Keyboard focus ·")):
                    values = ("Maybe",)
                self.maybe_tree.item(row_id, values=values, tags=("maybe-normal",))
            self.maybe_focus_label.config(text="Keyboard focus is on the Maybe queue", foreground=theme.TOKENS["muted"])

    def _maybe_mouse_select(self, event) -> None:
        row_id = self.maybe_tree.identify_row(event.y)
        if not row_id:
            return
        self.maybe_tree.selection_set(row_id)
        self.maybe_tree.focus(row_id)
        self._set_maybe_queue_focus(True)
        self._render_maybe_detail()

    def _maybe_mouse_focus(self, event) -> None:
        row_id = self.maybe_tree.identify_row(event.y)
        if row_id:
            self.maybe_tree.selection_set(row_id)
            self.maybe_tree.focus(row_id)
            self._set_maybe_queue_focus(True)

    def _maybe_jump_to_click(self, event) -> str | None:
        row_id = self.maybe_tree.identify_row(event.y)
        if not row_id:
            return None
        self.maybe_tree.selection_set(row_id)
        self.maybe_tree.focus(row_id)
        self._set_maybe_queue_focus(True)
        self._render_maybe_detail()
        return "break"

    def _render_maybe_queue(self, preserve_selection: str | None = "__unset__") -> None:
        """Item 9: search, counts, and status are computed strictly on
        top of `_maybe_all_records` -- the reviewer-scoped list
        `_refresh_maybe_tab` already fetched via
        `list_maybe_decisions_for_reviewer`. The search box filters
        that in-memory list only; it never issues its own database
        query, so it can never widen exposure beyond the own-vote
        filter already applied (matches the feasibility notes: "Query
        the current reviewer's own active Maybe vote set before
        populating the queue, search index, badge, or status text")."""
        if preserve_selection == "__unset__":
            sel = self.maybe_tree.selection()
            preserve_selection = sel[0] if sel else None

        query = self.maybe_search_var.get().strip().lower()
        if query:
            visible = [
                r for r in self._maybe_all_records
                if query in (r["title"] or "").lower()
                or query in (r.get("year") or "").lower()
                or query in (r.get("journal") or "").lower()
            ]
        else:
            visible = self._maybe_all_records

        self.maybe_tree.delete(*self.maybe_tree.get_children())
        for r in visible:
            title = r["title"] or "(no title)"
            meta = " · ".join(x for x in [r.get("year"), r.get("journal")] if x)
            self.maybe_tree.insert(
                "", "end", iid=r["occurrence_id"],
                text=f"{title}", values=("Maybe",),
                tags=(("maybe-keyboard-focus",) if r["occurrence_id"] == preserve_selection and self.maybe_tree.focus_get() == self.maybe_tree else ("maybe-normal",)),
            )

        total = len(self._maybe_all_records)
        shown = len(visible)
        self.maybe_queue_count_label.config(
            text=f"{total} in this reviewer's queue" if total != 1 else "1 in this reviewer's queue"
        )
        if query:
            self.maybe_status_label.config(
                text=f'Showing {shown} of {total} of your maybe records matching "{query}".',
            )
        else:
            self.maybe_status_label.config(
                text=f"{total} of your maybe record" + ("" if total == 1 else "s") + " pending re-review.",
            )

        if preserve_selection and self.maybe_tree.exists(preserve_selection):
            self.maybe_tree.selection_set(preserve_selection)
            self.maybe_tree.see(preserve_selection)
        self._set_maybe_queue_focus(self.maybe_tree.focus_get() == self.maybe_tree)
        if visible:
            self.maybe_queue_empty_label.place_forget()
        else:
            self.maybe_queue_empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self._render_maybe_detail()

    def _update_maybe_exclude_availability(self) -> None:
        has_selection = bool(self.maybe_tree.selection())
        for choice in self.maybe_reason_buttons:
            choice.state(["!disabled"] if has_selection else ["disabled"])
        enabled = has_selection and self.maybe_reason_var.get() > 0
        self.maybe_exclude_btn.set_enabled(enabled)

    def _set_maybe_actions_available(self, available: bool) -> None:
        for button in (self.maybe_include_btn, self.maybe_maybe_btn):
            button.set_enabled(available)

    def _render_maybe_detail(self) -> None:
        """Items 4/5: selecting a record shows its occurrence ID and
        the reviewer's own decision + timestamp -- not just the
        title/year/journal the queue row already carries."""
        self.maybe_detail_text.config(state="normal")
        self.maybe_detail_text.delete("1.0", "end")

        sel = self.maybe_tree.selection()
        if not sel:
            self.maybe_detail_text.config(state="disabled")
            self.maybe_decision_bar.pack_forget()
            self.maybe_footer_label.config(text="No record selected", foreground=theme.TOKENS["muted"])
            self._set_maybe_actions_available(False)
            self._update_maybe_exclude_availability()
            return
        occurrence_id = sel[0]
        r = self._maybe_record_by_id.get(occurrence_id)
        if r is None:
            self.maybe_detail_text.config(state="disabled")
            self.maybe_decision_bar.pack_forget()
            self.maybe_footer_label.config(text="No record selected", foreground=theme.TOKENS["muted"])
            self._set_maybe_actions_available(False)
            self._update_maybe_exclude_availability()
            return

        self.maybe_detail_text.insert("end", "\n", "maybe-panel-heading")
        self.maybe_detail_text.insert("end", "Your current vote · Maybe\n", "maybe_vote_badge")
        fields = self._load_fields(occurrence_id)
        authors = fields.get("authors") or "Authors not provided."
        abstract = fields.get("abstract") or "No abstract is available for this occurrence."
        self.maybe_detail_text.insert("end", f"{r['title'] or '(no title)'}\n", "maybe_heading")
        self.maybe_detail_text.insert("end", f"{authors} · {r.get('journal') or 'Journal not provided'} · {r.get('year') or 'Year not provided'}\n", "maybe_meta")
        self.maybe_detail_text.insert("end", f"Occurrence ID: {occurrence_id}\n\n", "maybe-meta")
        self.maybe_detail_text.insert("end", "No other reviewers’ vote, reason, or status is displayed.\n\n", "maybe-placeholder")
        self.maybe_detail_text.insert("end", "SOURCE ABSTRACT / EXCERPT\n", "maybe-panel-heading")
        self.maybe_detail_text.insert("end", f"{abstract}\n", "maybe-placeholder")
        self.maybe_detail_text.insert("end", "\n")
        self.maybe_detail_text.insert("end", "Own vote timestamp\n", "maybe-meta")
        self.maybe_detail_text.insert("end", f"{r['decided_at']}\n", "maybe_meta")
        self.maybe_detail_text.config(state="disabled")
        self.maybe_decision_bar.pack(fill="x", side="bottom", pady=(10, 0))
        self.maybe_footer_label.config(text=f"{occurrence_id} · your active Maybe vote", foreground=theme.TOKENS["accent"])
        self._set_maybe_actions_available(True)
        self._update_maybe_exclude_availability()

    def _handle_maybe_shortcut(self, key: str) -> str:
        if not self.maybe_tree.selection():
            return "break"
        if key == "i":
            self._maybe_decide("include")
        elif key == "m":
            self._maybe_decide("maybe")
        elif key == "e":
            self._maybe_decide("exclude")
        elif key in ("j", "k"):
            children = self.maybe_tree.get_children("")
            index = children.index(self.maybe_tree.selection()[0])
            target = index + (1 if key == "j" else -1)
            if 0 <= target < len(children):
                self.maybe_tree.selection_set(children[target])
                self.maybe_tree.focus(children[target])
                self.maybe_tree.see(children[target])
                self._render_maybe_detail()
                title = self._maybe_record_by_id.get(children[target], {}).get("title") or "selected record"
                self._set_status(f"Focused {title} in the Maybe queue.")
                self._set_maybe_queue_focus(True)
        return "break"

    def _maybe_tree_keypress(self, event) -> str | None:
        key = event.keysym.lower()
        if key not in ("i", "m", "e", "j", "k"):
            return None
        self._handle_maybe_shortcut(key)
        return "break"

    def _maybe_decide(self, decision: str) -> None:
        sel = self.maybe_tree.selection()
        if not sel:
            messagebox.showerror("Nothing selected", "Select a record in the Maybe list first.")
            return
        occurrence_id = sel[0]
        reason = None
        reason_index = self.maybe_reason_var.get() - 1 if decision == "exclude" else None
        if decision == "exclude":
            if reason_index is None or reason_index < 0:
                messagebox.showerror("Reason required", "Select exactly one exclusion reason before saving.")
                return
            reason = screening.EXCLUSION_REASONS[reason_index]
        screening.cast_vote(
            self.conn, occurrence_id=occurrence_id, reviewer_id=self.reviewer_id,
            decision=decision, reason=reason,
        )
        decision_copy = {"include": "Included", "maybe": "Kept as Maybe", "exclude": f"Excluded · {reason}"}[decision]
        title = self._maybe_record_by_id.get(occurrence_id, {}).get("title") or "(no title)"
        self._set_status(f"{decision_copy} {title}; your Maybe list updated.")
        self.maybe_feedback_label.config(text=f"{decision_copy} · {title} · your vote history updated.")
        self.refresh_all_tabs()

    # ---- duplicates tab (fuzzy candidate review; grouped into clusters) ----

    def _build_duplicates_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Duplicates")

        ttk.Label(frame, text="Open duplicate clusters (2+ records flagged as possibly the same study):").pack(anchor="w")

        self.dup_columns = ttk.Frame(frame)
        self.dup_columns.pack(fill="both", expand=True, pady=(8, 0))
        self.dup_columns.grid_columnconfigure(0, weight=25, minsize=250)
        self.dup_columns.grid_columnconfigure(1, weight=48, minsize=420)
        self.dup_columns.grid_columnconfigure(2, weight=28, minsize=280)
        self.dup_columns.rowconfigure(0, weight=1)
        self.dup_queue_card = ttk.Frame(self.dup_columns, padding=12, style="Card.TFrame")
        self.dup_queue_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.dup_queue_card.grid_propagate(False)
        self.dup_compare_card = ttk.Frame(self.dup_columns, width=656, padding=12, style="Card.TFrame")
        self.dup_compare_card.grid(row=0, column=1, sticky="nsew", padx=6)
        self.dup_compare_card.grid_propagate(False)
        self.dup_resolution_card = ttk.Frame(self.dup_columns, width=292, padding=12, style="Card.TFrame")
        self.dup_resolution_card.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.dup_resolution_card.grid_propagate(False)
        self.dup_queue_panel = ttk.Frame(self.dup_queue_card, width=220)
        self.dup_queue_panel.pack(fill="both", expand=True)
        self.dup_compare_panel = ttk.Frame(self.dup_compare_card, width=420)
        self.dup_compare_panel.pack(fill="both", expand=True)
        self.dup_resolution_panel = ttk.Frame(self.dup_resolution_card, width=280)
        self.dup_resolution_panel.pack(fill="both", expand=True)

        # UI reference target (Duplicates) item 2: candidates remain an
        # explicit, visible manual queue -- they never silently change
        # screening/PRISMA counts on their own.
        queue_note = tk.Frame(self.dup_queue_panel, bg=theme.TOKENS["info_soft"], padx=8, pady=6)
        queue_note.pack(fill="x", pady=(0, 8))
        self.dup_queue_note_label = tk.Label(
            queue_note, bg=theme.TOKENS["info_soft"], fg=theme.TOKENS["info"], font=(self.font_ui, 9),
            justify="left", anchor="w", wraplength=220,
            text="Manual queue. Candidates remain active and do not change screening or PRISMA"
                 " counts until a reviewer confirms Merge or Keep separate below.",
        )
        self.dup_queue_note_label.pack(anchor="w")
        self.dup_keyboard_help_label = ttk.Label(self.dup_queue_panel, text="Keyboard: Tab through queue, survivor, actions; Up/Down selects", foreground=theme.TOKENS["muted"], wraplength=220)
        self.dup_keyboard_help_label.pack(anchor="w", pady=(0, 6))

        self.dup_queue_list_frame = ttk.Frame(self.dup_queue_panel)
        self.dup_queue_list_frame.pack(fill="both", expand=True)
        self.dup_list = tk.Listbox(
            self.dup_queue_list_frame, height=10, exportselection=False,
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.dup_list.pack(fill="both", expand=True)
        self.dup_list.bind("<<ListboxSelect>>", lambda e: self._render_dup_cluster())
        self.dup_list.bind("<Up>", lambda _event: self._dup_move_selection(-1))
        self.dup_list.bind("<Down>", lambda _event: self._dup_move_selection(1))
        self.dup_list.bind("<FocusIn>", lambda _event: self.dup_list.configure(**theme.focus_outline_options(True)))
        self.dup_list.bind("<FocusOut>", lambda _event: self.dup_list.configure(**theme.focus_outline_options(False)))

        compare_frame = ttk.Frame(self.dup_compare_panel)
        compare_frame.pack(fill="both", expand=True)
        # Word-wrapped, one row per occurrence under each field: long titles
        # wrap with a hanging indent instead of pushing columns off-screen.
        self.dup_compare_text = tk.Text(
            compare_frame, height=6, wrap="word", font=(self.font_mono, 10),
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.dup_compare_text.pack(fill="both", expand=True)
        value_indent = tkfont.Font(root=self.root, font=(self.font_mono, 10)).measure("  #1  ")
        self.dup_compare_text.tag_configure("dup_value", lmargin1=0, lmargin2=value_indent)
        self.dup_compare_text.tag_configure("dup_heading", font=(self.font_ui, 9, "bold"), foreground=theme.TOKENS["muted"])
        self.dup_compare_text.tag_configure("dup_diff", background=theme.TOKENS["maybe_soft"], foreground=theme.TOKENS["ink"])
        self.dup_compare_text.tag_configure("dup_diff_label", foreground=theme.TOKENS["maybe"], font=(self.font_mono, 9, "italic"))
        self.dup_compare_text.tag_configure("sel", background=theme.TOKENS["accent_soft"], foreground=theme.TOKENS["ink"])
        self.dup_compare_text.config(state="disabled")

        survivor_frame = ttk.Frame(self.dup_resolution_panel)
        survivor_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(survivor_frame, text="Keep as survivor:").pack(anchor="w", pady=(0, 4))
        self.dup_survivor_list = tk.Listbox(
            survivor_frame, height=2, exportselection=False,
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["accent"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.dup_survivor_list.bind("<FocusIn>", lambda _event: self.dup_survivor_list.configure(**theme.focus_outline_options(True)))
        self.dup_survivor_list.bind("<FocusOut>", lambda _event: self.dup_survivor_list.configure(**theme.focus_outline_options(False)))
        self.dup_survivor_list.pack(fill="x")

        btns = ttk.Frame(self.dup_resolution_panel)
        btns.pack(fill="x")
        self.dup_merge_button = ttk.Button(btns, text="Merge cluster into selected survivor", command=self._dup_merge_cluster)
        self.dup_merge_button.pack(fill="x", pady=(0, 4))
        self.dup_keep_separate_button = ttk.Button(btns, text="Keep all separate", command=self._dup_keep_separate_cluster)
        self.dup_keep_separate_button.pack(fill="x")

        # UI reference target (Duplicates) item 9: reversibility and
        # append-only history, stated near the action (not buried in the
        # confirmation dialog alone -- that only appears for Merge, not
        # Keep separate, and this note covers both).
        reversibility_note = tk.Frame(self.dup_resolution_panel, bg=theme.TOKENS["info_soft"], padx=8, pady=6)
        reversibility_note.pack(fill="x", pady=(8, 0))
        self.dup_reversibility_note_label = tk.Label(
            reversibility_note, bg=theme.TOKENS["info_soft"], fg=theme.TOKENS["info"], font=(self.font_ui, 9),
            justify="left", anchor="w", wraplength=255,
            text="Reversible and auditable. Merge appends a new append-only event and can be"
                 " undone, restoring the prior active state. Keep separate also appends an"
                 " event; it does not merge anything, so there is nothing to restore.",
        )
        self.dup_reversibility_note_label.pack(anchor="w")

        self._dup_clusters: list[dict] = []
        self._set_dup_actions_available(False)

    def _set_dup_actions_available(self, available: bool) -> None:
        state = "normal" if available else "disabled"
        self.dup_merge_button.configure(state=state)
        self.dup_keep_separate_button.configure(state=state)

    def _refresh_duplicates_tab(self) -> None:
        self._dup_clusters = dedup.list_open_fuzzy_clusters(self.conn)
        self._set_dup_actions_available(False)
        self.dup_list.delete(0, "end")
        if not self._dup_clusters:
            self.dup_list.insert("end", "No open duplicate candidates.")
            self.dup_list.itemconfig(0, foreground=theme.TOKENS["muted"])
            self.dup_list.selection_clear(0, "end")
            self.dup_survivor_list.delete(0, "end")
            self.dup_survivor_list.insert("end", "Select an open candidate pair to choose a survivor.")
            self.dup_survivor_list.itemconfig(0, foreground=theme.TOKENS["muted"])
            self.dup_compare_text.config(state="normal")
            self.dup_compare_text.delete("1.0", "end")
            self.dup_compare_text.insert("end", "NO OPEN DUPLICATE CLUSTERS\n", "dup_heading")
            self.dup_compare_text.insert("end", "Candidates appear here only after review; no records are merged automatically.\n")
            self.dup_compare_text.config(state="disabled")
            return
        for cluster in self._dup_clusters:
            titles = [m.get("title") or "(no title)" for m in cluster["members"].values()]
            n = len(cluster["occurrence_ids"])
            preview = "  <->  ".join(titles[:3]) + (" ..." if n > 3 else "")
            self.dup_list.insert("end", f"[{n} records]  {preview}")
        self.dup_survivor_list.delete(0, "end")
        self.dup_compare_text.config(state="normal")
        self.dup_compare_text.delete("1.0", "end")
        self.dup_compare_text.config(state="disabled")

    def _selected_dup_cluster(self) -> dict | None:
        sel = self.dup_list.curselection()
        if not sel or sel[0] >= len(self._dup_clusters):
            return None
        return self._dup_clusters[sel[0]]

    def _dup_move_selection(self, delta: int) -> str:
        if not self._dup_clusters:
            return "break"
        selected = self.dup_list.curselection()
        current = selected[0] if selected else 0
        target = max(0, min(len(self._dup_clusters) - 1, current + delta))
        self.dup_list.selection_clear(0, "end")
        self.dup_list.selection_set(target)
        self.dup_list.activate(target)
        self.dup_list.see(target)
        self._render_dup_cluster()
        return "break"

    def _dup_provenance(self, occurrence_id: str) -> str:
        """UI reference target (Duplicates) item 5: provenance -- batch,
        source, and import row -- inspectable per occurrence, not just
        the match score/reasons."""
        row = self.conn.execute(
            "SELECT o.locator, b.source_name, b.batch_id"
            " FROM occurrences o JOIN import_batches b ON b.batch_id = o.batch_id"
            " WHERE o.occurrence_id = ?",
            (occurrence_id,),
        ).fetchone()
        if not row:
            return "(provenance unavailable)"
        return f"Batch {row['batch_id'][:12]}... · {row['locator']} · source {row['source_name']}"

    _DUP_FIELD_LABELS = [
        ("title", "Title"), ("authors", "Authors"), ("year", "Year"),
        ("journal", "Journal"), ("doi", "DOI"),
    ]

    def _render_dup_cluster(self) -> None:
        """Render an active comparison, or an explicit non-selectable empty state."""
        cluster = self._selected_dup_cluster()
        t = self.dup_compare_text
        t.config(state="normal")
        t.delete("1.0", "end")
        self.dup_survivor_list.delete(0, "end")
        self._dup_survivor_occurrence_ids: list[str] = []
        if not cluster:
            self._set_dup_actions_available(False)
            t.insert("end", "NO OPEN DUPLICATE CLUSTERS\n", "dup_heading")
            t.insert("end", "Candidates appear here only after review; no records are merged automatically.\n")
            self.dup_survivor_list.insert("end", "Select an open candidate pair to choose a survivor.")
            self.dup_survivor_list.itemconfig(0, foreground=theme.TOKENS["muted"])
            t.config(state="disabled")
            return

        occ_ids = list(cluster["members"].keys())

        field_rows = []
        for key, label in self._DUP_FIELD_LABELS:
            raw_values = [cluster["members"][occ_id].get(key) for occ_id in occ_ids]
            values = [
                "; ".join(v) if isinstance(v, list) else str(v or "")
                for v in raw_values
            ]
            values = [v or "(empty)" for v in values]
            field_rows.append((label, values, len(set(values)) > 1))

        t.insert("end", "MATCH EVIDENCE\n", "dup_heading")
        for pair in cluster["pairs"]:
            reason_labels = {
                "title_similarity": "title similarity",
                "shared_year": "shared publication year",
                "same_first_author": "same first author",
                "doi_match_title_mismatch": "DOI/title mismatch (manual review)",
            }
            reasons = ", ".join(reason_labels.get(reason, reason.replace("_", " ")) or reason for reason in pair["reasons"])
            evidence_lines = f"  Score {round(pair['score'], 2)} · Rule version {dedup.RULE_VERSION}\n"
            evidence_lines += "".join(f"  Match reason: {reason}\n" for reason in reasons.split(", "))
            t.insert("end", evidence_lines)
        t.insert("end", "\n")

        t.insert("end", "OCCURRENCES AND PROVENANCE\n", "dup_heading")
        for number, occ_id in enumerate(occ_ids, start=1):
            t.insert("end", f"  #{number}  {occ_id}\n", "dup_value")
            t.insert("end", f"      {self._dup_provenance(occ_id)}\n", "dup_value")
        t.insert("end", "\n")

        t.insert("end", "FIELD COMPARISON\n", "dup_heading")
        for label, values, differs in field_rows:
            t.insert("end", f"{label}\n")
            for number, value in enumerate(values, start=1):
                t.insert("end", f"  #{number}  ", "dup_value")
                start = t.index("end - 1 char")
                t.insert("end", value, "dup_value")
                if differs:
                    t.tag_add("dup_diff", start, t.index("end - 1 char"))
                t.insert("end", "\n")
            if differs:
                t.insert("end", "      ^ Difference -- raw source values shown unchanged above\n", ("dup_diff_label", "dup_value"))
        t.insert("end", "\n")

        for occ_id in occ_ids:
            self._dup_survivor_occurrence_ids.append(occ_id)
            fields = cluster["members"][occ_id]
            meta = f"{fields.get('title') or '(no title)'} ({fields.get('year') or '?'}, {fields.get('doi') or 'no DOI'})  -- {occ_id}"
            self.dup_survivor_list.insert("end", meta)
        self.dup_survivor_list.configure(height=min(5, max(2, len(occ_ids))))
        self.dup_survivor_list.selection_set(0)
        t.config(state="disabled")
        self._set_dup_actions_available(True)

    def _dup_merge_cluster(self) -> None:
        """UI reference target (Duplicates package) item 8: preview the
        survivor and absorbed occurrence IDs in an explicit confirmation
        before committing -- merge is otherwise a silent, immediate,
        hard-to-notice action on a background queue."""
        cluster = self._selected_dup_cluster()
        if cluster is None:
            return
        sel = self.dup_survivor_list.curselection()
        if not sel:
            messagebox.showerror("Pick a survivor", "Select which record to keep from the list.")
            return
        survivor = self._dup_survivor_occurrence_ids[sel[0]]
        absorbed = [occ_id for occ_id in cluster["occurrence_ids"] if occ_id != survivor]
        survivor_title = cluster["members"].get(survivor, {}).get("title") or survivor
        absorbed_lines = "\n".join(
            f"  - {cluster['members'].get(occ_id, {}).get('title') or '(no title)'}  ({occ_id})"
            for occ_id in absorbed
        )
        confirmed = messagebox.askyesno(
            "Confirm merge",
            f"Survivor (kept): {survivor_title}\n({survivor})\n\n"
            f"Absorbed (merged into survivor):\n{absorbed_lines}\n\n"
            "This is reversible: undo appends a new event and restores the"
            " prior active state.",
        )
        if not confirmed:
            return
        dedup.reviewer_merge_group(self.conn, self.reviewer_id, cluster["candidate_ids"], survivor, absorbed)
        self._set_status(f"Merged {len(absorbed)} occurrence(s) into {survivor}.")
        self.refresh_all_tabs()

    def _dup_keep_separate_cluster(self) -> None:
        cluster = self._selected_dup_cluster()
        if cluster is None:
            return
        dedup.reviewer_keep_separate_group(self.conn, self.reviewer_id, cluster["candidate_ids"])
        self.refresh_all_tabs()

    # ---- conflicts tab ----

    def _build_conflicts_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Conflicts")
        self.conflict_page_heading = ttk.Label(
            frame, text="Conflict resolution · resolve only unblinded disagreements",
            style="SectionHint.TLabel",
        )
        self.conflict_page_heading.pack(anchor="w", pady=(0, 8))
        self.conflict_columns = ttk.Frame(frame)
        self.conflict_columns.pack(fill="both", expand=True)
        self.conflict_columns.grid_columnconfigure(0, weight=28, minsize=300)
        self.conflict_columns.grid_columnconfigure(1, weight=48, minsize=560)
        self.conflict_columns.grid_columnconfigure(2, weight=27, minsize=280)
        self.conflict_columns.rowconfigure(0, weight=1)
        self.conflict_queue_card = ttk.Frame(self.conflict_columns, padding=12, style="Card.TFrame")
        self.conflict_queue_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.conflict_evidence_card = ttk.Frame(self.conflict_columns, width=560, padding=12, style="Card.TFrame")
        self.conflict_evidence_card.grid(row=0, column=1, sticky="nsew", padx=6)
        self.conflict_evidence_card.grid_propagate(False)
        self.conflict_gate_card = ttk.Frame(self.conflict_columns, width=292, padding=12, style="Card.TFrame")
        self.conflict_gate_card.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.conflict_gate_card.grid_propagate(False)
        self.conflict_queue_panel = ttk.Frame(self.conflict_queue_card, width=220)
        self.conflict_queue_panel.pack(fill="both", expand=True)
        self.conflict_evidence_panel = ttk.Frame(self.conflict_evidence_card, width=530)
        self.conflict_evidence_panel.pack(fill="both", expand=True)
        self.conflict_gate_panel = ttk.Frame(self.conflict_gate_card, width=260)
        self.conflict_gate_panel.pack(fill="both", expand=True)

        ttk.Label(self.conflict_queue_panel, text="CONFLICT QUEUE", style="SectionHint.TLabel").pack(anchor="w", pady=(0, 6))
        self.conflicts_lock_label = ttk.Label(
            self.conflict_queue_panel, text="", foreground=theme.TOKENS["info"], wraplength=220,
        )
        self.conflicts_lock_label.pack(anchor="w", pady=(0, 6))
        self.conflict_list_status_label = ttk.Label(
            self.conflict_queue_panel, text="", foreground=theme.TOKENS["info"], wraplength=220,
        )
        self.conflict_list_status_label.pack(anchor="w", pady=(0, 4))
        self.conflict_queue_note_label = ttk.Label(
            self.conflict_queue_panel,
            text="Only open disagreements appear here. IDs identify the record before selection.",
            foreground=theme.TOKENS["muted"], wraplength=220,
        )
        self.conflict_queue_note_label.pack(anchor="w", pady=(0, 6))
        conflict_queue_list_frame = ttk.Frame(self.conflict_queue_panel, height=300)
        conflict_queue_list_frame.pack(fill="x", expand=False)
        conflict_queue_list_frame.pack_propagate(False)
        self.conflict_queue_scroll = ttk.Scrollbar(conflict_queue_list_frame, orient="vertical")
        self.conflict_list = tk.Listbox(
            conflict_queue_list_frame, height=9, exportselection=False,
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["accent"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.conflict_queue_scroll.configure(command=self.conflict_list.yview)
        self.conflict_list.configure(yscrollcommand=self.conflict_queue_scroll.set)
        self.conflict_list.pack(side="left", fill="both", expand=True)
        self.conflict_queue_scroll.pack(side="right", fill="y")
        self.conflict_list.bind("<<ListboxSelect>>", lambda e: self._render_conflict())
        self.conflict_list.bind("<Up>", lambda event: self._move_conflict_selection(-1))
        self.conflict_list.bind("<Down>", lambda event: self._move_conflict_selection(1))
        self.conflict_list.bind("<FocusIn>", lambda _event: self.conflict_list.configure(**theme.focus_outline_options(True)))
        self.conflict_list.bind("<FocusOut>", lambda _event: self.conflict_list.configure(**theme.focus_outline_options(False)))
        self.conflict_queue_keyboard_help = ttk.Label(self.conflict_queue_panel, text="Keyboard: Up/Down changes conflict; Tab reaches evidence and actions", foreground=theme.TOKENS["muted"], wraplength=270)
        self.conflict_queue_keyboard_help.pack(anchor="w", pady=(6, 0))
        self.conflict_empty_label = ttk.Label(
            self.conflict_queue_panel, text="", foreground=theme.TOKENS["muted"], wraplength=220,
        )
        self.conflict_empty_label.pack(anchor="w", pady=(6, 0))

        ttk.Label(self.conflict_evidence_panel, text="REVIEW EVIDENCE", style="SectionHint.TLabel").pack(anchor="w", pady=(0, 5))
        self.conflict_evidence_empty_label = ttk.Label(self.conflict_evidence_panel, text="", foreground=theme.TOKENS["muted"], wraplength=520)
        self.conflict_evidence_empty_label.pack(anchor="w", pady=(0, 4))
        # Decision-derived and packed only when the unblinded refresh permits it.
        self.kappa_label = tk.Label(
            self.conflict_evidence_panel, text="", font=(self.font_ui, 9, "bold"), padx=10, pady=6,
            background=theme.TOKENS["accent_soft"], foreground=theme.TOKENS["accent"], anchor="w", justify="left",
        )
        self.export_packet_btn = ttk.Button(
            self.conflict_evidence_panel, text="Export reviewer packet...", command=self.action_export_reviewer_packet,
        )
        self.export_packet_btn.pack(anchor="w", pady=(0, 6))
        self.merge_votes_btn = ttk.Button(
            self.conflict_evidence_panel, text="Merge votes file...", command=self.action_merge_votes_file, state="disabled",
        )
        self.merge_votes_btn.pack(anchor="w", pady=(0, 6))
        compare_frame = ttk.Frame(self.conflict_evidence_panel)
        compare_frame.pack(fill="both", expand=True, pady=(0, 6))
        self.conflict_detail_text = tk.Text(
            compare_frame, height=8, wrap="word", font=(self.font_ui, 9),
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        conflict_detail_scroll = ttk.Scrollbar(compare_frame, orient="vertical", command=self.conflict_detail_text.yview)
        self.conflict_detail_text.configure(yscrollcommand=conflict_detail_scroll.set)
        conflict_detail_scroll.pack(side="right", fill="y")
        self.conflict_detail_text.pack(side="left", fill="both", expand=True)
        self.conflict_detail_text.tag_configure("conflict_heading", font=(self.font_ui, 9, "bold"), foreground=theme.TOKENS["muted"])
        self.conflict_detail_text.tag_configure("conflict-title", font=(self.font_title, 15), foreground=theme.TOKENS["ink"])
        self.conflict_detail_text.tag_configure("conflict-meta", font=(self.font_ui, 9), foreground=theme.TOKENS["muted"])
        self.conflict_detail_text.tag_configure("conflict-vote", font=(self.font_ui, 10, "bold"), foreground=theme.TOKENS["accent"])
        self.conflict_detail_text.tag_configure("conflict-reason", font=(self.font_ui, 9, "italic"), foreground=theme.TOKENS["muted"])
        self.conflict_detail_text.tag_configure("conflict-timestamp", font=(self.font_mono, 8), foreground=theme.TOKENS["muted"])
        self.conflict_detail_text.config(state="disabled")

        self.conflict_decision_heading = ttk.Label(
            self.conflict_evidence_panel, text="FINAL DECISION · CHOOSE ONE", style="SectionHint.TLabel",
        )
        self.conflict_decision_heading.pack(anchor="w", pady=(0, 4))
        note_frame = ttk.Frame(self.conflict_evidence_panel)
        note_frame.pack(fill="x", pady=(0, 2))
        ttk.Label(note_frame, text="Required resolution note:").pack(side="left")
        ttk.Label(note_frame, text="*required", foreground=theme.TOKENS["exclude"], font=(self.font_ui, 9, "bold")).pack(side="left", padx=(4, 0))
        self.conflict_note_entry = ttk.Entry(note_frame)
        self.conflict_note_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.conflict_note_entry.bind("<KeyRelease>", lambda e: self._update_conflict_note_hint())
        self.conflict_note_hint_label = tk.Label(
            self.conflict_evidence_panel, text="", font=(self.font_ui, 9, "italic"), fg=theme.TOKENS["exclude"], anchor="w",
            background=theme.TOKENS["canvas"],
        )
        self.conflict_note_hint_label.pack(fill="x", pady=(0, 4))
        btns = ttk.Frame(self.conflict_evidence_panel)
        btns.pack(fill="x")
        self.conflict_resolve_include_btn = ttk.Button(
            btns, text="Resolve: Include", command=lambda: self._resolve_conflict("include"), state="disabled", style="Accent.TButton",
        )
        self.conflict_resolve_include_btn.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.conflict_resolve_exclude_btn = ttk.Button(
            btns, text="Resolve: Exclude", command=lambda: self._resolve_conflict("exclude"), state="disabled", style="Quiet.TButton",
        )
        self.conflict_resolve_exclude_btn.pack(side="left", fill="x", expand=True, padx=(4, 0))

        ttk.Label(self.conflict_gate_panel, text="BLIND-REVIEW GATE", style="SectionHint.TLabel").pack(anchor="w", pady=(0, 8))
        self.conflict_gate_state_frame = tk.Frame(self.conflict_gate_panel, bg=theme.TOKENS["maybe_soft"], padx=8, pady=7)
        self.conflict_gate_state_frame.pack(fill="x")
        self.conflict_gate_state_label = tk.Label(
            self.conflict_gate_state_frame, text="Unblinded adjudication", bg=theme.TOKENS["maybe_soft"],
            fg=theme.TOKENS["maybe"], font=(self.font_ui, 9, "bold"), justify="left", anchor="w", wraplength=238,
        )
        self.conflict_gate_state_label.pack(anchor="w")
        self.conflict_blind_preview_frame = tk.Frame(self.conflict_gate_panel, bg=theme.TOKENS["info_soft"], padx=8, pady=7)
        self.conflict_blind_preview_frame.pack(fill="x", pady=(8, 0))
        self.conflict_blind_preview_frame.pack_forget()  # textual locked-state template; never show beside live decisions
        self.conflict_blind_preview_label = tk.Label(
            self.conflict_blind_preview_frame,
            text="Blind mode ON · conflict details hidden\nQueue locked · votes, reasons, and identities are not rendered.",
            bg=theme.TOKENS["info_soft"], fg=theme.TOKENS["info"], font=(self.font_ui, 9), justify="left", anchor="w", wraplength=238,
        )
        self.conflict_blind_preview_label.pack(anchor="w")
        self.conflict_authorization_label = ttk.Label(
            self.conflict_gate_panel, text="", foreground=theme.TOKENS["info"], wraplength=250,
        )
        self.conflict_authorization_label.pack(anchor="w", pady=(8, 0))
        ttk.Separator(self.conflict_gate_panel).pack(fill="x", pady=10)
        ttk.Label(self.conflict_gate_panel, text="APPEND-ONLY RESOLUTION TRAIL", style="SectionHint.TLabel").pack(anchor="w")
        self.conflict_audit_note_label = ttk.Label(
            self.conflict_gate_panel, text="No resolution saved. Save adds the actor, time, final decision, and required note; prior votes remain immutable.",
            foreground=theme.TOKENS["muted"], wraplength=250,
        )
        self.conflict_audit_note_label.pack(anchor="w", pady=(5, 0))
        self.conflict_gate_safety_label = ttk.Label(
            self.conflict_gate_panel, text="Blind isolation takes priority over opening conflict details.",
            foreground=theme.TOKENS["muted"], wraplength=250,
        )
        self.conflict_gate_safety_label.pack(anchor="w", pady=(8, 0))

        self._conflict_occurrence_ids: list[str] = []
        self._update_conflict_note_hint()

    def _update_conflict_note_hint(self) -> None:
        """Item 6: visible empty-state for the required resolution
        note, updated live as the reviewer types -- not just an error
        dialog the first time Resolve is clicked."""
        note_ready = bool(self.conflict_note_entry.get().strip())
        if note_ready:
            self.conflict_note_hint_label.config(text="")
        else:
            self.conflict_note_hint_label.config(text="Empty -- a resolution note is required before resolving.")
        can_resolve = (
            note_ready and self._selected_conflict_occurrence() is not None
            and roles.is_owner(self.conn, self.reviewer_id) and not roles.is_blind(self.conn)
        )
        state = "normal" if can_resolve else "disabled"
        self.conflict_resolve_include_btn.config(state=state)
        self.conflict_resolve_exclude_btn.config(state=state)

    def _refresh_conflicts_tab(self) -> None:
        """Screening-workflow spec §5: "Opening the conflict queue
        requires blind mode off." screening.resolve_conflict documents
        that this is enforced by the UI layer, not the backend -- this
        is that enforcement: while blind, the queue is not populated and
        resolve actions are disabled, with an explanatory lock message
        instead (UI reference target §3's "locked while blind" nav
        state)."""
        if roles.is_blind(self.conn):
            self._conflict_occurrence_ids = []
            self.conflict_list.config(state="normal")
            self.conflict_list.delete(0, "end")
            self.conflict_list.config(state="disabled")
            self.conflict_detail_text.config(state="normal")
            self.conflict_detail_text.delete("1.0", "end")
            self.conflict_detail_text.config(state="disabled")
            self.conflicts_lock_label.config(text="Conflicts are locked while blind mode is ON. The project owner must turn blind mode off to open this queue.")
            self.conflict_empty_label.configure(text="Queue locked · conflicts are unavailable until blind mode is off.")
            self.conflict_list_status_label.configure(text="Blind review is ON. Conflict records are concealed.")
            self.conflict_resolve_include_btn.config(state="disabled")
            self.conflict_resolve_exclude_btn.config(state="disabled")
            self.conflict_gate_state_frame.configure(bg=theme.TOKENS["info_soft"])
            self.conflict_gate_state_label.configure(text="Blind mode ON · conflict details hidden", bg=theme.TOKENS["info_soft"], fg=theme.TOKENS["info"])
            self.conflict_evidence_empty_label.config(text="Conflict evidence is locked while blind mode is on.")
            self.conflict_note_hint_label.config(text="Resolution is unavailable until blind mode is off.")
            self.merge_votes_btn.config(state="disabled")
            self.export_packet_btn.config(state="disabled")
            self.kappa_label.pack_forget()
            self.conflict_blind_preview_frame.pack(fill="x", pady=(8, 0))
            self.conflict_authorization_label.configure(text="Queue locked · votes, reasons, and identities are not rendered.", foreground=theme.TOKENS["info"])
            self.conflict_audit_note_label.configure(text="No resolution available while blind. Prior votes and audit history remain protected.")
            self.conflict_note_entry.config(state="disabled")
            return

        self.conflict_gate_state_frame.configure(bg=theme.TOKENS["maybe_soft"])
        self.conflict_gate_state_label.configure(text="Unblinded adjudication", bg=theme.TOKENS["maybe_soft"], fg=theme.TOKENS["maybe"])
        self.conflict_blind_preview_frame.pack_forget()
        self.conflict_gate_safety_label.configure(text="Blind isolation takes priority over opening conflict details.")
        self.export_packet_btn.config(state="normal")
        if self._conflict_occurrence_ids:
            self.conflict_authorization_label.configure(text="Owner authorization required. Turn blind mode off before resolving a conflict.", foreground=theme.TOKENS["info"])
        self.conflict_audit_note_label.configure(text="No resolution saved. Save adds the actor, time, final decision, and required note; prior votes remain immutable.")
        self.conflict_list.config(state="normal")
        self.conflicts_lock_label.config(text="")
        self.conflict_list_status_label.configure(text="")
        self._conflict_occurrence_ids = screening.list_conflicts(self.conn)
        self.conflict_list.delete(0, "end")
        self.conflict_evidence_empty_label.config(text="")
        if not self._conflict_occurrence_ids:
            self.conflict_empty_label.configure(text="Queue empty · no reviewer conflict is selected.")
            self.conflict_list.insert("end", "No open conflicts.")
            self.conflict_list.itemconfig(0, foreground=theme.TOKENS["muted"])
            self.conflict_detail_text.config(state="normal")
            self.conflict_detail_text.delete("1.0", "end")
            self.conflict_detail_text.insert("end", "NO OPEN CONFLICTS\n", "conflict_heading")
            self.conflict_detail_text.insert("end", "Conflicting votes will appear here only after two reviewers disagree.")
            self.conflict_detail_text.config(state="disabled")
            self.conflict_note_entry.config(state="disabled")
            self.conflict_note_hint_label.config(text="Resolution is unavailable until an open conflict is selected.")
            self.conflict_resolve_include_btn.config(state="disabled")
            self.conflict_resolve_exclude_btn.config(state="disabled")
            self.conflict_evidence_empty_label.config(text="No open conflicts. Conflicting votes will appear here only after two reviewers disagree.")
            self.merge_votes_btn.config(state="normal" if roles.is_owner(self.conn, self.reviewer_id) else "disabled")
            self.export_packet_btn.config(state="normal")
            self.kappa_label.pack(fill="x", pady=(0, 6), before=self.export_packet_btn)
            self._refresh_kappa_strip()
            return
        self.conflict_empty_label.configure(text="")
        self.conflict_evidence_empty_label.config(text="")
        for occ_id in self._conflict_occurrence_ids:
            self.conflict_list.insert("end", occ_id)
        self.conflict_note_entry.config(state="normal")
        self.conflict_note_entry.delete(0, "end")
        self._update_conflict_note_hint()
        self.conflict_resolve_include_btn.config(state="disabled")
        self.conflict_resolve_exclude_btn.config(state="disabled")

        # Items 7/9: owner authorization + blind-off requirement, and
        # append-only audit semantics, stated near the action -- and
        # actually enforced here (buttons disabled for a non-owner),
        # not just displayed. resolve_conflict() has no notion of
        # project ownership (same "UI layer enforces it" pattern as the
        # blind-mode check above), so this is the only place it's held.
        if self.conflict_list.curselection():
            self._render_conflict()
        is_owner = roles.is_owner(self.conn, self.reviewer_id)
        has_selection = self._selected_conflict_occurrence() is not None
        note_ready = bool(self.conflict_note_entry.get().strip())
        can_resolve = is_owner and has_selection and note_ready and not roles.is_blind(self.conn)
        if can_resolve:
            self.conflict_resolve_include_btn.config(state="normal")
            self.conflict_resolve_exclude_btn.config(state="normal")
        else:
            self.conflict_resolve_include_btn.config(state="disabled")
            self.conflict_resolve_exclude_btn.config(state="disabled")
        if is_owner:
            self.conflict_authorization_label.config(
                text="Owner authorization required: only the project owner may resolve conflicts while blind mode is off. Resolving appends an append-only event; prior votes remain in history.",
            )
            can_resolve = (
                self._selected_conflict_occurrence() is not None
                and bool(self.conflict_note_entry.get().strip())
                and is_owner and not roles.is_blind(self.conn)
            )
            state = "normal" if can_resolve else "disabled"
            self.conflict_resolve_include_btn.config(state=state)
            self.conflict_resolve_exclude_btn.config(state=state)
        else:
            owner_id = roles.get_owner(self.conn) or "(unset)"
            self.conflict_authorization_label.config(
                text=f"Owner authorization required: only the project owner ({owner_id}) may resolve conflicts. You are reviewer {self.reviewer_id}, not the owner; resolve controls are disabled.",
            )
        self.merge_votes_btn.config(state="normal" if roles.is_owner(self.conn, self.reviewer_id) else "disabled")

        self.kappa_label.pack(fill="x", pady=(0, 6), before=self.export_packet_btn)
        self._refresh_kappa_strip()

    def _refresh_kappa_strip(self) -> None:
        """Directive A: κ value, Landis-Koch label, raw agreement %, n --
        only called when not blind (see _refresh_conflicts_tab)."""
        kappa = screening.kappa_readout(self.conn, is_blind=False)
        if kappa is None:  # defensive; cannot happen given the is_blind=False call above
            self.kappa_label.config(text="")
            return
        if kappa["status"] != "ok":
            self.kappa_label.config(text=f"Agreement (Cohen's \u03ba): {kappa['label']}")
            return
        self.kappa_label.config(
            text=(
                f"Agreement (Cohen's \u03ba): \u03ba = {kappa['kappa']:.2f}  \u00b7  {kappa['label']}"
                f"  \u00b7  {kappa['agreement']*100:.0f}% raw agreement  \u00b7  n = {kappa['n']} double-decided"
            ),
        )

    def _move_conflict_selection(self, delta: int) -> str:
        if roles.is_blind(self.conn) or not self._conflict_occurrence_ids:
            return "break"
        selected = self.conflict_list.curselection()
        current = selected[0] if selected else 0
        target = max(0, min(len(self._conflict_occurrence_ids) - 1, current + delta))
        self.conflict_list.selection_clear(0, "end")
        self.conflict_list.selection_set(target)
        self.conflict_list.activate(target)
        self.conflict_list.see(target)
        self.conflict_list.event_generate("<<ListboxSelect>>")
        self._render_conflict()
        self._set_status(f"Focused conflict {target + 1} of {len(self._conflict_occurrence_ids)}.")
        return "break"

    def _selected_conflict_occurrence(self) -> str | None:
        sel = self.conflict_list.curselection()
        if not sel:
            return None
        return self._conflict_occurrence_ids[sel[0]]

    def _load_fields(self, occurrence_id: str) -> dict:
        row = self.conn.execute(
            "SELECT fields_json FROM occurrence_fields WHERE occurrence_id = ?", (occurrence_id,)
        ).fetchone()
        return json.loads(row["fields_json"]) if row else {}

    def _render_conflict(self) -> None:
        """UI reference target (Conflicts) items 1/2/3: the selected
        record's own ID and bibliographic fields, plus each vote's
        timestamp -- not just reviewer/decision/reason -- so the
        detail pane carries the same evidence the reference calls
        inspectable."""
        occ_id = self._selected_conflict_occurrence()
        self.conflict_detail_text.config(state="normal")
        self.conflict_detail_text.delete("1.0", "end")
        if occ_id:
            fields = self._load_fields(occ_id)
            self.conflict_detail_text.insert("end", "SELECTED RECORD\n", "conflict_heading")
            self.conflict_detail_text.insert("end", f"{fields.get('title') or '(no title)'}\n", "conflict-title")
            self.conflict_detail_text.insert("end", f"Occurrence ID: {occ_id}\n", "conflict-meta")
            authors = "; ".join(fields.get("authors") or []) or "(none)"
            self.conflict_detail_text.insert(
                "end", f"Authors: {authors}  ·  Year: {fields.get('year') or '?'}\n", "conflict-meta",
            )
            self.conflict_detail_text.insert("end", "\nREVIEWER DECISIONS\n", "conflict_heading")
            votes = screening.votes_for_occurrence(self.conn, occ_id)
            for v in votes:
                reason = f" ({v['reason']})" if v["reason"] else ""
                self.conflict_detail_text.insert(
                    "end", f"{v['reviewer_id']}: {v['decision']}\n", "conflict-vote",
                )
                if reason:
                    self.conflict_detail_text.insert("end", f"Reason: {v['reason']}\n", "conflict-reason")
                self.conflict_detail_text.insert("end", f"Timestamp: {v['created_at']}\n\n", "conflict-timestamp")
        self.conflict_detail_text.config(state="disabled")

    def _resolve_conflict(self, final_decision: str) -> None:
        if roles.is_blind(self.conn):
            messagebox.showerror(
                "Locked while blind",
                "Conflicts are locked while blind mode is ON (screening-workflow spec §5).",
            )
            return
        if not roles.is_owner(self.conn, self.reviewer_id):
            # Defense in depth: the buttons are already disabled for a
            # non-owner in _refresh_conflicts_tab; this covers any path
            # that calls the handler directly (screening.resolve_conflict
            # itself has no notion of project ownership -- the UI layer
            # is the only place this is enforced, same pattern as blind).
            messagebox.showerror(
                "Not permitted",
                f"Only the project owner may resolve conflicts. You are \u201c{self.reviewer_id}\u201d.",
            )
            return
        occ_id = self._selected_conflict_occurrence()
        if occ_id is None:
            return
        note = self.conflict_note_entry.get().strip()
        if not note:
            messagebox.showerror("Note required", "A resolution note is required.")
            return
        screening.resolve_conflict(
            self.conn, occurrence_id=occ_id, final_decision=final_decision,
            resolution_note=note, actor=self.reviewer_id,
        )
        self._set_status(f"Conflict resolved: {final_decision} ({note}).")
        self.conflict_note_entry.delete(0, "end")
        self._update_conflict_note_hint()
        self.refresh_all_tabs()

    def action_export_reviewer_packet(self) -> None:
        """Directive B §1/§5: host-side "Export reviewer packet..." in
        the Conflicts tab's unblinded view. The packet query deliberately
        excludes all screening-vote data; UI gating preserves blind
        isolation without changing the Directive B packet schema."""
        if roles.is_blind(self.conn):
            messagebox.showerror(
                "Locked while blind",
                "Exporting a reviewer packet is available from the unblinded Conflicts view.",
            )
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Screening Workbench reviewer packet", "*.json")],
        )
        if not path:
            return
        result = packets.export_packet(self.conn, path, actor=self.reviewer_id)
        self._set_status(f"Exported reviewer packet: {result['record_count']} record(s) to {os.path.basename(path)}.")
        messagebox.showinfo(
            "Packet exported",
            f"Exported {result['record_count']} record(s) to:\n{path}\n\nNo vote data is included.",
        )

    def action_merge_votes_file(self) -> None:
        """Directive B §4: host-side "Merge votes file..." -- owner-only,
        unblinded view only (both enforced by packets.merge_votes itself;
        this handler surfaces the refusal rather than pre-guessing it)."""
        if roles.is_blind(self.conn):
            messagebox.showerror(
                "Locked while blind",
                "Merging votes requires blind mode to be off (unblinded owner view only).",
            )
            return
        path = filedialog.askopenfilename(filetypes=[("Screening Workbench votes export", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            result = packets.merge_votes(self.conn, path, actor=self.reviewer_id)
        except PermissionError as exc:
            messagebox.showerror("Not permitted", str(exc))
            return
        except ValueError as exc:
            messagebox.showerror("Merge failed", str(exc))
            return
        self._set_status(
            f"Merged votes: {result['merged_count']} merged, {result['skipped_stale_count']} stale skipped,"
            f" {result['quarantined_count']} quarantined.",
        )
        messagebox.showinfo(
            "Votes merged",
            f"Merged: {result['merged_count']}\n"
            f"Skipped (stale, host already fresher): {result['skipped_stale_count']}\n"
            f"Quarantined (unknown/invalid): {result['quarantined_count']}",
        )
        self.refresh_all_tabs()  # conflict queue + kappa strip reflect the merge immediately

    # ---- full-text tab ----

    def _build_fulltext_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=16)
        self.notebook.add(frame, text="Full-text")
        self.fulltext_columns = ttk.Frame(frame)
        self.fulltext_columns.pack(fill="both", expand=True)

        self.fulltext_columns.grid_columnconfigure(0, weight=28, minsize=270, uniform="fulltext-cards")
        self.fulltext_columns.grid_columnconfigure(1, weight=46, minsize=510, uniform="fulltext-cards")
        self.fulltext_columns.grid_columnconfigure(2, weight=28, minsize=270, uniform="fulltext-cards")
        self.fulltext_columns.rowconfigure(0, weight=1)
        self.fulltext_queue_card = ttk.Frame(self.fulltext_columns, padding=12, style="Card.TFrame")
        self.fulltext_queue_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.fulltext_assessment_card = ttk.Frame(self.fulltext_columns, padding=12, style="Card.TFrame")
        self.fulltext_assessment_card.grid(row=0, column=1, sticky="nsew", padx=6)
        self.fulltext_support_card = ttk.Frame(self.fulltext_columns, padding=12, style="Card.TFrame")
        self.fulltext_support_card.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.fulltext_queue_panel = ttk.Frame(self.fulltext_queue_card)
        self.fulltext_queue_panel.pack(fill="both", expand=True)
        self.fulltext_assessment_panel = ttk.Frame(self.fulltext_assessment_card)
        self.fulltext_assessment_panel.pack(fill="both", expand=True)
        self.fulltext_support_panel = ttk.Frame(self.fulltext_support_card)
        self.fulltext_support_card.grid_rowconfigure(0, weight=1, minsize=0)
        self.fulltext_support_card.grid_columnconfigure(0, weight=1)
        self.fulltext_support_panel.grid(row=0, column=0, sticky="nsew")


        ttk.Label(self.fulltext_queue_panel, text="FULL-TEXT QUEUE", style="SectionHeading.TLabel").pack(anchor="w", pady=(0, 5))
        self.fulltext_lock_label = ttk.Label(
            self.fulltext_queue_panel, text="", foreground=theme.TOKENS["info"], wraplength=250,
        )
        self.fulltext_lock_label.pack(anchor="w", pady=(0, 5))
        ttk.Label(self.fulltext_queue_panel, text="Included at title/abstract, not yet a report:", wraplength=245).pack(anchor="w")
        promote_frame = ttk.Frame(self.fulltext_queue_panel)
        promote_frame.pack(fill="x", pady=(2, 0))
        self.promote_list = tk.Listbox(promote_frame, height=3, exportselection=False)
        self.promote_list.pack(fill="x")
        self.promote_empty_label = ttk.Label(
            self.fulltext_queue_panel, text="No included records are waiting to become reports.", foreground=theme.TOKENS["muted"], wraplength=245,
        )
        self.promote_empty_label.pack(anchor="w", pady=(2, 4))
        self.promote_report_btn = ttk.Button(
            self.fulltext_queue_panel, text="Create report from selection", command=self._promote_selected,
        )
        self.promote_report_btn.pack(fill="x", pady=(0, 6))

        ttk.Label(self.fulltext_queue_panel, text="REPORTS", style="SectionHeading.TLabel").pack(anchor="w", pady=(2, 3))
        self.report_empty_label = ttk.Label(
            self.fulltext_queue_panel, text="No reports yet. Promote an included record above to create one.", foreground=theme.TOKENS["muted"], wraplength=245,
        )
        self.report_empty_label.pack(anchor="w", padx=2, pady=3)
        self.report_rows_frame = ttk.Frame(self.fulltext_queue_panel)
        self.report_rows_frame.pack(fill="both", expand=True, pady=(0, 2))
        self.report_list = tk.Listbox(
            self.report_rows_frame, height=8, font=(self.font_ui, 9), exportselection=False,
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"], selectbackground=theme.TOKENS["accent_soft"],
            selectforeground=theme.TOKENS["accent"], highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        report_scroll = ttk.Scrollbar(self.report_rows_frame, orient="vertical", command=self.report_list.yview)
        report_xscroll = ttk.Scrollbar(self.fulltext_queue_panel, orient="horizontal", command=self.report_list.xview)
        self.report_list.config(yscrollcommand=report_scroll.set)
        self.report_list.pack(side="left", fill="both", expand=True)
        report_scroll.pack(side="right", fill="y")
        report_xscroll.pack(fill="x", pady=(0, 4))
        self.report_list.bind("<<ListboxSelect>>", lambda e: self._render_fulltext_detail())
        self.report_list.bind("<FocusIn>", lambda _event: self.report_list.configure(**theme.focus_outline_options(True)))
        self.report_list.bind("<FocusOut>", lambda _event: self.report_list.configure(**theme.focus_outline_options(False)))
        self.report_list.bind("<Up>", lambda _event: self._move_fulltext_report(-1))
        self.report_list.bind("<Down>", lambda _event: self._move_fulltext_report(1))
        self.fulltext_queue_note_label = ttk.Label(
            self.fulltext_queue_panel, text="Report-level queue. Each distinct report advances once; source occurrences remain linked for provenance.",
            foreground=theme.TOKENS["muted"], wraplength=245,
        )
        self.fulltext_queue_note_label.pack(anchor="w", pady=(3, 0))

        ttk.Label(self.fulltext_assessment_panel, text="ASSESS FULL TEXT", style="SectionHeading.TLabel").pack(anchor="w", pady=(0, 4))
        self.fulltext_selected_identity = ttk.Label(self.fulltext_assessment_panel, text="No report selected", foreground=theme.TOKENS["muted"], wraplength=490)
        self.fulltext_selected_identity.pack(anchor="w", pady=(0, 4))
        ttk.Label(self.fulltext_assessment_panel, text="SELECTED RECORD", style="SectionHeading.TLabel").pack(anchor="w", pady=(0, 3))
        self.fulltext_detail_text = tk.Text(
            self.fulltext_assessment_panel, height=12, wrap="word", font=(self.font_ui, 9),
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.fulltext_detail_text.pack(fill="both", expand=True, pady=(2, 4))
        self.fulltext_detail_text.tag_configure("fulltext_heading", font=(self.font_ui, 9, "bold"))
        self.fulltext_detail_text.tag_configure("fulltext-title", font=(self.font_title, 15), foreground=theme.TOKENS["ink"])
        self.fulltext_detail_text.tag_configure("fulltext-meta", font=(self.font_ui, 9), foreground=theme.TOKENS["muted"])
        self.fulltext_detail_text.tag_configure("fulltext-abstract-heading", font=(self.font_ui, 9, "bold"), foreground=theme.TOKENS["muted"])
        self.fulltext_detail_text.tag_configure("fulltext-abstract", font=(self.font_reading, 10), foreground=theme.TOKENS["ink"])
        self.fulltext_detail_text.config(state="disabled")
        self.fulltext_empty_detail_label = ttk.Label(
            self.fulltext_assessment_panel, text="No report selected. Create a report from an included record to begin full-text review.",
            foreground=theme.TOKENS["muted"], wraplength=490,
        )
        self.fulltext_empty_detail_label.pack_forget()
        self.fulltext_assessment_buttons = ttk.Frame(self.fulltext_assessment_panel)
        self.fulltext_assessment_buttons.pack(fill="x", pady=(2, 4))
        self.fulltext_not_retrieved_btn = ttk.Button(
            self.fulltext_assessment_buttons, text="Mark not retrieved", command=self._report_not_retrieved,
        )
        self.fulltext_not_retrieved_btn.pack(fill="x", pady=(0, 3))
        self.fulltext_decision_bar = ttk.Frame(self.fulltext_assessment_buttons)
        self.fulltext_decision_bar.pack(fill="x")
        self.fulltext_decision_bar.grid_columnconfigure((0, 1, 2), weight=1, uniform="fulltext-decision")
        self.fulltext_assess_included_btn = _KeycapButton(
            self.fulltext_decision_bar, key="I", word="Include", decision="include",
            command=lambda: self._report_assess("included"), font_ui=self.font_ui, font_mono=self.font_mono,
            font_size=9, vertical_padding=5, keycap_padx=4,
        )
        self.fulltext_assess_included_btn.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.fulltext_assess_maybe_btn = _KeycapButton(
            self.fulltext_decision_bar, key="M", word="Maybe", decision="maybe",
            command=lambda: self._report_assess("maybe"), font_ui=self.font_ui, font_mono=self.font_mono,
            font_size=9, vertical_padding=5, keycap_padx=4,
        )
        self.fulltext_assess_maybe_btn.grid(row=0, column=1, sticky="ew", padx=3)
        self.fulltext_assess_excluded_btn = _KeycapButton(
            self.fulltext_decision_bar, key="E", word="Exclude...", decision="exclude",
            command=lambda: self._report_assess("excluded"), font_ui=self.font_ui, font_mono=self.font_mono,
            font_size=9, vertical_padding=5, keycap_padx=4,
        )
        self.fulltext_assess_excluded_btn.grid(row=0, column=2, sticky="ew", padx=(3, 0))
        self.fulltext_mechanics_note = ttk.Label(
            self.fulltext_assessment_panel, text="Maybe remains pending for re-review; only Include/Exclude are terminal report outcomes.",
            foreground=theme.TOKENS["muted"], wraplength=490,
        )
        self.fulltext_mechanics_note.pack(anchor="w", pady=(0, 3))
        self.fulltext_navigation = ttk.Frame(self.fulltext_assessment_panel)
        self.fulltext_navigation.pack(fill="x")
        self.fulltext_previous_btn = ttk.Button(self.fulltext_navigation, text="Previous report", command=lambda: self._move_fulltext_report(-1))
        self.fulltext_previous_btn.pack(side="left", fill="x", expand=True, padx=(0, 3))
        self.fulltext_next_btn = ttk.Button(self.fulltext_navigation, text="Next report", style="FulltextNext.TButton", command=lambda: self._move_fulltext_report(1))
        self.fulltext_next_btn.pack(side="left", fill="x", expand=True, padx=(3, 0))

        ttk.Label(self.fulltext_support_panel, text="EXCLUSION REASONS", style="SectionHeading.TLabel").pack(anchor="w", pady=(0, 2))
        ttk.Label(self.fulltext_support_panel, text="PRISMA report stage", foreground=theme.TOKENS["muted"], wraplength=250).pack(anchor="w", pady=(0, 2))
        self.fulltext_reason_note = tk.Label(
            self.fulltext_support_panel,
            text="Required for a terminal full-text exclusion. Exactly one primary reason is attached to the report and feeds PRISMA ‘reports excluded.’",
            bg=theme.TOKENS["info_soft"], fg=theme.TOKENS["info"], font=(self.font_ui, 9), justify="left", anchor="w", wraplength=245, padx=8, pady=7, height=3,
        )
        # Paddings below are tight because Atkinson Hyperlegible runs ~2px
        # taller per line than Segoe UI; the attached-PDF row must still fit.
        self.fulltext_reason_note.pack(fill="x", pady=(0, 4))
        self.fulltext_reason_var = tk.StringVar(master=self.root, value="")
        self.fulltext_reason_radios = []
        ttk.Style(self.root).configure("FulltextReason.TRadiobutton", padding=(0, 0), font=(self.font_ui, 9))
        for reason in screening.EXCLUSION_REASONS:
            radio = ttk.Radiobutton(self.fulltext_support_panel, text=reason, variable=self.fulltext_reason_var, value=reason, command=self._update_fulltext_reason_state, style="FulltextReason.TRadiobutton")
            radio.pack(anchor="w", fill="x", pady=0)
            self.fulltext_reason_radios.append(radio)
        self.fulltext_reason_count_label = ttk.Label(self.fulltext_support_panel, text="Counts on save · reports excluded +0", foreground=theme.TOKENS["muted"], wraplength=245)
        self.fulltext_reason_count_label.pack(anchor="w", pady=(2, 0))
        self.fulltext_not_retrieved_note = ttk.Label(self.fulltext_support_panel, text="Not retrieved is separate; it never receives a full-text exclusion reason.", foreground=theme.TOKENS["muted"], wraplength=245)
        self.fulltext_not_retrieved_note.pack(anchor="w", pady=(0, 2))
        self.fulltext_keyboard_guide = ttk.Label(self.fulltext_support_panel, text="Keyboard: Tab moves through queue, assessment, reasons and actions.", foreground=theme.TOKENS["muted"], wraplength=245)
        self.fulltext_keyboard_guide.pack(anchor="w", pady=(0, 2))
        ttk.Separator(self.fulltext_support_panel).pack(fill="x", pady=3)
        ttk.Label(self.fulltext_support_panel, text="ATTACHED PDF", style="SectionHeading.TLabel").pack(anchor="w", pady=(0, 2))
        self.fulltext_attachment_list_frame = ttk.Frame(self.fulltext_support_panel)
        self.fulltext_attachment_list_frame.pack(fill="both", expand=True, pady=(0, 2))
        self.attachment_listbox = tk.Listbox(
            self.fulltext_attachment_list_frame, height=1, font=(self.font_ui, 9), exportselection=False,
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"], selectbackground=theme.TOKENS["accent_soft"],
            selectforeground=theme.TOKENS["accent"], highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.fulltext_attachment_scroll = ttk.Scrollbar(self.fulltext_attachment_list_frame, orient="vertical", command=self.attachment_listbox.yview)
        self.attachment_listbox.config(yscrollcommand=self.fulltext_attachment_scroll.set)
        self.attachment_listbox.pack(side="left", fill="both", expand=True)
        self.fulltext_attachment_scroll.pack(side="right", fill="y")
        self.fulltext_attachment_actions = ttk.Frame(self.fulltext_support_card)
        self.fulltext_attachment_actions.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.attach_pdf_btn = ttk.Button(self.fulltext_attachment_actions, text="Attach PDF...", command=self._attach_pdf)
        self.attach_pdf_btn.pack(fill="x", pady=(0, 3))
        self.open_attachment_btn = ttk.Button(self.fulltext_attachment_actions, text="Open selected", command=self._open_selected_attachment)
        self.open_attachment_btn.pack(fill="x", pady=(0, 3))
        self.remove_attachment_btn = ttk.Button(self.fulltext_attachment_actions, text="Remove selected...", command=self._remove_selected_attachment)
        self.remove_attachment_btn.pack(fill="x")

        self._promote_occurrence_ids: list[str] = []
        self._report_ids: list[str] = []
        self._report_rows: list[dict] = []
        self._attachment_ids: list[str] = []

    def _move_fulltext_report(self, delta: int) -> str:
        if roles.is_blind(self.conn) or not self._report_ids:
            return "break"
        selected = self.report_list.curselection()
        current = selected[0] if selected else 0
        target = max(0, min(len(self._report_ids) - 1, current + delta))
        self.report_list.selection_clear(0, "end")
        self.report_list.selection_set(target)
        self.report_list.activate(target)
        self.report_list.see(target)
        self._render_fulltext_detail()
        self._set_status(f"Focused report {target + 1} of {len(self._report_ids)}.")
        return "break"

    def _update_fulltext_reason_state(self) -> None:
        selected_indices = self.report_list.curselection()
        selected = bool(selected_indices and selected_indices[0] < len(self._report_rows))
        outcome = self._report_rows[selected_indices[0]].get("full_text_outcome") if selected else None
        reason_needed = selected and (outcome is None or outcome == "excluded")
        reason = self.fulltext_reason_var.get().strip()
        if roles.is_blind(self.conn):
            self.fulltext_selected_identity.config(text="Blind mode · report details are hidden")
            self.fulltext_previous_btn.config(state="disabled")
            self.fulltext_next_btn.config(state="disabled")
            self.fulltext_reason_var.set("")
            self.fulltext_reason_note.configure(text="Full-text details and decision controls are locked while blind mode is on.")
            self.fulltext_reason_count_label.configure(text="Counts unavailable while blind")
            for radio in self.fulltext_reason_radios:
                radio.configure(state="disabled")
            return
        for radio in self.fulltext_reason_radios:
            radio.configure(state="normal" if reason_needed else "disabled")
        if not selected or not reason_needed:
            self.fulltext_reason_var.set("")
        if reason_needed:
            self.fulltext_reason_note.configure(text="Choose exactly one primary reason before saving a terminal Exclude." if not reason else f"Selected exclusion reason: {reason}.")
            self.fulltext_reason_count_label.configure(text="Counts on save · reports excluded +1")
        elif not selected:
            self.fulltext_reason_note.configure(text="Select a report to review its terminal-exclusion reason state.")
            self.fulltext_reason_count_label.configure(text="Counts on save · reports excluded +0")
        else:
            self.fulltext_reason_note.configure(text="Required for a terminal full-text exclusion. Exactly one primary reason is attached to the report and feeds PRISMA ‘reports excluded.’")
            self.fulltext_reason_count_label.configure(text="Counts on save · reports excluded +0")

    def _refresh_fulltext_tab(self) -> None:
        """Item 9: mirrors `_refresh_conflicts_tab`'s blind branch --
        `reports.unlinked_included_occurrences` takes no reviewer
        parameter and returns every reviewer's current includes
        unfiltered, so while blind the promote/report queues are not
        populated and all four actions are disabled, with the same
        lock-label discipline as Conflicts. This is UI-layer
        enforcement, same pattern as Conflicts; reports.py is
        unchanged."""
        if roles.is_blind(self.conn):
            self._promote_occurrence_ids = []
            self.promote_list.delete(0, "end")  # must delete BEFORE disabling: Tk no-ops delete() while disabled
            self.promote_list.config(state="disabled")
            self._report_rows = []
            self._report_ids = []
            self._attachment_ids = []
            self.fulltext_selected_identity.config(text="Blind mode · report details are hidden")
            self.fulltext_previous_btn.config(state="disabled")
            self.fulltext_next_btn.config(state="disabled")
            self.fulltext_reason_var.set("")
            self.fulltext_reason_note.configure(text="Full-text details and decision controls are locked while blind mode is on.")
            self.fulltext_reason_count_label.configure(text="Counts unavailable while blind")
            for radio in self.fulltext_reason_radios:
                radio.configure(state="disabled")
            self.report_list.delete(0, "end")
            self.report_list.config(state="disabled")
            self.fulltext_detail_text.config(state="normal")
            self.fulltext_detail_text.delete("1.0", "end")
            self.fulltext_detail_text.config(state="disabled")
            self.promote_empty_label.pack_forget()
            self.report_empty_label.pack_forget()
            self.fulltext_empty_detail_label.pack_forget()
            self.fulltext_lock_label.config(
                text="Full-text is locked while blind mode is ON."
                " The project owner must turn blind mode off to open this tab.",
            )
            self.promote_report_btn.config(state="disabled")
            self.fulltext_not_retrieved_btn.config(state="disabled")
            self.fulltext_assess_included_btn.set_enabled(False)
            self.fulltext_assess_maybe_btn.set_enabled(False)
            self.fulltext_assess_excluded_btn.set_enabled(False)
            self.attachment_listbox.delete(0, "end")
            self.attachment_listbox.config(state="disabled")
            self.attach_pdf_btn.config(state="disabled")
            self.open_attachment_btn.config(state="disabled")
            self.remove_attachment_btn.config(state="disabled")
            self._render_fulltext_detail()
            return

        self.promote_list.config(state="normal")
        self.report_list.config(state="normal")
        self.fulltext_lock_label.config(text="")
        self.promote_report_btn.config(state="normal")
        self.fulltext_not_retrieved_btn.config(state="normal")
        self.fulltext_assess_included_btn.set_enabled(True)
        self.fulltext_assess_maybe_btn.set_enabled(True)
        self.fulltext_assess_excluded_btn.set_enabled(True)
        self.attachment_listbox.config(state="normal")
        self.attach_pdf_btn.config(state="normal")
        self.open_attachment_btn.config(state="normal")
        self.remove_attachment_btn.config(state="normal")

        candidates = reports.unlinked_included_occurrences(self.conn)
        self._promote_occurrence_ids = [c["occurrence_id"] for c in candidates]
        self.promote_list.delete(0, "end")
        for c in candidates:
            fields = self._load_fields(c["occurrence_id"])
            self.promote_list.insert("end", fields.get("title") or c["occurrence_id"])
        if candidates:
            self.promote_empty_label.pack_forget()
        else:
            self.promote_empty_label.pack(anchor="w", pady=(0, 4), before=self.promote_report_btn)

        self._report_rows = reports.list_reports(self.conn)
        self._report_ids = [r["report_id"] for r in self._report_rows]
        selected_id = self._selected_report_id()
        self.report_list.delete(0, "end")
        for r in self._report_rows:
            status = r["retrieval_status"] or "pending"
            outcome = f" -> {r['full_text_outcome']}" if r["full_text_outcome"] else ""
            fields = self._load_fields(r["canonical_occurrence"]) if r["canonical_occurrence"] else {}
            title = fields.get("title") or r["report_id"]
            # Keep retrieval/outcome and attachment affordances inside
            # the narrow queue width; full IDs remain in the detail pane.
            has_pdf = bool(attachments.list_attachments(self.conn, r["report_id"]))
            pdf_badge = " | ▣ PDF attached" if has_pdf else ""
            row = (
                f"[{status}{outcome}] R:{r['report_id'][:8]} "
                f"S:{(r['canonical_occurrence'] or '')[:8]}{pdf_badge}"
            )
            self.report_list.insert("end", row)
        if self._report_rows:
            self.report_empty_label.pack_forget()
        else:
            self.report_empty_label.pack(anchor="w", pady=(0, 4), before=self.report_rows_frame)
        if not self._report_rows:
            self.report_list.selection_clear(0, "end")
            self.fulltext_detail_text.config(state="normal")
            self.fulltext_detail_text.delete("1.0", "end")
            self.fulltext_detail_text.insert("end", "")
            self.fulltext_detail_text.config(state="disabled")
            self.fulltext_selected_identity.config(text="No report selected")
            self.fulltext_previous_btn.config(state="disabled")
            self.fulltext_next_btn.config(state="disabled")
            self.fulltext_assess_included_btn.set_enabled(False)
            self.fulltext_assess_maybe_btn.set_enabled(False)
            self.fulltext_assess_excluded_btn.set_enabled(False)
            self.fulltext_not_retrieved_btn.config(state="disabled")
            self.fulltext_reason_var.set("")
            self.fulltext_reason_note.configure(text="Select a report to review its terminal-exclusion reason state.")
            self.fulltext_reason_count_label.configure(text="Counts on save · reports excluded +0")
            for radio in self.fulltext_reason_radios:
                radio.configure(state="disabled")
            self.fulltext_empty_detail_label.pack(anchor="w", pady=(0, 6), before=self.fulltext_detail_text)
            self.fulltext_not_retrieved_btn.config(state="disabled")
            self.fulltext_assess_included_btn.set_enabled(False)
            self.fulltext_assess_maybe_btn.set_enabled(False)
            self.fulltext_assess_excluded_btn.set_enabled(False)
            self.attachment_listbox.config(state="disabled")
            self.attach_pdf_btn.config(state="disabled")
            self.open_attachment_btn.config(state="disabled")
            self.remove_attachment_btn.config(state="disabled")
            return
        self.attachment_listbox.config(state="normal")
        self.attach_pdf_btn.config(state="normal")
        self.open_attachment_btn.config(state="normal")
        self.remove_attachment_btn.config(state="normal")
        self.fulltext_empty_detail_label.pack_forget()
        if selected_id in self._report_ids:
            self.report_list.selection_set(self._report_ids.index(selected_id))
        elif self._report_ids:
            self.report_list.selection_set(0)
        self._render_fulltext_detail()

    def _render_fulltext_detail(self) -> None:
        """Item 4: show report identity separately from its source
        occurrence and render that source record's metadata and
        stored abstract/excerpt text."""
        selected = self.report_list.curselection()
        selected_id = self._selected_report_id()
        previous_id = getattr(self, "_fulltext_rendered_report_id", None)
        changed_report = selected_id != previous_id
        self._fulltext_rendered_report_id = selected_id
        if changed_report:
            self.fulltext_reason_var.set("")
        self._update_fulltext_reason_state()
        self.fulltext_detail_text.config(state="normal")
        self.fulltext_detail_text.delete("1.0", "end")
        if selected and selected[0] < len(self._report_rows):
            row = self._report_rows[selected[0]]
            self.fulltext_selected_identity.config(text=f"{row['report_id']} · {row['retrieval_status'] or 'pending'}")
            self.fulltext_previous_btn.config(state="normal" if selected[0] > 0 else "disabled")
            self.fulltext_next_btn.config(state="normal" if selected[0] < len(self._report_ids) - 1 else "disabled")
            self._update_fulltext_reason_state()
            occ_id = row["canonical_occurrence"]
            fields = self._load_fields(occ_id) if occ_id else {}
            title = fields.get("title") or "(no title)"
            authors = fields.get("authors") or []
            if isinstance(authors, (list, tuple)):
                authors_text = "; ".join(str(author) for author in authors)
            else:
                authors_text = str(authors)
            metadata = [
                f"Authors: {authors_text or '(none)'}",
                f"Year: {fields.get('year') or '(unknown)'}",
                f"Journal: {fields.get('journal') or '(not provided)'}",
                f"DOI: {fields.get('doi') or '(not provided)'}",
            ]
            abstract = fields.get("abstract") or "No abstract or excerpt is stored with this source record."
            self.fulltext_detail_text.insert("end", "REPORT DETAILS\n", "fulltext_heading")
            self.fulltext_detail_text.insert("end", f"{title}\n", "fulltext-title")
            self.fulltext_detail_text.insert("end", " · ".join(
                part for part in [authors_text or "(no author)", fields.get("journal"), fields.get("year")] if part
            ) + "\n", "fulltext-meta")
            self.fulltext_detail_text.insert("end", f"Report ID: {row['report_id']}\n", "fulltext-meta")
            self.fulltext_detail_text.insert("end", f"Source occurrence ID: {occ_id or '(not assigned)'}\n", "fulltext-meta")
            self.fulltext_detail_text.insert("end", f"DOI: {fields.get('doi') or '(not provided)'}\n\n", "fulltext-meta")
            self.fulltext_detail_text.insert("end", "SYNTHETIC EXCERPT · TITLE/ABSTRACT IMPORT\n", "fulltext-abstract-heading")
            self.fulltext_detail_text.insert("end", abstract, "fulltext-abstract")
        self.fulltext_detail_text.config(state="disabled")

        # Attachment list mirrors whichever report is now selected (or
        # is empty with nothing selected / while blind -- the blind
        # branch above already clears and disables this widget before
        # calling here).
        if self.attachment_listbox.cget("state") != "disabled":
            self.attachment_listbox.delete(0, "end")
            self._attachment_ids = []
            if selected and selected[0] < len(self._report_rows):
                row = self._report_rows[selected[0]]
                for att in attachments.list_attachments(self.conn, row["report_id"]):
                    self._attachment_ids.append(att["attachment_id"])
                    size_kb = att["byte_size"] / 1024
                    self.attachment_listbox.insert(
                        "end",
                        f"PDF · {att['filename']}  ({size_kb:.1f} KB, by {att['uploaded_by']})",
                    )

    def _promote_selected(self) -> None:
        sel = self.promote_list.curselection()
        if not sel:
            return
        occ_id = self._promote_occurrence_ids[sel[0]]
        reports.promote_occurrence_to_report(self.conn, self.reviewer_id, occ_id)
        self.refresh_all_tabs()

    def _selected_report_id(self) -> str | None:
        sel = self.report_list.curselection()
        if not sel:
            return None
        return self._report_ids[sel[0]]

    def _report_not_retrieved(self) -> None:
        rid = self._selected_report_id()
        if rid is None:
            return
        reports.mark_not_retrieved(self.conn, self.reviewer_id, rid)
        self.refresh_all_tabs()

    def _report_assess(self, outcome: str) -> None:
        """Item 6: terminal Exclude requires exactly one primary reason
        chosen from a closed taxonomy (reusing the title/abstract-stage
        picker, `_prompt_exclusion_reason`) instead of free text --
        cancelling the picker records no outcome, so Exclude without a
        reason remains impossible, same as at the screening stage."""
        rid = self._selected_report_id()
        if rid is None:
            return
        reason = self.fulltext_reason_var.get().strip()
        self.fulltext_reason_var.set("")
        if outcome == "excluded" and not reason:
            reason = self._prompt_exclusion_reason()
            if not reason:
                self.fulltext_reason_count_label.configure(text="Counts on save · reports excluded +0")
                self.fulltext_reason_note.configure(text="Choose one primary reason before saving a terminal Exclude.")
                return
        if outcome != "excluded":
            reason = None
        reports.record_full_text_assessment(self.conn, self.reviewer_id, rid, outcome, exclusion_reason=reason)
        self._set_status(f"Report assessed: {outcome}{f' · {reason}' if reason else ''}.")
        self.refresh_all_tabs()
        if reason:
            self.fulltext_reason_var.set(reason)
            self.fulltext_reason_note.configure(text=f"Selected exclusion reason: {reason}.")

    def _selected_attachment_id(self) -> str | None:
        sel = self.attachment_listbox.curselection()
        if not sel or sel[0] >= len(self._attachment_ids):
            return None
        return self._attachment_ids[sel[0]]

    def _attach_pdf(self) -> None:
        rid = self._selected_report_id()
        if rid is None:
            return
        path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        try:
            attachments.attach_pdf(self.conn, self.reviewer_id, rid, path)
        except ValueError as exc:
            messagebox.showerror("Attach failed", str(exc))
            return
        self.refresh_all_tabs()

    def _open_selected_attachment(self) -> None:
        """Opening the PDF is a separate action from any decision button
        (Tk feasibility note), and never mutates the attachment record --
        it only ever reads+verifies bytes and hands them to the OS's own
        PDF viewer via a throwaway temp copy."""
        rid = self._selected_report_id()
        attachment_id = self._selected_attachment_id()
        if rid is None or attachment_id is None:
            return
        row = next(
            (a for a in attachments.list_attachments(self.conn, rid) if a["attachment_id"] == attachment_id),
            None,
        )
        filename = row["filename"] if row else f"{attachment_id}.pdf"
        try:
            data = attachments.attachment_bytes(self.conn, attachment_id)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Open failed", f"Could not read {filename}: {exc}")
            return
        tmp_dir = tempfile.mkdtemp(prefix="screening-workbench-attachment-")
        tmp_path = os.path.join(tmp_dir, filename)
        with open(tmp_path, "wb") as fh:
            fh.write(data)
        try:
            os.startfile(tmp_path)  # Windows-only, per the owner-approved v1 stack
        except OSError as exc:
            messagebox.showerror("Open failed", f"Could not open {filename}: {exc}")

    def _remove_selected_attachment(self) -> None:
        rid = self._selected_report_id()
        attachment_id = self._selected_attachment_id()
        if rid is None or attachment_id is None:
            return
        row = next(
            (a for a in attachments.list_attachments(self.conn, rid) if a["attachment_id"] == attachment_id),
            None,
        )
        filename = row["filename"] if row else attachment_id
        if not messagebox.askyesno(
            "Remove attachment",
            f"Remove \u201c{filename}\u201d from this report?\n\n"
            "The underlying file is content-addressed and stays on disk if any"
            " other report shares its exact bytes (no garbage collection in v1).",
        ):
            return
        attachments.detach_pdf(self.conn, self.reviewer_id, attachment_id)
        self.refresh_all_tabs()

    # ---- studies tab ----

    def _build_studies_tab(self) -> None:
        frame = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(frame, text="Studies")
        frame.grid_columnconfigure(0, weight=22, minsize=250, uniform="studies-cards")
        frame.grid_columnconfigure(1, weight=52, minsize=500, uniform="studies-cards")
        frame.grid_columnconfigure(2, weight=26, minsize=285, uniform="studies-cards")
        frame.grid_rowconfigure(1, weight=1)
        self.studies_lock_label = ttk.Label(
            frame, text="", font=(self.font_ui, 10, "bold"), foreground=theme.TOKENS["info"],
            wraplength=1180, justify="left",
        )
        self.studies_lock_label.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.studies_columns = ttk.Frame(frame)
        self.studies_columns.grid(row=1, column=0, columnspan=3, sticky="nsew")
        self.studies_columns.grid_columnconfigure(0, weight=22, minsize=250, uniform="studies-cards")
        self.studies_columns.grid_columnconfigure(1, weight=52, minsize=500, uniform="studies-cards")
        self.studies_columns.grid_columnconfigure(2, weight=26, minsize=285, uniform="studies-cards")
        self.studies_columns.grid_rowconfigure(0, weight=1)
        self.studies_groups_card = ttk.Frame(self.studies_columns, padding=12, style="Card.TFrame")
        self.studies_groups_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.studies_detail_card = ttk.Frame(self.studies_columns, padding=12, style="Card.TFrame")
        self.studies_detail_card.grid(row=0, column=1, sticky="nsew", padx=6)
        self.studies_canonical_card = ttk.Frame(self.studies_columns, padding=12, style="Card.TFrame")
        self.studies_canonical_card.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        ttk.Label(self.studies_groups_card, text="STUDY GROUPS", style="SectionHeading.TLabel").pack(anchor="w", pady=(0, 5))
        self.new_study_btn = ttk.Button(self.studies_groups_card, text="New study", command=self._new_study)
        self.new_study_btn.pack(anchor="w", pady=(0, 8))

        # Item 2: a Treeview parent/child hierarchy -- study rows as
        # parents, their linked reports nested as children -- rather
        # than a flat list, so grouping is structural, not inferred
        # from adjacent rows. Item 3: study_id/report_id prefixes keep
        # the iid namespace collision-free across both levels.
        self.studies_tree_frame = tk.Frame(
            self.studies_groups_card, bg=theme.TOKENS["surface"], bd=0,
            **theme.focus_outline_options(False),
        )
        self.studies_tree_frame.pack(fill="both", expand=True)
        self.studies_tree_focus_frame = tk.Frame(
            self.studies_tree_frame, bg=theme.TOKENS["surface"], bd=0, padx=0, pady=0,
        )
        self.studies_tree_focus_frame.pack(fill="both", expand=True)
        self.study_tree = ttk.Treeview(self.studies_tree_focus_frame, show="tree", height=10, takefocus=True)
        tree_scroll = ttk.Scrollbar(self.studies_tree_focus_frame, orient="vertical", command=self.study_tree.yview)
        self.study_tree.config(yscrollcommand=tree_scroll.set)
        self.study_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.study_tree_empty_label = ttk.Label(
            self.studies_tree_frame, text="No studies yet. Select New study to add one; studies will appear here.",
            foreground=theme.TOKENS["muted"], justify="center", anchor="center", wraplength=210,
        )
        self.study_tree_empty_label.place(relx=0.5, rely=0.5, anchor="center")
        self.study_tree.bind("<<TreeviewSelect>>", lambda e: self._render_study_detail())
        self.study_tree.tag_configure("studies-keyboard-focus", background=theme.TOKENS["accent_soft"], foreground=theme.TOKENS["ink"])
        self.new_study_btn.bind("<Tab>", self._tab_from_new_study_to_tree, add="+")
        self.studies_focus_label = ttk.Label(
            self.studies_groups_card,
            text="Keyboard: Tab through groups, decisions, report linking, and canonical choices.",
            foreground=theme.TOKENS["muted"], wraplength=220,
        )
        self.studies_focus_label.pack(anchor="w", pady=(6, 0))
        self.study_tree.bind("<FocusIn>", self._set_studies_tree_focus, add="+")
        self.study_tree.bind("<FocusOut>", self._clear_studies_tree_focus, add="+")
        self.study_tree.bind("<Tab>", self._tab_from_studies_tree_to_link, add="+")

        ttk.Label(self.studies_detail_card, text="REPORTS & STUDY DECISION", style="SectionHeading.TLabel").pack(anchor="w", pady=(0, 5))
        self.study_detail_text = tk.Text(
            self.studies_detail_card, height=10, wrap="word", font=(self.font_ui, 9),
            background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
            selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
            highlightthickness=1, highlightbackground=theme.TOKENS["line"],
        )
        self.study_detail_text.pack(fill="both", expand=True, pady=(2, 8))
        self.study_detail_text.tag_configure("study_heading", font=(self.font_ui, 9, "bold"))

        self.study_detail_text.config(state="disabled")

        # Item 11 (build gap found during the round-3 keyboard check,
        # not a cosmetic tweak): item 4's canonical occurrence was only
        # ever *displayed* as read-only text in round 1 -- there was no
        # actual control to operate. The Tk feasibility notes call for
        # Radiobuttons here specifically so this choice is keyboard-
        # operable, not just visible. Populated per-selection in
        # _render_study_detail; empty for a study row or a single-
        # occurrence report (nothing to choose among).
        ttk.Label(self.studies_canonical_card, text="CANONICAL OCCURRENCE", style="SectionHeading.TLabel").pack(anchor="w", pady=(0, 5))
        self.study_canonical_var = tk.StringVar(master=self.root)
        self.study_canonical_frame = ttk.Frame(self.studies_canonical_card)
        self.study_canonical_frame.pack(anchor="nw", fill="both", expand=True)
        ttk.Label(
            self.studies_canonical_card,
            text="One progression per distinct report. The study link alone does not imply inclusion.",
            foreground=theme.TOKENS["muted"], wraplength=245, justify="left",
        ).pack(anchor="w", side="bottom", pady=(8, 0))

        self.studies_decision_frame = ttk.Frame(self.studies_detail_card)
        self.studies_decision_frame.pack(anchor="w", fill="x", pady=(0, 8))
        self.study_decide_included_btn = ttk.Button(
            self.studies_decision_frame, text="Decide: Included", command=lambda: self._study_decide("included"),
        )
        self.study_decide_included_btn.pack(side="left", padx=4)
        self.study_decide_excluded_btn = ttk.Button(
            self.studies_decision_frame, text="Decide: Excluded", command=lambda: self._study_decide("excluded"),
        )
        self.study_decide_excluded_btn.pack(side="left", padx=4)
        self.study_decide_unresolved_btn = ttk.Button(
            self.studies_decision_frame, text="Decide: Unresolved", command=lambda: self._study_decide("unresolved"),
        )
        self.study_decide_unresolved_btn.pack(side="left", padx=4)

        self.studies_link_frame = ttk.Frame(self.studies_detail_card)
        self.studies_link_frame.pack(anchor="w", fill="x")
        ttk.Label(self.studies_link_frame, text="Link to report #:").pack(side="left")
        self.study_link_report_entry = ttk.Entry(self.studies_link_frame, width=6)
        self.study_link_report_entry.pack(side="left", padx=6)
        self.study_link_btn = ttk.Button(self.studies_link_frame, text="Link", command=self._link_selected_study)
        self.study_link_btn.pack(side="left")

        self._study_ids: list[str] = []
        self._report_ids_for_link: list[str] = []
        self._study_row_by_id: dict[str, dict] = {}
        self._report_row_by_id: dict[str, dict] = {}

    def _refresh_studies_tab(self) -> None:
        """Item 10: mirrors `_refresh_conflicts_tab`/`_refresh_fulltext_tab`'s
        blind branch -- the Studies tab had NO blind handling at all
        before this round (confirmed by code read during the Studies
        baseline, not assumed). Decision, rationale, actor, and the
        conflict flag are all decision-derived data; the report-link
        control also read `reports.list_reports` with no gate,
        bypassing the Full-text tab's own blind lock. While blind, the
        tree and detail pane are emptied (nothing to leak) and every
        action is disabled, with the same lock-label discipline as
        Conflicts/Full-text."""
        if roles.is_blind(self.conn):
            self._study_ids = []
            self._study_row_by_id = {}
            self._report_ids_for_link = []
            self._report_row_by_id = {}
            self.study_tree.delete(*self.study_tree.get_children())
            self.study_tree_empty_label.place_forget()
            self.study_detail_text.delete("1.0", "end")
            self.study_detail_text.config(state="disabled")
            for child in self.study_canonical_frame.winfo_children():
                child.destroy()
            self.studies_lock_label.config(
                text="Studies is locked while blind mode is ON."
                " The project owner must turn blind mode off to open this tab.",
            )
            self.studies_focus_label.config(
                text="Keyboard actions are unavailable while blind mode is ON.", foreground=theme.TOKENS["info"],
            )
            self.new_study_btn.config(state="disabled")
            self.study_decide_included_btn.config(state="disabled")
            self.study_decide_excluded_btn.config(state="disabled")
            self.study_decide_unresolved_btn.config(state="disabled")
            self.study_link_btn.config(state="disabled")
            return

        self.studies_lock_label.config(text="")
        self.studies_focus_label.config(
            text="Keyboard: Tab through groups, decisions, report linking, and canonical choices.",
            foreground=theme.TOKENS["muted"],
        )
        self.new_study_btn.config(state="normal")
        self.study_decide_included_btn.config(state="normal")
        self.study_decide_excluded_btn.config(state="normal")
        self.study_decide_unresolved_btn.config(state="normal")
        self.study_link_btn.config(state="normal")

        selected = self.study_tree.selection()
        selected_iid = selected[0] if selected else None

        study_rows = studies.list_studies(self.conn)
        self._study_ids = [s["study_id"] for s in study_rows]
        self._study_row_by_id = {s["study_id"]: s for s in study_rows}

        report_rows = reports.list_reports(self.conn)
        self._report_ids_for_link = [r["report_id"] for r in report_rows]
        self._report_row_by_id = {r["report_id"]: r for r in report_rows}

        self.study_tree.delete(*self.study_tree.get_children())
        for s in study_rows:
            study_id = s["study_id"]
            report_ids = studies.reports_for_study(self.conn, study_id)
            flag = "  [CONFLICT]" if s["has_conflict"] else ""
            decision_label = s["decision"] or "no decision"
            # Item 1: the study's own row states its report count
            # directly, not something a reviewer has to count by
            # expanding it.
            count_label = f"{len(report_ids)} report" + ("" if len(report_ids) == 1 else "s")
            self.study_tree.insert(
                "", "end", iid=study_id,
                text=f"{decision_label}{flag}  --  {study_id}  ({count_label})",
            )
            for report_id in report_ids:
                r = self._report_row_by_id.get(report_id)
                fields = self._load_fields(r["canonical_occurrence"]) if r and r["canonical_occurrence"] else {}
                title = fields.get("title") or report_id
                status = (r["retrieval_status"] if r else None) or "pending"
                outcome = f" -> {r['full_text_outcome']}" if r and r["full_text_outcome"] else ""
                self.study_tree.insert(
                    study_id, "end", iid=report_id,
                    text=f"Report: {report_id}  [{status}{outcome}]  --  {title}",
                )

        if study_rows:
            self.study_tree_empty_label.place_forget()
        else:
            self.study_tree_empty_label.place(relx=0.5, rely=0.5, anchor="center")
        if selected_iid and self.study_tree.exists(selected_iid):
            self.study_tree.selection_set(selected_iid)
            self.study_tree.see(selected_iid)
        self._render_study_detail()

    def _set_studies_tree_focus(self, _event=None) -> None:
        """Show an outline distinct from the selected study/report row."""
        self.studies_tree_frame.configure(**theme.focus_outline_options(True))
        selected = self.study_tree.selection()
        for iid in self.study_tree.get_children(""):
            self.study_tree.item(iid, tags=())
            for child_iid in self.study_tree.get_children(iid):
                self.study_tree.item(child_iid, tags=())
        if selected and self.study_tree.exists(selected[0]):
            self.study_tree.item(selected[0], tags=("studies-keyboard-focus",))
        if not roles.is_blind(self.conn):
            self.studies_focus_label.config(
                text="Keyboard focus: Study/report groups.", foreground=theme.TOKENS["ink"],
            )

    def _tab_from_new_study_to_tree(self, _event=None) -> str:
        """Make the study/report hierarchy the next Tab stop after its action."""
        if not roles.is_blind(self.conn):
            self.study_tree.focus_set()
        return "break"

    def _tab_from_studies_tree_to_link(self, _event=None) -> str:
        """Continue keyboard traversal from the tree to report linking."""
        if not roles.is_blind(self.conn):
            self.study_link_report_entry.focus_set()
        return "break"

    def _clear_studies_tree_focus(self, _event=None) -> None:
        """Restore neutral tree styling and remove transient focus semantics."""
        for iid in self.study_tree.get_children(""):
            self.study_tree.item(iid, tags=())
            for child_iid in self.study_tree.get_children(iid):
                self.study_tree.item(child_iid, tags=())
        self.studies_tree_frame.configure(**theme.focus_outline_options(False))
        if not roles.is_blind(self.conn):
            self.studies_focus_label.config(
                text="Keyboard: Tab through groups, decisions, report linking, and canonical choices.",
                foreground=theme.TOKENS["muted"],
            )

    def _selected_study_id(self) -> str | None:
        """Item 3: studies and reports are separate tree entities with
        distinct iids, but acting (Decide/Link) always targets the
        study -- whichever row is selected, a report child or the
        study itself."""
        sel = self.study_tree.selection()
        if not sel:
            return None
        iid = sel[0]
        parent = self.study_tree.parent(iid)
        return parent if parent else iid

    def _render_study_detail(self) -> None:
        """Items 4/5/6/7/9: separate detail content for a selected
        study (decision, rationale, report count) versus a selected
        report (canonical occurrence, full source-occurrence
        provenance, branch, retrieval status) -- study and report stay
        visually distinct entities, not just distinct tree rows."""
        self.study_detail_text.config(state="normal")
        self.study_detail_text.delete("1.0", "end")
        for child in self.study_canonical_frame.winfo_children():
            child.destroy()

        sel = self.study_tree.selection()
        if not sel:
            self.study_detail_text.config(state="disabled")
            return
        iid = sel[0]
        parent = self.study_tree.parent(iid)

        if not parent:
            s = self._study_row_by_id.get(iid)
            if s is None:
                self.study_detail_text.config(state="disabled")
                return
            report_ids = studies.reports_for_study(self.conn, iid)
            self.study_detail_text.insert("end", f"Study ID: {iid}\n", "study_heading")
            decision = s["decision"] or "No decision yet"
            self.study_detail_text.insert("end", f"Decision: {decision}\n", "study_heading")
            if s["has_conflict"]:
                self.study_detail_text.insert(
                    "end", "Conflict: study decision disagrees with its linked reports' outcomes.\n",
                )
            self.study_detail_text.insert("end", f"Rationale: {s['rationale'] or '(none recorded)'}\n\n")
            count_label = f"{len(report_ids)} report" + ("" if len(report_ids) == 1 else "s")
            self.study_detail_text.insert("end", f"Linked reports ({count_label}):\n", "study_heading")
            if report_ids:
                for rid in report_ids:
                    r = self._report_row_by_id.get(rid)
                    fields = self._load_fields(r["canonical_occurrence"]) if r and r["canonical_occurrence"] else {}
                    title = fields.get("title") or rid
                    self.study_detail_text.insert("end", f"  - {rid}  --  {title}\n")
            else:
                self.study_detail_text.insert("end", "  (none linked yet)\n")
        else:
            r = self._report_row_by_id.get(iid)
            if r is None:
                self.study_detail_text.config(state="disabled")
                return
            canonical_id = r["canonical_occurrence"]
            canonical_fields = self._load_fields(canonical_id) if canonical_id else {}
            title = canonical_fields.get("title") or "(no title)"
            branch_name = None
            if r["branch_id"]:
                branch_row = self.conn.execute(
                    "SELECT name FROM branches WHERE branch_id = ?", (r["branch_id"],)
                ).fetchone()
                branch_name = branch_row["name"] if branch_row else None
            status = r["retrieval_status"] or "pending"
            outcome = r["full_text_outcome"]
            self.study_detail_text.insert("end", f"Report ID: {iid}\n", "study_heading")
            self.study_detail_text.insert("end", f"Parent study: {parent}\n")
            self.study_detail_text.insert("end", f"Title: {title}\n", "study_heading")
            self.study_detail_text.insert(
                "end", f"Canonical occurrence: {canonical_id or '(not assigned)'}\n", "study_heading",
            )
            self.study_detail_text.insert(
                "end", f"Branch/source: {branch_name or '(unknown)'}  ({r['branch_id'] or 'no branch'})\n",
            )
            if status != "retrieved":
                self.study_detail_text.insert(
                    "end", f"Retrieval status: {status} -- full-text not yet assessed.\n\n",
                )
            else:
                self.study_detail_text.insert(
                    "end", f"Retrieval status: retrieved -> {outcome or '(unassessed)'}\n\n",
                )
            occurrence_ids = reports.occurrences_for_report(self.conn, iid)
            self.study_detail_text.insert(
                "end", f"Linked source occurrences ({len(occurrence_ids)}) -- provenance:\n", "study_heading",
            )
            for occ_id in occurrence_ids:
                occ_fields = self._load_fields(occ_id)
                occ_title = occ_fields.get("title") or occ_id
                marker = "  (canonical)" if occ_id == canonical_id else ""
                self.study_detail_text.insert("end", f"  - {occ_id}  --  {occ_title}{marker}\n")

            # Item 11: a real, keyboard-operable canonical-selection
            # control (Radiobuttons, per the Tk feasibility notes) --
            # only when there's an actual choice to make (2+ linked
            # occurrences); a single-occurrence report has nothing to
            # select among.
            if len(occurrence_ids) > 1:
                ttk.Label(self.study_canonical_frame, text="Available source occurrences:").pack(anchor="w")
                self.study_canonical_var.set(canonical_id or "")
                for occ_id in occurrence_ids:
                    occ_fields = self._load_fields(occ_id)
                    occ_title = occ_fields.get("title") or occ_id
                    ttk.Radiobutton(
                        self.study_canonical_frame,
                        text=f"{occ_id}  --  {occ_title}",
                        value=occ_id,
                        variable=self.study_canonical_var,
                        command=lambda rid=iid, oid=occ_id: self._select_canonical_occurrence(rid, oid),
                    ).pack(anchor="w")

        self.study_detail_text.config(state="disabled")

    def _select_canonical_occurrence(self, report_id: str, occurrence_id: str) -> None:
        """Item 11's Radiobutton action. Wires to the existing backend:
        `assign_progression` for a report's first canonical pick,
        `correct_progression` (with a required rationale, matching the
        study-decision rationale pattern) for re-selecting an
        already-progressed report -- never a silent overwrite."""
        if roles.is_blind(self.conn):
            messagebox.showerror("Locked while blind", "Studies is locked while blind mode is ON.")
            return
        r = self._report_row_by_id.get(report_id)
        current = r["canonical_occurrence"] if r else None
        if current == occurrence_id:
            return
        try:
            if current is None:
                reports.assign_progression(self.conn, self.reviewer_id, report_id, occurrence_id)
            else:
                rationale = simpledialog.askstring(
                    "Correction rationale",
                    "Rationale for changing the canonical occurrence:",
                )
                if not rationale:
                    self.study_canonical_var.set(current)
                    return
                reports.correct_progression(self.conn, self.reviewer_id, report_id, occurrence_id, rationale)
        except ValueError as e:
            messagebox.showerror("Cannot change canonical occurrence", str(e))
            self.study_canonical_var.set(current or "")
            return
        self.refresh_all_tabs()

    def _new_study(self) -> None:
        if roles.is_blind(self.conn):
            # Defense in depth: the "New study" button is already
            # disabled while blind in _refresh_studies_tab; this covers
            # any path that calls the handler directly.
            messagebox.showerror(
                "Locked while blind",
                "Studies is locked while blind mode is ON.",
            )
            return
        studies.create_study(self.conn, self.reviewer_id)
        self.refresh_all_tabs()

    def _study_decide(self, decision: str) -> None:
        if roles.is_blind(self.conn):
            messagebox.showerror(
                "Locked while blind",
                "Studies is locked while blind mode is ON.",
            )
            return
        study_id = self._selected_study_id()
        if study_id is None:
            return
        rationale = simpledialog.askstring("Rationale", f"Rationale for marking this study {decision}:")
        if not rationale:
            return
        studies.set_study_decision(self.conn, self.reviewer_id, study_id, decision, rationale)
        self.refresh_all_tabs()

    def _link_selected_study(self) -> None:
        if roles.is_blind(self.conn):
            # Defense in depth: this also closes the pre-round-2 leak
            # where `_report_ids_for_link` (sourced from
            # `reports.list_reports`, ungated) let a blinded reviewer
            # resolve report positions -- and so infer another
            # reviewer's full-text assessments -- through this control
            # even while the Full-text tab itself was locked.
            messagebox.showerror(
                "Locked while blind",
                "Studies is locked while blind mode is ON.",
            )
            return
        study_id = self._selected_study_id()
        if study_id is None:
            return
        try:
            idx = int(self.study_link_report_entry.get().strip())
        except ValueError:
            messagebox.showerror("Invalid index", "Enter the report's position number from the Full-text tab list (0-based).")
            return
        if idx < 0 or idx >= len(self._report_ids_for_link):
            messagebox.showerror("Invalid index", "No report at that position.")
            return
        studies.link_report_study(self.conn, self.reviewer_id, self._report_ids_for_link[idx], study_id)
        self.refresh_all_tabs()

    # ---- PRISMA & audit tab (counts snapshot + export; sparse by design) ----

    def _build_prisma_tab(self) -> None:
        # This tab's content (counts + diagram + audit log) can exceed
        # a window's visible height; wrap it in its own scrollable
        # Canvas so every control stays reachable via scrollbar, mouse
        # wheel, or keyboard -- found as a real gap during item 11's
        # keyboard check, not a cosmetic nit: on a standard 1280x800
        # window the audit log and Export button were below the fold
        # with literally no way to reach them (no scroll at all), not
        # just a focus-order miss.
        outer = ttk.Frame(self.notebook)
        self.notebook.add(outer, text="PRISMA & audit")

        self.prisma_scroll_canvas = tk.Canvas(outer, **theme.canvas_options("page"), highlightthickness=0, takefocus=1)
        outer_scroll = ttk.Scrollbar(outer, orient="vertical", command=self.prisma_scroll_canvas.yview)
        self.prisma_scroll_canvas.configure(yscrollcommand=outer_scroll.set)
        self.prisma_scroll_canvas.pack(side="left", fill="both", expand=True)
        outer_scroll.pack(side="right", fill="y")

        frame = ttk.Frame(self.prisma_scroll_canvas, padding=16)
        self.prisma_content = frame
        self.prisma_content.grid_columnconfigure(0, weight=1, uniform="prisma-cards")
        self.prisma_content.grid_columnconfigure(1, weight=1, uniform="prisma-cards")
        self.prisma_content.grid_rowconfigure(0, weight=1)
        frame_window = self.prisma_scroll_canvas.create_window((0, 0), window=frame, anchor="nw")

        self.prisma_flow_card = ttk.Frame(self.prisma_content, padding=12, style="Card.TFrame")
        self.prisma_flow_card.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self.prisma_flow_card.grid_columnconfigure(0, weight=1)
        self.prisma_flow_card.grid_rowconfigure(6, weight=1)
        self.prisma_audit_card = ttk.Frame(self.prisma_content, padding=12, style="Card.TFrame")
        self.prisma_audit_card.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self.prisma_audit_card.grid_rowconfigure(2, weight=1)
        def _on_frame_configure(event=None):
            self.prisma_scroll_canvas.configure(scrollregion=self.prisma_scroll_canvas.bbox("all"))

        def _rewrap_flow_notices(event):
            # Wrap the preview notices to the card's real width, which is only
            # known after layout (and changes with the window and the fonts).
            wrap = max(300, event.width - 48)
            for label in (self.prisma_watermark_label, self.prisma_live_data_label):
                label.configure(wraplength=wrap)
        self.prisma_flow_card.bind("<Configure>", _rewrap_flow_notices, add="+")
        frame.bind("<Configure>", _on_frame_configure)

        def _on_outer_canvas_configure(event):
            self.prisma_scroll_canvas.itemconfig(frame_window, width=event.width)
        self.prisma_scroll_canvas.bind("<Configure>", _on_outer_canvas_configure)

        def _on_mousewheel(event):
            self.prisma_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self.prisma_scroll_canvas.bind(
            "<Enter>", lambda e: self.prisma_scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel),
        )
        self.prisma_scroll_canvas.bind(
            "<Leave>", lambda e: self.prisma_scroll_canvas.unbind_all("<MouseWheel>"),
        )
        # Keyboard scroll: the outer canvas itself is a reachable,
        # keyboard-operable control (Up/Down/Page Up/Page Down), not
        # just a passive container.
        self.prisma_scroll_canvas.bind("<Up>", lambda e: self.prisma_scroll_canvas.yview_scroll(-1, "units"))
        self.prisma_scroll_canvas.bind("<Down>", lambda e: self.prisma_scroll_canvas.yview_scroll(1, "units"))
        self.prisma_scroll_canvas.bind("<Prior>", lambda e: self.prisma_scroll_canvas.yview_scroll(-1, "pages"))
        self.prisma_scroll_canvas.bind("<Next>", lambda e: self.prisma_scroll_canvas.yview_scroll(1, "pages"))

        # Items 1/8: this in-app view is a live preview bound to the
        # current watermark sequence, explicitly distinguished from
        # the authoritative, separately-watermarked export package --
        # not a claim that this tab itself is the export.
        self.prisma_watermark_label = ttk.Label(
            self.prisma_flow_card, text="", font=(self.font_ui, 8, "bold"), foreground=theme.TOKENS["info"],
            wraplength=500, justify="left",
        )
        self.prisma_watermark_label.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        self.prisma_live_data_label = ttk.Label(
            self.prisma_flow_card, text="Live project data · preview only · not synthetic",
            font=(self.font_ui, 8, "bold"), foreground=theme.TOKENS["maybe"], wraplength=560,
        )
        self.prisma_live_data_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))
        ttk.Label(self.prisma_flow_card, text="PRISMA 2020 counts snapshot", font=(self.font_ui, 11, "bold")).grid(
            row=2, column=0, columnspan=2, sticky="w",
        )
        self.prisma_counts_frame = ttk.Frame(self.prisma_flow_card)
        self.prisma_counts_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(8, 8))
        self.prisma_counts_frame.grid_propagate(False)
        self.prisma_counts_frame.configure(height=150)
        self.prisma_counts_text = tk.Text(self.prisma_counts_frame, height=6, wrap="word", font=(self.font_ui, 9),
                                          background=theme.TOKENS["surface"], foreground=theme.TOKENS["ink"],
                                          selectbackground=theme.TOKENS["accent_soft"], selectforeground=theme.TOKENS["ink"],
                                          highlightthickness=1, highlightbackground=theme.TOKENS["line"],
                                          yscrollcommand=lambda *args: self.prisma_counts_scrollbar.set(*args))
        self.prisma_counts_text.tag_configure("snapshot-heading", font=(self.font_ui, 11, "bold"), foreground=theme.TOKENS["accent"])
        self.prisma_counts_text.tag_configure("snapshot-section", font=(self.font_ui, 9, "bold"), foreground=theme.TOKENS["muted"])
        # Values match the 9pt label size so every identification row,
        # through "Open fuzzy pairs", fits the fixed-height snapshot.
        self.prisma_counts_text.tag_configure("snapshot-value", font=(self.font_ui, 9, "bold"), foreground=theme.TOKENS["ink"])
        self.prisma_counts_text.tag_configure("snapshot-detail", font=(self.font_ui, 9), foreground=theme.TOKENS["muted"])
        self.prisma_counts_text.tag_configure("snapshot-status", font=(self.font_ui, 9, "bold"), foreground=theme.TOKENS["include"])
        self.prisma_counts_text.tag_configure("snapshot-reconcile", font=(self.font_ui, 9, "bold"), foreground=theme.TOKENS["info"])
        self.prisma_counts_scrollbar = ttk.Scrollbar(
            self.prisma_counts_frame, orient="vertical", command=self.prisma_counts_text.yview,
        )
        self.prisma_counts_text.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        self.prisma_counts_scrollbar.grid(row=0, column=1, sticky="ns", padx=(0, 6), pady=6)
        self.prisma_counts_frame.grid_columnconfigure(0, weight=1)
        self.prisma_counts_frame.grid_rowconfigure(0, weight=1)
        self.prisma_counts_text.config(state="disabled")
        # `export.prisma_flow_boxes` builds for the export SVG -- never
        # independently recalculated, so diagram and export package
        # always agree. A visible title/description sit above the
        # canvas as real, text-accessible labels (not just alt text
        # on an image a screen reader can't reach), mirroring the
        # SVG's own <title>/<desc>.
        self.prisma_flow_heading = ttk.Label(self.prisma_flow_card, text="Flow diagram", font=(self.font_ui, 11, "bold"))
        self.prisma_flow_heading.grid(row=4, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Label(
            self.prisma_flow_card, text=export.PRISMA_SVG_TITLE, font=(self.font_ui, 10, "bold"),
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(2, 0))
        ttk.Label(
            self.prisma_flow_card, text=export.PRISMA_SVG_DESC, font=(self.font_ui, 9),
            foreground=theme.TOKENS["muted"], wraplength=500, justify="left",
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(0, 4))
        diagram_frame = ttk.Frame(self.prisma_flow_card)
        self.prisma_diagram_frame = diagram_frame
        diagram_frame.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(0, 0))
        self.prisma_diagram_canvas = tk.Canvas(
            diagram_frame, width=650, height=205, **theme.canvas_options("diagram"),
        )
        self.prisma_diagram_canvas.pack(anchor="w", pady=(0, 2))

        # Items 6/7: a read-only audit log Treeview
        # actor/event type as separate columns, per the Tk feasibility
        # notes), gated by the same audit_read scope export.py already
        # uses (roles.is_owner_or_auditor) and locked while blind for
        # everyone regardless of scope -- mirrors the Conflicts/
        # Full-text/Studies blind-lock pattern (UI layer enforces it,
        # not the backend; no role bypasses blind).
        ttk.Label(self.prisma_audit_card, text="Audit log", font=(self.font_ui, 11, "bold")).pack(anchor="w", pady=(8, 0))
        self.prisma_audit_scope_label = ttk.Label(
            self.prisma_audit_card, text="", font=(self.font_ui, 9), foreground=theme.TOKENS["muted"],
        )
        self.prisma_audit_scope_label.pack(anchor="w", pady=(2, 4))
        self.prisma_audit_tree = ttk.Treeview(
            self.prisma_audit_card, columns=("sequence", "time", "actor", "event_type"), show="headings", height=8,
        )
        tree_font = tkfont.Font(root=self.root, font=ttk.Style(self.root).lookup("Treeview", "font"))
        time_width = tree_font.measure("0000-00-00 00:00:00") + 16
        for col, label, width in [
            ("sequence", "Seq", 48), ("time", "Time (UTC)", time_width),
            ("actor", "Actor", 88), ("event_type", "Event type", 168),
        ]:
            self.prisma_audit_tree.heading(col, text=label)
            self.prisma_audit_tree.column(col, width=width, anchor="w")
        self.prisma_audit_tree.pack(fill="both", expand=True, pady=(0, 8))

        self.prisma_export_button = ttk.Button(self.prisma_audit_card, text="Export package...", command=self.action_export)
        self.prisma_export_button.configure(takefocus=1)
        self.prisma_export_button.pack(anchor="w")
        ttk.Label(
            self.prisma_audit_card,
            text="Export package writes the official watermarked PRISMA diagram, decisions, and audit log."
                 " This tab is a read-only preview, not a separate export path.",
            font=(self.font_ui, 8), foreground=theme.TOKENS["muted"], wraplength=300,
        ).pack(anchor="w", pady=(4, 0))

    def _refresh_prisma_tab(self) -> None:
        # Aggregate counts can reveal another reviewer's decisions by
        # comparison. While blind, only owner/full_export may see them.
        if roles.is_blind(self.conn) and not roles.is_owner_or_auditor(
            self.conn, self.reviewer_id, "full_export",
        ):
            self.prisma_watermark_label.config(
                text="PRISMA counts and the flow diagram are locked while blind mode is ON.",
            )
            self.prisma_live_data_label.configure(text="Project-wide counts are hidden during blind review.")
            self.prisma_counts_text.config(state="normal")
            self.prisma_counts_text.delete("1.0", "end")
            self.prisma_counts_text.insert("1.0", "PRISMA counts are locked while blind mode is ON.")
            self.prisma_counts_text.config(state="disabled")
            self.prisma_diagram_canvas.delete("all")
            self.prisma_flow_boxes_by_id = {}
            self._refresh_prisma_audit_log()
            return

        watermark = export.watermark_sequence(self.conn)
        self.prisma_watermark_label.config(
            text=f"Preview as of watermark sequence {watermark} -- not the authoritative export."
                 " Use \"Export package...\" for the official watermarked PRISMA diagram and audit log.",
            wraplength=max(300, self.prisma_flow_card.winfo_width() - 48),
        )
        self.prisma_live_data_label.configure(
            text="Live project data · preview only · not synthetic",
            wraplength=max(300, self.prisma_flow_card.winfo_width() - 48),
        )

        snapshot = prisma.full_snapshot(self.conn)
        ident = snapshot["identification"]
        rep = snapshot["reports"]
        stud = snapshot["studies"]
        violations = prisma.verify_invariants(self.conn)

        lines = [
            f"Identified (database): {ident['identified_database']}",
            f"Identified (register): {ident['identified_register']}",
            f"Identified (other):    {ident['identified_other']}",
            f"Identified (total):    {ident['identified_total']}",
            f"Removed before screen: {ident['removed_before_screen']}",
            f"Post-screen corrections: {ident['post_screen_duplicate_corrections']}",
            f"Open fuzzy pairs:      {ident['open_fuzzy_pairs']}",
            "",
            "Per branch:",
        ]
        for branch_id, b in ident["branches"].items():
            lines.append(
                f"  {branch_id}: identified={b['identified']} removed={b['removed_before_screen']}"
                f" prescreen_pending={b['prescreen_pending']} screening_pending={b['screening_pending']}"
                f" screened={b['records_screened']}"
            )
            # Item 3: the literal reconciling arithmetic, not just a
            # pass/fail note -- recomputed with Python's own `==` on
            # every refresh, never hand-asserted.
            branch_sum = (
                b["removed_before_screen"] + b["prescreen_pending"]
                + b["screening_pending"] + b["records_screened"]
            )
            reconciled = b["identified"] == branch_sum
            lines.append(
                f"    reconciles: {b['identified']} = {b['removed_before_screen']}"
                f"+{b['prescreen_pending']}+{b['screening_pending']}+{b['records_screened']}"
                + ("  [reconciled]" if reconciled else "  [MISMATCH]")
            )
        lines += [
            "",
            f"Reports sought:    {rep['reports_sought']}",
            f"Reports pending:   {rep['reports_pending']}",
            f"Reports not retrieved: {rep['reports_not_retrieved']}",
            f"Reports assessed:  {rep['reports_assessed']}",
            f"Reports included:  {rep['reports_included']}",
            f"Reports excluded:  {rep['reports_excluded']}",
        ]
        # Item 4: same discipline -- the two equations
        # `verify_invariants` already checks, shown as literal
        # arithmetic, not just whether they passed.
        assessed_sum = rep["reports_included"] + rep["reports_excluded"]
        sought_sum = rep["reports_assessed"] + rep["reports_not_retrieved"] + rep["reports_pending"]
        lines.append(
            f"  reconciles: {rep['reports_assessed']} = {rep['reports_included']}+{rep['reports_excluded']}"
            + ("  [reconciled]" if rep["reports_assessed"] == assessed_sum else "  [MISMATCH]")
        )
        lines.append(
            f"  reconciles: {rep['reports_sought']} = {rep['reports_assessed']}"
            f"+{rep['reports_not_retrieved']}+{rep['reports_pending']}"
            + ("  [reconciled]" if rep["reports_sought"] == sought_sum else "  [MISMATCH]")
        )
        lines += [
            "",
            f"Studies included:  {stud['studies_included']}",
            f"Reports of included studies: {stud['reports_of_included_studies']}",
        ]
        if violations:
            lines += ["", "INVARIANT VIOLATIONS:"] + [f"  - {v}" for v in violations]
        else:
            lines += ["", "No invariant violations."]

        self.prisma_counts_text.config(state="normal")
        self.prisma_counts_text.delete("1.0", "end")
        self.prisma_counts_text.insert("1.0", "\n".join(lines))
        for line_number, line in enumerate(lines, start=1):
            start = f"{line_number}.0"
            end = f"{line_number}.end"
            if line in {"Per branch:", "INVARIANT VIOLATIONS:"}:
                self.prisma_counts_text.tag_add("snapshot-section", start, end)
            elif line.startswith("No invariant violations."):
                self.prisma_counts_text.tag_add("snapshot-status", start, end)
            elif line.startswith("    reconciles:") or line.startswith("  reconciles:"):
                self.prisma_counts_text.tag_add("snapshot-reconcile", start, end)
                status_index = line.find("[reconciled]")
                if status_index >= 0:
                    self.prisma_counts_text.tag_add(
                        "snapshot-status", f"{line_number}.{status_index}", end,
                    )
            elif ":" in line and not line.startswith("  "):
                colon = line.find(":")
                self.prisma_counts_text.tag_add("snapshot-section", start, f"{line_number}.{colon}")
                if colon + 1 < len(line):
                    self.prisma_counts_text.tag_add("snapshot-value", f"{line_number}.{colon + 1}", end)
        self.prisma_counts_text.config(state="disabled")

        self._refresh_prisma_diagram()
        self._refresh_prisma_audit_log()

    def _refresh_prisma_diagram(self) -> None:
        """Items 2/10: redraws the Canvas from `export.prisma_flow_boxes`
        -- the same box list (geometry/label/value) the export SVG
        builds from one `prisma.full_snapshot` call, so the live
        diagram and the exported one never disagree. Each box is two
        real Canvas text items (label + value), not an image -- the
        value is always plain, selectable text, never color-coded
        meaning (a box's fill never changes with its value)."""
        canvas = self.prisma_diagram_canvas
        canvas.delete("all")
        boxes = export.prisma_flow_boxes(self.conn)
        self.prisma_flow_boxes_by_id = {box["id"]: box for box in boxes}
        canvas_width = 650
        canvas_height = 205
        # Allocate within the live equal-card viewport; otherwise later
        # diagram boxes and their values are silently clipped by Tk Canvas.
        self.prisma_diagram_canvas.update_idletasks()
        canvas_width = max(300, min(610, self.prisma_flow_card.winfo_width() - 36))
        self.prisma_diagram_canvas.configure(width=canvas_width)
        # One lattice: six equal rows with a 7px arrow gap fit the fixed
        # 205px canvas; each side box shares its source row so exclusion
        # arrows run straight across. Widths come from measured text, so
        # a label never runs into its value or a neighbouring box.
        label_font = tkfont.Font(root=self.root, font=(self.font_ui, 8))
        stage_font = tkfont.Font(root=self.root, font=(self.font_ui, 8, "bold"))
        value_font = tkfont.Font(root=self.root, font=(self.font_ui, 10, "bold"))
        stages = (
            ("IDENTIFICATION", "box-identified"), ("SCREENING / RETRIEVAL", "box-sought"),
            ("ELIGIBILITY", "box-assessed"), ("INCLUDED", "box-included"),
        )
        stage_width = max(stage_font.measure(word) for text, _ in stages for word in text.split()) + 4
        main_rows = ["box-identified", "box-removed", "box-sought", "box-assessed", "box-included", "box-studies-included"]
        side_of = {"box-not-retrieved": "box-sought", "box-excluded": "box-assessed"}
        row_height, row_gap, top = 26, 7, 4
        value_reserve = max(value_font.measure(str(b["value"])) for b in boxes) + 12

        def box_width(ids) -> int:
            return max(label_font.measure(b["label"]) for b in boxes if b["id"] in ids) + 14 + value_reserve

        main_x = 8 + stage_width + 8
        main_width, side_width = box_width(main_rows), box_width(side_of)
        arrow_gap = max(16, min(36, canvas_width - 4 - main_x - main_width - side_width))
        side_x = main_x + main_width + arrow_gap
        if side_x + side_width > canvas_width - 4:
            # Narrow card: split the shortfall between the two columns;
            # labels then wrap inside their boxes instead of overflowing.
            shortfall = side_x + side_width - (canvas_width - 4)
            main_width -= shortfall // 2
            side_width -= shortfall - shortfall // 2
            side_x = main_x + main_width + arrow_gap
        row_y = {box_id: top + index * (row_height + row_gap) for index, box_id in enumerate(main_rows)}
        positions: dict[str, tuple[int, int, int, int]] = {}
        for box in boxes:
            if box["id"] in row_y:
                positions[box["id"]] = (main_x, row_y[box["id"]], main_width, row_height)
            else:
                positions[box["id"]] = (side_x, row_y[side_of[box["id"]]], side_width, row_height)

        # Live preview only: engineering graph paper on the lattice the
        # boxes use. Skipped in Windows high contrast; export.py never draws it.
        if not display_prefs.high_contrast():
            for x in range(0, canvas_width + 1, 8):
                canvas.create_line(x, 0, x, canvas_height, tags=("grid",),
                                   fill=theme.TOKENS["grid_major" if x % 40 == 0 else "grid_minor"])
            for y in range(0, canvas_height + 1, 8):
                canvas.create_line(0, y, canvas_width, y, tags=("grid",),
                                   fill=theme.TOKENS["grid_major" if y % 40 == 0 else "grid_minor"])

        # Preserve every original PRISMA box value/label; arrows show the
        # stage relationship without adding new derived data.
        for text, box_id in stages:
            canvas.create_text(
                8, row_y[box_id] + 5, anchor="nw", text=text, width=stage_width,
                font=(self.font_ui, 8, "bold"), fill=theme.TOKENS["muted"],
            )
        for start_id, end_id in (
            ("box-identified", "box-removed"),
            ("box-removed", "box-sought"),
            ("box-sought", "box-assessed"),
            ("box-assessed", "box-included"),
            ("box-included", "box-studies-included"),
        ):
            x1, y1, w1, h1 = positions[start_id]
            x2, y2, w2, _ = positions[end_id]
            canvas.create_line(
                x1 + w1 / 2, y1 + h1, x2 + w2 / 2, y2,
                fill=theme.TOKENS["muted"], width=1, arrow="last",
            )
        for side_id, source_id in side_of.items():
            source_x, source_y, source_w, source_h = positions[source_id]
            canvas.create_line(
                source_x + source_w, source_y + source_h / 2,
                positions[side_id][0], source_y + source_h / 2,
                fill=theme.TOKENS["muted"], width=1, arrow="last",
            )

        max_x = canvas_width
        max_y = canvas_height
        diagram = theme.diagram_style(self.root)
        for b in boxes:
            x, y, w, h = positions[b["id"]]
            canvas.create_rectangle(
                x, y, x + w, y + h, fill=diagram["fill"], outline=theme.TOKENS["line_strong"], width=1,
            )
            canvas.create_text(
                x + 7, y + 5, anchor="nw", text=b["label"],
                font=(self.font_ui, 8), fill=theme.TOKENS["muted"], width=max(40, w - 14 - value_reserve),
            )
            canvas.create_text(
                x + w - 7, y + h - 4,
                anchor="se", text=str(b["value"]),
                font=(self.font_ui, 10, "bold"), fill=theme.TOKENS["accent"],
            )
            max_x = max(max_x, x + w)
            max_y = max(max_y, y + h)
        canvas.config(scrollregion=(0, 0, max_x, max_y))

    def _refresh_prisma_audit_log(self) -> None:
        """Items 6/7: the audit log is reviewer-attributable, vote-
        level data the moment it's populated (confirmed during the
        baseline's blind check: `events` rows for screening.vote_cast
        carry `actor` and a decision payload) -- so it is locked while
        blind for everyone, same as Conflicts/Full-text/Studies, with
        no role-based bypass, and additionally gated by the
        `audit_read` scope (or ownership) export.py already uses, so a
        plain reviewer with blind off still can't see every actor's
        events without an explicit grant."""
        self.prisma_audit_tree.delete(*self.prisma_audit_tree.get_children())

        if roles.is_blind(self.conn):
            self.prisma_audit_scope_label.config(
                text="Audit log is locked while blind mode is ON."
                " The project owner must turn blind mode off to open it.",
            )
            return

        if not roles.is_owner_or_auditor(self.conn, self.reviewer_id, "audit_read"):
            self.prisma_audit_scope_label.config(
                text="Audit log requires the audit_read role, granted by the project owner.",
            )
            return

        self.prisma_audit_scope_label.config(
            text=f"Showing all events (owner/audit_read scope) as reviewer {self.reviewer_id}.",
        )
        for event in export.list_audit_events(self.conn):
            self.prisma_audit_tree.insert(
                "", "end", iid=event["event_id"],
                values=(event["sequence"], _audit_display_time(event["occurred_at"]), event["actor"], event["event_type"]),
            )


def _audit_display_time(occurred_at: str) -> str:
    """Whole seconds in UTC for the on-screen log; the export keeps full precision."""
    try:
        moment = datetime.datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return str(occurred_at)
    if moment.tzinfo is not None:
        moment = moment.astimezone(datetime.timezone.utc)
    return moment.strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    reviewer_id = os.environ.get(REVIEWER_ID_ENV, "reviewer1")
    default_path = os.path.join(os.path.expanduser("~"), "screening-workbench-project.sqlite")
    typefaces.load_bundled_fonts()  # before Tk's first font lookup
    root = tk.Tk()
    ScreeningWorkbenchApp(root, default_path, reviewer_id=reviewer_id)
    root.mainloop()


if __name__ == "__main__":
    main()


# --- Known v1 UI gaps (logged per implementer-prompt hard constraint #1) ---
# * The Studies tab's report-link control uses a plain position-number
#   entry (matched against the Full-text tab's report list order) rather
#   than a proper picker widget -- functional but not great UX; a
#   searchable report selector is a follow-up.
# * No bulk select/decide (deciding many occurrences in one action) --
#   screening-workflow spec §4's single-keystroke decisions plus search/
#   year/journal/batch filters and the undecided-only toggle are
#   implemented; batch decide-many-at-once is not.
# * No accessibility pass beyond the Screening record pane's focus ring
#   (focus-visible styling elsewhere, screen-reader status announcements)
#   has been done on these widgets yet.
# * The Duplicates tab's multi-way cluster merge keeps exactly one whole
#   survivor and absorbs everyone else in the cluster; there's no way to
#   split a cluster into two sub-groups if the automatic connected-
#   component grouping (any two members scoring >=0.90) over-groups a
#   borderline chain (A~B and B~C both just clear the threshold, but A
#   and C aren't really the same study).
# * docs/ui-reference-screening.md's visual chrome is NOT implemented:
#   no section-nav with per-tab count badges/locked-while-blind
#   indicator, no scrollable queue list showing upcoming records (only
#   the current one), no status bar with a live last-action confirmation
#   + compact key legend, no structured-abstract label styling, no token
#   colors/fonts/spacing from docs/design-system.md applied to ttk
#   widgets (current styling is plain Tk/ttk defaults). The Screening
#   tab's *structure* (search/facets/undecided-toggle/focus-ring/
#   taxonomy-picker/recent-decisions-panel) matches the reference;
#   the *visual* pass against it has not started.

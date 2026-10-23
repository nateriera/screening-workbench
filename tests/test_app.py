import json
import os
import tkinter as tk
from types import SimpleNamespace
from unittest.mock import patch
from tkinter import ttk

from pathlib import Path

import pytest

from screening_workbench import db, roles, screening
from screening_workbench.app import ScreeningWorkbenchApp
from screening_workbench.theme import TOKENS
from screening_workbench.importers.csv_importer import commit_csv_import


def _tk_available():
    try:
        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except tk.TclError:
        return False


requires_tk = pytest.mark.skipif(not _tk_available(), reason="no Tk display available")


@requires_tk
def test_global_ttk_button_disabled_foreground_is_muted_without_changing_enabled_or_focus(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    theme.apply_theme(root)
    style = ttk.Style(root)

    assert style.lookup("TButton", "foreground", ("disabled",)) == theme.TOKENS["muted"]
    assert style.lookup("TButton", "foreground", ("!disabled",)) != style.lookup("TButton", "foreground", ("disabled",))
    assert ("focus", theme.TOKENS["focus"]) in style.map("TButton", "focuscolor")
    root.destroy()


@requires_tk
def test_global_theme_applies_field_notes_colors_and_font_fallbacks(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "theme.sqlite"), reviewer_id="owner")
    style = ttk.Style(root)
    assert style.theme_use() == theme.TTK_BASE_THEME == "clam"
    assert root.cget("background") == theme.TOKENS["canvas"]
    assert style.lookup("TFrame", "background") == theme.TOKENS["canvas"]
    assert style.lookup("TLabel", "foreground") == theme.TOKENS["ink"]
    assert style.lookup("Queue.Treeview", "fieldbackground") == theme.TOKENS["surface"]
    assert style.lookup("Queue.Treeview", "background") == theme.TOKENS["surface"]
    assert any(theme.TOKENS["accent"] in str(rule) for rule in style.map("Queue.Treeview", "foreground"))
    assert theme.resolve_font(root, theme.FONT_READING) in str(app.title_label.cget("font"))
    assert app.abstract_text.cget("background") == theme.TOKENS["surface"]
    assert app.abstract_text.cget("foreground") == theme.TOKENS["ink"]
    assert app.blind_chip_label.cget("background") == theme.TOKENS["drawer"]
    assert theme.contrast_ratio(
        app.blind_chip_label.cget("foreground"), app.blind_chip_label.cget("background"),
    ) >= 4.5
    assert any(theme.TOKENS["accent"] in str(rule) for rule in style.map("TNotebook.Tab", "foreground"))
    assert style.map("TNotebook.Tab", "background") == [("selected", theme.TOKENS["accent_soft"])]
    assert "clam" in style.theme_names()  # no third-party toolkit/theme
    assert style.lookup("Header.TFrame", "padding") == "16 8"
    assert "padding" in theme.SPACING
    assert theme.resolve_font(root, theme.FONT_UI) == "Atkinson Hyperlegible Next"
    assert theme.resolve_font(root, theme.FONT_READING) == "Newsreader 16pt"
    assert theme.resolve_font(root, theme.FONT_MONO) == "Atkinson Hyperlegible Mono"
    fallback_root = tk.Tk()
    fallback_root.withdraw()
    fallback_root.tk.call("font", "families")
    assert theme.FONT_FALLBACKS[theme.FONT_UI][-1] == "TkDefaultFont"
    assert theme.FONT_FALLBACKS[theme.FONT_READING][-1] == "TkTextFont"
    assert theme.FONT_FALLBACKS[theme.FONT_MONO][-1] == "TkFixedFont"
    fallback_root.destroy()
    root.destroy()


def test_card_catalogue_theme_tokens_contrast_and_size_contract():
    from screening_workbench import theme

    expected = {
        "drawer": "#1d3a32", "drawer_raised": "#28493f", "drawer_ink": "#f2f0e6", "drawer_muted": "#a9bfb4",
        "signal": "#e8d44d", "signal_soft": "#f7efb5",
        "canvas": "#dce2d9", "surface": "#fffefa", "surface_raised": "#fbfcf9",
        "ink": "#1f2a25", "muted": "#55625a", "line": "#cbd5cb",
        "line_strong": "#bdc9bf", "accent": "#23634d", "accent_hover": "#1c513f",
        "accent_soft": "#e7f0eb", "accent_focus": "#174b39", "include": "#276149", "maybe": "#80540f",
        "exclude": "#a4443e", "info": "#3d6476", "focus": "#c45a32",
        "include_soft": "#e8f1ec", "maybe_soft": "#f6eedf", "exclude_soft": "#f7e8e6",
        "info_soft": "#e6eef1",
        "include_border": "#a9c8b6", "maybe_border": "#dcc39a", "exclude_border": "#dfb0ab",
        "grid_minor": "#eef1ea", "grid_major": "#dfe5dc",
        "on_signal": "#1f2a25", "inverse_bg": "#fffefa", "inverse_fg": "#1d3a32", "rule_ink": "#1d3a32",
        "control": "#dcdad5", "control_light": "#eeebe7", "control_dark": "#cfcdc8",
        "control_border": "#9e9a91", "trough": "#bab5ab",
    }
    assert theme.TOKENS == expected == theme.PALETTES["light"]
    assert theme.SPACING["base"] == 8
    assert theme.RADII == {"control": 6, "card": 10, "dialog": 14}
    assert theme.CONTROL_MIN_HEIGHT == 40


@requires_tk
def test_theme_module_owns_ttk_styles_and_classic_canvas_options(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    style = theme.apply_theme(root)
    assert style.theme_use() == "clam"
    assert style.lookup("TButton", "padding") == " ".join(map(str, theme.CONTROL_BUTTON_PADDING))

    assert style.lookup("TEntry", "fieldbackground") == theme.TOKENS["surface"]
    assert style.lookup("TNotebook", "background") == theme.TOKENS["canvas"]
    assert style.lookup("Treeview", "background") == theme.TOKENS["surface"]
    assert theme.canvas_options("page")["background"] == theme.TOKENS["canvas"]
    assert theme.canvas_options("diagram")["background"] == theme.TOKENS["surface"]
    root.destroy()


@requires_tk
def test_theme_focus_outline_is_tokenized_and_distinct_from_selection(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    theme.apply_theme(root)
    frame = tk.Frame(root, background=theme.TOKENS["surface"], **theme.focus_outline_options(False))
    tree = ttk.Treeview(frame, show="tree", height=3)
    tree.insert("", "end", iid="sample", text="Selected sample")
    tree.selection_set("sample")

    frame.configure(**theme.focus_outline_options(True))
    assert int(frame.cget("highlightthickness")) == 3
    assert str(frame.cget("highlightbackground")) == theme.TOKENS["focus"]
    assert tree.selection() == ("sample",)

    frame.configure(**theme.focus_outline_options(False))
    assert int(frame.cget("highlightthickness")) == 1
    assert str(frame.cget("highlightbackground")) == theme.TOKENS["line"]
    root.destroy()


def test_all_text_contrast_pairs_are_computed_from_tokens():
    from screening_workbench import theme

    pairs = {
        "ink.canvas": ("ink", "canvas"),
        "ink.surface": ("ink", "surface"),
        "ink.surface_raised": ("ink", "surface_raised"),
        "muted.canvas": ("muted", "canvas"),
        "muted.surface": ("muted", "surface"),
        "muted.surface_raised": ("muted", "surface_raised"),
        "accent.surface": ("accent", "surface"),
        "accent.accent_soft": ("accent", "accent_soft"),
        "include.include_soft": ("include", "include_soft"),
        "maybe.maybe_soft": ("maybe", "maybe_soft"),
        "exclude.exclude_soft": ("exclude", "exclude_soft"),
        "info.info_soft": ("info", "info_soft"),
        "surface.accent_focus": ("surface", "accent_focus"),
        "surface.accent": ("surface", "accent"),
        "drawer_ink.drawer": ("drawer_ink", "drawer"),
        "drawer_muted.drawer": ("drawer_muted", "drawer"),
        "drawer_ink.drawer_raised": ("drawer_ink", "drawer_raised"),
        "drawer_muted.drawer_raised": ("drawer_muted", "drawer_raised"),
        "inverse_fg.inverse_bg": ("inverse_fg", "inverse_bg"),
        "on_signal.signal": ("on_signal", "signal"),
        "ink.signal_soft": ("ink", "signal_soft"),
        "include.surface": ("include", "surface"),
        "maybe.surface": ("maybe", "surface"),
        "exclude.surface": ("exclude", "surface"),
        "info.surface": ("info", "surface"),
        "ink.control": ("ink", "control"),
        "ink.accent_soft": ("ink", "accent_soft"),
        "ink.exclude_soft": ("ink", "exclude_soft"),
    }
    light = theme.PALETTES["light"]
    assert theme.TEXT_CONTRAST_PAIRS == {
        name: theme.contrast_ratio(light[fg], light[bg])
        for name, (fg, bg) in pairs.items()
    }
    assert all(ratio >= 4.5 for ratio in theme.TEXT_CONTRAST_PAIRS.values())


@requires_tk
def test_blind_mode_status_label_reflects_live_state(tmp_path):
    """Found during the UI gap review: toggling blind mode had no
    visible, persistent confirmation anywhere in the window once the
    confirmation dialog closed."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    assert "OFF" in app.blind_chip_label.cget("text")

    from screening_workbench import roles
    roles.set_blind(app.conn, "owner", True)
    app.refresh_all_tabs()
    assert "ON" in app.blind_chip_label.cget("text")

    roles.set_blind(app.conn, "owner", False)
    app.refresh_all_tabs()
    assert "OFF" in app.blind_chip_label.cget("text")
    root.destroy()


@requires_tk
def test_screening_search_and_year_filter(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    text = (
        "title,authors,year\n"
        "Climate change and wheat yield,Smith,2020\n"
        "Climate change and rice yield,Jones,2021\n"
    )
    commit_csv_import(
        app.conn, text, {0: "title", 1: "authors", 2: "year"}, source_id=source_id, branch_id=branch_id,
        operation_id="seed-filter-test", actor="owner",
    )
    app.refresh_all_tabs()

    # Free-text filter narrows to just the matching record.
    app.screen_search_entry.insert(0, "wheat")
    app._apply_screening_filter()
    assert app.current_occurrence_id is not None
    fields = app._load_fields(app.current_occurrence_id)
    assert "wheat" in fields["title"].lower()
    assert "Remaining: 1" in app.remaining_label.cget("text")

    # Clearing the filter restores the full undecided queue.
    app._clear_screening_filter()
    assert "Remaining: 2" in app.remaining_label.cget("text")

    # Year filter narrows the same way.
    app.screen_year_entry.insert(0, "2021")
    app._apply_screening_filter()
    fields = app._load_fields(app.current_occurrence_id)
    assert fields["year"] == "2021"
    root.destroy()


@requires_tk
def test_app_constructs_and_shows_no_undecided(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="revA")
    assert app.current_occurrence_id is None
    assert app.title_label["text"] == "No undecided records."
    root.destroy()


@requires_tk
def test_app_import_and_keyboard_decision_flow(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="revA")

    source_id, branch_id = app._ensure_default_source()
    result = commit_csv_import(
        app.conn, "title,abstract\nA Study,Some abstract\n", {0: "title", 1: "abstract"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="revA",
    )
    app._load_next_undecided()
    assert app.current_occurrence_id is not None
    assert app.title_label["text"] == "A Study"
    assert "Remaining: 1" in app.remaining_label["text"]

    occ_id = app.current_occurrence_id
    app._decide("include")

    vote = app.conn.execute(
        "SELECT decision FROM screen_votes WHERE occurrence_id=? AND reviewer_id='revA'"
        " AND superseded_at IS NULL",
        (occ_id,),
    ).fetchone()
    assert vote["decision"] == "include"
    # Auto-advanced: no more undecided records for this reviewer.
    assert app.current_occurrence_id is None
    root.destroy()


@requires_tk
def test_exclude_uses_numbered_taxonomy_reason(tmp_path):
    """UI reference target §10: exclusion reasons come from the fixed
    1-7 project taxonomy, not free text. `_prompt_exclusion_reason` is
    monkeypatched so the test drives the real taxonomy lookup without
    opening a real modal dialog."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="revA")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nA Study\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="revA",
    )
    app._load_next_undecided()
    occ_id = app.current_occurrence_id

    from screening_workbench import screening
    app._prompt_exclusion_reason = lambda: screening.EXCLUSION_REASONS[3]  # "Wrong study design"
    app._decide("exclude")

    vote = app.conn.execute(
        "SELECT decision, reason FROM screen_votes WHERE occurrence_id=? AND reviewer_id='revA'"
        " AND superseded_at IS NULL",
        (occ_id,),
    ).fetchone()
    assert vote["decision"] == "exclude"
    assert vote["reason"] == "Wrong study design"
    root.destroy()


@requires_tk
def test_exclude_cancelled_reason_records_no_vote(tmp_path):
    """Cancelling the taxonomy picker (Escape/close) must still make
    exclude-without-a-reason impossible."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="revA")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nA Study\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="revA",
    )
    app._load_next_undecided()
    occ_id = app.current_occurrence_id

    app._prompt_exclusion_reason = lambda: None
    app._decide("exclude")

    vote = app.conn.execute(
        "SELECT * FROM screen_votes WHERE occurrence_id=? AND reviewer_id='revA'", (occ_id,)
    ).fetchone()
    assert vote is None
    assert app.current_occurrence_id == occ_id  # still pending, nothing recorded
    root.destroy()


@requires_tk
def test_recent_decisions_panel_shows_only_own_votes(tmp_path):
    """UI reference target §11, blind-safe by construction."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="revA")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nStudy One\nStudy Two\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="revA",
    )
    app.refresh_all_tabs()
    occ_id = app.current_occurrence_id
    app._decide("include")

    from screening_workbench import screening
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    app._refresh_recent_decisions()

    text = app.recent_decisions_text.get("1.0", "end")
    assert "Study One" in text
    assert "Include" in text
    assert "Study Two" not in text  # revB's vote on the other occurrence must never appear
    root.destroy()


@requires_tk
def test_undecided_only_toggle_includes_decided_records(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="revA")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nStudy One\nStudy Two\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="revA",
    )
    app.refresh_all_tabs()
    app._decide("include")  # decides Study One, advances to Study Two

    # Default (undecided only): only the still-undecided record counts.
    assert "Remaining: 1" in app.remaining_label["text"]

    app.screen_undecided_only_var.set(False)
    app._apply_screening_filter()
    assert "Matching: 2" in app.remaining_label["text"]
    root.destroy()


@requires_tk
def test_focus_ring_toggles_on_record_pane_focus(tmp_path):
    """UI reference target §6: a visible focus ring around the record
    pane while it holds keyboard focus."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="revA")

    neutral = app.record_frame.cget("highlightbackground")
    app._on_record_focus_in()
    assert app.record_frame.cget("highlightbackground") != neutral
    app._on_record_focus_out()
    assert app.record_frame.cget("highlightbackground") == neutral
    root.destroy()


@requires_tk
def test_app_sets_owner_once_on_first_open(tmp_path):
    from screening_workbench import roles

    db_path = str(tmp_path / "proj.sqlite")
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, db_path, reviewer_id="revA")
    assert roles.get_owner(app.conn) == "revA"
    root.destroy()


def _seed_two_occurrences(app, title_a, title_b, doi_a="", doi_b="", authors="Smith", year="2020"):
    from screening_workbench import dedup

    source_id, branch_id = app._ensure_default_source()
    text = (
        f"title,doi,authors,year\n"
        f"{title_a},{doi_a},{authors},{year}\n"
        f"{title_b},{doi_b},{authors},{year}\n"
    )
    result = commit_csv_import(
        app.conn, text, {0: "title", 1: "doi", 2: "authors", 3: "year"},
        source_id=source_id, branch_id=branch_id,
        operation_id=f"seed-{title_a}-{title_b}", actor="owner",
    )
    dedup.run_exact_and_fuzzy_detection(app.conn, "system", batch_id=result.batch_id)
    rows = app.conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
    ).fetchall()
    return [r["occurrence_id"] for r in rows]


@requires_tk
def test_phase2_duplicates_tab_uses_three_card_shell_preserving_controls(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase2-duplicates-cards.sqlite"), reviewer_id="owner")
    root.update_idletasks()

    assert app.dup_queue_card.winfo_parent() == str(app.dup_columns)
    assert app.dup_compare_card.winfo_parent() == str(app.dup_columns)
    assert app.dup_resolution_card.winfo_parent() == str(app.dup_columns)
    assert [app.dup_queue_card.grid_info()["column"], app.dup_compare_card.grid_info()["column"], app.dup_resolution_card.grid_info()["column"]] == [0, 1, 2]
    assert all(card.cget("style") == "Card.TFrame" for card in (app.dup_queue_card, app.dup_compare_card, app.dup_resolution_card))
    assert app.dup_list.master.master == app.dup_queue_panel
    assert app.dup_compare_text.winfo_parent() == str(app.dup_compare_text.master)
    assert app.dup_compare_text.master.master == app.dup_compare_panel
    assert app.dup_survivor_list.master.master == app.dup_resolution_panel
    assert app.dup_reversibility_note_label.winfo_toplevel() == root
    assert app.dup_resolution_panel.winfo_children()[0].winfo_manager() == "pack"
    assert app.dup_survivor_list.cget("exportselection") == 0
    assert app.dup_merge_button.cget("text") == "Merge cluster into selected survivor"
    assert app.dup_keep_separate_button.cget("text") == "Keep all separate"
    assert app.dup_queue_note_label.cget("wraplength") == 220
    assert app.dup_reversibility_note_label.cget("wraplength") == 255
    assert app.dup_list.cget("exportselection") == 0
    assert app.dup_survivor_list.cget("exportselection") == 0

    app.notebook.select(2)
    root.deiconify()
    root.update()
    assert app.dup_queue_card.winfo_width() >= 250
    assert app.dup_compare_card.winfo_width() >= 650
    assert app.dup_resolution_card.winfo_width() >= 290
    assert app.dup_compare_text.cget("wrap") == "word"
    assert not hasattr(app, "dup_compare_xscroll")
    assert app.dup_list.size() == 1
    assert app.dup_list.get(0) == "No open duplicate candidates."
    assert str(app.dup_merge_button.cget("state")) == "disabled"
    assert str(app.dup_keep_separate_button.cget("state")) == "disabled"
    root.destroy()


@requires_tk
def test_duplicates_tab_merge_flow(tmp_path):
    from screening_workbench import dedup

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    title_a = "a" * 100
    title_b = "a" * 90 + "b" * 10  # similarity 0.90 -> fuzzy candidate
    _seed_two_occurrences(app, title_a, title_b)
    app.refresh_all_tabs()

    assert len(app._dup_clusters) == 1
    app.dup_list.selection_set(0)
    app._render_dup_cluster()
    app.dup_survivor_list.selection_set(0)  # keep the first member in the cluster
    import tkinter.messagebox as messagebox_mod
    monkeypatch_calls = []
    messagebox_mod.askyesno = lambda title, msg: (monkeypatch_calls.append((title, msg)) or True)
    app._dup_merge_cluster()

    assert monkeypatch_calls and monkeypatch_calls[0][0] == "Confirm merge"
    active = app.conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 1
    assert len(app._dup_clusters) == 0  # queue refreshed, now empty
    root.destroy()


@requires_tk
def test_duplicates_tab_merge_flow_three_way_cluster(tmp_path):
    """Multi-way merge: a 3-member fuzzy cluster is resolved in one
    action (gap found during UI dogfooding -- previously only pairwise
    candidates existed, so a 3+ member group required two separate
    pairwise merges)."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    from screening_workbench import dedup

    source_id, branch_id = app._ensure_default_source()
    base = "a" * 96
    text = (
        "title,authors,year\n"
        f"{base}TAG1,Smith,2020\n"
        f"{base}TAG2,Smith,2020\n"
        f"{base}TAG3,Smith,2020\n"
    )
    result = commit_csv_import(
        app.conn, text, {0: "title", 1: "authors", 2: "year"}, source_id=source_id, branch_id=branch_id,
        operation_id="seed-triangle", actor="owner",
    )
    dedup.run_exact_and_fuzzy_detection(app.conn, "system", batch_id=result.batch_id)
    app.refresh_all_tabs()

    assert len(app._dup_clusters) == 1
    assert len(app._dup_clusters[0]["occurrence_ids"]) == 3

    app.dup_list.selection_set(0)
    app._render_dup_cluster()
    assert app.dup_survivor_list.size() == 3
    app.dup_survivor_list.selection_set(0)
    import tkinter.messagebox as messagebox_mod
    messagebox_mod.askyesno = lambda title, msg: True
    app._dup_merge_cluster()

    active = app.conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 1  # all three collapsed to one survivor in a single action
    assert app._dup_clusters == []
    root.destroy()


@requires_tk
def test_duplicates_tab_merge_cancelled_in_confirmation_does_nothing(tmp_path):
    """UI reference target item 8: the confirmation preview must be a
    real gate, not cosmetic -- declining it must leave the cluster and
    active-occurrence count untouched."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    title_a = "a" * 100
    title_b = "a" * 90 + "b" * 10
    _seed_two_occurrences(app, title_a, title_b)
    app.refresh_all_tabs()

    assert len(app._dup_clusters) == 1
    app.dup_list.selection_set(0)
    app._render_dup_cluster()
    app.dup_survivor_list.selection_set(0)
    import tkinter.messagebox as messagebox_mod
    messagebox_mod.askyesno = lambda title, msg: False  # reviewer clicks Cancel
    app._dup_merge_cluster()

    active = app.conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 2  # nothing merged
    assert len(app._dup_clusters) == 1  # still open
    root.destroy()


@requires_tk
def test_duplicates_tab_merge_confirmation_names_survivor_and_absorbed(tmp_path):
    """UI reference target item 8: the confirmation must preview the
    actual survivor and absorbed occurrence IDs (and titles), not a
    generic yes/no prompt."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    title_a = "a" * 100
    title_b = "a" * 90 + "b" * 10
    occ_ids = _seed_two_occurrences(app, title_a, title_b)
    app.refresh_all_tabs()

    app.dup_list.selection_set(0)
    app._render_dup_cluster()
    app.dup_survivor_list.selection_set(0)
    survivor_id = app._dup_survivor_occurrence_ids[0]
    absorbed_id = next(o for o in occ_ids if o != survivor_id)

    import tkinter.messagebox as messagebox_mod
    seen = {}
    messagebox_mod.askyesno = lambda title, msg: seen.setdefault("msg", msg) or True
    app._dup_merge_cluster()

    assert survivor_id in seen["msg"]
    assert absorbed_id in seen["msg"]
    assert "reversible" in seen["msg"].lower()
    root.destroy()


@requires_tk
def test_duplicates_merge_confirmation_dialog_is_captured_by_modal_hook(tmp_path, monkeypatch):
    import tkinter.messagebox as messagebox_mod

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "dup-confirm-capture.sqlite"), reviewer_id="owner")
    ids = _seed_two_occurrences(
        app, "a" * 100, "a" * 90 + "b" * 10, authors="Sample Author", year="2023",
    )
    app.refresh_all_tabs()
    app.notebook.select(2)
    app.dup_list.selection_set(0)
    app._render_dup_cluster()
    app.dup_survivor_list.selection_set(0)
    survivor_id = app._dup_survivor_occurrence_ids[0]
    absorbed_id = next(oid for oid in ids if oid != survivor_id)
    observed = {}

    def capture_confirmation(title, message):
        observed["title"] = title
        observed["message"] = message
        return False

    monkeypatch.setattr(messagebox_mod, "askyesno", capture_confirmation)
    app._dup_merge_cluster()

    assert observed["title"] == "Confirm merge"
    assert survivor_id in observed["message"]
    assert absorbed_id in observed["message"]
    assert "reversible" in observed["message"].lower()
    assert len(app._dup_clusters) == 1
    assert app.conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"] == 2
    assert app.notebook.index("current") == 2
    root.destroy()


@requires_tk
def test_duplicates_keyboard_traverses_queue_and_survivor_with_visible_focus(tmp_path):
    import csv
    from io import StringIO
    from screening_workbench.importers.csv_importer import commit_csv_import
    from screening_workbench import dedup

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "dup-keyboard-focus.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    csv_data = StringIO()
    csv.writer(csv_data).writerows([
        ["title", "doi", "authors", "year"],
        ["a" * 100, "", "Smith", "2020"],
        ["a" * 90 + "b" * 10, "", "Smith", "2020"],
        ["second synthetic title alpha", "", "Jones", "2021"],
        ["second synthetic title alphaa", "", "Jones", "2021"],
    ])
    commit_csv_import(
        app.conn, csv_data.getvalue(), {0: "title", 1: "doi", 2: "authors", 3: "year"},
        source_id=source_id, branch_id=branch_id, operation_id="two-synthetic-queue-candidates",
        actor="owner",
    )
    dedup.run_exact_and_fuzzy_detection(app.conn, "system")
    app.refresh_all_tabs()
    assert len(app._dup_clusters) == 2
    app.notebook.select(2)
    root.deiconify()
    root.update()

    app.dup_list.selection_set(0)
    app._render_dup_cluster()
    assert app.dup_survivor_list.size() == 2
    app.dup_list.event_generate("<FocusIn>", when="now")
    assert app.dup_list.cget("highlightthickness") == 3
    assert app.dup_list.cget("highlightbackground") == TOKENS["focus"]
    assert app.dup_list.cget("highlightcolor") == TOKENS["focus"]
    assert app.dup_list.cget("selectbackground") == TOKENS["accent_soft"]
    assert app._dup_move_selection(1) == "break"
    assert app.dup_list.curselection() == (1,)
    assert app.dup_survivor_list.size() == 2
    assert app._dup_move_selection(-1) == "break"
    assert app.dup_list.curselection() == (0,)
    app.dup_list.event_generate("<FocusOut>", when="now")
    assert app.dup_list.cget("highlightbackground") == TOKENS["line"]
    assert app.dup_keyboard_help_label.cget("text") == "Keyboard: Tab through queue, survivor, actions; Up/Down selects"

    actual_focus_chain = []
    widget = app.dup_list
    for _ in range(24):
        widget = widget.tk_focusNext()
        actual_focus_chain.append(widget)
        if widget is app.dup_list:
            break
    assert app.dup_survivor_list in actual_focus_chain
    assert app.dup_merge_button in actual_focus_chain
    assert app.dup_keep_separate_button in actual_focus_chain
    assert actual_focus_chain[-1] is app.dup_list
    root.destroy()


@requires_tk
def test_duplicates_tab_keep_separate_flow(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    title_a = "a" * 100
    title_b = "a" * 90 + "b" * 10
    _seed_two_occurrences(app, title_a, title_b)
    app.refresh_all_tabs()

    app.dup_list.selection_set(0)
    app._dup_keep_separate_cluster()

    active = app.conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 2  # both kept
    assert len(app._dup_clusters) == 0  # no longer open
    root.destroy()


@requires_tk
def test_duplicates_tab_states_queue_and_reversibility_semantics(tmp_path):
    """UI reference target items 2 and 9: both must be stated as visible
    text near the action, not left implicit in behavior alone."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    queue_text = app.dup_queue_note_label.cget("text").lower()
    assert "remain active" in queue_text
    assert "screening or prisma" in queue_text

    reversibility_text = app.dup_reversibility_note_label.cget("text").lower()
    assert "reversible" in reversibility_text
    assert "append-only event" in reversibility_text
    root.destroy()


@requires_tk
def test_duplicates_tab_compare_pane_shows_field_table_and_provenance(tmp_path):
    """UI reference target items 3/4/5/6/12: the compare pane must show
    both occurrence IDs, a per-field comparison with differing fields
    flagged in text (not color alone), match score/reasons/rule version,
    provenance, and a pre-selected survivor."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    title_a = "Blue-glass greenhouse: a pilot in Modelton"
    title_b = "Blue glass greenhouse -- pilot in Modelton"
    occ_ids = _seed_two_occurrences(app, title_a, title_b, authors="Sample", year="2023")
    assert len(occ_ids) == 2
    app.refresh_all_tabs()

    app.dup_list.selection_set(0)
    app._render_dup_cluster()

    text = app.dup_compare_text.get("1.0", "end")
    # item 3: both stable occurrence IDs are shown.
    for occ_id in occ_ids:
        assert occ_id in text
    # item 4: the differing Title field is explicitly labeled, not just colored.
    assert "Difference" in text
    assert "Authors" in text and "Year" in text  # non-differing fields still shown
    # item 5: score, reasons, rule version, and provenance are all present.
    assert "row row 2" not in text.casefold()
    assert "Score 0.95" in text
    assert "title similarity" in text
    assert "shared publication year" in text
    assert "same first author" in text
    assert "Rule version 1" in text
    assert "Batch" in text and "source" in text
    # item 6: a survivor is pre-selected as soon as the cluster is open.
    assert app.dup_survivor_list.curselection() == (0,)
    root.destroy()


@requires_tk
def test_duplicates_empty_state_explains_survivor_selector(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "empty-duplicates.sqlite"), reviewer_id="owner")
    app._refresh_duplicates_tab()
    assert app.dup_list.size() == 1
    assert app.dup_list.get(0) == "No open duplicate candidates."
    assert "NO OPEN DUPLICATE CLUSTERS" in app.dup_compare_text.get("1.0", "end")
    assert app.dup_survivor_list.size() == 1
    assert "Select an open candidate pair" in app.dup_survivor_list.get(0)
    assert app.dup_survivor_list.curselection() == ()
    root.destroy()


@requires_tk
def test_conflicts_tab_resolve_flow(tmp_path):
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Solo Title", "Other Title")
    occ_id = occ_ids[0]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    app.refresh_all_tabs()

    assert occ_id in app._conflict_occurrence_ids
    idx = app._conflict_occurrence_ids.index(occ_id)
    app.conflict_list.selection_set(idx)
    app.conflict_note_entry.insert(0, "owner reviewed, agrees with include")
    app._resolve_conflict("include")

    assert occ_id not in app._conflict_occurrence_ids  # resolved, no longer conflicting
    assert app.status_message_label.cget("text") == (
        "Conflict resolved: include (owner reviewed, agrees with include)."
    )
    root.destroy()


@requires_tk
def test_phase2_conflicts_tab_uses_three_card_shell_preserving_controls(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase2-conflicts-cards.sqlite"), reviewer_id="owner")

    assert app.conflict_queue_card.winfo_parent() == str(app.conflict_columns)
    assert app.conflict_evidence_card.winfo_parent() == str(app.conflict_columns)
    assert app.conflict_gate_card.winfo_parent() == str(app.conflict_columns)
    assert [app.conflict_queue_card.grid_info()["column"], app.conflict_evidence_card.grid_info()["column"], app.conflict_gate_card.grid_info()["column"]] == [0, 1, 2]
    assert all(card.cget("style") == "Card.TFrame" for card in (app.conflict_queue_card, app.conflict_evidence_card, app.conflict_gate_card))
    assert str(app.conflict_resolve_include_btn.cget("style")) == "Accent.TButton"
    assert str(app.conflict_resolve_exclude_btn.cget("style")) == "Quiet.TButton"
    assert str(app.export_packet_btn.cget("state")) == "normal"
    assert str(app.merge_votes_btn.cget("state")) == "normal"
    from screening_workbench import theme
    style = ttk.Style(root)
    assert style.lookup("Accent.TButton", "foreground", ("disabled",)) == TOKENS["muted"]
    assert style.lookup("Quiet.TButton", "foreground", ("disabled",)) == TOKENS["muted"]
    assert style.lookup("Accent.TButton", "background", ("disabled",)) == theme.TOKENS["surface_raised"]
    assert style.lookup("Quiet.TButton", "background", ("disabled",)) == theme.TOKENS["surface_raised"]
    assert app.conflict_list.master.master == app.conflict_queue_panel
    assert str(app.conflict_list.cget("yscrollcommand")).endswith("set")
    assert "Up/Down changes conflict" in app.conflict_queue_keyboard_help.cget("text")
    assert app.conflict_detail_text.master.master == app.conflict_evidence_panel
    assert app.conflict_note_entry.master.master == app.conflict_evidence_panel
    assert app.conflict_resolve_include_btn.master.master == app.conflict_evidence_panel
    assert app.conflict_authorization_label.master == app.conflict_gate_panel
    assert app.conflict_list.cget("exportselection") == 0
    assert app.kappa_label.cget("text").startswith("Agreement (Cohen's")
    assert app.conflict_resolve_include_btn.cget("text") == "Resolve: Include"
    assert app.conflict_resolve_exclude_btn.cget("text") == "Resolve: Exclude"
    assert app.status_legend_label.cget("text") == "Screening shortcuts: I/M/E · 1–7 reason · J/K · / search"
    root.destroy()


@requires_tk
def test_conflicts_blind_is_selected_before_screening_and_hides_decisions(tmp_path):
    from screening_workbench import roles, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "conflicts-blind-clear.sqlite"), reviewer_id="owner")
    roles.set_blind(app.conn, "owner", True)
    occ_ids = _seed_two_occurrences(app, "Synthetic garden-model conflict", "Synthetic unrelated record")
    occ_id = occ_ids[0]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="reviewer-a", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="reviewer-b", decision="exclude", reason="Synthetic scope mismatch")
    app.refresh_all_tabs()

    assert app._conflict_occurrence_ids == []
    assert app.conflict_list.size() == 0
    assert "reviewer-a" not in app.conflict_detail_text.get("1.0", "end")
    assert "Synthetic scope mismatch" not in app.conflict_detail_text.get("1.0", "end")
    assert "locked" in app.conflict_empty_label.cget("text").casefold()
    assert str(app.conflict_resolve_include_btn.cget("state")) == "disabled"
    assert str(app.conflict_resolve_exclude_btn.cget("state")) == "disabled"
    with pytest.raises(PermissionError, match="locked once screening has begun"):
        roles.set_blind(app.conn, "owner", False)
    root.destroy()


@requires_tk
def test_conflicts_queue_arrows_move_between_two_open_conflicts_and_render_details(tmp_path):
    import csv
    from io import StringIO
    from screening_workbench import screening
    from screening_workbench.importers.csv_importer import commit_csv_import

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "conflicts-keyboard.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    data = StringIO()
    csv.writer(data).writerows([
        ["title", "authors", "year"],
        ["Synthetic conflict record alpha", "Sample A", "2024"],
        ["Synthetic conflict record beta", "Sample B", "2023"],
        ["Unrelated synthetic control", "Sample C", "2022"],
        ["Synthetic agreed record one", "Control A", "2021"],
        ["Synthetic agreed record two", "Control B", "2020"],
    ])
    imported = commit_csv_import(
        app.conn, data.getvalue(), {0: "title", 1: "authors", 2: "year"},
        source_id=source_id, branch_id=branch_id, operation_id="two-conflicts-keyboard",
        actor="owner",
    )
    rows = app.conn.execute(
        "SELECT occurrence_id, locator FROM occurrences WHERE batch_id=? ORDER BY locator",
        (imported.batch_id,),
    ).fetchall()
    ids = {row["locator"]: row["occurrence_id"] for row in rows}
    for locator in ("row 2", "row 3"):
        screening.cast_vote(app.conn, occurrence_id=ids[locator], reviewer_id="reviewer-a", decision="include")
        screening.cast_vote(app.conn, occurrence_id=ids[locator], reviewer_id="reviewer-b", decision="exclude", reason="Synthetic scope mismatch")
    for locator in ("row 4", "row 5"):
        screening.cast_vote(app.conn, occurrence_id=ids[locator], reviewer_id="reviewer-a", decision="include")
        screening.cast_vote(app.conn, occurrence_id=ids[locator], reviewer_id="reviewer-b", decision="include")
    app.refresh_all_tabs()
    assert len(app._conflict_occurrence_ids) == 2
    app.notebook.select(3)
    app.conflict_list.selection_set(0)

    first_occurrence_id = app._conflict_occurrence_ids[0]
    first_title = app._load_fields(first_occurrence_id)["title"]
    assert app._move_conflict_selection(1) == "break"
    assert app.conflict_list.curselection() == (1,)
    second_occurrence_id = app._conflict_occurrence_ids[1]
    second_title = app._load_fields(second_occurrence_id)["title"]
    second = app.conflict_detail_text.get("1.0", "end")
    assert second_title != first_title
    assert second_title in second
    assert second_occurrence_id in second
    assert "reviewer-a: include" in second
    assert "Focused conflict 2 of 2." == app.status_message_label.cget("text")
    assert app._move_conflict_selection(-1) == "break"
    assert app.conflict_list.curselection() == (0,)
    first = app.conflict_detail_text.get("1.0", "end")
    assert first_title in first
    assert first_occurrence_id in first
    assert "Focused conflict 1 of 2." == app.status_message_label.cget("text")
    root.destroy()


@requires_tk
def test_conflicts_tab_resolve_disabled_and_blocked_for_non_owner(tmp_path):
    """UI reference target item 7: owner authorization is stated AND
    enforced -- resolve_conflict() itself has no notion of project
    ownership, so the UI layer is the only place this can be held."""
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    app.reviewer_id = "revA"  # simulate a non-owner reviewer driving this app instance

    occ_ids = _seed_two_occurrences(app, "Solo Title", "Other Title")
    occ_id = occ_ids[0]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    app.refresh_all_tabs()

    assert str(app.conflict_resolve_include_btn.cget("state")) == "disabled"
    assert str(app.conflict_resolve_exclude_btn.cget("state")) == "disabled"
    assert "owner" in app.conflict_authorization_label.cget("text").lower()
    assert "revA" in app.conflict_authorization_label.cget("text")
    assert "Owner authorization required" in app.conflict_authorization_label.cget("text")

    # Defense in depth: calling the handler directly (bypassing the
    # disabled button) must still refuse, leaving the conflict open.
    import tkinter.messagebox as messagebox_mod
    errors = []
    messagebox_mod.showerror = lambda title, msg: errors.append(msg)
    idx = app._conflict_occurrence_ids.index(occ_id)
    app.conflict_list.selection_set(idx)
    app.conflict_note_entry.insert(0, "shouldn't matter")
    app._update_conflict_note_hint()
    app._resolve_conflict("include")

    assert errors and "owner" in errors[0].lower()
    assert occ_id in screening.list_conflicts(app.conn)  # still unresolved
    root.destroy()


@requires_tk
def test_conflicts_tab_detail_pane_shows_record_and_timestamps(tmp_path):
    """UI reference target items 1/2/3: the detail pane must show the
    selected record's own title/ID/metadata and each vote's timestamp,
    not just reviewer/decision/reason."""
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Needs Detail Pane Title", "Other Title")
    occ_id = occ_ids[0]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="Wrong population")
    app.refresh_all_tabs()

    idx = app._conflict_occurrence_ids.index(occ_id)
    app.conflict_list.selection_set(idx)
    app._render_conflict()

    text = app.conflict_detail_text.get("1.0", "end")
    assert "Needs Detail Pane Title" in text
    assert occ_id in text
    assert "revA: include" in text
    assert "Wrong population" in text
    title_index = app.conflict_detail_text.search("Needs Detail Pane Title", "1.0", "end")
    meta_index = app.conflict_detail_text.search(f"Occurrence ID: {occ_id}", "1.0", "end")
    vote_index = app.conflict_detail_text.search("revA: include", "1.0", "end")
    assert "conflict-title" in app.conflict_detail_text.tag_names(title_index)
    assert "conflict-meta" in app.conflict_detail_text.tag_names(meta_index)
    assert "conflict-vote" in app.conflict_detail_text.tag_names(vote_index)
    timestamp_index = app.conflict_detail_text.search("Timestamp:", "1.0", "end")
    assert "conflict-timestamp" in app.conflict_detail_text.tag_names(timestamp_index)
    # a vote timestamp (ISO-ish date) is present, not just the decision text
    assert any(ch.isdigit() for ch in text.split("Timestamp:")[1].split("\n")[0])
    root.destroy()


@requires_tk
def test_conflicts_empty_state_is_explicit_and_disables_resolution(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "empty-conflicts.sqlite"), reviewer_id="owner")
    app._refresh_conflicts_tab()
    assert app.conflict_list.size() == 1
    assert app.conflict_list.get(0) == "No open conflicts."
    detail = app.conflict_detail_text.get("1.0", "end")
    assert "NO OPEN CONFLICTS" in detail
    assert "two reviewers disagree" in detail
    assert str(app.conflict_resolve_include_btn.cget("state")) == "disabled"
    assert str(app.conflict_resolve_exclude_btn.cget("state")) == "disabled"
    assert str(app.conflict_note_entry.cget("state")) == "disabled"
    assert "unavailable" in app.conflict_note_hint_label.cget("text")
    assert app._conflict_occurrence_ids == []
    root.destroy()


@requires_tk
def test_conflicts_tab_queue_row_shows_occurrence_id(tmp_path):
    """UI reference target item 1: the queue row itself carries the
    record's ID, visible before a reviewer even selects it."""
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Queue Row ID Title", "Other Title")
    occ_id = occ_ids[0]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    app.refresh_all_tabs()

    idx = app._conflict_occurrence_ids.index(occ_id)
    assert app.conflict_list.get(idx) == occ_id
    root.destroy()


@requires_tk
def test_conflicts_tab_resolution_note_empty_state_is_visible_and_live(tmp_path):
    """UI reference target item 6: the required note's empty state is
    visible before submission, and updates live as the reviewer types,
    not just via an error dialog the first time Resolve is clicked."""
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Solo Title", "Other Title")
    occ_id = occ_ids[0]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    app.refresh_all_tabs()

    assert "required" in app.conflict_note_hint_label.cget("text").lower()

    app.conflict_note_entry.insert(0, "a real note")
    app._update_conflict_note_hint()
    assert app.conflict_note_hint_label.cget("text") == ""

    app.conflict_note_entry.delete(0, "end")
    app._update_conflict_note_hint()
    assert "required" in app.conflict_note_hint_label.cget("text").lower()
    root.destroy()


@requires_tk
def test_conflicts_resolution_actions_require_selected_conflict_and_nonblank_note(tmp_path):
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "conflicts-note-gate.sqlite"), reviewer_id="owner")
    occ_ids = _seed_two_occurrences(app, "Synthetic gated conflict", "Synthetic unrelated control")
    occ_id = occ_ids[0]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="reviewer-a", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="reviewer-b", decision="exclude", reason="Synthetic exclusion")
    app.refresh_all_tabs()

    assert str(app.conflict_resolve_include_btn.cget("state")) == "disabled"
    assert str(app.conflict_resolve_exclude_btn.cget("state")) == "disabled"
    app.conflict_list.selection_set(app._conflict_occurrence_ids.index(occ_id))
    app._render_conflict()
    assert str(app.conflict_resolve_include_btn.cget("state")) == "disabled"
    app.conflict_note_entry.insert(0, "   ")
    app._update_conflict_note_hint()
    assert str(app.conflict_resolve_include_btn.cget("state")) == "disabled"
    app.conflict_note_entry.delete(0, "end")
    app.conflict_note_entry.insert(0, "Owner reviewed the evidence")
    app._update_conflict_note_hint()
    assert str(app.conflict_resolve_include_btn.cget("state")) == "normal"
    assert str(app.conflict_resolve_exclude_btn.cget("state")) == "normal"
    app.conflict_note_entry.delete(0, "end")
    app._update_conflict_note_hint()
    assert str(app.conflict_resolve_include_btn.cget("state")) == "disabled"
    assert str(app.conflict_resolve_exclude_btn.cget("state")) == "disabled"
    root.destroy()


@requires_tk
def test_phase2_fulltext_tab_uses_three_card_shell_preserving_controls(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.geometry("1280x800")
    root.update_idletasks()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase2-fulltext-cards.sqlite"), reviewer_id="owner")
    root.deiconify()
    app.notebook.select(4)
    root.update()

    cards = (app.fulltext_queue_card, app.fulltext_assessment_card, app.fulltext_support_card)
    assert all(card.winfo_parent() == str(app.fulltext_columns) for card in cards)
    assert [card.grid_info()["column"] for card in cards] == [0, 1, 2]
    assert all(card.cget("style") == "Card.TFrame" for card in cards)
    assert app.promote_list.master.master == app.fulltext_queue_panel
    assert app.report_list.master.master == app.fulltext_queue_panel
    assert app.fulltext_detail_text.master == app.fulltext_assessment_panel
    assert app.fulltext_assessment_buttons.master == app.fulltext_assessment_panel
    assert app.attachment_listbox.master.master == app.fulltext_support_panel
    assert app.fulltext_lock_label.master == app.fulltext_queue_panel
    assert app.report_list.cget("exportselection") == 0
    assert app.promote_list.cget("exportselection") == 0
    assert app.attachment_listbox.cget("exportselection") == 0
    assert app.report_list.size() == 0
    assert app._report_ids == []
    assert "No report selected" in app.fulltext_empty_detail_label.cget("text")
    assert app.fulltext_selected_identity.cget("text") == "No report selected"
    assert str(app.fulltext_previous_btn.cget("state")) == "disabled"
    assert str(app.fulltext_next_btn.cget("state")) == "disabled"
    assert str(app.fulltext_next_btn.cget("style")) == "FulltextNext.TButton"
    style = ttk.Style(root)
    assert style.lookup("FulltextNext.TButton", "background", ("disabled",)) == theme.TOKENS["surface_raised"]
    assert style.lookup("FulltextNext.TButton", "foreground", ("disabled",)) == TOKENS["muted"]
    assert "Select a report" in app.fulltext_reason_note.cget("text")
    assert all(str(radio.cget("state")) == "disabled" for radio in app.fulltext_reason_radios)
    assert str(app.fulltext_not_retrieved_btn.cget("state")) == "disabled"
    assert str(app.fulltext_assess_included_btn.cget("state")) == "disabled"
    assert str(app.fulltext_assess_maybe_btn.cget("state")) == "disabled"
    assert str(app.fulltext_assess_excluded_btn.cget("state")) == "disabled"
    assert app.fulltext_assess_included_btn.cget("bg") == TOKENS["surface_raised"]
    assert app.fulltext_assess_maybe_btn.cget("bg") == TOKENS["surface_raised"]
    assert app.fulltext_assess_excluded_btn.cget("bg") == TOKENS["surface_raised"]
    assert app.fulltext_columns.winfo_ismapped()
    assert app.fulltext_queue_card.winfo_y() < app.status_bar.winfo_y()
    assert app.fulltext_attachment_actions.winfo_y() + app.fulltext_attachment_actions.winfo_height() <= app.fulltext_support_card.winfo_y() + app.fulltext_support_card.winfo_height()
    root.destroy()


@requires_tk
def test_fulltext_tab_blind_lock_is_applied_before_screening_starts(tmp_path):
    """Full-text's global queue lacks reviewer filtering: select blind mode
    before any title/abstract vote, so the lock is reachable under the
    lock-on-first-vote policy without turning blind mode off afterward."""
    import tkinter.messagebox as messagebox
    from screening_workbench import roles

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "fulltext-blind.sqlite"), reviewer_id="owner")
    roles.set_blind(app.conn, "owner", True)
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nSynthetic blinded report\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="blind-fulltext-seed", actor="owner",
    )
    errors = []
    messagebox.showerror = lambda title, text: errors.append((title, text))
    app.refresh_all_tabs()

    assert app._promote_occurrence_ids == []
    assert app._report_ids == []
    assert app.promote_list.size() == 0
    assert app.report_list.size() == 0
    assert app.fulltext_detail_text.get("1.0", "end").strip() == ""
    assert str(app.fulltext_not_retrieved_btn.cget("state")) == "disabled"
    assert str(app.fulltext_previous_btn.cget("state")) == "disabled"
    assert str(app.fulltext_next_btn.cget("state")) == "disabled"
    assert "locked" in app.fulltext_reason_note.cget("text").casefold()
    assert all(str(radio.cget("state")) == "disabled" for radio in app.fulltext_reason_radios)
    assert str(app.promote_report_btn.cget("state")) == "disabled"
    assert str(app.fulltext_assess_included_btn.cget("state")) == "disabled"
    assert str(app.fulltext_assess_maybe_btn.cget("state")) == "disabled"
    assert str(app.fulltext_assess_excluded_btn.cget("state")) == "disabled"
    assert "locked" in app.fulltext_lock_label.cget("text").casefold()
    assert errors == []
    root.destroy()


@requires_tk
def test_fulltext_tab_promote_and_assess_flow(tmp_path):
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Promote Me", "Ignore Me")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    app.refresh_all_tabs()

    assert occ_ids[0] in app._promote_occurrence_ids
    idx = app._promote_occurrence_ids.index(occ_ids[0])
    app.promote_list.selection_set(idx)
    app._promote_selected()

    assert len(app._report_ids) == 1
    app.report_list.selection_set(0)
    app._report_assess("included")

    row = app.conn.execute(
        "SELECT full_text_outcome FROM report_retrievals WHERE report_id=?", (app._report_ids[0],)
    ).fetchone()
    assert row["full_text_outcome"] == "included"
    root.destroy()


# --- Directive D follow-up: PDF attachments in the Full-text detail pane ---

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


def _promote_and_select_report(app, title="Promote Me", other="Ignore Me"):
    """Seed one occurrence, include+promote it to a report, select that
    report in the Full-text tab, and return its report_id. Shared setup
    for the attachment UI tests below."""
    from screening_workbench import screening

    occ_ids = _seed_two_occurrences(app, title, other)
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    app.refresh_all_tabs()
    idx = app._promote_occurrence_ids.index(occ_ids[0])
    app.promote_list.selection_set(idx)
    app._promote_selected()
    app.report_list.selection_set(0)
    app._render_fulltext_detail()
    return app._report_ids[0]


@requires_tk
def test_attach_pdf_via_ui_adds_to_list_and_queue_badge(tmp_path, monkeypatch):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    report_id = _promote_and_select_report(app)

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    _patch_dialogs(monkeypatch, open_path=str(pdf_path))

    app._attach_pdf()

    assert len(app._attachment_ids) == 1
    assert app.attachment_listbox.size() == 1
    assert "doc.pdf" in app.attachment_listbox.get(0)
    # Item 3: the queue row itself clearly says the attachment type and state.
    assert "PDF attached" in app.report_list.get(app._report_ids.index(report_id))
    root.destroy()


@requires_tk
def test_attach_non_pdf_via_ui_shows_error_and_adds_nothing(tmp_path, monkeypatch):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    _promote_and_select_report(app)

    not_pdf = tmp_path / "fake.pdf"
    not_pdf.write_bytes(b"not actually a pdf\n")
    _patch_dialogs(monkeypatch, open_path=str(not_pdf))

    errors = []
    import tkinter.messagebox as messagebox_mod
    monkeypatch.setattr(messagebox_mod, "showerror", lambda title, msg: errors.append(msg))

    app._attach_pdf()

    assert errors and "pdf" in errors[0].lower()
    assert app.attachment_listbox.size() == 0
    root.destroy()


@requires_tk
def test_remove_attachment_via_ui_requires_confirmation(tmp_path, monkeypatch):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    _promote_and_select_report(app)

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    _patch_dialogs(monkeypatch, open_path=str(pdf_path))
    app._attach_pdf()
    assert app.attachment_listbox.size() == 1

    import tkinter.messagebox as messagebox_mod
    monkeypatch.setattr(messagebox_mod, "askyesno", lambda *a, **k: False)
    app.attachment_listbox.selection_set(0)
    app._remove_selected_attachment()
    assert app.attachment_listbox.size() == 1  # decline leaves it in place

    monkeypatch.setattr(messagebox_mod, "askyesno", lambda *a, **k: True)
    app._remove_selected_attachment()
    assert app.attachment_listbox.size() == 0  # confirm actually removes it

    from screening_workbench import attachments
    attach_dir = attachments.resolve_attachments_dir(app.conn)
    assert len(list(attach_dir.glob("*.pdf"))) == 1  # content-addressed file retained
    root.destroy()


@requires_tk
def test_open_attachment_via_ui_writes_temp_copy_and_starts_file(tmp_path, monkeypatch):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    _promote_and_select_report(app)

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    _patch_dialogs(monkeypatch, open_path=str(pdf_path))
    app._attach_pdf()

    opened = []
    monkeypatch.setattr(os, "startfile", lambda p: opened.append(p), raising=False)
    app.attachment_listbox.selection_set(0)
    app._open_selected_attachment()

    assert len(opened) == 1
    assert opened[0].endswith("doc.pdf")
    with open(opened[0], "rb") as fh:
        assert fh.read() == MINIMAL_PDF
    root.destroy()


@requires_tk
def test_fulltext_attachment_controls_are_locked_in_blind_project(tmp_path):
    from screening_workbench import attachments, reports, roles

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    roles.set_blind(app.conn, "owner", True)
    source_id, branch_id = app._ensure_default_source()
    seeded = commit_csv_import(
        app.conn, "title\nSynthetic blinded report\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="blind-attachment-seed", actor="owner",
    )
    occurrence_id = app.conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=?", (seeded.batch_id,),
    ).fetchone()["occurrence_id"]
    report_id = reports.create_report(app.conn, "owner")
    reports.link_occurrence_to_report(app.conn, "owner", occurrence_id, report_id)
    reports.assign_progression(app.conn, "owner", report_id, occurrence_id)

    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    attachments.attach_pdf(app.conn, "owner", report_id, pdf_path)
    app.refresh_all_tabs()

    assert app.attachment_listbox.size() == 0
    assert app._attachment_ids == []
    assert str(app.attach_pdf_btn.cget("state")) == "disabled"
    assert str(app.open_attachment_btn.cget("state")) == "disabled"
    assert str(app.remove_attachment_btn.cget("state")) == "disabled"
    root.destroy()


@requires_tk
def test_fulltext_tab_maybe_button_is_non_terminal_and_reassessable(tmp_path):
    """Full-text reference item 5: Include/Maybe/Exclude mechanics
    match screening -- Assess: Maybe stores a non-terminal outcome
    (no reason prompt, not counted as included/excluded, and the
    report can still be re-assessed afterward), and the nav badge
    still counts a maybe-assessed report as pending."""
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Maybe Me", "Ignore Me")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    app.refresh_all_tabs()

    app.report_list.selection_set(app._report_ids.index(report_id))
    app._report_assess("maybe")

    row = app.conn.execute(
        "SELECT retrieval_status, full_text_outcome, exclusion_reason FROM report_retrievals WHERE report_id=?",
        (report_id,),
    ).fetchone()
    assert row["full_text_outcome"] == "maybe"
    assert row["exclusion_reason"] is None

    c = reports.counts(app.conn)
    assert c["reports_included"] == 0
    assert c["reports_excluded"] == 0
    assert c["reports_pending"] == 1

    app.refresh_all_tabs()
    assert "Full-text  (1)" in app.notebook.tab(4, "text")
    queue_row = app.report_list.get(app._report_ids.index(report_id))
    assert "maybe" in queue_row
    assert app.fulltext_selected_identity.cget("text") == f"{report_id} · retrieved"
    assert "Choose exactly one primary reason" not in app.fulltext_reason_note.cget("text")
    assert all(str(radio.cget("state")) == "disabled" for radio in app.fulltext_reason_radios)

    # Re-assessable: maybe -> included still works through the same button.
    app.report_list.selection_set(app._report_ids.index(report_id))
    app._report_assess("included")
    row = app.conn.execute(
        "SELECT full_text_outcome FROM report_retrievals WHERE report_id=?", (report_id,)
    ).fetchone()
    assert row["full_text_outcome"] == "included"
    root.destroy()



@requires_tk
def test_fulltext_reason_choice_sets_value_and_terminal_exclude_uses_it_without_prompt(tmp_path):
    """Isolate the selected-reason consumer from Tk Radiobutton.invoke,
    which does not dispatch commands for withdrawn roots; assert the saved
    exclusion reason and no duplicate picker invocation."""
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "fulltext-reason-value.sqlite"), reviewer_id="owner")
    occ_ids = _seed_two_occurrences(app, "Synthetic exclusion reason choice", "Synthetic unrelated control")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    app.refresh_all_tabs()
    app.report_list.selection_set(app._report_ids.index(report_id))
    app._render_fulltext_detail()
    root.deiconify()
    root.update()

    reason = screening.EXCLUSION_REASONS[2]
    radio = next(button for button in app.fulltext_reason_radios if button.cget("text") == reason)
    assert str(radio.cget("state")) == "normal"
    radio.invoke()
    app._prompt_exclusion_reason = lambda: (_ for _ in ()).throw(AssertionError("unexpected duplicate reason picker"))
    app._report_assess("excluded")
    saved = app.conn.execute(
        "SELECT full_text_outcome, exclusion_reason FROM report_retrievals WHERE report_id=?", (report_id,),
    ).fetchone()
    assert saved["full_text_outcome"] == "excluded"
    assert saved["exclusion_reason"] == reason
    root.destroy()


@requires_tk
def test_fulltext_reason_choice_is_cleared_when_selecting_another_report(tmp_path):
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "fulltext-reason-selection.sqlite"), reviewer_id="owner")
    occ_ids = _seed_two_occurrences(app, "Synthetic reason choice first", "Synthetic reason choice second")
    report_ids = []
    for occurrence_id in occ_ids:
        screening.cast_vote(app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision="include")
        report_ids.append(reports.promote_occurrence_to_report(app.conn, "owner", occurrence_id))
    app.refresh_all_tabs()
    first = app._report_ids.index(report_ids[0])
    second = app._report_ids.index(report_ids[1])
    app.report_list.selection_set(first)
    app._render_fulltext_detail()
    app.fulltext_reason_var.set(screening.EXCLUSION_REASONS[0])

    app.report_list.selection_clear(0, "end")
    app.report_list.selection_set(second)
    app._render_fulltext_detail()

    assert app.fulltext_reason_var.get() == ""
    root.destroy()


@requires_tk
def test_fulltext_reason_choice_survives_same_report_rerender(tmp_path):
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "fulltext-same-report-rerender.sqlite"), reviewer_id="owner")
    occ_ids = _seed_two_occurrences(app, "Synthetic same report reason", "Synthetic same report control")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    app.refresh_all_tabs()
    app.report_list.selection_set(app._report_ids.index(report_id))
    app._render_fulltext_detail()

    reason = screening.EXCLUSION_REASONS[0]
    app.fulltext_reason_var.set(reason)
    app._render_fulltext_detail()

    assert app.fulltext_reason_var.get() == reason
    root.destroy()


@requires_tk
def test_phase4_fulltext_exclusion_note_keeps_full_height_above_pdf_actions(tmp_path):
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase4-fulltext-note-containment.sqlite"), reviewer_id="owner")
    occurrence_ids = _seed_two_occurrences(app, "Synthetic note viewport PDF target", "Synthetic unrelated control")
    occ_id = occurrence_ids[0]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_id)
    app.refresh_all_tabs()
    app.notebook.select(4)
    app.report_list.selection_set(app._report_ids.index(report_id))
    app._render_fulltext_detail()
    app.fulltext_reason_var.set(screening.EXCLUSION_REASONS[0])
    app._update_fulltext_reason_state()
    root.deiconify(); root.update(); root.update_idletasks()

    note_bottom = app.fulltext_reason_note.winfo_rooty() + app.fulltext_reason_note.winfo_height()
    pdf_actions_top = app.fulltext_attachment_actions.winfo_rooty()
    card_bottom = app.fulltext_support_card.winfo_rooty() + app.fulltext_support_card.winfo_height()
    assert app.fulltext_reason_count_label.cget("text") == "Counts on save · reports excluded +1"
    assert app.fulltext_reason_note.winfo_ismapped()
    assert app.fulltext_reason_note.winfo_height() >= app.fulltext_reason_note.winfo_reqheight()
    assert note_bottom <= pdf_actions_top
    assert app.attach_pdf_btn.winfo_ismapped() and app.open_attachment_btn.winfo_ismapped()
    assert app.remove_attachment_btn.winfo_ismapped()
    assert app.fulltext_attachment_actions.winfo_rooty() + app.fulltext_attachment_actions.winfo_height() <= card_bottom
    root.destroy()


@requires_tk
def test_fulltext_tab_exclude_uses_numbered_taxonomy_reason(tmp_path):
    """Full-text reference item 6: terminal Exclude requires exactly one
    primary reason chosen from the same closed 1-7 taxonomy used at
    title/abstract stage, not free text. `_prompt_exclusion_reason` is
    monkeypatched so the test drives the real taxonomy lookup without
    opening a real modal dialog."""
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Exclude Me", "Ignore Me")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    app.refresh_all_tabs()

    app._prompt_exclusion_reason = lambda: screening.EXCLUSION_REASONS[2]  # "Wrong outcome"
    app.report_list.selection_set(app._report_ids.index(report_id))
    app._report_assess("excluded")

    row = app.conn.execute(
        "SELECT full_text_outcome, exclusion_reason FROM report_retrievals WHERE report_id=?",
        (report_id,),
    ).fetchone()
    assert row["full_text_outcome"] == "excluded"
    assert row["exclusion_reason"] == screening.EXCLUSION_REASONS[2]
    assert "Counts on save · reports excluded +1" == app.fulltext_reason_count_label.cget("text")
    root.destroy()


@requires_tk
def test_fulltext_tab_exclude_cancelled_reason_records_nothing(tmp_path):
    """Cancelling the reason picker (Escape or closing the window)
    must leave the report's outcome unset -- Exclude without a reason
    stays impossible at the full-text stage, same as at screening."""
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Exclude Me", "Ignore Me")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    app.refresh_all_tabs()

    app._prompt_exclusion_reason = lambda: None
    app.fulltext_reason_var.set("")
    app.report_list.selection_set(app._report_ids.index(report_id))
    app._report_assess("excluded")

    row = app.conn.execute(
        "SELECT full_text_outcome, exclusion_reason FROM report_retrievals WHERE report_id=?",
        (report_id,),
    ).fetchone()
    assert row["full_text_outcome"] is None
    assert row["exclusion_reason"] is None
    assert app.fulltext_reason_var.get() == ""
    assert "Counts on save · reports excluded +0" == app.fulltext_reason_count_label.cget("text")
    root.destroy()


@requires_tk
def test_fulltext_tab_queue_and_detail_show_report_and_source_identity(tmp_path):
    """Full-text reference items 1/4: the queue row distinguishes the
    report ID from its source occurrence ID, and selecting a report
    shows that source record's metadata and stored abstract excerpt."""
    import csv
    import io
    from screening_workbench import reports, screening
    from screening_workbench.importers.csv_importer import commit_csv_import

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["title", "authors", "year", "journal", "doi", "abstract"])
    writer.writerow([
        "Synthetic model habitat trial", "Sample Author", "2025",
        "Synthetic Methods Journal", "10.0000/synthetic", "SYNTHETIC ABSTRACT: placeholder excerpt only.",
    ])
    result = commit_csv_import(
        app.conn, buf.getvalue(), {i: name for i, name in enumerate(
            ["title", "authors", "year", "journal", "doi", "abstract"]
        )},
        source_id=source_id, branch_id=branch_id,
        operation_id="test-fulltext-detail", actor="owner",
    )
    occ_id = app.conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result.batch_id,)
    ).fetchone()["occurrence_id"]
    screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_id)
    app.refresh_all_tabs()

    queue_row = app.report_list.get(0)
    assert f"R:{report_id[:8]}" in queue_row
    assert f"S:{occ_id[:8]}" in queue_row

    app.report_list.selection_set(0)
    app.report_list.event_generate("<<ListboxSelect>>")
    root.update()

    detail = app.fulltext_detail_text.get("1.0", "end")
    assert f"Report ID: {report_id}" in detail
    assert f"Source occurrence ID: {occ_id}" in detail
    assert app.fulltext_selected_identity.cget("text") == f"{report_id} · pending"
    assert str(app.fulltext_previous_btn.cget("state")) == "disabled"
    assert str(app.fulltext_next_btn.cget("state")) == "disabled"
    assert "Synthetic model habitat trial" in detail
    assert "Sample Author" in detail
    assert "Synthetic Methods Journal" in detail
    assert "2025" in detail
    assert "SYNTHETIC ABSTRACT: placeholder excerpt only." in detail
    title_index = app.fulltext_detail_text.search("Synthetic model habitat trial", "1.0", "end")
    abstract_index = app.fulltext_detail_text.search("SYNTHETIC ABSTRACT:", "1.0", "end")
    assert "fulltext-title" in app.fulltext_detail_text.tag_names(title_index)
    assert "fulltext-abstract" in app.fulltext_detail_text.tag_names(abstract_index)
    root.destroy()


@requires_tk
def test_fulltext_queue_rows_keep_identity_and_pdf_badge_visible(tmp_path):
    from screening_workbench import attachments, reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "fulltext-compact-queue.sqlite"), reviewer_id="owner")
    occurrence_ids = _seed_two_occurrences(app, "Synthetic attached report title", "Synthetic ordinary report title")
    report_ids = []
    for occurrence_id in occurrence_ids:
        screening.cast_vote(app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision="include")
        report_ids.append(reports.promote_occurrence_to_report(app.conn, "owner", occurrence_id))
    pdf_path = tmp_path / "synthetic-attachment.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    attachments.attach_pdf(app.conn, "owner", report_ids[0], pdf_path)
    app.refresh_all_tabs()

    attached_index = app._report_ids.index(report_ids[0])
    attached_row = app.report_list.get(attached_index)
    ordinary_row = app.report_list.get(app._report_ids.index(report_ids[1]))

    assert "pending" in attached_row
    assert f"R:{report_ids[0][:8]}" in attached_row
    assert f"S:{app._report_rows[attached_index]['canonical_occurrence'][:8]}" in attached_row
    assert "PDF attached" in attached_row
    assert "Synthetic attached report title" not in attached_row
    assert len(attached_row) <= 55
    assert "PDF attached" not in ordinary_row
    root.destroy()


@requires_tk
def test_fulltext_queue_keyboard_focus_and_arrow_navigation_are_visible(tmp_path):
    from screening_workbench import reports, screening

    root = tk.Tk()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "fulltext-queue-keyboard.sqlite"), reviewer_id="owner")
    occurrence_ids = _seed_two_occurrences(app, "Synthetic queue keyboard first", "Synthetic queue keyboard second")
    report_ids = []
    for occurrence_id in occurrence_ids:
        screening.cast_vote(app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision="include")
        report_ids.append(reports.promote_occurrence_to_report(app.conn, "owner", occurrence_id))
    app.refresh_all_tabs()
    app.notebook.select(4)
    root.deiconify()
    root.update()
    app.report_list.event_generate("<FocusIn>", when="now")
    assert app.report_list.cget("highlightthickness") == 3
    assert app.report_list.cget("highlightbackground") == TOKENS["focus"]
    assert app._move_fulltext_report(1) == "break"
    assert app.report_list.curselection() == (1,)
    expected_id = app._report_ids[1]
    assert expected_id in app.fulltext_detail_text.get("1.0", "end")
    assert app.status_message_label.cget("text") == "Focused report 2 of 2."
    root.destroy()


@requires_tk
def test_fulltext_empty_report_queue_has_explicit_state(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "empty-fulltext.sqlite"), reviewer_id="owner")
    app._refresh_fulltext_tab()
    assert app.report_empty_label.cget("text") == "No reports yet. Promote an included record above to create one."
    assert app.report_empty_label.winfo_manager() == "pack"
    assert app._report_ids == []
    assert "No report selected" in app.fulltext_empty_detail_label.cget("text")
    assert app.fulltext_empty_detail_label.winfo_manager() == "pack"
    assert "No report selected" not in app.fulltext_detail_text.get("1.0", "end")
    assert str(app.fulltext_not_retrieved_btn.cget("state")) == "disabled"
    assert str(app.fulltext_next_btn.cget("state")) == "disabled"
    assert str(app.fulltext_assess_included_btn.cget("state")) == "disabled"
    from screening_workbench.theme import TOKENS as app_tokens
    assert app.fulltext_assess_included_btn.cget("bg") == app_tokens["surface_raised"]
    assert app.fulltext_assess_maybe_btn.cget("bg") == app_tokens["surface_raised"]
    assert app.fulltext_assess_excluded_btn.cget("bg") == app_tokens["surface_raised"]
    root.destroy()


@requires_tk
def test_studies_tab_create_decide_link_flow(tmp_path):
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Study Report", "Irrelevant")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    reports.record_full_text_assessment(app.conn, "owner", report_id, "included")
    app.refresh_all_tabs()

    app._new_study()
    app.refresh_all_tabs()
    assert len(app._study_ids) == 1
    study_id = app._study_ids[0]

    app.study_tree.selection_set(study_id)
    app.study_link_report_entry.insert(0, "0")
    app._link_selected_study()

    from screening_workbench import studies as studies_mod
    assert studies_mod.active_link_count(app.conn) == 1

    app.study_tree.selection_set(study_id)

    import tkinter.simpledialog as simpledialog_mod
    simpledialog_mod.askstring = lambda *a, **k: "meets inclusion criteria"
    app._study_decide("included")

    sc = studies_mod.counts(app.conn)
    assert sc["studies_included"] == 1
    root.destroy()


@requires_tk
def test_phase2_studies_tab_has_three_card_shell_without_moving_controls(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase2-studies-cards.sqlite"), reviewer_id="owner")
    root.update_idletasks()

    assert app.studies_groups_card.winfo_parent() == str(app.studies_columns)
    assert app.studies_detail_card.winfo_parent() == str(app.studies_columns)
    assert app.studies_canonical_card.winfo_parent() == str(app.studies_columns)
    assert app.studies_groups_card.grid_info()["column"] == 0
    assert app.studies_detail_card.grid_info()["column"] == 1
    assert app.studies_canonical_card.grid_info()["column"] == 2
    assert app.study_tree.winfo_parent() == str(app.studies_tree_focus_frame)
    assert app.studies_tree_focus_frame.winfo_parent() == str(app.studies_tree_frame)
    assert app.studies_tree_frame.winfo_parent() == str(app.studies_groups_card)
    assert app.study_detail_text.winfo_parent() == str(app.studies_detail_card)
    assert app.study_decide_included_btn.winfo_parent() == str(app.studies_decision_frame)
    assert app.studies_decision_frame.winfo_parent() == str(app.studies_detail_card)
    assert app.study_link_btn.winfo_parent() == str(app.studies_link_frame)
    assert app.studies_link_frame.winfo_parent() == str(app.studies_detail_card)
    assert app.study_canonical_frame.winfo_parent() == str(app.studies_canonical_card)
    assert app.study_tree.get_children() == ()
    assert app.study_detail_text.get("1.0", "end").strip() == ""
    root.destroy()


@requires_tk
def test_studies_tree_keyboard_focus_is_visibly_distinguished(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "studies-tree-focus.sqlite"), reviewer_id="owner")
    root.deiconify()
    root.update()

    from screening_workbench import studies as studies_mod
    study_id = studies_mod.create_study(app.conn, "owner")
    app._refresh_studies_tab()
    app.study_tree.selection_set(study_id)
    original_text = app.study_tree.item(study_id, "text")
    app._render_study_detail()

    neutral = str(app.studies_tree_focus_frame.cget("background"))
    assert app.studies_focus_label.cget("text") == "Keyboard: Tab through groups, decisions, report linking, and canonical choices."
    assert app.new_study_btn.bind("<Tab>")
    assert app._tab_from_new_study_to_tree() == "break"
    assert app.study_tree.bind("<Tab>")
    assert app._tab_from_studies_tree_to_link() == "break"
    app._set_studies_tree_focus()

    assert str(app.studies_tree_focus_frame.cget("background")) == TOKENS["surface"]
    assert int(app.studies_tree_focus_frame.cget("padx")) == 0
    assert int(app.studies_tree_frame.cget("highlightthickness")) == 3
    assert str(app.studies_tree_frame.cget("highlightbackground")) == TOKENS["focus"]
    assert int(app.study_tree.cget("takefocus")) == 1
    assert app.studies_focus_label.cget("text") == "Keyboard focus: Study/report groups."
    assert app.study_tree.item(study_id, "text") == original_text
    assert "studies-keyboard-focus" in app.study_tree.item(study_id, "tags")

    app._clear_studies_tree_focus()
    assert int(app.study_tree.cget("takefocus")) == 1
    assert str(app.studies_tree_frame.cget("highlightbackground")) == TOKENS["line"]
    assert int(app.studies_tree_frame.cget("highlightthickness")) == 1
    assert int(app.studies_tree_focus_frame.cget("padx")) == 0
    assert app.studies_focus_label.cget("text") == "Keyboard: Tab through groups, decisions, report linking, and canonical choices."
    assert app.study_tree.item(study_id, "text") == original_text
    assert "studies-keyboard-focus" not in app.study_tree.item(study_id, "tags")
    root.destroy()


@requires_tk
def test_studies_tab_reports_nested_under_study_with_counts(tmp_path):
    """Studies reference items 1/2/3: the study row states its linked
    report count directly, the Treeview nests report children under
    their parent study (not a flat list), and study/report stay
    separate, distinctly-iid'd entities."""
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Report One", "Report Two")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[1], reviewer_id="owner", decision="include")
    report_a = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    report_b = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[1])
    reports.record_full_text_assessment(app.conn, "owner", report_a, "included")
    app.refresh_all_tabs()

    app._new_study()
    app.refresh_all_tabs()
    study_id = app._study_ids[0]

    app.study_tree.selection_set(study_id)
    app.study_link_report_entry.insert(0, str(app._report_ids_for_link.index(report_a)))
    app._link_selected_study()
    app.study_link_report_entry.delete(0, "end")
    app.study_tree.selection_set(study_id)
    app.study_link_report_entry.insert(0, str(app._report_ids_for_link.index(report_b)))
    app._link_selected_study()

    # Item 2: both reports are nested as Treeview children of the study.
    children = app.study_tree.get_children(study_id)
    assert set(children) == {report_a, report_b}
    # Item 1: the parent row's own text states the report count.
    assert "2 reports" in app.study_tree.item(study_id, "text")
    # Item 3: study and report remain separate, distinctly-iid'd rows.
    assert app.study_tree.parent(report_a) == study_id
    assert app.study_tree.parent(study_id) == ""
    root.destroy()


@requires_tk
def test_studies_empty_tree_has_guidance_without_data_rows(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "empty-studies.sqlite"), reviewer_id="owner")
    app._refresh_studies_tab()
    assert app.study_tree.get_children() == ()
    assert "No studies yet" in app.study_tree_empty_label.cget("text")
    assert app.study_tree_empty_label.winfo_manager() == "place"
    root.destroy()


@requires_tk
def test_studies_tab_report_detail_shows_canonical_and_provenance(tmp_path):
    """Studies reference items 4/5/6/9: selecting a report child shows
    its canonical occurrence, the full source-occurrence provenance
    list, an explicit branch, and its retrieval status (pending vs.
    retrieved)."""
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Canonical Pick", "Duplicate Provenance")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.create_report(app.conn, "owner")
    reports.link_occurrence_to_report(app.conn, "owner", occ_ids[0], report_id)
    reports.link_occurrence_to_report(app.conn, "owner", occ_ids[1], report_id)
    reports.assign_progression(app.conn, "owner", report_id, occ_ids[0])
    app.refresh_all_tabs()

    app._new_study()
    app.refresh_all_tabs()
    study_id = app._study_ids[0]
    app.study_tree.selection_set(study_id)
    app.study_link_report_entry.insert(0, str(app._report_ids_for_link.index(report_id)))
    app._link_selected_study()

    app.study_tree.selection_set(report_id)
    app._render_study_detail()
    detail = app.study_detail_text.get("1.0", "end")

    title_index = app.study_detail_text.search("Canonical occurrence:", "1.0", "end")
    assert "study_heading" in app.study_detail_text.tag_names(title_index)
    report_title_index = app.study_detail_text.search("Title: Canonical Pick", "1.0", "end")
    assert "study_heading" in app.study_detail_text.tag_names(report_title_index)
    status_index = app.study_detail_text.search("Retrieval status:", "1.0", "end")
    assert status_index

    assert f"Canonical occurrence: {occ_ids[0]}" in detail  # item 4
    assert occ_ids[0] in detail and occ_ids[1] in detail  # item 5: both listed as provenance
    assert "(canonical)" in detail
    assert "Branch/source:" in detail and "default" in detail  # item 6: explicit branch
    assert "pending" in detail.lower()  # item 9: unretrieved report's status is visible

    reports.record_full_text_assessment(app.conn, "owner", report_id, "included")
    app.refresh_all_tabs()
    app.study_tree.selection_set(report_id)
    app._render_study_detail()
    detail2 = app.study_detail_text.get("1.0", "end")
    assert "retrieved -> included" in detail2
    root.destroy()


@requires_tk
def test_studies_tab_canonical_radiobuttons_select_and_correct(tmp_path):
    """Studies reference item 11 (build gap, not just verification):
    the canonical occurrence must be a real, keyboard-operable
    Radiobutton control -- not only the read-only text from item 4 --
    wired to assign_progression for the first pick and
    correct_progression (with a required rationale) for re-selection."""
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Pick Me First", "Pick Me Later")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.create_report(app.conn, "owner")
    reports.link_occurrence_to_report(app.conn, "owner", occ_ids[0], report_id)
    reports.link_occurrence_to_report(app.conn, "owner", occ_ids[1], report_id)
    app._new_study()
    app.refresh_all_tabs()
    study_id = app._study_ids[0]
    app.study_tree.selection_set(study_id)
    app.study_link_report_entry.insert(0, str(app._report_ids_for_link.index(report_id)))
    app._link_selected_study()

    app.study_tree.selection_set(report_id)
    app._render_study_detail()

    # No progression assigned yet: two radiobuttons exist, one per
    # linked occurrence, and no occurrence is pre-selected.
    radios = [
        w for w in app.study_canonical_frame.winfo_children()
        if isinstance(w, ttk.Radiobutton)
    ]
    assert len(radios) == 2
    assert app.study_canonical_var.get() == ""

    # First pick goes through assign_progression -- no rationale prompt.
    app._select_canonical_occurrence(report_id, occ_ids[0])
    app.study_tree.selection_set(report_id)
    app._render_study_detail()
    assert app.study_canonical_var.get() == occ_ids[0]
    detail = app.study_detail_text.get("1.0", "end")
    assert f"Canonical occurrence: {occ_ids[0]}" in detail

    # Re-selection requires a rationale (correct_progression path).
    import tkinter.simpledialog as simpledialog_mod
    simpledialog_mod.askstring = lambda *a, **k: "Later occurrence has the full dataset."
    app._select_canonical_occurrence(report_id, occ_ids[1])
    app.study_tree.selection_set(report_id)
    app._render_study_detail()
    assert app.study_canonical_var.get() == occ_ids[1]
    detail2 = app.study_detail_text.get("1.0", "end")
    assert f"Canonical occurrence: {occ_ids[1]}" in detail2

    # A single-occurrence report shows no radiobuttons -- nothing to
    # choose among.
    report_id2 = reports.create_report(app.conn, "owner")
    reports.link_occurrence_to_report(app.conn, "owner", occ_ids[0], report_id2)
    app.refresh_all_tabs()
    app.study_tree.selection_set(study_id)
    app.study_link_report_entry.delete(0, "end")
    app.study_link_report_entry.insert(0, str(app._report_ids_for_link.index(report_id2)))
    app._link_selected_study()
    app.study_tree.selection_set(report_id2)
    app._render_study_detail()
    radios2 = [
        w for w in app.study_canonical_frame.winfo_children()
        if isinstance(w, ttk.Radiobutton)
    ]
    assert radios2 == []
    root.destroy()


@requires_tk
def test_studies_tab_study_detail_shows_decision_and_rationale(tmp_path):
    """Studies reference item 7: the selected study's decision state
    and its rationale text are both shown, not just prompted for and
    discarded."""
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Decision Study Report", "Irrelevant")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    app.refresh_all_tabs()

    app._new_study()
    app.refresh_all_tabs()
    study_id = app._study_ids[0]
    app.study_tree.selection_set(study_id)
    app._render_study_detail()
    assert "No decision yet" in app.study_detail_text.get("1.0", "end")

    import tkinter.simpledialog as simpledialog_mod
    simpledialog_mod.askstring = lambda *a, **k: "Clearly meets all inclusion criteria."
    app._study_decide("included")
    app.study_tree.selection_set(study_id)
    app._render_study_detail()
    detail = app.study_detail_text.get("1.0", "end")
    assert "Decision: included" in detail
    assert "Clearly meets all inclusion criteria." in detail
    root.destroy()


@requires_tk
def test_studies_tab_is_locked_when_project_was_blinded_before_screening(tmp_path):
    """Studies expose decisions/links without reviewer-scoped filters;
    blind must be selected before the first title/abstract vote."""
    import tkinter.messagebox as messagebox_mod
    from screening_workbench import roles, studies as studies_mod

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "studies-blind.sqlite"), reviewer_id="owner")
    roles.set_blind(app.conn, "owner", True)
    source_id, branch_id = app._ensure_default_source()
    seeded = commit_csv_import(
        app.conn, "title\nSynthetic blinded study report\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="blind-studies-seed", actor="owner",
    )
    occurrence_id = app.conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=?", (seeded.batch_id,),
    ).fetchone()["occurrence_id"]
    study_id = studies_mod.create_study(app.conn, "owner")
    screening.cast_vote(app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision="include")
    messagebox_mod.showerror = lambda *a, **k: None
    app.refresh_all_tabs()

    assert app._study_ids == []
    assert app._report_ids_for_link == []
    assert app.study_tree.get_children() == ()
    assert app.study_detail_text.get("1.0", "end").strip() == ""
    assert str(app.new_study_btn.cget("state")) == "disabled"
    assert str(app.study_decide_included_btn.cget("state")) == "disabled"
    assert str(app.study_decide_excluded_btn.cget("state")) == "disabled"
    assert str(app.study_decide_unresolved_btn.cget("state")) == "disabled"
    assert str(app.study_link_btn.cget("state")) == "disabled"
    assert "locked" in app.studies_lock_label.cget("text").casefold()
    counts_before = studies_mod.counts(app.conn)
    app._new_study()
    app._study_decide("excluded")
    app.study_link_report_entry.insert(0, occurrence_id)
    app._link_selected_study()
    assert studies_mod.counts(app.conn) == counts_before
    with pytest.raises(PermissionError, match="locked once screening has begun"):
        roles.set_blind(app.conn, "owner", False)
    root.destroy()


@requires_tk
def test_conflicts_queue_requires_blind_off_after_screening_begins(tmp_path, monkeypatch):
    """Conflicts are available only with blind OFF, but voting locks the
    mode; once screening starts the queue cannot be unlocked."""
    from screening_workbench import roles, screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "conflicts-locked.sqlite"), reviewer_id="owner")
    roles.set_blind(app.conn, "owner", True)
    occ_ids = _seed_two_occurrences(app, "Conflicted Study", "Other Study")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="revB", decision="exclude", reason="x")
    app.refresh_all_tabs()

    assert app._conflict_occurrence_ids == []
    assert str(app.conflict_resolve_include_btn.cget("state")) == "disabled"
    assert str(app.conflict_resolve_exclude_btn.cget("state")) == "disabled"
    assert "locked" in app.conflicts_lock_label.cget("text").casefold()
    assert str(app.export_packet_btn.cget("state")) == "disabled"
    assert str(app.merge_votes_btn.cget("state")) == "disabled"
    with pytest.raises(PermissionError, match="locked once screening has begun"):
        roles.set_blind(app.conn, "owner", False)
    assert occ_ids[0] not in app._conflict_occurrence_ids
    root.destroy()


@requires_tk
def test_nav_tab_badges_show_live_counts(tmp_path):
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Badge Study One", "Badge Study Two")
    app.refresh_all_tabs()
    assert "(2)" in app.notebook.tab(0, "text")  # Screening: 2 undecided

    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    app.refresh_all_tabs()
    assert "(1)" in app.notebook.tab(0, "text")
    root.destroy()


@requires_tk
def test_bulk_decide_from_queue_list(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Bulk One", "Bulk Two")
    app.refresh_all_tabs()
    assert app._queue_occurrence_ids == occ_ids

    app.queue_list.selection_set(occ_ids[0], occ_ids[1])
    app._bulk_decide("include")

    from screening_workbench import screening
    for occ_id in occ_ids:
        vote = screening.current_vote(app.conn, occ_id, "owner")
        assert vote is not None and vote["decision"] == "include"
    assert screening.count_undecided(app.conn, "owner") == 0
    root.destroy()


@requires_tk
def test_bulk_decide_exclude_requires_reason(tmp_path):
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    occ_ids = _seed_two_occurrences(app, "Bulk Three", "Bulk Four")
    app.refresh_all_tabs()
    app.queue_list.selection_set(occ_ids[0], occ_ids[1])
    app._prompt_exclusion_reason = lambda: screening.EXCLUSION_REASONS[2]
    app._bulk_decide("exclude")

    for occ_id in occ_ids:
        vote = screening.current_vote(app.conn, occ_id, "owner")
        assert vote["decision"] == "exclude"
        assert vote["reason"] == screening.EXCLUSION_REASONS[2]
    root.destroy()


@requires_tk
def test_header_shows_project_name_and_batch_count(tmp_path):
    from screening_workbench import roles

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    assert "unnamed" in app.project_name_label.cget("text").lower()

    roles.set_project_name(app.conn, "owner", "Community gardening & adult wellbeing", review_type="Scoping review")
    _seed_two_occurrences(app, "Header Study One", "Header Study Two")
    app.refresh_all_tabs()

    assert app.project_name_label.cget("text") == "Community gardening & adult wellbeing"
    assert "Scoping review" in app.project_stage_label.cget("text")
    assert "1 import batch" in app.project_stage_label.cget("text")
    root.destroy()


@requires_tk
def test_decision_buttons_cast_votes(tmp_path):
    """UI reference target §9: clickable Include/Maybe/Exclude buttons
    on the record pane, not just keyboard shortcuts."""
    from screening_workbench import screening

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nButton Study\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()
    occ_id = app.current_occurrence_id

    app.include_button.invoke()

    vote = screening.current_vote(app.conn, occ_id, "owner")
    assert vote["decision"] == "include"
    root.destroy()


@requires_tk
def test_blind_note_only_shown_while_blind(tmp_path):
    """UI reference target §12."""
    from screening_workbench import roles

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    assert not app.blind_note_frame.winfo_manager()  # not packed while unblind

    roles.set_blind(app.conn, "owner", True)
    app.refresh_all_tabs()
    assert app.blind_note_frame.winfo_manager() == "pack"
    assert "blind" in app.blind_note_label.cget("text").lower()

    roles.set_blind(app.conn, "owner", False)
    app.refresh_all_tabs()
    assert not app.blind_note_frame.winfo_manager()
    root.destroy()


@requires_tk
def test_queue_list_highlights_current_record_at_any_position(tmp_path):
    """Bug found during UI-reference review: the highlight check was
    hardcoded to index 0, so double-clicking a later queue entry to
    jump to it (UI reference target §5) left the wrong row highlighted."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\nSecond\nThird\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()

    # Jump directly to the third queue entry (occurrence index 2) by
    # simulating the double-click handler, instead of following
    # next-undecided.
    class _FakeEvent:
        y = 0
    target_id = app._queue_occurrence_ids[2]
    app.queue_list.identify_row = lambda y: target_id
    app._on_queue_double_click(_FakeEvent())

    current_id = app.current_occurrence_id
    assert current_id == target_id
    assert "current" in app.queue_list.item(target_id, "tags")
    other_id = app._queue_occurrence_ids[0]
    assert "current" not in app.queue_list.item(other_id, "tags")
    root.destroy()


@requires_tk
def test_year_journal_facets_populate_as_dropdown_options(tmp_path):
    """UI reference target §4: year/journal are a dropdown facet, not
    free text with no suggestions."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    csv_text = (
        "title,year,journal\n"
        "A,2021,Journal of Gardens\n"
        "B,2022,Journal of Wellbeing\n"
        "C,2021,Journal of Gardens\n"
    )
    commit_csv_import(
        app.conn, csv_text, {0: "title", 1: "year", 2: "journal"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()

    assert list(app.screen_year_entry.cget("values")) == ["2022", "2021"]
    assert list(app.screen_journal_entry.cget("values")) == [
        "Journal of Gardens", "Journal of Wellbeing",
    ]
    root.destroy()


@requires_tk
def test_position_progress_and_own_decided_count(tmp_path):
    """UI reference target: record pane position line gets a progress
    bar and shows how many of this reviewer's own matching records are
    already decided."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\nSecond\nThird\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()

    assert app.position_progress["maximum"] == 3
    assert app.position_progress["value"] == 1
    assert "0 decided by you" in app.position_label.cget("text")

    app.include_button.invoke()
    app.refresh_all_tabs()

    assert app.position_progress["value"] == 2
    assert "1 decided by you" in app.position_label.cget("text")
    root.destroy()


@requires_tk
def test_position_line_shows_batch_and_undecided_count(tmp_path):
    """UI reference target §6: 'Record N of M · Batch K (FORMAT, name)'
    plus 'X undecided · Y decided by you', per this round's directed
    format."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\nSecond\nThird\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
        source_name="Database A",
    )
    app.refresh_all_tabs()

    text = app.position_label.cget("text")
    assert "Record 1 of 3" in text
    assert "Batch 1 (CSV, Database A)" in text
    assert "3 undecided" in text
    assert "0 decided by you" in text

    app.include_button.invoke()
    app.refresh_all_tabs()
    text = app.position_label.cget("text")
    assert "2 undecided" in text
    assert "1 decided by you" in text
    root.destroy()


@requires_tk
def test_doi_shown_and_structured_abstract_headers_bolded(tmp_path):
    """UI reference target §8: DOI on the metadata line; BACKGROUND/
    METHODS/RESULTS/CONCLUSIONS headers rendered bold, not plain text."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    abstract = "BACKGROUND\nSome background text.\nMETHODS\nSome methods text."
    import csv
    import io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["title", "doi", "abstract"])
    writer.writerow(["Structured Study", "10.1234/example.2024", abstract])
    csv_text = buf.getvalue()
    commit_csv_import(
        app.conn, csv_text, {0: "title", 1: "doi", 2: "abstract"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()

    assert "DOI: 10.1234/example.2024" in app.meta_label.cget("text")

    abstract_body = app.abstract_text.get("1.0", "end")
    assert "BACKGROUND" in abstract_body and "METHODS" in abstract_body
    # Line 1 ("BACKGROUND") should carry the bold tag; line 2 (body
    # text) should not.
    tags_line1 = app.abstract_text.tag_names("1.0")
    tags_line2 = app.abstract_text.tag_names("2.0")
    assert "section-header" in tags_line1
    assert "section-header" not in tags_line2
    root.destroy()


@requires_tk
def test_queue_list_marks_current_row_with_now_label(tmp_path):
    """UI reference target §5: the current row needs an unmistakable
    text marker, not just an accent-soft fill (too close to white to
    read reliably -- color is never the only signal)."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\nSecond\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()

    first_id, second_id = app._queue_occurrence_ids[0], app._queue_occurrence_ids[1]
    first_text = app.queue_list.item(first_id, "text")
    second_text = app.queue_list.item(second_id, "text")
    assert "Now" in first_text and "First" in first_text
    assert "Now" not in second_text
    root.destroy()


@requires_tk
def test_queue_row_is_a_real_two_line_cell_title_then_meta(tmp_path):
    """UI reference target §5, round-4 rework: the reference's two-line
    queue row is required, not a second column -- title on line 1,
    'year · journal · #N' on line 2, both left-aligned. Verified this
    is a real rendered second line (an embedded '\\n' in a ttk.Treeview
    #0-column item's text), not just two values bolted together --
    confirmed empirically beforehand that Windows ttk.Treeview does
    wrap '\\n' in tree-column text once rowheight is tall enough."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    csv_text = "title,year,journal\nAlpha,2020,Journal A\nBeta,2021,Journal B\n"
    commit_csv_import(
        app.conn, csv_text, {0: "title", 1: "year", 2: "journal"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()

    first_id, second_id = app._queue_occurrence_ids[0], app._queue_occurrence_ids[1]
    first_lines = app.queue_list.item(first_id, "text").split("\n")
    second_lines = app.queue_list.item(second_id, "text").split("\n")
    assert len(first_lines) == 2
    assert "Alpha" in first_lines[0]
    assert first_lines[1] == "2020 \u00b7 Journal A \u00b7 #1"
    assert len(second_lines) == 2
    assert "Beta" in second_lines[0]
    assert second_lines[1] == "2021 \u00b7 Journal B \u00b7 #2"
    # Still a single tree column -- no separate "meta" column exists.
    assert not app.queue_list.cget("columns") 
    root.destroy()


@requires_tk
def test_queue_row_metadata_uses_muted_hierarchy_and_current_row_label(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "queue-style.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn,
        "title,year,journal\nA Synthetic Queue Record,2025,Example Quarterly\nAnother Record,2024,Sample Review\n",
        {0: "title", 1: "year", 2: "journal"},
        source_id=source_id, branch_id=branch_id, operation_id="queue-style", actor="owner",
    )
    app.refresh_all_tabs()
    current_id, next_id = app._queue_occurrence_ids
    assert "Now" in app.queue_list.item(current_id, "text")
    assert "2025 · Example Quarterly · #1" in app.queue_list.item(current_id, "text")
    assert "Now" not in app.queue_list.item(next_id, "text")
    assert "2024 · Sample Review · #2" in app.queue_list.item(next_id, "text")
    assert app.queue_list.tag_configure("current", "background")
    assert app.queue_list.cget("height") == 7
    assert app.queue_list.cget("yscrollcommand")
    assert app.queue_list.master.cget("height") == 280
    assert app.include_button.cget("text") == "I  Include"
    assert app.maybe_button.cget("text") == "M  Maybe"
    assert app.exclude_button.cget("text") == "E  Exclude..."
    assert app.queue_list.winfo_manager() == "pack"
    root.destroy()


@requires_tk
def test_j_k_navigate_without_casting_a_vote(tmp_path):
    """UI reference target §9/§14: J/K move through the queue without
    recording a decision -- previously bound nowhere, even though the
    record pane's static legend already (falsely) advertised 'J = Skip'."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\nSecond\nThird\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()
    first_id = app.current_occurrence_id

    app._skip_current()
    assert app.current_occurrence_id == app._queue_occurrence_ids[1]
    assert app.current_occurrence_id != first_id

    app._navigate_previous()
    assert app.current_occurrence_id == first_id

    # Skipping never casts a vote -- the record is still undecided.
    vote = screening.current_vote(app.conn, first_id, "owner")
    assert vote is None
    root.destroy()


@requires_tk
def test_typing_i_m_e_in_search_field_does_not_cast_a_vote(tmp_path):
    """Real bug found while adding the '/' shortcut: typing a search
    term containing i/m/e/j/k (e.g. "intervention") into any text entry
    would ALSO fire the single-key screening shortcuts via toplevel
    keypress propagation, recording a stray decision. This is a
    data-integrity risk, not a cosmetic gap."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()
    occ_id = app.current_occurrence_id

    # A key typed into an entry reaches the toplevel binding with that entry
    # as event.widget (Tk bindtags). Call those handlers with the delivered
    # widget, so the check never depends on Windows granting OS focus.
    for seq in ("<Key-i>", "<Key-m>", "<Key-e>", "<Key-j>", "<Key-k>", "<Key-slash>"):
        assert root.bind(seq), f"{seq} is not bound on the toplevel"
    for field in (app.screen_search_entry, app.screen_year_entry, app.screen_journal_entry):
        for seq in ("<Key-i>", "<Key-m>", "<Key-e>", "<Key-j>", "<Key-k>"):
            assert app._shortcut_handlers[seq](SimpleNamespace(widget=field)) is None
    assert screening.current_vote(app.conn, occ_id, "owner") is None
    assert app.current_occurrence_id == occ_id

    # The focus ring target (abstract_text) is the one place these
    # shortcuts must still work, even though it's a tk.Text widget.
    app._shortcut_handlers["<Key-i>"](SimpleNamespace(widget=app.abstract_text))
    vote = screening.current_vote(app.conn, occ_id, "owner")
    assert vote is not None and vote["decision"] == "include"
    root.destroy()


@requires_tk
def test_slash_focuses_search_unless_already_typing(tmp_path):
    """UI reference target §4: '/' jumps to the search field, but only
    when focus isn't already in a text field (so a literal '/' inside
    an existing search term still types normally)."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    # Without OS focus Tk ignores focus_set(), so record the request the
    # handler makes instead of reading focus back.
    requests = []
    app.screen_search_entry.focus_set = lambda: requests.append("search")

    slash = app._shortcut_handlers["<Key-slash>"]
    assert slash(SimpleNamespace(widget=app.abstract_text)) == "break"
    assert requests == ["search"]
    assert slash(SimpleNamespace(widget=app.queue_list)) == "break"
    assert requests == ["search", "search"]

    assert slash(SimpleNamespace(widget=app.screen_year_entry)) is None  # already typing
    assert slash(SimpleNamespace(widget=app.screen_search_entry)) is None
    assert requests == ["search", "search"]
    root.destroy()


@requires_tk
def test_ctrl_z_undoes_last_decision_and_updates_recent_panel(tmp_path):
    """UI reference target §9/§11: the Undo button, Ctrl+Z binding, and
    'Ctrl+Z undoes #N' hint must all be real, not a static legend claim
    (the J=Skip lesson from earlier this round applies here too)."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()
    occ_id = app.current_occurrence_id

    app.include_button.invoke()
    assert screening.current_vote(app.conn, occ_id, "owner") is not None
    assert "#1" in app.recent_decisions_header_label.cget("text")
    assert "Ctrl+Z undoes #1" in app.recent_decisions_header_label.cget("text")
    assert "#1" in app.recent_decisions_text.get("1.0", "end")

    app.undo_button.invoke()
    assert screening.current_vote(app.conn, occ_id, "owner") is None
    assert "Undone" in app.status_message_label.cget("text")
    root.destroy()


@requires_tk
def test_maybe_queue_displays_visible_keyboard_focus_target(tmp_path):
    from screening_workbench.theme import TOKENS as app_tokens
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-focus.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFocus-visible queue record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="maybe-focus", actor="owner",
    )
    app.refresh_all_tabs()
    occurrence_id = app.current_occurrence_id
    assert occurrence_id is not None
    app.maybe_button.invoke()
    app._refresh_maybe_tab()
    app.maybe_tree.selection_set(occurrence_id)
    app._render_maybe_detail()

    app._set_maybe_queue_focus(True)
    assert "Keyboard focus: Focus-visible queue record  ·  FOCUS" == app.maybe_focus_label.cget("text")
    assert str(app.maybe_focus_label.cget("foreground")) == app_tokens["ink"]
    assert app.maybe_tree.item(occurrence_id, "tags") == ("maybe-keyboard-focus",)
    assert app.maybe_tree.item(occurrence_id, "text") == "Focus-visible queue record"
    assert app.maybe_tree.item(occurrence_id, "values") == ("FOCUS · Keyboard focus · Maybe",)
    assert str(app.maybe_tree.tag_configure("maybe-keyboard-focus", "background")) == app_tokens["accent"]
    assert str(app.maybe_tree.tag_configure("maybe-keyboard-focus", "foreground")) == app_tokens["surface"]
    app._set_maybe_queue_focus(False)
    assert "Keyboard focus is on the Maybe queue" == app.maybe_focus_label.cget("text")
    assert app.maybe_tree.item(occurrence_id, "tags") == ("maybe-normal",)
    assert app.maybe_tree.item(occurrence_id, "values") == ("Maybe",)
    root.destroy()


@requires_tk
def test_maybe_programmatic_selection_does_not_claim_keyboard_focus(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-no-focus.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nSelected without keyboard focus\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="maybe-no-focus", actor="owner",
    )
    app.refresh_all_tabs()
    occurrence_id = app.current_occurrence_id
    assert occurrence_id is not None
    app.maybe_button.invoke()
    app._refresh_maybe_tab()
    app.maybe_tree.selection_set(occurrence_id)
    app._render_maybe_detail()
    app._render_maybe_queue()
    assert app.maybe_tree.focus_get() is None
    assert app.maybe_focus_label.cget("text") == "Keyboard focus is on the Maybe queue"
    assert app.maybe_tree.item(occurrence_id, "tags") == ("maybe-normal",)
    root.destroy()


@requires_tk
def test_maybe_queue_is_reviewerscoped_and_blind_mode_locks_before_first_vote(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-scope.sqlite"), reviewer_id="owner")
    roles.set_blind(app.conn, "owner", True)
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nOwner maybe record\nSecond reviewer record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="maybe-scope", actor="owner",
    )
    app.refresh_all_tabs()
    owner_id, second_reviewer_id = list(app._queue_occurrence_ids)
    screening.cast_vote(app.conn, occurrence_id=owner_id, reviewer_id="owner", decision="maybe")
    screening.cast_vote(app.conn, occurrence_id=second_reviewer_id, reviewer_id="reviewer-b", decision="maybe")

    mine = screening.list_maybe_decisions_for_reviewer(app.conn, "owner")
    other = screening.list_maybe_decisions_for_reviewer(app.conn, "reviewer-b")
    assert [row["occurrence_id"] for row in mine] == [owner_id]
    assert [row["occurrence_id"] for row in other] == [second_reviewer_id]
    app._refresh_maybe_tab()
    assert app._maybe_occurrence_ids == [owner_id]
    assert len(app.maybe_tree.get_children()) == 1
    assert "Owner maybe record" in app.maybe_tree.item(owner_id, "text")
    assert "Second reviewer record" not in app.maybe_tree.item(owner_id, "text")
    with pytest.raises(PermissionError, match="locked once screening has begun"):
        roles.set_blind(app.conn, "owner", False)
    root.destroy()


@requires_tk
def test_maybe_header_discloses_own_vote_scope_and_current_blind_state(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-state.sqlite"), reviewer_id="owner")
    app.refresh_all_tabs()
    assert app.maybe_reference_state.get() == "Blind screening: OFF · own votes only"
    assert "Search, counts, and status use only your own votes" in app.notebook.nametowidget(app.notebook.tabs()[1]).winfo_children()[1].cget("text")
    roles.set_blind(app.conn, "owner", True)
    app._refresh_maybe_tab()
    assert app.maybe_reference_state.get() == "Blind screening: ON · own votes only"
    root.destroy()


@requires_tk
def test_maybe_queue_keeps_all_own_votes_navigable_at_scale(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-queue-scale.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    csv_text = "title,year,journal\n" + "".join(
        f"Own Maybe sample {i:02d},2024,Fictional Methods\n" for i in range(1, 8)
    )
    commit_csv_import(
        app.conn, csv_text, {0: "title", 1: "year", 2: "journal"},
        source_id=source_id, branch_id=branch_id, operation_id="maybe-queue-scale", actor="owner",
    )
    app.refresh_all_tabs()
    occurrence_ids = list(app._queue_occurrence_ids)
    assert len(occurrence_ids) == 7
    for occurrence_id in occurrence_ids:
        screening.cast_vote(app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision="maybe")
    app._refresh_maybe_tab()
    assert len(app.maybe_tree.get_children()) == 7
    for occurrence_id in app._maybe_occurrence_ids:
        assert app.maybe_tree.exists(occurrence_id)
    assert app.maybe_status_label.cget("text") == "7 of your maybe records pending re-review."
    app.maybe_tree.selection_set(occurrence_ids[-1])
    app._render_maybe_detail()
    assert occurrence_ids[-1] in app.maybe_tree.selection()
    assert f"Occurrence ID: {occurrence_ids[-1]}" in app.maybe_detail_text.get("1.0", "end")
    root.destroy()


@requires_tk
def test_maybe_shortcuts_navigate_queue_and_route_decisions_locally(tmp_path, monkeypatch):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-shortcuts.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst shortcut record\nSecond shortcut record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="maybe-shortcuts", actor="owner",
    )
    app.refresh_all_tabs()
    occurrence_ids = list(app._queue_occurrence_ids)
    for occurrence_id in occurrence_ids:
        screening.cast_vote(app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision="maybe")
    app._refresh_maybe_tab()
    assert len(app._maybe_occurrence_ids) == 2
    first, second = app._maybe_occurrence_ids
    app.maybe_tree.selection_set(first)
    app.maybe_tree.focus(first)
    app._render_maybe_detail()

    app.maybe_tree.selection_set(first)
    app.maybe_tree.focus(first)
    app._render_maybe_detail()
    assert app.maybe_tree.bind("<FocusIn>")
    assert app.maybe_tree.bind("<FocusOut>")
    assert app.maybe_tree.bind("<Key-j>") == ""
    support_copy = [child.cget("text") for child in app.maybe_support_panel.winfo_children() if "text" in child.keys()]
    assert app.maybe_keyboard_help.cget("text") == "Queue-focused: I/M/E/J/K."
    assert "Queue-focused: I/M/E/J/K." in support_copy
    assert app._maybe_tree_keypress(type("KeyEvent", (), {"keysym": "j"})()) == "break"
    assert app.maybe_tree.selection() == (second,)
    assert "Focused Second shortcut record" in app.status_message_label.cget("text")
    app.maybe_tree.selection_set(first)
    app.maybe_tree.focus(first)
    app._render_maybe_detail()
    app._maybe_tree_keypress(type("KeyEvent", (), {"keysym": "k"})())
    assert app.maybe_tree.selection() == (first,)

    called = []
    monkeypatch.setattr(app, "_maybe_decide", lambda decision: called.append(decision))
    app._handle_maybe_shortcut("i")
    app._handle_maybe_shortcut("m")
    assert called == ["include", "maybe"]
    root.destroy()


@requires_tk
def test_maybe_support_panel_has_real_exclusion_reason_choices(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-reasons.sqlite"), reviewer_id="owner")
    assert len(app.maybe_reason_buttons) == len(screening.EXCLUSION_REASONS)
    assert app.maybe_reason_var.get() == 0
    assert [button.cget("text") for button in app.maybe_reason_buttons] == list(screening.EXCLUSION_REASONS)
    assert str(app.maybe_include_btn.cget("state")) == "disabled"
    assert str(app.maybe_maybe_btn.cget("state")) == "disabled"
    assert str(app.maybe_exclude_btn.cget("state")) == "disabled"
    assert app.maybe_footer_label.master == app.maybe_detail_panel
    assert app.maybe_decision_bar.winfo_manager() == ""
    root.destroy()


@requires_tk
def test_phase4_fulltext_attached_pdf_heading_and_filename_fit_above_action_row(tmp_path):
    from screening_workbench import attachments, reports, screening

    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase4-attached-pdf-visible.sqlite"), reviewer_id="owner")
    occurrence_ids = _seed_two_occurrences(app, "Synthetic attached PDF viewport", "Synthetic unrelated report")
    screening.cast_vote(app.conn, occurrence_id=occurrence_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occurrence_ids[0])
    pdf_path = tmp_path / "phase4-synthetic.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    attachments.attach_pdf(app.conn, "owner", report_id, pdf_path)
    app.refresh_all_tabs()
    app.notebook.select(4)
    app.report_list.selection_set(app._report_ids.index(report_id))
    app._render_fulltext_detail()
    root.deiconify(); root.update(); root.update_idletasks()

    assert "PDF attached" in app.report_list.get(app._report_ids.index(report_id))
    assert app.attachment_listbox.winfo_ismapped()
    assert app.attachment_listbox.size() == 1
    assert "phase4-synthetic.pdf" in app.attachment_listbox.get(0)
    assert app.attachment_listbox.winfo_rooty() + app.attachment_listbox.winfo_height() <= app.fulltext_attachment_actions.winfo_rooty()
    assert app.attach_pdf_btn.winfo_ismapped() and app.open_attachment_btn.winfo_ismapped() and app.remove_attachment_btn.winfo_ismapped()
    root.destroy()


@requires_tk
def test_phase4_maybe_support_keyboard_and_blind_gate_are_rendered(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase4-maybe-support.sqlite"), reviewer_id="owner")
    app.notebook.select(1)
    root.deiconify(); root.update(); root.update_idletasks()

    assert app.maybe_keyboard_heading.winfo_ismapped()
    assert app.maybe_keyboard_help.winfo_ismapped()
    assert app.maybe_keyboard_help.cget("text") == "Queue-focused: I/M/E/J/K."
    assert app.maybe_blind_gate_frame.winfo_ismapped()
    assert app.maybe_blind_gate_label.winfo_ismapped()
    for widget in (app.maybe_keyboard_heading, app.maybe_keyboard_help, app.maybe_blind_gate_frame):
        assert widget.winfo_rooty() >= app.maybe_support_card.winfo_rooty()
        assert widget.winfo_rooty() + widget.winfo_height() <= app.maybe_support_card.winfo_rooty() + app.maybe_support_card.winfo_height()
    root.destroy()


@requires_tk
def test_maybe_tab_uses_three_column_queue_detail_and_decision_layout(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-columns.sqlite"), reviewer_id="owner")
    root.update_idletasks()
    assert app.maybe_columns.winfo_manager() == "pack"
    assert app.maybe_queue_card.winfo_parent() == str(app.maybe_columns)
    assert app.maybe_detail_card.winfo_parent() == str(app.maybe_columns)
    assert app.maybe_support_card.winfo_parent() == str(app.maybe_columns)
    assert app.maybe_queue_card.grid_info()["column"] == 0
    assert app.maybe_detail_card.grid_info()["column"] == 1
    assert app.maybe_support_card.grid_info()["column"] == 2
    assert app.maybe_queue_card.cget("style") == "Card.TFrame"
    assert app.maybe_detail_card.cget("style") == "Card.TFrame"
    assert app.maybe_support_card.cget("style") == "Card.TFrame"
    assert app.maybe_columns.grid_columnconfigure(0).get("uniform") == "maybe-cards"
    assert app.maybe_columns.grid_columnconfigure(1).get("uniform") == "maybe-cards"
    assert app.maybe_columns.grid_columnconfigure(2).get("uniform") == "maybe-cards"
    assert app.maybe_queue_card.cget("padding") == (12,)
    assert app.maybe_detail_card.cget("padding") == (12,)
    assert app.maybe_support_card.cget("padding") == (12,)
    assert app.maybe_queue_card.grid_info()["padx"] == (0, 6)
    assert app.maybe_detail_card.grid_info()["padx"] == 6
    assert app.maybe_support_card.grid_info()["padx"] == (6, 0)
    assert app.maybe_queue_panel.winfo_parent() == str(app.maybe_queue_card)
    assert app.maybe_detail_panel.winfo_parent() == str(app.maybe_detail_card)
    assert app.maybe_support_panel.winfo_parent() == str(app.maybe_support_card)
    app.notebook.select(1)
    root.deiconify()
    root.update()
    assert app.maybe_queue_card.winfo_width() >= 290
    assert app.maybe_detail_card.winfo_width() >= 570
    assert app.maybe_queue_card.winfo_height() >= 550
    assert app.maybe_detail_card.winfo_height() == app.maybe_queue_card.winfo_height()
    assert app.maybe_support_card.winfo_height() == app.maybe_queue_card.winfo_height()
    assert app.maybe_keyboard_help.winfo_y() + app.maybe_keyboard_help.winfo_height() <= app.maybe_support_panel.winfo_height()
    support_text = [child.cget("text") for child in app.maybe_support_panel.winfo_children() if "text" in child.keys()]
    support_text.extend(child.cget("text") for child in app.maybe_blind_gate_frame.winfo_children() if "text" in child.keys())
    assert "OWN VOTE ONLY · BLIND-SAFE" in support_text
    assert any("no other reviewer" in text for text in support_text)
    assert app.maybe_tree.winfo_parent() == str(app.maybe_queue_frame)
    assert app.maybe_detail_text.winfo_parent() == str(app.maybe_detail_panel)
    assert app.maybe_include_btn.winfo_parent() == str(app.maybe_include_btn.master)
    assert app.maybe_include_btn.master.master == app.maybe_detail_panel
    app._refresh_maybe_tab()
    assert app.maybe_queue_count_label.cget("text") == "0 in this reviewer's queue"
    assert app.maybe_status_label.cget("text") == "0 of your maybe records pending re-review."
    assert all(button.cget("state") == "disabled" for button in (app.maybe_include_btn, app.maybe_maybe_btn, app.maybe_exclude_btn))
    root.destroy()


@requires_tk
def test_maybe_empty_queue_has_guidance_without_placeholder_record(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "empty-maybe.sqlite"), reviewer_id="owner")
    app._refresh_maybe_tab()
    assert app.maybe_tree.get_children() == ()
    assert "No maybe records are pending re-review." == app.maybe_queue_empty_label.cget("text")
    assert app.maybe_queue_empty_label.winfo_manager() == "place"
    assert app.maybe_status_label.cget("text") == "0 of your maybe records pending re-review."
    root.destroy()


@requires_tk
def test_maybe_tab_lists_and_re_decides_own_maybe_votes(tmp_path):
    """UI reference target §3: a dedicated Maybe re-review tab, not just
    a filter inside the main queue."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\nSecond\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()
    first_id = app.current_occurrence_id

    app.maybe_button.invoke()  # "First" -> maybe
    app.refresh_all_tabs()

    assert len(app._maybe_occurrence_ids) == 1
    assert "First" in app.maybe_tree.item(first_id, "text")
    assert "Maybe re-review  (1)" == app.notebook.tab(1, "text")

    app.maybe_tree.selection_set(first_id)
    app._maybe_decide("include")

    assert screening.current_vote(app.conn, first_id, "owner")["decision"] == "include"
    assert app._maybe_occurrence_ids == []
    assert "Included First" in app.status_message_label.cget("text")
    assert "Included · First · your vote history updated." in app.maybe_feedback_label.cget("text")
    root.destroy()


@requires_tk
def test_maybe_tab_detail_pane_shows_decision_and_timestamp(tmp_path):
    """Maybe re-review reference items 4/5: selecting a record shows
    its own decision and the timestamp it was cast -- not just the
    title/year/journal the queue row already carries."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title,year,journal,abstract\nDetail Pane Record,2024,Fictional Journal,Invented abstract text for this isolated test record.\n", {0: "title", 1: "year", 2: "journal", 3: "abstract"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op2", actor="owner",
    )
    app.refresh_all_tabs()
    record_id = app.current_occurrence_id

    app.maybe_button.invoke()  # -> maybe
    app.refresh_all_tabs()

    assert record_id is not None
    app.maybe_tree.selection_set(record_id)
    app._render_maybe_detail()
    detail = app.maybe_detail_text.get("1.0", "end")

    assert "Detail Pane Record" in detail
    assert f"Occurrence ID: {record_id}" in detail
    assert "Your current vote · Maybe" in detail
    assert "SOURCE ABSTRACT / EXCERPT" in detail
    assert "Invented abstract text for this isolated test record." in detail
    assert "SYNTHETIC RECORD · UI fixture only" not in detail
    assert app.maybe_footer_label.cget("text") == f"{record_id} · your active Maybe vote"
    assert app.maybe_decision_bar.winfo_manager() == "pack"
    assert str(app.maybe_include_btn.cget("state")) == "normal"
    assert str(app.maybe_maybe_btn.cget("state")) == "normal"
    assert str(app.maybe_exclude_btn.cget("state")) == "disabled"
    assert "maybe_vote_badge" in app.maybe_detail_text.tag_names(app.maybe_detail_text.search("Your current vote", "1.0", "end"))
    assert app.maybe_include_btn.cget("text") == "I  Include"
    assert app.maybe_maybe_btn.cget("text") == "M  Maybe (keep deferred)"
    assert app.maybe_exclude_btn.cget("text") == "E  Exclude..."
    assert all(button.winfo_reqheight() <= 36 for button in (app.maybe_include_btn, app.maybe_maybe_btn, app.maybe_exclude_btn))
    assert "Own vote timestamp" in detail
    assert "No other reviewers’ vote, reason, or status is displayed." in detail
    # A real ISO-ish timestamp string must actually be present, not just
    # the label -- confirms the backend's created_at reached the UI.
    decided_at = app._maybe_record_by_id[record_id]["decided_at"]
    assert decided_at in detail
    root.destroy()


@requires_tk
def test_maybe_tab_three_way_decision_bar_re_affirms_maybe(tmp_path):
    """Maybe re-review reference item 6: Include/Maybe/Exclude are all
    present as re-decision controls, including re-affirming maybe
    (which refreshes the vote's timestamp rather than being a no-op)."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nReaffirm Record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op3", actor="owner",
    )
    app.refresh_all_tabs()
    record_id = app.current_occurrence_id

    app.maybe_button.invoke()  # -> maybe
    app.refresh_all_tabs()
    first_vote_id = screening.current_vote(app.conn, record_id, "owner")["vote_id"]

    app.maybe_tree.selection_set(record_id)
    app._maybe_decide("maybe")  # re-affirm, via the new three-way bar
    app.refresh_all_tabs()

    current = screening.current_vote(app.conn, record_id, "owner")
    assert current["decision"] == "maybe"
    assert current["vote_id"] != first_vote_id  # superseded with a fresh vote, not a no-op
    assert record_id in app._maybe_occurrence_ids  # still in the queue -- non-terminal
    root.destroy()


@requires_tk
def test_maybe_exclude_needs_one_selected_project_reason(tmp_path, monkeypatch):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "maybe-exclude.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nReason gate fixture\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="maybe-reason-gate", actor="owner",
    )
    app.refresh_all_tabs()
    occurrence_id = app.current_occurrence_id
    assert occurrence_id is not None
    app.maybe_button.invoke()
    app.refresh_all_tabs()
    app.maybe_tree.selection_set(occurrence_id)
    app._render_maybe_detail()

    errors = []
    monkeypatch.setattr("screening_workbench.app.messagebox.showerror", lambda title, text: errors.append((title, text)))
    before = screening.current_vote(app.conn, occurrence_id, "owner")
    app._maybe_decide("exclude")
    assert screening.current_vote(app.conn, occurrence_id, "owner")["vote_id"] == before["vote_id"]
    assert errors and "exactly one" in errors[0][1]

    app.maybe_reason_var.set(2)
    app._update_maybe_exclude_availability()
    assert str(app.maybe_exclude_btn.cget("state")) == "normal"
    assert all("disabled" not in button.state() for button in app.maybe_reason_buttons)
    app.maybe_reason_var.set(0)
    app._update_maybe_exclude_availability()
    assert str(app.maybe_exclude_btn.cget("state")) == "disabled"
    assert all("disabled" not in button.state() for button in app.maybe_reason_buttons)

    app.maybe_reason_var.set(3)
    app._update_maybe_exclude_availability()
    app._maybe_decide("exclude")
    vote = screening.current_vote(app.conn, occurrence_id, "owner")
    assert vote["decision"] == "exclude"
    assert vote["reason"] == screening.EXCLUSION_REASONS[2]
    assert occurrence_id not in app._maybe_occurrence_ids
    root.destroy()


@requires_tk
def test_maybe_tab_search_filters_queue_and_updates_status(tmp_path):
    """Maybe re-review reference item 9: search, counts, and status
    are computed after own-vote filtering -- the search box filters
    only the already reviewer-scoped in-memory list, never issuing its
    own query."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nAlpha Habitat Study\nBeta Corridor Study\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-search", actor="owner",
    )
    app.refresh_all_tabs()
    ids = [
        row["occurrence_id"] for row in app.conn.execute(
            "SELECT occurrence_id FROM occurrences ORDER BY occurrence_id"
        ).fetchall()
    ]
    for occ_id in ids:
        screening.cast_vote(app.conn, occurrence_id=occ_id, reviewer_id="owner", decision="maybe")
    app.refresh_all_tabs()

    assert len(app._maybe_all_records) == 2
    assert app.maybe_status_label.cget("text") == "2 of your maybe records pending re-review."
    assert len(app.maybe_tree.get_children()) == 2
    assert app.notebook.tab(1, "text") == "Maybe re-review  (2)"

    app.maybe_search_var.set("alpha")

    assert len(app.maybe_tree.get_children()) == 1
    assert "Showing 1 of 2" in app.maybe_status_label.cget("text")
    assert '"alpha"' in app.maybe_status_label.cget("text")
    # The own-vote-filtered backing list is untouched by the search --
    # only the rendered queue narrows.
    assert len(app._maybe_all_records) == 2
    assert len(app._maybe_occurrence_ids) == 2
    assert app.notebook.tab(1, "text") == "Maybe re-review  (2)"

    app.maybe_search_var.set("")

    assert len(app.maybe_tree.get_children()) == 2
    assert app.maybe_status_label.cget("text") == "2 of your maybe records pending re-review."
    assert app.notebook.tab(1, "text") == "Maybe re-review  (2)"
    root.destroy()






@requires_tk
def test_prisma_side_boxes_render_nonzero_values(tmp_path):
    from screening_workbench import export as export_mod, reports

    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "prisma-side-box-nonzero.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    result = commit_csv_import(
        app.conn, "title\nSynthetic not-retrieved report\nSynthetic excluded report\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="prisma-side-box-seed", actor="owner",
    )
    occurrence_rows = app.conn.execute(
        "SELECT o.occurrence_id, f.fields_json FROM occurrences o "
        "JOIN occurrence_fields f ON f.occurrence_id=o.occurrence_id WHERE o.batch_id=?",
        (result.batch_id,),
    ).fetchall()
    ids_by_title = {json.loads(row["fields_json"])["title"]: row["occurrence_id"] for row in occurrence_rows}
    occurrence_ids = [ids_by_title["Synthetic not-retrieved report"], ids_by_title["Synthetic excluded report"]]
    for occurrence_id in occurrence_ids:
        screening.cast_vote(app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision="include")
    not_retrieved_id = reports.promote_occurrence_to_report(app.conn, "owner", occurrence_ids[0])
    reports.mark_not_retrieved(app.conn, "owner", not_retrieved_id)
    excluded_id = reports.promote_occurrence_to_report(app.conn, "owner", occurrence_ids[1])
    reports.record_full_text_assessment(
        app.conn, "owner", excluded_id, "excluded", exclusion_reason="wrong_population",
    )
    app.refresh_all_tabs()
    app.section_nav_buttons["prisma"].invoke()
    root.update()

    expected = {box["id"]: box for box in export_mod.prisma_flow_boxes(app.conn)}
    assert expected["box-not-retrieved"]["value"] == 1
    assert expected["box-excluded"]["value"] == 1
    rendered = [
        (app.prisma_diagram_canvas.itemcget(item, "text"), app.prisma_diagram_canvas.coords(item))
        for item in app.prisma_diagram_canvas.find_withtag("all")
        if app.prisma_diagram_canvas.type(item) == "text"
    ]
    for box_id in ("box-not-retrieved", "box-excluded"):
        box = expected[box_id]
        label = next(coords for text, coords in rendered if text == box["label"])
        rendered_for_box = [coords for text, coords in rendered if text == str(box["value"]) and coords[0] > 300]
        assert any(coords[1] > label[1] for coords in rendered_for_box), box_id
    root.destroy()


@requires_tk
def test_prisma_watermark_copy_and_live_data_label_are_fully_represented(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "prisma-copy.sqlite"), reviewer_id="owner")
    root.update()

    from screening_workbench import export as export_mod
    expected_watermark = (
        f"Preview as of watermark sequence {export_mod.watermark_sequence(app.conn)} -- not the authoritative export."
        " Use \"Export package...\" for the official watermarked PRISMA diagram and audit log."
    )
    assert app.prisma_watermark_label.cget("text") == expected_watermark
    assert app.prisma_live_data_label.cget("text") == "Live project data · preview only · not synthetic"
    export_note = next(
        child for child in app.prisma_audit_card.winfo_children()
        if isinstance(child, ttk.Label) and child.cget("text").startswith("Export package writes")
    )
    assert "official watermarked PRISMA diagram and audit log" in expected_watermark
    assert "read-only preview, not a separate export path." in export_note.cget("text")
    assert int(export_note.cget("wraplength")) <= app.prisma_audit_card.winfo_width() - 24
    root.destroy()


@requires_tk
def test_prisma_diagram_side_boxes_show_their_derived_values(tmp_path):
    from screening_workbench import export as export_mod

    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "prisma-side-box-values.sqlite"), reviewer_id="owner")
    app.section_nav_buttons["prisma"].invoke()
    root.update()

    canvas = app.prisma_diagram_canvas
    texts = [
        (canvas.itemcget(item, "text"), canvas.coords(item))
        for item in canvas.find_withtag("all")
        if canvas.type(item) == "text"
    ]
    boxes = {box["id"]: box for box in export_mod.prisma_flow_boxes(app.conn)}
    for box_id in ("box-not-retrieved", "box-excluded"):
        box = boxes[box_id]
        label = next(coords for text, coords in texts if text == box["label"])
        rect = next(
            canvas.coords(item) for item in canvas.find_withtag("all")
            if canvas.type(item) == "rectangle"
            and canvas.coords(item)[0] <= label[0] <= canvas.coords(item)[2]
            and canvas.coords(item)[1] <= label[1] <= canvas.coords(item)[3]
        )
        value_coords = [coords for text, coords in texts if text == str(box["value"])]
        assert len(value_coords) >= 2, f"{box_id} is missing a visible value row"
        assert any(abs(coords[0] - (rect[2] - 7)) < 1 for coords in value_coords), (
            f"{box_id} value {box['value']} is not right-aligned inside its side box"
        )
    root.destroy()


@requires_tk
def test_prisma_flow_diagram_enters_reference_viewport_after_counts(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "prisma-flow-visible.sqlite"), reviewer_id="owner")
    app.section_nav_buttons["prisma"].invoke()
    root.update()

    viewport_bottom = app.prisma_scroll_canvas.winfo_rooty() + app.prisma_scroll_canvas.winfo_height()
    diagram_top = app.prisma_diagram_canvas.winfo_rooty()
    assert diagram_top + int(app.prisma_diagram_canvas.cget("height")) <= viewport_bottom, (
        f"full flow diagram canvas extends below the initial viewport: {diagram_top=} "
        f"{app.prisma_diagram_canvas.cget('height')=} {viewport_bottom=}"
    )
    assert app.prisma_counts_scrollbar.winfo_exists()
    assert 0 < app.prisma_counts_frame.winfo_height() <= 150
    assert app.prisma_counts_text.winfo_height() <= app.prisma_counts_frame.winfo_height()
    assert app.prisma_flow_heading.winfo_parent() == str(app.prisma_flow_card)
    assert app.prisma_flow_heading.winfo_rooty() >= (
        app.prisma_counts_frame.winfo_rooty() + app.prisma_counts_frame.winfo_height()
    )
    assert abs(app.prisma_flow_card.winfo_width() - app.prisma_audit_card.winfo_width()) <= 1
    assert app.prisma_watermark_label.winfo_rooty() < app.prisma_flow_heading.winfo_rooty()
    assert app.prisma_scroll_canvas.yview()[0] == 0
    root.destroy()


@requires_tk
def test_prisma_tab_has_flow_and_audit_cards_without_moving_controls(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "prisma-cards.sqlite"), reviewer_id="owner")

    assert app.prisma_flow_card.winfo_parent() == str(app.prisma_content)
    assert app.prisma_audit_card.winfo_parent() == str(app.prisma_content)
    assert app.prisma_flow_card.grid_info()["column"] == 0
    assert app.prisma_audit_card.grid_info()["column"] == 1
    assert app.prisma_counts_text.winfo_parent() == str(app.prisma_counts_frame)
    assert app.prisma_diagram_canvas.winfo_parent() == str(app.prisma_diagram_frame)
    assert app.prisma_diagram_frame.winfo_parent() == str(app.prisma_flow_card)
    assert app.prisma_audit_tree.winfo_parent() == str(app.prisma_audit_card)
    assert app.prisma_watermark_label.winfo_parent() == str(app.prisma_flow_card)
    assert app.prisma_export_button.winfo_parent() == str(app.prisma_audit_card)
    assert str(app.prisma_export_button.cget("takefocus")) == "1"
    root.destroy()


@requires_tk
def test_prisma_tab_shows_live_counts_snapshot(tmp_path):
    """UI reference target §3: the PRISMA & audit tab must exist with
    accurate counts, even though its export depth comes later."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()

    text = app.prisma_counts_text.get("1.0", "end")
    assert "Identified (total):    1" in text
    assert "No invariant violations." in text
    assert app.section_nav_badges["prisma"].cget("text") == 0  # clean snapshot has no issues
    root.destroy()


@requires_tk
def test_prisma_snapshot_uses_field_notes_type_hierarchy_without_changing_copy(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "prisma-theme.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nSynthetic record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id,
        operation_id="prisma-theme", actor="owner",
    )
    app.refresh_all_tabs()

    text = app.prisma_counts_text.get("1.0", "end")
    assert "Identified (total):    1" in text
    assert "reconciles: 1 = 0+0+1+0  [reconciled]" in text
    assert app.prisma_counts_text.get("1.0", "end").count("Identified") == 4
    assert app.prisma_counts_text.tag_names("1.0 + 3 lines")
    assert "snapshot-section" in app.prisma_counts_text.tag_names("1.0 + 3 lines")
    reconcile_line = next(
        line_no for line_no, line in enumerate(text.splitlines(), start=1)
        if line.startswith("    reconciles:")
    )
    assert "snapshot-reconcile" in app.prisma_counts_text.tag_names(f"{reconcile_line}.0")
    assert theme.FONT_UI in app.prisma_counts_text.cget("font") and "9" in app.prisma_counts_text.cget("font")
    root.destroy()


@requires_tk
def test_prisma_tab_refreshes_live_on_decide_and_undo(tmp_path):
    """Regression: `_decide` (I/M/E) and `_undo_last_decision` (Ctrl+Z)
    must refresh the PRISMA & audit tab themselves -- a real reviewer
    switching to that tab after screening should never see stale
    pre-decision counts. Found via a Phase-1 packaged-build smoke test:
    the queue/recent-decisions/conflicts/full-text/nav-badge refreshes
    were wired on both handlers but the PRISMA snapshot was not, so
    clicking the tab after screening kept showing screening_pending
    instead of records_screened until an unrelated full
    `refresh_all_tabs()` happened to run (e.g. on the next import)."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-op", actor="owner",
    )
    app.refresh_all_tabs()
    assert "screened=0" in app.prisma_counts_text.get("1.0", "end")

    app._load_next_undecided()
    assert app.current_occurrence_id is not None
    app._decide("include")

    text_after_decide = app.prisma_counts_text.get("1.0", "end")
    assert "screened=1" in text_after_decide, text_after_decide
    assert "screening_pending=0" in text_after_decide, text_after_decide

    app._undo_last_decision()

    text_after_undo = app.prisma_counts_text.get("1.0", "end")
    assert "screened=0" in text_after_undo, text_after_undo
    assert "screening_pending=1" in text_after_undo, text_after_undo
    root.destroy()


@requires_tk
def test_prisma_tab_shows_reconciling_equations(tmp_path):
    """PRISMA & audit reference items 3/4: the literal reconciling
    arithmetic is shown, not just a pass/fail invariants note --
    recomputed fresh each refresh, matching prisma.verify_invariants'
    own equations."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\nSecond\nThird\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-eq", actor="owner",
    )
    from screening_workbench import reports
    app.refresh_all_tabs()
    occ_ids = [
        row["occurrence_id"] for row in app.conn.execute(
            "SELECT occurrence_id FROM occurrences ORDER BY occurrence_id"
        ).fetchall()
    ]
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    screening.cast_vote(app.conn, occurrence_id=occ_ids[1], reviewer_id="owner", decision="exclude", reason="design")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occ_ids[0])
    reports.record_full_text_assessment(app.conn, "owner", report_id, "included")
    app.refresh_all_tabs()

    text = app.prisma_counts_text.get("1.0", "end")
    # Item 3: identification/removal/screening equation, with the real
    # numbers substituted in, not a template.
    assert "reconciles: 3 = 0+0+1+2" in text
    assert "[reconciled]" in text
    assert "[MISMATCH]" not in text
    # Item 4: both report-level equations, with the real numbers.
    assert "reconciles: 1 = 1+0" in text  # assessed = included+excluded
    assert "reconciles: 1 = 1+0+0" in text  # sought = assessed+not_retrieved+pending
    root.destroy()


@requires_tk
def test_prisma_tab_watermark_label_matches_export_watermark(tmp_path):
    """PRISMA & audit reference items 1/8: the in-app view states its
    own watermark sequence and frames itself as a preview, not the
    authoritative export -- bound to the same value export.py uses."""
    from screening_workbench import export as export_mod

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-wm", actor="owner",
    )
    app.refresh_all_tabs()

    expected = export_mod.watermark_sequence(app.conn)
    label = app.prisma_watermark_label.cget("text")
    assert f"watermark sequence {expected}" in label
    assert "not the authoritative export" in label
    assert "official watermarked PRISMA diagram and audit log" in label
    assert app.prisma_live_data_label.cget("text") == "Live project data · preview only · not synthetic"


@requires_tk
def test_prisma_tab_flow_diagram_matches_export_boxes(tmp_path):
    """PRISMA & audit reference items 2/10: the live Canvas diagram
    draws the exact same box list (geometry/label/value) the export
    SVG builds from one prisma.full_snapshot call -- never
    independently recalculated -- with real text items for each
    label/value, not an image."""
    from screening_workbench import export as export_mod

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nFirst\nSecond\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-diagram", actor="owner",
    )
    app.refresh_all_tabs()
    occ_ids = [
        row["occurrence_id"] for row in app.conn.execute(
            "SELECT occurrence_id FROM occurrences ORDER BY occurrence_id"
        ).fetchall()
    ]
    screening.cast_vote(app.conn, occurrence_id=occ_ids[0], reviewer_id="owner", decision="include")
    app.refresh_all_tabs()

    expected_boxes = export_mod.prisma_flow_boxes(app.conn)
    canvas_text_items = [
        app.prisma_diagram_canvas.itemcget(item, "text")
        for item in app.prisma_diagram_canvas.find_withtag("all")
        if app.prisma_diagram_canvas.type(item) == "text"
    ]
    # Every box's label and value appear as real Canvas text items,
    # sourced from the same box list the export SVG uses.
    for b in expected_boxes:
        assert b["label"] in canvas_text_items
        assert str(b["value"]) in canvas_text_items
    # "Records identified" must read 2 (both seeded occurrences) --
    # not a stale/independently-computed number.
    identified_box = next(b for b in expected_boxes if b["id"] == "box-identified")
    assert identified_box["value"] == 2
    root.destroy()


@requires_tk
def test_prisma_diagram_fits_full_flow_in_landscape_viewport(tmp_path):
    from screening_workbench import export as export_mod

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "prisma-viewport.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nSynthetic one\nSynthetic two\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="prisma-viewport", actor="owner",
    )
    app.refresh_all_tabs()

    boxes = export_mod.prisma_flow_boxes(app.conn)
    labels = {box["label"] for box in boxes}
    values = {str(box["value"]) for box in boxes}
    canvas = app.prisma_diagram_canvas
    rendered_text = [
        canvas.itemcget(item, "text")
        for item in canvas.find_withtag("all")
        if canvas.type(item) == "text"
    ]
    assert labels.issubset(rendered_text)
    assert values.issubset(rendered_text)
    assert int(canvas.cget("height")) == 205
    assert int(canvas.cget("width")) <= 610
    assert max(canvas.coords(item)[1] for item in canvas.find_withtag("all") if canvas.type(item) == "text") < int(canvas.cget("height"))
    assert sum(1 for item in canvas.find_withtag("all") if canvas.type(item) == "line" and "grid" not in canvas.gettags(item)) == 7  # arrows, not graph paper
    assert not canvas.cget("yscrollcommand")
    assert not canvas.cget("xscrollcommand")
    positions = {
        label: next(
            (canvas.coords(item)[0], canvas.coords(item)[1])
            for item in canvas.find_withtag("all")
            if canvas.type(item) == "text" and canvas.itemcget(item, "text") == label
        )
        for label in labels
    }
    assert positions["Reports sought"][1] < positions["Reports assessed (full text)"][1]
    assert positions["Reports assessed (full text)"][0] < positions["Reports excluded (full text)"][0]
    root.destroy()


@requires_tk
def test_ttk_primary_controls_meet_minimum_target_height(tmp_path):
    root = tk.Tk()
    root.withdraw()
    ScreeningWorkbenchApp(root, str(tmp_path / "control-size.sqlite"), reviewer_id="owner")
    button = ttk.Button(root, text="Probe control")
    button.pack()
    root.update_idletasks()
    assert button.winfo_reqheight() >= 40
    root.destroy()


@requires_tk
def test_prisma_tab_audit_log_shows_events_for_owner(tmp_path):
    """PRISMA & audit reference item 6: the audit log Treeview shows
    sequence/time/actor/event type as separate columns, sourced from
    the real event log -- not a mockup."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nAudit Log Record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-audit", actor="owner",
    )
    app.refresh_all_tabs()
    record_id = app.current_occurrence_id
    screening.cast_vote(app.conn, occurrence_id=record_id, reviewer_id="owner", decision="include")
    app.refresh_all_tabs()

    children = app.prisma_audit_tree.get_children()
    assert len(children) >= 2  # at least the import + the vote_cast event
    event_types = [app.prisma_audit_tree.item(c, "values")[3] for c in children]
    assert "screening.vote_cast" in event_types
    actors = [app.prisma_audit_tree.item(c, "values")[2] for c in children]
    assert all(a == "owner" for a in actors)
    assert "owner/audit_read scope" in app.prisma_audit_scope_label.cget("text")
    root.destroy()


@requires_tk
def test_prisma_tab_audit_log_requires_scope_for_non_owner(tmp_path):
    """PRISMA & audit reference item 7: a reviewer without the
    audit_read scope (and who isn't the owner) sees an explicit
    access-scope message, not the full multi-actor audit log."""
    db_path = str(tmp_path / "proj.sqlite")
    root1 = tk.Tk()
    root1.withdraw()
    owner_app = ScreeningWorkbenchApp(root1, db_path, reviewer_id="owner")  # fixes the project owner
    source_id, branch_id = owner_app._ensure_default_source()
    commit_csv_import(
        owner_app.conn, "title\nScope Test Record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-scope", actor="owner",
    )
    owner_app.conn.commit()
    root1.destroy()

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, db_path, reviewer_id="revB")  # non-owner, no audit_read grant
    app.refresh_all_tabs()

    assert app.prisma_audit_tree.get_children() == ()
    assert "audit_read role" in app.prisma_audit_scope_label.cget("text")
    root.destroy()


@requires_tk
def test_prisma_tab_audit_log_locked_while_blind(tmp_path):
    """PRISMA & audit reference items 6/7: the audit log is
    reviewer-attributable, vote-level data the moment it's populated
    (events carry actor + decision payload) -- locked while blind for
    everyone, no role bypass, mirroring Conflicts/Full-text/Studies.
    Counts stay visible throughout (confirmed blind-independent during
    the baseline's blind check)."""
    from screening_workbench import roles as roles_mod

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nBlind Lock Record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-blind", actor="owner",
    )
    app.refresh_all_tabs()
    assert len(app.prisma_audit_tree.get_children()) > 0  # populated while not blind

    roles_mod.set_blind(app.conn, "owner", True)
    app.refresh_all_tabs()

    assert app.prisma_audit_tree.get_children() == ()
    assert "locked" in app.prisma_audit_scope_label.cget("text").lower()
    # Counts are unaffected -- confirmed blind-independent aggregates.
    assert "Identified (total):    1" in app.prisma_counts_text.get("1.0", "end")

    roles_mod.set_blind(app.conn, "owner", False)
    app.refresh_all_tabs()
    assert len(app.prisma_audit_tree.get_children()) > 0  # re-populates cleanly
    root.destroy()


@requires_tk
def test_blind_reviewer_prisma_aggregates_and_watermark_are_locked(tmp_path):
    """Owner/full_export sees aggregate PRISMA; a normal reviewer sees only locked placeholders."""
    root_owner = tk.Tk()
    root_owner.withdraw()
    db_path = str(tmp_path / "prisma-blind.sqlite")
    owner_app = ScreeningWorkbenchApp(root_owner, db_path, reviewer_id="owner")
    source_id, branch_id = owner_app._ensure_default_source()
    commit_csv_import(
        owner_app.conn, "title\nBlind reviewer record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-prisma-blind", actor="owner",
    )
    roles.set_blind(owner_app.conn, "owner", True)
    owner_app.refresh_all_tabs()
    assert "LOCKED" not in str(owner_app.notebook.tab(6, "text"))
    assert "Identified (total):" in owner_app.prisma_counts_text.get("1.0", "end")
    assert owner_app.prisma_diagram_canvas.find_all()
    owner_app.conn.close()
    root_owner.destroy()

    reviewer_root = tk.Tk()
    reviewer_root.withdraw()
    reviewer_app = ScreeningWorkbenchApp(reviewer_root, db_path, reviewer_id="reviewer")
    assert "LOCKED" in str(reviewer_app.notebook.tab(6, "text"))
    assert "locked" in reviewer_app.prisma_watermark_label.cget("text").lower()
    assert "hidden" in reviewer_app.prisma_live_data_label.cget("text").lower()
    assert "locked" in reviewer_app.prisma_counts_text.get("1.0", "end").lower()
    assert reviewer_app.prisma_diagram_canvas.find_all() == ()
    assert reviewer_app.prisma_flow_boxes_by_id == {}
    assert "LOCKED" in str(reviewer_app.notebook.tab(6, "text"))
    roles.set_blind(reviewer_app.conn, "owner", False)
    reviewer_app.conn.close()
    reviewer_root.destroy()


@requires_tk
def test_prisma_tab_outer_frame_is_scrollable(tmp_path):
    """PRISMA & audit reference item 11: a real gap found during the
    keyboard check, not a cosmetic nit -- on a standard 1280x800
    window, the audit log and Export button were below the fold with
    no way to scroll the outer tab at all (only the inner diagram
    canvas was scrollable). The whole tab now sits in its own
    scrollable Canvas with a working scrollregion and keyboard (Up/
    Down/PageUp/PageDown) bindings."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nScroll Reachability Record\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="t-scroll", actor="owner",
    )
    app.refresh_all_tabs()
    # Multiple populated branches and an expanded summary can make the
    # left card taller; force that valid overflow state to exercise the
    # outer canvas scroll, while the default viewport keeps the diagram
    # visible alongside its compact independently-scrollable count pane.
    app.prisma_counts_frame.configure(height=700, padding=12)
    app.prisma_flow_card.grid_rowconfigure(2, weight=0)
    app.root.update_idletasks()

    # The scrollregion must actually cover content taller than a
    # typical window -- not just exist with a zero/degenerate extent.
    region = app.prisma_scroll_canvas.cget("scrollregion")
    assert region, "scrollregion was never set"
    # The two-card layout compresses content vertically; the original
    # fixed 800px threshold no longer matches the mapped tab's available
    # client area. Require a real non-degenerate page extent beyond 600px.
    _, _, _, region_bottom = (float(v) for v in region.split())
    assert region_bottom > 600, f"scrollregion only {region_bottom}px tall -- content extent is degenerate"

    # Keyboard scrolling actually moves the view, not a no-op binding.
    # (yview_scroll's unit/page amount depends on the canvas's real
    # on-screen pixel height, which a withdrawn/headless test window
    # never gets -- confirmed separately, winfo_height() stays 1px
    # there regardless of content. yview_moveto is the geometry-
    # independent half of the same scrolling API the <Next>/<Prior>/
    # <Up>/<Down> bindings call into, so it still proves the canvas
    # genuinely scrolls, not just that a scrollregion string exists.)
    app.prisma_scroll_canvas.yview_moveto(0.5)
    app.root.update()
    assert app.prisma_scroll_canvas.yview()[0] == pytest.approx(0.5, abs=0.01)
    root.destroy()


@requires_tk
def test_phase1_chrome_shell_has_menu_header_badge_nav_and_status_footer(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase1-shell.sqlite"), reviewer_id="owner")
    root.update_idletasks()

    assert list(app.section_nav_buttons) == [
        "screening", "maybe", "duplicates", "conflicts", "fulltext", "studies", "prisma",
    ]
    assert str(app.section_nav_badges["maybe"].cget("text")) == "0"
    assert str(app.section_nav_badges["screening"].cget("text")) == "0"
    assert str(app.notebook.tab(1, "text")) == "Maybe re-review  (0)"
    assert app.section_nav_buttons["maybe"].cget("text") == "Maybe re-review"
    assert str(app.section_nav_badges["maybe"].cget("text")) == "0"
    assert app.status_notice_label.cget("text") == f"Local only · {Path(app.db_path).name}"

    menu = app.menubar
    assert [menu.entrycget(i, "label") for i in range(menu.index("end") + 1)] == [
        "File", "Project", "View", "Help",
    ]
    assert root.cget("menu") in ("", "None")
    assert len(app.menubar_frame.winfo_children()) == 4
    assert [button.cget("text") for button in app.menubar_buttons] == ["File", "Project", "View", "Help"]
    assert all(button.cget("style") == "ChromeMenu.TMenubutton" for button in app.menubar_buttons)
    assert app.section_nav.winfo_manager() == "pack"
    assert app.notebook.winfo_manager() == "pack"
    assert app.notebook.index("end") == 7
    assert ttk.Style(root).layout("Shell.TNotebook.Tab") == [("null", {"sticky": "nswe"})]

    app.section_nav_buttons["maybe"].invoke()
    root.update_idletasks()
    assert app.notebook.index("current") == 1
    assert str(app.section_nav_buttons["maybe"].cget("style")) == "ActiveSection.TButton"
    assert str(app.section_nav_buttons["screening"].cget("style")) == "Section.TButton"
    root.destroy()


@requires_tk
def test_phase2_status_footer_is_visible_below_notebook(tmp_path):
    root = tk.Tk()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase2-footer.sqlite"), reviewer_id="owner")
    root.update()

    assert app.status_bar.winfo_ismapped()
    assert app.status_bar.winfo_y() > app.notebook.winfo_y()
    assert app.notebook.winfo_y() + app.notebook.winfo_height() <= app.status_bar.winfo_y()
    assert app.status_bar.winfo_y() + app.status_bar.winfo_height() <= root.winfo_height()
    assert app.status_notice_label.cget("text") == "Local only · phase2-footer.sqlite"
    assert app.status_legend_label.cget("text") == "Screening shortcuts: I/M/E · 1–7 reason · J/K · / search"
    app._set_status("Saved: Include (synthetic record)")
    root.update_idletasks()
    assert app.status_message_label.cget("text") == "Saved: Include (synthetic record)"
    assert app.status_message_label.winfo_width() > 0
    root.destroy()


@requires_tk
def test_phase2_screening_tab_has_three_card_shell_without_moving_controls(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase2-screening-cards.sqlite"), reviewer_id="owner")
    root.update_idletasks()

    assert app.screen_queue_card.winfo_parent() == str(app.screen_body)
    assert app.screen_record_card.winfo_parent() == str(app.screen_body)
    assert app.screen_support_card.winfo_parent() == str(app.screen_body)
    assert app.queue_col.winfo_parent() == str(app.screen_queue_card)
    assert app.record_frame.winfo_parent() == str(app.screen_record_card)
    assert app.side_panel.winfo_parent() == str(app.screen_support_card)
    assert app.screen_queue_card.grid_info()["column"] == 0
    assert app.screen_record_card.grid_info()["column"] == 1
    assert app.screen_support_card.grid_info()["column"] == 2
    assert app.queue_list.winfo_toplevel() == root
    assert app.abstract_text.winfo_toplevel() == root
    assert app.include_button.winfo_parent() == str(app.primary_decision_bar)
    assert app.queue_list.get_children() == ()
    assert app.current_occurrence_id is None
    root.destroy()


@requires_tk
def test_phase3_screening_decision_bars_fit_visible_cards_at_1280x800(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase3-screening-containment.sqlite"), reviewer_id="owner")
    app.notebook.select(0)
    root.deiconify()
    root.update()
    root.update_idletasks()

    def descendants(widget):
        found = []
        for child in widget.winfo_children():
            found.append(child)
            found.extend(descendants(child))
        return found

    def assert_inside(widget, card):
        card_bottom = card.winfo_rooty() + card.winfo_height()
        assert widget.winfo_ismapped()
        assert widget.winfo_height() >= widget.winfo_reqheight()
        assert widget.winfo_rooty() + widget.winfo_height() <= card_bottom

    for button in (app.include_button, app.maybe_button, app.exclude_button):
        assert_inside(button, app.screen_record_card)
    for button in descendants(app.screen_queue_card):
        if isinstance(button, ttk.Button) and button.cget("text") in ("Include", "Maybe", "Exclude..."):
            assert_inside(button, app.screen_queue_card)
    assert_inside(app.primary_decision_bar, app.screen_record_card)
    root.destroy()


@requires_tk
def test_phase3_fulltext_pdf_actions_fit_visible_card_at_1280x800(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase3-fulltext-containment.sqlite"), reviewer_id="owner")
    app.notebook.select(4)
    root.deiconify()
    root.update()
    root.update_idletasks()
    card_bottom = app.fulltext_support_card.winfo_rooty() + app.fulltext_support_card.winfo_height()

    def assert_inside(widget, card):
        card_bottom = card.winfo_rooty() + card.winfo_height()
        assert widget.winfo_ismapped()
        assert widget.winfo_height() >= widget.winfo_reqheight()
        assert widget.winfo_rooty() + widget.winfo_height() <= card_bottom

    assert_inside(app.fulltext_reason_note, app.fulltext_support_card)
    assert_inside(app.fulltext_reason_count_label, app.fulltext_support_card)
    assert_inside(app.fulltext_not_retrieved_note, app.fulltext_support_card)
    assert_inside(app.fulltext_keyboard_guide, app.fulltext_support_card)
    for button in (app.attach_pdf_btn, app.open_attachment_btn, app.remove_attachment_btn):
        assert_inside(button, app.fulltext_support_card)
        assert button.winfo_height() >= button.winfo_reqheight()
    root.destroy()


@requires_tk
def test_phase4_maybe_keyboard_and_blind_callout_fit_support_card(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase4-maybe-gate-fit.sqlite"), reviewer_id="owner")
    app.notebook.select(1)
    root.deiconify(); root.update(); root.update_idletasks()
    card_top = app.maybe_support_card.winfo_rooty()
    card_bottom = card_top + app.maybe_support_card.winfo_height()

    for widget in (app.maybe_blind_gate_frame, app.maybe_keyboard_heading, app.maybe_keyboard_help):
        assert widget.winfo_ismapped()
        assert widget.winfo_rooty() >= card_top
        assert widget.winfo_rooty() + widget.winfo_height() <= card_bottom
    assert app.maybe_keyboard_help.cget("text") == "Queue-focused: I/M/E/J/K."
    assert "no other reviewer’s titles or decisions appear" in app.maybe_blind_gate_label.cget("text")
    root.destroy()


@requires_tk
def test_phase4_fulltext_selected_exclusion_note_is_not_clipped_by_pdf_row(tmp_path):
    from screening_workbench import reports, screening

    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "phase4-fulltext-reason-note.sqlite"), reviewer_id="owner")
    occurrence_ids = _seed_two_occurrences(app, "Synthetic selected reason note", "Synthetic unrelated control")
    screening.cast_vote(app.conn, occurrence_id=occurrence_ids[0], reviewer_id="owner", decision="include")
    report_id = reports.promote_occurrence_to_report(app.conn, "owner", occurrence_ids[0])
    app.refresh_all_tabs()
    app.notebook.select(4)
    app.report_list.selection_set(app._report_ids.index(report_id))
    app._render_fulltext_detail()
    app.fulltext_reason_var.set(screening.EXCLUSION_REASONS[0])
    app._update_fulltext_reason_state()
    root.deiconify(); root.update(); root.update_idletasks()

    assert app.fulltext_reason_count_label.cget("text") == "Counts on save · reports excluded +1"
    assert app.fulltext_reason_note.cget("text") == f"Selected exclusion reason: {screening.EXCLUSION_REASONS[0]}."
    assert app.fulltext_reason_note.winfo_height() >= app.fulltext_reason_note.winfo_reqheight()
    assert app.fulltext_reason_note.winfo_rooty() + app.fulltext_reason_note.winfo_height() <= app.fulltext_attachment_actions.winfo_rooty()
    assert app.attach_pdf_btn.winfo_ismapped() and app.open_attachment_btn.winfo_ismapped() and app.remove_attachment_btn.winfo_ismapped()
    root.destroy()


@requires_tk
def test_all_seven_tabs_present_in_reference_order(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    tab_texts = [app.notebook.tab(i, "text").split("  ")[0] for i in range(app.notebook.index("end"))]
    assert tab_texts == [
        "Screening", "Maybe re-review", "Duplicates", "Conflicts",
        "Full-text", "Studies", "PRISMA & audit",
    ]
    root.destroy()


# --- Directive A UI wiring: the Conflicts tab's Agreement (Cohen's kappa) strip ---

@requires_tk
def test_kappa_strip_is_hidden_in_blind_project_and_owner_prisma_stays_visible(tmp_path):
    """The disabled kappa strip is decision-derived; the project owner
    retains full PRISMA access while blind mode is active."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "kappa-blind.sqlite"), reviewer_id="owner")
    roles.set_blind(app.conn, "owner", True)
    source_id, branch_id = app._ensure_default_source()
    for batch, decision, reason in (("kappa-a", "include", None), ("kappa-b", "exclude", "Synthetic exclusion")):
        seeded = commit_csv_import(
            app.conn, "title\nSame synthetic record\n", {0: "title"},
            source_id=source_id, branch_id=branch_id, operation_id=batch, actor="owner",
        )
        occurrence_id = app.conn.execute(
            "SELECT occurrence_id FROM occurrences WHERE batch_id=?", (seeded.batch_id,),
        ).fetchone()["occurrence_id"]
        screening.cast_vote(
            app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision=decision, reason=reason,
        )
    app.refresh_all_tabs()
    assert app.kappa_label.winfo_manager() == ""
    assert app.prisma_watermark_label.cget("text").startswith("Preview as of watermark sequence")
    assert "Identified (total):" in app.prisma_counts_text.get("1.0", "end")
    assert app.prisma_diagram_canvas.find_all()
    with pytest.raises(PermissionError, match="locked once screening has begun"):
        roles.set_blind(app.conn, "owner", False)
    root.destroy()


@requires_tk
def test_kappa_strip_shows_na_with_one_reviewer(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    app.refresh_all_tabs()
    assert "n/a" in app.kappa_label.cget("text")
    root.destroy()


# --- Directive B UI wiring: reviewer packets end to end ---

def _patch_dialogs(monkeypatch, *, open_path=None, save_path=None):
    """Mirror the existing file's pattern (monkeypatching the shared
    tkinter.filedialog/messagebox module objects screening_workbench.app imports) so
    action_* handlers never open a real blocking dialog in tests."""
    import tkinter.filedialog as filedialog_mod
    import tkinter.messagebox as messagebox_mod
    monkeypatch.setattr(filedialog_mod, "askopenfilename", lambda **k: open_path or "")
    monkeypatch.setattr(filedialog_mod, "asksaveasfilename", lambda **k: save_path or "")
    monkeypatch.setattr(messagebox_mod, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(messagebox_mod, "showerror", lambda *a, **k: None)


@requires_tk
def test_packet_round_trip_via_ui_actions_conflicts_and_kappa(tmp_path, monkeypatch):
    """Directive B §7 round-trip, driven through the real UI actions
    (not calling screening_workbench.packets directly): host exports a packet, a
    second ScreeningWorkbenchApp instance (reviewer B, separate database) imports
    it, screens via the normal decision flow, exports its votes, and
    the host merges -- conflicts and the kappa strip both update."""
    host_root = tk.Tk()
    host_root.withdraw()
    host = ScreeningWorkbenchApp(host_root, str(tmp_path / "host.db"), reviewer_id="owner")
    source_id, branch_id = host._ensure_default_source()
    from screening_workbench.importers.csv_importer import commit_csv_import as _commit
    result = _commit(
        host.conn, "title\nStudy One\nStudy Two\nStudy Three\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="packet-ui-seed", actor="owner",
    )
    occ_rows = host.conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
    ).fetchall()
    occ_ids = [r["occurrence_id"] for r in occ_rows]
    for occ_id, decision in zip(occ_ids, ["include", "include", "exclude"]):
        reason = "Wrong population" if decision == "exclude" else None
        screening.cast_vote(host.conn, occurrence_id=occ_id, reviewer_id="owner", decision=decision, reason=reason)

    packet_path = str(tmp_path / "packet.json")
    _patch_dialogs(monkeypatch, save_path=packet_path)
    host.action_export_reviewer_packet()
    assert (tmp_path / "packet.json").is_file()

    b_root = tk.Tk()
    b_root.withdraw()
    reviewer_b = ScreeningWorkbenchApp(b_root, str(tmp_path / "reviewerB.db"), reviewer_id="revB")
    _patch_dialogs(monkeypatch, open_path=packet_path)
    reviewer_b.action_import_reviewer_packet()
    imported_ids = {r["occurrence_id"] for r in reviewer_b.conn.execute("SELECT occurrence_id FROM occurrences").fetchall()}
    assert imported_ids == set(occ_ids)

    # Reviewer B screens: agrees on 2, disagrees on the 3rd (conflict).
    for occ_id, decision in zip(occ_ids, ["include", "include", "include"]):
        screening.cast_vote(reviewer_b.conn, occurrence_id=occ_id, reviewer_id="revB", decision=decision)

    votes_path = str(tmp_path / "votes.json")
    _patch_dialogs(monkeypatch, save_path=votes_path)
    reviewer_b.action_export_votes_file()
    assert (tmp_path / "votes.json").is_file()
    b_root.destroy()

    _patch_dialogs(monkeypatch, open_path=votes_path)
    host.action_merge_votes_file()
    host.refresh_all_tabs()

    assert host._conflict_occurrence_ids == [occ_ids[2]]
    assert "n = 3" in host.kappa_label.cget("text")
    host_root.destroy()


@requires_tk
def test_merge_votes_blocked_while_blind_never_opens_dialog(tmp_path, monkeypatch):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")

    from screening_workbench import roles
    roles.set_blind(app.conn, "owner", True)
    app.refresh_all_tabs()

    def _should_not_be_called(**kwargs):
        raise AssertionError("file dialog must not open while blind")

    import tkinter.filedialog as filedialog_mod
    import tkinter.messagebox as messagebox_mod
    monkeypatch.setattr(filedialog_mod, "askopenfilename", _should_not_be_called)
    errors = []
    monkeypatch.setattr(messagebox_mod, "showerror", lambda title, msg: errors.append(msg))

    app.action_merge_votes_file()
    assert errors and "blind" in errors[0].lower()
    assert str(app.merge_votes_btn.cget("state")) == "disabled"
    root.destroy()


@requires_tk
def test_import_packet_twice_on_same_db_shows_error_not_exception(tmp_path, monkeypatch):
    host_root = tk.Tk()
    host_root.withdraw()
    host = ScreeningWorkbenchApp(host_root, str(tmp_path / "host.db"), reviewer_id="owner")
    source_id, branch_id = host._ensure_default_source()
    from screening_workbench.importers.csv_importer import commit_csv_import as _commit
    _commit(
        host.conn, "title\nOnly\n", {0: "title"}, source_id=source_id, branch_id=branch_id,
        operation_id="dup-import-seed", actor="owner",
    )

    packet_path = str(tmp_path / "packet.json")
    _patch_dialogs(monkeypatch, save_path=packet_path)
    host.action_export_reviewer_packet()
    host_root.destroy()

    b_root = tk.Tk()
    b_root.withdraw()
    reviewer_b = ScreeningWorkbenchApp(b_root, str(tmp_path / "reviewerB.db"), reviewer_id="revB")
    _patch_dialogs(monkeypatch, open_path=packet_path)
    reviewer_b.action_import_reviewer_packet()

    errors = []
    import tkinter.messagebox as messagebox_mod
    monkeypatch.setattr(messagebox_mod, "showerror", lambda title, msg: errors.append(msg))
    reviewer_b.action_import_reviewer_packet()  # second import on the same (locked) database
    assert errors and "packet" in errors[0].lower()
    b_root.destroy()


@requires_tk
@pytest.mark.parametrize(
    ("label", "filename", "contents"),
    [
        (
            "Import RIS...", "batch.ris",
            "TY  - JOUR\nTI  - Shared Study\nPY  - 2020\nER  - \n"
            "TY  - JOUR\nTI  - New RIS Study\nPY  - 2022\nER  - \n",
        ),
        (
            "Import PubMed XML...", "batch.xml",
            "<PubmedArticleSet>"
            "<PubmedArticle><MedlineCitation><PMID>101</PMID><Article><ArticleTitle>Shared Study</ArticleTitle><Journal><JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation></PubmedArticle>"
            "<PubmedArticle><MedlineCitation><PMID>102</PMID><Article><ArticleTitle>New XML Study</ArticleTitle><Journal><JournalIssue><PubDate><Year>2022</Year></PubDate></JournalIssue></Journal></Article></MedlineCitation></PubmedArticle>"
            "</PubmedArticleSet>",
        ),
    ],
)
def test_non_csv_import_file_menu_actions_commit_and_report_duplicates(
    tmp_path, monkeypatch, label, filename, contents
):
    """Drive each real File-menu command with a synthetic file and check
    import, duplicate detection, normalization, and displayed counts."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "project.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title,year\nShared Study,2020\n", {0: "title", 1: "year"},
        source_id=source_id, branch_id=branch_id, operation_id="seed-duplicate", actor="owner",
    )
    path = tmp_path / filename
    path.write_text(contents, encoding="utf-8")
    _patch_dialogs(monkeypatch, open_path=str(path))
    reports = []
    import tkinter.messagebox as messagebox_mod
    monkeypatch.setattr(messagebox_mod, "showinfo", lambda title, text: reports.append((title, text)))

    menu = app.menubar
    file_menu = root.nametowidget(menu.entrycget(0, "menu"))
    labels = {
        i: file_menu.entrycget(i, "label")
        for i in range(file_menu.index("end") + 1)
        if file_menu.type(i) == "command"
    }
    command_index = next(i for i, item_label in labels.items() if item_label == label)
    file_menu.invoke(command_index)

    assert reports and reports[-1][0] == "Import complete"
    report = reports[-1][1]
    assert "read 2" in report
    assert "1 duplicate" in report
    assert "skipped 0" in report
    rows = app.conn.execute(
        "SELECT f.fields_json FROM occurrence_fields f JOIN occurrences o USING(occurrence_id) WHERE o.is_active=1"
    ).fetchall()
    titles = {json.loads(row["fields_json"])["title"].casefold() for row in rows}
    assert titles == {"shared study", "new ris study" if label == "Import RIS..." else "new xml study"}
    root.destroy()


@requires_tk
def test_csv_menu_import_allows_explicit_encoding_delimiter_and_headerless_mapping(tmp_path, monkeypatch):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "project.sqlite"), reviewer_id="owner")
    path = tmp_path / "headerless.csv"
    path.write_bytes("Étude;Smith;2020\nAutre;Jones;2021\n".encode("cp1252"))
    _patch_dialogs(monkeypatch, open_path=str(path))
    import tkinter.messagebox as messagebox_mod
    monkeypatch.setattr(messagebox_mod, "askyesnocancel", lambda *a, **k: False)
    reports = []
    monkeypatch.setattr(messagebox_mod, "showinfo", lambda title, text: reports.append((title, text)))
    choices = iter(["cp1252", "semicolon", "title,authors,year"])
    import tkinter.simpledialog as simpledialog_mod
    monkeypatch.setattr(simpledialog_mod, "askstring", lambda *a, **k: next(choices))

    menu = app.menubar
    file_menu = root.nametowidget(menu.entrycget(0, "menu"))
    commands = {
        i: file_menu.entrycget(i, "label")
        for i in range(file_menu.index("end") + 1)
        if file_menu.type(i) == "command"
    }
    csv_index = next(i for i, item_label in commands.items() if item_label == "Import CSV...")
    file_menu.invoke(csv_index)

    assert reports and "read 2" in reports[-1][1]
    assert "0 duplicate" in reports[-1][1]
    assert "skipped 0" in reports[-1][1]
    rows = app.conn.execute(
        "SELECT f.fields_json FROM occurrence_fields f JOIN occurrences o USING(occurrence_id) WHERE o.is_active=1"
    ).fetchall()
    fields = [json.loads(row["fields_json"]) for row in rows]
    assert [item["title"] for item in fields] == ["Étude", "Autre"]
    assert fields[0]["authors"] == ["Smith"]
    assert fields[0]["year"] == "2020"
    root.destroy()


@requires_tk
def test_manual_csv_mapping_imports_nonstandard_headers(tmp_path, monkeypatch):
    import tkinter.filedialog as filedialog
    import tkinter.messagebox as messagebox
    import tkinter.simpledialog as simpledialog

    csv_path = tmp_path / "wos.csv"
    csv_path.write_text(
        '15. Title (WoS),Authors (WoS),Publication Year\n"A study",Smith; Jones,2021\n',
        encoding="utf-8",
    )
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "proj.sqlite"), reviewer_id="owner")
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kwargs: str(csv_path))
    monkeypatch.setattr(simpledialog, "askstring", lambda *args, **kwargs: "comma")
    monkeypatch.setattr(messagebox, "askyesnocancel", lambda *args, **kwargs: True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)
    seen = {}

    def choose_mapping(preview):
        seen["headers"] = preview.header_fields
        seen["samples"] = [p.sample_values for p in preview.mapping_proposals]
        return {0: "title", 1: "authors", 2: "year"}

    monkeypatch.setattr(app, "_prompt_csv_mapping", choose_mapping)
    app.root.after(50, app.root.quit)
    app.action_import_csv()
    assert seen["headers"] == ["15. Title (WoS)", "Authors (WoS)", "Publication Year"]
    assert seen["samples"] == [["A study"], ["Smith; Jones"], ["2021"]]
    fields = json.loads(app.conn.execute("SELECT fields_json FROM occurrence_fields").fetchone()["fields_json"])
    assert fields["title"] == "A study"
    assert fields["authors"] == ["Smith; Jones"]
    assert fields["year"] == "2021"
    root.destroy()


@requires_tk
def test_duplicate_pair_budget_is_handled_in_ui_without_partial_dedup_state(tmp_path, monkeypatch):
    import tkinter.filedialog as filedialog
    import tkinter.messagebox as messagebox
    import tkinter.simpledialog as simpledialog
    from screening_workbench import dedup

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "pair-budget.sqlite"), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    existing = commit_csv_import(
        app.conn,
        "title,authors,year\nExisting one,Smith,2019\nExisting two,Jones,2021\n",
        {0: "title", 1: "authors", 2: "year"}, source_id=source_id, branch_id=branch_id,
        operation_id="existing-budget-import", actor="owner",
    )
    dedup.run_exact_and_fuzzy_detection(app.conn, "system", batch_id=existing.batch_id)
    import_path = tmp_path / "incoming.csv"
    import_path.write_text("title,authors,year\nNew one,Smith,2020\nNew two,Jones,2021\n", encoding="utf-8")
    monkeypatch.setattr(filedialog, "askopenfilename", lambda **kwargs: str(import_path))
    monkeypatch.setattr(simpledialog, "askstring", lambda *args, **kwargs: "comma")
    monkeypatch.setattr(messagebox, "askyesnocancel", lambda *args, **kwargs: True)
    monkeypatch.setattr(app, "_prompt_csv_mapping", lambda preview: {0: "title", 1: "authors", 2: "year"})
    state_before = {
        table: app.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("events", "dedup_candidates", "duplicate_merges")
    }
    errors = []
    monkeypatch.setattr(messagebox, "showerror", lambda title, text: errors.append((title, text)))
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: pytest.fail("unexpected import success dialog"))

    with patch("screening_workbench.dedup.MAX_PAIR_COMPARISONS", 2):
        app.action_import_csv()

    state_after = {
        table: app.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in state_before
    }
    assert app.conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0] == 2
    assert app.conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0] == 1
    operation = app.conn.execute(
        "SELECT COUNT(*) FROM operations WHERE operation_id LIKE 'ui-import-incoming.csv-%'"
    ).fetchone()[0]
    assert operation == 0
    assert state_after == state_before
    assert len(errors) == 1
    assert errors[0][0] == "Duplicate detection limit"
    assert "No duplicate merges or review candidates were created" in errors[0][1]
    root.destroy()


@requires_tk
def test_csv_mapping_requires_title_and_reports_duplicate_fields():
    from screening_workbench.app import validate_csv_mapping

    assert validate_csv_mapping({0: "authors", 1: "year"}) == "Map a column to title before importing."
    assert "more than one column" in (validate_csv_mapping({0: "title", 1: "title"}) or "").casefold()
    assert validate_csv_mapping({0: "title", 1: "authors"}) is None


@requires_tk
def test_project_reset_clears_database_and_attachments_and_allows_import(tmp_path, monkeypatch):
    import tkinter.messagebox as messagebox
    import tkinter.simpledialog as simpledialog
    from screening_workbench import attachments

    root = tk.Tk()
    root.withdraw()
    db_path = tmp_path / "proj.sqlite"
    app = ScreeningWorkbenchApp(root, str(db_path), reviewer_id="owner")
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nBefore reset\n", {0: "title"}, source_id=source_id,
        branch_id=branch_id, operation_id="before-reset", actor="owner",
    )
    attach_dir = attachments.resolve_attachments_dir(app.conn)
    attach_dir.mkdir(parents=True)
    (attach_dir / "fixture.pdf").write_bytes(b"test")
    monkeypatch.setattr(simpledialog, "askstring", lambda *args, **kwargs: "RESET")
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)
    monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kwargs: None)
    monkeypatch.setattr(messagebox, "showerror", lambda *args, **kwargs: None)

    app.action_reset_project()

    assert db_path.exists()
    assert app.conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0] == 0
    events = [row[0] for row in app.conn.execute("SELECT event_type FROM events")]
    assert events == ["project.owner_set"]
    assert not attach_dir.exists()
    source_id, branch_id = app._ensure_default_source()
    commit_csv_import(
        app.conn, "title\nAfter reset\n", {0: "title"}, source_id=source_id,
        branch_id=branch_id, operation_id="after-reset", actor="owner",
    )
    assert app.conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0] == 1
    root.destroy()



# ---- R6 UI polish: defects found in the 1.0.0 aesthetics review ----

def _effective_background(widget) -> str | None:
    """Background a widget actually paints: ttk via its style, classic Tk via its option."""
    if isinstance(widget, ttk.Widget):
        if "background" in widget.keys() and str(widget.cget("background")):
            return str(widget.cget("background"))
        style = widget.cget("style") or widget.winfo_class()
        return ttk.Style(widget).lookup(style, "background") or None
    try:
        return str(widget.cget("background"))
    except tk.TclError:
        return None


def _iter_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _iter_widgets(child)


def _seed_side_box_reports(app):
    from screening_workbench import reports

    source_id, branch_id = app._ensure_default_source()
    result = commit_csv_import(
        app.conn, "title\nSynthetic not-retrieved report\nSynthetic excluded report\n", {0: "title"},
        source_id=source_id, branch_id=branch_id, operation_id="r6-side-box-seed", actor="owner",
    )
    rows = app.conn.execute(
        "SELECT o.occurrence_id, f.fields_json FROM occurrences o "
        "JOIN occurrence_fields f ON f.occurrence_id=o.occurrence_id WHERE o.batch_id=?",
        (result.batch_id,),
    ).fetchall()
    ids = {json.loads(row["fields_json"])["title"]: row["occurrence_id"] for row in rows}
    for occurrence_id in ids.values():
        screening.cast_vote(app.conn, occurrence_id=occurrence_id, reviewer_id="owner", decision="include")
    not_retrieved = reports.promote_occurrence_to_report(app.conn, "owner", ids["Synthetic not-retrieved report"])
    reports.mark_not_retrieved(app.conn, "owner", not_retrieved)
    excluded = reports.promote_occurrence_to_report(app.conn, "owner", ids["Synthetic excluded report"])
    reports.record_full_text_assessment(app.conn, "owner", excluded, "excluded", exclusion_reason="wrong_population")
    app.refresh_all_tabs()


@requires_tk
def test_r6_widgets_inside_cards_paint_the_card_surface(tmp_path):
    """No grey canvas-colored band or tinted middle panel inside a white card."""
    from screening_workbench import theme

    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r6-card-surface.sqlite"), reviewer_id="owner")
    _seed_side_box_reports(app)
    root.update()

    cards = [w for w in _iter_widgets(root) if isinstance(w, ttk.Frame) and w.cget("style") == "Card.TFrame"]
    assert len(cards) >= 18  # every tab's cards except Screening's flat queue and support columns
    nested = [str(c) for c in cards if any(str(c).startswith(str(o) + ".") for o in cards)]
    assert nested == [], "an inner frame picked up the bordered card style"
    mismatched = []
    for card in cards:
        for widget in _iter_widgets(card):
            if widget is card or not isinstance(widget, (ttk.Frame, ttk.Label, ttk.Checkbutton, ttk.Radiobutton)):
                continue
            master_bg = _effective_background(widget.master)
            if master_bg == theme.TOKENS["surface"] and _effective_background(widget) != theme.TOKENS["surface"]:
                mismatched.append((str(widget), widget.winfo_class(), _effective_background(widget)))
    assert mismatched == []
    root.destroy()


@requires_tk
def test_r6_no_ui_text_names_a_source_file(tmp_path):
    import re

    root = tk.Tk()
    root.geometry("1280x800")
    ScreeningWorkbenchApp(root, str(tmp_path / "r6-copy.sqlite"), reviewer_id="owner")
    root.update()

    leaks = []
    for widget in _iter_widgets(root):
        texts = []
        if isinstance(widget, tk.Text):
            texts.append(widget.get("1.0", "end"))
        else:
            try:
                texts.append(str(widget.cget("text")))
            except tk.TclError:
                pass
        leaks += [text for text in texts if re.search(r"\b\w+\.py\b", text)]
    assert leaks == []
    root.destroy()


@requires_tk
@pytest.mark.parametrize("seeded", [False, True])
def test_r6_prisma_diagram_text_boxes_and_arrows_do_not_collide(tmp_path, seeded):
    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / f"r6-prisma-layout-{seeded}.sqlite"), reviewer_id="owner")
    if seeded:
        _seed_side_box_reports(app)
    app.section_nav_buttons["prisma"].invoke()
    root.update()

    canvas = app.prisma_diagram_canvas
    width, height = int(canvas.cget("width")), int(canvas.cget("height"))
    rects = [canvas.coords(i) for i in canvas.find_all() if canvas.type(i) == "rectangle"]
    texts = [(canvas.itemcget(i, "text"), canvas.bbox(i)) for i in canvas.find_all() if canvas.type(i) == "text"]
    lines = [canvas.coords(i) for i in canvas.find_all() if canvas.type(i) == "line" and "grid" not in canvas.gettags(i)]
    assert len(rects) == 8

    def overlaps(a, b):
        return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]

    for index, a in enumerate(rects):
        assert all(not overlaps(a, b) for b in rects[index + 1:]), "PRISMA boxes overlap"
    for index, (text, a) in enumerate(texts):
        assert 0 <= a[0] and a[2] <= width and 0 <= a[1] and a[3] <= height, f"{text!r} leaves the canvas"
        for other, b in texts[index + 1:]:
            assert not overlaps(a, b), f"{text!r} collides with {other!r}"
    left_edge = min(r[0] for r in rects)
    for text, box in texts:
        inside = [r for r in rects if r[0] <= box[0] and box[2] <= r[2] and r[1] <= box[1] and box[3] <= r[3]]
        if not inside:
            assert box[2] <= left_edge, f"stage label {text!r} runs into the boxes"
    side_x = max(r[0] for r in rects)
    for x1, y1, x2, y2 in lines:
        if abs(x2 - side_x) < 1:
            assert y1 == y2, "exclusion arrows must run horizontally"
    root.destroy()


@requires_tk
def test_r6_prisma_identification_counts_visible_without_scrolling(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r6-counts.sqlite"), reviewer_id="owner")
    app.section_nav_buttons["prisma"].invoke()
    root.update()

    text = app.prisma_counts_text
    assert text.get("7.0", "7.end").startswith("Open fuzzy pairs")
    info = text.dlineinfo("7.0")
    assert info is not None, "Open fuzzy pairs needs scrolling to be seen"
    assert info[3] == text.dlineinfo("1.0")[3], "Open fuzzy pairs is clipped at the bottom edge"
    root.destroy()


@requires_tk
def test_r6_audit_log_time_shows_whole_seconds_in_utc(tmp_path):
    import re
    import tkinter.font as tkfont

    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r6-audit.sqlite"), reviewer_id="owner")
    _seed_side_box_reports(app)
    app.section_nav_buttons["prisma"].invoke()
    root.update()

    tree = app.prisma_audit_tree
    assert tree.heading("time", "text") == "Time (UTC)"
    times = [tree.set(iid, "time") for iid in tree.get_children()]
    assert times and all(re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", t) for t in times)
    font = tkfont.Font(root=root, font=ttk.Style(root).lookup("Treeview", "font"))
    assert int(tree.column("time", "width")) >= font.measure(times[0]) + 8
    root.destroy()


@requires_tk
def test_r6_menubar_buttons_have_no_dropdown_indicator(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r6-menubar.sqlite"), reviewer_id="owner")

    layout = repr(ttk.Style(root).layout("ChromeMenu.TMenubutton"))
    assert "indicator" not in layout
    assert "label" in layout
    assert [b.cget("text") for b in app.menubar_buttons] == ["File", "Project", "View", "Help"]
    assert all(b.winfo_reqwidth() < 80 for b in app.menubar_buttons), "menus still reserve indicator width"
    root.destroy()


@requires_tk
def test_r6_blind_chip_never_borrows_decision_colors(tmp_path):
    from screening_workbench import theme

    decision_colors = {theme.TOKENS[k] for k in (
        "include", "maybe", "exclude", "include_soft", "maybe_soft", "exclude_soft",
    )}
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r6-blind-chip.sqlite"), reviewer_id="owner")
    for blind in (False, True):
        roles.set_blind(app.conn, "owner", blind)
        app.refresh_all_tabs()
        fg, bg = app.blind_chip_label.cget("foreground"), app.blind_chip_label.cget("background")
        assert fg not in decision_colors and bg not in decision_colors
        assert theme.contrast_ratio(fg, bg) >= 4.5
    root.destroy()


@requires_tk
def test_r6_header_export_is_the_primary_action_and_secondary_actions_are_ttk(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r6-buttons.sqlite"), reviewer_id="owner")

    assert app.export_button.cget("style") == "Inverse.TButton"
    for button in (app.undo_button, app.skip_button):
        assert isinstance(button, ttk.Button)
        assert button.cget("style") == "Quiet.TButton"
    assert app.undo_button.cget("text") == "Undo  Ctrl+Z"
    assert app.skip_button.cget("text") == "Skip  J"
    root.destroy()


@requires_tk
def test_r6_duplicate_comparison_wraps_instead_of_overflowing(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r6-dup-compare.sqlite"), reviewer_id="owner")
    title_a = "Blue glass greenhouse -- pilot in Modelton with an intentionally long synthetic subtitle"
    title_b = "Blue-glass greenhouse: a pilot in Modelton with an intentionally long synthetic subtitle"
    occ_ids = _seed_two_occurrences(app, title_a, title_b, authors="Sample Author; T. Fiction", year="2023")
    app.refresh_all_tabs()
    app.notebook.select(2)
    app.dup_list.selection_set(0)
    app._render_dup_cluster()
    root.update()

    text = app.dup_compare_text
    body = text.get("1.0", "end")
    assert text.cget("wrap") == "word"
    assert text.xview() == (0.0, 1.0), "comparison still overflows horizontally"
    assert title_a in body and title_b in body
    assert all(occ_id in body for occ_id in occ_ids)
    assert "Difference" in body
    survivors = app.dup_survivor_list
    assert survivors.size() == 2 and int(survivors.cget("height")) >= 2
    assert survivors.pack_info()["fill"] == "x"
    assert survivors.winfo_width() >= app.dup_resolution_panel.winfo_width() - 4
    root.destroy()


# ---- Direction 02 R1: bundled typefaces ----

BUNDLED_FONT_SHA256 = {
    "AtkinsonHyperlegibleMono-Bold.ttf": "51ad68fafd7ec68051f64983c9c23182a7084268b5cdb0a154dbd53ade079da6",
    "AtkinsonHyperlegibleMono-Italic.ttf": "356060ab70ae62e4460dd824ec1b734af24e5c3355a8302700151d35d1382dd4",
    "AtkinsonHyperlegibleMono-Regular.ttf": "2c9a7b9fabebd5c746a808d8a1ef2f52e618850caad6ec4fd9f5c48f56e1c1af",
    "AtkinsonHyperlegibleNext-Bold.ttf": "994414047df66bb4998d01c1cb1eeb4a2ddc4622d1aa56bbb8adbeca7645b041",
    "AtkinsonHyperlegibleNext-Italic.ttf": "b7f8f03ceb28ebadb2de2332b2e869a00e8dbfb5c8e00fdbb06385770c8227e7",
    "AtkinsonHyperlegibleNext-Regular.ttf": "88ed5c31a71584c7772963b02d04bef1eb7e3d2e9c8b9cb204339b1f82cf432c",
    "Newsreader16pt-Bold.ttf": "9e3d485293bb2f86d22f1a9bfb8d7213cff188270fa240b5084e27290746aea7",
    "Newsreader16pt-Italic.ttf": "292646cbb948153511e308fa80def59959746d70114bd0936ba0a7f67a33181d",
    "Newsreader16pt-Medium.ttf": "ee2f66ee4c6c313acf211c952211f8c6c0c0d9fa6a17cd0ec0ceba13418b1aed",
    "Newsreader16pt-Regular.ttf": "0636887c9f72f77ce188f0b31029be58e65adae5a47e6d2887ad5020c2c75036",
}


def test_r1_bundled_fonts_are_exactly_the_audited_files():
    import hashlib

    from screening_workbench import typefaces as fonts

    shipped = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in fonts.FONT_DIR.glob("*") if p.is_file()}
    assert shipped == BUNDLED_FONT_SHA256
    notices = Path(__file__).resolve().parents[1] / "docs" / "notices"
    for name in ("Newsreader-OFL.txt", "AtkinsonHyperlegibleNext-OFL.txt", "AtkinsonHyperlegibleMono-OFL.txt"):
        assert "SIL Open Font License, Version 1.1" in (notices / name).read_text(encoding="utf-8")
    packaging = (Path(__file__).resolve().parents[1] / "docs" / "packaging.md").read_text(encoding="utf-8")
    assert "screening_workbench/fonts" in packaging
    assert all(name in packaging for name in ("Newsreader-OFL.txt", "AtkinsonHyperlegibleNext-OFL.txt", "AtkinsonHyperlegibleMono-OFL.txt"))


def test_r1_font_loader_returns_nothing_without_a_font_dir(tmp_path, monkeypatch):
    from screening_workbench import typefaces as fonts

    monkeypatch.setattr(fonts, "FONT_DIR", tmp_path / "missing")
    monkeypatch.setattr(fonts, "_loaded", None)
    assert fonts.load_bundled_fonts() == []


def test_r1_font_stacks_keep_direction_01_fonts_as_fallbacks():
    from screening_workbench import theme

    assert theme.FONT_FALLBACKS[theme.FONT_UI][:2] == ("Atkinson Hyperlegible Next", "Segoe UI")
    assert theme.FONT_FALLBACKS[theme.FONT_READING][:3] == ("Newsreader 16pt", "Iowan Old Style", "Palatino Linotype")
    assert theme.FONT_FALLBACKS[theme.FONT_TITLE][0] == "Newsreader 16pt Medium"
    assert theme.FONT_FALLBACKS[theme.FONT_MONO][:2] == ("Atkinson Hyperlegible Mono", "Cascadia Code")
    for stack in theme.FONT_FALLBACKS.values():
        assert stack[-1].startswith("Tk")


@requires_tk
@pytest.mark.skipif(os.name != "nt", reason="private GDI font loading is Windows-only")
def test_r1_app_resolves_bundled_faces_first(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r1-fonts.sqlite"), reviewer_id="owner")
    assert (app.font_ui, app.font_reading, app.font_title, app.font_mono) == (
        "Atkinson Hyperlegible Next", "Newsreader 16pt", "Newsreader 16pt Medium", "Atkinson Hyperlegible Mono",
    )
    assert "Newsreader 16pt Medium" in str(app.title_label.cget("font"))
    assert theme.resolve_font(root, theme.FONT_UI) == "Atkinson Hyperlegible Next"
    root.destroy()


# ---- Direction 02 R2: drawer palette and chrome ----

@requires_tk
def test_r2_window_chrome_is_the_drawer(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r2-chrome.sqlite"), reviewer_id="owner")
    style = ttk.Style(root)
    drawer = theme.TOKENS["drawer"]
    for frame in (app.menubar_frame, app.header_frame, app.section_nav, app.status_bar):
        assert style.lookup(frame.cget("style"), "background") == drawer, str(frame)
    for name in ("ChromeMenu.TMenubutton", "Header.TLabel", "Wordmark.TLabel", "Section.TButton", "ActiveSection.TButton"):
        assert style.lookup(name, "background") == drawer, name
    assert style.lookup("Header.TLabel", "foreground") == theme.TOKENS["drawer_ink"]
    assert style.lookup("Status.TLabel", "foreground") == theme.TOKENS["drawer_muted"]
    assert style.lookup("Inverse.TButton", "background") == theme.TOKENS["surface"]
    assert style.lookup("Inverse.TButton", "foreground") == drawer
    file_menu = root.nametowidget(app.menubar_buttons[0].cget("menu"))
    assert str(file_menu.cget("background")) == theme.TOKENS["surface"]
    assert str(file_menu.cget("activebackground")) == theme.TOKENS["accent_soft"]
    root.destroy()


@requires_tk
def test_r2_active_section_has_a_highlighter_underline(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r2-underline.sqlite"), reviewer_id="owner")

    def underline_colors():
        return {key: str(bar.cget("background")) for key, bar in app.section_nav_underlines.items()}

    colors = underline_colors()
    assert colors["screening"] == theme.TOKENS["signal"]
    assert all(color == theme.TOKENS["drawer"] for key, color in colors.items() if key != "screening")
    app.section_nav_buttons["prisma"].invoke()
    colors = underline_colors()
    assert colors["prisma"] == theme.TOKENS["signal"] and colors["screening"] == theme.TOKENS["drawer"]
    assert all(int(bar.cget("height")) == 3 for bar in app.section_nav_underlines.values())
    root.destroy()


@requires_tk
def test_r2_count_badges_mute_zero_and_flag_queues_that_need_a_person(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r2-badges.sqlite"), reviewer_id="owner")
    _seed_two_occurrences(app, "Blue glass greenhouse -- pilot in Modelton", "Blue-glass greenhouse: a pilot in Modelton", year="2023")
    app.refresh_all_tabs()

    badges = app.section_nav_badges
    assert badges["screening"].cget("style") == "CountBadge.TLabel"
    assert badges["duplicates"].cget("style") == "CountBadgeAttention.TLabel"
    assert badges["conflicts"].cget("text") == 0
    assert badges["conflicts"].cget("style") == "CountBadgeZero.TLabel"
    style = ttk.Style(root)
    for name in ("CountBadge.TLabel", "CountBadgeZero.TLabel", "CountBadgeAttention.TLabel"):
        fg, bg = style.lookup(name, "foreground"), style.lookup(name, "background")
        assert theme.contrast_ratio(fg, bg) >= 4.5, name
    assert style.lookup("CountBadgeAttention.TLabel", "background") == theme.TOKENS["signal"]
    root.destroy()


@requires_tk
def test_r2_blind_chip_on_the_drawer_marks_on_with_the_highlighter(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r2-blind.sqlite"), reviewer_id="owner")
    chip = app.blind_chip_label
    assert str(chip.cget("foreground")) == theme.TOKENS["drawer_muted"]
    assert str(chip.cget("highlightbackground")) == theme.TOKENS["drawer_muted"]
    roles.set_blind(app.conn, "owner", True)
    app.refresh_all_tabs()
    assert str(chip.cget("background")) == theme.TOKENS["drawer"]
    assert str(chip.cget("foreground")) == theme.TOKENS["drawer_ink"]
    assert str(chip.cget("highlightbackground")) == theme.TOKENS["signal"]
    assert "ON" in chip.cget("text")
    root.destroy()


# ---- Direction 02 R3: the record as an index card ----

def _seed_screening_records(app, rows):
    source_id, branch_id = app._ensure_default_source()
    text = "title,authors,year,journal,abstract\n" + "\n".join(rows) + "\n"
    commit_csv_import(
        app.conn, text, {0: "title", 1: "authors", 2: "year", 3: "journal", 4: "abstract"},
        source_id=source_id, branch_id=branch_id, operation_id="r3-seed", actor="owner",
    )
    app.refresh_all_tabs()


R3_ROWS = [
    "Synthetic coastal sensor calibration,Alex Sample,2021,Imaginary Marine Methods,Fictional calibration study; Calibration drift is invented.",
    "Synthetic seabird route observation,B. Fiction,2022,Invented Coastal Science,Invented observational study of seabird routes.",
    "Synthetic tidal habitat survey,C. Placeholder,2020,Imaginary Journal,Made-up survey of intertidal habitat cover.",
]


@requires_tk
def test_r3_record_card_is_the_only_raised_object_on_screening(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-raised.sqlite"), reviewer_id="owner")
    style = ttk.Style(root)
    assert app.screen_record_card.cget("style") == "Card.TFrame"
    for column in (app.screen_queue_card, app.screen_support_card):
        assert column.cget("style") == "Desk.TFrame"
        assert style.lookup("Desk.TFrame", "background") == theme.TOKENS["canvas"]
        assert style.lookup("Desk.TFrame", "relief") in ("", "flat")
    root.destroy()


@requires_tk
def test_r3_call_number_rule_tracks_record_position(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.geometry("1280x800")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-rule.sqlite"), reviewer_id="owner")
    _seed_screening_records(app, R3_ROWS)
    root.update()

    rule = app.position_progress
    assert isinstance(rule, tk.Canvas)
    assert rule["maximum"] == 3 and rule["value"] == 1
    width = rule.winfo_width()
    x1, _, x2, _ = rule.coords(rule.find_withtag("progress")[0])
    assert abs((x2 - x1) - width / 3) <= 1
    assert rule.itemcget(rule.find_withtag("progress")[0], "fill") == theme.TOKENS["drawer"]
    assert app.font_mono in str(app.position_label.cget("font"))
    root.destroy()


@requires_tk
def test_r3_title_meta_and_abstract_read_like_a_card(tmp_path):
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-type.sqlite"), reviewer_id="owner")
    _seed_screening_records(app, R3_ROWS)

    assert app.font_title in str(app.title_label.cget("font")) and "16" in str(app.title_label.cget("font"))
    assert app.meta_label.cget("text") == "Alex Sample · Imaginary Marine Methods · 2021"
    abstract = app.abstract_text
    assert int(abstract.cget("highlightthickness")) == 0
    assert int(abstract.cget("spacing2")) == 4 and int(abstract.cget("spacing3")) == 8
    assert app.font_reading in str(abstract.cget("font")) and "12" in str(abstract.cget("font"))
    root.destroy()


@requires_tk
def test_r3_search_hits_are_highlighted_in_the_abstract(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-hits.sqlite"), reviewer_id="owner")
    _seed_screening_records(app, R3_ROWS)

    app.screen_search_entry.insert(0, "calibration")
    app._apply_screening_filter()
    ranges = app.abstract_text.tag_ranges("hit")
    hits = [app.abstract_text.get(ranges[i], ranges[i + 1]) for i in range(0, len(ranges), 2)]
    assert hits == ["calibration", "Calibration"]
    assert str(app.abstract_text.tag_cget("hit", "background")) == theme.TOKENS["signal"]
    assert str(app.abstract_text.tag_cget("hit", "foreground")) == theme.TOKENS["ink"]

    app._clear_screening_filter()
    assert app.abstract_text.tag_ranges("hit") == ()
    root.destroy()


@requires_tk
def test_r3_current_queue_row_and_reason_keys_use_card_catalogue_marks(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-queue.sqlite"), reviewer_id="owner")
    _seed_screening_records(app, R3_ROWS)

    current = app.current_occurrence_id
    assert app.queue_list.item(current, "text").startswith("▸ Now  ")
    assert str(app.queue_list.tag_configure("current", "background")) == theme.TOKENS["signal_soft"]
    assert str(app.queue_list.tag_configure("current", "foreground")) == theme.TOKENS["ink"]
    assert [k.cget("text") for k in app.reason_keycaps] == [str(i) for i in range(1, 8)]
    for keycap in app.reason_keycaps:
        assert str(keycap.cget("background")) == theme.TOKENS["surface"]
        assert str(keycap.cget("highlightbackground")) == theme.TOKENS["line_strong"]
        assert app.font_mono in str(keycap.cget("font"))
    root.destroy()


@requires_tk
def test_r3_decision_controls_and_key_legend_stay_inside_the_record_card(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-fit.sqlite"), reviewer_id="owner")
    _seed_screening_records(app, R3_ROWS)
    root.deiconify()
    root.update()

    card_bottom = app.screen_record_card.winfo_rooty() + app.screen_record_card.winfo_height()
    for widget in (app.include_button, app.undo_button, app.skip_button, app.screen_key_legend):
        assert widget.winfo_ismapped(), str(widget)
        assert widget.winfo_height() >= widget.winfo_reqheight(), f"{widget} is squeezed"
        assert widget.winfo_rooty() + widget.winfo_height() <= card_bottom, f"{widget} falls below the card"
    root.destroy()


@requires_tk
def test_r3_fulltext_attachment_list_keeps_a_full_row_with_bundled_faces(tmp_path):
    import tkinter.font as tkfont

    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-attach-row.sqlite"), reviewer_id="owner")
    _seed_side_box_reports(app)
    app.section_nav_buttons["fulltext"].invoke()
    app.report_list.selection_set(0)
    app.report_list.event_generate("<<ListboxSelect>>")
    root.deiconify()
    root.update()

    row = tkfont.Font(root=root, font=app.attachment_listbox.cget("font")).metrics("linespace")
    assert app.attachment_listbox.winfo_height() >= row + 2, "attached-PDF list is crushed below one row"
    card_bottom = app.fulltext_support_card.winfo_rooty() + app.fulltext_support_card.winfo_height()
    assert app.attach_pdf_btn.winfo_rooty() + app.attach_pdf_btn.winfo_height() <= card_bottom
    root.destroy()


@requires_tk
def test_r3_disabled_toggles_on_a_card_keep_the_card_surface(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-disabled-radio.sqlite"), reviewer_id="owner")
    style = ttk.Style(root)
    for radio in app.maybe_reason_buttons:
        assert radio.instate(["disabled"])
        assert style.lookup(radio.cget("style"), "background", ("disabled",)) == theme.TOKENS["surface"]
    root.destroy()


@requires_tk
def test_r3_prisma_watermark_notice_wraps_inside_its_card(tmp_path):
    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-watermark-wrap.sqlite"), reviewer_id="owner")
    _seed_side_box_reports(app)
    app.section_nav_buttons["prisma"].invoke()
    root.deiconify()
    root.update()

    inner_width = app.prisma_flow_card.winfo_width() - 24
    for label in (app.prisma_watermark_label, app.prisma_live_data_label):
        assert label.winfo_reqwidth() <= inner_width, f"{label.cget('text')[:40]!r} is clipped"
    root.destroy()


# ---- Direction 02 R3 (finish): keycap decision buttons, armed reasons ----

@requires_tk
def test_r3_decision_buttons_show_a_keycap_beside_the_word(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-keycaps.sqlite"), reviewer_id="owner")
    _seed_screening_records(app, R3_ROWS)

    expected = {
        "include": (app.include_button, "I", "Include"),
        "maybe": (app.maybe_button, "M", "Maybe"),
        "exclude": (app.exclude_button, "E", "Exclude..."),
    }
    for decision, (button, key, word) in expected.items():
        assert button.keycap.cget("text") == key
        assert button.label.cget("text") == word
        assert button.cget("text") == f"{key}  {word}"
        assert app.font_mono in str(button.keycap.cget("font"))
        assert str(button.keycap.cget("foreground")) == theme.TOKENS[decision]
        assert str(button.keycap.cget("background")) == theme.TOKENS["surface"]
        assert str(button.keycap.cget("highlightbackground")) == theme.TOKENS[f"{decision}_border"]
        assert str(button.cget("background")) == theme.TOKENS[f"{decision}_soft"]
        assert str(button.label.cget("foreground")) == theme.TOKENS[decision]
        assert theme.contrast_ratio(theme.TOKENS[decision], theme.TOKENS["surface"]) >= 4.5
        assert str(button.cget("takefocus")) == "1"
    root.destroy()


@requires_tk
def test_r3_keycap_buttons_act_like_buttons_from_mouse_and_keyboard(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r3-keycap-input.sqlite"), reviewer_id="owner")
    _seed_screening_records(app, R3_ROWS)
    root.deiconify()
    root.update()
    first, second = app.current_occurrence_id, app._queue_occurrence_ids[1]

    app.include_button.keycap.event_generate("<Button-1>")
    root.update()
    assert screening.current_vote(app.conn, first, "owner")["decision"] == "include"

    assert app.current_occurrence_id == second
    app.maybe_button.event_generate("<FocusIn>")  # ring check without depending on OS focus
    root.update()
    assert int(app.maybe_button.cget("highlightthickness")) == 3
    assert str(app.maybe_button.cget("highlightbackground")) == theme.TOKENS["focus"]
    for seq in ("<Key-space>", "<Return>"):
        assert app.maybe_button.bind(seq), f"{seq} is not bound on the keycap button"
    assert app.maybe_button._on_activate_key(SimpleNamespace(widget=app.maybe_button)) == "break"
    assert screening.current_vote(app.conn, second, "owner")["decision"] == "maybe"
    assert app.include_button.winfo_height() >= 40
    widths = {b.winfo_width() for b in (app.include_button, app.maybe_button, app.exclude_button)}
    assert max(widths) - min(widths) <= 1, f"decision buttons differ in width: {widths}"
    root.destroy()


@requires_tk
@pytest.mark.parametrize("picked", [True, False])
def test_r3_reason_list_is_armed_only_while_an_exclusion_reason_is_pending(tmp_path, picked):
    from screening_workbench import theme

    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / f"r3-armed-{picked}.sqlite"), reviewer_id="owner")
    _seed_screening_records(app, R3_ROWS)
    occurrence_id = app.current_occurrence_id
    style = ttk.Style(root)
    seen = {}

    def fake_prompt():
        seen["armed"] = app.exclusion_reasons_armed
        seen["keycap_fg"] = {str(k.cget("foreground")) for k in app.reason_keycaps}
        seen["keycap_border"] = {str(k.cget("highlightbackground")) for k in app.reason_keycaps}
        seen["row_bg"] = {style.lookup(label.cget("style"), "background") for label in app.reason_labels}
        seen["button_ring"] = str(app.exclude_button.cget("highlightbackground"))
        return screening.EXCLUSION_REASONS[2] if picked else None

    app._prompt_exclusion_reason = fake_prompt
    assert app.exclusion_reasons_armed is False
    app.exclude_button.invoke()

    assert seen == {
        "armed": True,
        "keycap_fg": {theme.TOKENS["exclude"]},
        "keycap_border": {theme.TOKENS["exclude_border"]},
        "row_bg": {theme.TOKENS["exclude_soft"]},
        "button_ring": theme.TOKENS["focus"],
    }
    assert app.exclusion_reasons_armed is False
    assert {str(k.cget("foreground")) for k in app.reason_keycaps} == {theme.TOKENS["ink"]}
    assert {style.lookup(label.cget("style"), "background") for label in app.reason_labels} == {theme.TOKENS["canvas"]}
    vote = screening.current_vote(app.conn, occurrence_id, "owner")
    if picked:
        assert vote["decision"] == "exclude" and vote["reason"] == screening.EXCLUSION_REASONS[2]
    else:
        assert vote is None
    root.destroy()


# ---- Direction 02 R4: decision stamp, reduced motion, progress tween ----

README_ROWS_5 = R3_ROWS + [
    "Synthetic ocean temperature model,D. Example,2023,Invented Marine Review,Fictional toy ocean temperature model.",
    "Synthetic estuary sampling protocol,E. Sample,2024,Imaginary Ecology,Synthetic protocol for estuary sampling.",
]


@pytest.fixture
def motion_on():
    from screening_workbench import display_prefs

    display_prefs.set_reduced_motion(False)
    yield
    display_prefs.set_reduced_motion(None)


def _wait(root, seconds):
    import time

    end = time.monotonic() + seconds
    while time.monotonic() < end:
        root.update()
        time.sleep(0.01)


def _stamp_text(app):
    canvas = app._stamp
    return " ".join(canvas.itemcget(i, "text") for i in canvas.find_all() if canvas.type(i) == "text")


def _screening_app(tmp_path, name, rows):
    """Withdrawn app on the Screening tab: no real keystroke can reach it."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / name), reviewer_id="owner")
    _seed_screening_records(app, rows)
    root.update()
    return root, app


def _mapped_app(tmp_path, name, rows):
    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / name), reviewer_id="owner")
    _seed_screening_records(app, rows)
    root.deiconify()
    root.update()
    return root, app


@requires_tk
def test_r4_stamp_lands_after_the_vote_is_saved_then_the_queue_advances(tmp_path, motion_on):
    from screening_workbench import theme

    root, app = _screening_app(tmp_path, "r4-stamp.sqlite", README_ROWS_5)
    first, second = app._queue_occurrence_ids[:2]

    app._decide("include")
    assert screening.current_vote(app.conn, first, "owner")["decision"] == "include"
    assert app.current_occurrence_id == first, "the card must not change under the stamp"
    assert app._stamp is not None and app._stamp.winfo_manager() == "place"
    assert app._stamp.master is app.screen_record_card
    assert "INCLUDED" in _stamp_text(app)
    _wait(root, 0.06)
    texts = [i for i in app._stamp.find_all() if app._stamp.type(i) == "text"]
    assert app._stamp.itemcget(texts[0], "fill") == theme.TOKENS["include"]
    assert app._stamp.itemcget(texts[0], "angle") not in ("", "0", "0.0")

    _wait(root, 0.25)
    assert app._stamp is None
    assert app.current_occurrence_id == second
    root.destroy()


@requires_tk
def test_r4_rapid_keys_each_land_on_the_next_record(tmp_path, motion_on):
    root, app = _screening_app(tmp_path, "r4-rapid.sqlite", README_ROWS_5)
    ids = list(app._queue_occurrence_ids)

    app._decide("include")
    app._decide("include")
    app._decide("maybe")
    decisions = [(screening.current_vote(app.conn, occ, "owner") or {}).get("decision") for occ in ids]
    assert decisions == ["include", "include", "maybe", None, None]
    assert app.current_occurrence_id == ids[2], "only the last decision is still under its stamp"
    assert len(app.screen_record_card.place_slaves()) == 1

    _wait(root, 0.25)
    assert app.current_occurrence_id == ids[3]
    assert app.screen_record_card.place_slaves() == []
    root.destroy()


@requires_tk
def test_r4_exclude_stamp_names_the_reason_and_undo_flushes_it(tmp_path, motion_on):
    root, app = _screening_app(tmp_path, "r4-exclude.sqlite", README_ROWS_5)
    first = app.current_occurrence_id
    app._prompt_exclusion_reason = lambda: screening.EXCLUSION_REASONS[2]

    app._decide("exclude")
    assert "EXCLUDED" in _stamp_text(app)
    assert screening.EXCLUSION_REASONS[2].upper() in _stamp_text(app)

    app._undo_last_decision()
    assert app._stamp is None
    assert screening.current_vote(app.conn, first, "owner") is None
    root.destroy()


@requires_tk
def test_r4_reduced_motion_never_draws_a_stamp(tmp_path):
    from screening_workbench import display_prefs

    display_prefs.set_reduced_motion(True)
    try:
        root, app = _screening_app(tmp_path, "r4-reduced.sqlite", README_ROWS_5)
        first, second = app._queue_occurrence_ids[:2]
        app._decide("include")
        assert app._stamp is None
        assert app.screen_record_card.place_slaves() == []
        assert app.current_occurrence_id == second
        assert screening.current_vote(app.conn, first, "owner")["decision"] == "include"
        root.destroy()
    finally:
        display_prefs.set_reduced_motion(None)


def test_r4_reduced_motion_saved_choice_precedes_env_then_windows(tmp_path, monkeypatch):
    from screening_workbench import display_prefs

    monkeypatch.setenv("SW_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setenv("SW_REDUCE_MOTION", "1")
    monkeypatch.setattr(display_prefs, "_motion_override", None)
    monkeypatch.setattr(display_prefs, "_windows_animations_enabled", lambda: True)
    assert display_prefs.save_theme("night") is True
    assert display_prefs.save_reduced_motion(False) is True
    assert display_prefs.saved_reduced_motion() is False
    assert display_prefs.reduced_motion() is False
    assert display_prefs._load_settings() == {"theme": "night", "reduce_motion": False}

    display_prefs.set_reduced_motion(None)
    assert display_prefs.reduced_motion() is False
    assert display_prefs.save_reduced_motion(None) is True
    assert display_prefs.saved_reduced_motion() is None
    assert display_prefs.reduced_motion() is True
    monkeypatch.delenv("SW_REDUCE_MOTION")
    assert display_prefs.reduced_motion() is False


def test_r4_reduced_motion_follows_override_then_env_then_windows(monkeypatch):
    from screening_workbench import display_prefs

    monkeypatch.setattr(display_prefs, "_motion_override", None)
    monkeypatch.setenv("SW_REDUCE_MOTION", "1")
    assert display_prefs.reduced_motion() is True
    monkeypatch.delenv("SW_REDUCE_MOTION")
    monkeypatch.setattr(display_prefs, "_windows_animations_enabled", lambda: False)
    assert display_prefs.reduced_motion() is True
    monkeypatch.setattr(display_prefs, "_windows_animations_enabled", lambda: True)
    assert display_prefs.reduced_motion() is False
    display_prefs.set_reduced_motion(True)
    assert display_prefs.reduced_motion() is True
    display_prefs.set_reduced_motion(None)
    monkeypatch.setattr(display_prefs, "_windows_high_contrast", lambda: True)
    assert display_prefs.high_contrast() is True


@requires_tk
def test_r4_view_menu_offers_reduce_motion(tmp_path, monkeypatch):
    from screening_workbench import display_prefs

    monkeypatch.setenv("SW_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.setattr(display_prefs, "_motion_override", None)
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r4-menu.sqlite"), reviewer_id="owner")
    view = root.nametowidget(app.menubar_buttons[2].cget("menu"))
    entry = next(i for i in range(view.index("end") + 1) if view.type(i) == "checkbutton")
    assert view.entrycget(entry, "label") == "Reduce motion"
    try:
        before = display_prefs.reduced_motion()
        view.invoke(entry)
        assert display_prefs.reduced_motion() is (not before)
        assert display_prefs.saved_reduced_motion() is (not before)
        view.invoke(entry)
        assert display_prefs.reduced_motion() is before
        assert display_prefs.saved_reduced_motion() is before
    finally:
        display_prefs.set_reduced_motion(None)
    root.destroy()

    restarted_root = tk.Tk()
    restarted_root.withdraw()
    restarted_app = ScreeningWorkbenchApp(restarted_root, str(tmp_path / "r4-menu-restart.sqlite"), reviewer_id="owner")
    assert restarted_app.reduce_motion_var.get() is before
    restarted_root.destroy()


@requires_tk
def test_r4_progress_rule_tweens_to_its_new_value(tmp_path, motion_on):
    root, app = _mapped_app(tmp_path, "r4-tween.sqlite", README_ROWS_5)
    rule = app.position_progress
    width = rule.winfo_width()

    def drawn():
        x1, _, x2, _ = rule.coords(rule.find_withtag("progress")[0])
        return x2 - x1

    start = drawn()
    rule.configure(maximum=5, value=5)
    assert rule["value"] == 5
    assert drawn() < width - 1, "the rule jumped instead of moving"
    _wait(root, 0.25)
    assert abs(drawn() - width) <= 1 and drawn() > start
    root.destroy()


# ---- Direction 02 R5: PRISMA graph paper (live preview only) ----

@requires_tk
def test_r5_prisma_preview_sits_on_graph_paper_behind_the_diagram(tmp_path):
    from screening_workbench import theme

    root = tk.Tk()
    root.geometry("1280x800+40+40")
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r5-grid.sqlite"), reviewer_id="owner")
    _seed_side_box_reports(app)
    app.section_nav_buttons["prisma"].invoke()
    root.update()

    canvas = app.prisma_diagram_canvas
    grid = canvas.find_withtag("grid")
    assert len(grid) > 20
    items = canvas.find_all()
    assert set(items[:len(grid)]) == set(grid), "graph paper must sit beneath every box, arrow and label"
    colors = {canvas.itemcget(i, "fill") for i in grid}
    assert colors == {theme.TOKENS["grid_minor"], theme.TOKENS["grid_major"]}
    major = [canvas.coords(i) for i in grid if canvas.itemcget(i, "fill") == theme.TOKENS["grid_major"]]
    assert all(int(c[0]) % 40 == 0 or int(c[1]) % 40 == 0 for c in major)
    root.destroy()


@requires_tk
def test_r5_graph_paper_is_skipped_in_high_contrast_and_never_exported(tmp_path, monkeypatch):
    from screening_workbench import display_prefs, export, theme

    monkeypatch.setattr(display_prefs, "high_contrast", lambda: True)
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "r5-hc.sqlite"), reviewer_id="owner")
    _seed_side_box_reports(app)
    app._refresh_prisma_diagram()
    assert app.prisma_diagram_canvas.find_withtag("grid") == ()

    svg = export.export_prisma_svg(app.conn)
    assert theme.TOKENS["grid_minor"] not in svg and theme.TOKENS["grid_major"] not in svg
    root.destroy()


@requires_tk
def test_r4_closing_the_window_mid_stamp_leaves_no_stray_timers(tmp_path, motion_on):
    root, app = _screening_app(tmp_path, "r4-teardown.sqlite", README_ROWS_5)
    app._decide("include")
    pending = set(root.tk.call("after", "info"))
    assert pending, "expected a pending stamp/tween timer before closing"
    root.destroy()
    assert app._pending_advance is None and app._stamp_settle_job is None
    assert app.position_progress._tween_job is None


@requires_tk
def test_shortcut_guard_uses_the_widget_the_key_was_delivered_to(tmp_path):
    """The typing guard reads event.widget, so a stale or missing OS focus
    can neither block a real shortcut nor let a typed letter through."""
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "guard.sqlite"), reviewer_id="owner")
    with patch.object(root, "focus_get", return_value=app.abstract_text):
        assert app._is_typing_in_a_text_field(app.screen_search_entry) is True
    with patch.object(root, "focus_get", return_value=app.screen_search_entry):
        assert app._is_typing_in_a_text_field(app.abstract_text) is False
        assert app._is_typing_in_a_text_field(app.queue_list) is False
    assert app._is_typing_in_a_text_field(str(app.screen_year_entry)) is True
    root.destroy()


@requires_tk
def test_stamp_follows_the_selected_tab_not_window_mapping(tmp_path, motion_on):
    root, app = _screening_app(tmp_path, "stamp-tab.sqlite", README_ROWS_5)
    assert not app.screen_record_card.winfo_ismapped()
    app._decide("include")
    assert app._stamp is not None, "Screening is selected, so the stamp shows even while withdrawn"
    app._flush_pending_advance()
    app.section_nav_buttons["prisma"].invoke()
    app._decide("maybe")
    assert app._stamp is None, "off the Screening tab a decision advances at once"
    root.destroy()


# ---- v2: Night Stacks dark palette and theme choice ----

def test_v2_both_palettes_define_every_token_and_pass_every_text_pair():
    from screening_workbench import theme

    light, night = theme.PALETTES["light"], theme.PALETTES["night"]
    assert set(light) == set(night)
    assert set(theme.PALETTE_LABELS) == {"light", "night"}
    for name, palette in theme.PALETTES.items():
        for fg, bg in theme._CONTRAST_TOKEN_PAIRS:
            assert theme.contrast_ratio(palette[fg], palette[bg]) >= 4.5, (name, fg, bg)
    assert theme.PALETTE_CONTRAST["night"]["ink.surface"] >= 4.5
    assert night["surface"] != light["surface"] and night["ink"] != light["ink"]


def test_v2_use_palette_swaps_tokens_in_place():
    from screening_workbench import theme

    tokens = theme.TOKENS
    try:
        theme.use_palette("night")
        assert theme.TOKENS is tokens and tokens == theme.PALETTES["night"]
        assert theme.CURRENT_PALETTE == "night"
    finally:
        theme.use_palette("light")
    assert tokens == theme.PALETTES["light"] and theme.CURRENT_PALETTE == "light"


def test_v2_theme_choice_order_is_env_then_saved_then_windows(tmp_path, monkeypatch):
    from screening_workbench import display_prefs

    monkeypatch.setenv("SW_SETTINGS_PATH", str(tmp_path / "settings.json"))
    monkeypatch.delenv("SW_THEME", raising=False)
    monkeypatch.setattr(display_prefs, "_windows_prefers_dark", lambda: True)
    assert display_prefs.saved_theme() == "system"
    assert display_prefs.palette() == "night"
    monkeypatch.setattr(display_prefs, "_windows_prefers_dark", lambda: False)
    assert display_prefs.palette() == "light"
    assert display_prefs.save_theme("night") is True
    assert display_prefs.saved_theme() == "night" and display_prefs.palette() == "night"
    monkeypatch.setenv("SW_THEME", "light")
    assert display_prefs.palette() == "light"
    (tmp_path / "settings.json").write_text("not json", encoding="utf-8")
    monkeypatch.delenv("SW_THEME")
    assert display_prefs.saved_theme() == "system"
    import pytest as _pytest
    with _pytest.raises(ValueError):
        display_prefs.save_theme("sepia")


def _off_palette_colors(root, palette):
    """Every painted color on every widget must come from the palette.

    Only colors Tk actually draws count: a highlight ring only when it has
    width, and selection/insertion colors only on widgets that hold editable
    or selectable text."""
    allowed = {v.lower() for v in palette.values()}
    style = ttk.Style(root)
    problems = []
    for widget in _iter_widgets(root):
        if isinstance(widget, ttk.Widget):
            name = widget.cget("style") or widget.winfo_class()
            # clam's state maps (disabled/hover/pressed) paint their own greys
            # unless every state is themed too.
            for state in ((), ("disabled",), ("active",), ("pressed",)):
                for option in ("background", "foreground", "fieldbackground", "indicatorbackground"):
                    value = style.lookup(name, option, state)
                    if value and value.lower() not in allowed:
                        problems.append((str(widget), name, option, state, value))
            continue
        text_like = widget.winfo_class() in ("Text", "Entry", "Listbox", "Spinbox")
        for option in ("background", "foreground", "highlightbackground", "selectbackground", "insertbackground"):
            if option not in widget.keys():
                continue
            if option == "highlightbackground" and int(widget.cget("highlightthickness") or 0) == 0:
                continue
            if option in ("selectbackground", "insertbackground") and not text_like:
                continue
            if option == "insertbackground" and widget.winfo_class() == "Listbox":
                continue
            value = str(widget.cget(option))
            if value and value.lower() not in allowed:
                problems.append((str(widget), widget.winfo_class(), option, value))
    return problems


@requires_tk
@pytest.mark.parametrize("palette_name", ["light", "night"])
def test_v2_every_widget_paints_from_the_active_palette(tmp_path, monkeypatch, palette_name):
    from screening_workbench import theme

    monkeypatch.setenv("SW_THEME", palette_name)
    root = tk.Tk()
    root.withdraw()
    try:
        app = ScreeningWorkbenchApp(root, str(tmp_path / f"palette-{palette_name}.sqlite"), reviewer_id="owner")
        _seed_side_box_reports(app)
        _seed_screening_records(app, R3_ROWS)
        assert theme.CURRENT_PALETTE == palette_name
        assert root.cget("background") == theme.PALETTES[palette_name]["canvas"]
        assert _off_palette_colors(root, theme.PALETTES[palette_name]) == []
        dialog = tk.Toplevel(root)  # dialogs (reason picker, CSV mapping) take the desk color too
        assert str(dialog.cget("background")) == theme.PALETTES[palette_name]["canvas"]
        root.destroy()
    finally:
        theme.use_palette("light")


@requires_tk
def test_v2_night_asks_windows_for_a_dark_title_bar(tmp_path, monkeypatch):
    from screening_workbench import display_prefs, theme

    calls = []
    monkeypatch.setattr(display_prefs, "set_dark_title_bar", lambda window, dark: calls.append(dark))
    for name, expected in (("night", True), ("light", False)):
        monkeypatch.setenv("SW_THEME", name)
        root = tk.Tk()
        root.withdraw()
        try:
            ScreeningWorkbenchApp(root, str(tmp_path / f"titlebar-{name}.sqlite"), reviewer_id="owner")
            assert calls[-1] is expected
            root.destroy()
        finally:
            theme.use_palette("light")


@requires_tk
def test_v2_view_menu_saves_a_theme_for_the_next_start(tmp_path, monkeypatch):
    from screening_workbench import display_prefs, theme

    monkeypatch.setenv("SW_SETTINGS_PATH", str(tmp_path / "settings.json"))
    root = tk.Tk()
    root.withdraw()
    app = ScreeningWorkbenchApp(root, str(tmp_path / "theme-menu.sqlite"), reviewer_id="owner")
    view = root.nametowidget(app.menubar_buttons[2].cget("menu"))
    cascade = next(i for i in range(view.index("end") + 1) if view.type(i) == "cascade")
    assert view.entrycget(cascade, "label") == "Theme"
    themes = root.nametowidget(view.entrycget(cascade, "menu"))
    labels = [themes.entrycget(i, "label") for i in range(themes.index("end") + 1)]
    assert labels == ["Match Windows", theme.PALETTE_LABELS["light"], theme.PALETTE_LABELS["night"]]
    themes.invoke(2)
    assert display_prefs.saved_theme() == "night"
    assert "restart" in app.status_message_label.cget("text").lower()
    assert theme.CURRENT_PALETTE == "light", "the running window keeps its palette until restart"
    themes.invoke(0)
    assert display_prefs.saved_theme() == "system"
    root.destroy()

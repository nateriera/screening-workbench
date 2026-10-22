import pytest

from screening_workbench import db, screening
from screening_workbench.importers.csv_importer import commit_csv_import


def _setup(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute(
        "INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))"
    )
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    result = commit_csv_import(
        conn, "title\nA Study\n", {0: "title"}, source_id="s1", branch_id="b1",
        operation_id="op1", actor="owner",
    )
    occ = conn.execute("SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result.batch_id,)).fetchone()
    return conn, occ["occurrence_id"]


def test_cast_include_vote(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    vote = screening.current_vote(conn, occ_id, "revA")
    assert vote["decision"] == "include"
    conn.close()


def test_exclude_requires_reason(tmp_path):
    conn, occ_id = _setup(tmp_path)
    with pytest.raises(ValueError):
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="exclude")
    conn.close()


def test_exclude_with_reason_ok(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="exclude", reason="not relevant")
    vote = screening.current_vote(conn, occ_id, "revA")
    assert vote["decision"] == "exclude"
    assert vote["reason"] == "not relevant"
    conn.close()


def test_reason_not_allowed_for_include(tmp_path):
    conn, occ_id = _setup(tmp_path)
    with pytest.raises(ValueError):
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include", reason="x")
    conn.close()


def test_later_vote_supersedes_prior_preserves_history(tmp_path):
    conn, occ_id = _setup(tmp_path)
    v1 = screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="maybe")
    v2 = screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    current = screening.current_vote(conn, occ_id, "revA")
    assert current["vote_id"] == v2
    all_rows = conn.execute("SELECT * FROM screen_votes WHERE occurrence_id=?", (occ_id,)).fetchall()
    assert len(all_rows) == 2  # history preserved, not overwritten
    old = conn.execute("SELECT superseded_at FROM screen_votes WHERE vote_id=?", (v1,)).fetchone()
    assert old["superseded_at"] is not None
    conn.close()


# Blind isolation: a blinded reviewer sees only their own vote.
def test_blind_isolation_hides_other_reviewer_vote(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")

    visible_to_a = screening.visible_votes_for_reviewer(
        conn, occ_id, "revA", is_blind=True, is_owner_or_auditor=False
    )
    assert len(visible_to_a) == 1
    assert visible_to_a[0]["reviewer_id"] == "revA"
    conn.close()


def test_owner_sees_all_even_while_blind(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    visible_to_owner = screening.visible_votes_for_reviewer(
        conn, occ_id, "owner", is_blind=True, is_owner_or_auditor=True
    )
    assert len(visible_to_owner) == 2
    conn.close()


def test_unblinded_reviewer_sees_all(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    visible = screening.visible_votes_for_reviewer(
        conn, occ_id, "revA", is_blind=False, is_owner_or_auditor=False
    )
    assert len(visible) == 2
    conn.close()


# Conflict detection: include vs exclude disagree; maybe disagrees with anything.
def test_conflict_include_vs_exclude(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    assert screening.has_conflict(conn, occ_id) is True
    conn.close()


def test_conflict_maybe_disagrees_with_include(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="maybe")
    assert screening.has_conflict(conn, occ_id) is True
    conn.close()


def test_no_conflict_when_both_agree(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="include")
    assert screening.has_conflict(conn, occ_id) is False
    conn.close()


def test_no_conflict_with_single_vote(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    assert screening.has_conflict(conn, occ_id) is False
    conn.close()


def test_resolve_conflict_requires_note(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    with pytest.raises(ValueError):
        screening.resolve_conflict(
            conn, occurrence_id=occ_id, final_decision="include", resolution_note="", actor="owner"
        )
    conn.close()


def test_resolve_conflict_logged_and_immutable_history(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    screening.resolve_conflict(
        conn, occurrence_id=occ_id, final_decision="include",
        resolution_note="third reviewer agreed with A", actor="owner",
    )
    all_rows = conn.execute("SELECT * FROM screen_votes WHERE occurrence_id=?", (occ_id,)).fetchall()
    # Original 2 votes + 1 resolution row, none deleted.
    assert len(all_rows) == 3
    resolution = conn.execute(
        "SELECT * FROM screen_votes WHERE reviewer_id='__resolution__' AND occurrence_id=?", (occ_id,)
    ).fetchone()
    assert resolution["decision"] == "include"
    conn.close()


# --- find_next_undecided / count_undecided search & year filter ---
# Screening-workflow spec §4 ergonomics gap found during UI gap review:
# the undecided queue had no way to search or filter, forcing a strict
# front-to-back march through potentially thousands of records.

def _setup_two(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    result = commit_csv_import(
        conn,
        "title,year\nClimate change and wheat yield,2020\nClimate change and rice yield,2021\n",
        {0: "title", 1: "year"}, source_id="s1", branch_id="b1", operation_id="op1", actor="owner",
    )
    rows = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
    ).fetchall()
    return conn, [r["occurrence_id"] for r in rows]


def test_find_next_undecided_search_filter(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    found = screening.find_next_undecided(conn, "revA", search="wheat")
    assert found == occ_ids[0]
    assert screening.count_undecided(conn, "revA", search="wheat") == 1
    assert screening.count_undecided(conn, "revA") == 2
    conn.close()


def test_find_next_undecided_year_filter(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    found = screening.find_next_undecided(conn, "revA", year="2021")
    assert found == occ_ids[1]
    assert screening.count_undecided(conn, "revA", year="2021") == 1
    conn.close()


def test_find_next_undecided_filter_excludes_already_voted(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    assert screening.find_next_undecided(conn, "revA", search="wheat") is None
    assert screening.count_undecided(conn, "revA") == 1
    conn.close()


def test_find_next_undecided_no_match_returns_none(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    assert screening.find_next_undecided(conn, "revA", search="nonexistent topic") is None
    assert screening.count_undecided(conn, "revA", search="nonexistent topic") == 0
    conn.close()


def test_find_next_undecided_journal_filter(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    result = commit_csv_import(
        conn,
        "title,journal\nStudy A,Journal of Field Studies\nStudy B,Annals of Something Else\n",
        {0: "title", 1: "journal"}, source_id="s1", branch_id="b1", operation_id="op1", actor="owner",
    )
    rows = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
    ).fetchall()
    occ_ids = [r["occurrence_id"] for r in rows]

    found = screening.find_next_undecided(conn, "revA", journal="field studies")
    assert found == occ_ids[0]
    assert screening.count_undecided(conn, "revA", journal="field studies") == 1
    conn.close()


def test_undecided_only_false_includes_decided_occurrences(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")

    assert screening.count_undecided(conn, "revA", undecided_only=True) == 1
    assert screening.count_undecided(conn, "revA", undecided_only=False) == 2
    # With undecided_only=False, the already-decided occurrence can still
    # be found by its own content (useful for re-browsing past decisions).
    found = screening.find_next_undecided(conn, "revA", search="wheat", undecided_only=False)
    assert found == occ_ids[0]
    conn.close()


def test_find_next_undecided_batch_filter(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    batch_id = conn.execute(
        "SELECT batch_id FROM occurrences WHERE occurrence_id=?", (occ_ids[0],)
    ).fetchone()["batch_id"]
    assert screening.count_undecided(conn, "revA", batch_id=batch_id) == 2
    assert screening.count_undecided(conn, "revA", batch_id="nonexistent-batch") == 0
    conn.close()


def test_list_active_batches(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    batches = screening.list_active_batches(conn)
    assert len(batches) == 1
    assert batches[0]["count"] == 2


def test_recent_decisions_for_reviewer_own_votes_only_newest_first(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_ids[1], reviewer_id="revA", decision="exclude", reason="Wrong population")
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revB", decision="exclude", reason="Wrong outcome")

    recent = screening.recent_decisions_for_reviewer(conn, "revA")
    assert len(recent) == 2
    assert recent[0]["decision"] == "exclude"  # most recent first
    assert recent[0]["reason"] == "Wrong population"
    assert recent[1]["decision"] == "include"
    assert all("revB" not in str(r) for r in recent)  # never another reviewer's vote
    conn.close()


def test_recent_decisions_for_reviewer_respects_limit(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    rows_csv = "\n".join(f"Study {i}" for i in range(6))
    result = commit_csv_import(
        conn, "title\n" + rows_csv + "\n", {0: "title"}, source_id="s1", branch_id="b1",
        operation_id="op1", actor="owner",
    )
    occ_rows = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
    ).fetchall()
    for r in occ_rows:
        screening.cast_vote(conn, occurrence_id=r["occurrence_id"], reviewer_id="revA", decision="include")

    assert len(screening.recent_decisions_for_reviewer(conn, "revA", limit=4)) == 4
    assert len(screening.recent_decisions_for_reviewer(conn, "revA", limit=100)) == 6
    conn.close()


def test_list_undecided_returns_queue_order_with_fields(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    queue = screening.list_undecided(conn, "revA")
    assert [q["occurrence_id"] for q in queue] == occ_ids
    assert queue[0]["title"] == "Climate change and wheat yield"
    assert queue[0]["year"] == "2020"


def test_list_undecided_respects_limit_and_filters(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    assert len(screening.list_undecided(conn, "revA", limit=1)) == 1
    rice_only = screening.list_undecided(conn, "revA", search="rice")
    assert [q["occurrence_id"] for q in rice_only] == [occ_ids[1]]


def test_bulk_cast_vote_includes_everyone(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    n = screening.bulk_cast_vote(conn, occurrence_ids=occ_ids, reviewer_id="revA", decision="include")
    assert n == 2
    for occ_id in occ_ids:
        vote = screening.current_vote(conn, occ_id, "revA")
        assert vote["decision"] == "include"
    assert screening.count_undecided(conn, "revA") == 0
    conn.close()


def test_bulk_cast_vote_exclude_requires_one_shared_reason(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    with pytest.raises(ValueError):
        screening.bulk_cast_vote(conn, occurrence_ids=occ_ids, reviewer_id="revA", decision="exclude")
    screening.bulk_cast_vote(
        conn, occurrence_ids=occ_ids, reviewer_id="revA", decision="exclude", reason="Wrong population",
    )
    for occ_id in occ_ids:
        vote = screening.current_vote(conn, occ_id, "revA")
        assert vote["decision"] == "exclude"
        assert vote["reason"] == "Wrong population"
    conn.close()


def test_batch_info_for_occurrence(tmp_path):
    """UI reference target §6: 'Batch N (FORMAT, source name)' on the
    record-pane position line."""
    conn, occ_id = _setup(tmp_path)
    info = screening.batch_info_for_occurrence(conn, occ_id)
    assert info is not None
    assert info["ordinal"] == 1
    assert info["source_format"] == "CSV"
    assert info["source_name"] == "import.csv"
    conn.close()


def test_batch_info_ordinal_increments_across_batches(tmp_path):
    conn, occ_id = _setup(tmp_path)
    result2 = commit_csv_import(
        conn, "title\nB Study\n", {0: "title"}, source_id="s1", branch_id="b1",
        operation_id="op2", actor="owner", source_name="second.csv",
    )
    occ2 = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result2.batch_id,),
    ).fetchone()["occurrence_id"]

    info1 = screening.batch_info_for_occurrence(conn, occ_id)
    info2 = screening.batch_info_for_occurrence(conn, occ2)
    assert info1["ordinal"] == 1
    assert info2["ordinal"] == 2
    assert info2["source_name"] == "second.csv"
    conn.close()


def test_batch_info_for_unknown_occurrence_returns_none(tmp_path):
    conn, _occ_id = _setup(tmp_path)
    assert screening.batch_info_for_occurrence(conn, "not-a-real-id") is None
    conn.close()


def test_bulk_cast_vote_empty_list_is_a_noop(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    assert screening.bulk_cast_vote(conn, occurrence_ids=[], reviewer_id="revA", decision="include") == 0
    assert screening.count_undecided(conn, "revA") == 2
    conn.close()


def test_undo_last_vote_restores_undecided(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    assert screening.current_vote(conn, occ_id, "revA") is not None

    undone = screening.undo_last_vote(conn, "revA")
    assert undone["decision"] == "include"
    assert undone["occurrence_id"] == occ_id
    assert screening.current_vote(conn, occ_id, "revA") is None
    conn.close()


def test_undo_last_vote_targets_the_most_recent_occurrence(tmp_path):
    conn, occ_ids = _setup_two(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_ids[1], reviewer_id="revA", decision="maybe")

    undone = screening.undo_last_vote(conn, "revA")
    assert undone["occurrence_id"] == occ_ids[1]
    # The first vote is untouched -- only the most recent one is undone.
    assert screening.current_vote(conn, occ_ids[0], "revA")["decision"] == "include"
    assert screening.current_vote(conn, occ_ids[1], "revA") is None
    conn.close()


def test_undo_last_vote_with_nothing_to_undo_returns_none(tmp_path):
    conn, occ_id = _setup(tmp_path)
    assert screening.undo_last_vote(conn, "revA") is None
    conn.close()


def test_undo_last_vote_numbers_are_stable_and_real(tmp_path, monkeypatch):
    """UI reference target §11: '#N' per recent decision must be a real,
    stable number (screen_votes' implicit rowid), not decorative text."""
    conn, occ_ids = _setup_two(tmp_path)

    # Force equal event timestamps and UUID order opposite insertion order.
    # Lexical vote_id ordering must not decide which decision is newest.
    monkeypatch.setattr(screening.db, "now_rfc3339", lambda: "2026-01-01T00:00:00.000000Z")
    vote_ids = iter(("vote_z", "vote_a", "vote_b"))
    monkeypatch.setattr(screening, "new_id", lambda _prefix: next(vote_ids))
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_ids[1], reviewer_id="revA", decision="maybe")
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revB", decision="include")

    recent = screening.recent_decisions_for_reviewer(conn, "revA")
    assert recent[0]["number"] > recent[1]["number"]  # newest first, strictly increasing
    assert [row["occurrence_id"] for row in recent] == [occ_ids[1], occ_ids[0]]
    assert screening.recent_decisions_for_reviewer(conn, "revA", stage="full_text") == []
    assert len(screening.recent_decisions_for_reviewer(conn, "revB")) == 1

    undone = screening.undo_last_vote(conn, "revA")
    assert undone["n"] == recent[0]["number"]
    assert undone["occurrence_id"] == recent[0]["occurrence_id"]
    conn.close()


# --- Directive A: inter-rater reliability (Cohen's kappa) ---
# Independent implementation; no incumbent tool's kappa code was read.

def _setup_n(tmp_path, n: int):
    """n synthetic occurrences via a minimal CSV import, for kappa fixtures."""
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    rows_csv = "\n".join(f"Study {i}" for i in range(n))
    result = commit_csv_import(
        conn, "title\n" + rows_csv + "\n", {0: "title"}, source_id="s1", branch_id="b1",
        operation_id="op1", actor="owner",
    )
    occ_rows = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
    ).fetchall()
    return conn, [r["occurrence_id"] for r in occ_rows]


def test_kappa_single_reviewer_is_na(tmp_path):
    """Directive A §3: single-reviewer projects show 'n/a -- needs two
    reviewers', never a zero kappa (zero would misleadingly read as
    "no agreement" rather than "not computable")."""
    conn, occ_ids = _setup_n(tmp_path, 1)
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    result = screening.cohens_kappa(conn)
    assert result["status"] == "insufficient_reviewers"
    assert result["kappa"] is None
    assert result["label"] == "n/a -- needs two reviewers"
    assert result["n"] == 0
    conn.close()


def test_kappa_perfect_agreement(tmp_path):
    """Both reviewers cast identical decisions across all three
    categories (3 include, 3 maybe, 3 exclude) -> kappa = 1.0 exactly."""
    conn, occ_ids = _setup_n(tmp_path, 9)
    pattern = ["include"] * 3 + ["maybe"] * 3 + ["exclude"] * 3
    for occ_id, decision in zip(occ_ids, pattern):
        reason = "Wrong population" if decision == "exclude" else None
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision=decision, reason=reason)
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision=decision, reason=reason)

    result = screening.cohens_kappa(conn)
    assert result["status"] == "ok"
    assert result["kappa"] == pytest.approx(1.0)
    assert result["label"] == "Almost perfect"
    assert result["agreement"] == pytest.approx(1.0)
    assert result["n"] == 9
    conn.close()


def test_kappa_chance_level_agreement(tmp_path):
    """Exact (not simulated) chance-level construction: reviewer A's
    3 categories x reviewer B's 3 categories, one occurrence per
    combination, so every contingency cell = 1 and observed agreement
    exactly equals expected-by-chance agreement -> kappa = 0.0 exactly.
    po = 3/9; pe = 3*(3/9 * 3/9) = 3/9; kappa = (po-pe)/(1-pe) = 0."""
    conn, occ_ids = _setup_n(tmp_path, 9)
    decisions = ("include", "maybe", "exclude")
    reasons = {"include": None, "maybe": None, "exclude": "Wrong population"}
    i = 0
    for da in decisions:
        for db_ in decisions:
            occ_id = occ_ids[i]
            screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision=da, reason=reasons[da])
            screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision=db_, reason=reasons[db_])
            i += 1

    result = screening.cohens_kappa(conn)
    assert result["status"] == "ok"
    assert result["kappa"] == pytest.approx(0.0, abs=1e-9)
    assert result["n"] == 9
    conn.close()


def test_kappa_published_worked_example(tmp_path):
    """Hand-verified against a published 3x3 worked example (turtle
    species rating by two raters, N=36, kappa ~0.45): "Cohen's Kappa"
    course handout, Sungkyunkwan University Security Lab,
    https://seclab.skku.edu/wp-content/uploads/2022/11/hckappa.pdf
    Contingency table (rater1 rows x rater2 cols, categories
    yellow-bellied/red-bellied/cooters):
        y  r  c
      y 9  3  1
      r 4  8  2
      c 2  1  6
    Published result: Sum(agreements)=23, Sum(expected)=12.34,
    kappa = (23-12.34)/(36-12.34) = 0.45 (rounded to 2dp in the source).
    """
    table = {
        "include": {"include": 9, "maybe": 3, "exclude": 1},
        "maybe": {"include": 4, "maybe": 8, "exclude": 2},
        "exclude": {"include": 2, "maybe": 1, "exclude": 6},
    }
    total = sum(sum(row.values()) for row in table.values())
    assert total == 36

    conn, occ_ids = _setup_n(tmp_path, total)
    reasons = {"include": None, "maybe": None, "exclude": "Wrong population"}
    i = 0
    for da, row in table.items():
        for db_, count in row.items():
            for _ in range(count):
                occ_id = occ_ids[i]
                screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision=da, reason=reasons[da])
                screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision=db_, reason=reasons[db_])
                i += 1

    result = screening.cohens_kappa(conn)
    assert result["status"] == "ok"
    assert result["n"] == 36
    assert result["agreement"] == pytest.approx(23 / 36, abs=1e-9)
    assert result["kappa"] == pytest.approx(0.45, abs=0.01)
    assert result["label"] == "Moderate"
    conn.close()


def test_kappa_excludes_single_reviewer_decided_records(tmp_path):
    """Directive A §5: a record only one reviewer has decided is
    excluded from n, not treated as a disagreement."""
    conn, occ_ids = _setup_n(tmp_path, 3)
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revB", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_ids[1], reviewer_id="revA", decision="exclude", reason="Wrong population")
    screening.cast_vote(conn, occurrence_id=occ_ids[1], reviewer_id="revB", decision="exclude", reason="Wrong population")
    # occ_ids[2] decided by revA only -- must not count toward n.
    screening.cast_vote(conn, occurrence_id=occ_ids[2], reviewer_id="revA", decision="maybe")

    result = screening.cohens_kappa(conn)
    assert result["n"] == 2
    assert result["kappa"] == pytest.approx(1.0)
    conn.close()


def test_kappa_no_double_decided_records_is_na(tmp_path):
    conn, occ_ids = _setup_n(tmp_path, 2)
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_ids[1], reviewer_id="revB", decision="include")
    result = screening.cohens_kappa(conn)
    assert result["status"] == "no_double_decided"
    assert result["kappa"] is None
    assert result["n"] == 0
    conn.close()


def test_kappa_recomputes_after_vote_undone(tmp_path):
    """Directive A §5: kappa recomputes correctly after a vote is
    changed via the undo path, not cached/stale."""
    conn, occ_ids = _setup_n(tmp_path, 3)
    for occ_id in occ_ids:
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="include")

    before = screening.cohens_kappa(conn)
    assert before["n"] == 3
    assert before["kappa"] == pytest.approx(1.0)

    screening.undo_last_vote(conn, "revA")  # retract revA's most recent current vote

    after = screening.cohens_kappa(conn)
    assert after["n"] == 2  # one record now decided by only one reviewer
    assert after["kappa"] == pytest.approx(1.0)  # the remaining 2 still agree perfectly
    conn.close()


def test_kappa_more_than_two_reviewers_requires_explicit_pair(tmp_path):
    """Out of scope (Directive A, named gap): v1 kappa is pairwise
    only; a third active reviewer must not be silently folded in."""
    conn, occ_ids = _setup_n(tmp_path, 1)
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revB", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="revC", decision="include")
    with pytest.raises(ValueError):
        screening.cohens_kappa(conn)
    # Explicit pair still works.
    result = screening.cohens_kappa(conn, reviewer_a="revA", reviewer_b="revB")
    assert result["status"] == "ok"
    conn.close()


def test_kappa_is_descriptive_never_blocks_anything(tmp_path):
    """Directive A §4: low/zero agreement must not raise, block, or in
    any way prevent export/unblind/other actions -- it is information.
    This test only asserts the function returns normally on a
    deliberately disagreeing (kappa=0) fixture; no exception path."""
    conn, occ_ids = _setup_n(tmp_path, 9)
    decisions = ("include", "maybe", "exclude")
    reasons = {"include": None, "maybe": None, "exclude": "Wrong population"}
    i = 0
    for da in decisions:
        for db_ in decisions:
            occ_id = occ_ids[i]
            screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision=da, reason=reasons[da])
            screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision=db_, reason=reasons[db_])
            i += 1
    result = screening.cohens_kappa(conn)  # must not raise despite kappa == 0
    assert result["kappa"] == pytest.approx(0.0, abs=1e-9)
    conn.close()


def test_kappa_readout_absent_while_blind(tmp_path):
    """Directive A §3: the kappa readout renders ONLY in the unblinded
    adjudication view -- rendered-against-blind-on-state check at the
    data layer (app.py wiring is out of scope for this round)."""
    conn, occ_ids = _setup_n(tmp_path, 2)
    for occ_id in occ_ids:
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="include")

    blind_view = screening.kappa_readout(conn, is_blind=True)
    assert blind_view is None

    unblind_view = screening.kappa_readout(conn, is_blind=False)
    assert unblind_view is not None
    assert unblind_view["status"] == "ok"
    assert unblind_view["kappa"] == pytest.approx(1.0)
    conn.close()

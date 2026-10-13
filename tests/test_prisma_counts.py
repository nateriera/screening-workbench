import json

import pytest

from screening_workbench import db, dedup, prisma, reports
from screening_workbench.importers.csv_importer import commit_csv_import
from screening_workbench import screening


def _seed(conn, source_id, branch_id, cls):
    conn.execute(
        "INSERT OR IGNORE INTO branches (branch_id, name, created_at) VALUES (?, ?, datetime('now'))",
        (branch_id, branch_id),
    )
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES (?, ?, ?, ?, datetime('now'))",
        (source_id, source_id, cls, branch_id),
    )
    conn.commit()


def _import_one(conn, title, source_id, branch_id, op_id, doi="10.1/shared"):
    result = commit_csv_import(
        conn, f"title,doi\n{title},{doi}\n", {0: "title", 1: "doi"},
        source_id=source_id, branch_id=branch_id, operation_id=op_id, actor="owner",
    )
    occ = conn.execute("SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result.batch_id,)).fetchone()
    return occ["occurrence_id"]


# Acceptance test 6 (source/branch fixture).
def test_acceptance_6_source_branch_fixture(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    _seed(conn, "s_db", "A", "database")
    _seed(conn, "s_reg", "B", "register")

    x1 = _import_one(conn, "Shared Title One", "s_db", "A", "op-x1")
    x2 = _import_one(conn, "Shared Title Two", "s_db", "A", "op-x2", doi="10.1/other")
    x3 = _import_one(conn, "Register Title", "s_reg", "B", "op-x3", doi="10.1/reg")
    x4 = _import_one(conn, "Shared Title One", "s_db", "A", "op-x4")  # exact DOI dup of x1

    # x1 screened include; x2 screened maybe; x3 screened include; x4 unscreened.
    screening.cast_vote(conn, occurrence_id=x1, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=x2, reviewer_id="revA", decision="maybe")
    screening.cast_vote(conn, occurrence_id=x3, reviewer_id="revA", decision="include")

    # Before any merges: branch A has 3 occurrences (x1,x2,x4); x2's
    # maybe is pending, x4 is undecided, and only x1 has a terminal vote.
    # Branch B has 1 terminally screened occurrence (x3).
    ident = prisma.identification_and_screening_counts(conn)
    a = ident["branches"]["A"]
    assert a["identified"] == 3
    assert a["removed_before_screen"] == 0
    assert a["prescreen_pending"] == 0
    assert a["screening_pending"] == 2  # x2 maybe + x4 unscreened
    assert a["records_screened"] == 1   # x1 only; maybe is not terminal
    b = ident["branches"]["B"]
    assert b["identified"] == 1
    assert b["removed_before_screen"] == 0
    assert b["screening_pending"] == 0
    assert b["records_screened"] == 1
    assert ident["identified_database"] == 3
    assert ident["identified_register"] == 1

    # Merge x4 (unscreened) into x1 before x4 is screened: one pre-screen removal.
    dedup.run_exact_and_fuzzy_detection(conn, "system")
    ident2 = prisma.identification_and_screening_counts(conn)
    a2 = ident2["branches"]["A"]
    assert a2["identified"] == 3  # identified count never shrinks
    assert a2["removed_before_screen"] == 1
    assert a2["screening_pending"] == 1  # x2 remains maybe-pending
    assert a2["records_screened"] == 1

    # No invariant violations at this point.
    assert prisma.verify_invariants(conn) == []
    conn.close()


def test_mixed_vote_duplicate_counted_as_post_screen_correction(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    _seed(conn, "s_db", "A", "database")
    occ1 = _import_one(conn, "Same", "s_db", "A", "op1", doi="10.1/x")
    occ2 = _import_one(conn, "Same", "s_db", "A", "op2", doi="10.1/x")
    # occ1 (the older occurrence, hence the deterministic survivor) stays
    # unscreened; occ2 (which will be absorbed) gets a vote first --
    # exercising the post-screen-correction path on the absorbed side.
    screening.cast_vote(conn, occurrence_id=occ2, reviewer_id="revA", decision="maybe")
    dedup.run_exact_and_fuzzy_detection(conn, "system")
    ident = prisma.identification_and_screening_counts(conn)
    # occ1 is the survivor (oldest created_at); occ2 is absorbed and carried
    # a prior vote, so it is a post-screen correction, not a pre-screen
    # removal -- there is no unscreened absorbed row in this fixture.
    assert ident["removed_before_screen"] == 0
    assert ident["post_screen_duplicate_corrections"] == 1
    assert prisma.verify_invariants(conn) == []
    conn.close()


# Acceptance test 6, second half: conflicting-vote merge after screening,
# adjudication before progression, canonical selection per branch, and
# unchanged source-class totals regardless of which branch is selected.
def _build_fixture_6_through_canonical_selection(tmp_path, select_branch):
    """Shared setup for the two canonical-selection variants below.
    Returns (conn, r1_report_id, x1, x3) after: x1/x2/x3/x4 seeded and
    screened/merged as in test_acceptance_6_source_branch_fixture; x5
    (branch A, conflicting vote vs x2) discovered as x2's duplicate and
    merged AFTER screening; the resulting conflict adjudicated; R1
    created and linked to x1 (branch A) and x3 (branch B); progression
    assigned to whichever of x1/x3 `select_branch` names.
    """
    conn = db.connect(tmp_path / "t.db")
    _seed(conn, "s_db", "A", "database")
    _seed(conn, "s_reg", "B", "register")

    x1 = _import_one(conn, "Shared Title One", "s_db", "A", "op-x1")
    x2 = _import_one(conn, "Shared Title Two", "s_db", "A", "op-x2", doi="10.1/other")
    x3 = _import_one(conn, "Register Title", "s_reg", "B", "op-x3", doi="10.1/reg")
    x4 = _import_one(conn, "Shared Title One", "s_db", "A", "op-x4")  # exact DOI dup of x1

    screening.cast_vote(conn, occurrence_id=x1, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=x2, reviewer_id="revA", decision="maybe")
    screening.cast_vote(conn, occurrence_id=x3, reviewer_id="revA", decision="include")

    dedup.run_exact_and_fuzzy_detection(conn, "system")  # x4 -> pre-screen removal into x1

    # Discover x2's duplicate: a conflicting vote (exclude vs x2's maybe)
    # on x5, then merge after both are screened.
    x5 = _import_one(conn, "Shared Title Two", "s_db", "A", "op-x5", doi="10.1/other")
    screening.cast_vote(conn, occurrence_id=x5, reviewer_id="revB", decision="exclude", reason="Wrong population")
    source_total_before = prisma.identification_and_screening_counts(conn)
    db_total_before = source_total_before["identified_database"]
    reg_total_before = source_total_before["identified_register"]

    dedup.run_exact_and_fuzzy_detection(conn, "system")
    ident = prisma.identification_and_screening_counts(conn)
    # x4's removal was already counted; this second merge is x2/x5 --
    # whichever survives carries a prior vote, so it's a post-screen
    # correction, not a second pre-screen removal.
    assert ident["removed_before_screen"] == 1
    assert ident["post_screen_duplicate_corrections"] == 1
    # Source-class totals are provenance counts, not duplicate-adjusted --
    # merging never changes them.
    assert ident["identified_database"] == db_total_before
    assert ident["identified_register"] == reg_total_before

    # Adjudicate the conflicting x2/x5 vote (maybe vs exclude) before any
    # report progression can proceed -- find whichever occurrence of the
    # merged pair survived as active.
    survivor_row = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE occurrence_id IN (?, ?) AND is_active = 1",
        (x2, x5),
    ).fetchone()
    survivor = survivor_row["occurrence_id"]
    screening.resolve_conflict(
        conn, occurrence_id=survivor, final_decision="exclude",
        resolution_note="Adjudicated: wrong population confirmed by second reviewer",
        actor="owner",
    )

    r1 = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", x1, r1)
    reports.link_occurrence_to_report(conn, "owner", x3, r1)
    selected = x1 if select_branch == "A" else x3
    reports.assign_progression(conn, "owner", r1, selected)
    return conn, r1, x1, x3


def test_acceptance_6_canonical_selection_branch_a(tmp_path):
    conn, r1, x1, x3 = _build_fixture_6_through_canonical_selection(tmp_path, "A")
    progression = conn.execute(
        "SELECT * FROM report_progressions WHERE report_id=?", (r1,),
    ).fetchone()
    assert progression["branch_id"] == "A"
    assert progression["canonical_occurrence"] == x1
    # Both source occurrences remain in provenance (record_reports links)
    # regardless of which one is canonical -- x3 doesn't advance again.
    links = conn.execute(
        "SELECT occurrence_id FROM record_reports WHERE report_id=?", (r1,),
    ).fetchall()
    assert {l["occurrence_id"] for l in links} == {x1, x3}
    all_progressions = conn.execute(
        "SELECT COUNT(*) AS n FROM report_progressions WHERE report_id=?", (r1,),
    ).fetchone()["n"]
    assert all_progressions == 1
    conn.close()


def test_acceptance_6_canonical_selection_branch_b(tmp_path):
    conn, r1, x1, x3 = _build_fixture_6_through_canonical_selection(tmp_path, "B")
    progression = conn.execute(
        "SELECT * FROM report_progressions WHERE report_id=?", (r1,),
    ).fetchone()
    assert progression["branch_id"] == "B"
    assert progression["canonical_occurrence"] == x3
    all_progressions = conn.execute(
        "SELECT COUNT(*) AS n FROM report_progressions WHERE report_id=?", (r1,),
    ).fetchone()["n"]
    assert all_progressions == 1
    conn.close()


# Acceptance test 2: cross-branch fixture links duplicate occurrences to
# one report; select one canonical occurrence/branch. It advances once;
# replay/correction/undo restore expected counts.
def test_acceptance_2_progression_correction_switches_canonical_branch(tmp_path):
    conn, r1, x1, x3 = _build_fixture_6_through_canonical_selection(tmp_path, "A")
    ident_before = prisma.identification_and_screening_counts(conn)

    # The report advances once, via branch A/x1, per the base fixture.
    progression = conn.execute(
        "SELECT * FROM report_progressions WHERE report_id=?", (r1,),
    ).fetchone()
    assert progression["branch_id"] == "A"
    assert progression["canonical_occurrence"] == x1

    # A second plain assign_progression call must still be refused --
    # the correction path is the only way to re-select, never a silent
    # second assignment.
    with pytest.raises(ValueError):
        reports.assign_progression(conn, "owner", r1, x3)

    # Correct the progression to branch B/x3.
    reports.correct_progression(
        conn, "owner", r1, x3,
        rationale="Branch A's register entry was found to be the weaker provenance trail on review.",
    )

    progression2 = conn.execute(
        "SELECT * FROM report_progressions WHERE report_id=?", (r1,),
    ).fetchone()
    assert progression2["branch_id"] == "B"
    assert progression2["canonical_occurrence"] == x3

    # Still exactly one progression row for this report -- a correction
    # is a re-selection, not a second advancement.
    all_progressions = conn.execute(
        "SELECT COUNT(*) AS n FROM report_progressions WHERE report_id=?", (r1,),
    ).fetchone()["n"]
    assert all_progressions == 1

    # Both occurrences remain in provenance regardless of which is
    # canonical (record_reports is untouched by a progression
    # correction).
    links = conn.execute(
        "SELECT occurrence_id FROM record_reports WHERE report_id=?", (r1,),
    ).fetchall()
    assert {l["occurrence_id"] for l in links} == {x1, x3}

    # Identification/screening counts are untouched by a progression
    # correction -- it only changes which occurrence a REPORT advances
    # through, not any identification-stage count.
    ident_after = prisma.identification_and_screening_counts(conn)
    assert ident_after == ident_before

    # The correction is itself a distinct, auditable event -- not a
    # silent overwrite of the original assignment event.
    events = db.all_events(conn)
    corrected = [e for e in events if e["event_type"] == "report.progression_corrected"]
    assert len(corrected) == 1
    payload = json.loads(corrected[0]["payload_json"])
    assert payload["prior_canonical_occurrence"] == x1
    assert payload["canonical_occurrence"] == x3
    assert payload["rationale"]

    assert prisma.verify_invariants(conn) == []
    conn.close()


def test_correct_progression_requires_a_rationale(tmp_path):
    conn, r1, x1, x3 = _build_fixture_6_through_canonical_selection(tmp_path, "A")
    with pytest.raises(ValueError):
        reports.correct_progression(conn, "owner", r1, x3, rationale="")
    conn.close()


def test_correct_progression_rejects_an_unlinked_occurrence(tmp_path):
    conn, r1, x1, x3 = _build_fixture_6_through_canonical_selection(tmp_path, "A")
    stray = _import_one(conn, "Unrelated Record", "s_db", "A", "op-stray", doi="10.1/unrelated")
    with pytest.raises(ValueError):
        reports.correct_progression(conn, "owner", r1, stray, rationale="Should be rejected")
    conn.close()


def test_correct_progression_on_a_never_assigned_report_raises(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    _seed(conn, "s_db", "A", "database")
    x1 = _import_one(conn, "Lonely Study", "s_db", "A", "op-x1")
    r1 = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", x1, r1)
    with pytest.raises(ValueError):
        reports.correct_progression(conn, "owner", r1, x1, rationale="No progression exists yet")
    conn.close()


# §3.1 equations E3/E4/E5 (identified_other, identified_db_register,
# identified_total) had zero test coverage anywhere in the suite until
# this test -- every existing fixture only used database/register
# source classes. Closing that gap for the priority-2 equation->test
# audit.
def test_identified_other_method_source_class_and_totals(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    _seed(conn, "s_db", "A", "database")
    _seed(conn, "s_reg", "B", "register")
    _seed(conn, "s_other", "C", "other_method")

    _import_one(conn, "DB One", "s_db", "A", "op-db1")
    _import_one(conn, "DB Two", "s_db", "A", "op-db2", doi="10.1/db2")
    _import_one(conn, "Register One", "s_reg", "B", "op-reg1")
    _import_one(conn, "Other One", "s_other", "C", "op-other1")
    _import_one(conn, "Other Two", "s_other", "C", "op-other2", doi="10.1/other2")
    _import_one(conn, "Other Three", "s_other", "C", "op-other3", doi="10.1/other3")

    ident = prisma.identification_and_screening_counts(conn)
    assert ident["identified_database"] == 2
    assert ident["identified_register"] == 1
    assert ident["identified_other"] == 3
    assert ident["identified_db_register"] == 3  # database(2) + register(1)
    assert ident["identified_total"] == 6         # db_register(3) + other(3)
    assert prisma.verify_invariants(conn) == []
    conn.close()


# Acceptance test 1 (import retry/re-import): "retrying an uncommitted
# operation commits once" is covered by test_im18_retry_same_operation
# _is_idempotent (same operation_id). The other half of the same
# sentence -- "a deliberate re-import creates a new batch and
# occurrence IDs" (a DIFFERENT operation_id for identical content) --
# had no dedicated test; closing that gap here.
def test_deliberate_re_import_creates_new_batch_and_occurrence_ids(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    _seed(conn, "s_db", "A", "database")
    text = "title,doi\nSame Content,10.1/x\n"
    mapping = {0: "title", 1: "doi"}
    r1 = commit_csv_import(
        conn, text, mapping, source_id="s_db", branch_id="A",
        operation_id="first-import", actor="owner",
    )
    r2 = commit_csv_import(
        conn, text, mapping, source_id="s_db", branch_id="A",
        operation_id="second-import", actor="owner",  # deliberately different op id
    )
    assert r1.batch_id != r2.batch_id
    occ1 = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=?", (r1.batch_id,)
    ).fetchone()["occurrence_id"]
    occ2 = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=?", (r2.batch_id,)
    ).fetchone()["occurrence_id"]
    assert occ1 != occ2
    # Both occurrences are real, independent, active rows -- a
    # deliberate re-import is not idempotent-collapsed like a retry.
    total = conn.execute("SELECT COUNT(*) AS n FROM occurrences").fetchone()["n"]
    assert total == 2
    conn.close()

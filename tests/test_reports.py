import pytest

from screening_workbench import db, reports
from screening_workbench.importers.csv_importer import commit_csv_import


def _setup(tmp_path, n_occurrences=1, branch_id="b1"):
    conn = db.connect(tmp_path / "t.db")
    conn.execute(
        "INSERT INTO branches (branch_id, name, created_at) VALUES (?, ?, datetime('now'))",
        (branch_id, branch_id),
    )
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database',?,datetime('now'))",
        (branch_id,),
    )
    conn.commit()
    rows = "\n".join(f"Title {i}" for i in range(n_occurrences))
    result = commit_csv_import(
        conn, "title\n" + rows + "\n", {0: "title"}, source_id="s1", branch_id=branch_id,
        operation_id="op1", actor="owner",
    )
    occ_ids = [
        r["occurrence_id"] for r in conn.execute(
            "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
        ).fetchall()
    ]
    return conn, occ_ids


def test_create_link_and_progress_report(tmp_path):
    conn, occ_ids = _setup(tmp_path)
    report_id = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], report_id)
    reports.assign_progression(conn, "owner", report_id, occ_ids[0])
    row = conn.execute("SELECT * FROM report_progressions WHERE report_id=?", (report_id,)).fetchone()
    assert row["canonical_occurrence"] == occ_ids[0]
    conn.close()


def test_progression_requires_link_first(tmp_path):
    conn, occ_ids = _setup(tmp_path)
    report_id = reports.create_report(conn, "owner")
    with pytest.raises(ValueError):
        reports.assign_progression(conn, "owner", report_id, occ_ids[0])
    conn.close()


def test_report_advances_once_second_assignment_rejected(tmp_path):
    conn, occ_ids = _setup(tmp_path, n_occurrences=2)
    report_id = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], report_id)
    reports.link_occurrence_to_report(conn, "owner", occ_ids[1], report_id)
    reports.assign_progression(conn, "owner", report_id, occ_ids[0])
    with pytest.raises(ValueError):
        reports.assign_progression(conn, "owner", report_id, occ_ids[1])
    conn.close()


def test_occurrences_for_report_lists_all_provenance_including_canonical(tmp_path):
    conn, occ_ids = _setup(tmp_path, n_occurrences=2)
    report_id = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], report_id)
    reports.link_occurrence_to_report(conn, "owner", occ_ids[1], report_id)
    reports.assign_progression(conn, "owner", report_id, occ_ids[0])

    linked = reports.occurrences_for_report(conn, report_id)
    assert set(linked) == set(occ_ids)  # canonical occurrence is one of these, not separate
    assert occ_ids[0] in linked

    other_report = reports.create_report(conn, "owner")
    assert reports.occurrences_for_report(conn, other_report) == []
    conn.close()


# Acceptance test 2 (cross-branch): duplicate occurrences from two branches
# link to one report; select one canonical occurrence/branch; it advances once.
def test_cross_branch_fixture_advances_once(tmp_path):
    conn, occ_a = _setup(tmp_path, n_occurrences=1, branch_id="A")
    conn.execute(
        "INSERT INTO branches (branch_id, name, created_at) VALUES ('B','B',datetime('now'))"
    )
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s2','s2','register','B',datetime('now'))"
    )
    conn.commit()
    result_b = commit_csv_import(
        conn, "title\nTitle B\n", {0: "title"}, source_id="s2", branch_id="B",
        operation_id="op-b", actor="owner",
    )
    occ_b = conn.execute("SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result_b.batch_id,)).fetchone()["occurrence_id"]

    report_id = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_a[0], report_id)
    reports.link_occurrence_to_report(conn, "owner", occ_b, report_id)
    reports.assign_progression(conn, "owner", report_id, occ_a[0])  # select branch A

    progression = conn.execute("SELECT * FROM report_progressions WHERE report_id=?", (report_id,)).fetchone()
    assert progression["branch_id"] == "A"
    # Both source occurrences remain in provenance regardless of selection.
    links = conn.execute("SELECT occurrence_id FROM record_reports WHERE report_id=?", (report_id,)).fetchall()
    assert {l["occurrence_id"] for l in links} == {occ_a[0], occ_b}
    # The report has exactly one progression row -- advances once.
    all_progressions = conn.execute("SELECT COUNT(*) AS n FROM report_progressions WHERE report_id=?", (report_id,)).fetchone()["n"]
    assert all_progressions == 1
    conn.close()


# Acceptance test 3 (retrieval fixture): four sought, one pending, one not
# retrieved, one included, one excluded with reason X.
def test_retrieval_fixture_four_reports(tmp_path):
    conn, occ_ids = _setup(tmp_path, n_occurrences=4)
    report_ids = []
    for occ_id in occ_ids:
        rid = reports.create_report(conn, "owner")
        reports.link_occurrence_to_report(conn, "owner", occ_id, rid)
        reports.assign_progression(conn, "owner", rid, occ_id)
        report_ids.append(rid)

    # r0 stays pending (no action)
    reports.mark_not_retrieved(conn, "owner", report_ids[1])
    reports.record_full_text_assessment(conn, "owner", report_ids[2], "included")
    reports.record_full_text_assessment(conn, "owner", report_ids[3], "excluded", exclusion_reason="reason-X")

    c = reports.counts(conn)
    assert c["reports_sought"] == 4
    assert c["reports_pending"] == 1
    assert c["reports_not_retrieved"] == 1
    assert c["reports_assessed"] == 2
    assert c["reports_included"] == 1
    assert c["reports_excluded"] == 1
    assert c["reasons"]["reason-X"] == 1
    # Both PRISMA equations (spec §3.2):
    assert c["reports_assessed"] == c["reports_included"] + c["reports_excluded"]
    assert c["reports_sought"] == c["reports_assessed"] + c["reports_not_retrieved"] + c["reports_pending"]
    conn.close()


def test_excluded_requires_reason(tmp_path):
    conn, occ_ids = _setup(tmp_path)
    rid = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], rid)
    reports.assign_progression(conn, "owner", rid, occ_ids[0])
    with pytest.raises(ValueError):
        reports.record_full_text_assessment(conn, "owner", rid, "excluded")
    conn.close()


def test_included_must_not_carry_reason(tmp_path):
    conn, occ_ids = _setup(tmp_path)
    rid = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], rid)
    reports.assign_progression(conn, "owner", rid, occ_ids[0])
    with pytest.raises(ValueError):
        reports.record_full_text_assessment(conn, "owner", rid, "included", exclusion_reason="x")
    conn.close()


# Directive C: full-text reference item 5 -- Maybe is non-terminal at
# the full-text stage, mirroring the screening-stage Maybe vote.
def test_maybe_outcome_stored_without_reason(tmp_path):
    conn, occ_ids = _setup(tmp_path)
    rid = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], rid)
    reports.assign_progression(conn, "owner", rid, occ_ids[0])

    reports.record_full_text_assessment(conn, "owner", rid, "maybe")
    row = conn.execute(
        "SELECT retrieval_status, full_text_outcome, exclusion_reason FROM report_retrievals WHERE report_id=?",
        (rid,),
    ).fetchone()
    assert row["full_text_outcome"] == "maybe"
    assert row["exclusion_reason"] is None
    conn.close()


def test_maybe_must_not_carry_reason(tmp_path):
    conn, occ_ids = _setup(tmp_path)
    rid = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], rid)
    reports.assign_progression(conn, "owner", rid, occ_ids[0])
    with pytest.raises(ValueError):
        reports.record_full_text_assessment(conn, "owner", rid, "maybe", exclusion_reason="x")
    conn.close()


def test_maybe_assessed_report_counts_as_pending_not_included_or_excluded(tmp_path):
    conn, occ_ids = _setup(tmp_path, n_occurrences=2)
    rid0 = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], rid0)
    reports.assign_progression(conn, "owner", rid0, occ_ids[0])
    rid1 = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[1], rid1)
    reports.assign_progression(conn, "owner", rid1, occ_ids[1])

    reports.record_full_text_assessment(conn, "owner", rid0, "maybe")
    reports.record_full_text_assessment(conn, "owner", rid1, "included")

    c = reports.counts(conn)
    assert c["reports_sought"] == 2
    assert c["reports_pending"] == 1  # the maybe-assessed report
    assert c["reports_included"] == 1
    assert c["reports_excluded"] == 0
    assert c["reports_assessed"] == 1
    # Both PRISMA equations (spec §3.2) must still hold with maybe present.
    assert c["reports_assessed"] == c["reports_included"] + c["reports_excluded"]
    assert c["reports_sought"] == c["reports_assessed"] + c["reports_not_retrieved"] + c["reports_pending"]
    conn.close()


def test_maybe_report_reassessed_to_excluded_then_included(tmp_path):
    conn, occ_ids = _setup(tmp_path)
    rid = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_ids[0], rid)
    reports.assign_progression(conn, "owner", rid, occ_ids[0])

    reports.record_full_text_assessment(conn, "owner", rid, "maybe")
    reports.record_full_text_assessment(conn, "owner", rid, "excluded", exclusion_reason="reason-X")
    row = conn.execute(
        "SELECT full_text_outcome, exclusion_reason FROM report_retrievals WHERE report_id=?", (rid,)
    ).fetchone()
    assert row["full_text_outcome"] == "excluded"
    assert row["exclusion_reason"] == "reason-X"

    reports.record_full_text_assessment(conn, "owner", rid, "included")
    row = conn.execute(
        "SELECT full_text_outcome, exclusion_reason FROM report_retrievals WHERE report_id=?", (rid,)
    ).fetchone()
    assert row["full_text_outcome"] == "included"
    assert row["exclusion_reason"] is None

    reports.record_full_text_assessment(conn, "owner", rid, "maybe")
    row = conn.execute(
        "SELECT full_text_outcome FROM report_retrievals WHERE report_id=?", (rid,)
    ).fetchone()
    assert row["full_text_outcome"] == "maybe"
    conn.close()


# §3.4's report equations (reports_sought_b, reports_assessed_b, ...)
# are explicitly per-branch, and invariant 6 requires each report be
# attributable to exactly one branch at each stage -- counts() alone
# never exercised that dimension. Closing that gap here with a real
# two-branch fixture whose per-branch totals sum to the known global
# totals.
def test_counts_by_branch_sums_to_global_totals(tmp_path):
    conn, occ_a = _setup(tmp_path, n_occurrences=2, branch_id="A")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('B','B',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s2','s2','register','B',datetime('now'))"
    )
    conn.commit()
    result_b = commit_csv_import(
        conn, "title\nTitle B1\nTitle B2\n", {0: "title"}, source_id="s2", branch_id="B",
        operation_id="op-b", actor="owner",
    )
    occ_b = [
        r["occurrence_id"] for r in conn.execute(
            "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result_b.batch_id,)
        ).fetchall()
    ]

    # Branch A: one included, one not retrieved.
    ra1 = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_a[0], ra1)
    reports.assign_progression(conn, "owner", ra1, occ_a[0])
    reports.record_full_text_assessment(conn, "owner", ra1, "included")

    ra2 = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_a[1], ra2)
    reports.assign_progression(conn, "owner", ra2, occ_a[1])
    reports.mark_not_retrieved(conn, "owner", ra2)

    # Branch B: one excluded with a reason, one pending.
    rb1 = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_b[0], rb1)
    reports.assign_progression(conn, "owner", rb1, occ_b[0])
    reports.record_full_text_assessment(conn, "owner", rb1, "excluded", exclusion_reason="reason-Y")

    rb2 = reports.create_report(conn, "owner")
    reports.link_occurrence_to_report(conn, "owner", occ_b[1], rb2)
    reports.assign_progression(conn, "owner", rb2, occ_b[1])
    # rb2 stays pending (no action).

    by_branch = reports.counts_by_branch(conn)
    a = by_branch["A"]
    assert a["reports_sought"] == 2
    assert a["reports_included"] == 1
    assert a["reports_not_retrieved"] == 1
    assert a["reports_assessed"] == a["reports_included"] + a["reports_excluded"]

    b = by_branch["B"]
    assert b["reports_sought"] == 2
    assert b["reports_excluded"] == 1
    assert b["reports_pending"] == 1
    assert b["reasons"]["reason-Y"] == 1
    assert sum(b["reasons"].values()) == b["reports_excluded"]

    # Per-branch totals sum to the global totals.
    total = reports.counts(conn)
    assert a["reports_sought"] + b["reports_sought"] == total["reports_sought"]
    assert a["reports_included"] + b["reports_included"] == total["reports_included"]
    assert a["reports_excluded"] + b["reports_excluded"] == total["reports_excluded"]
    assert a["reports_not_retrieved"] + b["reports_not_retrieved"] == total["reports_not_retrieved"]
    assert a["reports_pending"] + b["reports_pending"] == total["reports_pending"]

    from screening_workbench import prisma
    assert prisma.verify_invariants(conn) == []
    conn.close()

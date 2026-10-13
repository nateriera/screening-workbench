import pytest

from screening_workbench import db, reports, studies
from screening_workbench.importers.csv_importer import commit_csv_import


def _setup_reports(tmp_path, n=3):
    conn = db.connect(tmp_path / "t.db")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    rows = "\n".join(f"Title {i}" for i in range(n))
    result = commit_csv_import(
        conn, "title\n" + rows + "\n", {0: "title"}, source_id="s1", branch_id="b1",
        operation_id="op1", actor="owner",
    )
    occ_ids = [
        r["occurrence_id"] for r in conn.execute(
            "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
        ).fetchall()
    ]
    report_ids = []
    for occ_id in occ_ids:
        rid = reports.create_report(conn, "owner")
        reports.link_occurrence_to_report(conn, "owner", occ_id, rid)
        reports.assign_progression(conn, "owner", rid, occ_id)
        report_ids.append(rid)
    return conn, report_ids


def test_create_study_and_decision(tmp_path):
    conn, _ = _setup_reports(tmp_path, n=1)
    sid = studies.create_study(conn, "owner")
    studies.set_study_decision(conn, "owner", sid, "included", "meets criteria")
    row = conn.execute("SELECT * FROM study_decisions WHERE study_id=?", (sid,)).fetchone()
    assert row["decision"] == "included"
    conn.close()


def test_decision_requires_rationale(tmp_path):
    conn, _ = _setup_reports(tmp_path, n=1)
    sid = studies.create_study(conn, "owner")
    with pytest.raises(ValueError):
        studies.set_study_decision(conn, "owner", sid, "included", "")
    conn.close()


def test_link_alone_does_not_include(tmp_path):
    conn, report_ids = _setup_reports(tmp_path, n=1)
    sid = studies.create_study(conn, "owner")
    studies.link_report_study(conn, "owner", report_ids[0], sid)
    c = studies.counts(conn)
    assert c["studies_included"] == 0  # no explicit included decision yet
    conn.close()


def test_reports_for_study_lists_active_links_only(tmp_path):
    conn, report_ids = _setup_reports(tmp_path, n=2)
    sid = studies.create_study(conn, "owner")
    studies.link_report_study(conn, "owner", report_ids[0], sid)
    studies.link_report_study(conn, "owner", report_ids[1], sid)
    assert set(studies.reports_for_study(conn, sid)) == set(report_ids)

    studies.unlink_report_study(conn, "owner", report_ids[1], sid, "wrong link")
    assert studies.reports_for_study(conn, sid) == [report_ids[0]]

    other_sid = studies.create_study(conn, "owner")
    assert studies.reports_for_study(conn, other_sid) == []
    conn.close()


# Acceptance test 4: three reports, two studies, four links (one a repeat).
def test_acceptance_4_study_report_fixture(tmp_path):
    conn, (r1, r2, r3) = _setup_reports(tmp_path, n=3)
    reports.record_full_text_assessment(conn, "owner", r1, "included")
    reports.record_full_text_assessment(conn, "owner", r2, "excluded", exclusion_reason="reason-X")
    reports.mark_not_retrieved(conn, "owner", r3)

    s1 = studies.create_study(conn, "owner")
    s2 = studies.create_study(conn, "owner")
    studies.set_study_decision(conn, "owner", s1, "included", "primary study")
    studies.set_study_decision(conn, "owner", s2, "excluded", "ineligible design")

    studies.link_report_study(conn, "owner", r1, s1)
    studies.link_report_study(conn, "owner", r2, s1)
    studies.link_report_study(conn, "owner", r2, s2)
    studies.link_report_study(conn, "owner", r3, s2)
    # Repeated link-add/correction event: re-add an existing pair.
    studies.link_report_study(conn, "owner", r1, s1, rationale="re-confirmed")

    assert studies.active_link_count(conn) == 4  # (r1,s1)(r2,s1)(r2,s2)(r3,s2)
    assert studies.link_history_count(conn) == 5  # 4 original adds + 1 repeat

    rep_counts = reports.counts(conn)
    assert rep_counts["reports_sought"] == 3
    assert rep_counts["reports_not_retrieved"] == 1
    assert rep_counts["reports_assessed"] == 2
    assert rep_counts["reports_included"] == 1
    assert rep_counts["reports_excluded"] == 1
    assert rep_counts["reasons"]["reason-X"] == 1

    sc = studies.counts(conn)
    assert sc["reports_of_included_studies"] == 1  # only r1 (included + linked to included study s1)
    assert sc["studies_included"] == 1             # only s1

    # Correct S2 to included: its linked reports (r2 excluded, r3 not
    # retrieved) give it no terminal included report -> conflict.
    studies.set_study_decision(conn, "owner", s2, "included", "reconsidered")
    assert studies.detect_conflict(conn, s2) is True

    # Correct back to excluded with rationale; conflict resolves.
    studies.set_study_decision(conn, "owner", s2, "excluded", "confirmed exclusion stands")
    assert studies.detect_conflict(conn, s2) is False
    sc2 = studies.counts(conn)
    assert sc2["studies_included"] == 1  # unchanged by the duplicate-history event
    conn.close()


# Acceptance test 5: all linked reports excluded while study included blocks.
def test_acceptance_5_study_conflict_fixture(tmp_path):
    conn, (r1, r2) = _setup_reports(tmp_path, n=2)
    reports.record_full_text_assessment(conn, "owner", r1, "excluded", exclusion_reason="wrong population")
    reports.record_full_text_assessment(conn, "owner", r2, "excluded", exclusion_reason="wrong population")

    sid = studies.create_study(conn, "owner")
    studies.link_report_study(conn, "owner", r1, sid)
    studies.link_report_study(conn, "owner", r2, sid)
    studies.set_study_decision(conn, "owner", sid, "included", "should have an included report")

    assert studies.detect_conflict(conn, sid) is True

    # One included + one excluded report may coexist with an included study.
    reports.record_full_text_assessment(conn, "owner", r1, "included")
    # (direct re-assessment after an excluded terminal state is a modeling
    # simplification for this fixture; full-text correction workflow is a
    # documented v1 gap noted in reports.py.)
    assert studies.detect_conflict(conn, sid) is False
    conn.close()


def test_unresolved_decision_with_links_is_conflict(tmp_path):
    conn, (r1,) = _setup_reports(tmp_path, n=1)
    sid = studies.create_study(conn, "owner")
    studies.link_report_study(conn, "owner", r1, sid)
    studies.set_study_decision(conn, "owner", sid, "unresolved", "pending adjudication")
    assert studies.detect_conflict(conn, sid) is True
    conn.close()


def test_unlink_requires_rationale(tmp_path):
    conn, (r1,) = _setup_reports(tmp_path, n=1)
    sid = studies.create_study(conn, "owner")
    studies.link_report_study(conn, "owner", r1, sid)
    with pytest.raises(ValueError):
        studies.unlink_report_study(conn, "owner", r1, sid, "")
    conn.close()


def test_unlink_removes_active_but_keeps_history(tmp_path):
    conn, (r1,) = _setup_reports(tmp_path, n=1)
    sid = studies.create_study(conn, "owner")
    studies.link_report_study(conn, "owner", r1, sid)
    studies.unlink_report_study(conn, "owner", r1, sid, "mistaken link")
    assert studies.active_link_count(conn) == 0
    assert studies.link_history_count(conn) == 2  # add + remove, both retained
    conn.close()

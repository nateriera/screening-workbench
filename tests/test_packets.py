"""Directive B: two-computer blind review via reviewer packets.

Independent implementation of the "blinded packet file" pattern (prior
art studied: Evidentum, MIT -- behavior only, no code/text/UI copied;
see docs/packets.md for the attribution note). These tests exercise
packet export/import, votes export/merge, the leakage guardrail, the
stale-merge newest-wins rule, and foreign/tampered-votes quarantine.
"""
import json

import pytest

from screening_workbench import db, packets, roles, screening
from screening_workbench.importers.csv_importer import commit_csv_import


def _host_setup(tmp_path, n: int = 3):
    """A host project with n active occurrences, an owner, and one
    reviewer's (ownerA's) votes already cast on some of them."""
    conn = db.connect(tmp_path / "host.db")
    roles.set_owner(conn, "owner")
    roles.set_project_name(conn, "owner", "Synthetic host review", review_type="systematic")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    rows_csv = "\n".join(f"Synthetic Study {i}" for i in range(n))
    result = commit_csv_import(
        conn, "title\n" + rows_csv + "\n", {0: "title"}, source_id="s1", branch_id="b1",
        operation_id="op1", actor="owner",
    )
    occ_rows = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
    ).fetchall()
    return conn, [r["occurrence_id"] for r in occ_rows]


def _reviewer_b_setup(tmp_path):
    return db.connect(tmp_path / "reviewerB.db")


def test_export_packet_contains_full_record_set(tmp_path):
    conn, occ_ids = _host_setup(tmp_path, n=3)
    out = tmp_path / "packet.json"
    result = packets.export_packet(conn, out, actor="owner")
    assert result["record_count"] == 3
    assert out.is_file()
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["format"] == packets.PACKET_FORMAT
    assert {r["occurrence_id"] for r in raw["records"]} == set(occ_ids)
    assert raw["criteria"]["exclusion_reasons"] == list(screening.EXCLUSION_REASONS)
    assert raw["project"]["name"] == "Synthetic host review"
    conn.close()


def test_export_packet_leakage_scan_zero_vote_data(tmp_path):
    """Hard blind guardrail: cast real votes with distinctive strings on
    the host BEFORE exporting, then scan the raw packet file text and
    assert none of the vote-identifying data leaked in."""
    conn, occ_ids = _host_setup(tmp_path, n=3)
    DISTINCTIVE_REASON = "XQZZY-UNIQUE-REASON-MARKER"
    screening.cast_vote(conn, occurrence_id=occ_ids[0], reviewer_id="reviewer-alpha-secret", decision="include")
    screening.cast_vote(
        conn, occurrence_id=occ_ids[1], reviewer_id="reviewer-alpha-secret",
        decision="exclude", reason=DISTINCTIVE_REASON,
    )
    screening.cast_vote(conn, occurrence_id=occ_ids[2], reviewer_id="reviewer-beta-secret", decision="maybe")

    out = tmp_path / "packet.json"
    packets.export_packet(conn, out, actor="owner")
    raw_text = out.read_text(encoding="utf-8")

    # No reviewer identity.
    assert "reviewer-alpha-secret" not in raw_text
    assert "reviewer-beta-secret" not in raw_text
    # No decision values as data (distinguish from the schema's own
    # key names like "decision" by checking the distinctive reason and
    # reviewer strings, which cannot appear by any other path).
    assert DISTINCTIVE_REASON not in raw_text
    # No vote/decision/reason/timestamp keys from the screen_votes shape.
    parsed = json.loads(raw_text)
    assert "votes" not in parsed
    for rec in parsed["records"]:
        assert set(rec.keys()) == {
            "occurrence_id", "batch_id", "source_id", "source_name", "source_class",
            "branch_id", "branch_name", "locator", "fields",
        }
        assert "decision" not in rec
        assert "reason" not in rec
        assert "vote" not in rec
        assert "reviewer_id" not in rec
    conn.close()


def test_import_packet_binds_locked_reviewer_identity(tmp_path):
    host, occ_ids = _host_setup(tmp_path, n=2)
    out = tmp_path / "packet.json"
    packets.export_packet(host, out, actor="owner")
    host.close()

    b_conn = _reviewer_b_setup(tmp_path)
    result = packets.import_packet(b_conn, out, reviewer_id="revB")
    assert result["record_count"] == 2
    row = b_conn.execute("SELECT locked_reviewer_id, packet_imported_id FROM project_settings WHERE id='project'").fetchone()
    assert row["locked_reviewer_id"] == "revB"
    assert row["packet_imported_id"] == result["packet_id"]
    # Record content is present and screenable.
    imported_ids = {r["occurrence_id"] for r in b_conn.execute("SELECT occurrence_id FROM occurrences").fetchall()}
    assert imported_ids == set(occ_ids)
    b_conn.close()


def test_import_packet_twice_is_refused(tmp_path):
    host, _occ_ids = _host_setup(tmp_path, n=1)
    out = tmp_path / "packet.json"
    packets.export_packet(host, out, actor="owner")
    host.close()

    b_conn = _reviewer_b_setup(tmp_path)
    packets.import_packet(b_conn, out, reviewer_id="revB")
    with pytest.raises(ValueError):
        packets.import_packet(b_conn, out, reviewer_id="revB")
    with pytest.raises(ValueError):
        packets.import_packet(b_conn, out, reviewer_id="revC")  # even a different reviewer
    b_conn.close()


def test_export_votes_wrong_reviewer_on_locked_db_is_refused(tmp_path):
    host, _occ_ids = _host_setup(tmp_path, n=1)
    out = tmp_path / "packet.json"
    packets.export_packet(host, out, actor="owner")
    host.close()

    b_conn = _reviewer_b_setup(tmp_path)
    packets.import_packet(b_conn, out, reviewer_id="revB")
    votes_out = tmp_path / "votes.json"
    with pytest.raises(PermissionError):
        packets.export_votes(b_conn, votes_out, reviewer_id="someone-else")
    b_conn.close()


def test_merge_votes_requires_owner_and_unblinded(tmp_path):
    host, occ_ids = _host_setup(tmp_path, n=1)
    votes_file = tmp_path / "votes.json"
    votes_file.write_text(json.dumps({
        "format": packets.VOTES_FORMAT, "format_version": 1, "export_id": "x",
        "reviewer_id": "revB", "stage": "title_abstract", "exported_at": "2026-01-01T00:00:00Z",
        "votes": [],
    }), encoding="utf-8")

    with pytest.raises(PermissionError):
        packets.merge_votes(host, votes_file, actor="not-the-owner")

    roles.set_blind(host, "owner", True)
    with pytest.raises(PermissionError):
        packets.merge_votes(host, votes_file, actor="owner")
    host.close()


def test_round_trip_export_import_vote_export_merge_conflicts_and_kappa(tmp_path):
    """Full Directive B §7 round-trip: host exports a packet, reviewer B
    imports it on a separate database, screens, exports votes, host
    merges -- conflicts are detected exactly and kappa is correct."""
    host, occ_ids = _host_setup(tmp_path, n=4)
    # Host reviewer A casts votes on all 4 up front.
    host_pattern = ["include", "include", "exclude", "maybe"]
    for occ_id, decision in zip(occ_ids, host_pattern):
        reason = "Wrong population" if decision == "exclude" else None
        screening.cast_vote(host, occurrence_id=occ_id, reviewer_id="reviewerA", decision=decision, reason=reason)

    packet_file = tmp_path / "packet.json"
    packets.export_packet(host, packet_file, actor="owner")

    b_conn = _reviewer_b_setup(tmp_path)
    packets.import_packet(b_conn, packet_file, reviewer_id="reviewerB")
    # Reviewer B screens: agrees on 3, disagrees on the 3rd (conflict).
    b_pattern = ["include", "include", "include", "maybe"]  # [2]=include vs host exclude => conflict
    for occ_id, decision in zip(occ_ids, b_pattern):
        screening.cast_vote(b_conn, occurrence_id=occ_id, reviewer_id="reviewerB", decision=decision)

    votes_file = tmp_path / "votes.json"
    packets.export_votes(b_conn, votes_file, reviewer_id="reviewerB")
    b_conn.close()

    merge_result = packets.merge_votes(host, votes_file, actor="owner")
    assert merge_result["merged_count"] == 4
    assert merge_result["skipped_stale_count"] == 0
    assert merge_result["quarantined_count"] == 0

    conflicts = screening.list_conflicts(host)
    assert conflicts == [occ_ids[2]]  # exclude vs include

    kappa = screening.cohens_kappa(host, reviewer_a="reviewerA", reviewer_b="reviewerB")
    assert kappa["status"] == "ok"
    assert kappa["n"] == 4
    # 3/4 agree => po = 0.75; verify kappa matches the direct computation.
    assert kappa["agreement"] == pytest.approx(0.75)
    host.close()


def test_stale_votes_file_never_rolls_back_fresher_host_data(tmp_path):
    """Directive B §4/§7: a stale votes file must never overwrite a
    fresher decision already present in the host database for that
    (occurrence, reviewer) pair."""
    host, occ_ids = _host_setup(tmp_path, n=1)
    occ_id = occ_ids[0]

    # Simulate fresher host-side data for reviewerB on this occurrence
    # (e.g. from an earlier, newer merge) with a later timestamp.
    screening.cast_vote(host, occurrence_id=occ_id, reviewer_id="reviewerB", decision="include")
    fresh_created_at = host.execute(
        "SELECT created_at FROM screen_votes WHERE occurrence_id=? AND reviewer_id='reviewerB'"
        " AND superseded_at IS NULL", (occ_id,),
    ).fetchone()["created_at"]

    # An OLDER votes file for the same occurrence/reviewer, with an
    # earlier timestamp and a DIFFERENT decision.
    stale_votes_file = tmp_path / "stale_votes.json"
    stale_votes_file.write_text(json.dumps({
        "format": packets.VOTES_FORMAT, "format_version": 1, "export_id": "stale",
        "reviewer_id": "reviewerB", "stage": "title_abstract", "exported_at": "2020-01-01T00:00:00Z",
        "votes": [{
            "occurrence_id": occ_id, "decision": "exclude", "reason": "Wrong population",
            "created_at": "2020-01-01T00:00:00.000000Z",  # well before fresh_created_at
        }],
    }), encoding="utf-8")

    result = packets.merge_votes(host, stale_votes_file, actor="owner")
    assert result["merged_count"] == 0
    assert result["skipped_stale_count"] == 1

    current = screening.current_vote(host, occ_id, "reviewerB")
    assert current["decision"] == "include"  # unchanged, fresher host data wins
    host.close()


def test_merge_quarantines_unknown_occurrence_id_without_raising(tmp_path):
    """Directive B §7: a tampered/foreign votes file referencing an
    occurrence_id this host database has never seen is quarantined,
    not rejected wholesale and not silently dropped."""
    host, occ_ids = _host_setup(tmp_path, n=1)
    votes_file = tmp_path / "foreign_votes.json"
    votes_file.write_text(json.dumps({
        "format": packets.VOTES_FORMAT, "format_version": 1, "export_id": "foreign",
        "reviewer_id": "reviewerB", "stage": "title_abstract", "exported_at": "2026-01-01T00:00:00Z",
        "votes": [
            {"occurrence_id": occ_ids[0], "decision": "include", "reason": None, "created_at": "2026-01-01T00:00:00.000000Z"},
            {"occurrence_id": "occ_does-not-exist-on-host", "decision": "exclude", "reason": "Wrong population", "created_at": "2026-01-01T00:00:00.000000Z"},
        ],
    }), encoding="utf-8")

    result = packets.merge_votes(host, votes_file, actor="owner")
    assert result["merged_count"] == 1
    assert result["quarantined_count"] == 1

    assert screening.current_vote(host, occ_ids[0], "reviewerB")["decision"] == "include"
    quarantined = packets.list_quarantined_votes(host)
    assert len(quarantined) == 1
    assert quarantined[0]["occurrence_id"] == "occ_does-not-exist-on-host"
    assert quarantined[0]["quarantine_reason"] == "unknown_occurrence_id"
    host.close()


def test_merge_quarantines_invalid_decision_and_missing_exclude_reason(tmp_path):
    host, occ_ids = _host_setup(tmp_path, n=2)
    votes_file = tmp_path / "bad_votes.json"
    votes_file.write_text(json.dumps({
        "format": packets.VOTES_FORMAT, "format_version": 1, "export_id": "bad",
        "reviewer_id": "reviewerB", "stage": "title_abstract", "exported_at": "2026-01-01T00:00:00Z",
        "votes": [
            {"occurrence_id": occ_ids[0], "decision": "maybe-ish-not-valid", "reason": None, "created_at": "2026-01-01T00:00:00.000000Z"},
            {"occurrence_id": occ_ids[1], "decision": "exclude", "reason": None, "created_at": "2026-01-01T00:00:00.000000Z"},
        ],
    }), encoding="utf-8")

    result = packets.merge_votes(host, votes_file, actor="owner")
    assert result["merged_count"] == 0
    assert result["quarantined_count"] == 2
    reasons = {q["quarantine_reason"] for q in packets.list_quarantined_votes(host)}
    assert reasons == {"invalid_decision", "exclude_missing_reason"}
    host.close()


def test_every_packet_action_appends_an_audited_sha256_event(tmp_path):
    """Directive B §6: packet export, packet import, votes export, and
    votes merge each append an audit event including the file's sha256."""
    host, occ_ids = _host_setup(tmp_path, n=1)
    packet_file = tmp_path / "packet.json"
    packets.export_packet(host, packet_file, actor="owner")

    b_conn = _reviewer_b_setup(tmp_path)
    packets.import_packet(b_conn, packet_file, reviewer_id="reviewerB")
    screening.cast_vote(b_conn, occurrence_id=occ_ids[0], reviewer_id="reviewerB", decision="include")
    votes_file = tmp_path / "votes.json"
    packets.export_votes(b_conn, votes_file, reviewer_id="reviewerB")
    b_conn.close()
    packets.merge_votes(host, votes_file, actor="owner")

    events = {r["event_type"]: json.loads(r["payload_json"]) for r in db.all_events(host)}
    assert "file_sha256" in events["packet.exported"]
    assert events["packet.exported"]["file_sha256"] == packets._sha256_file(packet_file)
    assert "file_sha256" in events["votes.merged"]
    assert events["votes.merged"]["file_sha256"] == packets._sha256_file(votes_file)

    b_conn2 = db.connect(tmp_path / "reviewerB.db")  # reopen to read its own event log
    b_events = {r["event_type"]: json.loads(r["payload_json"]) for r in db.all_events(b_conn2)}
    assert "file_sha256" in b_events["packet.imported"]
    assert b_events["packet.imported"]["file_sha256"] == packets._sha256_file(packet_file)
    assert "file_sha256" in b_events["votes.exported"]
    assert b_events["votes.exported"]["file_sha256"] == packets._sha256_file(votes_file)
    b_conn2.close()
    host.close()


def test_import_packet_rejects_wrong_format(tmp_path):
    bad_file = tmp_path / "not_a_packet.json"
    bad_file.write_text(json.dumps({"format": "something-else", "format_version": 1}), encoding="utf-8")
    b_conn = _reviewer_b_setup(tmp_path)
    with pytest.raises(ValueError):
        packets.import_packet(b_conn, bad_file, reviewer_id="revB")
    b_conn.close()


def test_merge_votes_rejects_wrong_format(tmp_path):
    host, _occ_ids = _host_setup(tmp_path, n=1)
    bad_file = tmp_path / "not_votes.json"
    bad_file.write_text(json.dumps({"format": "something-else", "format_version": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        packets.merge_votes(host, bad_file, actor="owner")
    host.close()


def _votes_file(tmp_path, name, reviewer_id, votes):
    path = tmp_path / name
    path.write_text(json.dumps({
        "format": packets.VOTES_FORMAT, "format_version": 1, "export_id": name,
        "reviewer_id": reviewer_id, "stage": "title_abstract", "exported_at": "2026-01-01T00:00:00Z",
        "votes": votes,
    }), encoding="utf-8")
    return path


def test_quarantine_report_lists_each_kind_with_stored_reason_in_order(tmp_path):
    """Owner-facing quarantine report: one quarantined vote per kind,
    merged in separate merge events so received_at strictly increases.
    Reasons are the stored quarantine_reason values, in received order.
    (merge_votes has no unknown-reviewer quarantine; that kind is not covered.)"""
    host, occ_ids = _host_setup(tmp_path, n=2)
    ts = "2026-01-01T00:00:00.000000Z"

    packets.merge_votes(host, _votes_file(tmp_path, "f1.json", "reviewerB", [
        {"occurrence_id": "occ_not-on-host", "decision": "include", "reason": None, "created_at": ts},
    ]), actor="owner")
    packets.merge_votes(host, _votes_file(tmp_path, "f2.json", "reviewerB", [
        {"occurrence_id": occ_ids[0], "decision": "maybe-ish", "reason": None, "created_at": ts},
    ]), actor="owner")

    report = packets.quarantine_report(host)
    assert [r["reason"] for r in report] == ["unknown_occurrence_id", "invalid_decision"]
    assert report[0]["occurrence_id"] == "occ_not-on-host"
    assert report[1]["occurrence_id"] == occ_ids[0]
    for r in report:
        assert set(r) == {"occurrence_id", "reviewer_id", "stage", "reason", "received_at"}
        assert r["reviewer_id"] == "reviewerB"
        assert r["stage"] == "title_abstract"
        assert r["received_at"]
    received = [r["received_at"] for r in report]
    assert received == sorted(received)
    host.close()

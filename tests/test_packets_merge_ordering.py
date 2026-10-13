"""Invariant tests for packets.merge_votes newest-wins ordering.

merge_votes decides newest-wins by comparing ``created_at`` strings
lexicographically (``existing >= incoming`` means skip). That is only
correct while every timestamp is the same fixed-width UTC RFC 3339 shape.
These tests pin that shape at the export boundary and pin the merge
behavior the rule implies.
"""
import datetime as _dt
import json
import re

from screening_workbench import db, packets, screening
from screening_workbench.importers.csv_importer import commit_csv_import

RFC3339_UTC_MICROS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def _host_setup(tmp_path, n: int = 1):
    conn = db.connect(tmp_path / "host.db")
    from screening_workbench import roles
    roles.set_owner(conn, "owner")
    roles.set_project_name(conn, "owner", "Synthetic ordering review", review_type="systematic")
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


def _write_votes(path, votes):
    path.write_text(json.dumps({
        "format": packets.VOTES_FORMAT, "format_version": 1, "export_id": "test",
        "reviewer_id": "reviewerB", "stage": "title_abstract",
        "exported_at": "2026-06-01T00:00:00.000000Z", "votes": votes,
    }), encoding="utf-8")


def _current_row(conn, occ_id, reviewer_id="reviewerB"):
    return conn.execute(
        "SELECT decision, created_at FROM screen_votes WHERE occurrence_id=? AND reviewer_id=?"
        " AND stage='title_abstract' AND superseded_at IS NULL",
        (occ_id, reviewer_id),
    ).fetchone()


def test_exported_vote_timestamps_are_utc_rfc3339(tmp_path):
    """Invariant (a): every created_at written by export_votes is a
    fixed-width UTC RFC 3339 string, the shape newest-wins relies on."""
    host, occ_ids = _host_setup(tmp_path, n=2)
    packet_file = tmp_path / "packet.json"
    packets.export_packet(host, packet_file, actor="owner")

    reviewer = db.connect(tmp_path / "reviewerB.db")
    packets.import_packet(reviewer, packet_file, reviewer_id="reviewerB")
    for occ in occ_ids:
        screening.cast_vote(reviewer, occurrence_id=occ, reviewer_id="reviewerB", decision="include")

    out = tmp_path / "votes.json"
    packets.export_votes(reviewer, out, reviewer_id="reviewerB")
    votes = json.loads(out.read_text(encoding="utf-8"))["votes"]
    assert len(votes) == 2
    for v in votes:
        ts = v["created_at"]
        assert RFC3339_UTC_MICROS.match(ts), f"not UTC RFC 3339 fixed-width: {ts!r}"
        parsed = _dt.datetime.fromisoformat(ts)
        assert parsed.utcoffset() == _dt.timedelta(0), f"not UTC: {ts!r}"
    reviewer.close()
    host.close()


def test_stale_then_fresh_vote_pair_keeps_fresh_vote(tmp_path):
    """Invariant (b): a votes file holding a stale vote followed by a fresh
    vote for the same (occurrence, reviewer) leaves the fresh vote current."""
    host, occ_ids = _host_setup(tmp_path, n=1)
    occ = occ_ids[0]
    votes_file = tmp_path / "votes.json"
    _write_votes(votes_file, [
        {"occurrence_id": occ, "decision": "exclude", "reason": "Wrong population",
         "created_at": "2020-01-01T00:00:00.000000Z"},
        {"occurrence_id": occ, "decision": "include", "reason": None,
         "created_at": "2026-06-01T00:00:00.000000Z"},
    ])

    result = packets.merge_votes(host, votes_file, actor="owner")
    assert result["quarantined_count"] == 0
    current = _current_row(host, occ)
    assert current["decision"] == "include"
    assert current["created_at"] == "2026-06-01T00:00:00.000000Z"
    host.close()


def test_equal_timestamp_resolves_to_existing_host_vote(tmp_path):
    """Invariant (c): when an incoming vote's created_at equals the host's
    current vote timestamp, the merge skips the incoming vote (the check is
    ``existing >= incoming``). The outcome is deterministic: host vote kept."""
    host, occ_ids = _host_setup(tmp_path, n=1)
    occ = occ_ids[0]
    screening.cast_vote(host, occurrence_id=occ, reviewer_id="reviewerB", decision="include")
    host_ts = _current_row(host, occ)["created_at"]

    votes_file = tmp_path / "votes.json"
    _write_votes(votes_file, [
        {"occurrence_id": occ, "decision": "exclude", "reason": "Wrong population",
         "created_at": host_ts},
    ])

    result = packets.merge_votes(host, votes_file, actor="owner")
    assert result["merged_count"] == 0
    assert result["skipped_stale_count"] == 1
    current = _current_row(host, occ)
    assert current["decision"] == "include"
    assert current["created_at"] == host_ts
    host.close()

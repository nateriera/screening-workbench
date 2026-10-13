"""End-to-end: blind two-reviewer packet flow (Directive B).

Owner exports a reviewer packet (zero vote data); reviewer B imports it into
a fresh DB (identity lock); B screens blind and exports a votes file; owner
merges unblinded. Asserts disagreements become conflicts, agreements do not,
and kappa_readout returns ok with n > 0.
"""
import json

import pytest

from screening_workbench import db, packets, roles, screening
from screening_workbench.importers.csv_importer import commit_csv_import

HOST_REVIEWER = "reviewerA"
B_REVIEWER = "reviewerB"
# Host (A) vs B decisions per record. Index 0,1 agree; 2,3 disagree.
HOST_DECISIONS = ["include", "exclude", "include", "maybe"]
B_DECISIONS = ["include", "exclude", "exclude", "include"]


def _host(tmp_path):
    (tmp_path / "host").mkdir(exist_ok=True)
    conn = db.connect(tmp_path / "host" / "host.db")
    roles.set_owner(conn, "owner")
    roles.set_project_name(conn, "owner", "E2E blind review", review_type="systematic")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    csv_body = "title\n" + "\n".join(f"Synthetic Study {i}" for i in range(len(HOST_DECISIONS))) + "\n"
    result = commit_csv_import(
        conn, csv_body, {0: "title"}, source_id="s1", branch_id="b1",
        operation_id="op-e2e", actor="owner",
    )
    rows = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id=? ORDER BY locator", (result.batch_id,)
    ).fetchall()
    return conn, [r["occurrence_id"] for r in rows]


def test_blind_two_reviewer_end_to_end(tmp_path):
    host, occ_ids = _host(tmp_path)
    assert len(occ_ids) == len(HOST_DECISIONS)

    # Host reviewer A votes before export, so the vote data exists to leak.
    for occ, dec in zip(occ_ids, HOST_DECISIONS):
        screening.cast_vote(
            host, occurrence_id=occ, reviewer_id=HOST_REVIEWER, decision=dec,
            reason="Wrong population" if dec == "exclude" else None,
        )

    # (a) Owner exports packet; assert zero vote data in the file.
    packet_file = tmp_path / "packet.json"
    exp = packets.export_packet(host, packet_file, actor="owner")
    assert exp["record_count"] == len(occ_ids)
    raw = json.loads(packet_file.read_text(encoding="utf-8"))
    text = packet_file.read_text(encoding="utf-8")
    for rec in raw["records"]:
        assert set(rec) == {
            "occurrence_id", "batch_id", "source_id", "source_name", "source_class",
            "branch_id", "branch_name", "locator", "fields",
        }, "record carries unexpected keys (possible vote leakage)"
    for forbidden_key in ("votes", "decision", "reason", "created_at", "reviewer_id", "screen_votes"):
        assert f'"{forbidden_key}"' not in text, f"vote-related key {forbidden_key!r} leaked"
    assert HOST_REVIEWER not in text, "host reviewer identity leaked into packet"
    for occ in occ_ids:
        for vote in host.execute("SELECT vote_id FROM screen_votes WHERE occurrence_id=?", (occ,)).fetchall():
            assert vote["vote_id"] not in text, "vote_id leaked into packet"

    # (b) Reviewer B imports into a fresh DB; second import refused (identity lock).
    b_dir = tmp_path / "reviewerB"
    b_dir.mkdir(exist_ok=True)
    b_conn = db.connect(b_dir / "b.db")
    imp = packets.import_packet(b_conn, packet_file, reviewer_id=B_REVIEWER)
    assert imp["record_count"] == len(occ_ids)
    with pytest.raises(ValueError, match="already imported"):
        packets.import_packet(b_conn, packet_file, reviewer_id=B_REVIEWER)
    with pytest.raises(ValueError, match="already imported"):
        packets.import_packet(b_conn, packet_file, reviewer_id="someoneElse")
    with pytest.raises(PermissionError, match="locked"):
        packets.export_votes(b_conn, tmp_path / "x.json", reviewer_id="someoneElse")

    # (c) B screens blind and exports votes file.
    for occ, dec in zip(occ_ids, B_DECISIONS):
        screening.cast_vote(
            b_conn, occurrence_id=occ, reviewer_id=B_REVIEWER, decision=dec,
            reason="Wrong population" if dec == "exclude" else None,
        )
    votes_file = tmp_path / "votes.json"
    vexp = packets.export_votes(b_conn, votes_file, reviewer_id=B_REVIEWER)
    assert vexp["vote_count"] == len(occ_ids)
    b_conn.close()

    # (d) Owner merges unblinded.
    assert not roles.is_blind(host), "host must be unblinded for merge"
    merged = packets.merge_votes(host, votes_file, actor="owner")
    assert merged["merged_count"] == len(occ_ids)
    assert merged["quarantined_count"] == 0

    expected_conflicts = {
        occ for occ, a, b in zip(occ_ids, HOST_DECISIONS, B_DECISIONS) if a != b
    }
    expected_agreements = set(occ_ids) - expected_conflicts
    conflicts = set(screening.list_conflicts(host))
    assert conflicts == expected_conflicts, f"conflicts {conflicts} != disagreements {expected_conflicts}"
    for occ in expected_agreements:
        assert not screening.has_conflict(host, occ), "agreement wrongly surfaced as conflict"
    for occ in expected_conflicts:
        assert screening.has_conflict(host, occ)

    readout = screening.kappa_readout(
        host, is_blind=False, reviewer_a=HOST_REVIEWER, reviewer_b=B_REVIEWER,
    )
    assert readout is not None
    assert readout["status"] == "ok", readout
    assert readout["n"] > 0
    assert readout["n"] == len(occ_ids)
    host.close()

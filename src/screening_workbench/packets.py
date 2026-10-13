"""Directive B: two-computer blind review via reviewer packets.

Behavior studied from prior art (Evidentum, MIT) at the "blinded packet
file" level only: a host exports a record set with zero vote data, a
second reviewer screens it on a separate machine/install, exports only
their own votes, and the host merges those votes back in. This is an
independent implementation -- no incumbent code, text, or UI was read
or copied; see docs/packets.md for the attribution note (clean-room
protocol, OSS lane) and the full format documentation.

Two self-contained JSON file formats (Hermes's choice; documented in
docs/packets.md, not established by any external standard):

- **Reviewer packet** (`cull-reviewer-packet` v1; existing versioned wire-format identifier, retained for compatibility): project name/
  review-type, the exclusion-reason taxonomy, and every active
  occurrence's bibliographic fields and import provenance. Contains
  ZERO vote/decision/reason/decision-timestamp data -- this is the
  hard blind guardrail the module exists to prove (see the leakage
  scan in tests/test_packets.py), not an incidental property.
- **Votes export** (`cull-votes-export` v1; existing versioned wire-format identifier, retained for compatibility): one reviewer's current
  votes only -- occurrence_id, decision, reason, and the ORIGINAL vote
  timestamp (never the export time, so a host merge can apply
  newest-wins correctly). Nothing else: no record content, no
  criteria, no other reviewer's data.

Merge rule (Directive B §4, Nate's accepted default): newest-wins per
(occurrence, reviewer) by vote timestamp -- a stale votes file can
never roll back fresher data already in the host database for that
reviewer/record pair, however that fresher data got there (a direct
vote or an earlier merge). Votes referencing an occurrence_id unknown
to the host database, or otherwise malformed, are quarantined into
``quarantined_votes`` -- never silently dropped and never raising the
whole merge -- per Directive B §7's "Hermes's choice, document it"
instruction.
"""
from __future__ import annotations

import hashlib
import json
import datetime as dt
from pathlib import Path

from screening_workbench import db, roles, screening
from screening_workbench.ids import new_id, now_rfc3339
from screening_workbench.importers.limits import (
    ImportLimitError, MAX_IMPORT_RECORDS, read_limited_bytes, validate_json_value,
)

SCREENING_WORKBENCH_PACKET_FORMAT = "cull-reviewer-packet"
SCREENING_WORKBENCH_VOTES_FORMAT = "cull-votes-export"

PACKET_FORMAT = SCREENING_WORKBENCH_PACKET_FORMAT
PACKET_FORMAT_VERSION = 1
VOTES_FORMAT = SCREENING_WORKBENCH_VOTES_FORMAT
VOTES_FORMAT_VERSION = 1
DEFAULT_STAGE = "title_abstract"


def _sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_import_json(path) -> tuple[str, dict]:
    raw_bytes = read_limited_bytes(path)
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    try:
        raw = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"invalid or excessively nested JSON import: {exc}") from exc
    validate_json_value(raw)
    if not isinstance(raw, dict):
        raise ValueError("JSON import root must be an object")
    return sha256, raw


def assert_reviewer_identity(conn, reviewer_id: str) -> None:
    """Raise if this database is packet-locked to a different reviewer
    (Directive B §2). A no-op on an un-locked database (normal host
    usage, or a fresh database that has not imported a packet)."""
    row = conn.execute(
        "SELECT locked_reviewer_id FROM project_settings WHERE id='project'"
    ).fetchone()
    locked = row["locked_reviewer_id"] if row else None
    if locked and reviewer_id != locked:
        raise PermissionError(
            f"this database is locked to reviewer {locked!r} by its imported"
            f" packet; cannot act as {reviewer_id!r}"
        )


def export_packet(conn, path, *, actor: str) -> dict:
    """Host side: "Export reviewer packet..." (Directive B §1). Writes
    one portable file with the full active record set and project
    criteria/config. ALL vote data is stripped by construction -- this
    query never touches ``screen_votes``."""
    name_info = roles.get_project_name(conn)
    rows = conn.execute(
        "SELECT o.occurrence_id, o.batch_id, o.source_id, o.branch_id, o.locator,"
        " of.fields_json, s.name AS source_name, s.class AS source_class,"
        " b.name AS branch_name"
        " FROM occurrences o"
        " JOIN occurrence_fields of ON of.occurrence_id = o.occurrence_id"
        " JOIN sources s ON s.source_id = o.source_id"
        " JOIN branches b ON b.branch_id = o.branch_id"
        " WHERE o.is_active = 1"
        " ORDER BY o.created_at ASC"
    ).fetchall()

    records = [
        {
            "occurrence_id": r["occurrence_id"],
            "batch_id": r["batch_id"],
            "source_id": r["source_id"],
            "source_name": r["source_name"],
            "source_class": r["source_class"],
            "branch_id": r["branch_id"],
            "branch_name": r["branch_name"],
            "locator": r["locator"],
            "fields": json.loads(r["fields_json"]),
        }
        for r in rows
    ]

    packet_id = new_id("packet")
    packet = {
        "format": PACKET_FORMAT,
        "format_version": PACKET_FORMAT_VERSION,
        "packet_id": packet_id,
        "exported_at": now_rfc3339(),
        "exported_by": actor,
        "project": name_info,
        "criteria": {"exclusion_reasons": list(screening.EXCLUSION_REASONS)},
        "records": records,
    }
    Path(path).write_text(json.dumps(packet, indent=2, sort_keys=True), encoding="utf-8")
    sha256 = _sha256_file(path)

    def apply_fn(c, event):
        pass  # host-side projections are unaffected by exporting a packet

    db.append_event(
        conn, "packet.exported", actor,
        {"packet_id": packet_id, "file_sha256": sha256, "record_count": len(records)},
        apply_fn=apply_fn,
    )
    return {"packet_id": packet_id, "file_sha256": sha256, "record_count": len(records)}


def import_packet(conn, path, *, reviewer_id: str, actor: str | None = None) -> dict:
    """Reviewer-B side: project-level "Import reviewer packet..." on a
    separate machine/install (Directive B §2). Binds this database to
    ``reviewer_id`` permanently -- a second import on this database is
    refused regardless of reviewer_id. The UI afterward is identical to
    a normal project; there is simply no host vote data present to leak."""
    actor = actor or reviewer_id
    existing = conn.execute(
        "SELECT packet_imported_id, locked_reviewer_id FROM project_settings WHERE id='project'"
    ).fetchone()
    if existing and existing["packet_imported_id"]:
        raise ValueError(
            f"this database already imported packet {existing['packet_imported_id']!r}"
            f" bound to reviewer {existing['locked_reviewer_id']!r}; a database imports"
            " one packet only"
        )

    sha256, raw = _read_import_json(path)
    if raw.get("format") != PACKET_FORMAT:
        raise ValueError(f"not a {PACKET_FORMAT!r} file")
    if raw.get("format_version") != PACKET_FORMAT_VERSION:
        raise ValueError(f"unsupported packet format version: {raw.get('format_version')!r}")
    if not isinstance(raw.get("records"), list):
        raise ValueError("packet records must be a list")
    if len(raw["records"]) > MAX_IMPORT_RECORDS:
        raise ImportLimitError(f"packet exceeds the {MAX_IMPORT_RECORDS}-record import limit")
    if not isinstance(raw.get("packet_id"), str) or not raw["packet_id"]:
        raise ValueError("packet_id must be a non-empty string")
    if not isinstance(raw.get("project", {}), dict):
        raise ValueError("packet project must be an object")
    required_record_fields = {
        "branch_id", "branch_name", "source_id", "source_name", "source_class",
        "batch_id", "occurrence_id", "locator", "fields",
    }
    for index, record in enumerate(raw["records"]):
        if not isinstance(record, dict) or not required_record_fields.issubset(record):
            raise ValueError(f"packet record {index + 1} is malformed")
        if not isinstance(record["fields"], dict):
            raise ValueError(f"packet record {index + 1} fields must be an object")
        if any(not isinstance(record[key], str) for key in required_record_fields - {"fields"}):
            raise ValueError(f"packet record {index + 1} contains a non-text field")

    payload = {
        "packet_id": raw["packet_id"],
        "file_sha256": sha256,
        "reviewer_id": reviewer_id,
        "project": raw.get("project") or {},
        "records": raw["records"],
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute("INSERT OR IGNORE INTO project_settings (id) VALUES ('project')")
        c.execute(
            "UPDATE project_settings SET name=?, review_type=?, locked_reviewer_id=?,"
            " packet_imported_id=? WHERE id='project'",
            (
                p["project"].get("name"), p["project"].get("review_type"),
                p["reviewer_id"], p["packet_id"],
            ),
        )
        seen_branches: set[str] = set()
        seen_sources: set[str] = set()
        seen_batches: set[str] = set()
        for rec in p["records"]:
            if rec["branch_id"] not in seen_branches:
                c.execute(
                    "INSERT OR IGNORE INTO branches (branch_id, name, created_at) VALUES (?,?,?)",
                    (rec["branch_id"], rec["branch_name"], event["occurred_at"]),
                )
                seen_branches.add(rec["branch_id"])
            if rec["source_id"] not in seen_sources:
                c.execute(
                    "INSERT OR IGNORE INTO sources (source_id, name, class, branch_id, created_at)"
                    " VALUES (?,?,?,?,?)",
                    (
                        rec["source_id"], rec["source_name"], rec["source_class"],
                        rec["branch_id"], event["occurred_at"],
                    ),
                )
                seen_sources.add(rec["source_id"])
            if rec["batch_id"] not in seen_batches:
                c.execute(
                    "INSERT OR IGNORE INTO import_batches (batch_id, operation_id, source_id,"
                    " branch_id, source_format, source_name, mapping_json, mapping_version,"
                    " imported_at, records_read, records_skipped) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        rec["batch_id"], f"packet-import-{p['packet_id']}", rec["source_id"],
                        rec["branch_id"], "packet", rec["source_name"], "{}", 1,
                        event["occurred_at"], 0, 0,
                    ),
                )
                seen_batches.add(rec["batch_id"])
            c.execute(
                "INSERT OR IGNORE INTO occurrences (occurrence_id, batch_id, source_id,"
                " branch_id, locator, raw_source_text, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    rec["occurrence_id"], rec["batch_id"], rec["source_id"], rec["branch_id"],
                    rec["locator"], "", event["occurred_at"],
                ),
            )
            c.execute(
                "INSERT OR IGNORE INTO occurrence_fields (occurrence_id, fields_json,"
                " normalized_json) VALUES (?,?,?)",
                (rec["occurrence_id"], json.dumps(rec["fields"]), "{}"),
            )

    db.append_event(conn, "packet.imported", actor, payload, apply_fn=apply_fn)
    return {
        "packet_id": raw["packet_id"], "file_sha256": sha256,
        "record_count": len(raw["records"]), "reviewer_id": reviewer_id,
    }


def export_votes(
    conn, path, *, reviewer_id: str, actor: str | None = None, stage: str = DEFAULT_STAGE,
) -> dict:
    """Reviewer-B side: project-level "Export votes file..." (Directive
    B §3). Exports ONLY this reviewer's current votes -- occurrence_id,
    decision, reason, and the original vote timestamp. Nothing else."""
    actor = actor or reviewer_id
    assert_reviewer_identity(conn, reviewer_id)

    rows = conn.execute(
        "SELECT occurrence_id, decision, reason, created_at FROM screen_votes"
        " WHERE reviewer_id=? AND stage=? AND superseded_at IS NULL"
        " ORDER BY created_at ASC",
        (reviewer_id, stage),
    ).fetchall()
    votes = [
        {
            "occurrence_id": r["occurrence_id"], "decision": r["decision"],
            "reason": r["reason"], "created_at": r["created_at"],
        }
        for r in rows
    ]

    export_id = new_id("votesexp")
    doc = {
        "format": VOTES_FORMAT,
        "format_version": VOTES_FORMAT_VERSION,
        "export_id": export_id,
        "reviewer_id": reviewer_id,
        "stage": stage,
        "exported_at": now_rfc3339(),
        "votes": votes,
    }
    Path(path).write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    sha256 = _sha256_file(path)

    def apply_fn(c, event):
        pass  # this reviewer's own projections are unaffected by exporting

    db.append_event(
        conn, "votes.exported", actor,
        {"export_id": export_id, "file_sha256": sha256, "reviewer_id": reviewer_id, "vote_count": len(votes)},
        apply_fn=apply_fn,
    )
    return {"export_id": export_id, "file_sha256": sha256, "vote_count": len(votes)}


def merge_votes(conn, path, *, actor: str) -> dict:
    """Host side: Conflicts tab's "Merge votes file..." (Directive B
    §4), unblinded owner view only. Newest-wins per (occurrence,
    reviewer) by vote timestamp; unknown occurrence_ids and malformed
    votes are quarantined, never silently dropped, and never abort the
    rest of the merge."""
    if not roles.is_owner(conn, actor):
        raise PermissionError("only the project owner may merge a votes file")
    if roles.is_blind(conn):
        raise PermissionError("merging votes requires blind mode to be off (unblinded owner view only)")

    sha256, raw = _read_import_json(path)
    if raw.get("format") != VOTES_FORMAT:
        raise ValueError(f"not a {VOTES_FORMAT!r} file")
    if raw.get("format_version") != VOTES_FORMAT_VERSION:
        raise ValueError(f"unsupported votes format version: {raw.get('format_version')!r}")
    if not isinstance(raw.get("votes", []), list):
        raise ValueError("votes must be a list")
    if len(raw.get("votes", [])) > MAX_IMPORT_RECORDS:
        raise ImportLimitError(f"votes file exceeds the {MAX_IMPORT_RECORDS}-record import limit")

    reviewer_id = raw["reviewer_id"]
    stage = raw.get("stage", DEFAULT_STAGE)
    if not isinstance(reviewer_id, str) or not reviewer_id.strip():
        raise ValueError("reviewer_id must be a non-empty string")
    if not isinstance(stage, str) or not stage:
        raise ValueError("stage must be a non-empty string")
    known_ids = {r["occurrence_id"] for r in conn.execute("SELECT occurrence_id FROM occurrences").fetchall()}

    merged: list[dict] = []
    skipped_stale: list[dict] = []
    quarantined: list[dict] = []  # each gets a "quarantine_reason" key

    def quarantine_vote(vote: dict, reason_code: str) -> None:
        occurrence_id = vote.get("occurrence_id")
        decision = vote.get("decision")
        reason = vote.get("reason")
        created_at = vote.get("created_at")
        quarantined.append({
            "occurrence_id": occurrence_id if isinstance(occurrence_id, str) and occurrence_id else "<malformed-vote-row>",
            "decision": decision if isinstance(decision, str) else None,
            "reason": reason if isinstance(reason, str) else None,
            "created_at": created_at if isinstance(created_at, str) else None,
            "quarantine_reason": reason_code,
            "raw_vote": vote,
        })

    for v in raw.get("votes", []):
        if not isinstance(v, dict):
            quarantine_vote({"raw_vote": v}, "malformed_vote_row")
            continue
        occ_id = v.get("occurrence_id")
        decision = v.get("decision")
        reason = v.get("reason")
        created_at = v.get("created_at")

        if not isinstance(occ_id, str) or not occ_id:
            quarantine_vote(v, "invalid_occurrence_id")
            continue
        if occ_id not in known_ids:
            quarantine_vote(v, "unknown_occurrence_id")
            continue
        if not isinstance(decision, str) or decision not in screening.VALID_DECISIONS:
            quarantine_vote(v, "invalid_decision")
            continue
        if reason is not None and not isinstance(reason, str):
            quarantine_vote(v, "invalid_reason")
            continue
        if decision == "exclude" and not reason:
            quarantine_vote(v, "exclude_missing_reason")
            continue
        if not isinstance(created_at, str) or not created_at:
            quarantine_vote(v, "missing_or_invalid_timestamp")
            continue
        try:
            parsed_created_at = dt.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            if parsed_created_at.tzinfo is None:
                raise ValueError("timestamp requires an explicit timezone")
        except ValueError:
            quarantine_vote(v, "invalid_timestamp")
            continue
        if parsed_created_at > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
            quarantine_vote(v, "future_timestamp")
            continue

        existing = conn.execute(
            "SELECT created_at FROM screen_votes WHERE occurrence_id=? AND reviewer_id=?"
            " AND stage=? AND superseded_at IS NULL",
            (occ_id, reviewer_id, stage),
        ).fetchone()
        if existing is not None and existing["created_at"] >= created_at:
            # Newest-wins: a stale votes file can never roll back
            # fresher host-side data for this (occurrence, reviewer).
            skipped_stale.append(v)
            continue
        merged.append(v)

    payload = {
        "export_id": raw.get("export_id"), "file_sha256": sha256,
        "reviewer_id": reviewer_id, "stage": stage,
        "merged": merged, "skipped_stale": skipped_stale, "quarantined": quarantined,
    }

    def apply_fn(c, event):
        p = event["payload"]
        for v in p["merged"]:
            c.execute(
                "UPDATE screen_votes SET superseded_at=? WHERE occurrence_id=? AND reviewer_id=?"
                " AND stage=? AND superseded_at IS NULL",
                (event["occurred_at"], v["occurrence_id"], p["reviewer_id"], p["stage"]),
            )
            c.execute(
                "INSERT INTO screen_votes (vote_id, occurrence_id, stage, reviewer_id, decision,"
                " reason, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    new_id("vote"), v["occurrence_id"], p["stage"], p["reviewer_id"],
                    v["decision"], v.get("reason"), v["created_at"],
                ),
            )
        for v in p["quarantined"]:
            c.execute(
                "INSERT INTO quarantined_votes (quarantine_id, occurrence_id, reviewer_id, stage,"
                " decision, reason, vote_created_at, quarantine_reason, merge_event_id,"
                " quarantined_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    new_id("quar"), v.get("occurrence_id"), p["reviewer_id"], p["stage"],
                    v.get("decision"), v.get("reason"), v.get("created_at"),
                    v["quarantine_reason"], event["event_id"], event["occurred_at"],
                ),
            )

    db.append_event(conn, "votes.merged", actor, payload, apply_fn=apply_fn)
    return {
        "merged_count": len(merged), "skipped_stale_count": len(skipped_stale),
        "quarantined_count": len(quarantined), "file_sha256": sha256, "reviewer_id": reviewer_id,
    }


def list_quarantined_votes(conn) -> list[dict]:
    """Owner-visible list of every quarantined row (Directive B §7:
    quarantine must be visible, not a silent drop)."""
    rows = conn.execute(
        "SELECT * FROM quarantined_votes ORDER BY quarantined_at ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def quarantine_report(conn) -> list[dict]:
    """Display-ready view of quarantined votes for the owner: one dict per
    quarantined row with occurrence_id, reviewer_id, stage, reason,
    received_at, sorted oldest first by received_at.

    `reason` is the stored quarantine_reason, never re-derived from the
    vote. `received_at` is the stored quarantined_at (when the host
    received the row in a merge), not the vote's own created_at."""
    rows = conn.execute(
        "SELECT occurrence_id, reviewer_id, stage, quarantine_reason AS reason,"
        " quarantined_at AS received_at FROM quarantined_votes"
        " ORDER BY quarantined_at ASC, rowid ASC"
    ).fetchall()
    return [dict(r) for r in rows]

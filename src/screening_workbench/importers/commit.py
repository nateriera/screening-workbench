"""Shared, format-agnostic commit path for all v1 importers.

Every importer (CSV/RIS/PubMed XML) parses+maps its own format, then hands
a plain list of staged occurrences to :func:`commit_occurrences`, which is
the single place that creates the ``ImportBatch``/``occurrences`` rows,
computes normalized comparison keys (dedup spec §3.1), and enforces
import-operation idempotency (PRISMA spec §2.1.1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from screening_workbench import db
from screening_workbench.ids import new_id
from screening_workbench import dedup
from screening_workbench.normalize import compute_normalized


@dataclass
class CommitResult:
    batch_id: str
    records_read: int
    records_skipped: int
    skipped_reasons: list[dict] = field(default_factory=list)
    idempotent_replay: bool = False


def commit_occurrences(
    conn,
    *,
    occurrences: list[dict],   # [{"occurrence_id","locator","raw_source_text","fields"}]
    skipped: list[dict],       # [{"locator","reason"}]
    source_format: str,
    source_id: str,
    branch_id: str,
    mapping: dict,
    mapping_version: int,
    operation_id: str,
    actor: str,
    source_name: str,
) -> CommitResult:
    prior = db.begin_or_get_operation(conn, operation_id, f"import_{source_format}")
    if prior is not None:
        return CommitResult(**prior, idempotent_replay=True)
    dedup.ensure_pair_comparison_budget(conn, len(occurrences))

    batch_id = new_id("batch")
    for occ in occurrences:
        occ["normalized"] = compute_normalized(occ["fields"])

    payload = {
        "batch_id": batch_id,
        "source_id": source_id,
        "branch_id": branch_id,
        "source_format": source_format,
        "source_name": source_name,
        "mapping": mapping,
        "mapping_version": mapping_version,
        "occurrences": occurrences,
        "skipped": skipped,
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO import_batches (batch_id, operation_id, source_id, branch_id,"
            " source_format, source_name, mapping_json, mapping_version, imported_at,"
            " records_read, records_skipped) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                p["batch_id"], operation_id, p["source_id"], p["branch_id"],
                p["source_format"], p["source_name"], json.dumps(p["mapping"]),
                p["mapping_version"], event["occurred_at"],
                len(p["occurrences"]), len(p["skipped"]),
            ),
        )
        for occ in p["occurrences"]:
            c.execute(
                "INSERT INTO occurrences (occurrence_id, batch_id, source_id, branch_id,"
                " locator, raw_source_text, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    occ["occurrence_id"], p["batch_id"], p["source_id"], p["branch_id"],
                    occ["locator"], occ["raw_source_text"], event["occurred_at"],
                ),
            )
            c.execute(
                "INSERT INTO occurrence_fields (occurrence_id, fields_json, normalized_json)"
                " VALUES (?, ?, ?)",
                (occ["occurrence_id"], json.dumps(occ["fields"]), json.dumps(occ["normalized"])),
            )
        for sk in p["skipped"]:
            c.execute(
                "INSERT INTO import_skips (skip_id, batch_id, locator, reason) VALUES (?,?,?,?)",
                (new_id("skip"), p["batch_id"], sk["locator"], sk["reason"]),
            )

    db.append_event(conn, f"import.{source_format}.committed", actor, payload, apply_fn=apply_fn)

    result = CommitResult(
        batch_id=batch_id,
        records_read=len(occurrences),
        records_skipped=len(skipped),
        skipped_reasons=skipped,
    )
    db.commit_operation(
        conn, operation_id, f"import_{source_format}",
        {
            "batch_id": result.batch_id,
            "records_read": result.records_read,
            "records_skipped": result.records_skipped,
            "skipped_reasons": result.skipped_reasons,
        },
    )
    return result

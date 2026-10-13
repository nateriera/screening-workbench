"""PDF attachments for full-text report records (Directive D, migration 009).

Implements the only open v1 gap in the Full-text reference package
(item 3, "PDF attachment has an icon and a text label"): a data model
for attaching a PDF to a ``report_retrievals`` report.

Metadata (filename, hash, size, uploader, timestamp) lives in the
``report_attachments`` SQLite table. The file bytes themselves never do
-- they live outside the database, content-addressed by SHA-256, at
``<attachments_dir>/<sha256>.pdf``. This keeps SQLite lean, makes the
export manifest hash-verifiable, and dedupes identical files for free
(the same bytes attached to two different reports is one on-disk file
and two metadata rows).

No GC pass is implemented: ``detach_pdf`` removes the metadata row but
never the on-disk file, since another report's row may reference the
same content hash. Documented as future work, not a bug.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from screening_workbench import db
from screening_workbench.ids import new_id
from screening_workbench.importers.limits import ImportLimitError, read_limited_bytes

MAX_ATTACHMENT_BYTES = 100 * 1024 * 1024  # 100 MB; adjust with justification if ever needed.
PDF_MAGIC = b"%PDF-"


def resolve_attachments_dir(conn, attachments_dir: str | Path | None = None) -> Path:
    """Where attachment bytes live for this project database.

    Defaults to an ``attachments`` sibling folder of the DB file itself
    (via ``PRAGMA database_list``, not a path the caller has to track
    separately), with an explicit override for tests/alternate layouts.
    """
    if attachments_dir is not None:
        return Path(attachments_dir)
    row = conn.execute("PRAGMA database_list").fetchone()
    db_file = Path(row["file"]) if row and row["file"] else Path(".")
    base = db_file.parent if str(db_file.parent) else Path(".")
    return base / "attachments"


def attach_pdf(
    conn,
    actor: str,
    report_id: str,
    source_path: str | Path,
    attachments_dir: str | Path | None = None,
) -> str:
    """Attach a PDF file to ``report_id``. Returns the new/existing
    ``attachment_id``.

    ``report_id`` must already have a ``report_retrievals`` row -- i.e.
    the report has reached the retrieval/full-text stage (created
    automatically by ``reports.assign_progression`` /
    ``reports.promote_occurrence_to_report``). This matches the Full-text
    tab's own scope: a bare freshly-created ``reports`` row with no
    retrieval progression yet cannot take an attachment.

    Validates by magic bytes (``%PDF-`` at offset 0), not by file
    extension, and rejects anything over ``MAX_ATTACHMENT_BYTES``. The
    same bytes attached twice to the same report returns the existing
    row's ``attachment_id`` rather than creating a duplicate (the
    ``UNIQUE(report_id, content_sha256)`` constraint backs this, but the
    check here avoids relying on catching the resulting IntegrityError).
    """
    report_row = conn.execute(
        "SELECT report_id FROM report_retrievals WHERE report_id = ?", (report_id,)
    ).fetchone()
    if report_row is None:
        raise ValueError(
            f"report {report_id!r} has no report_retrievals row yet (a report must have"
            " reached the retrieval/full-text stage -- e.g. via reports.assign_progression"
            " or reports.promote_occurrence_to_report -- before a PDF can be attached)"
        )

    source_path = Path(source_path)
    try:
        data = read_limited_bytes(source_path, MAX_ATTACHMENT_BYTES)
    except ImportLimitError as exc:
        raise ValueError(
            f"rejected: attachment exceeds the {MAX_ATTACHMENT_BYTES}-byte limit"
        ) from exc
    if not data.startswith(PDF_MAGIC):
        raise ValueError("rejected: not a PDF (missing '%PDF-' magic bytes at offset 0)")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValueError(
            f"rejected: {len(data)} bytes exceeds the {MAX_ATTACHMENT_BYTES}-byte attachment cap"
        )

    sha = hashlib.sha256(data).hexdigest()

    existing = conn.execute(
        "SELECT attachment_id FROM report_attachments WHERE report_id = ? AND content_sha256 = ?",
        (report_id, sha),
    ).fetchone()
    if existing is not None:
        return existing["attachment_id"]

    attach_dir = resolve_attachments_dir(conn, attachments_dir)
    attach_dir.mkdir(parents=True, exist_ok=True)
    dest = attach_dir / f"{sha}.pdf"
    if not dest.exists():  # dedup: identical bytes already on disk from any report
        with open(dest, "wb") as fh:
            fh.write(data)

    attachment_id = new_id("att")
    payload = {
        "attachment_id": attachment_id,
        "report_id": report_id,
        "filename": source_path.name,
        "content_sha256": sha,
        "byte_size": len(data),
        "mime_type": "application/pdf",
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO report_attachments"
            " (attachment_id, report_id, filename, content_sha256, byte_size, mime_type,"
            "  uploaded_by, uploaded_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                p["attachment_id"], p["report_id"], p["filename"], p["content_sha256"],
                p["byte_size"], p["mime_type"], event["actor"], event["occurred_at"],
            ),
        )

    db.append_event(conn, "report.attachment_added", actor, payload, apply_fn=apply_fn)
    return attachment_id


def list_attachments(conn, report_id: str) -> list[dict]:
    """Metadata only, never bytes."""
    rows = conn.execute(
        "SELECT attachment_id, report_id, filename, content_sha256, byte_size, mime_type,"
        " uploaded_by, uploaded_at FROM report_attachments"
        " WHERE report_id = ? ORDER BY uploaded_at ASC",
        (report_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_all_attachments(conn) -> list[dict]:
    """Every attachment across every report (metadata only); used by the
    export package to build its manifest and bundle, not by per-report UI."""
    rows = conn.execute(
        "SELECT attachment_id, report_id, filename, content_sha256, byte_size, mime_type,"
        " uploaded_by, uploaded_at FROM report_attachments ORDER BY uploaded_at ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def attachment_bytes(conn, attachment_id: str, attachments_dir: str | Path | None = None) -> bytes:
    """Read an attachment's bytes back, verifying SHA-256 on every read.

    Raises on a missing file (``FileNotFoundError``, from the OS) or a
    hash mismatch (``ValueError``) -- an integrity failure never returns
    a silent wrong file.
    """
    row = conn.execute(
        "SELECT content_sha256 FROM report_attachments WHERE attachment_id = ?",
        (attachment_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"attachment {attachment_id!r} does not exist")

    sha = row["content_sha256"]
    attach_dir = resolve_attachments_dir(conn, attachments_dir)
    path = attach_dir / f"{sha}.pdf"
    data = read_limited_bytes(path, MAX_ATTACHMENT_BYTES)
    actual_sha = hashlib.sha256(data).hexdigest()
    if actual_sha != sha:
        raise ValueError(
            f"attachment {attachment_id!r} integrity failure: on-disk file hash {actual_sha}"
            f" does not match recorded content_sha256 {sha}"
        )
    return data


def detach_pdf(conn, actor: str, attachment_id: str) -> None:
    """Remove the attachment's metadata row and audit the removal. The
    content-addressed file stays on disk -- other reports' rows may
    still reference the same hash, and v1 has no GC pass (future work)."""
    row = conn.execute(
        "SELECT report_id, content_sha256 FROM report_attachments WHERE attachment_id = ?",
        (attachment_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"attachment {attachment_id!r} does not exist")

    payload = {
        "attachment_id": attachment_id,
        "report_id": row["report_id"],
        "content_sha256": row["content_sha256"],
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute("DELETE FROM report_attachments WHERE attachment_id = ?", (p["attachment_id"],))

    db.append_event(conn, "report.attachment_removed", actor, payload, apply_fn=apply_fn)

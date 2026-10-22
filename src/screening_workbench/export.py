"""Local export package: PRISMA SVG, decisions/link CSVs, audit log,
and manifest -- all from one immutable snapshot/watermark.

Implements docs/specs/behavioral-spec-prisma-counts-export.md §2.6 and §5.
"""
from __future__ import annotations

import csv
import io
import json
import os

from screening_workbench import attachments, db, prisma, roles
from screening_workbench.ids import new_id, now_rfc3339


def _watermark(conn) -> int:
    row = conn.execute("SELECT MAX(sequence) AS n FROM events").fetchone()
    return row["n"] or 0


def watermark_sequence(conn) -> int:
    """Public accessor for the current watermark (max event sequence) --
    the same value the export package's SVG/audit-log/manifest are all
    bound to (PRISMA & audit reference item 2/8: diagram and watermark
    come from one named immutable snapshot, not independent
    recalculation). UI callers should use this, not the private
    ``_watermark``."""
    return _watermark(conn)


def list_audit_events(conn, *, through_sequence: int | None = None) -> list[dict]:
    """Append-only audit log rows (sequence, event_id, event_type,
    occurred_at, actor), for the PRISMA & audit tab's read-only log
    view (reference item 6). Mirrors ``export_audit_log_jsonl``'s
    query but returns dicts, not JSONL text, for UI rendering. Has no
    notion of blind state or audit-read scope -- same pattern as
    ``export_audit_log_jsonl`` and ``export_decisions_csv``'s
    ``can_see_all`` parameter: the caller (UI layer, mirroring every
    other blind-lock in this app) decides whether to call this at
    all, not this function."""
    if through_sequence is None:
        through_sequence = _watermark(conn)
    rows = conn.execute(
        "SELECT sequence, event_id, event_type, occurred_at, actor FROM events"
        " WHERE sequence <= ? ORDER BY sequence ASC",
        (through_sequence,),
    ).fetchall()
    return [dict(r) for r in rows]


def write_package_to_folder(package: dict[str, "str | bytes"], folder: str) -> None:
    """Write an export package's files into ``folder``, preserving any
    prior artifacts there if a local-write failure happens partway
    through (acceptance fixture 9: "local-write failure ... preserves
    prior artifacts").

    Writing each file directly to its final name, one at a time, is NOT
    safe: if write N of M fails (disk full, permission error, a path
    that's actually a directory, ...), files 1..N-1 of the NEW export
    have already silently overwritten the prior export's files, while
    N..M were never written -- the folder now holds an inconsistent mix
    of old and new, which is worse than failing cleanly.

    Instead: write every file to a ``.screening-workbench-export-tmp`` sibling of its
    final name, in the SAME folder (so the final rename is atomic on
    the same filesystem/volume, both on POSIX and Windows NTFS -- unlike
    a separate staging directory, which would need a cross-volume copy
    that is not atomic). Only after every file has staged successfully
    are the temp files renamed into place. If any staging write fails,
    every temp file created so far in this attempt is removed and the
    original error re-raised; no final filename is ever touched.

    A final target that is already a directory (not a file) is checked
    for up front, before any writes happen -- `os.replace` cannot
    overwrite a directory with a file, so discovering this only at
    rename time, after every other file in the package has already been
    renamed into place, would leave exactly the inconsistent mix this
    function exists to prevent.

    Values may be ``str`` (written as UTF-8 text, e.g. the manifest and
    CSVs) or ``bytes`` (written as-is, e.g. bundled ``attachments/*.pdf``
    files -- Directive D). A filename containing a subdirectory
    separator (``attachments/<sha>.pdf``) has that subdirectory created
    first.
    """
    for filename in package:
        final_path = os.path.join(folder, filename)
        if os.path.isdir(final_path):
            raise IsADirectoryError(f"export target is a directory, not a file: {final_path}")

    staged: list[tuple[str, str]] = []
    try:
        for filename, content in package.items():
            final_path = os.path.join(folder, filename)
            parent_dir = os.path.dirname(final_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            tmp_path = final_path + ".screening-workbench-export-tmp"
            if isinstance(content, bytes):
                with open(tmp_path, "wb") as fh:
                    fh.write(content)
            else:
                with open(tmp_path, "w", encoding="utf-8") as fh:
                    fh.write(content)
            staged.append((tmp_path, final_path))
    except OSError:
        for tmp_path, _final_path in staged:
            try:
                os.remove(tmp_path)
            except OSError:
                pass  # best-effort cleanup; the original error is what matters
        raise

    for tmp_path, final_path in staged:
        os.replace(tmp_path, final_path)


def compute_completeness(conn) -> tuple[bool, list[str]]:
    """A complete export requires no pending/unresolved/conflicting items
    (spec §2.4.3, §2.5, §2.6.2)."""
    issues: list[str] = []

    invariant_violations = prisma.verify_invariants(conn)
    issues.extend(invariant_violations)

    pending_reports = conn.execute(
        "SELECT COUNT(*) AS n FROM report_retrievals"
        " WHERE retrieval_status = 'pending' OR full_text_outcome = 'maybe'"
    ).fetchone()["n"]
    if pending_reports:
        issues.append(f"{pending_reports} report(s) pending retrieval/assessment")

    open_fuzzy = conn.execute(
        "SELECT COUNT(*) AS n FROM dedup_candidates WHERE kind='fuzzy' AND state='open'"
    ).fetchone()["n"]
    if open_fuzzy:
        issues.append(f"{open_fuzzy} open fuzzy duplicate candidate(s) unresolved")

    # Title/abstract screening conflicts (reviewers' current votes
    # disagree) are distinct from study-level inclusion conflicts below
    # and were not previously checked here -- found while working
    # acceptance fixture 9 ("unresolved conflicts ... prevents complete
    # package"): a record with two reviewers' votes still disagreeing
    # was silently exportable as complete.
    from screening_workbench import screening as screening_mod
    unresolved_screening_conflicts = screening_mod.list_conflicts(conn)
    if unresolved_screening_conflicts:
        issues.append(
            f"{len(unresolved_screening_conflicts)} title/abstract screening conflict(s) unresolved"
        )

    # Maybe decisions and not-yet-voted records remain in the PRISMA
    # screening-pending bucket; they are not terminal screened records.
    ident_counts = prisma.identification_and_screening_counts(conn)
    pending_screening = sum(
        branch["screening_pending"] + branch["prescreen_pending"]
        for branch in ident_counts["branches"].values()
    )
    if pending_screening:
        issues.append(f"{pending_screening} record(s) pending title/abstract screening")

    unresolved_studies = conn.execute(
        "SELECT study_id FROM study_decisions WHERE decision = 'unresolved'"
    ).fetchall()
    if unresolved_studies:
        issues.append(f"{len(unresolved_studies)} study decision(s) unresolved")

    for row in conn.execute("SELECT study_id FROM studies").fetchall():
        from screening_workbench import studies as studies_mod
        if studies_mod.detect_conflict(conn, row["study_id"]):
            issues.append(f"study {row['study_id']} has an unresolved inclusion conflict")

    # An occurrence with a current title/abstract 'include' vote that has
    # not yet been promoted to a report is unfinished review work -- the
    # export cannot be called complete while screening decisions haven't
    # progressed to a report/study outcome (dogfood-milestone.md: "A real-
    # corpus export may only be called complete if all included reports
    # have owner-confirmed study associations and study-inclusion
    # decisions; otherwise label it incomplete and state why."). Found via
    # the 2026-10-07 dogfood run against the real dogfood corpus, where a
    # project with 98 included-but-unpromoted occurrences and zero reports
    # was incorrectly reported as complete before this check existed.
    from screening_workbench import reports as reports_mod
    unpromoted = reports_mod.unlinked_included_occurrences(conn)
    if unpromoted:
        issues.append(
            f"{len(unpromoted)} occurrence(s) included at title/abstract but not yet"
            " promoted to a full-text report"
        )

    return (len(issues) == 0, issues)


def build_manifest(conn, actor: str) -> dict:
    is_complete, issues = compute_completeness(conn)
    snapshot = prisma.full_snapshot(conn)
    attachment_rows = attachments.list_all_attachments(conn)
    return {
        "manifest_version": 1,
        "generated_by": actor,
        "as_of": now_rfc3339(),
        "watermark_sequence": _watermark(conn),
        "owner": roles.get_owner(conn),
        "completeness": {
            "is_complete": is_complete,
            "unresolved_issues": issues,
        },
        "counts": snapshot,
        # Directive D: attachments are supplementary (compute_completeness
        # never requires them -- a design decision, not an oversight), but
        # every attached PDF is still listed here so the bundle below can
        # be verified hash-by-hash against this manifest.
        "attachments": [
            {
                "report_id": r["report_id"],
                "filename": r["filename"],
                "sha256": r["content_sha256"],
                "byte_size": r["byte_size"],
            }
            for r in attachment_rows
        ],
    }


def export_decisions_csv(conn, actor: str, *, is_blind: bool) -> str:
    """Occurrence-level decisions CSV (spec §5). While blind and the
    actor is not owner/auditor-full_export, only the actor's own votes
    are included (partial export, never labeled complete)."""
    can_see_all = not is_blind or roles.is_owner_or_auditor(conn, actor, "full_export")

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow([
        "occurrence_id", "batch_id", "source_id", "branch_id", "is_active",
        "duplicate_of", "reviewer_id", "stage", "decision", "reason",
    ])
    rows = conn.execute(
        "SELECT o.occurrence_id, o.batch_id, o.source_id, o.branch_id, o.is_active, o.duplicate_of,"
        " sv.reviewer_id, sv.stage, sv.decision, sv.reason"
        " FROM occurrences o LEFT JOIN screen_votes sv ON sv.occurrence_id = o.occurrence_id"
        " AND sv.superseded_at IS NULL"
    ).fetchall()
    for r in rows:
        if not can_see_all and r["reviewer_id"] not in (None, actor):
            continue
        writer.writerow([
            *(_safe_csv_cell(value) for value in [
                r["occurrence_id"], r["batch_id"], r["source_id"], r["branch_id"], r["is_active"],
                r["duplicate_of"] or "", r["reviewer_id"] or "", r["stage"] or "",
                r["decision"] or "", r["reason"] or "",
            ]),
        ])
    return buf.getvalue()


def export_report_study_links_csv(conn) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["report_id", "study_id", "action", "actor", "occurred_at", "rationale", "event_row_id"])
    rows = conn.execute(
        "SELECT report_id, study_id, action, actor, occurred_at, rationale, event_row_id"
        " FROM report_study_link_events ORDER BY occurred_at ASC"
    ).fetchall()
    for r in rows:
        writer.writerow([
            *(_safe_csv_cell(value) for value in [
                r["report_id"], r["study_id"], r["action"], r["actor"],
                r["occurred_at"], r["rationale"] or "", r["event_row_id"],
            ]),
        ])
    return buf.getvalue()


def _safe_csv_cell(value):
    """Prefix formula-like text so spreadsheet applications keep it inert."""
    if not isinstance(value, str):
        return value
    first = next((
        char for char in value
        if not char.isspace() and ord(char) >= 32
    ), "")
    if first.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def export_audit_log_jsonl(conn, actor: str, *, is_blind: bool, through_sequence: int | None = None) -> str:
    """All events up to (and including) the given watermark sequence,
    one JSON object per line (spec §5). Mirrors
    ``export_decisions_csv``'s ``can_see_all`` logic: while blind and
    the actor is not owner/auditor-full_export, any event whose
    payload carries another reviewer's ``reviewer_id`` is dropped
    entirely (not redacted in place -- the whole event is excluded, so
    no decision/reason/vote_id tied to another reviewer ever reaches
    this file). Vote-cast and vote-undo events carry ``reviewer_id``;
    every other event type doesn't and is always safe to include."""
    can_see_all = not is_blind or roles.is_owner_or_auditor(conn, actor, "full_export")

    if through_sequence is None:
        through_sequence = _watermark(conn)
    rows = conn.execute(
        "SELECT * FROM events WHERE sequence <= ? ORDER BY sequence ASC", (through_sequence,)
    ).fetchall()
    lines = []
    for r in rows:
        payload = json.loads(r["payload_json"])
        if not can_see_all and payload.get("reviewer_id") not in (None, actor):
            continue
        lines.append(json.dumps({
            "sequence": r["sequence"],
            "event_id": r["event_id"],
            "event_type": r["event_type"],
            "occurred_at": r["occurred_at"],
            "actor": r["actor"],
            "schema_version": r["schema_version"],
            "payload": payload,
        }, sort_keys=True))
    return "\n".join(lines) + ("\n" if lines else "")


def prisma_flow_boxes(conn) -> list[dict]:
    """The PRISMA flow diagram's box geometry + labels + values, as one
    list derived from a single `prisma.full_snapshot(conn)` call --
    the shared source both `export_prisma_svg` (the export package)
    and the live PRISMA & audit tab's Canvas rendering draw from, so
    the two are never independently recalculated from different
    snapshots (reference item 2: "generated from one named immutable
    snapshot"). Geometry fields (x/y/w/h) are in the SVG's own
    520x650 coordinate space.
    """
    ident = prisma.identification_and_screening_counts(conn)
    snapshot = prisma.full_snapshot(conn)
    rep = snapshot["reports"]
    studies_counts = snapshot["studies"]

    def box(box_id, x, y, w, h, label, value):
        return {"id": box_id, "x": x, "y": y, "w": w, "h": h, "label": label, "value": value}

    return [
        box("box-identified", 20, 20, 220, 60, "Records identified", ident["identified_total"]),
        box("box-removed", 20, 110, 220, 60, "Duplicates removed (pre-screen)", ident["removed_before_screen"]),
        box("box-sought", 20, 200, 220, 60, "Reports sought", rep["reports_sought"]),
        box("box-not-retrieved", 20, 290, 220, 60, "Reports not retrieved", rep["reports_not_retrieved"]),
        box("box-assessed", 20, 380, 220, 60, "Reports assessed (full text)", rep["reports_assessed"]),
        box("box-excluded", 260, 380, 220, 60, "Reports excluded (full text)", rep["reports_excluded"]),
        box("box-included", 20, 470, 220, 60, "Reports included", rep["reports_included"]),
        box("box-studies-included", 20, 560, 220, 60, "Studies included", studies_counts["studies_included"]),
    ]


PRISMA_SVG_TITLE = "Screening Workbench PRISMA 2020 flow diagram"
PRISMA_SVG_DESC = (
    "Original Screening Workbench-generated PRISMA flow diagram showing identification,"
    " screening, retrieval, and inclusion counts for this review."
)


def export_prisma_svg(conn) -> str:
    """Minimal original PRISMA 2020 flow diagram as SVG text/numbers.

    Deliberately simple geometric boxes + text (no incumbent artwork
    copied); presents identification, screening, retrieval, and
    inclusion stage counts with accessible title/description per spec §5.
    """
    boxes = prisma_flow_boxes(conn)

    def box_svg(b):
        x, y, w, h = b["x"], b["y"], b["w"], b["h"]
        return (
            f'<g id="{b["id"]}">'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke="#1f2a25" stroke-width="2"/>'
            f'<text x="{x + w/2}" y="{y + h/2 - 6}" text-anchor="middle" font-family="sans-serif" font-size="13">{b["label"]}</text>'
            f'<text x="{x + w/2}" y="{y + h/2 + 14}" text-anchor="middle" font-family="sans-serif" font-size="16" font-weight="bold">{b["value"]}</text>'
            f'</g>'
        )

    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 520 650" '
        'role="img" aria-labelledby="screening-workbench-prisma-title screening-workbench-prisma-desc">'
        f'<title id="screening-workbench-prisma-title">{PRISMA_SVG_TITLE}</title>'
        f'<desc id="screening-workbench-prisma-desc">{PRISMA_SVG_DESC}</desc>'
        + "".join(box_svg(b) for b in boxes) +
        "</svg>"
    )
    return svg


def export_package(conn, actor: str, *, is_blind: bool) -> dict:
    """Build the full local package and record the export audit event.
    Returns {filename: content}. A blinded reviewer without full_export
    receives only their own decisions and a minimal manifest; project-wide
    counts, links, audit sequence, flow, and attachments are withheld because
    they can reveal or help infer another reviewer's decisions.
    """
    can_full_export = not is_blind or roles.is_owner_or_auditor(conn, actor, "full_export")

    if is_blind and not can_full_export:
        # Do not compute or return project-wide counts, attachments, owner
        # identity, or the global event watermark in a reviewer-only export.
        manifest = {
            "manifest_version": 1,
            "generated_by": actor,
            "as_of": now_rfc3339(),
            "export_scope": "reviewer_decisions_only",
            "completeness": {
                "is_complete": False,
                "unresolved_issues": [
                    "Blinded partial export; project-wide completeness is not disclosed."
                ],
            },
        }
        watermark_sequence = _watermark(conn)
    else:
        manifest = build_manifest(conn, actor)
        watermark_sequence = manifest["watermark_sequence"]

    package: dict[str, "str | bytes"] = {
        "manifest.json": json.dumps(manifest, indent=2, sort_keys=True),
        "decisions.csv": export_decisions_csv(conn, actor, is_blind=is_blind),
    }

    if can_full_export:
        package.update({
            "report-study-links.csv": export_report_study_links_csv(conn),
            "audit-log.jsonl": export_audit_log_jsonl(
                conn, actor, is_blind=is_blind, through_sequence=watermark_sequence
            ),
            "prisma-flow.svg": export_prisma_svg(conn),
        })

    # Directive D: bundle every attachment the manifest lists, keyed by
    # content hash (the same hash may appear once in the manifest per
    # report but only needs writing once as a file). The package fails
    # closed: a manifest entry whose on-disk bytes are missing or
    # tampered aborts the whole export rather than silently shipping a
    # manifest that references absent/wrong bytes (the dogfood
    # non-atomic-export lesson).
    if can_full_export:
        all_attachments = attachments.list_all_attachments(conn)
        bundled_sha: set[str] = set()
        for row in manifest["attachments"]:
            sha = row["sha256"]
            if sha in bundled_sha:
                continue
            matching = next(a for a in all_attachments if a["content_sha256"] == sha)
            try:
                data = attachments.attachment_bytes(conn, matching["attachment_id"])
            except (OSError, ValueError) as exc:
                raise RuntimeError(
                    f"export failed: attachment sha256={sha} ({row['filename']!r}, report"
                    f" {row['report_id']!r}) bytes missing or corrupt on disk: {exc}"
                ) from exc
            package[f"attachments/{sha}.pdf"] = data
            bundled_sha.add(sha)

    def apply_fn(c, event):
        pass  # the export event itself carries no projection state

    db.append_event(
        conn, "export.package_generated", actor,
        {
            "watermark_sequence": watermark_sequence,
            "is_complete": manifest["completeness"]["is_complete"],
            "is_blind_partial": bool(is_blind and not can_full_export),
        },
        apply_fn=apply_fn,
    )
    return package

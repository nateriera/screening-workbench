"""Report progression, retrieval, and full-text assessment.

Implements docs/specs/behavioral-spec-prisma-counts-export.md §2.3 and the
count equations in §3.2/§3.4.

Known v1 gap: ``record_full_text_assessment`` does not yet prevent a
second call from silently overwriting an already-terminal outcome with a
later-events-dependent correction event (spec §2.3.4 calls full-text
outcome "terminal"). A dedicated correction workflow with its own audit
reason -- analogous to ``studies.set_study_decision``'s rationale
requirement -- is required before release; today a caller can
re-assess a report and the prior outcome is simply replaced.
"""
from __future__ import annotations

from screening_workbench import db
from screening_workbench.ids import new_id


def create_report(conn, actor: str) -> str:
    """Create a new distinct `Report` (never inferred from occurrences)."""
    report_id = new_id("report")
    payload = {"report_id": report_id}

    def apply_fn(c, event):
        c.execute(
            "INSERT INTO reports (report_id, created_at) VALUES (?, ?)",
            (event["payload"]["report_id"], event["occurred_at"]),
        )

    db.append_event(conn, "report.created", actor, payload, apply_fn=apply_fn)
    return report_id


def link_occurrence_to_report(conn, actor: str, occurrence_id: str, report_id: str) -> None:
    """Record `RecordReport` provenance. Idempotent: linking the same pair
    twice is a no-op (not a duplicate link row)."""
    existing = conn.execute(
        "SELECT 1 FROM record_reports WHERE occurrence_id=? AND report_id=?",
        (occurrence_id, report_id),
    ).fetchone()
    if existing:
        return

    payload = {"occurrence_id": occurrence_id, "report_id": report_id}

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT OR IGNORE INTO record_reports (occurrence_id, report_id, created_at) VALUES (?,?,?)",
            (p["occurrence_id"], p["report_id"], event["occurred_at"]),
        )

    db.append_event(conn, "report.occurrence_linked", actor, payload, apply_fn=apply_fn)


def assign_progression(conn, actor: str, report_id: str, canonical_occurrence: str) -> None:
    """Select the one canonical occurrence/branch that advances this
    report (PRISMA spec §2.3.1-2). A report advances once only; calling
    this again on an already-progressed report raises, matching
    "at most one progression/branch" (spec §3.4.3) -- re-selection must go
    through an explicit correction path, not a silent overwrite.
    """
    existing = conn.execute(
        "SELECT 1 FROM report_progressions WHERE report_id = ?", (report_id,)
    ).fetchone()
    if existing:
        raise ValueError(
            f"report {report_id} already has a progression; use a correction event, not a second assignment"
        )
    link = conn.execute(
        "SELECT branch_id FROM occurrences WHERE occurrence_id = ?", (canonical_occurrence,)
    ).fetchone()
    if link is None:
        raise ValueError(f"unknown occurrence: {canonical_occurrence}")
    linked = conn.execute(
        "SELECT 1 FROM record_reports WHERE occurrence_id=? AND report_id=?",
        (canonical_occurrence, report_id),
    ).fetchone()
    if not linked:
        raise ValueError("canonical occurrence must already be linked to the report")

    payload = {
        "report_id": report_id,
        "canonical_occurrence": canonical_occurrence,
        "branch_id": link["branch_id"],
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO report_progressions (report_id, canonical_occurrence, branch_id, actor, decided_at)"
            " VALUES (?,?,?,?,?)",
            (p["report_id"], p["canonical_occurrence"], p["branch_id"], event["actor"], event["occurred_at"]),
        )
        c.execute(
            "INSERT OR IGNORE INTO report_retrievals (report_id, retrieval_status, actor, updated_at)"
            " VALUES (?, 'pending', ?, ?)",
            (p["report_id"], event["actor"], event["occurred_at"]),
        )

    db.append_event(conn, "report.progression_assigned", actor, payload, apply_fn=apply_fn)


def correct_progression(
    conn, actor: str, report_id: str, new_canonical_occurrence: str, rationale: str,
) -> None:
    """Re-select the canonical occurrence/branch that advances a report
    whose progression was already assigned (PRISMA spec §3.4.3,
    acceptance fixture 2: "replay/correction/undo restore expected
    counts" for a cross-branch duplicate-to-one-report fixture).

    `assign_progression` intentionally refuses a second call on an
    already-progressed report ("use a correction event, not a second
    assignment") -- this is that correction path. The report still
    advances exactly once at any instant (``report_progressions.report_id``
    is a single-row primary key, not an append-only history table), but
    the event log itself records both the prior and new canonical
    occurrence/branch, so a correction is auditable and distinguishable
    from the original assignment on replay -- never a silent overwrite.
    """
    if not rationale or not rationale.strip():
        raise ValueError("a rationale is required to correct a report progression")
    existing = conn.execute(
        "SELECT canonical_occurrence, branch_id FROM report_progressions WHERE report_id = ?",
        (report_id,),
    ).fetchone()
    if existing is None:
        raise ValueError(f"report {report_id} has no progression to correct; use assign_progression instead")
    link = conn.execute(
        "SELECT branch_id FROM occurrences WHERE occurrence_id = ?", (new_canonical_occurrence,)
    ).fetchone()
    if link is None:
        raise ValueError(f"unknown occurrence: {new_canonical_occurrence}")
    linked = conn.execute(
        "SELECT 1 FROM record_reports WHERE occurrence_id=? AND report_id=?",
        (new_canonical_occurrence, report_id),
    ).fetchone()
    if not linked:
        raise ValueError("canonical occurrence must already be linked to the report")

    payload = {
        "report_id": report_id,
        "prior_canonical_occurrence": existing["canonical_occurrence"],
        "prior_branch_id": existing["branch_id"],
        "canonical_occurrence": new_canonical_occurrence,
        "branch_id": link["branch_id"],
        "rationale": rationale,
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "UPDATE report_progressions SET canonical_occurrence = ?, branch_id = ?, actor = ?, decided_at = ?"
            " WHERE report_id = ?",
            (p["canonical_occurrence"], p["branch_id"], event["actor"], event["occurred_at"], p["report_id"]),
        )

    db.append_event(conn, "report.progression_corrected", actor, payload, apply_fn=apply_fn)


def mark_not_retrieved(conn, actor: str, report_id: str) -> None:
    _update_retrieval(conn, actor, report_id, retrieval_status="not_retrieved")


def record_full_text_assessment(
    conn, actor: str, report_id: str, outcome: str, exclusion_reason: str | None = None
) -> None:
    """Full-text outcome (spec §2.3.4; Directive C, reference item 5):
    'included' or 'excluded' are terminal -- excluded requires exactly
    one primary reason, included must not carry one. 'maybe' is NOT
    terminal (mirrors the screening-stage Maybe vote): the report stays
    pending, counts in neither included nor excluded, must not carry a
    reason, and may be re-assessed to included/excluded/maybe again
    through this same update path."""
    if outcome not in ("included", "excluded", "maybe"):
        raise ValueError("outcome must be 'included', 'excluded', or 'maybe'")
    if outcome == "excluded" and not exclusion_reason:
        raise ValueError("excluded outcome requires exactly one primary reason")
    if outcome == "included" and exclusion_reason:
        raise ValueError("included outcome must not carry an exclusion reason")
    if outcome == "maybe" and exclusion_reason:
        raise ValueError("maybe outcome must not carry an exclusion reason")
    _update_retrieval(
        conn, actor, report_id,
        retrieval_status="retrieved", full_text_outcome=outcome, exclusion_reason=exclusion_reason,
    )


def _update_retrieval(conn, actor: str, report_id: str, **fields) -> None:
    row = conn.execute("SELECT * FROM report_retrievals WHERE report_id = ?", (report_id,)).fetchone()
    if row is None:
        raise ValueError(f"report {report_id} has no progression/retrieval row yet")
    payload = {"report_id": report_id, **fields}

    def apply_fn(c, event):
        p = event["payload"]
        sets = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [event["actor"], event["occurred_at"], p["report_id"]]
        c.execute(
            f"UPDATE report_retrievals SET {sets}, actor = ?, updated_at = ? WHERE report_id = ?",
            values,
        )

    db.append_event(conn, "report.retrieval_updated", actor, payload, apply_fn=apply_fn)


def promote_occurrence_to_report(conn, actor: str, occurrence_id: str) -> str:
    """Convenience wrapper for the UI: create a report, link this
    occurrence as provenance, and assign it as the canonical progression
    in one step. Returns the new report_id. Does not itself decide
    whether the occurrence deserves a report -- the caller (UI) is
    responsible for only offering this for occurrences with a current
    'include' title/abstract vote.
    """
    report_id = create_report(conn, actor)
    link_occurrence_to_report(conn, actor, occurrence_id, report_id)
    assign_progression(conn, actor, report_id, occurrence_id)
    return report_id


def list_reports(conn) -> list[dict]:
    """All reports with their current progression/retrieval status, for
    a UI management screen."""
    rows = conn.execute(
        "SELECT r.report_id, rp.canonical_occurrence, rp.branch_id,"
        " rr.retrieval_status, rr.full_text_outcome, rr.exclusion_reason"
        " FROM reports r"
        " LEFT JOIN report_progressions rp ON rp.report_id = r.report_id"
        " LEFT JOIN report_retrievals rr ON rr.report_id = r.report_id"
        " ORDER BY r.created_at ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def occurrences_for_report(conn, report_id: str) -> list[str]:
    """All source occurrence IDs linked to this report via `record_reports`
    (provenance; Studies reference item 5) -- the canonical occurrence is
    one of these, never the only one once duplicate/cross-branch records
    have been linked."""
    rows = conn.execute(
        "SELECT occurrence_id FROM record_reports WHERE report_id = ? ORDER BY created_at ASC",
        (report_id,),
    ).fetchall()
    return [r["occurrence_id"] for r in rows]


def unlinked_included_occurrences(conn, stage: str = "title_abstract") -> list[dict]:
    """Occurrences with a current 'include' vote at the given stage that
    are not yet linked to any report -- candidates to promote to
    full-text (screening-workflow spec §6: "Records included at title/
    abstract flow into a full-text queue in the same project")."""
    rows = conn.execute(
        "SELECT o.occurrence_id, sv.reviewer_id FROM occurrences o"
        " JOIN screen_votes sv ON sv.occurrence_id = o.occurrence_id"
        "   AND sv.stage = ? AND sv.decision = 'include' AND sv.superseded_at IS NULL"
        " WHERE o.is_active = 1"
        " AND o.occurrence_id NOT IN (SELECT occurrence_id FROM record_reports)",
        (stage,),
    ).fetchall()
    return [dict(r) for r in rows]


def counts(conn) -> dict:
    """Derived report-level counts (PRISMA spec §3.2, §3.4). A 'maybe'
    full-text outcome (Directive C) is non-terminal -- it stays
    pending, not included or excluded, matching the screening-stage
    Maybe semantics."""
    rows = conn.execute("SELECT * FROM report_retrievals").fetchall()
    sought = len(rows)
    not_retrieved = sum(1 for r in rows if r["retrieval_status"] == "not_retrieved")
    pending = sum(
        1 for r in rows
        if r["retrieval_status"] == "pending"
        or (r["retrieval_status"] == "retrieved" and r["full_text_outcome"] == "maybe")
    )
    assessed_rows = [r for r in rows if r["retrieval_status"] == "retrieved"]
    included = sum(1 for r in assessed_rows if r["full_text_outcome"] == "included")
    excluded = sum(1 for r in assessed_rows if r["full_text_outcome"] == "excluded")
    assessed = included + excluded
    reason_counts: dict[str, int] = {}
    for r in assessed_rows:
        if r["full_text_outcome"] == "excluded" and r["exclusion_reason"]:
            reason_counts[r["exclusion_reason"]] = reason_counts.get(r["exclusion_reason"], 0) + 1
    return {
        "reports_sought": sought,
        "reports_not_retrieved": not_retrieved,
        "reports_pending": pending,
        "reports_assessed": assessed,
        "reports_included": included,
        "reports_excluded": excluded,
        "reasons": reason_counts,
    }


def counts_by_branch(conn) -> dict[str, dict]:
    """Per-branch report counts (spec §3.4's branch-scoped equations:
    ``reports_sought_b``, ``reports_not_retrieved_b``,
    ``reports_sought_pending_b``, ``reports_assessed_b``,
    ``reports_excluded_b``, ``reports_included_b``, and the per-branch
    full-text-reason sum). Branch here is ``report_progressions
    .branch_id`` -- a report has a branch only once it has advanced
    (spec invariant §3.4.6: "Each report appears once at each stage in
    its one ReportProgression.branch_id"); a report with no progression
    yet contributes to no branch's counts, matching ``reports_pending``
    coverage in the global totals, not a branch breakdown.

    This was previously a real gap: ``counts()`` had no branch
    dimension at all, even though the spec's §3.4 equations are
    explicitly per-branch and invariant 6 requires reports to be
    attributable to exactly one branch at each stage.
    """
    rows = conn.execute(
        "SELECT rr.*, rp.branch_id AS branch_id FROM report_retrievals rr"
        " JOIN report_progressions rp ON rp.report_id = rr.report_id"
    ).fetchall()
    by_branch: dict[str, dict] = {}
    for r in rows:
        b = by_branch.setdefault(r["branch_id"], {
            "reports_sought": 0, "reports_not_retrieved": 0, "reports_pending": 0,
            "reports_assessed": 0, "reports_included": 0, "reports_excluded": 0,
            "reasons": {},
        })
        b["reports_sought"] += 1
        if r["retrieval_status"] == "not_retrieved":
            b["reports_not_retrieved"] += 1
        elif r["retrieval_status"] == "pending":
            b["reports_pending"] += 1
        elif r["retrieval_status"] == "retrieved":
            if r["full_text_outcome"] == "included":
                b["reports_assessed"] += 1
                b["reports_included"] += 1
            elif r["full_text_outcome"] == "excluded":
                b["reports_assessed"] += 1
                b["reports_excluded"] += 1
                if r["exclusion_reason"]:
                    b["reasons"][r["exclusion_reason"]] = b["reasons"].get(r["exclusion_reason"], 0) + 1
            elif r["full_text_outcome"] == "maybe":
                # Directive C: 'maybe' is non-terminal, same as a
                # not-yet-retrieved report -- it must not silently drop
                # out of reports_sought_b = not_retrieved_b + assessed_b
                # + pending_b.
                b["reports_pending"] += 1
    return by_branch

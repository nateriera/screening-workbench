"""Study entities, study decisions, and report-study linking/conflicts.

Implements docs/specs/behavioral-spec-prisma-counts-export.md §2.4-2.5 and
the count equations in §3.3.
"""
from __future__ import annotations

from screening_workbench import db
from screening_workbench.ids import new_id

VALID_DECISIONS = ("included", "excluded", "unresolved")


def create_study(conn, actor: str) -> str:
    study_id = new_id("study")

    def apply_fn(c, event):
        c.execute(
            "INSERT INTO studies (study_id, created_at) VALUES (?, ?)",
            (event["payload"]["study_id"], event["occurred_at"]),
        )

    db.append_event(conn, "study.created", actor, {"study_id": study_id}, apply_fn=apply_fn)
    return study_id


def set_study_decision(conn, actor: str, study_id: str, decision: str, rationale: str) -> None:
    """Record an explicit, audited study decision (spec §2.4.1).

    Always appends a history row; the current-decision table reflects
    only the latest. A link alone never sets inclusion -- this is the
    only path to ``studies_included`` membership.
    """
    if decision not in VALID_DECISIONS:
        raise ValueError(f"invalid decision: {decision}")
    if not rationale or not rationale.strip():
        raise ValueError("a rationale is required for every study decision")

    payload = {"study_id": study_id, "decision": decision, "rationale": rationale}

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO study_decision_events (event_row_id, study_id, decision, rationale, actor, occurred_at)"
            " VALUES (?,?,?,?,?,?)",
            (new_id("sde"), p["study_id"], p["decision"], p["rationale"], event["actor"], event["occurred_at"]),
        )
        c.execute(
            "INSERT INTO study_decisions (study_id, decision, rationale, actor, decided_at) VALUES (?,?,?,?,?)"
            " ON CONFLICT(study_id) DO UPDATE SET decision=excluded.decision, rationale=excluded.rationale,"
            " actor=excluded.actor, decided_at=excluded.decided_at",
            (p["study_id"], p["decision"], p["rationale"], event["actor"], event["occurred_at"]),
        )

    db.append_event(conn, "study.decision_set", actor, payload, apply_fn=apply_fn)


def link_report_study(conn, actor: str, report_id: str, study_id: str, rationale: str | None = None) -> None:
    """Add a report<->study link. Always appends a link-history event even
    if the active link already exists, per acceptance test 4's "repeated
    link-add ... leaves the active relationship set at N distinct pairs
    but more link-history rows" requirement.
    """
    payload = {"report_id": report_id, "study_id": study_id, "rationale": rationale}

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO report_study_link_events (event_row_id, report_id, study_id, action, actor,"
            " occurred_at, rationale) VALUES (?,?,?,?,?,?,?)",
            (new_id("rsle"), p["report_id"], p["study_id"], "add", event["actor"], event["occurred_at"], p["rationale"]),
        )
        c.execute(
            "INSERT OR IGNORE INTO report_study_links (report_id, study_id) VALUES (?, ?)",
            (p["report_id"], p["study_id"]),
        )

    db.append_event(conn, "study.link_added", actor, payload, apply_fn=apply_fn)


def unlink_report_study(conn, actor: str, report_id: str, study_id: str, rationale: str) -> None:
    if not rationale or not rationale.strip():
        raise ValueError("a rationale is required to remove a report-study link")
    payload = {"report_id": report_id, "study_id": study_id, "rationale": rationale}

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO report_study_link_events (event_row_id, report_id, study_id, action, actor,"
            " occurred_at, rationale) VALUES (?,?,?,?,?,?,?)",
            (new_id("rsle"), p["report_id"], p["study_id"], "remove", event["actor"], event["occurred_at"], p["rationale"]),
        )
        c.execute(
            "DELETE FROM report_study_links WHERE report_id = ? AND study_id = ?",
            (p["report_id"], p["study_id"]),
        )

    db.append_event(conn, "study.link_removed", actor, payload, apply_fn=apply_fn)


def active_link_count(conn) -> int:
    """Distinct active report-study pairs (not link-history row count)."""
    return conn.execute("SELECT COUNT(*) AS n FROM report_study_links").fetchone()["n"]


def reports_for_study(conn, study_id: str) -> list[str]:
    """Active (not removed) report IDs linked to this study, for the
    Studies UI's grouped hierarchy (reference items 1/2: report counts
    and nesting under the selected study)."""
    rows = conn.execute(
        "SELECT report_id FROM report_study_links WHERE study_id = ?", (study_id,)
    ).fetchall()
    return [r["report_id"] for r in rows]


def link_history_count(conn) -> int:
    """Total link-history event rows (add+remove), for audit/testing."""
    return conn.execute("SELECT COUNT(*) AS n FROM report_study_link_events").fetchone()["n"]


def _report_full_text_outcome(conn, report_id: str) -> str | None:
    row = conn.execute(
        "SELECT full_text_outcome FROM report_retrievals WHERE report_id = ?", (report_id,)
    ).fetchone()
    return row["full_text_outcome"] if row else None


def detect_conflict(conn, study_id: str) -> bool:
    """A conflict exists when the study is included with no terminal
    included report, excluded despite an included linked report, or the
    decision is unresolved while links exist (spec §2.5).
    """
    decision_row = conn.execute("SELECT decision FROM study_decisions WHERE study_id = ?", (study_id,)).fetchone()
    decision = decision_row["decision"] if decision_row else "unresolved"
    linked_reports = [
        r["report_id"] for r in conn.execute(
            "SELECT report_id FROM report_study_links WHERE study_id = ?", (study_id,)
        ).fetchall()
    ]
    outcomes = [_report_full_text_outcome(conn, r) for r in linked_reports]
    has_included_report = "included" in outcomes

    if decision == "included" and not has_included_report:
        return True
    if decision == "excluded" and has_included_report:
        return True
    if decision == "unresolved" and linked_reports:
        return True
    return False


def counts(conn) -> dict:
    """Derived study/report-link counts (PRISMA spec §3.3): distinct IDs,
    never link-row counts."""
    included_studies = {
        r["study_id"] for r in conn.execute(
            "SELECT study_id FROM study_decisions WHERE decision = 'included'"
        ).fetchall()
    }
    included_reports = {
        r["report_id"] for r in conn.execute(
            "SELECT report_id FROM report_retrievals WHERE full_text_outcome = 'included'"
        ).fetchall()
    }
    links = conn.execute("SELECT report_id, study_id FROM report_study_links").fetchall()

    studies_included = {
        s for (r, s) in ((l["report_id"], l["study_id"]) for l in links)
        if s in included_studies and r in included_reports
    }
    reports_of_included_studies = {
        r for (r, s) in ((l["report_id"], l["study_id"]) for l in links)
        if s in included_studies and r in included_reports
    }
    return {
        "studies_included": len(studies_included),
        "reports_of_included_studies": len(reports_of_included_studies),
        "active_links": active_link_count(conn),
        "link_history_rows": link_history_count(conn),
    }


def list_studies(conn) -> list[dict]:
    """All studies with current decision and conflict flag, for a UI
    management screen."""
    rows = conn.execute(
        "SELECT s.study_id, sd.decision, sd.rationale FROM studies s"
        " LEFT JOIN study_decisions sd ON sd.study_id = s.study_id"
        " ORDER BY s.created_at ASC"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["has_conflict"] = detect_conflict(conn, r["study_id"])
        out.append(d)
    return out

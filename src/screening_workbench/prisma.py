"""PRISMA 2020 count derivation: identification/screening stage.

Implements docs/specs/behavioral-spec-prisma-counts-export.md §3.1 and the
invariants in §3.4. Report/study-level counts live in reports.py/studies.py
and are merged in here for one complete snapshot.
"""
from __future__ import annotations

from screening_workbench import dedup, reports, studies


def _occurrences_by_source_class(conn) -> dict[str, int]:
    rows = conn.execute(
        "SELECT s.class AS class, COUNT(*) AS n FROM occurrences o"
        " JOIN sources s ON s.source_id = o.source_id GROUP BY s.class"
    ).fetchall()
    out = {"database": 0, "register": 0, "other_method": 0}
    for r in rows:
        out[r["class"]] = r["n"]
    return out


def _branch_breakdown(conn, branch_id: str) -> dict:
    total = conn.execute(
        "SELECT COUNT(*) AS n FROM occurrences WHERE branch_id = ?", (branch_id,)
    ).fetchone()["n"]
    removed = conn.execute(
        "SELECT COUNT(*) AS n FROM duplicate_merges dm"
        " JOIN occurrences o ON o.occurrence_id = dm.absorbed_occurrence"
        " WHERE o.branch_id = ? AND dm.classification = 'pre_screen_removal' AND dm.undone_at IS NULL",
        (branch_id,),
    ).fetchone()["n"]
    # A maybe vote is explicitly nonterminal; unresolved disagreements are
    # pending until an owner resolution supersedes them. Count only distinct
    # occurrences with a current include/exclude outcome and no conflict.
    from screening_workbench import screening
    unresolved_conflicts = set(screening.list_conflicts(conn, "title_abstract"))
    screened_rows = conn.execute(
        "SELECT DISTINCT sv.occurrence_id FROM screen_votes sv"
        " JOIN occurrences o ON o.occurrence_id = sv.occurrence_id"
        " WHERE o.branch_id = ? AND sv.superseded_at IS NULL AND sv.stage = 'title_abstract'"
        " AND sv.decision IN ('include', 'exclude')",
        (branch_id,),
    ).fetchall()
    screened = sum(1 for r in screened_rows if r["occurrence_id"] not in unresolved_conflicts)
    # "Screening pending" = active, unscreened/nonterminal, not removed.
    # "Prescreen pending" (awaiting a dedup decision such as an open fuzzy
    # candidate) is a documented v1 simplification: treated as 0 since fuzzy
    # candidates don't block screening eligibility in this version.
    prescreen_pending = 0
    screening_pending = max(total - removed - screened - prescreen_pending, 0)
    return {
        "identified": total,
        "removed_before_screen": removed,
        "prescreen_pending": prescreen_pending,
        "screening_pending": screening_pending,
        "records_screened": screened,
    }


def identification_and_screening_counts(conn) -> dict:
    """§3.1 identification/screening count model, per branch and totals."""
    by_class = _occurrences_by_source_class(conn)
    identified_database = by_class["database"]
    identified_register = by_class["register"]
    identified_other = by_class["other_method"]
    identified_db_register = identified_database + identified_register
    identified_total = identified_db_register + identified_other

    branch_rows = conn.execute("SELECT branch_id FROM branches").fetchall()
    branches = {}
    for b in branch_rows:
        branches[b["branch_id"]] = _branch_breakdown(conn, b["branch_id"])

    dedup_counts = dedup.counts(conn)

    return {
        "identified_database": identified_database,
        "identified_register": identified_register,
        "identified_other": identified_other,
        "identified_db_register": identified_db_register,
        "identified_total": identified_total,
        "removed_before_screen": dedup_counts["duplicates_removed_before_screening"],
        "post_screen_duplicate_corrections": dedup_counts["duplicates_merged_after_screening"],
        "open_fuzzy_pairs": dedup_counts["open_fuzzy_pairs"],
        "branches": branches,
    }


def full_snapshot(conn) -> dict:
    """One complete count snapshot across all PRISMA stages (§2.6.1)."""
    return {
        "identification": identification_and_screening_counts(conn),
        "reports": reports.counts(conn),
        "studies": studies.counts(conn),
    }


def verify_invariants(conn) -> list[str]:
    """Check the §3.4 invariants; return a list of violation messages
    (empty list means all checked invariants hold)."""
    violations: list[str] = []
    ident = identification_and_screening_counts(conn)
    for branch_id, b in ident["branches"].items():
        lhs = b["identified"]
        rhs = (
            b["removed_before_screen"] + b["prescreen_pending"]
            + b["screening_pending"] + b["records_screened"]
        )
        if lhs != rhs:
            violations.append(
                f"branch {branch_id}: identified({lhs}) != removed+prescreen_pending"
                f"+screening_pending+screened({rhs})"
            )

    rep = reports.counts(conn)
    if rep["reports_assessed"] != rep["reports_included"] + rep["reports_excluded"]:
        violations.append("reports_assessed != reports_included + reports_excluded")
    if rep["reports_sought"] != rep["reports_assessed"] + rep["reports_not_retrieved"] + rep["reports_pending"]:
        violations.append("reports_sought != reports_assessed + reports_not_retrieved + reports_pending")

    # §3.4 branch-scoped report equations (reports_sought_b etc.) --
    # previously unchecked here entirely; reports.counts_by_branch
    # closes that gap.
    by_branch = reports.counts_by_branch(conn)
    for branch_id, b in by_branch.items():
        if b["reports_assessed"] != b["reports_included"] + b["reports_excluded"]:
            violations.append(f"branch {branch_id}: reports_assessed_b != reports_included_b + reports_excluded_b")
        if b["reports_sought"] != b["reports_assessed"] + b["reports_not_retrieved"] + b["reports_pending"]:
            violations.append(
                f"branch {branch_id}: reports_sought_b != reports_assessed_b"
                "+reports_not_retrieved_b+reports_sought_pending_b"
            )
        reason_sum = sum(b["reasons"].values())
        if reason_sum != b["reports_excluded"]:
            violations.append(f"branch {branch_id}: sum(full_text_reason_count_b) != reports_excluded_b")

    return violations

"""Screening workflow: votes, blind-mode isolation, and conflict resolution.

Implements docs/specs/behavioral-spec-screening-workflow.md §4-5 and the
blind-export/auditor-role rules in PRISMA spec §2.6 for the subset relevant
to screening (full export authorization lives in export.py, build-order
item 7).
"""
from __future__ import annotations

import json

from screening_workbench import db
from screening_workbench.ids import new_id

VALID_DECISIONS = ("include", "maybe", "exclude")

# Fixed exclusion-reason taxonomy, key-capped 1-7 (UI reference target
# §10, docs/ui-reference-screening.md): replaces the old free-text
# exclude-reason prompt with a closed project taxonomy. Position in this
# tuple is the key number shown/bound in the UI (index 0 -> key "1").
EXCLUSION_REASONS = (
    "Wrong population",
    "Wrong intervention or exposure",
    "Wrong outcome",
    "Wrong study design",
    "Not primary research",
    "Language",
    "Outside date range",
)


def cast_vote(
    conn,
    *,
    occurrence_id: str,
    reviewer_id: str,
    decision: str,
    reason: str | None = None,
    stage: str = "title_abstract",
    actor: str | None = None,
) -> str:
    """Cast (or replace) one reviewer's vote on one occurrence.

    A later vote by the same reviewer/occurrence/stage supersedes the
    prior one (marks it ``superseded_at``) rather than deleting it --
    preserving decision history per screening-workflow spec §4.
    Exclude requires exactly one reason (spec: "requires exactly one
    reason from the project taxonomy").
    """
    if decision not in VALID_DECISIONS:
        raise ValueError(f"invalid decision: {decision}")
    if decision == "exclude" and not reason:
        raise ValueError("exclude requires exactly one reason")
    if decision != "exclude" and reason:
        raise ValueError("reason is only valid for an exclude decision")

    actor = actor or reviewer_id
    vote_id = new_id("vote")
    payload = {
        "vote_id": vote_id,
        "occurrence_id": occurrence_id,
        "reviewer_id": reviewer_id,
        "stage": stage,
        "decision": decision,
        "reason": reason,
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute("INSERT OR IGNORE INTO project_settings (id) VALUES ('project')")
        c.execute("UPDATE project_settings SET screening_started = 1 WHERE id='project'")
        c.execute(
            "UPDATE screen_votes SET superseded_at = ? WHERE occurrence_id = ? AND"
            " reviewer_id = ? AND stage = ? AND superseded_at IS NULL",
            (event["occurred_at"], p["occurrence_id"], p["reviewer_id"], p["stage"]),
        )
        c.execute(
            "INSERT INTO screen_votes (vote_id, occurrence_id, stage, reviewer_id,"
            " decision, reason, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                p["vote_id"], p["occurrence_id"], p["stage"], p["reviewer_id"],
                p["decision"], p["reason"], event["occurred_at"],
            ),
        )

    db.append_event(conn, "screening.vote_cast", actor, payload, apply_fn=apply_fn)
    return vote_id


def undo_last_vote(conn, reviewer_id: str, stage: str = "title_abstract", actor: str | None = None) -> dict | None:
    """Retract this reviewer's most recently cast current vote, restoring
    that occurrence to undecided for them (UI reference target §9/§11:
    "Ctrl+Z undoes #N"). Recorded as its own append-only event, same
    pattern as every other write -- never a silent row mutation.

    Returns the undone vote (including its "#N" -- `screen_votes`'s
    implicit SQLite rowid, a real monotonic integer since `vote_id` is a
    TEXT primary key and the table is not WITHOUT ROWID), or None if
    this reviewer has no current vote to undo."""
    row = conn.execute(
        "SELECT screen_votes.rowid AS n, * FROM screen_votes WHERE reviewer_id=? AND stage=? AND superseded_at IS NULL"
        " ORDER BY created_at DESC, screen_votes.rowid DESC LIMIT 1",
        (reviewer_id, stage),
    ).fetchone()
    if row is None:
        return None

    actor = actor or reviewer_id
    payload = {"vote_id": row["vote_id"], "occurrence_id": row["occurrence_id"], "reviewer_id": reviewer_id, "stage": stage}

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "UPDATE screen_votes SET superseded_at = ? WHERE vote_id = ? AND superseded_at IS NULL",
            (event["occurred_at"], p["vote_id"]),
        )

    db.append_event(conn, "screening.vote_undone", actor, payload, apply_fn=apply_fn)
    return dict(row)


def current_vote(conn, occurrence_id: str, reviewer_id: str, stage: str = "title_abstract") -> dict | None:
    row = conn.execute(
        "SELECT * FROM screen_votes WHERE occurrence_id=? AND reviewer_id=? AND stage=?"
        " AND superseded_at IS NULL",
        (occurrence_id, reviewer_id, stage),
    ).fetchone()
    return dict(row) if row else None


def votes_for_occurrence(conn, occurrence_id: str, stage: str = "title_abstract") -> list[dict]:
    """All reviewers' current votes for one occurrence (owner/auditor view;
    NOT the blind-filtered view -- see `visible_votes_for_reviewer`)."""
    rows = conn.execute(
        "SELECT * FROM screen_votes WHERE occurrence_id=? AND stage=? AND superseded_at IS NULL",
        (occurrence_id, stage),
    ).fetchall()
    return [dict(r) for r in rows]


def visible_votes_for_reviewer(
    conn, occurrence_id: str, viewer_reviewer_id: str, *, is_blind: bool, is_owner_or_auditor: bool, stage: str = "title_abstract",
) -> list[dict]:
    """Blind-mode isolation (spec §4): while blind, a reviewer sees only
    their own vote; an owner/auditor (or an unblinded project) sees all.
    """
    all_votes = votes_for_occurrence(conn, occurrence_id, stage)
    if not is_blind or is_owner_or_auditor:
        return all_votes
    return [v for v in all_votes if v["reviewer_id"] == viewer_reviewer_id]


def has_conflict(conn, occurrence_id: str, stage: str = "title_abstract") -> bool:
    """A conflict exists when final decisions disagree; `maybe` disagrees
    with anything (spec §5: "maybe counts as disagreeing with anything").
    """
    votes = votes_for_occurrence(conn, occurrence_id, stage)
    decisions = {v["decision"] for v in votes}
    if len(decisions) <= 1 and "maybe" not in decisions:
        return False
    return len(votes) >= 2 and (len(decisions) > 1)


def list_conflicts(conn, stage: str = "title_abstract") -> list[str]:
    """Occurrence IDs with an unresolved conflict (>=2 current votes that
    disagree and no resolution vote has superseded them yet)."""
    rows = conn.execute(
        "SELECT DISTINCT occurrence_id FROM screen_votes"
        " WHERE stage = ? AND superseded_at IS NULL AND reviewer_id != '__resolution__'",
        (stage,),
    ).fetchall()
    return [r["occurrence_id"] for r in rows if has_conflict(conn, r["occurrence_id"], stage)]


def _queue_rows(conn, reviewer_id: str, stage: str, *, undecided_only: bool):
    if undecided_only:
        return conn.execute(
            "SELECT o.occurrence_id, o.batch_id, of.fields_json FROM occurrences o"
            " JOIN occurrence_fields of ON of.occurrence_id = o.occurrence_id"
            " LEFT JOIN screen_votes sv ON sv.occurrence_id = o.occurrence_id"
            "   AND sv.reviewer_id = ? AND sv.stage = ? AND sv.superseded_at IS NULL"
            " WHERE o.is_active = 1 AND sv.vote_id IS NULL"
            " ORDER BY o.created_at ASC",
            (reviewer_id, stage),
        ).fetchall()
    return conn.execute(
        "SELECT o.occurrence_id, o.batch_id, of.fields_json FROM occurrences o"
        " JOIN occurrence_fields of ON of.occurrence_id = o.occurrence_id"
        " WHERE o.is_active = 1 ORDER BY o.created_at ASC",
    ).fetchall()


def _matches_filters(fields: dict, *, search: str, year: str, journal: str) -> bool:
    if year and str(fields.get("year") or "") != year:
        return False
    if journal and journal not in str(fields.get("journal") or "").lower():
        return False
    if search:
        haystack = " ".join(str(fields.get(k) or "") for k in ("title", "abstract", "journal")).lower()
        if search not in haystack:
            return False
    return True


def list_distinct_years(conn, reviewer_id: str, stage: str = "title_abstract") -> list[str]:
    """Distinct years present among this reviewer's active occurrences,
    sorted descending, for the Screening tab's year facet (UI reference
    target §4: a dropdown, not free text)."""
    rows = _queue_rows(conn, reviewer_id, stage, undecided_only=False)
    years: set[str] = set()
    for row in rows:
        fields = json.loads(row["fields_json"])
        year = str(fields.get("year") or "").strip()
        if year:
            years.add(year)
    return sorted(years, reverse=True)


def list_distinct_journals(conn, reviewer_id: str, stage: str = "title_abstract") -> list[str]:
    """Distinct journal names present among this reviewer's active
    occurrences, sorted alphabetically, for the Screening tab's journal
    facet (UI reference target §4)."""
    rows = _queue_rows(conn, reviewer_id, stage, undecided_only=False)
    journals: set[str] = set()
    for row in rows:
        fields = json.loads(row["fields_json"])
        journal = str(fields.get("journal") or "").strip()
        if journal:
            journals.add(journal)
    return sorted(journals)


def find_next_undecided(
    conn,
    reviewer_id: str,
    *,
    stage: str = "title_abstract",
    search: str | None = None,
    year: str | None = None,
    journal: str | None = None,
    batch_id: str | None = None,
    undecided_only: bool = True,
) -> str | None:
    """Next occurrence in the reviewer's queue, optionally restricted to
    a free-text title/abstract/journal match, an exact year, a journal
    substring, a batch, and/or "undecided only" (screening-workflow spec
    §4 ergonomics: search + year/journal/batch facets, UI reference
    target §4). An empty/whitespace-only filter value means "no filter".
    `undecided_only=False` browses every active occurrence regardless of
    this reviewer's vote state (the reference's "Undecided only" toggle,
    on by default)."""
    search = (search or "").strip().lower()
    year = (year or "").strip()
    journal = (journal or "").strip().lower()
    batch_id = (batch_id or "").strip() or None

    rows = _queue_rows(conn, reviewer_id, stage, undecided_only=undecided_only)
    for row in rows:
        if batch_id and row["batch_id"] != batch_id:
            continue
        fields = json.loads(row["fields_json"])
        if not _matches_filters(fields, search=search, year=year, journal=journal):
            continue
        return row["occurrence_id"]
    return None


def count_undecided(
    conn,
    reviewer_id: str,
    *,
    stage: str = "title_abstract",
    search: str | None = None,
    year: str | None = None,
    journal: str | None = None,
    batch_id: str | None = None,
    undecided_only: bool = True,
) -> int:
    """Count matching the same filter as `find_next_undecided` (for a
    "N remaining"/"N of total" label)."""
    search = (search or "").strip().lower()
    year = (year or "").strip()
    journal = (journal or "").strip().lower()
    batch_id = (batch_id or "").strip() or None

    rows = _queue_rows(conn, reviewer_id, stage, undecided_only=undecided_only)
    n = 0
    for row in rows:
        if batch_id and row["batch_id"] != batch_id:
            continue
        fields = json.loads(row["fields_json"])
        if _matches_filters(fields, search=search, year=year, journal=journal):
            n += 1
    return n


def list_undecided(
    conn,
    reviewer_id: str,
    *,
    stage: str = "title_abstract",
    search: str | None = None,
    year: str | None = None,
    journal: str | None = None,
    batch_id: str | None = None,
    undecided_only: bool = True,
    limit: int | None = None,
) -> list[dict]:
    """Every occurrence matching the same filter as `find_next_undecided`
    (title + year + journal + occurrence_id, in queue order) -- backs
    the Screening tab's upcoming-queue list (UI reference target §5) and
    bulk select/decide (screening-workflow spec §4: "bulk select + bulk
    decide for obvious batches")."""
    search = (search or "").strip().lower()
    year = (year or "").strip()
    journal = (journal or "").strip().lower()
    batch_id = (batch_id or "").strip() or None

    rows = _queue_rows(conn, reviewer_id, stage, undecided_only=undecided_only)
    out = []
    for row in rows:
        if batch_id and row["batch_id"] != batch_id:
            continue
        fields = json.loads(row["fields_json"])
        if not _matches_filters(fields, search=search, year=year, journal=journal):
            continue
        out.append({
            "occurrence_id": row["occurrence_id"],
            "title": fields.get("title"),
            "year": fields.get("year"),
            "journal": fields.get("journal"),
        })
        if limit is not None and len(out) >= limit:
            break
    return out


def bulk_cast_vote(
    conn,
    *,
    occurrence_ids: list[str],
    reviewer_id: str,
    decision: str,
    reason: str | None = None,
    stage: str = "title_abstract",
    actor: str | None = None,
) -> int:
    """Cast the same decision on multiple occurrences in one UI action
    (screening-workflow spec §4: "bulk select + bulk decide for obvious
    batches"). Each occurrence still gets its own `screening.vote_cast`
    event in the audit log -- bulk is a UI convenience, not a different
    data model; a single reason is required up front for exclude so the
    whole batch shares one taxonomy entry, the same rule as a single
    exclude vote. Returns the number of votes cast."""
    if not occurrence_ids:
        return 0
    for occurrence_id in occurrence_ids:
        cast_vote(
            conn, occurrence_id=occurrence_id, reviewer_id=reviewer_id,
            decision=decision, reason=reason, stage=stage, actor=actor,
        )
    return len(occurrence_ids)


def list_active_batches(conn) -> list[dict]:
    """Distinct import batches among currently-active occurrences, for
    the Screening tab's batch facet filter (UI reference target §4)."""
    rows = conn.execute(
        "SELECT ib.batch_id, ib.source_name, COUNT(*) AS n FROM occurrences o"
        " JOIN import_batches ib ON ib.batch_id = o.batch_id"
        " WHERE o.is_active = 1"
        " GROUP BY ib.batch_id, ib.source_name"
        " ORDER BY ib.imported_at ASC"
    ).fetchall()
    return [{"batch_id": r["batch_id"], "source_name": r["source_name"], "count": r["n"]} for r in rows]


def batch_info_for_occurrence(conn, occurrence_id: str) -> dict | None:
    """The import batch an occurrence came from, plus its 1-based
    ordinal among ALL import batches (not just active ones -- an
    occurrence's own batch is always itself active) and its source
    format, for the record-pane position line (UI reference target §6:
    'Batch 2 (RIS, Database A)'). Returns None if the occurrence has no
    batch (should not happen for a committed import, but defensive)."""
    row = conn.execute(
        "SELECT o.batch_id, ib.source_name, ib.source_format, ib.imported_at"
        " FROM occurrences o JOIN import_batches ib ON ib.batch_id = o.batch_id"
        " WHERE o.occurrence_id = ?",
        (occurrence_id,),
    ).fetchone()
    if row is None:
        return None
    ordinal = conn.execute(
        "SELECT COUNT(*) AS n FROM import_batches WHERE imported_at <= ?",
        (row["imported_at"],),
    ).fetchone()["n"]
    format_labels = {"csv": "CSV", "ris": "RIS", "pubmed_xml": "PubMed XML"}
    return {
        "batch_id": row["batch_id"],
        "ordinal": ordinal,
        "source_name": row["source_name"],
        "source_format": format_labels.get(row["source_format"], row["source_format"]),
    }


def recent_decisions_for_reviewer(conn, reviewer_id: str, *, stage: str = "title_abstract", limit: int = 4) -> list[dict]:
    """The reviewer's own last N current decisions (title + decision +
    reason), newest first -- UI reference target §11 "Your recent
    decisions" panel. Blind-safe by construction: this query only ever
    reads ``reviewer_id``'s own votes, never another reviewer's, so it
    is correct to show unconditionally regardless of the project's
    blind-mode setting."""
    rows = conn.execute(
        "SELECT sv.rowid AS n, sv.occurrence_id, sv.decision, sv.reason, sv.created_at, of.fields_json"
        " FROM screen_votes sv"
        " JOIN occurrence_fields of ON of.occurrence_id = sv.occurrence_id"
        " WHERE sv.reviewer_id = ? AND sv.stage = ? AND sv.superseded_at IS NULL"
        " ORDER BY sv.created_at DESC, sv.rowid DESC LIMIT ?",
        (reviewer_id, stage, limit),
    ).fetchall()
    out = []
    for r in rows:
        fields = json.loads(r["fields_json"])
        out.append({
            "number": r["n"],
            "occurrence_id": r["occurrence_id"],
            "decision": r["decision"],
            "reason": r["reason"],
            "title": fields.get("title"),
        })
    return out


def list_maybe_decisions_for_reviewer(conn, reviewer_id: str, stage: str = "title_abstract") -> list[dict]:
    """Every occurrence this reviewer currently has a 'maybe' vote on,
    for the Maybe re-review tab (UI reference target §3: a dedicated
    section, not folded into the main queue). Blind-safe by
    construction -- only ever this reviewer's own votes."""
    rows = conn.execute(
        "SELECT sv.occurrence_id, sv.created_at, of.fields_json FROM screen_votes sv"
        " JOIN occurrence_fields of ON of.occurrence_id = sv.occurrence_id"
        " WHERE sv.reviewer_id = ? AND sv.stage = ? AND sv.decision = 'maybe' AND sv.superseded_at IS NULL"
        " ORDER BY sv.created_at ASC",
        (reviewer_id, stage),
    ).fetchall()
    out = []
    for r in rows:
        fields = json.loads(r["fields_json"])
        out.append({
            "occurrence_id": r["occurrence_id"],
            "title": fields.get("title"),
            "year": fields.get("year"),
            "journal": fields.get("journal"),
            "decided_at": r["created_at"],
        })
    return out


LANDIS_KOCH_BANDS = (
    (0.00, "Slight"),
    (0.20, "Fair"),
    (0.40, "Moderate"),
    (0.60, "Substantial"),
    (0.80, "Almost perfect"),
)


def _landis_koch_label(kappa: float) -> str:
    """Landis & Koch (1977) benchmark labels for an unweighted kappa.
    <0 Poor, 0.00-0.20 Slight, 0.21-0.40 Fair, 0.41-0.60 Moderate,
    0.61-0.80 Substantial, 0.81-1.00 Almost perfect."""
    if kappa < 0:
        return "Poor"
    for threshold, label in reversed(LANDIS_KOCH_BANDS):
        if kappa > threshold:
            return label
    return "Slight"


def cohens_kappa(
    conn,
    *,
    stage: str = "title_abstract",
    reviewer_a: str | None = None,
    reviewer_b: str | None = None,
) -> dict:
    """Unweighted Cohen's kappa (Directive A) over title/abstract votes
    for the records BOTH of two reviewers have currently decided.

    Descriptive only: never gates export, unblind, or any other action
    (Directive A section 4) -- callers must not branch control flow on
    the returned kappa value, only display it. v1 computes a pairwise
    kappa for exactly two reviewers; more than two active reviewers
    requires ``reviewer_a``/``reviewer_b`` to disambiguate the pair
    (Fleiss' kappa for >2 raters is out of scope -- named gap, not
    silently extended).

    Returns a dict:
      status: "ok" | "insufficient_reviewers" | "no_double_decided"
      kappa: float | None
      label: str  -- Landis-Koch label, or "n/a -- needs two reviewers"
              / "n/a -- no double-decided records yet" when status != "ok"
      agreement: float | None  -- raw % agreement (po), 0..1
      n: int  -- records both named reviewers have currently decided
      table: dict[str, dict[str, int]] | None  -- 3x3 contingency table,
              table[reviewer_a's decision][reviewer_b's decision] = count
      reviewers: tuple[str, str] | None  -- the pair actually used
    """
    if (reviewer_a is None) != (reviewer_b is None):
        raise ValueError("reviewer_a and reviewer_b must be given together")

    if reviewer_a is None:
        rows = conn.execute(
            "SELECT DISTINCT reviewer_id FROM screen_votes WHERE stage=? AND"
            " superseded_at IS NULL AND reviewer_id != '__resolution__'",
            (stage,),
        ).fetchall()
        active_reviewers = sorted(r["reviewer_id"] for r in rows)
        if len(active_reviewers) < 2:
            return {
                "status": "insufficient_reviewers", "kappa": None,
                "label": "n/a -- needs two reviewers", "agreement": None,
                "n": 0, "table": None, "reviewers": None,
            }
        if len(active_reviewers) > 2:
            raise ValueError(
                f"project has {len(active_reviewers)} reviewers with votes"
                " (v1 kappa is pairwise only); pass reviewer_a/reviewer_b"
                f" explicitly, e.g. one of {active_reviewers}"
            )
        reviewer_a, reviewer_b = active_reviewers
    elif reviewer_a == reviewer_b:
        raise ValueError("reviewer_a and reviewer_b must be different reviewers")

    rows_a = {
        r["occurrence_id"]: r["decision"]
        for r in conn.execute(
            "SELECT occurrence_id, decision FROM screen_votes"
            " WHERE reviewer_id=? AND stage=? AND superseded_at IS NULL",
            (reviewer_a, stage),
        ).fetchall()
    }
    rows_b = {
        r["occurrence_id"]: r["decision"]
        for r in conn.execute(
            "SELECT occurrence_id, decision FROM screen_votes"
            " WHERE reviewer_id=? AND stage=? AND superseded_at IS NULL",
            (reviewer_b, stage),
        ).fetchall()
    }
    # Records decided by only one reviewer are excluded from n (Directive
    # A section 5): intersect, do not union, the two reviewers' sets.
    shared = sorted(set(rows_a) & set(rows_b))
    n = len(shared)
    reviewers = (reviewer_a, reviewer_b)
    if n == 0:
        return {
            "status": "no_double_decided", "kappa": None,
            "label": "n/a -- no double-decided records yet", "agreement": None,
            "n": 0, "table": None, "reviewers": reviewers,
        }

    table = {d1: {d2: 0 for d2 in VALID_DECISIONS} for d1 in VALID_DECISIONS}
    diagonal = 0
    for occurrence_id in shared:
        da, db_ = rows_a[occurrence_id], rows_b[occurrence_id]
        table[da][db_] += 1
        if da == db_:
            diagonal += 1

    row_totals = {d: sum(table[d].values()) for d in VALID_DECISIONS}
    col_totals = {d: sum(table[d1][d] for d1 in VALID_DECISIONS) for d in VALID_DECISIONS}

    po = diagonal / n
    pe = sum((row_totals[d] / n) * (col_totals[d] / n) for d in VALID_DECISIONS)

    if pe >= 1.0:
        # Degenerate case: both reviewers' marginals are concentrated on
        # one category, so chance agreement is already total. kappa is
        # mathematically undefined (0/0); treat perfect observed
        # agreement as kappa=1.0 and anything else as 0.0 rather than
        # raising, since this is a descriptive readout (Directive A
        # section 4), not a value callers should have to guard against.
        kappa = 1.0 if po >= 1.0 else 0.0
    else:
        kappa = (po - pe) / (1 - pe)

    return {
        "status": "ok",
        "kappa": kappa,
        "label": _landis_koch_label(kappa),
        "agreement": po,
        "n": n,
        "table": table,
        "reviewers": reviewers,
    }


def kappa_readout(
    conn,
    *,
    is_blind: bool,
    stage: str = "title_abstract",
    reviewer_a: str | None = None,
    reviewer_b: str | None = None,
) -> dict | None:
    """Blind-gated wrapper around `cohens_kappa` for the Conflicts tab's
    "Agreement (Cohen's kappa)" strip (Directive A section 3). Kappa is
    decision-derived data: while the project is blind, this returns
    None unconditionally -- the readout renders ONLY in the unblinded
    adjudication view, with no owner/auditor exception (consistent with
    the screening-workflow spec section 5 rule that opening the
    conflict queue at all requires blind mode off project-wide)."""
    if is_blind:
        return None
    return cohens_kappa(conn, stage=stage, reviewer_a=reviewer_a, reviewer_b=reviewer_b)


def resolve_conflict(
    conn,
    *,
    occurrence_id: str,
    final_decision: str,
    resolution_note: str,
    actor: str,
    stage: str = "title_abstract",
) -> None:
    """Record an owner-authorized conflict resolution (spec §5).

    Requires blind mode to already be off at the call site (enforced by
    the caller/UI layer per spec: "Opening the conflict queue requires
    blind mode off" -- this function does not re-check blind state since
    it has no notion of the project's blind flag yet).
    """
    if final_decision not in ("include", "exclude"):
        raise ValueError("conflict resolution final decision must be include or exclude")
    if not resolution_note or not resolution_note.strip():
        raise ValueError("resolution note is required")

    payload = {
        "occurrence_id": occurrence_id,
        "stage": stage,
        "final_decision": final_decision,
        "resolution_note": resolution_note,
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "UPDATE screen_votes SET superseded_at = ? WHERE occurrence_id = ? AND stage = ?"
            " AND superseded_at IS NULL",
            (event["occurred_at"], p["occurrence_id"], p["stage"]),
        )
        c.execute(
            "INSERT INTO screen_votes (vote_id, occurrence_id, stage, reviewer_id, decision,"
            " reason, created_at) VALUES (?,?,?,?,?,?,?)",
            (
                new_id("vote"), p["occurrence_id"], p["stage"], "__resolution__",
                p["final_decision"], p["resolution_note"], event["occurred_at"],
            ),
        )

    db.append_event(conn, "screening.conflict_resolved", actor, payload, apply_fn=apply_fn)

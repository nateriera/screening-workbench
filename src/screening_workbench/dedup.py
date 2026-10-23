"""Deduplication engine: exact auto-merge and fuzzy candidate queue.

Implements docs/specs/behavioral-spec-duplicate-detection.md §3 and the
row-level pre/post-screen classification in §3.1.1 and the PRISMA spec's
§2.2.2.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from screening_workbench import db
from screening_workbench.ids import new_id
from screening_workbench.normalize import levenshtein, title_similarity

RULE_VERSION = 1
FUZZY_THRESHOLD = 0.90
# Covers an all-pairs pass for about 7,000 records; pairs are counted lazily
# to bound memory. CPU time remains the residual risk; the limit stays fail-closed.
MAX_PAIR_COMPARISONS = 25_000_000


class PairComparisonLimitError(ValueError):
    """Raised before deduplication when a project exceeds its pair budget."""

    def __init__(self, limit: int = MAX_PAIR_COMPARISONS):
        self.limit = limit
        super().__init__(
            f"Duplicate detection needs more than {limit:,} pair comparisons. "
            "This project is too large for the current automatic comparison limit. "
            "No duplicate merges or review candidates were created."
        )


def _occurrence_normalized(conn, occurrence_id: str) -> dict:
    row = conn.execute(
        "SELECT normalized_json FROM occurrence_fields WHERE occurrence_id = ?",
        (occurrence_id,),
    ).fetchone()
    return json.loads(row["normalized_json"])


def _active_occurrences(conn, exclude_ids: set[str] | None = None) -> list[sqlite3Row]:
    rows = conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE is_active = 1"
    ).fetchall()
    if exclude_ids:
        rows = [r for r in rows if r["occurrence_id"] not in exclude_ids]
    return rows


def _titles_agree(norm_a: dict, norm_b: dict) -> bool:
    """True only when both sides have a non-empty normalized title and agree."""
    ta, tb = norm_a.get("title"), norm_b.get("title")
    return bool(ta and tb and ta == tb)


def _is_exact_match(norm_a: dict, norm_b: dict) -> tuple[bool, list[str]]:
    """Silent DOI merges require normalized-title agreement; title/year
    matches remain an independent exact-match path (spec §3.1)."""
    reasons = []
    doi_a, doi_b = norm_a.get("doi"), norm_b.get("doi")
    doi_match = bool(doi_a and doi_b and doi_a == doi_b)
    titles_agree = _titles_agree(norm_a, norm_b)
    years_match = bool(set(norm_a.get("years", [])) & set(norm_b.get("years", [])))
    if titles_agree and years_match:
        reasons.append("title_year_match")
    if doi_match and titles_agree:
        reasons.append("doi_match")
    return (len(reasons) > 0, reasons)


def _is_doi_conflict_candidate(norm_a: dict, norm_b: dict) -> tuple[bool, list[str]]:
    """Shared DOI with differing/missing titles must go to manual review."""
    doi_a, doi_b = norm_a.get("doi"), norm_b.get("doi")
    doi_match = bool(doi_a and doi_b and doi_a == doi_b)
    if not doi_match or _titles_agree(norm_a, norm_b):
        return False, []
    return True, ["doi_match_title_mismatch"]


def _is_fuzzy_candidate(norm_a: dict, norm_b: dict) -> tuple[bool, float, list[str]]:
    exact, _ = _is_exact_match(norm_a, norm_b)
    if exact:
        return False, 0.0, []
    title_a, title_b = norm_a.get("title"), norm_b.get("title")
    if not title_a or not title_b:
        return False, 0.0, []
    years_a, years_b = set(norm_a.get("years", [])), set(norm_b.get("years", []))
    if not (years_a & years_b):
        return False, 0.0, []
    fa, fb = norm_a.get("first_author"), norm_b.get("first_author")
    if not fa or not fb or fa != fb:
        return False, 0.0, []
    score = title_similarity(title_a, title_b)
    if score < FUZZY_THRESHOLD:
        return False, score, []
    return True, score, ["title_similarity", "same_first_author", "shared_year"]


def _classify_absorbed_row(conn, occurrence_id: str) -> str:
    """Return 'pre_screen_removal' or 'post_screen_correction' based on the
    absorbed occurrence's own vote history immediately before merge
    (dedup spec §3.1.1 -- row-level, independent of other group members).
    """
    vote = conn.execute(
        "SELECT 1 FROM screen_votes WHERE occurrence_id = ? AND superseded_at IS NULL LIMIT 1",
        (occurrence_id,),
    ).fetchone()
    return "post_screen_correction" if vote else "pre_screen_removal"


@dataclass
class DedupRunResult:
    exact_merges: int
    fuzzy_candidates_created: int
    doi_conflict_candidates_created: int = 0


def _iter_candidate_pairs(new_ids: list[str] | None, all_ids: list[str], *, limit: int | None = None):
    """Yield each unordered comparison pair without retaining the cross product."""
    if limit is None:
        limit = MAX_PAIR_COMPARISONS
    comparisons = 0

    def emit(a: str, b: str):
        nonlocal comparisons
        comparisons += 1
        if comparisons > limit:
            raise PairComparisonLimitError(limit)
        return a, b

    if new_ids is None:
        for i, a in enumerate(all_ids):
            for j in range(i + 1, len(all_ids)):
                yield emit(a, all_ids[j])
        return

    new_positions = {occurrence_id: index for index, occurrence_id in enumerate(new_ids)}
    for a in new_ids:
        a_position = new_positions[a]
        for b in all_ids:
            if b == a:
                continue
            b_position = new_positions.get(b)
            if b_position is not None and b_position < a_position:
                continue
            yield emit(a, b)


def ensure_pair_comparison_budget(conn, new_occurrence_count: int) -> None:
    """Reject an import before commit if its dedup pass would exceed the budget."""
    if new_occurrence_count <= 0:
        return
    existing_count = conn.execute(
        "SELECT COUNT(*) FROM occurrences WHERE is_active = 1"
    ).fetchone()[0]
    pair_count = new_occurrence_count * existing_count + new_occurrence_count * (new_occurrence_count - 1) // 2
    if pair_count > MAX_PAIR_COMPARISONS:
        raise PairComparisonLimitError()


def run_exact_and_fuzzy_detection(conn, actor: str, *, batch_id: str | None = None) -> DedupRunResult:
    """Run exact auto-merge and fuzzy candidate detection.

    If ``batch_id`` is given, only new occurrences from that batch are
    compared against all other active occurrences (import-time dedup
    pass per screening-workflow spec §3). Without it, the whole active
    set is scanned (useful after metadata edits / recompute).
    """
    if batch_id:
        new_rows = conn.execute(
            "SELECT occurrence_id FROM occurrences WHERE batch_id = ? AND is_active = 1",
            (batch_id,),
        ).fetchall()
        new_ids = [r["occurrence_id"] for r in new_rows]
        all_active = conn.execute(
            "SELECT occurrence_id FROM occurrences WHERE is_active = 1"
        ).fetchall()
        all_ids = [r["occurrence_id"] for r in all_active]
        pairs = _iter_candidate_pairs(new_ids, all_ids)
    else:
        all_active = conn.execute(
            "SELECT occurrence_id FROM occurrences WHERE is_active = 1"
        ).fetchall()
        all_ids = [r["occurrence_id"] for r in all_active]
        pairs = _iter_candidate_pairs(None, all_ids)

    exact_merges = 0
    fuzzy_created = 0
    # Union-find for exact-match connected components within this run.
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    norm_cache: dict[str, dict] = {}

    def norm(occ_id: str) -> dict:
        if occ_id not in norm_cache:
            norm_cache[occ_id] = _occurrence_normalized(conn, occ_id)
        return norm_cache[occ_id]

    # The candidate iterator enforces the budget as it emits pairs. No database
    # writes occur until the full comparison pass has completed.
    exact_pairs: list[tuple[str, str, list[str]]] = []
    fuzzy_pairs: list[tuple[str, str, float, list[str]]] = []
    doi_conflict_pairs: list[tuple[str, str, list[str]]] = []

    for a, b in pairs:
        na, nb = norm(a), norm(b)
        is_exact, reasons = _is_exact_match(na, nb)
        if is_exact:
            exact_pairs.append((a, b, reasons))
            union(a, b)
            continue
        is_doi_conflict, dreasons = _is_doi_conflict_candidate(na, nb)
        if is_doi_conflict:
            doi_conflict_pairs.append((a, b, dreasons))
            continue
        is_fuzzy, score, freasons = _is_fuzzy_candidate(na, nb)
        if is_fuzzy:
            fuzzy_pairs.append((a, b, score, freasons))

    # Group exact matches into connected components; survivor = oldest
    # created_at, tie-broken by lexicographically smallest ID (spec §3.1).
    components: dict[str, list[str]] = {}
    touched = {a for a, b, _ in exact_pairs} | {b for a, b, _ in exact_pairs}
    for occ_id in touched:
        root = find(occ_id)
        components.setdefault(root, []).append(occ_id)

    for root, members in components.items():
        if len(members) < 2:
            continue
        survivor = _pick_survivor(conn, members)
        absorbed = [m for m in members if m != survivor]
        reasons_by_member = {}
        for a, b, reasons in exact_pairs:
            if a in members and b in members:
                reasons_by_member[a] = reasons_by_member.get(a, []) + reasons
                reasons_by_member[b] = reasons_by_member.get(b, []) + reasons
        _apply_exact_merge(conn, actor, survivor, absorbed, reasons_by_member)
        exact_merges += len(absorbed)

    absorbed_ids = {m for members in components.values() if len(members) >= 2 for m in members}
    for a, b, score, reasons in fuzzy_pairs:
        if a in absorbed_ids or b in absorbed_ids:
            continue  # no longer both active; exact merge took priority
        _create_fuzzy_candidate(conn, a, b, score, reasons)
        fuzzy_created += 1

    doi_conflict_created = 0
    for a, b, reasons in doi_conflict_pairs:
        if a in absorbed_ids or b in absorbed_ids:
            continue
        _create_fuzzy_candidate(conn, a, b, 1.0, reasons)
        doi_conflict_created += 1

    return DedupRunResult(
        exact_merges=exact_merges,
        fuzzy_candidates_created=fuzzy_created,
        doi_conflict_candidates_created=doi_conflict_created,
    )


def _pick_survivor(conn, member_ids: list[str]) -> str:
    rows = conn.execute(
        f"SELECT occurrence_id, created_at FROM occurrences WHERE occurrence_id IN "
        f"({','.join('?' for _ in member_ids)})",
        member_ids,
    ).fetchall()
    rows_sorted = sorted(rows, key=lambda r: (r["created_at"], r["occurrence_id"]))
    return rows_sorted[0]["occurrence_id"]


def _apply_exact_merge(conn, actor: str, survivor: str, absorbed: list[str], reasons_by_member: dict) -> None:
    classifications = {occ_id: _classify_absorbed_row(conn, occ_id) for occ_id in absorbed}

    payload = {
        "survivor": survivor,
        "absorbed": absorbed,
        "classifications": classifications,
        "reasons": {k: v for k, v in reasons_by_member.items() if k in absorbed},
        "rule_version": RULE_VERSION,
    }

    def apply_fn(c, event):
        p = event["payload"]
        candidate_id = new_id("cand")
        c.execute(
            "INSERT INTO dedup_candidates (candidate_id, occurrence_a, occurrence_b, kind,"
            " reasons_json, score, rule_version, state, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                candidate_id, p["survivor"], p["absorbed"][0] if p["absorbed"] else p["survivor"],
                "exact", json.dumps(p["reasons"]), None, p["rule_version"], "merged",
                event["occurred_at"],
            ),
        )
        for occ_id in p["absorbed"]:
            c.execute("UPDATE occurrences SET is_active = 0, duplicate_of = ? WHERE occurrence_id = ?", (p["survivor"], occ_id))
            c.execute(
                "INSERT INTO duplicate_merges (merge_id, absorbed_occurrence, canonical_occurrence,"
                " classification, merge_kind, candidate_id, actor, merged_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    new_id("merge"), occ_id, p["survivor"], p["classifications"][occ_id],
                    "exact", candidate_id, event["actor"], event["occurred_at"],
                ),
            )

    db.append_event(conn, "dedup.exact_merge", actor, payload, apply_fn=apply_fn)


def _create_fuzzy_candidate(conn, occ_a: str, occ_b: str, score: float, reasons: list[str]) -> str:
    candidate_id = new_id("cand")
    payload = {
        "candidate_id": candidate_id,
        "occurrence_a": occ_a,
        "occurrence_b": occ_b,
        "score": score,
        "reasons": reasons,
        "rule_version": RULE_VERSION,
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO dedup_candidates (candidate_id, occurrence_a, occurrence_b, kind,"
            " reasons_json, score, rule_version, state, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                p["candidate_id"], p["occurrence_a"], p["occurrence_b"], "fuzzy",
                json.dumps(p["reasons"]), p["score"], p["rule_version"], "open",
                event["occurred_at"],
            ),
        )

    db.append_event(conn, "dedup.fuzzy_candidate_created", "system", payload, apply_fn=apply_fn)
    return candidate_id


def reviewer_merge(conn, actor: str, candidate_id: str, survivor: str, absorbed: list[str]) -> None:
    """Reviewer-confirmed merge of a fuzzy candidate (spec §4.2 Merge)."""
    cand = conn.execute("SELECT * FROM dedup_candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
    if cand is None:
        raise ValueError(f"unknown candidate: {candidate_id}")
    if cand["state"] != "open":
        raise ValueError(f"candidate {candidate_id} is not open (state={cand['state']})")
    valid_members = {cand["occurrence_a"], cand["occurrence_b"]}
    if survivor not in valid_members or not set(absorbed).issubset(valid_members):
        raise ValueError("merge members must belong to the candidate link")

    classifications = {occ_id: _classify_absorbed_row(conn, occ_id) for occ_id in absorbed}
    payload = {
        "candidate_id": candidate_id,
        "survivor": survivor,
        "absorbed": absorbed,
        "classifications": classifications,
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute("UPDATE dedup_candidates SET state = 'merged' WHERE candidate_id = ?", (p["candidate_id"],))
        for occ_id in p["absorbed"]:
            c.execute("UPDATE occurrences SET is_active = 0, duplicate_of = ? WHERE occurrence_id = ?", (p["survivor"], occ_id))
            c.execute(
                "INSERT INTO duplicate_merges (merge_id, absorbed_occurrence, canonical_occurrence,"
                " classification, merge_kind, candidate_id, actor, merged_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    new_id("merge"), occ_id, p["survivor"], p["classifications"][occ_id],
                    "reviewer", p["candidate_id"], event["actor"], event["occurred_at"],
                ),
            )

    db.append_event(conn, "dedup.reviewer_merge", actor, payload, apply_fn=apply_fn)


def reviewer_keep_separate(conn, actor: str, candidate_id: str) -> None:
    """Mark a fuzzy candidate pair as reviewer-confirmed non-duplicate."""
    cand = conn.execute("SELECT * FROM dedup_candidates WHERE candidate_id = ?", (candidate_id,)).fetchone()
    if cand is None:
        raise ValueError(f"unknown candidate: {candidate_id}")
    if cand["state"] != "open":
        raise ValueError(f"candidate {candidate_id} is not open (state={cand['state']})")

    payload = {"candidate_id": candidate_id}

    def apply_fn(c, event):
        c.execute(
            "UPDATE dedup_candidates SET state = 'kept_separate' WHERE candidate_id = ?",
            (event["payload"]["candidate_id"],),
        )

    db.append_event(conn, "dedup.keep_separate", actor, payload, apply_fn=apply_fn)


def undo_merge(conn, actor: str, merge_id: str, reason: str | None = None) -> None:
    """Reverse one merge (exact or reviewer), restoring the absorbed
    occurrence to active status. Does not delete the original merge
    event/row; appends a linked undo event (spec §4.3).
    """
    merge = conn.execute("SELECT * FROM duplicate_merges WHERE merge_id = ?", (merge_id,)).fetchone()
    if merge is None:
        raise ValueError(f"unknown merge: {merge_id}")
    if merge["undone_at"] is not None:
        raise ValueError(f"merge {merge_id} already undone")

    payload = {
        "merge_id": merge_id,
        "absorbed_occurrence": merge["absorbed_occurrence"],
        "reason": reason,
    }

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "UPDATE occurrences SET is_active = 1, duplicate_of = NULL WHERE occurrence_id = ?",
            (p["absorbed_occurrence"],),
        )
        c.execute(
            "UPDATE duplicate_merges SET undone_at = ? WHERE merge_id = ?",
            (event["occurred_at"], p["merge_id"]),
        )

    db.append_event(conn, "dedup.undo_merge", actor, payload, apply_fn=apply_fn)


def counts(conn) -> dict:
    """Derived dedup counts (spec §6): row-level, not group/event-level."""
    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active = 1").fetchone()["n"]
    pre_screen = conn.execute(
        "SELECT COUNT(*) AS n FROM duplicate_merges WHERE classification = 'pre_screen_removal' AND undone_at IS NULL"
    ).fetchone()["n"]
    post_screen = conn.execute(
        "SELECT COUNT(*) AS n FROM duplicate_merges WHERE classification = 'post_screen_correction' AND undone_at IS NULL"
    ).fetchone()["n"]
    open_fuzzy = conn.execute(
        "SELECT COUNT(*) AS n FROM dedup_candidates WHERE kind = 'fuzzy' AND state = 'open'"
    ).fetchone()["n"]
    return {
        "active_records": active,
        "duplicates_removed_before_screening": pre_screen,
        "duplicates_merged_after_screening": post_screen,
        "open_fuzzy_pairs": open_fuzzy,
    }


def list_open_fuzzy_candidates(conn) -> list[dict]:
    """Open fuzzy candidates with both occurrences' titles, for a UI
    review queue (spec §4.2)."""
    rows = conn.execute(
        "SELECT dc.candidate_id, dc.occurrence_a, dc.occurrence_b, dc.score, dc.reasons_json,"
        " fa.fields_json AS fields_a, fb.fields_json AS fields_b"
        " FROM dedup_candidates dc"
        " JOIN occurrence_fields fa ON fa.occurrence_id = dc.occurrence_a"
        " JOIN occurrence_fields fb ON fb.occurrence_id = dc.occurrence_b"
        " WHERE dc.kind = 'fuzzy' AND dc.state = 'open'"
        " ORDER BY dc.created_at ASC"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["fields_a"] = json.loads(d["fields_a"])
        d["fields_b"] = json.loads(d["fields_b"])
        d["reasons"] = json.loads(d["reasons_json"])
        out.append(d)
    return out


def list_open_fuzzy_clusters(conn) -> list[dict]:
    """Group open fuzzy candidates into connected components so a chain
    of pairwise matches (A~B, B~C) is reviewed and merged as one
    multi-way decision instead of two separate pairwise ones -- gap
    found during UI dogfooding: `reviewer_merge` only ever accepted a
    single pair, so a 3+ member duplicate group required resolving each
    pair one at a time and could leave the group in an inconsistent
    state (e.g. merge A-B, then B is gone when trying to resolve B-C).

    Each cluster dict: occurrence_ids (all members), members
    (occurrence_id -> fields dict), candidate_ids (every open candidate
    touching this cluster), pairs (the raw pairwise evidence, for
    display).
    """
    candidates = list_open_fuzzy_candidates(conn)
    if not candidates:
        return []

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for c in candidates:
        union(c["occurrence_a"], c["occurrence_b"])

    clusters: dict[str, dict] = {}
    for c in candidates:
        root = find(c["occurrence_a"])
        cluster = clusters.setdefault(root, {"candidate_ids": [], "members": {}, "pairs": []})
        cluster["candidate_ids"].append(c["candidate_id"])
        cluster["members"][c["occurrence_a"]] = c["fields_a"]
        cluster["members"][c["occurrence_b"]] = c["fields_b"]
        cluster["pairs"].append({
            "candidate_id": c["candidate_id"], "occurrence_a": c["occurrence_a"],
            "occurrence_b": c["occurrence_b"], "score": c["score"], "reasons": c["reasons"],
        })

    out = []
    for cluster in clusters.values():
        out.append({
            "occurrence_ids": list(cluster["members"].keys()),
            "members": cluster["members"],
            "candidate_ids": cluster["candidate_ids"],
            "pairs": cluster["pairs"],
        })
    return out


def reviewer_merge_group(
    conn,
    actor: str,
    candidate_ids: list[str],
    survivor: str,
    absorbed: list[str],
    *,
    resolution_note: str | None = None,
) -> None:
    """Reviewer-confirmed merge of an entire connected-component cluster
    of open fuzzy candidates at once (multi-way merge; spec §4.2,
    generalizing the pairwise `reviewer_merge`).

    ``survivor`` plus ``absorbed`` must exactly equal the union of
    occurrence ids referenced by ``candidate_ids`` -- a partial subset
    is rejected rather than silently merging only some members, since a
    cluster that's merged halfway would leave stale open candidates
    pointing at an occurrence that's no longer active. Optional
    ``resolution_note`` is preserved in the append-only merge event for
    auditable provenance of human/operator rationale.
    """
    if not candidate_ids:
        raise ValueError("candidate_ids must not be empty")
    rows = conn.execute(
        f"SELECT * FROM dedup_candidates WHERE candidate_id IN"
        f" ({','.join('?' for _ in candidate_ids)})",
        candidate_ids,
    ).fetchall()
    if len(rows) != len(candidate_ids):
        raise ValueError("one or more candidate_ids not found")

    member_ids: set[str] = set()
    for r in rows:
        if r["kind"] != "fuzzy":
            raise ValueError(f"candidate {r['candidate_id']} is not a fuzzy candidate")
        if r["state"] != "open":
            raise ValueError(f"candidate {r['candidate_id']} is not open (state={r['state']})")
        member_ids.add(r["occurrence_a"])
        member_ids.add(r["occurrence_b"])

    if set([survivor, *absorbed]) != member_ids:
        raise ValueError("survivor + absorbed must exactly match the cluster's occurrence set")

    classifications = {occ_id: _classify_absorbed_row(conn, occ_id) for occ_id in absorbed}
    payload = {
        "candidate_ids": candidate_ids,
        "survivor": survivor,
        "absorbed": absorbed,
        "classifications": classifications,
    }
    if resolution_note:
        payload["resolution_note"] = resolution_note

    def apply_fn(c, event):
        p = event["payload"]
        for cid in p["candidate_ids"]:
            c.execute("UPDATE dedup_candidates SET state = 'merged' WHERE candidate_id = ?", (cid,))
        for occ_id in p["absorbed"]:
            c.execute(
                "UPDATE occurrences SET is_active = 0, duplicate_of = ? WHERE occurrence_id = ?",
                (p["survivor"], occ_id),
            )
            c.execute(
                "INSERT INTO duplicate_merges (merge_id, absorbed_occurrence, canonical_occurrence,"
                " classification, merge_kind, candidate_id, actor, merged_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    new_id("merge"), occ_id, p["survivor"], p["classifications"][occ_id],
                    "reviewer", p["candidate_ids"][0], event["actor"], event["occurred_at"],
                ),
            )

    db.append_event(conn, "dedup.reviewer_merge_group", actor, payload, apply_fn=apply_fn)


def reviewer_keep_separate_group(conn, actor: str, candidate_ids: list[str]) -> None:
    """Mark every pairwise candidate in a cluster as kept-separate at
    once (the group-level counterpart to `reviewer_keep_separate`)."""
    for candidate_id in candidate_ids:
        reviewer_keep_separate(conn, actor, candidate_id)

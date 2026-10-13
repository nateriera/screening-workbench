import json

from screening_workbench import db, dedup
from screening_workbench.importers.csv_importer import commit_csv_import


def _seed_source(conn, source_id="src1", branch_id="branchA", cls="database"):
    conn.execute(
        "INSERT INTO branches (branch_id, name, created_at) VALUES (?, ?, datetime('now'))",
        (branch_id, branch_id),
    )
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES (?, ?, ?, ?, datetime('now'))",
        (source_id, source_id, cls, branch_id),
    )
    conn.commit()
    return source_id, branch_id


def _import(conn, rows_csv, source_id, branch_id, op_id):
    header = "title,authors,year,doi\n"
    mapping = {0: "title", 1: "authors", 2: "year", 3: "doi"}
    return commit_csv_import(
        conn, header + rows_csv, mapping, source_id=source_id, branch_id=branch_id,
        operation_id=op_id, actor="owner",
    )


def _occ_ids(conn, batch_id):
    return [r["occurrence_id"] for r in conn.execute(
        "SELECT occurrence_id FROM occurrences WHERE batch_id = ? ORDER BY locator", (batch_id,)
    ).fetchall()]


# Exact DOI match (case/resolver-prefix differences) -> silent merge,
# as long as titles agree (amended 2026-10-07; see
# test_doi_match_title_mismatch_routes_to_review below for the other half).
def test_exact_doi_merge_case_and_resolver_prefix(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(
        conn,
        'Same Paper Title,Smith,2020,https://doi.org/10.1/ABC\n'
        'Same Paper Title,Jones,2020,doi:10.1/abc\n',
        source_id, branch_id, "op1",
    )
    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.exact_merges == 1
    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 1
    conn.close()


# DOI match with materially different (or missing) titles must NOT
# silently merge -- dogfood run 2026-10-07 found real DOI collisions
# between unrelated papers (shared-DOI metadata errors in the source
# data) and the old rule silently merged them. Now it must route to the
# manual-review (fuzzy) queue instead, tagged with a distinct reason so
# a reviewer knows it's a DOI conflict, not an ordinary near-duplicate.
def test_doi_match_title_mismatch_routes_to_review(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(
        conn,
        'Totally Different Paper One,Smith,2020,10.1/xyz\n'
        'Completely Unrelated Paper Two,Jones,2021,10.1/xyz\n',
        source_id, branch_id, "op1",
    )
    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.exact_merges == 0
    assert result.doi_conflict_candidates_created == 1
    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 2  # neither side auto-merged

    candidates = dedup.list_open_fuzzy_candidates(conn)
    assert len(candidates) == 1
    assert candidates[0]["reasons"] == ["doi_match_title_mismatch"]
    conn.close()


# DOI match where one side has no title at all must also route to
# review, not auto-merge -- an empty title can trivially "agree" with
# nothing, so it must never be treated as a confirmed match.
def test_doi_match_missing_title_routes_to_review(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(
        conn,
        'Has A Real Title,Smith,2020,10.1/missing-title\n'
        ',Jones,2021,10.1/missing-title\n',
        source_id, branch_id, "op1",
    )
    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.exact_merges == 0
    assert result.doi_conflict_candidates_created == 1
    conn.close()


# Exact title+year match (no DOI) -> silent merge.
def test_exact_title_year_merge():
    pass  # covered by DB-backed variant below


def test_exact_title_year_merge_db(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(
        conn,
        'The Impact of COVID: A Review,Smith,2020,\n'
        'the impact of covid a review,Jones,2020,\n',
        source_id, branch_id, "op1",
    )
    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.exact_merges == 1
    conn.close()


# No year -> no exact title match, no fuzzy candidate either.
def test_identical_title_no_year_no_merge_no_candidate(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(conn, 'Same Title,Smith,,\nSame Title,Smith,,\n', source_id, branch_id, "op1")
    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.exact_merges == 0
    assert result.fuzzy_candidates_created == 0
    conn.close()


# Fuzzy: same first author/year, score >= 0.90 -> candidate, not auto-merge.
def test_fuzzy_candidate_created_above_threshold(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    title_a = "a" * 100
    title_b = "a" * 90 + "b" * 10  # similarity exactly 0.90
    r = _import(conn, f'{title_a},Smith,2020,\n{title_b},Smith,2020,\n', source_id, branch_id, "op1")
    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.exact_merges == 0
    assert result.fuzzy_candidates_created == 1
    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 2  # fuzzy candidates never auto-remove
    conn.close()


def test_fuzzy_candidate_below_threshold_no_candidate(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    title_a = "a" * 100
    title_b = "a" * 80 + "b" * 20  # similarity 0.80, below threshold
    r = _import(conn, f'{title_a},Smith,2020,\n{title_b},Smith,2020,\n', source_id, branch_id, "op1")
    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.fuzzy_candidates_created == 0
    conn.close()


def test_fuzzy_candidate_different_first_author_no_candidate(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    title_a = "a" * 100
    title_b = "a" * 90 + "b" * 10
    r = _import(conn, f'{title_a},Smith,2020,\n{title_b},Jones,2020,\n', source_id, branch_id, "op1")
    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.fuzzy_candidates_created == 0
    conn.close()


# Mixed-group row-level classification: one voted + one unscreened absorbed
# row -> one pre-screen removal AND one post-screen correction (not either/or).
def test_mixed_group_classification_vote_preserved(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(
        conn,
        'Exact Match Title,Smith,2020,10.1/same\n'   # x1 - will get a vote
        'Exact Match Title,Smith,2020,10.1/same\n'   # x2 - no vote
        'Exact Match Title,Smith,2020,10.1/same\n',  # x3 - no vote
        source_id, branch_id, "op1",
    )
    ids = _occ_ids(conn, r.batch_id)
    x1, x2, x3 = ids
    # All three share the same created_at (same import transaction), so
    # the deterministic survivor is the lexicographically smallest ID.
    # Vote on one of the two occurrences that will actually be absorbed,
    # leaving the other absorbed occurrence unvoted -- exercising both
    # classification branches within one merge.
    survivor_id = sorted(ids)[0]
    absorbed_ids = [i for i in ids if i != survivor_id]
    voted_absorbed, unvoted_absorbed = absorbed_ids[0], absorbed_ids[1]

    conn.execute(
        "INSERT INTO screen_votes (vote_id, occurrence_id, stage, reviewer_id, decision, created_at)"
        " VALUES ('v1', ?, 'title_abstract', 'rev1', 'include', datetime('now'))",
        (voted_absorbed,),
    )
    conn.commit()

    result = dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    assert result.exact_merges == 2  # two absorbed into one survivor

    classifications = {
        row["absorbed_occurrence"]: row["classification"]
        for row in conn.execute("SELECT absorbed_occurrence, classification FROM duplicate_merges").fetchall()
    }
    assert classifications[voted_absorbed] == "post_screen_correction"
    assert classifications[unvoted_absorbed] == "pre_screen_removal"

    counts = dedup.counts(conn)
    assert counts["duplicates_removed_before_screening"] == 1
    assert counts["duplicates_merged_after_screening"] == 1
    conn.close()


def test_survivor_is_oldest_then_lexicographically_smallest_id(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(conn, 'T,Smith,2020,10.1/x\nT,Smith,2020,10.1/x\n', source_id, branch_id, "op1")
    ids = _occ_ids(conn, r.batch_id)
    dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    survivor_row = conn.execute("SELECT occurrence_id FROM occurrences WHERE is_active = 1").fetchone()
    # Both created in the same batch/transaction (same timestamp), so the
    # tie-break is the lexicographically smallest ID.
    assert survivor_row["occurrence_id"] == sorted(ids)[0]
    conn.close()


# Reviewer merge/keep-separate on a fuzzy candidate.
def test_reviewer_merge_and_keep_separate(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    title_a = "a" * 100
    title_b = "a" * 90 + "b" * 10
    r = _import(conn, f'{title_a},Smith,2020,\n{title_b},Smith,2020,\n', source_id, branch_id, "op1")
    dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    cand = conn.execute("SELECT * FROM dedup_candidates WHERE kind='fuzzy'").fetchone()
    ids = _occ_ids(conn, r.batch_id)

    dedup.reviewer_merge(conn, "owner", cand["candidate_id"], survivor=ids[0], absorbed=[ids[1]])
    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 1
    state = conn.execute("SELECT state FROM dedup_candidates WHERE candidate_id=?", (cand["candidate_id"],)).fetchone()["state"]
    assert state == "merged"
    conn.close()


def test_keep_separate_leaves_both_active(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    title_a = "a" * 100
    title_b = "a" * 90 + "b" * 10
    r = _import(conn, f'{title_a},Smith,2020,\n{title_b},Smith,2020,\n', source_id, branch_id, "op1")
    dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    cand = conn.execute("SELECT * FROM dedup_candidates WHERE kind='fuzzy'").fetchone()
    dedup.reviewer_keep_separate(conn, "owner", cand["candidate_id"])
    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 2
    state = conn.execute("SELECT state FROM dedup_candidates WHERE candidate_id=?", (cand["candidate_id"],)).fetchone()["state"]
    assert state == "kept_separate"
    conn.close()


# Undo restores exact pre-merge state without deleting the merge event.
def test_undo_merge_restores_active_state(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(conn, 'T,Smith,2020,10.1/x\nT,Smith,2020,10.1/x\n', source_id, branch_id, "op1")
    dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    merge = conn.execute("SELECT * FROM duplicate_merges").fetchone()
    dedup.undo_merge(conn, "owner", merge["merge_id"], reason="mistaken merge")
    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 2
    # Merge row itself is retained with undone_at set, not deleted.
    row = conn.execute("SELECT undone_at FROM duplicate_merges WHERE merge_id=?", (merge["merge_id"],)).fetchone()
    assert row["undone_at"] is not None
    conn.close()


def test_replay_reproduces_same_dedup_state(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    r = _import(conn, 'T,Smith,2020,10.1/x\nT,Smith,2020,10.1/x\n', source_id, branch_id, "op1")
    dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    events_before = db.all_events(conn)
    counts_before = dedup.counts(conn)

    # Rebuild a fresh DB and replay the exact same event sequence manually
    # by re-running the same operations (acts as a behavioral replay proxy
    # since this version does not yet implement a generic event replayer).
    conn2 = db.connect(tmp_path / "t2.db")
    source_id2, branch_id2 = _seed_source(conn2)
    r2 = _import(conn2, 'T,Smith,2020,10.1/x\nT,Smith,2020,10.1/x\n', source_id2, branch_id2, "op1")
    dedup.run_exact_and_fuzzy_detection(conn2, "system", batch_id=r2.batch_id)
    counts_after = dedup.counts(conn2)
    assert counts_before == counts_after
    conn.close()
    conn2.close()


# --- Multi-way (3+ member) fuzzy cluster merge UI support ---
# Found during UI dogfooding: `reviewer_merge` only ever accepted a
# single pair, so a genuine 3+ member duplicate group required
# resolving pairs one at a time and could leave the group half-merged.

def _three_way_fuzzy_cluster(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    base = "a" * 96
    r = _import(
        conn,
        f"{base}TAG1,Smith,2020,\n{base}TAG2,Smith,2020,\n{base}TAG3,Smith,2020,\n",
        source_id, branch_id, "op1",
    )
    dedup.run_exact_and_fuzzy_detection(conn, "system", batch_id=r.batch_id)
    occ_ids = _occ_ids(conn, r.batch_id)
    return conn, occ_ids


def test_list_open_fuzzy_clusters_groups_triangle_into_one_cluster(tmp_path):
    conn, occ_ids = _three_way_fuzzy_cluster(tmp_path)
    clusters = dedup.list_open_fuzzy_clusters(conn)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert set(cluster["occurrence_ids"]) == set(occ_ids)
    assert len(cluster["candidate_ids"]) == 3  # all 3 pairwise edges
    conn.close()


def test_reviewer_merge_group_merges_all_three_at_once(tmp_path):
    conn, occ_ids = _three_way_fuzzy_cluster(tmp_path)
    cluster = dedup.list_open_fuzzy_clusters(conn)[0]
    survivor = occ_ids[0]
    absorbed = [occ_ids[1], occ_ids[2]]

    note = "Record B CSV verdict=exclude, tag=2; Record A tag=4 retained."
    dedup.reviewer_merge_group(
        conn, "dogfood-operator", cluster["candidate_ids"], survivor, absorbed,
        resolution_note=note,
    )

    event = conn.execute(
        "SELECT actor, payload_json FROM events WHERE event_type='dedup.reviewer_merge_group'"
    ).fetchone()
    assert event["actor"] == "dogfood-operator"
    assert json.loads(event["payload_json"])["resolution_note"] == note

    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 1
    merged_states = conn.execute(
        "SELECT state FROM dedup_candidates WHERE candidate_id IN"
        f" ({','.join('?' for _ in cluster['candidate_ids'])})",
        cluster["candidate_ids"],
    ).fetchall()
    assert all(s["state"] == "merged" for s in merged_states)
    assert dedup.list_open_fuzzy_clusters(conn) == []
    conn.close()


def test_reviewer_merge_group_rejects_partial_member_set(tmp_path):
    conn, occ_ids = _three_way_fuzzy_cluster(tmp_path)
    cluster = dedup.list_open_fuzzy_clusters(conn)[0]
    import pytest

    with pytest.raises(ValueError):
        # Omits occ_ids[2] -- survivor+absorbed don't cover the cluster.
        dedup.reviewer_merge_group(conn, "owner", cluster["candidate_ids"], occ_ids[0], [occ_ids[1]])
    conn.close()


def test_reviewer_keep_separate_group_clears_whole_cluster(tmp_path):
    conn, occ_ids = _three_way_fuzzy_cluster(tmp_path)
    cluster = dedup.list_open_fuzzy_clusters(conn)[0]

    dedup.reviewer_keep_separate_group(conn, "owner", cluster["candidate_ids"])

    assert dedup.list_open_fuzzy_clusters(conn) == []
    active = conn.execute("SELECT COUNT(*) AS n FROM occurrences WHERE is_active=1").fetchone()["n"]
    assert active == 3  # nothing merged
    conn.close()

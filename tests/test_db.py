import json
import sqlite3

import pytest

from screening_workbench import db


def test_migrate_creates_tables(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "events" in tables
    assert "occurrences" in tables
    assert "operations" in tables
    conn.close()


def test_migrate_is_idempotent(tmp_path):
    path = tmp_path / "test.db"
    conn1 = db.connect(path)
    conn1.close()
    conn2 = db.connect(path)  # re-opening/re-migrating must not error
    version = conn2.execute("PRAGMA user_version").fetchone()[0]
    assert version == db.SCHEMA_VERSION
    conn2.close()


# Directive C: migration 008 widens report_retrievals.full_text_outcome's
# CHECK to accept 'maybe'. SQLite cannot alter a CHECK in place, so this
# rebuilds the table -- must apply cleanly on a fresh DB and preserve
# every pre-existing row's values on an upgraded one.
def test_migration_008_applies_on_fresh_db(tmp_path):
    conn = db.connect(tmp_path / "fresh.db")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == db.SCHEMA_VERSION
    assert version >= 8
    # The new CHECK accepts 'maybe' on a brand-new database.
    conn.execute(
        "INSERT INTO reports (report_id, created_at) VALUES ('r1', datetime('now'))"
    )
    conn.execute(
        "INSERT INTO report_retrievals (report_id, retrieval_status, full_text_outcome, actor, updated_at)"
        " VALUES ('r1', 'retrieved', 'maybe', 'owner', datetime('now'))"
    )
    conn.commit()
    row = conn.execute(
        "SELECT full_text_outcome FROM report_retrievals WHERE report_id='r1'"
    ).fetchone()
    assert row["full_text_outcome"] == "maybe"
    conn.close()


def test_migration_008_preserves_existing_data_and_enforces_new_check(tmp_path):
    path = tmp_path / "pre_008.db"
    # Build a version-7 database by hand (migrations 1-7 only), insert
    # rows under the OLD CHECK (included/excluded/NULL only -- 'maybe'
    # would be rejected here), then let db.connect() run migration 008.
    raw = sqlite3.connect(str(path))
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    db._migration_001_initial(raw)
    db._migration_002_dedup_and_screening(raw)
    db._migration_003_reports(raw)
    db._migration_004_studies(raw)
    db._migration_005_roles(raw)
    db._migration_006_project_metadata(raw)
    db._migration_007_packets(raw)
    raw.execute("PRAGMA user_version = 7")
    raw.commit()

    for rid, status, outcome, reason in [
        ("r-included", "retrieved", "included", None),
        ("r-excluded", "retrieved", "excluded", "reason-X"),
        ("r-pending", "pending", None, None),
    ]:
        raw.execute("INSERT INTO reports (report_id, created_at) VALUES (?, datetime('now'))", (rid,))
        raw.execute(
            "INSERT INTO report_retrievals (report_id, retrieval_status, full_text_outcome, exclusion_reason, actor, updated_at)"
            " VALUES (?, ?, ?, ?, 'owner', datetime('now'))",
            (rid, status, outcome, reason),
        )
    raw.commit()
    # Confirm the old CHECK really is in effect before migrating -- a
    # 'maybe' insert must fail under the version-7 schema.
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute(
            "INSERT INTO report_retrievals (report_id, retrieval_status, full_text_outcome, actor, updated_at)"
            " VALUES ('r-maybe-rejected', 'retrieved', 'maybe', 'owner', datetime('now'))"
        )
    raw.rollback()
    raw.close()

    conn = db.connect(path)  # triggers migration 008 on open
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == db.SCHEMA_VERSION

    rows = {
        r["report_id"]: dict(r)
        for r in conn.execute("SELECT * FROM report_retrievals").fetchall()
    }
    assert rows["r-included"]["full_text_outcome"] == "included"
    assert rows["r-excluded"]["full_text_outcome"] == "excluded"
    assert rows["r-excluded"]["exclusion_reason"] == "reason-X"
    assert rows["r-pending"]["retrieval_status"] == "pending"
    assert rows["r-pending"]["full_text_outcome"] is None

    # The new CHECK now accepts 'maybe'.
    conn.execute("INSERT INTO reports (report_id, created_at) VALUES ('r-maybe', datetime('now'))")
    conn.execute(
        "INSERT INTO report_retrievals (report_id, retrieval_status, full_text_outcome, actor, updated_at)"
        " VALUES ('r-maybe', 'retrieved', 'maybe', 'owner', datetime('now'))"
    )
    conn.commit()
    row = conn.execute(
        "SELECT full_text_outcome FROM report_retrievals WHERE report_id='r-maybe'"
    ).fetchone()
    assert row["full_text_outcome"] == "maybe"
    conn.close()


# Directive D: migration 009 adds report_attachments. A fresh DB has
# the table, empty, and SCHEMA_VERSION reaches 9.
def test_migration_009_applies_on_fresh_db(tmp_path):
    conn = db.connect(tmp_path / "fresh9.db")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == db.SCHEMA_VERSION
    assert version >= 9
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "report_attachments" in tables
    rows = conn.execute("SELECT * FROM report_attachments").fetchall()
    assert rows == []
    conn.close()


def test_migration_009_upgrades_from_v8_db_preserving_reports(tmp_path):
    path = tmp_path / "pre_009.db"
    raw = sqlite3.connect(str(path))
    raw.row_factory = sqlite3.Row
    raw.execute("PRAGMA foreign_keys = ON")
    db._migration_001_initial(raw)
    db._migration_002_dedup_and_screening(raw)
    db._migration_003_reports(raw)
    db._migration_004_studies(raw)
    db._migration_005_roles(raw)
    db._migration_006_project_metadata(raw)
    db._migration_007_packets(raw)
    db._migration_008_fulltext_maybe(raw)
    raw.execute("PRAGMA user_version = 8")
    raw.execute("INSERT INTO reports (report_id, created_at) VALUES ('r1', datetime('now'))")
    raw.commit()
    raw.close()

    conn = db.connect(path)  # triggers migration 009 on open
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert version == db.SCHEMA_VERSION

    # Existing report untouched.
    row = conn.execute("SELECT report_id FROM reports WHERE report_id='r1'").fetchone()
    assert row["report_id"] == "r1"

    # New table present and empty.
    tables = {
        r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "report_attachments" in tables
    assert conn.execute("SELECT COUNT(*) AS n FROM report_attachments").fetchone()["n"] == 0
    conn.close()


def test_append_event_records_and_applies(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    applied = []

    def apply_fn(c, event):
        applied.append(event["event_type"])

    event = db.append_event(
        conn, "demo.created", "owner", {"x": 1}, apply_fn=apply_fn
    )
    assert applied == ["demo.created"]
    rows = db.all_events(conn)
    assert len(rows) == 1
    assert rows[0]["event_id"] == event["event_id"]
    assert json.loads(rows[0]["payload_json"]) == {"x": 1}
    conn.close()


def test_append_event_rolls_back_on_apply_failure(tmp_path):
    conn = db.connect(tmp_path / "test.db")

    def failing_apply(c, event):
        raise RuntimeError("boom")

    try:
        db.append_event(conn, "demo.created", "owner", {}, apply_fn=failing_apply)
    except RuntimeError:
        pass
    # The event insert must have rolled back along with the failed apply.
    assert db.all_events(conn) == []
    conn.close()


def test_operation_idempotency_ledger(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    assert db.begin_or_get_operation(conn, "op-1", "import") is None
    db.commit_operation(conn, "op-1", "import", {"batch_id": "b1"})
    result = db.begin_or_get_operation(conn, "op-1", "import")
    assert result == {"batch_id": "b1"}
    conn.close()


def test_events_are_sequence_ordered(tmp_path):
    conn = db.connect(tmp_path / "test.db")
    for i in range(5):
        db.append_event(conn, "x", "owner", {"i": i}, apply_fn=lambda c, e: None)
    rows = db.all_events(conn)
    sequences = [r["sequence"] for r in rows]
    assert sequences == sorted(sequences)
    conn.close()

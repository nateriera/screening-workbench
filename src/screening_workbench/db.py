"""SQLite storage layer: schema migrations and the append-only event log.

Architecture (see docs/specs/behavioral-spec-prisma-counts-export.md §3.4.8
"Empty-log replay reconstructs occurrences, votes, dispositions, progression,
reports, studies, links, counts, and snapshots." and
behavioral-spec-duplicate-detection.md §5 "Replaying the same committed event
stream from its initial state produces the same current duplicate
relationships and PRISMA counts."):

Every state-changing action in Screening Workbench is appended to the ``events`` table
(never updated or deleted) and then applied to materialized "projection"
tables that represent current state. **A generic ``replay_all`` that wipes
and reconstructs every projection from an empty database is not implemented
in v1.** Event append/apply paths and undo are tested individually, but the
specs' full empty-log replay requirements remain a known product gap.

All storage is local SQLite; no network access occurs anywhere in this
module (local-first requirement, screening-workflow spec §8).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from screening_workbench.ids import new_id, now_rfc3339

SCHEMA_VERSION = 9


def connect(path: str | Path) -> sqlite3.Connection:
    """Open (and if needed, initialize) a Screening Workbench project database file."""
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    """Apply schema migrations up to SCHEMA_VERSION, idempotently."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current < 1:
        _migration_001_initial(conn)
        current = 1
    if current < 2:
        _migration_002_dedup_and_screening(conn)
        current = 2
    if current < 3:
        _migration_003_reports(conn)
        current = 3
    if current < 4:
        _migration_004_studies(conn)
        current = 4
    if current < 5:
        _migration_005_roles(conn)
        current = 5
    if current < 6:
        _migration_006_project_metadata(conn)
        current = 6
    if current < 7:
        _migration_007_packets(conn)
        current = 7
    if current < 8:
        _migration_008_fulltext_maybe(conn)
        current = 8
    if current < 9:
        _migration_009_attachments(conn)
        current = 9
    conn.execute(f"PRAGMA user_version = {current}")
    conn.commit()


def _migration_001_initial(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        -- Append-only event log. `sequence` is the authoritative replay
        -- order (SQLite ROWID-backed autoincrement). Events are never
        -- updated or deleted by application code.
        CREATE TABLE IF NOT EXISTS events (
            sequence       INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id       TEXT NOT NULL UNIQUE,
            event_type     TEXT NOT NULL,
            occurred_at    TEXT NOT NULL,
            actor          TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            payload_json   TEXT NOT NULL
        );

        -- Idempotency ledger for retried-but-uncommitted operations
        -- (import-field-mapping spec §2.2, PRISMA spec §2.1.1): a retry of
        -- the same operation_id commits at most once.
        CREATE TABLE IF NOT EXISTS operations (
            operation_id TEXT PRIMARY KEY,
            kind         TEXT NOT NULL,
            committed_at TEXT NOT NULL,
            result_json  TEXT NOT NULL
        );

        -- ---- Projections (rebuilt from events by replay_all) ----

        CREATE TABLE IF NOT EXISTS sources (
            source_id  TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            class      TEXT NOT NULL CHECK (class IN ('database','register','other_method')),
            branch_id  TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS branches (
            branch_id  TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS import_batches (
            batch_id        TEXT PRIMARY KEY,
            operation_id    TEXT NOT NULL,
            source_id       TEXT NOT NULL REFERENCES sources(source_id),
            branch_id       TEXT NOT NULL REFERENCES branches(branch_id),
            source_format   TEXT NOT NULL CHECK (source_format IN ('csv','ris','pubmed_xml')),
            source_name     TEXT NOT NULL,
            mapping_json    TEXT NOT NULL,
            mapping_version INTEGER NOT NULL,
            imported_at     TEXT NOT NULL,
            records_read    INTEGER NOT NULL,
            records_skipped INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS import_skips (
            skip_id      TEXT PRIMARY KEY,
            batch_id     TEXT NOT NULL REFERENCES import_batches(batch_id),
            locator      TEXT NOT NULL,
            reason       TEXT NOT NULL
        );

        -- One row per bibliographic source-occurrence record. Immutable
        -- once created; never hard-deleted (dedup spec §5 `Record`).
        CREATE TABLE IF NOT EXISTS occurrences (
            occurrence_id    TEXT PRIMARY KEY,
            batch_id         TEXT NOT NULL REFERENCES import_batches(batch_id),
            source_id        TEXT NOT NULL REFERENCES sources(source_id),
            branch_id        TEXT NOT NULL REFERENCES branches(branch_id),
            locator          TEXT NOT NULL,
            raw_source_text  TEXT NOT NULL,
            created_at       TEXT NOT NULL,
            -- Duplicate-group state (dedup spec §5 `Record`):
            is_active        INTEGER NOT NULL DEFAULT 1,
            duplicate_of     TEXT REFERENCES occurrences(occurrence_id)
        );

        -- Canonical field values per occurrence (import-field-mapping §2.1).
        -- Stored as one JSON blob per occurrence for v1 simplicity; every
        -- canonical field is always present (possibly empty string / empty
        -- list), per the spec's "even if their values are empty" rule.
        CREATE TABLE IF NOT EXISTS occurrence_fields (
            occurrence_id TEXT PRIMARY KEY REFERENCES occurrences(occurrence_id),
            fields_json   TEXT NOT NULL,
            normalized_json TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_occurrences_batch ON occurrences(batch_id);
        CREATE INDEX IF NOT EXISTS idx_occurrences_active ON occurrences(is_active);
        """
    )


def _migration_002_dedup_and_screening(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        -- Fuzzy/exact candidate pairs (dedup spec §5 `DedupCandidate`).
        -- Exact groups are applied immediately and recorded here with
        -- state='merged' for audit visibility; fuzzy pairs start 'open'.
        CREATE TABLE IF NOT EXISTS dedup_candidates (
            candidate_id    TEXT PRIMARY KEY,
            occurrence_a    TEXT NOT NULL REFERENCES occurrences(occurrence_id),
            occurrence_b    TEXT NOT NULL REFERENCES occurrences(occurrence_id),
            kind            TEXT NOT NULL CHECK (kind IN ('exact','fuzzy')),
            reasons_json    TEXT NOT NULL,
            score           REAL,
            rule_version    INTEGER NOT NULL,
            state           TEXT NOT NULL CHECK (state IN ('open','merged','kept_separate','stale')),
            created_at      TEXT NOT NULL
        );

        -- One row per absorbed occurrence per merge, carrying the
        -- pre-screen-removal vs. post-screen-correction classification
        -- (duplicate-detection spec §3.1.1 / §6; PRISMA spec §2.2.2).
        -- Row-level, never group/event-level, per the explicit ruling.
        CREATE TABLE IF NOT EXISTS duplicate_merges (
            merge_id              TEXT PRIMARY KEY,
            absorbed_occurrence   TEXT NOT NULL REFERENCES occurrences(occurrence_id),
            canonical_occurrence  TEXT NOT NULL REFERENCES occurrences(occurrence_id),
            classification        TEXT NOT NULL CHECK (classification IN ('pre_screen_removal','post_screen_correction')),
            merge_kind            TEXT NOT NULL CHECK (merge_kind IN ('exact','reviewer')),
            candidate_id          TEXT REFERENCES dedup_candidates(candidate_id),
            actor                 TEXT NOT NULL,
            merged_at             TEXT NOT NULL,
            undone_at             TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_dupmerge_absorbed ON duplicate_merges(absorbed_occurrence);
        CREATE INDEX IF NOT EXISTS idx_dupmerge_canonical ON duplicate_merges(canonical_occurrence);

        -- Title/abstract (and later full-text) screening votes, per
        -- occurrence/stage/reviewer (screening-workflow spec §4;
        -- PRISMA spec §2.2.4). `stage` v1 values: 'title_abstract'.
        CREATE TABLE IF NOT EXISTS screen_votes (
            vote_id       TEXT PRIMARY KEY,
            occurrence_id TEXT NOT NULL REFERENCES occurrences(occurrence_id),
            stage         TEXT NOT NULL CHECK (stage IN ('title_abstract')),
            reviewer_id   TEXT NOT NULL,
            decision      TEXT NOT NULL CHECK (decision IN ('include','maybe','exclude')),
            reason        TEXT,
            created_at    TEXT NOT NULL,
            superseded_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_votes_occurrence ON screen_votes(occurrence_id);
        CREATE INDEX IF NOT EXISTS idx_votes_reviewer ON screen_votes(reviewer_id);
        """
    )


def _migration_003_reports(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        -- A distinct bibliographic report selected to progress beyond
        -- screening (PRISMA spec §2.3/§4 `Report`). Never inferred from
        -- occurrences; created explicitly when a report is identified.
        CREATE TABLE IF NOT EXISTS reports (
            report_id  TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );

        -- Occurrence-to-report provenance (`RecordReport`). Many
        -- occurrences (including cross-branch duplicates) may link to
        -- one report; this table is never pruned on progression.
        CREATE TABLE IF NOT EXISTS record_reports (
            occurrence_id TEXT NOT NULL REFERENCES occurrences(occurrence_id),
            report_id     TEXT NOT NULL REFERENCES reports(report_id),
            created_at    TEXT NOT NULL,
            PRIMARY KEY (occurrence_id, report_id)
        );

        -- Exactly one progression per report: the selected canonical
        -- occurrence/branch that advances (PRISMA spec §2.3.1-2, §3.4.3:
        -- "Each distinct report has at most one progression/branch").
        CREATE TABLE IF NOT EXISTS report_progressions (
            report_id            TEXT PRIMARY KEY REFERENCES reports(report_id),
            canonical_occurrence TEXT NOT NULL REFERENCES occurrences(occurrence_id),
            branch_id            TEXT NOT NULL REFERENCES branches(branch_id),
            actor                TEXT NOT NULL,
            decided_at           TEXT NOT NULL
        );

        -- Retrieval attempt / full-text outcome, one terminal row per
        -- report (PRISMA spec §2.3.3-4, §3.2). `retrieval_status` is
        -- 'pending' until explicitly set to 'not_retrieved' or
        -- 'retrieved'; `full_text_outcome` is only set once retrieved.
        CREATE TABLE IF NOT EXISTS report_retrievals (
            report_id        TEXT PRIMARY KEY REFERENCES reports(report_id),
            retrieval_status TEXT NOT NULL CHECK (retrieval_status IN ('pending','not_retrieved','retrieved')),
            full_text_outcome TEXT CHECK (full_text_outcome IN ('included','excluded')),
            exclusion_reason  TEXT,
            actor             TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );
        """
    )


def _migration_004_studies(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        -- Distinct, explicitly user-created `Study` (PRISMA spec §2.4.1-2).
        -- Never inferred from reports or bibliographic similarity.
        CREATE TABLE IF NOT EXISTS studies (
            study_id   TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        );

        -- Current study decision (one row per study, latest wins) plus
        -- full append-only history in study_decision_events below.
        CREATE TABLE IF NOT EXISTS study_decisions (
            study_id   TEXT PRIMARY KEY REFERENCES studies(study_id),
            decision   TEXT NOT NULL CHECK (decision IN ('included','excluded','unresolved')),
            rationale  TEXT NOT NULL,
            actor      TEXT NOT NULL,
            decided_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS study_decision_events (
            event_row_id TEXT PRIMARY KEY,
            study_id     TEXT NOT NULL REFERENCES studies(study_id),
            decision     TEXT NOT NULL CHECK (decision IN ('included','excluded','unresolved')),
            rationale    TEXT NOT NULL,
            actor        TEXT NOT NULL,
            occurred_at  TEXT NOT NULL
        );

        -- Current active report<->study links (many-to-many; a link alone
        -- never implies inclusion -- PRISMA spec §2.4.1,4). Full
        -- append-only link history lives in report_study_link_events so
        -- acceptance test 4's "four link-history rows, three active
        -- distinct pairs" scenario is representable.
        CREATE TABLE IF NOT EXISTS report_study_links (
            report_id TEXT NOT NULL REFERENCES reports(report_id),
            study_id  TEXT NOT NULL REFERENCES studies(study_id),
            PRIMARY KEY (report_id, study_id)
        );

        CREATE TABLE IF NOT EXISTS report_study_link_events (
            event_row_id TEXT PRIMARY KEY,
            report_id    TEXT NOT NULL REFERENCES reports(report_id),
            study_id     TEXT NOT NULL REFERENCES studies(study_id),
            action       TEXT NOT NULL CHECK (action IN ('add','remove')),
            actor        TEXT NOT NULL,
            occurred_at  TEXT NOT NULL,
            rationale    TEXT
        );
        """
    )


def _migration_005_roles(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        -- Project owner, fixed at creation (PRISMA spec §2.6.5). Single
        -- row, set exactly once via roles.set_owner.
        CREATE TABLE IF NOT EXISTS project_owner (
            owner_id   TEXT PRIMARY KEY,
            set_at     TEXT NOT NULL
        );

        -- Project-wide blind-mode flag (screening-workflow spec §1:
        -- "the blind toggle locks once screening begins and only the
        -- project owner can change it"). Single row, id fixed = 'project'.
        CREATE TABLE IF NOT EXISTS project_settings (
            id              TEXT PRIMARY KEY DEFAULT 'project',
            is_blind        INTEGER NOT NULL DEFAULT 0,
            screening_started INTEGER NOT NULL DEFAULT 0
        );

        -- Auditor-role grants/revocations (PRISMA spec §2.6.5): append-
        -- only history; current authorization = latest non-revoked grant
        -- per (target, scope).
        CREATE TABLE IF NOT EXISTS auditor_grant_events (
            grant_event_id TEXT PRIMARY KEY,
            target         TEXT NOT NULL,
            scope          TEXT NOT NULL CHECK (scope IN ('audit_read','full_export')),
            action         TEXT NOT NULL CHECK (action IN ('grant','revoke')),
            actor          TEXT NOT NULL,
            reason         TEXT NOT NULL,
            occurred_at    TEXT NOT NULL
        );
        """
    )


def _migration_006_project_metadata(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        -- Project name and review-type label (screening-workflow spec
        -- §1 setup step (a): "name the review"). Lives on the same
        -- single-row project_settings table as the blind-mode flag.
        ALTER TABLE project_settings ADD COLUMN name TEXT;
        ALTER TABLE project_settings ADD COLUMN review_type TEXT;
        """
    )


def _migration_007_packets(conn: sqlite3.Connection) -> None:
    """Directive B: two-computer blind review via reviewer packets.

    Widens ``import_batches.source_format`` to accept ``'packet'`` (a
    packet import is not a CSV/RIS/PubMed-XML import, but reuses the
    occurrence/batch projection shape) and adds the reviewer-identity
    lock plus a quarantine table for merged votes that reference an
    unknown occurrence_id (screening_workbench.packets module, "document, never
    silently drop" per the behavioral directive).

    SQLite CHECK constraints cannot be altered in place, so
    ``import_batches`` is rebuilt under FK enforcement temporarily
    disabled, then re-enabled -- this migration step only, not a
    standing relaxation of referential integrity elsewhere.
    """
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE import_batches_new (
            batch_id        TEXT PRIMARY KEY,
            operation_id    TEXT NOT NULL,
            source_id       TEXT NOT NULL REFERENCES sources(source_id),
            branch_id       TEXT NOT NULL REFERENCES branches(branch_id),
            source_format   TEXT NOT NULL CHECK (source_format IN ('csv','ris','pubmed_xml','packet')),
            source_name     TEXT NOT NULL,
            mapping_json    TEXT NOT NULL,
            mapping_version INTEGER NOT NULL,
            imported_at     TEXT NOT NULL,
            records_read    INTEGER NOT NULL,
            records_skipped INTEGER NOT NULL
        );
        INSERT INTO import_batches_new SELECT * FROM import_batches;
        DROP TABLE import_batches;
        ALTER TABLE import_batches_new RENAME TO import_batches;

        -- The reviewer identity a packet-imported database is
        -- permanently bound to (Directive B §2: "import binds to a
        -- locked reviewer identity"), and the packet_id that set it
        -- (a second `import_packet` call on this database is refused
        -- regardless of reviewer_id -- one packet per database).
        ALTER TABLE project_settings ADD COLUMN locked_reviewer_id TEXT;
        ALTER TABLE project_settings ADD COLUMN packet_imported_id TEXT;

        -- Votes from a merged votes file whose occurrence_id is not
        -- known to this database (foreign/tampered file, or a record
        -- dropped on the host side since the packet was cut). Never
        -- silently dropped: quarantined and visible for owner review
        -- (Directive B §7's documented choice: quarantine, not reject
        -- the whole merge, and not silently discard the individual row).
        CREATE TABLE IF NOT EXISTS quarantined_votes (
            quarantine_id     TEXT PRIMARY KEY,
            occurrence_id     TEXT NOT NULL,
            reviewer_id       TEXT NOT NULL,
            stage             TEXT NOT NULL,
            decision          TEXT,
            reason            TEXT,
            vote_created_at   TEXT,
            quarantine_reason TEXT NOT NULL,
            merge_event_id    TEXT NOT NULL,
            quarantined_at    TEXT NOT NULL
        );
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def _migration_008_fulltext_maybe(conn: sqlite3.Connection) -> None:
    """Directive C: full-text reference item 5 -- Include/Maybe/Exclude
    mechanics must match screening, with Maybe remaining pending (not
    terminal, not counted as included or excluded).

    Widens ``report_retrievals.full_text_outcome`` to accept ``'maybe'``
    alongside the existing ``'included'``/``'excluded'`` values; the
    column stays nullable (NULL = unassessed, unchanged). SQLite cannot
    alter a CHECK constraint in place, so the table is rebuilt under FK
    enforcement temporarily disabled (same approach as migration 007),
    preserving every existing row untouched.
    """
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript(
        """
        CREATE TABLE report_retrievals_new (
            report_id        TEXT PRIMARY KEY REFERENCES reports(report_id),
            retrieval_status TEXT NOT NULL CHECK (retrieval_status IN ('pending','not_retrieved','retrieved')),
            full_text_outcome TEXT CHECK (full_text_outcome IN ('included','excluded','maybe')),
            exclusion_reason  TEXT,
            actor             TEXT NOT NULL,
            updated_at        TEXT NOT NULL
        );
        INSERT INTO report_retrievals_new SELECT * FROM report_retrievals;
        DROP TABLE report_retrievals;
        ALTER TABLE report_retrievals_new RENAME TO report_retrievals;
        """
    )
    conn.execute("PRAGMA foreign_keys = ON")


def _migration_009_attachments(conn: sqlite3.Connection) -> None:
    """Directive D: PDF attachments for full-text records.

    Attachment metadata lives here; the file bytes themselves never do
    (screening_workbench.attachments module). ``UNIQUE(report_id, content_sha256)``
    means attaching the same bytes to the same report twice is one row,
    not two -- per-report dedup. The same bytes attached to two
    *different* reports are two rows (one per report) sharing one
    on-disk, content-addressed file.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS report_attachments (
            attachment_id  TEXT PRIMARY KEY,
            report_id      TEXT NOT NULL REFERENCES report_retrievals(report_id),
            filename       TEXT NOT NULL,
            content_sha256 TEXT NOT NULL,
            byte_size      INTEGER NOT NULL,
            mime_type      TEXT NOT NULL,
            uploaded_by    TEXT NOT NULL,
            uploaded_at    TEXT NOT NULL,
            UNIQUE (report_id, content_sha256)
        );

        CREATE INDEX IF NOT EXISTS idx_report_attachments_report
            ON report_attachments(report_id);
        """
    )


def append_event(
    conn: sqlite3.Connection,
    event_type: str,
    actor: str,
    payload: dict[str, Any],
    *,
    apply_fn,
    schema_version: int = 1,
) -> dict[str, Any]:
    """Append one event and apply it to projections, atomically.

    ``apply_fn(conn, event_row)`` performs the projection update for this
    event type. Both the insert and the projection update happen in the
    same transaction so projections never diverge from the log.
    """
    event = {
        "event_id": new_id("evt"),
        "event_type": event_type,
        "occurred_at": now_rfc3339(),
        "actor": actor,
        "schema_version": schema_version,
        "payload": payload,
    }
    with conn:
        conn.execute(
            "INSERT INTO events (event_id, event_type, occurred_at, actor, schema_version, payload_json)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                event["event_id"],
                event["event_type"],
                event["occurred_at"],
                event["actor"],
                event["schema_version"],
                json.dumps(payload, sort_keys=True),
            ),
        )
        apply_fn(conn, event)
    return event


def begin_or_get_operation(conn: sqlite3.Connection, operation_id: str, kind: str) -> dict[str, Any] | None:
    """Return the prior committed result for ``operation_id`` if it exists.

    Implements the retry-idempotency requirement: "A retry of an
    uncommitted import operation uses its operation ID and commits
    atomically at most once" (PRISMA spec §2.1.1; import-mapping §2.2).
    """
    row = conn.execute(
        "SELECT result_json FROM operations WHERE operation_id = ? AND kind = ?",
        (operation_id, kind),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["result_json"])


def commit_operation(conn: sqlite3.Connection, operation_id: str, kind: str, result: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO operations (operation_id, kind, committed_at, result_json) VALUES (?, ?, ?, ?)",
        (operation_id, kind, now_rfc3339(), json.dumps(result, sort_keys=True)),
    )


def all_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM events ORDER BY sequence ASC").fetchall()

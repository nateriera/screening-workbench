import json

import pytest

from screening_workbench import db
from screening_workbench.importers.csv_importer import commit_csv_import, preview_csv


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


# IM-01: valid CSV with headers for the full canonical set.
def test_im01_valid_csv_full_headers():
    text = (
        "title,authors,journal,year,doi,abstract,keywords,language,url\n"
        'One Study,Smith,Journal A,2021,10.1/abc,Some abstract,"kw1,kw2",en,http://x\n'
    )
    preview = preview_csv(text)
    mapped = {p.source_field: p.canonical_field for p in preview.mapping_proposals}
    assert mapped["title"] == "title"
    assert mapped["authors"] == "authors"
    assert mapped["doi"] == "doi"
    assert preview.rows_readable == 1


def test_csv_preview_supports_explicit_delimiter_and_headerless_columns():
    preview = preview_csv("Study One\tSmith\t2020\nStudy Two\tJones\t2021\n", delimiter="\t", has_header=False)
    assert preview.header_fields == ["column 1 (unnamed)", "column 2 (unnamed)", "column 3 (unnamed)"]
    assert [proposal.canonical_field for proposal in preview.mapping_proposals] == [None, None, None]
    assert preview.rows_total == 2
    assert preview.rows_readable == 2
    assert preview.mapping_proposals[0].sample_values == ["Study One", "Study Two"]


def test_headerless_csv_commit_includes_first_row_and_selected_delimiter(tmp_path):
    conn = db.connect(tmp_path / "headerless.db")
    source_id, branch_id = _seed_source(conn)
    result = commit_csv_import(
        conn, "Study One\tSmith\t2020\nStudy Two\tJones\t2021\n",
        {0: "title", 1: "authors", 2: "year"}, source_id=source_id, branch_id=branch_id,
        operation_id="headerless-tab", actor="owner", delimiter="\t", has_header=False,
    )
    assert result.records_read == 2
    fields = [
        json.loads(row["fields_json"])
        for row in conn.execute("SELECT fields_json FROM occurrence_fields ORDER BY rowid")
    ]
    assert fields[0]["title"] == "Study One"
    assert fields[0]["authors"] == ["Smith"]
    assert fields[0]["year"] == "2020"
    assert fields[1]["title"] == "Study Two"
    conn.close()


def test_im01_commit_stores_values(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "title,authors,year,doi\nOne Study,Smith,2021,10.1/abc\n"
    mapping = {0: "title", 1: "authors", 2: "year", 3: "doi"}
    result = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="op1", actor="owner",
    )
    assert result.records_read == 1
    assert result.records_skipped == 0
    row = conn.execute("SELECT * FROM occurrences WHERE batch_id = ?", (result.batch_id,)).fetchone()
    fields = json.loads(
        conn.execute(
            "SELECT fields_json FROM occurrence_fields WHERE occurrence_id = ?",
            (row["occurrence_id"],),
        ).fetchone()["fields_json"]
    )
    assert fields["title"] == "One Study"
    assert fields["authors"] == ["Smith"]
    assert fields["doi"] == "10.1/abc"
    assert fields["journal"] == ""  # present and empty, per canonical-fields rule
    conn.close()


# IM-02: quoted comma, doubled quote, embedded newline, CRLF/LF survive.
def test_im02_quoted_fields_and_embedded_newline():
    text = (
        "title,abstract\r\n"
        '"Title, with comma","Line one\nLine two with ""quotes"""\r\n'
    )
    preview = preview_csv(text)
    assert preview.rows_readable == 1
    assert preview.rows_total == 1  # one logical record despite embedded newline


def test_im02_commit_preserves_embedded_values(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = (
        "title,abstract\r\n"
        '"Title, with comma","Line one\nLine two with ""quotes"""\r\n'
    )
    mapping = {0: "title", 1: "abstract"}
    result = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="op2", actor="owner",
    )
    assert result.records_read == 1
    occ = conn.execute("SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result.batch_id,)).fetchone()
    fields = json.loads(
        conn.execute("SELECT fields_json FROM occurrence_fields WHERE occurrence_id=?", (occ["occurrence_id"],)).fetchone()["fields_json"]
    )
    assert fields["title"] == "Title, with comma"
    assert 'Line one\nLine two with "quotes"' == fields["abstract"]
    conn.close()


# IM-03: unknown, blank, and duplicate headers are all visible/distinct.
def test_im03_duplicate_and_blank_headers():
    text = "title,title,,year\nA,B,C,2020\n"
    preview = preview_csv(text)
    labels = preview.header_fields
    assert labels[0] == "title (col 1)"
    assert labels[1] == "title (col 2)"
    assert labels[2] == "column 3 (unnamed)"
    assert labels[3] == "year"
    # Both "title" columns are ambiguous: neither auto-maps.
    by_label = {p.source_field: p for p in preview.mapping_proposals}
    assert by_label["title (col 1)"].canonical_field is None
    assert by_label["title (col 1)"].ambiguous is True
    assert by_label["column 3 (unnamed)"].nonempty_count == 1


# IM-05: too few/too many cells among valid rows -> skipped, not shifted.
def test_im05_column_count_mismatch_skipped():
    text = "title,authors,year\nGood,Smith,2020\nBad,OnlyTwoCols\nAlsoGood,Jones,2021\n"
    preview = preview_csv(text)
    assert preview.rows_readable == 2
    assert len(preview.skipped) == 1
    assert preview.skipped[0]["reason"] == "column_count_mismatch"
    assert preview.skipped[0]["locator"] == "row 3"


def test_im05_commit_skips_malformed_row_others_commit(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "title,authors,year\nGood,Smith,2020\nBad,OnlyTwoCols\nAlsoGood,Jones,2021\n"
    mapping = {0: "title", 1: "authors", 2: "year"}
    result = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="op3", actor="owner",
    )
    assert result.records_read == 2
    assert result.records_skipped == 1
    assert result.skipped_reasons[0]["reason"] == "column_count_mismatch"
    conn.close()


# IM-07: two different columns both map to `title` -> block, no silent merge.
def test_im07_duplicate_single_valued_mapping_rejected(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "title,alt_title,year\nA,B,2020\n"
    mapping = {0: "title", 1: "title", 2: "year"}  # both column 0 and 1 -> title
    with pytest.raises(ValueError):
        commit_csv_import(
            conn, text, mapping, source_id=source_id, branch_id=branch_id,
            operation_id="op4", actor="owner",
        )
    conn.close()


def test_csv_commit_requires_title_mapping(tmp_path):
    conn = db.connect(tmp_path / "title-required.db")
    source_id, branch_id = _seed_source(conn)
    with pytest.raises(ValueError, match="required title field"):
        commit_csv_import(
            conn, "authors,year\nSmith,2020\n", {0: "authors", 1: "year"},
            source_id=source_id, branch_id=branch_id, operation_id="no-title", actor="owner",
        )
    assert conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0] == 0
    conn.close()


# Blank lines counted separately, not as bibliographic records.
def test_blank_lines_counted_separately():
    text = "title,year\nA,2020\n\nB,2021\n"
    preview = preview_csv(text)
    assert preview.rows_readable == 2
    assert preview.blank_lines == 1


# IM-17: importing the same input twice creates two distinct batches.
def test_im17_reimport_same_file_creates_new_batch(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "title,year\nA,2020\n"
    mapping = {0: "title", 1: "year"}
    r1 = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="op-a", actor="owner",
    )
    r2 = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="op-b", actor="owner",  # different operation = deliberate re-import
    )
    assert r1.batch_id != r2.batch_id
    occ_count = conn.execute("SELECT COUNT(*) AS n FROM occurrences").fetchone()["n"]
    assert occ_count == 2  # both batches' records retained, not merged/overwritten
    conn.close()


# IM-18: retrying the SAME operation_id commits exactly once (idempotent).
def test_im18_retry_same_operation_is_idempotent(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "title,year\nA,2020\n"
    mapping = {0: "title", 1: "year"}
    r1 = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="same-op", actor="owner",
    )
    r2 = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="same-op", actor="owner",
    )
    assert r1.batch_id == r2.batch_id
    assert r2.idempotent_replay is True
    batch_count = conn.execute("SELECT COUNT(*) AS n FROM import_batches").fetchone()["n"]
    assert batch_count == 1
    conn.close()


# Canonical fields are always present, even empty, per import-mapping §2.1.
def test_canonical_fields_always_present_even_empty(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "title\nOnly Title\n"
    mapping = {0: "title"}
    result = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="op-empty", actor="owner",
    )
    occ = conn.execute("SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result.batch_id,)).fetchone()
    fields = json.loads(
        conn.execute("SELECT fields_json FROM occurrence_fields WHERE occurrence_id=?", (occ["occurrence_id"],)).fetchone()["fields_json"]
    )
    from screening_workbench.importers import CANONICAL_FIELDS
    for f in CANONICAL_FIELDS:
        assert f in fields
    assert fields["doi"] == ""
    assert fields["authors"] == []
    conn.close()

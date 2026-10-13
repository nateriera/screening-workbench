import json

from screening_workbench import db
from screening_workbench.importers.csv_importer import commit_csv_import
from screening_workbench.importers.pubmed_xml_importer import commit_pubmed_xml_import
from screening_workbench.importers.ris_importer import commit_ris_import


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


def test_csv_commit_computes_normalized_fields(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "title,authors,year,doi\nA Study,Smith,2021,https://doi.org/10.1/ABC\n"
    mapping = {0: "title", 1: "authors", 2: "year", 3: "doi"}
    result = commit_csv_import(
        conn, text, mapping, source_id=source_id, branch_id=branch_id,
        operation_id="op1", actor="owner",
    )
    occ = conn.execute("SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result.batch_id,)).fetchone()
    normalized = json.loads(
        conn.execute(
            "SELECT normalized_json FROM occurrence_fields WHERE occurrence_id=?",
            (occ["occurrence_id"],),
        ).fetchone()["normalized_json"]
    )
    assert normalized["doi"] == "10.1/abc"
    assert normalized["title"] == "a study"
    assert normalized["years"] == ["2021"]
    assert normalized["first_author"] == "smith"
    conn.close()


def test_ris_commit_end_to_end(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "TY  - JOUR\nTI  - RIS Study\nAU  - Jones\nPY  - 2019\nER  - \n"
    result = commit_ris_import(
        conn, text, source_id=source_id, branch_id=branch_id,
        operation_id="ris-op1", actor="owner",
    )
    assert result.records_read == 1
    assert result.records_skipped == 0
    batch = conn.execute("SELECT * FROM import_batches WHERE batch_id=?", (result.batch_id,)).fetchone()
    assert batch["source_format"] == "ris"
    conn.close()


def test_ris_commit_damaged_record_is_skipped_not_imported(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = "TY  - JOUR\nTI  - Unterminated\n"  # missing ER
    result = commit_ris_import(
        conn, text, source_id=source_id, branch_id=branch_id,
        operation_id="ris-op2", actor="owner",
    )
    assert result.records_read == 0
    assert result.records_skipped == 1
    assert result.skipped_reasons[0]["reason"] == "missing_record_boundary"
    conn.close()


def test_pubmed_xml_commit_end_to_end(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    text = (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>1</PMID><Article>"
        "<ArticleTitle>XML Study</ArticleTitle></Article></MedlineCitation></PubmedArticle>"
        "</PubmedArticleSet>"
    )
    result = commit_pubmed_xml_import(
        conn, text, source_id=source_id, branch_id=branch_id,
        operation_id="xml-op1", actor="owner",
    )
    assert result.records_read == 1
    occ = conn.execute("SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result.batch_id,)).fetchone()
    fields = json.loads(
        conn.execute("SELECT fields_json FROM occurrence_fields WHERE occurrence_id=?", (occ["occurrence_id"],)).fetchone()["fields_json"]
    )
    assert fields["title"] == "XML Study"
    assert fields["pmid"] == "1"
    conn.close()


def test_pubmed_xml_xxe_commit_imports_nothing_not_error(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    source_id, branch_id = _seed_source(conn)
    xxe = (
        '<?xml version="1.0"?>'
        '<!DOCTYPE PubmedArticleSet [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        "<PubmedArticleSet>&xxe;</PubmedArticleSet>"
    )
    result = commit_pubmed_xml_import(
        conn, xxe, source_id=source_id, branch_id=branch_id,
        operation_id="xml-xxe", actor="owner",
    )
    assert result.records_read == 0
    assert result.skipped_reasons[0]["reason"].startswith("invalid_encoding")
    conn.close()

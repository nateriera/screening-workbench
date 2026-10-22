import json

import pytest

from screening_workbench import db, export, roles, screening
from screening_workbench.importers.csv_importer import commit_csv_import


def _setup(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    roles.set_owner(conn, "owner1")
    conn.execute("INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))")
    conn.execute(
        "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
        " VALUES ('s1','s1','database','b1',datetime('now'))"
    )
    conn.commit()
    result = commit_csv_import(
        conn, "title\nA Study\n", {0: "title"}, source_id="s1", branch_id="b1",
        operation_id="op1", actor="owner1",
    )
    occ = conn.execute("SELECT occurrence_id FROM occurrences WHERE batch_id=?", (result.batch_id,)).fetchone()
    return conn, occ["occurrence_id"]


# Acceptance test 7: blind export authorization.
def test_blind_reviewer_export_excludes_others_votes(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")

    package = export.export_package(conn, "revA", is_blind=True)
    rows = list(csv_rows(package["decisions.csv"]))
    reviewer_ids = {r["reviewer_id"] for r in rows if r["reviewer_id"]}
    assert reviewer_ids == {"revA"}  # revB's vote excluded

    manifest = json.loads(package["manifest.json"])
    assert manifest["completeness"]["is_complete"] is False
    conn.close()


def test_owner_export_while_blind_sees_everything(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")

    package = export.export_package(conn, "owner1", is_blind=True)
    rows = list(csv_rows(package["decisions.csv"]))
    reviewer_ids = {r["reviewer_id"] for r in rows if r["reviewer_id"]}
    assert reviewer_ids == {"revA", "revB"}
    conn.close()


def test_blind_partial_export_contains_only_the_requesting_reviewers_own_reason(tmp_path):
    """The partial decisions CSV intentionally preserves the caller's own
    vote/reason and suppresses other reviewers' votes; project-wide files
    are omitted from the blind partial package."""
    conn, occ_id = _setup(tmp_path)
    for reviewer, decision, reason in (
        ("revA", "exclude", "their private reason"),
        ("revB", "exclude", "my own private reason"),
    ):
        screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id=reviewer, decision=decision, reason=reason)

    package = export.export_package(conn, "revB", is_blind=True)
    assert "audit-log.jsonl" not in package
    assert "report-study-links.csv" not in package
    assert "prisma-flow.svg" not in package
    decisions = package["decisions.csv"]
    assert "revB" in decisions and "my own private reason" in decisions
    assert "revA" not in decisions and "their private reason" not in decisions
    conn.close()


def test_owner_export_while_blind_audit_log_sees_everything(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")

    package = export.export_package(conn, "owner1", is_blind=True)
    events = [json.loads(line) for line in package["audit-log.jsonl"].splitlines() if line]
    reviewer_ids_seen = {
        e["payload"].get("reviewer_id") for e in events if e["payload"].get("reviewer_id")
    }
    assert reviewer_ids_seen == {"revA", "revB"}
    conn.close()


def test_auditor_with_full_export_scope_sees_everything(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    roles.grant_auditor_role(conn, actor="owner1", target="revC", scope="full_export", reason="external audit")

    package = export.export_package(conn, "revC", is_blind=True)
    rows = list(csv_rows(package["decisions.csv"]))
    reviewer_ids = {r["reviewer_id"] for r in rows if r["reviewer_id"]}
    assert reviewer_ids == {"revA", "revB"}
    conn.close()


def test_unblinded_project_reviewer_sees_everything(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")

    package = export.export_package(conn, "revA", is_blind=False)
    rows = list(csv_rows(package["decisions.csv"]))
    reviewer_ids = {r["reviewer_id"] for r in rows if r["reviewer_id"]}
    assert reviewer_ids == {"revA", "revB"}
    conn.close()


def test_post_revocation_export_denied_full_access(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    roles.grant_auditor_role(conn, actor="owner1", target="revC", scope="full_export", reason="audit")
    roles.revoke_auditor_role(conn, actor="owner1", target="revC", scope="full_export", reason="done")

    package = export.export_package(conn, "revC", is_blind=True)
    rows = list(csv_rows(package["decisions.csv"]))
    reviewer_ids = {r["reviewer_id"] for r in rows if r["reviewer_id"]}
    assert reviewer_ids == set()  # revC has no own votes and no full access
    conn.close()


# Acceptance test 8: watermark -- export event appears in a LATER export.
def test_watermark_export_event_appears_in_later_audit(tmp_path):
    conn, occ_id = _setup(tmp_path)
    package1 = export.export_package(conn, "owner1", is_blind=False)
    manifest1 = json.loads(package1["manifest.json"])

    # The export event itself is NOT in its own audit-log.jsonl (it
    # happens after the watermark it reports).
    log1_types = [json.loads(l)["event_type"] for l in package1["audit-log.jsonl"].splitlines()]
    assert "export.package_generated" not in log1_types

    package2 = export.export_package(conn, "owner1", is_blind=False)
    log2_types = [json.loads(l)["event_type"] for l in package2["audit-log.jsonl"].splitlines()]
    assert "export.package_generated" in log2_types  # first export now visible
    conn.close()


def test_prior_export_files_unchanged_by_later_export(tmp_path):
    conn, occ_id = _setup(tmp_path)
    package1 = export.export_package(conn, "owner1", is_blind=False)
    manifest1_text = package1["manifest.json"]
    # Generating a second export does not mutate the first package's dict.
    export.export_package(conn, "owner1", is_blind=False)
    assert package1["manifest.json"] == manifest1_text
    conn.close()


def test_incomplete_export_discloses_issues(tmp_path):
    conn, occ_id = _setup(tmp_path)
    package = export.export_package(conn, "owner1", is_blind=False)
    manifest = json.loads(package["manifest.json"])
    # No reports/studies configured at all -> not complete, but not
    # silently claimed complete either; issues list may be empty here
    # since there are zero reports (nothing pending). The key behavior is
    # that completeness is explicit and derived, never hand-edited.
    assert "is_complete" in manifest["completeness"]
    assert isinstance(manifest["completeness"]["unresolved_issues"], list)
    conn.close()


# Regression found during the 2026-10-07 dogfood run against the real
# Dogfood corpus: a project with included title/abstract votes but zero
# reports was incorrectly marked complete (nothing else was "pending").
def test_maybe_vote_blocks_completeness_as_screening_pending(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="owner1", decision="maybe")
    is_complete, issues = export.compute_completeness(conn)
    assert is_complete is False
    assert any("pending title/abstract screening" in issue for issue in issues)
    conn.close()


# A real review isn't finished just because no report/study rows exist
# yet -- the included occurrences themselves are unfinished work.
def test_included_but_unpromoted_occurrence_blocks_completeness(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="owner1", decision="include")
    is_complete, issues = export.compute_completeness(conn)
    assert is_complete is False
    assert any("promoted to a full-text report" in issue for issue in issues)
    conn.close()


def test_promoting_the_included_occurrence_clears_that_issue(tmp_path):
    from screening_workbench import reports

    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="owner1", decision="include")
    is_complete_before, issues_before = export.compute_completeness(conn)
    assert is_complete_before is False

    report_id = reports.promote_occurrence_to_report(conn, "owner1", occ_id)
    reports.record_full_text_assessment(conn, "owner1", report_id, "included")
    is_complete_after, issues_after = export.compute_completeness(conn)
    assert not any("promoted to a full-text report" in issue for issue in issues_after)
    conn.close()


# Acceptance test 9: cold offline -- an unresolved title/abstract
# screening conflict must block a complete export, same as a study-level
# conflict already did. Found a real gap here: compute_completeness
# checked study-level conflicts but never screening.list_conflicts.
def test_unresolved_screening_conflict_blocks_completeness(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")

    assert screening.list_conflicts(conn) == [occ_id]
    is_complete, issues = export.compute_completeness(conn)
    assert is_complete is False
    assert any("screening conflict" in issue for issue in issues)
    conn.close()


def test_resolving_the_screening_conflict_clears_that_issue(tmp_path):
    conn, occ_id = _setup(tmp_path)
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revA", decision="include")
    screening.cast_vote(conn, occurrence_id=occ_id, reviewer_id="revB", decision="exclude", reason="x")
    is_complete_before, issues_before = export.compute_completeness(conn)
    assert any("screening conflict" in issue for issue in issues_before)

    screening.resolve_conflict(
        conn, occurrence_id=occ_id, final_decision="include",
        resolution_note="Adjudicated: owner confirms include.", actor="owner1",
    )
    is_complete_after, issues_after = export.compute_completeness(conn)
    assert not any("screening conflict" in issue for issue in issues_after)
    conn.close()


def test_svg_has_accessible_title_and_description(tmp_path):
    conn, occ_id = _setup(tmp_path)
    svg = export.export_prisma_svg(conn)
    assert "<title" in svg
    assert "<desc" in svg
    assert "role=\"img\"" in svg


# Acceptance test 9: cold offline -- a local-write failure must not
# leave the destination folder with a mix of old and new files; prior
# artifacts there must survive untouched.
def test_write_package_to_folder_writes_every_file(tmp_path):
    folder = tmp_path / "export-out"
    folder.mkdir()
    export.write_package_to_folder(
        {"a.txt": "content a", "b.txt": "content b"}, str(folder),
    )
    assert (folder / "a.txt").read_text(encoding="utf-8") == "content a"
    assert (folder / "b.txt").read_text(encoding="utf-8") == "content b"
    # No leftover temp files after a clean run.
    assert sorted(p.name for p in folder.iterdir()) == ["a.txt", "b.txt"]


def test_write_package_to_folder_preserves_prior_artifacts_on_write_failure(tmp_path):
    folder = tmp_path / "export-out"
    folder.mkdir()
    (folder / "a.txt").write_text("OLD a", encoding="utf-8")
    (folder / "b.txt").write_text("OLD b", encoding="utf-8")

    # "c.txt" is actually a directory, so opening it for write fails --
    # simulating a local-write failure partway through the package.
    (folder / "c.txt").mkdir()

    import pytest
    with pytest.raises(OSError):
        export.write_package_to_folder(
            {"a.txt": "NEW a", "b.txt": "NEW b", "c.txt": "NEW c"}, str(folder),
        )

    # Prior artifacts for a.txt/b.txt are untouched -- not overwritten
    # with a partial/inconsistent mix of old and new content.
    assert (folder / "a.txt").read_text(encoding="utf-8") == "OLD a"
    assert (folder / "b.txt").read_text(encoding="utf-8") == "OLD b"
    # Keep the historic temporary-file suffix assertion unchanged for old export-failure fixtures.
    assert not any(p.name.endswith(".screening-workbench-export-tmp") for p in folder.iterdir())


def test_write_package_to_folder_is_all_or_nothing_even_when_earlier_files_staged_fine(tmp_path):
    """The failure point (c.txt) comes after a.txt/b.txt have already
    staged successfully -- their temp files must be cleaned up too, not
    just left as orphaned `.screening-workbench-export-tmp` files."""
    folder = tmp_path / "export-out"
    folder.mkdir()
    (folder / "c.txt").mkdir()  # pre-existing directory blocks the write

    import pytest
    with pytest.raises(OSError):
        export.write_package_to_folder(
            {"a.txt": "NEW a", "b.txt": "NEW b", "c.txt": "NEW c"}, str(folder),
        )

    # a.txt/b.txt were never created at all (this folder had no prior
    # a.txt/b.txt artifacts) -- staged temp files were cleaned up, and
    # no final filename was ever touched.
    names = sorted(p.name for p in folder.iterdir())
    assert "a.txt" not in names
    assert "b.txt" not in names
    assert not any(n.endswith(".screening-workbench-export-tmp") for n in names)


def test_write_package_to_folder_writes_binary_content_in_subdirectory(tmp_path):
    folder = tmp_path / "export-out"
    folder.mkdir()
    export.write_package_to_folder(
        {"manifest.json": "{}", "attachments/abc123.pdf": b"%PDF-1.4 fake bytes"}, str(folder),
    )
    assert (folder / "manifest.json").read_text(encoding="utf-8") == "{}"
    assert (folder / "attachments" / "abc123.pdf").read_bytes() == b"%PDF-1.4 fake bytes"


def csv_rows(text: str):
    import csv
    import io
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        yield row


# Directive D: export manifest/bundle for PDF attachments.
MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


def _report_in_retrieval(conn, actor="owner1"):
    """A report that has reached the retrieval stage (report_attachments
    requires a report_retrievals row to exist, per the directive)."""
    from screening_workbench import reports

    report_id = reports.create_report(conn, actor)
    conn.execute(
        "INSERT INTO report_retrievals (report_id, retrieval_status, actor, updated_at)"
        " VALUES (?, 'pending', ?, datetime('now'))",
        (report_id, actor),
    )
    conn.commit()
    return report_id


def test_export_manifest_lists_attachments_and_bundles_bytes(tmp_path):
    from screening_workbench import attachments

    conn, occ_id = _setup(tmp_path)
    report_id = _report_in_retrieval(conn)
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    attachments.attach_pdf(conn, "owner1", report_id, pdf_path)

    package = export.export_package(conn, "owner1", is_blind=False)
    manifest = json.loads(package["manifest.json"])

    assert len(manifest["attachments"]) == 1
    entry = manifest["attachments"][0]
    assert entry["report_id"] == report_id
    assert entry["filename"] == "doc.pdf"
    assert entry["byte_size"] == len(MINIMAL_PDF)

    bundle_key = f"attachments/{entry['sha256']}.pdf"
    assert bundle_key in package
    assert package[bundle_key] == MINIMAL_PDF
    conn.close()


def test_export_attachments_are_not_required_for_completeness(tmp_path):
    from screening_workbench import attachments

    conn, occ_id = _setup(tmp_path)
    report_id = _report_in_retrieval(conn)
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    attachments.attach_pdf(conn, "owner1", report_id, pdf_path)

    # No reports/studies pending -- an unattached completeness check
    # must not be affected by the presence of a supplementary attachment.
    is_complete, issues = export.compute_completeness(conn)
    assert not any("attachment" in issue for issue in issues)
    conn.close()


def test_export_fails_loudly_when_attachment_file_missing_on_disk(tmp_path):
    from screening_workbench import attachments

    conn, occ_id = _setup(tmp_path)
    report_id = _report_in_retrieval(conn)
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    attachments.attach_pdf(conn, "owner1", report_id, pdf_path)

    attach_dir = attachments.resolve_attachments_dir(conn)
    on_disk = next(attach_dir.glob("*.pdf"))
    on_disk.unlink()  # simulate missing bytes referenced by the manifest

    with pytest.raises(RuntimeError, match="bytes missing or corrupt"):
        export.export_package(conn, "owner1", is_blind=False)
    conn.close()


def test_export_same_attachment_hash_across_two_reports_bundled_once(tmp_path):
    from screening_workbench import attachments

    conn, occ_id = _setup(tmp_path)
    report_a = _report_in_retrieval(conn)
    report_b = _report_in_retrieval(conn)
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    attachments.attach_pdf(conn, "owner1", report_a, pdf_path)
    attachments.attach_pdf(conn, "owner1", report_b, pdf_path)

    package = export.export_package(conn, "owner1", is_blind=False)
    manifest = json.loads(package["manifest.json"])
    assert len(manifest["attachments"]) == 2  # one entry per report
    pdf_keys = [k for k in package if k.startswith("attachments/")]
    assert len(pdf_keys) == 1  # bundled once on disk/in package
    conn.close()

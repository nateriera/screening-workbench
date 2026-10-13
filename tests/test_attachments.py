"""Directive D: PDF attachments for full-text report records."""
from __future__ import annotations

import hashlib

import pytest

from screening_workbench import attachments, db, reports, roles

MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


def _setup(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    roles.set_owner(conn, "owner1")
    report_id = reports.create_report(conn, "owner1")
    # Attachments require the report to have reached the retrieval/
    # full-text stage (report_attachments.report_id REFERENCES
    # report_retrievals(report_id) per the directive); mirror the
    # 'pending' row reports.assign_progression creates in production.
    conn.execute(
        "INSERT INTO report_retrievals (report_id, retrieval_status, actor, updated_at)"
        " VALUES (?, 'pending', 'owner1', datetime('now'))",
        (report_id,),
    )
    conn.commit()
    return conn, report_id


def _new_report_in_retrieval(conn, actor="owner1"):
    report_id = reports.create_report(conn, actor)
    conn.execute(
        "INSERT INTO report_retrievals (report_id, retrieval_status, actor, updated_at)"
        " VALUES (?, 'pending', ?, datetime('now'))",
        (report_id, actor),
    )
    conn.commit()
    return report_id


def _write_pdf(tmp_path, name: str, data: bytes = MINIMAL_PDF):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_attach_pdf_accepts_real_minimal_pdf_bytes(tmp_path):
    conn, report_id = _setup(tmp_path)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")

    attachment_id = attachments.attach_pdf(conn, "owner1", report_id, pdf_path)
    assert attachment_id

    rows = attachments.list_attachments(conn, report_id)
    assert len(rows) == 1
    row = rows[0]
    assert row["filename"] == "doc.pdf"
    assert row["mime_type"] == "application/pdf"
    assert row["byte_size"] == len(MINIMAL_PDF)
    assert row["content_sha256"] == hashlib.sha256(MINIMAL_PDF).hexdigest()
    assert row["uploaded_by"] == "owner1"
    conn.close()


def test_attach_pdf_rejects_non_pdf(tmp_path):
    conn, report_id = _setup(tmp_path)
    not_pdf = tmp_path / "fake.pdf"
    not_pdf.write_bytes(b"this is not a pdf, just text\n")

    with pytest.raises(ValueError, match="not a PDF"):
        attachments.attach_pdf(conn, "owner1", report_id, not_pdf)
    conn.close()


def test_attach_pdf_rejects_unknown_report(tmp_path):
    conn, _report_id = _setup(tmp_path)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")
    with pytest.raises(ValueError, match="no report_retrievals row"):
        attachments.attach_pdf(conn, "owner1", "report_nonexistent", pdf_path)
    conn.close()


def test_attach_pdf_rejects_oversize(tmp_path, monkeypatch):
    conn, report_id = _setup(tmp_path)
    monkeypatch.setattr(attachments, "MAX_ATTACHMENT_BYTES", 10)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")  # well over 10 bytes

    with pytest.raises(ValueError, match="exceeds"):
        attachments.attach_pdf(conn, "owner1", report_id, pdf_path)
    conn.close()


def test_same_file_twice_to_one_report_is_one_row(tmp_path):
    conn, report_id = _setup(tmp_path)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")

    first_id = attachments.attach_pdf(conn, "owner1", report_id, pdf_path)
    second_id = attachments.attach_pdf(conn, "owner1", report_id, pdf_path)
    assert first_id == second_id
    assert len(attachments.list_attachments(conn, report_id)) == 1
    conn.close()


def test_same_file_to_two_reports_is_two_rows_one_on_disk_file(tmp_path):
    conn, report_id_a = _setup(tmp_path)
    report_id_b = _new_report_in_retrieval(conn)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")

    id_a = attachments.attach_pdf(conn, "owner1", report_id_a, pdf_path)
    id_b = attachments.attach_pdf(conn, "owner1", report_id_b, pdf_path)
    assert id_a != id_b

    rows_a = attachments.list_attachments(conn, report_id_a)
    rows_b = attachments.list_attachments(conn, report_id_b)
    assert len(rows_a) == 1 and len(rows_b) == 1
    assert rows_a[0]["content_sha256"] == rows_b[0]["content_sha256"]

    attach_dir = attachments.resolve_attachments_dir(conn)
    pdf_files = list(attach_dir.glob("*.pdf"))
    assert len(pdf_files) == 1  # deduped on disk
    conn.close()


def test_attachment_bytes_returns_exact_bytes(tmp_path):
    conn, report_id = _setup(tmp_path)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")
    attachment_id = attachments.attach_pdf(conn, "owner1", report_id, pdf_path)

    data = attachments.attachment_bytes(conn, attachment_id)
    assert data == MINIMAL_PDF
    conn.close()


def test_attachment_bytes_raises_on_tampered_file(tmp_path):
    conn, report_id = _setup(tmp_path)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")
    attachment_id = attachments.attach_pdf(conn, "owner1", report_id, pdf_path)

    attach_dir = attachments.resolve_attachments_dir(conn)
    on_disk = next(attach_dir.glob("*.pdf"))
    on_disk.write_bytes(MINIMAL_PDF + b"\ntampered")

    with pytest.raises(ValueError, match="integrity failure"):
        attachments.attachment_bytes(conn, attachment_id)
    conn.close()


def test_attachment_bytes_raises_on_missing_file(tmp_path):
    conn, report_id = _setup(tmp_path)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")
    attachment_id = attachments.attach_pdf(conn, "owner1", report_id, pdf_path)

    attach_dir = attachments.resolve_attachments_dir(conn)
    on_disk = next(attach_dir.glob("*.pdf"))
    on_disk.unlink()

    with pytest.raises(OSError):
        attachments.attachment_bytes(conn, attachment_id)
    conn.close()


def test_detach_pdf_removes_row_audits_and_keeps_file(tmp_path):
    conn, report_id = _setup(tmp_path)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")
    attachment_id = attachments.attach_pdf(conn, "owner1", report_id, pdf_path)
    attach_dir = attachments.resolve_attachments_dir(conn)
    on_disk = next(attach_dir.glob("*.pdf"))
    assert on_disk.exists()

    attachments.detach_pdf(conn, "owner1", attachment_id)

    assert attachments.list_attachments(conn, report_id) == []
    assert on_disk.exists()  # content-addressed file retained

    event_types = [r["event_type"] for r in db.all_events(conn)]
    assert "report.attachment_added" in event_types
    assert "report.attachment_removed" in event_types
    conn.close()


def test_detach_pdf_rejects_unknown_attachment(tmp_path):
    conn, _report_id = _setup(tmp_path)
    with pytest.raises(ValueError, match="does not exist"):
        attachments.detach_pdf(conn, "owner1", "att_nonexistent")
    conn.close()


def test_list_attachments_returns_metadata_only(tmp_path):
    conn, report_id = _setup(tmp_path)
    pdf_path = _write_pdf(tmp_path, "doc.pdf")
    attachments.attach_pdf(conn, "owner1", report_id, pdf_path)

    rows = attachments.list_attachments(conn, report_id)
    assert rows[0].keys() == {
        "attachment_id", "report_id", "filename", "content_sha256",
        "byte_size", "mime_type", "uploaded_by", "uploaded_at",
    }
    conn.close()

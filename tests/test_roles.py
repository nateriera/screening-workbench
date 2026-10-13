import pytest

from screening_workbench import db, roles


def _setup(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    roles.set_owner(conn, "owner1")
    return conn


def test_set_owner_once(tmp_path):
    conn = _setup(tmp_path)
    assert roles.get_owner(conn) == "owner1"
    with pytest.raises(ValueError):
        roles.set_owner(conn, "someone_else")
    conn.close()


def test_blind_mode_owner_only(tmp_path):
    conn = _setup(tmp_path)
    with pytest.raises(PermissionError):
        roles.set_blind(conn, "revA", True)
    roles.set_blind(conn, "owner1", True)
    assert roles.is_blind(conn) is True
    conn.close()


def test_blind_mode_locks_after_screening_starts(tmp_path):
    conn = _setup(tmp_path)
    roles.set_blind(conn, "owner1", True)
    roles.mark_screening_started(conn, "owner1")
    with pytest.raises(PermissionError):
        roles.set_blind(conn, "owner1", False)
    conn.close()


def test_owner_can_grant_and_revoke_auditor_scope(tmp_path):
    conn = _setup(tmp_path)
    roles.grant_auditor_role(conn, actor="owner1", target="revA", scope="full_export", reason="needs full export for PRISMA")
    assert roles.has_scope(conn, "revA", "full_export") is True
    roles.revoke_auditor_role(conn, actor="owner1", target="revA", scope="full_export", reason="task complete")
    assert roles.has_scope(conn, "revA", "full_export") is False
    conn.close()


def test_non_owner_cannot_self_grant(tmp_path):
    conn = _setup(tmp_path)
    with pytest.raises(PermissionError):
        roles.grant_auditor_role(conn, actor="revA", target="revA", scope="full_export", reason="I want it")
    assert roles.has_scope(conn, "revA", "full_export") is False
    conn.close()


def test_revocation_denies_immediately(tmp_path):
    conn = _setup(tmp_path)
    roles.grant_auditor_role(conn, actor="owner1", target="revB", scope="audit_read", reason="audit task")
    assert roles.has_scope(conn, "revB", "audit_read") is True
    roles.revoke_auditor_role(conn, actor="owner1", target="revB", scope="audit_read", reason="done")
    assert roles.has_scope(conn, "revB", "audit_read") is False
    # Prior grant event itself is retained (append-only), not deleted.
    rows = conn.execute("SELECT COUNT(*) AS n FROM auditor_grant_events WHERE target='revB'").fetchone()["n"]
    assert rows == 2
    conn.close()


def test_grant_requires_reason(tmp_path):
    conn = _setup(tmp_path)
    with pytest.raises(ValueError):
        roles.grant_auditor_role(conn, actor="owner1", target="revA", scope="full_export", reason="")
    conn.close()


def test_is_owner_or_auditor(tmp_path):
    conn = _setup(tmp_path)
    assert roles.is_owner_or_auditor(conn, "owner1", "full_export") is True
    assert roles.is_owner_or_auditor(conn, "revA", "full_export") is False
    roles.grant_auditor_role(conn, actor="owner1", target="revA", scope="full_export", reason="x")
    assert roles.is_owner_or_auditor(conn, "revA", "full_export") is True
    conn.close()


def test_set_project_name_owner_only(tmp_path):
    conn = _setup(tmp_path)
    with pytest.raises(PermissionError):
        roles.set_project_name(conn, "revA", "Community gardening & adult wellbeing")
    roles.set_project_name(conn, "owner1", "Community gardening & adult wellbeing", review_type="Scoping review")
    info = roles.get_project_name(conn)
    assert info["name"] == "Community gardening & adult wellbeing"
    assert info["review_type"] == "Scoping review"
    conn.close()


def test_set_project_name_rejects_empty(tmp_path):
    conn = _setup(tmp_path)
    with pytest.raises(ValueError):
        roles.set_project_name(conn, "owner1", "   ")
    conn.close()


def test_get_project_name_defaults_to_none(tmp_path):
    conn = _setup(tmp_path)
    info = roles.get_project_name(conn)
    assert info == {"name": None, "review_type": None}
    conn.close()


def test_set_project_name_can_be_renamed_later(tmp_path):
    """Unlike owner/blind-lock, naming has no screening-started lock."""
    conn = _setup(tmp_path)
    roles.set_project_name(conn, "owner1", "First name")
    roles.mark_screening_started(conn, "owner1")
    roles.set_project_name(conn, "owner1", "Renamed after screening started")
    assert roles.get_project_name(conn)["name"] == "Renamed after screening started"
    conn.close()

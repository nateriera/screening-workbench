"""Owner/auditor role model and blind-mode project settings.

Implements docs/specs/behavioral-spec-prisma-counts-export.md §2.6.5-6
and the screening-workflow spec §1/§4 blind-toggle rules.
"""
from __future__ import annotations

from screening_workbench import db
from screening_workbench.ids import new_id

VALID_SCOPES = ("audit_read", "full_export")


def set_owner(conn, owner_id: str) -> None:
    """Fix the project owner. Callable exactly once per project."""
    existing = conn.execute("SELECT owner_id FROM project_owner").fetchone()
    if existing is not None:
        raise ValueError(f"owner already set to {existing['owner_id']}; owner is fixed at creation")

    def apply_fn(c, event):
        c.execute(
            "INSERT INTO project_owner (owner_id, set_at) VALUES (?, ?)",
            (event["payload"]["owner_id"], event["occurred_at"]),
        )
        c.execute("INSERT OR IGNORE INTO project_settings (id) VALUES ('project')")

    db.append_event(conn, "project.owner_set", owner_id, {"owner_id": owner_id}, apply_fn=apply_fn)


def get_owner(conn) -> str | None:
    row = conn.execute("SELECT owner_id FROM project_owner").fetchone()
    return row["owner_id"] if row else None


def is_owner(conn, actor: str) -> bool:
    return get_owner(conn) == actor


def set_blind(conn, actor: str, is_blind: bool) -> None:
    """Only the owner may change blind mode, and only before screening
    begins (screening-workflow spec §1: "the blind toggle locks once
    screening begins")."""
    if not is_owner(conn, actor):
        raise PermissionError("only the project owner may change blind mode")
    row = conn.execute("SELECT screening_started FROM project_settings WHERE id='project'").fetchone()
    if row and row["screening_started"]:
        raise PermissionError("blind mode is locked once screening has begun")

    def apply_fn(c, event):
        c.execute(
            "UPDATE project_settings SET is_blind = ? WHERE id='project'",
            (1 if event["payload"]["is_blind"] else 0,),
        )

    db.append_event(conn, "project.blind_mode_set", actor, {"is_blind": is_blind}, apply_fn=apply_fn)


def mark_screening_started(conn, actor: str) -> None:
    def apply_fn(c, event):
        c.execute("UPDATE project_settings SET screening_started = 1 WHERE id='project'")

    db.append_event(conn, "project.screening_started", actor, {}, apply_fn=apply_fn)


def is_blind(conn) -> bool:
    row = conn.execute("SELECT is_blind FROM project_settings WHERE id='project'").fetchone()
    return bool(row["is_blind"]) if row else False


def set_project_name(conn, actor: str, name: str, review_type: str | None = None) -> None:
    """Name the review (screening-workflow spec §1 setup step (a)).
    Owner-only, consistent with other project-level settings; callable
    again later to rename (unlike the owner/blind-lock, naming has no
    "locks once screening begins" rule in the spec)."""
    if not is_owner(conn, actor):
        raise PermissionError("only the project owner may set the project name")
    if not name or not name.strip():
        raise ValueError("project name must not be empty")

    payload = {"name": name.strip(), "review_type": (review_type or "").strip() or None}

    def apply_fn(c, event):
        p = event["payload"]
        c.execute("INSERT OR IGNORE INTO project_settings (id) VALUES ('project')")
        c.execute(
            "UPDATE project_settings SET name = ?, review_type = ? WHERE id='project'",
            (p["name"], p["review_type"]),
        )

    db.append_event(conn, "project.name_set", actor, payload, apply_fn=apply_fn)


def get_project_name(conn) -> dict:
    row = conn.execute("SELECT name, review_type FROM project_settings WHERE id='project'").fetchone()
    if row is None:
        return {"name": None, "review_type": None}
    return {"name": row["name"], "review_type": row["review_type"]}


def grant_auditor_role(conn, *, actor: str, target: str, scope: str, reason: str) -> None:
    """Owner-only grant of an auditor scope (spec §2.6.5). Reviewers
    cannot grant themselves roles -- enforced by requiring ``actor`` to
    be the owner and ``target`` to not equal ``actor`` unless the owner
    is also the target reviewer (owner granting themselves scope they
    already implicitly have is a no-op allowance, not a security risk;
    the forbidden case is a non-owner granting any role to anyone,
    including themselves).
    """
    if scope not in VALID_SCOPES:
        raise ValueError(f"invalid scope: {scope}")
    if not reason or not reason.strip():
        raise ValueError("a reason is required for every grant/revocation")
    if not is_owner(conn, actor):
        raise PermissionError("only the project owner may grant an auditor role")

    payload = {"target": target, "scope": scope, "action": "grant", "reason": reason}

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO auditor_grant_events (grant_event_id, target, scope, action, actor, reason, occurred_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (new_id("grant"), p["target"], p["scope"], p["action"], event["actor"], p["reason"], event["occurred_at"]),
        )

    db.append_event(conn, "role.auditor_granted", actor, payload, apply_fn=apply_fn)


def revoke_auditor_role(conn, *, actor: str, target: str, scope: str, reason: str) -> None:
    if scope not in VALID_SCOPES:
        raise ValueError(f"invalid scope: {scope}")
    if not reason or not reason.strip():
        raise ValueError("a reason is required for every grant/revocation")
    if not is_owner(conn, actor):
        raise PermissionError("only the project owner may revoke an auditor role")

    payload = {"target": target, "scope": scope, "action": "revoke", "reason": reason}

    def apply_fn(c, event):
        p = event["payload"]
        c.execute(
            "INSERT INTO auditor_grant_events (grant_event_id, target, scope, action, actor, reason, occurred_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (new_id("grant"), p["target"], p["scope"], p["action"], event["actor"], p["reason"], event["occurred_at"]),
        )

    db.append_event(conn, "role.auditor_revoked", actor, payload, apply_fn=apply_fn)


def has_scope(conn, target: str, scope: str) -> bool:
    """Current authorization = latest grant/revoke event for
    (target, scope); revocation denies immediately (spec §2.6.5)."""
    row = conn.execute(
        "SELECT action FROM auditor_grant_events WHERE target = ? AND scope = ?"
        " ORDER BY occurred_at DESC, grant_event_id DESC LIMIT 1",
        (target, scope),
    ).fetchone()
    return bool(row) and row["action"] == "grant"


def is_owner_or_auditor(conn, actor: str, scope: str) -> bool:
    return is_owner(conn, actor) or has_scope(conn, actor, scope)

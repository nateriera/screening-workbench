"""RFC 3339 timestamp and stable ID helpers used across Screening Workbench's domain layer.

Timestamps are always UTC with an explicit ``Z`` offset, matching the audit
log requirement in docs/specs/behavioral-spec-duplicate-detection.md §5
([S8] RFC 3339) and the PRISMA spec's append-only event requirement.
"""
from __future__ import annotations

import datetime as _dt
import uuid


def now_rfc3339() -> str:
    """Return the current UTC time as an RFC 3339 string with a 'Z' offset."""
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def new_id(prefix: str) -> str:
    """Return a new opaque, immutable, globally-unique ID.

    IDs are prefixed (e.g. ``src_``, ``rec_``, ``evt_``) purely for human
    readability in logs/exports; the prefix is not parsed by any code path.
    Uniqueness and immutability are the only behavioral requirements from
    the specs (e.g. duplicate-detection spec §5: "Immutable record_id").
    """
    return f"{prefix}_{uuid.uuid4().hex}"

"""Canonical record fields shared by every v1 import format.

See docs/specs/behavioral-spec-import-field-mapping.md §2.1. Every
committed occurrence has all of these fields, even when empty.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CANONICAL_FIELDS: tuple[str, ...] = (
    "title",
    "authors",
    "journal",
    "year",
    "volume",
    "issue",
    "pages",
    "doi",
    "pmid",
    "abstract",
    "keywords",
    "language",
    "url",
)

# Fields whose logical value is an ordered list rather than a single string.
LIST_FIELDS: frozenset[str] = frozenset({"authors", "keywords"})

# System-generated fields: never user-mapped (spec §2.1 table rows for
# `import batch` and `raw source line`). Not part of CANONICAL_FIELDS
# because they are not candidates for source-to-canonical mapping.
SYSTEM_FIELDS: tuple[str, ...] = ("import_batch", "raw_source_line")

#: Case/whitespace-insensitive CSV header aliases that *propose* a mapping.
#: Proposals only -- the user may override before commit (spec §4.1 CSV).
CSV_HEADER_ALIASES: dict[str, str] = {
    "title": "title",
    "authors": "authors",
    "author": "authors",
    "journal": "journal",
    "journal/source": "journal",
    "source": "journal",
    "year": "year",
    "volume": "volume",
    "issue": "issue",
    "pages": "pages",
    "doi": "doi",
    "pmid": "pmid",
    "abstract": "abstract",
    "keywords": "keywords",
    "language": "language",
    "url": "url",
}


def empty_fields() -> dict[str, str | list[str]]:
    """A canonical field dict with every field present and empty."""
    out: dict[str, str | list[str]] = {}
    for name in CANONICAL_FIELDS:
        out[name] = [] if name in LIST_FIELDS else ""
    return out


@dataclass
class FieldMappingProposal:
    """One proposed (or user-confirmed) source-field -> canonical mapping."""

    source_field: str
    canonical_field: str | None  # None means "unmapped"
    nonempty_count: int
    sample_values: list[str] = field(default_factory=list)
    ambiguous: bool = False


@dataclass
class ImportPreview:
    """Result of parsing+mapping-proposal before any commit (spec §3)."""

    source_format: str
    header_fields: list[str]
    mapping_proposals: list[FieldMappingProposal]
    rows_total: int
    rows_readable: int
    skipped: list[dict]  # [{"locator": str, "reason": str}]
    blank_lines: int = 0

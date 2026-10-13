"""CSV importer: preview/mapping-proposal and atomic commit.

Implements the CSV-relevant subset of
docs/specs/behavioral-spec-import-field-mapping.md. Known v1 gaps (documented
rather than silently handled) are listed at the bottom of this module.
"""
from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass

from screening_workbench import db
from screening_workbench.ids import new_id, now_rfc3339
from screening_workbench.importers import (
    CANONICAL_FIELDS,
    CSV_HEADER_ALIASES,
    FieldMappingProposal,
    ImportPreview,
    empty_fields,
)
from screening_workbench.importers.commit import CommitResult, commit_occurrences
from screening_workbench.importers.limits import (
    ImportLimitError, MAX_FIELD_CHARS, MAX_IMPORT_RECORDS, validate_text_size,
)

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_header(name: str) -> str:
    return _WHITESPACE_RE.sub(" ", name.strip().casefold())


def _label_headers(headers: list[str]) -> list[str]:
    """Give every column a unique display label; ordinal-qualify blank or
    duplicate headers (spec §4.1: "Duplicate header names are distinct
    source columns identified by ordinal" / "A blank header is labeled by
    position")."""
    seen: dict[str, int] = {}
    counts: dict[str, int] = {}
    for h in headers:
        key = h.strip()
        counts[key] = counts.get(key, 0) + 1
    labels: list[str] = []
    for i, h in enumerate(headers, start=1):
        key = h.strip()
        if not key:
            labels.append(f"column {i} (unnamed)")
        elif counts[key] > 1:
            seen[key] = seen.get(key, 0) + 1
            labels.append(f"{key} (col {i})")
        else:
            labels.append(key)
    return labels


_SUPPORTED_DELIMITERS = {",", "\t", ";", "|"}
MAX_COLUMNS = 10_000


def _preflight_column_count(text: str, delimiter: str) -> None:
    """Reject wide logical CSV records before csv.reader allocates their cells."""
    columns = 1
    in_quotes = False
    field_start = True
    i = 0
    while i < len(text):
        char = text[i]
        if in_quotes:
            if char == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    i += 1
                else:
                    in_quotes = False
        elif char == '"' and field_start:
            in_quotes = True
            field_start = False
        elif char == delimiter:
            columns += 1
            if columns > MAX_COLUMNS:
                raise ImportLimitError(f"CSV row exceeds the {MAX_COLUMNS}-column import limit")
            field_start = True
        elif char in "\r\n":
            columns = 1
            field_start = True
            if char == "\r" and i + 1 < len(text) and text[i + 1] == "\n":
                i += 1
        else:
            field_start = False
        i += 1


def _read_rows(text: str, delimiter: str = ",", has_header: bool = True) -> tuple[list[str], list[list[str]]]:
    if delimiter not in _SUPPORTED_DELIMITERS:
        raise ValueError("delimiter must be comma, tab, semicolon, or pipe")
    validate_text_size(text)
    _preflight_column_count(text, delimiter)
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    previous_field_limit = csv.field_size_limit()
    rows = []
    try:
        csv.field_size_limit(MAX_FIELD_CHARS)
        for row in reader:
            record_rows = len(rows) - (1 if has_header and rows else 0)
            if record_rows >= MAX_IMPORT_RECORDS:
                raise ImportLimitError(f"CSV exceeds the {MAX_IMPORT_RECORDS}-record import limit")
            if row and len(row) > MAX_COLUMNS:
                raise ImportLimitError(f"CSV row exceeds the {MAX_COLUMNS}-column import limit")
            rows.append(row)
    except csv.Error as exc:
        raise ImportLimitError(f"CSV field exceeds the {MAX_FIELD_CHARS}-character limit") from exc
    finally:
        csv.field_size_limit(previous_field_limit)
    if not rows:
        return [], []
    if not has_header:
        return [""] * len(rows[0]), rows
    header, *data_rows = rows
    return header, data_rows


def preview_csv(text: str, *, delimiter: str = ",", has_header: bool = True) -> ImportPreview:
    """Parse ``text`` as CSV and propose a source->canonical mapping.

    ``has_header`` and ``delimiter`` are explicit user choices; values are
    never inferred from cell content.
    """
    header, data_rows = _read_rows(text, delimiter, has_header)
    labels = _label_headers(header)
    n_cols = len(header)

    # Column index -> list of nonempty sample values (first 3) and count.
    nonempty_counts = [0] * n_cols
    samples: list[list[str]] = [[] for _ in range(n_cols)]
    blank_lines = 0
    skipped: list[dict] = []
    rows_readable = 0

    for row_num, row in enumerate(data_rows, start=2 if has_header else 1):
        if row == [] or all(cell.strip() == "" for cell in row):
            blank_lines += 1
            continue
        if len(row) != n_cols:
            skipped.append(
                {
                    "locator": f"row {row_num}",
                    "reason": "column_count_mismatch",
                }
            )
            continue
        rows_readable += 1
        for i, cell in enumerate(row):
            if cell.strip():
                nonempty_counts[i] += 1
                if len(samples[i]) < 3:
                    samples[i].append(cell)

    # Propose mappings; detect ambiguous multi-column-to-one-field conflicts.
    proposed_canonical: dict[int, str] = {}
    for i, h in enumerate(header):
        canon = CSV_HEADER_ALIASES.get(_normalize_header(h))
        if canon:
            proposed_canonical[i] = canon

    canon_to_cols: dict[str, list[int]] = {}
    for i, canon in proposed_canonical.items():
        canon_to_cols.setdefault(canon, []).append(i)

    proposals: list[FieldMappingProposal] = []
    for i, label in enumerate(labels):
        canon = proposed_canonical.get(i)
        ambiguous = canon is not None and len(canon_to_cols[canon]) > 1
        proposals.append(
            FieldMappingProposal(
                source_field=label,
                canonical_field=None if ambiguous else canon,
                nonempty_count=nonempty_counts[i],
                sample_values=samples[i],
                ambiguous=ambiguous,
            )
        )

    return ImportPreview(
        source_format="csv",
        header_fields=labels,
        mapping_proposals=proposals,
        rows_total=len(data_rows),
        rows_readable=rows_readable,
        skipped=skipped,
        blank_lines=blank_lines,
    )


def commit_csv_import(
    conn,
    text: str,
    mapping: dict[int, str],
    *,
    source_id: str,
    branch_id: str,
    operation_id: str,
    actor: str,
    source_name: str = "import.csv",
    delimiter: str = ",",
    has_header: bool = True,
) -> CommitResult:
    """Atomically commit a CSV import under ``mapping`` (column index ->
    canonical field name, one column per canonical field for v1).

    Idempotent: retrying the same ``operation_id`` returns the previously
    committed result without creating a second batch (import-mapping spec
    §2.2, §3.6; IM-18).
    """
    if "title" not in mapping.values():
        raise ValueError("mapping must assign a column to the required title field")
    mapped_canon = list(mapping.values())
    if len(mapped_canon) != len(set(mapped_canon)):
        raise ValueError(
            "mapping assigns more than one column to the same canonical "
            "field; resolve priority or leave one unmapped (IM-07)"
        )
    for canon in mapped_canon:
        if canon not in CANONICAL_FIELDS:
            raise ValueError(f"unknown canonical field: {canon}")

    header, data_rows = _read_rows(text, delimiter, has_header)
    n_cols = len(header)

    occurrences: list[dict] = []
    skipped: list[dict] = []
    for row_num, row in enumerate(data_rows, start=2 if has_header else 1):
        if row == [] or all(cell.strip() == "" for cell in row):
            continue  # blank line, not a bibliographic record
        if len(row) != n_cols:
            skipped.append({"locator": f"row {row_num}", "reason": "column_count_mismatch"})
            continue
        fields = empty_fields()
        for col_idx, canon in mapping.items():
            value = row[col_idx].strip() if col_idx < len(row) else ""
            if canon in ("authors", "keywords"):
                fields[canon] = [value] if value else []
            else:
                fields[canon] = value
        occurrences.append(
            {
                "occurrence_id": new_id("occ"),
                "locator": f"row {row_num}",
                "raw_source_text": delimiter.join(row),
                "fields": fields,
            }
        )

    return commit_occurrences(
        conn,
        occurrences=occurrences,
        skipped=skipped,
        source_format="csv",
        source_id=source_id,
        branch_id=branch_id,
        mapping={
            "columns": {str(k): v for k, v in mapping.items()},
            "delimiter": "tab" if delimiter == "\t" else delimiter,
            "has_header": has_header,
        },
        mapping_version=1,
        operation_id=operation_id,
        actor=actor,
        source_name=source_name,
    )


# --- Known v1 gaps (logged per implementer-prompt hard constraint #1) ---
# * Multi-column combination for repeatable authors/keywords across several
#   source columns (one column each) is not yet supported; only a single
#   column may map to `authors` or `keywords` in this version.

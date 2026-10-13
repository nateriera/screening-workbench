"""RIS importer: tag-based record parsing per
docs/specs/behavioral-spec-import-field-mapping.md §4.2.

Known v1 gaps are documented at the bottom of this module.
"""
from __future__ import annotations

import re
import io
from dataclasses import dataclass, field

from screening_workbench.importers import CANONICAL_FIELDS, empty_fields
from screening_workbench.importers.commit import CommitResult, commit_occurrences
from screening_workbench.ids import new_id
from screening_workbench.importers.limits import (
    ImportLimitError, MAX_FIELD_CHARS, MAX_IMPORT_RECORDS, MAX_SKIPPED_LINES, validate_text_size,
)

_TAG_RE = re.compile(r"^([A-Za-z0-9]{2})(\s{1,2})-(.*)$")

# Proposed common mappings (spec §4.2). `TY` is structural, never mapped.
_SINGLE_VALUE_TAGS: dict[str, str] = {
    "DO": "doi",
    "VL": "volume",
    "IS": "issue",
    "LA": "language",
}
_TITLE_TAGS = ("TI", "T1")
_JOURNAL_TAGS = ("JO", "JF", "JA", "J2", "T2")
_YEAR_TAGS = ("PY", "Y1")
_URL_TAGS = ("UR", "LK")
_ABSTRACT_TAGS = ("AB", "N2")
_AUTHOR_TAGS = ("AU", "A1")
_KEYWORD_TAG = "KW"
_PMID_TAG = "AN"
_FOUR_DIGIT_YEAR = re.compile(r"\d{4}")


@dataclass
class RisRecord:
    locator: str
    tags: list[tuple[str, str]] = field(default_factory=list)  # (tag, value) in order
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class RisParseResult:
    records: list[RisRecord]
    skipped: list[dict]  # [{"locator": str, "reason": str}]


def parse_ris(text: str) -> RisParseResult:
    """Split RIS text into records bounded by ``TY`` ... ``ER``.

    Recovery policy (spec §4.2 IM-09): a missing ``ER``, a nested/new ``TY``
    before ``ER``, or unparseable tag lines are reported; recovery happens
    only at the next unambiguous ``TY`` boundary, otherwise the damaged
    record is skipped with a reason. Content outside any record is ignored
    (counted as a skip with reason ``malformed_record`` if nonblank).
    """
    validate_text_size(text)
    records: list[RisRecord] = []
    skipped: list[dict] = []

    current: RisRecord | None = None
    current_tag: str | None = None
    record_start_line = 0

    def append_skip(line_no: int, reason: str) -> None:
        if len(skipped) >= MAX_SKIPPED_LINES:
            raise ImportLimitError(f"RIS exceeds the {MAX_SKIPPED_LINES}-diagnostic import limit")
        skipped.append({"locator": f"line {line_no}", "reason": reason})

    def flush_damaged(reason: str, line_no: int) -> None:
        append_skip(record_start_line or line_no, reason)

    for line_no, line in enumerate(io.StringIO(text), start=1):
        stripped = line.rstrip("\r\n")
        match = _TAG_RE.match(stripped)
        if match:
            tag = match.group(1).upper()
            value = match.group(3).strip()
            if len(value) > MAX_FIELD_CHARS:
                raise ImportLimitError(f"RIS field exceeds the {MAX_FIELD_CHARS}-character limit")
            if tag == "TY":
                if current is not None:
                    # Nested/new TY before ER: damaged, skip the unterminated one.
                    flush_damaged("missing_record_boundary", line_no)
                current = RisRecord(locator=f"line {line_no}")
                record_start_line = line_no
                current.tags.append((tag, value))
                current.raw_lines.append(stripped)
                current_tag = tag
            elif tag == "ER":
                if current is None:
                    if stripped.strip():
                        append_skip(line_no, "malformed_record")
                else:
                    current.raw_lines.append(stripped)
                    records.append(current)
                    if len(records) > MAX_IMPORT_RECORDS:
                        raise ImportLimitError(f"RIS exceeds the {MAX_IMPORT_RECORDS}-record import limit")
                    current = None
                    current_tag = None
            else:
                if current is None:
                    if stripped.strip():
                        append_skip(line_no, "malformed_record")
                else:
                    current.tags.append((tag, value))
                    current.raw_lines.append(stripped)
                    current_tag = tag
        elif stripped.strip() == "":
            pass  # blank line, ignored
        else:
            # Continuation line for the active tag, or an orphan.
            if current is not None and current_tag is not None:
                # Append to the most recent occurrence of current_tag.
                for idx in range(len(current.tags) - 1, -1, -1):
                    if current.tags[idx][0] == current_tag:
                        t, v = current.tags[idx]
                        value = v + "\n" + stripped.strip()
                        if len(value) > MAX_FIELD_CHARS:
                            raise ImportLimitError(f"RIS field exceeds the {MAX_FIELD_CHARS}-character limit")
                        current.tags[idx] = (t, value)
                        break
                current.raw_lines.append(stripped)
            else:
                append_skip(line_no, "malformed_record")

    if current is not None:
        # Reached EOF without ER: unrecoverable, skip the damaged record.
        append_skip(record_start_line, "missing_record_boundary")

    return RisParseResult(records=records, skipped=skipped)


def _first_value(tags: list[tuple[str, str]], names: tuple[str, ...] | str) -> str | None:
    wanted = (names,) if isinstance(names, str) else names
    for t, v in tags:
        if t in wanted and v.strip():
            return v.strip()
    return None


def _all_values(tags: list[tuple[str, str]], name: str) -> list[str]:
    return [v.strip() for t, v in tags if t == name and v.strip()]


def map_ris_record(record: RisRecord) -> dict:
    """Map one parsed RIS record to canonical fields (spec §4.2 proposals)."""
    fields = empty_fields()

    title = _first_value(record.tags, _TITLE_TAGS)
    if title:
        fields["title"] = title

    journal = _first_value(record.tags, _JOURNAL_TAGS)
    if journal:
        fields["journal"] = journal

    year_raw = _first_value(record.tags, _YEAR_TAGS)
    if year_raw:
        m = _FOUR_DIGIT_YEAR.search(year_raw)
        if m:
            fields["year"] = m.group(0)

    for tag, canon in _SINGLE_VALUE_TAGS.items():
        v = _first_value(record.tags, tag)
        if v:
            fields[canon] = v

    sp = _first_value(record.tags, "SP")
    ep = _first_value(record.tags, "EP")
    if sp and ep and "-" not in sp:
        fields["pages"] = f"{sp}-{ep}"
    elif sp:
        fields["pages"] = sp

    url = _first_value(record.tags, _URL_TAGS)
    if url:
        fields["url"] = url

    abstract = _first_value(record.tags, _ABSTRACT_TAGS)
    if abstract:
        fields["abstract"] = abstract

    authors = _all_values(record.tags, "AU") + _all_values(record.tags, "A1")
    if authors:
        fields["authors"] = authors

    keywords = _all_values(record.tags, _KEYWORD_TAG)
    if keywords:
        fields["keywords"] = keywords

    return fields


# --- Known v1 gaps (logged per implementer-prompt hard constraint #1) ---
# * One-space-before-dash relaxed tag syntax (spec: "Accept one or two
#   spaces before the dash") is not yet exercised by a dedicated fixture
#   beyond the regex `\s{1,2}` already accepting it.
# * Conflicting TI/T1 or PY/Y1 values (IM-10) are not flagged as an explicit
#   "conflicting_single_value" skip reason; this version silently prefers
#   the first match. This is a known deviation from the spec's
#   no-first-wins requirement and must be fixed before release.
# * AN -> PMID "only when value is explicitly a PubMed identifier or user
#   confirms" is not implemented; AN is currently left unmapped entirely.


def commit_ris_import(
    conn,
    text: str,
    *,
    source_id: str,
    branch_id: str,
    operation_id: str,
    actor: str,
    source_name: str = "import.ris",
) -> CommitResult:
    """Parse, map, and atomically commit an RIS file's complete records.

    Damaged/unterminated records reported by :func:`parse_ris` are carried
    through as skips with their original reason; they never become
    occurrences.
    """
    parsed = parse_ris(text)
    occurrences = []
    for record in parsed.records:
        fields = map_ris_record(record)
        occurrences.append(
            {
                "occurrence_id": new_id("occ"),
                "locator": record.locator,
                "raw_source_text": "\n".join(record.raw_lines),
                "fields": fields,
            }
        )
    return commit_occurrences(
        conn,
        occurrences=occurrences,
        skipped=parsed.skipped,
        source_format="ris",
        source_id=source_id,
        branch_id=branch_id,
        mapping={"format": "ris-standard-proposals-v1"},
        mapping_version=1,
        operation_id=operation_id,
        actor=actor,
        source_name=source_name,
    )


"""Deterministic normalization rules for deduplication comparisons.

Implements docs/specs/behavioral-spec-duplicate-detection.md §3.1
"Normalization contract". Normalized values are additional comparison
keys only; they never replace the stored raw/display value.
"""
from __future__ import annotations

import re
import unicodedata

_DOI_PREFIX_RE = re.compile(
    r"^\s*(doi\s*:\s*|https?://(dx\.)?doi\.org/)", re.IGNORECASE
)
_TRAILING_PUNCT_RE = re.compile(r"[\s.,;]+$")
_PUNCT_OR_WS_RUN_RE = re.compile(r"[^0-9A-Za-z]+", re.UNICODE)
_FOUR_DIGIT_YEAR_RE = re.compile(r"(1[5-9]\d{2}|20\d{2}|21\d{2})")


def normalize_doi(raw: str | None) -> str | None:
    """Normalize a DOI for exact-match comparison.

    Trims whitespace, strips a leading ``doi:`` label or
    ``http(s)://(dx.)doi.org/`` resolver prefix (case-insensitive), strips
    trailing citation punctuation, then lowercases. Returns ``None`` if the
    input is empty/missing -- an empty DOI is never a usable match key.
    """
    if not raw or not raw.strip():
        return None
    value = _DOI_PREFIX_RE.sub("", raw.strip())
    value = _TRAILING_PUNCT_RE.sub("", value)
    value = value.strip()
    if not value:
        return None
    return value.lower()


def normalize_title(raw: str | None) -> str | None:
    """Normalize a title for exact/fuzzy comparison.

    NFKC + casefold, collapse punctuation/symbol/whitespace runs to a
    single ASCII space, trim ends. Never strips diacritics, reorders
    tokens, or removes words. An empty normalized title is ``None`` and
    never participates in a match (spec: "Empty normalized titles never
    match.").
    """
    if not raw or not raw.strip():
        return None
    value = unicodedata.normalize("NFKC", raw).casefold()
    # Collapse any run of characters that are not letters/digits (this
    # folds in both punctuation and whitespace) to one ASCII space, but
    # preserve individual Unicode letters (including diacritics) as-is.
    out = []
    prev_was_sep = False
    for ch in value:
        if ch.isalnum():
            out.append(ch)
            prev_was_sep = False
        else:
            if not prev_was_sep:
                out.append(" ")
                prev_was_sep = True
    normalized = "".join(out).strip()
    return normalized or None


def extract_years(raw_date_fields: list[str | None]) -> set[str]:
    """Extract four-digit years from explicit publication-date fields only.

    Callers must pass only fields the import format mapped as
    publication/issued/online/print date -- never import/accession/
    current-year or database deposit date (spec §3.1 Year rule).
    """
    years: set[str] = set()
    for field in raw_date_fields:
        if not field:
            continue
        match = _FOUR_DIGIT_YEAR_RE.search(field)
        if match:
            years.add(match.group(0))
    return years


def normalize_first_author(raw_authors: list[str]) -> str | None:
    """Normalize the first listed author's family-name component.

    Expects each author string already split by the importer (one list
    item per author, order preserved). This function takes the first
    item and treats it as already the family-name-bearing token when the
    importer could not reliably separate given/family names; callers that
    have a structured family name should pass that directly as the sole
    list item. Returns ``None`` if no first author is available.
    """
    if not raw_authors:
        return None
    first = raw_authors[0]
    if not first or not first.strip():
        return None
    value = unicodedata.normalize("NFKC", first).casefold()
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def levenshtein(a: str, b: str) -> int:
    """Classic O(len(a)*len(b)) edit-distance, stdlib only (no numpy)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(
                prev[j] + 1,      # deletion
                cur[j - 1] + 1,   # insertion
                prev[j - 1] + cost,  # substitution
            )
        prev = cur
    return prev[-1]


def title_similarity(title_a: str, title_b: str) -> float:
    """``1 - LevenshteinDistance(a, b) / max(len(a), len(b))`` per §3.2.4.

    Inputs must already be normalized titles (non-empty). The result is
    not rounded; rounding happens only for display per the spec.
    """
    max_len = max(len(title_a), len(title_b))
    if max_len == 0:
        return 0.0
    distance = levenshtein(title_a, title_b)
    return 1 - (distance / max_len)


def compute_normalized(fields: dict) -> dict:
    """Compute the normalized comparison-key bundle for one occurrence's
    canonical fields (dedup spec §3.1). Used at import-commit time so
    deduplication never has to re-derive these from raw values later.
    """
    doi = normalize_doi(fields.get("doi") or None)
    title = normalize_title(fields.get("title") or None)
    years = sorted(extract_years([fields.get("year") or None]))
    first_author = normalize_first_author(fields.get("authors") or [])
    return {
        "doi": doi,
        "title": title,
        "years": years,
        "first_author": first_author,
    }

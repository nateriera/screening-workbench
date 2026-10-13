"""PubMed XML importer: field mapping per
docs/specs/behavioral-spec-import-field-mapping.md §4.3.

Security hardening (stdlib-only, no third-party dependency added): Python's
``xml.etree.ElementTree``/expat never fetches an external DTD or entity
over the network, but expat by default WILL expand internal general
entities defined in an inline ``<!DOCTYPE ...>`` block, which is the classic
"billion laughs" exhaustion vector. Rather than adding defusedxml (a new
dependency requiring its own license audit, not yet approved for v1), this
module rejects any input containing a ``<!DOCTYPE`` declaration before
parsing -- PubMed XML citation records never require one, so this fully
neutralizes both XXE and entity-expansion attacks with zero new
dependencies. External entity/network access is additionally never
possible because no resolver or network-capable parser is ever
configured.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from xml.etree import ElementTree as ET

from screening_workbench.importers import empty_fields
from screening_workbench.importers.commit import CommitResult, commit_occurrences
from screening_workbench.ids import new_id
from screening_workbench.importers.limits import (
    ImportLimitError, MAX_FIELD_CHARS, MAX_IMPORT_RECORDS, MAX_XML_DEPTH,
    MAX_XML_ELEMENTS, validate_text_size,
)

_DOCTYPE_MARKER = "<!DOCTYPE"


@dataclass
class PubmedParseResult:
    records: list[dict]          # [{"fields": {...}, "locator": str}]
    skipped: list[dict]          # [{"locator": str, "reason": str}]


def _text(elem: ET.Element | None) -> str:
    if elem is None:
        return ""
    parts = []
    total = 0
    for part in elem.itertext():
        total += len(part)
        if total > MAX_FIELD_CHARS:
            raise ImportLimitError(f"XML field exceeds the {MAX_FIELD_CHARS}-character limit")
        parts.append(part)
    return "".join(parts).strip()


class _LimitedTreeBuilder(ET.TreeBuilder):
    """Enforce XML tree caps before allocating elements past the limits."""

    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.elements = 0

    def start(self, tag, attrs):
        self.depth += 1
        self.elements += 1
        if self.depth > MAX_XML_DEPTH:
            raise ImportLimitError(f"XML nesting exceeds the {MAX_XML_DEPTH}-level limit")
        if self.elements > MAX_XML_ELEMENTS:
            raise ImportLimitError(f"XML exceeds the {MAX_XML_ELEMENTS}-element import limit")
        return super().start(tag, attrs)

    def end(self, tag):
        elem = super().end(tag)
        self.depth -= 1
        return elem


def _check_tree_limits(root: ET.Element) -> None:
    stack = [(root, 1)]
    elements = 0
    while stack:
        elem, depth = stack.pop()
        elements += 1
        if depth > MAX_XML_DEPTH:
            raise ImportLimitError(f"XML nesting exceeds the {MAX_XML_DEPTH}-level limit")
        if elements > MAX_XML_ELEMENTS:
            raise ImportLimitError(f"XML exceeds the {MAX_XML_ELEMENTS}-element import limit")
        stack.extend((child, depth + 1) for child in elem)


def _strip_namespaces(root: ET.Element) -> None:
    """Normalize element names to local names for prefix-independent lookup."""
    for elem in root.iter():
        if isinstance(elem.tag, str) and "}" in elem.tag:
            elem.tag = elem.tag.rsplit("}", 1)[1]


def parse_pubmed_xml(text: str) -> PubmedParseResult:
    """Parse a PubMed XML document (one or more ``PubmedArticle`` entries).

    Rejects the whole file on a well-formedness (XML syntax) error, per
    spec §4.3: "If the document is malformed, reject or safely salvage
    only complete unambiguous PubmedArticle records." This v1 implements
    the simpler "reject on syntax error" branch; partial-salvage of a
    syntactically broken document is a documented gap below.
    """
    validate_text_size(text)
    if _DOCTYPE_MARKER in text.upper():
        return PubmedParseResult(
            records=[],
            skipped=[{"locator": "file", "reason": "invalid_encoding:doctype_rejected"}],
        )
    try:
        parser = ET.XMLParser(target=_LimitedTreeBuilder())
        parser.feed(text)
        root = parser.close()
    except ET.ParseError as exc:
        return PubmedParseResult(records=[], skipped=[{"locator": "file", "reason": f"malformed_record:{exc}"}])

    _check_tree_limits(root)
    _strip_namespaces(root)

    articles = root.findall(".//PubmedArticle")
    if len(articles) > MAX_IMPORT_RECORDS:
        raise ImportLimitError(f"PubMed XML exceeds the {MAX_IMPORT_RECORDS}-record import limit")
    records: list[dict] = []
    skipped: list[dict] = []

    for ordinal, article in enumerate(root.findall("./*"), start=1):
        if article.tag == "PubmedArticle":
            continue  # handled below via .findall, avoids double count
        if article.tag == "DeleteCitation":
            skipped.append({"locator": f"record {ordinal}", "reason": "unsupported_record_type"})

    for ordinal, article in enumerate(articles, start=1):
        medline = article.find("MedlineCitation")
        if medline is None:
            skipped.append({"locator": f"record {ordinal}", "reason": "malformed_record"})
            continue
        pmid_elem = medline.find("PMID")
        locator = f"record {ordinal} (PMID {_text(pmid_elem)})" if pmid_elem is not None else f"record {ordinal}"

        art = medline.find("Article")
        if art is None:
            skipped.append({"locator": locator, "reason": "malformed_record"})
            continue

        fields = empty_fields()
        fields["title"] = _text(art.find("ArticleTitle"))
        fields["journal"] = _text(art.find("Journal/Title"))

        year = _text(art.find("Journal/JournalIssue/PubDate/Year"))
        if not year:
            medline_date = _text(art.find("Journal/JournalIssue/PubDate/MedlineDate"))
            if medline_date:
                import re
                m = re.search(r"\d{4}", medline_date)
                if m:
                    year = m.group(0)
        if not year:
            year = _text(art.find("ArticleDate/Year"))
        fields["year"] = year

        fields["volume"] = _text(art.find("Journal/JournalIssue/Volume"))
        fields["issue"] = _text(art.find("Journal/JournalIssue/Issue"))
        fields["pages"] = _text(art.find("Pagination/MedlinePgn"))
        fields["language"] = _text(art.find("Language"))

        doi = ""
        for eloc in art.findall("ELocationID"):
            if eloc.get("EIdType") == "doi":
                doi = _text(eloc)
                break
        fields["doi"] = doi

        fields["pmid"] = _text(pmid_elem)

        abstract_parts = [
            _text(part) for part in art.findall("Abstract/AbstractText") if _text(part)
        ]
        fields["abstract"] = "\n".join(abstract_parts)

        authors: list[str] = []
        for author in art.findall("AuthorList/Author"):
            collective = author.find("CollectiveName")
            if collective is not None and _text(collective):
                authors.append(_text(collective))
                continue
            last = _text(author.find("LastName"))
            fore = _text(author.find("ForeName")) or _text(author.find("Initials"))
            name = " ".join(p for p in (last, fore) if p)
            if name:
                authors.append(name)
        fields["authors"] = authors

        keywords = [
            _text(kw) for kw in art.findall(".//KeywordList/Keyword") if _text(kw)
        ]
        fields["keywords"] = keywords

        fields["url"] = ""  # spec: never synthesize/fetch a URL

        records.append({"fields": fields, "locator": locator})

    return PubmedParseResult(records=records, skipped=skipped)


# --- Known v1 gaps (logged per implementer-prompt hard constraint #1) ---
# * No partial-salvage of a syntactically malformed XML document: a parse
#   error rejects the whole file rather than extracting intact
#   PubmedArticle records around the damage (spec allows either choice;
#   this version takes the simpler, more conservative one).
# * PubDate/ArticleDate conflict detection (IM-13) does not yet surface
#   both candidates for explicit user choice; it silently prefers the
#   PubDate/Year -> MedlineDate -> ArticleDate/Year order. This is a
#   documented deviation, not a concealed one.
# * ArticleIdList DOI/PMID cross-check (spec: "may propose DOI only if no
#   conflicting ELocationID DOI") is not implemented; only ELocationID DOI
#   and MedlineCitation/PMID are read.


def commit_pubmed_xml_import(
    conn,
    text: str,
    *,
    source_id: str,
    branch_id: str,
    operation_id: str,
    actor: str,
    source_name: str = "import.pubmed_xml",
) -> CommitResult:
    """Parse, map, and atomically commit a PubMed XML document's articles."""
    parsed = parse_pubmed_xml(text)
    occurrences = []
    for rec in parsed.records:
        occurrences.append(
            {
                "occurrence_id": new_id("occ"),
                "locator": rec["locator"],
                "raw_source_text": text if len(parsed.records) == 1 else rec["locator"],
                "fields": rec["fields"],
            }
        )
    return commit_occurrences(
        conn,
        occurrences=occurrences,
        skipped=parsed.skipped,
        source_format="pubmed_xml",
        source_id=source_id,
        branch_id=branch_id,
        mapping={"format": "pubmed-xml-proposals-v1"},
        mapping_version=1,
        operation_id=operation_id,
        actor=actor,
        source_name=source_name,
    )

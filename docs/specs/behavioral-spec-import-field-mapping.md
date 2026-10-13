# Screening Workbench v1 import field-mapping behavioral specification

**Status:** Clean-room behavioral specification; testable requirements, not implementation.  
**Source cutoff / access date:** 2026-10-06.  
**Scope:** Maps records imported from CSV, RIS, and PubMed XML into Screening Workbench's canonical fields. No incumbent product UI, code, or assets were accessed.
**Compatibility boundary:** Product-brief scope names CSV (Zotero-friendly dialect), RIS, and PubMed XML. BibTeX appears in an existing artifact 01, but **BibTeX is excluded from v1** unless the product owner explicitly expands scope. This spec does not describe BibTeX detection or parsing.

## 1. Purpose and requirements provenance

The importer turns source-format fields into Screening Workbench canonical fields while keeping original source evidence, surfacing uncertainty, and making the mapping inspectable before records are committed. The product context requires CSV/RIS/PubMed XML, source-field-to-canonical mapping visibility, read/skipped record counts with reasons, unmapped-field visibility, and append-only import batches. The canonical fields below are fixed by supplied project context. The detailed parser rules and UX-independent behaviors are conservative first-principles proposals where public format documentation does not dictate application behavior.

Clean-room rule: use public format standards/documentation and the supplied project brief only. Do not reproduce another product's interface, language, mappings, or behavior. Parser compatibility choices below are Screening Workbench proposals, not claims about any other importer.

## 2. Canonical model and invariants

### 2.1 Canonical fields

Every committed source record has these canonical fields, even if their values are empty:

| Canonical field | Logical value shape | Mapping and preservation rule |
|---|---|---|
| `title` | Single text | One selected source value. Multiple conflicting candidates require explicit choice or remain unmapped. |
| `authors` | Ordered list of author strings | Preserve author order and each source author as a distinct item where the format expresses repetition. Never split a single author string on commas without an explicit CSV mapping/parse choice. |
| `journal/source` | Single text | Journal/container/source title. Preserve full source string; do not abbreviate or infer. |
| `year` | Single year string | Preserve source year token; derive a year only from a clearly identified publication date using the format rules in §4. No import/accession/current-year fallback. |
| `volume` | Single text | Preserve formatting including leading zeros and supplements. |
| `issue` | Single text | Preserve formatting including leading zeros. |
| `pages` | Single text | Preserve a source range or pagination expression. Combine start/end only under §4; don't numerically normalize. |
| `DOI` | Single text | Preserve raw DOI spelling in source evidence; canonical value may trim whitespace and a leading resolver/`doi:` prefix, but must not discard a value or silently select among conflicting DOI candidates. |
| `PMID` | Single text | Preserve as text (including leading zeros if present); do not coerce to a number. |
| `abstract` | Text | Preserve meaningful whitespace/line breaks as far as canonical storage permits; do not summarize or rewrite. |
| `keywords` | Ordered list of strings | Preserve repeated values and order. For CSV, list splitting requires explicit delimiter/configuration; otherwise keep the cell as one value. |
| `language` | Single text | Preserve source code/label exactly; no unrequested translation or normalization. |
| `URL` | Single text | Preserve the selected source URL as text; do not fetch it. |
| `import batch` | System-generated batch reference | Set by Screening Workbench to the new batch; never map an input column/tag into this field. |
| `raw source line` | Source evidence reference/text | Preserve exact source row/line or XML record fragment plus file/record locator. It is system-generated, not user-mapped. |

An empty source value maps to an empty canonical value; it does not erase a nonempty value from an earlier batch. Values and provenance from earlier batches are retained. Conflicting values from separate imports remain attributable to their batch and source field; import mapping must not silently overwrite a previously imported value. How a later user-facing record view chooses a preferred display value is outside this mapping spec, but every source value must remain recoverable.

### 2.2 Source provenance and batches

- Each import creates a new immutable `ImportBatch` with a unique ID, source format/name, source class, branch, import timestamp, mapping configuration/version, and counts. Source class/branch classification is required before commit as specified in the PRISMA import contract; this is review provenance, not bibliographic field mapping.

- Every imported record/value retains batch ID and source locator (CSV logical row and column/header; RIS record number and tag occurrence; PubMed XML record ordinal and element path).
- Re-importing the same file creates a **new batch** and appends new source records when the user explicitly starts a new import. A retry of an uncommitted import operation uses its operation ID and commits atomically at most once; a deliberate subsequent import creates new record-occurrence IDs. It must not overwrite or merge into a prior batch as an implicit side effect. Any later duplicate detection is a separate workflow and is not a mapping operation.
- Store an input fingerprint if available for audit/re-import identification, but do not use it to suppress a requested import occurrence.
- Raw source evidence is preserved locally. Mapping/preview must not require an internet connection.

## 3. Import lifecycle and observable behavior

1. **Identify format.** Screening Workbench accepts CSV, RIS, or PubMed XML only. Extension is a hint, not proof. Content that does not parse as the selected/recognized format is rejected with a plain reason. Never reinterpret an unsupported/ambiguous file as BibTeX.
2. **Parse to staging.** Decode and parse without creating records. Preserve original text bytes or an equivalent faithful raw representation where practical, plus record/field locators. No partial batch is visible as committed data.
3. **Propose mappings.** Show every source field/tag/path encountered, its proposed canonical destination (or “unmapped”), how many records contain a value, and example values. The user can review and change mappings before commit. System fields `import batch` and `raw source line` are shown as Screening Workbench-generated, not candidates for source mapping.
4. **Resolve ambiguity.** A one-to-one source-to-canonical mapping is the default. Multiple source fields aimed at a single-valued canonical field, multiple possible source fields for `title`, or uncertain headerless CSV interpretation must be explicitly resolved or left unmapped. Repeatable author/keyword occurrences can be combined in order under one destination.
5. **Preview record outcomes.** Show records expected to be read, skipped, and why; show unmapped fields and the count of nonempty values affected. Show field-level examples and conflicts, not merely a success total.
6. **Commit or cancel.** Commit creates the batch and all accepted records atomically. Cancel, parse failure, or persistence failure creates no partial batch or records. Report a recoverable error and allow a fresh attempt.
7. **Report outcome.** After commit, show records read/created, skipped with categorized reasons, unmapped source fields and affected-value counts, selected mapping summary, and batch identity. A zero-record file can be imported only if it is valid and the user confirms; report zero read and the reason.

“Read” means a source record was structurally parsed and accepted into the staged record set. A record missing optional bibliographic data is still read; missing optional fields alone do not make it skippable. “Skipped” means an individual record was not committed, and it must have a specific reason. File-level rejection is distinct from a successfully parsed batch with skipped records.

## 4. Format-specific mapping rules

### 4.1 CSV

RFC 4180 describes a common CSV form (comma-separated fields, quoted fields, doubled quote escapes, and records/lines with consistent field counts) but explicitly does not establish one universal CSV dialect.[S1] Screening Workbench therefore supports a visible, conservative profile:

- Recognize comma delimiter by default; allow user selection among comma, tab, semicolon, or pipe only when preview provides a consistent parse. Do not silently guess a delimiter when two parses are plausible.
- Support quoted fields, embedded delimiters, doubled quotes, CRLF and commonly encountered LF line endings. A quoted multiline cell is part of one logical record, not multiple records. Do not treat physical line number as CSV row number after multiline fields.
- UTF-8 is preferred. If decoding fails, offer supported alternate encodings only through explicit user choice; never silently replace invalid bytes. Preserve raw bytes/text evidence.
- First logical record is treated as a header only if the parser detects a plausible header row or the user confirms it. Headerless CSV requires explicit user selection of “first row is data” plus positional mapping; do not infer field meaning from cell values alone.
- Header names are shown verbatim. Case/whitespace-insensitive matching may propose mappings for clear aliases (e.g., `title`, `author`, `journal`, `year`, `doi`, `pmid`, `abstract`, `keywords`, `url`), but aliases are proposals only. Unknown/ambiguous headers remain unmapped until reviewed. Similarity alone never auto-assigns a canonical field.
- Duplicate header names are distinct source columns identified by ordinal. A blank header is labeled by position, e.g. column 4 (unnamed); never discarded invisibly.
- Each data row is one source record. A row with too many/few fields is malformed: quarantine/skip that row with its logical row number and reason; do not shift columns or silently pad/truncate. Blank rows are ignored and counted separately as blank lines, not bibliographic records.
- Repeated authors or keywords in a cell remain a single raw cell unless the user explicitly selects a split delimiter. If split is chosen, apply it consistently and preserve order; a delimiter inside quoted CSV syntax is already decoded as cell content and must not be confused with the CSV structural delimiter.
- If an explicit mapping assigns more than one column to `title`, `year`, `DOI`, `PMID`, `journal/source`, or another single-valued field, require a source priority/choice or leave the field unmapped. Do not concatenate arbitrary columns.

### 4.2 RIS

RIS is a tagged text format with repeated field tags and record boundaries. Public RIS descriptions document common structures/tags, but RIS exports vary and the original vendor documentation link is not reliably available: search results reported the former RefMan URL redirects to a general support page rather than the format specification. A public community-maintained RIS parser specification and RefDB manual remain accessible references, not a normative standards authority.[S2][S3]

- Recognize a record beginning at `TY` and ending at `ER`, case-insensitively for the two-letter tag only; preserve original spelling and lines. Accept one or two spaces before the dash as a compatibility choice; record this relaxed parsing in mapping diagnostics. Do not require a fixed order for descriptive tags.
- `TY` identifies record type; it is structural and is not mapped to a canonical bibliographic field. Missing `ER`, nested/new `TY` before an `ER`, malformed tag lines, or content outside a record are reported. Recover only when the next unambiguous `TY` gives a safe boundary; otherwise skip the damaged record with reason. Never silently drop a malformed record.
- Repeated `AU` and `A1` values are treated as ordered author occurrences, preserving order and source tag. Do not include `A2`/editor or later-author categories in `authors` by default; they remain unmapped unless the user explicitly maps them to an available canonical field (none is editor-specific) or elects to append them to authors with that lossy semantic choice stated.
- Proposed common mappings: `TI`/`T1` → title; `JO`/`JF`/`JA`/`J2`/`T2` → journal/source (context varies); `PY`/`Y1` → year; `VL` → volume; `IS` → issue; `SP` plus `EP` → pages; `DO` → DOI; `UR`/`LK` → URL; `AB`/`N2` → abstract; `KW` → keywords; `LA` → language; `AN` → PMID only when value is explicitly a PubMed identifier or user confirms that mapping. These are proposals displayed for review, not unconditional equivalences.[S2][S3]
- Context-sensitive or less portable tags (including `BT`, `M1`–`M3`, `SN`, `DB`, `ID`, custom tags) are unmapped by default unless an unambiguous context-specific rule is known and presented. In particular `SN` can mean ISSN or ISBN and must not be guessed as journal/source or identifier.
- `PY`/`Y1` date strings: map only an unambiguous four-digit leading publication year. Preserve full raw date token in source evidence; canonical `year` is the year token. If a tag contains no clear four-digit year, leave it unmapped and explain.
- Pages: if only `SP` is present, map its full value to pages. If both `SP` and `EP` are present and non-conflicting, combine as `SP-EP` (with a single en dash not required; proposed canonical separator is ASCII hyphen). If `SP` itself already expresses a range, do not append `EP` without review. Conflicts/duplicate competing page tags require user choice or remain unmapped.
- For competing synonyms (e.g., both `TI` and `T1` with different values), equal values may be treated as one logical value with both provenances shown; differing values require explicit choice or leave title unmapped. No first-wins/last-wins behavior for conflicting single-valued fields.
- Lines continuing a previous field are appended to that field with a newline only when parser can identify an active tag unambiguously. Orphan continuation lines are reported and retained in raw evidence, not attached to a guessed field.

### 4.3 PubMed XML

Use the NCBI PubMed XML DTD documentation and annotated element descriptions as the structural reference; XML elements and allowed content can evolve across DTD versions.[S4][S5]

- Accept a well-formed XML document containing one or more `PubmedArticle` entries, including a PubMed article-set wrapper. Identify each record by its document ordinal and PMID when present.
- Parse namespace-aware XML; do not depend on prefixes. Disable external entity resolution and network DTD fetching. XML entities must not trigger filesystem/network access. If the document is malformed, reject or safely salvage only complete unambiguous `PubmedArticle` records; list every excluded fragment/record and reason. No partial successful count may conceal a parse failure.
- Proposed element mappings (XPath-like paths use local element names):
  - `MedlineCitation/Article/ArticleTitle` → title.
  - `MedlineCitation/Article/AuthorList/Author` entries → authors in document order; preserve collective `CollectiveName` or combine `LastName`, `ForeName`, `Initials`, and suffix without guessing a missing name component. Preserve source substructure for reconstruction.
  - `MedlineCitation/Article/Journal/Title` → journal/source.
  - Publication date: `MedlineCitation/Article/Journal/JournalIssue/PubDate/Year`, or `MedlineCitation/Article/Journal/JournalIssue/PubDate/MedlineDate` only when its first year is unambiguous, or `ArticleDate/Year` when no journal publication year is available. Prefer explicit journal PubDate Year; if candidate dates conflict, show candidates and require mapping preference or leave year empty. Never derive year from `DateCompleted`, `DateRevised`, or import time.
  - `JournalIssue/Volume` → volume; `JournalIssue/Issue` → issue.
  - `Pagination/MedlinePgn` → pages as given; do not split or normalize.
  - `ELocationID` with `EIdType="doi"` → DOI; preserve other ELocationID types as unmapped source values.
  - `MedlineCitation/PMID` → PMID.
  - `Article/Abstract/AbstractText` → abstract; concatenate repeated sections in source order, preserving section labels as text (e.g., `Label` attribute plus content) and paragraph boundaries. Do not truncate silently.
  - `MeshHeadingList`/`KeywordList` values are not keywords by default: map only `KeywordList/Keyword` → keywords. MeSH terms remain unmapped because they are controlled-vocabulary indexing and not necessarily author keywords.
  - `Article/Language` → language (repeated values require explicit handling; do not silently choose one if conflicting).
  - `PubmedData/ArticleIdList/ArticleId` with `IdType="doi"` may propose DOI only if no conflicting `ELocationID` DOI; with `IdType="pubmed"` may propose PMID only if consistent with `MedlineCitation/PMID`. Conflicts are shown and block automatic single-value selection.
  - `Article/ELocationID` of type `pii` and `PubmedData/ArticleIdList` identifiers of other types are unmapped by default.
  - PubMed XML does not provide a general article URL field with a guaranteed canonical web URL. Do not synthesize or fetch a URL; leave `URL` empty unless an explicit source element and user mapping supplies one.
- Preserve mixed XML content as readable text without losing text content. Keep original XML fragment as raw source evidence. Unsupported elements and attributes are counted/listed as unmapped where they contain nonempty bibliographic data; structural wrapper elements are not presented as unmapped field values.
- A `DeleteCitation` entry or non-article entry is not an importable citation record for this v1 behavior: skip with explicit record-type reason. It is not treated as deletion of an existing Screening Workbench record.

## 5. Mapping conflicts, validation, and malformed input

- Mapping is explicit and reversible before commit. Persist the mapping configuration with the batch so later audit can reproduce how source fields were assigned.
- Never use a source value to execute code, resolve a URL, or access a path. Treat all imported text/XML content as untrusted data. Do not render source HTML as active markup.
- Canonical type validation is conservative. Preserve arbitrary text; flag suspicious but parseable values rather than silently correcting them. `year` must be a recognizable year string to map automatically; otherwise keep it unmapped. DOI/PMID remain text and do not fail solely due to unfamiliar punctuation/format.
- Empty values and whitespace-only values are displayed as empty and do not overwrite earlier data. Do not strip interior whitespace from abstracts or alter punctuation in titles/authors.
- Duplicate source field values are retained. For a repeated source value mapped to a single-valued target: identical values can collapse to one displayed canonical value with all source provenance; conflicting values require selection or remain unmapped. Never choose first/last occurrence silently.
- Unmapped report includes every encountered nonempty source field/tag/path, occurrence count, and example(s). Empty-only unknown fields may be listed with zero nonempty values. User may leave them unmapped; importer must not discard raw evidence.
- A file-level structural failure yields a rejected-file result, not a batch with invented zero records. A record-level failure yields a skipped record plus reason if other records can be safely parsed. If safe boundaries cannot be established, reject the file rather than claim a trustworthy partial import.
- Skipped-reason vocabulary is stable and machine-readable, including at least: `malformed_record`, `missing_record_boundary`, `column_count_mismatch`, `unsupported_record_type`, `invalid_encoding`, `ambiguous_mapping`, `conflicting_single_value`, and `empty_nonrecord` (the latter reported outside bibliographic skipped count).

## 6. Acceptance tests

A release passes only when tests assert both visible import report and stored records/provenance. Use fixtures with expected mappings explicitly written; no network access.

| ID | Fixture / action | Required result |
|---|---|---|
| IM-01 | Import valid CSV with headers for title, authors, journal, year, DOI, abstract, keywords, language, URL | Mapping preview shows each source-to-canonical proposal and samples; accepted records contain expected values and raw row/header provenance. |
| IM-02 | CSV quoted comma, doubled quote, embedded newline, CRLF and LF | Values parse without splitting a logical record; raw row locator is logical row and source evidence is preserved. |
| IM-03 | CSV has unknown, blank, and duplicate headers | All columns appear distinctly (ordinal shown); unknown/blank columns are listed unmapped with nonempty counts; no silent loss. |
| IM-04 | Headerless CSV with plausible but ambiguous columns | Import pauses for header/data and positional mapping selection; no semantic auto-mapping based only on sample values. |
| IM-05 | CSV row has too few/too many cells among valid rows | Valid records stage correctly; malformed row is skipped with logical row and `column_count_mismatch`; no shifted values. |
| IM-06 | CSV contains repeated author/keyword values separated by comma inside a quoted cell | Cell stays intact unless user explicitly chooses a list delimiter; chosen split preserves order and original raw cell. |
| IM-07 | CSV maps two different nonidentical columns to title | Preview blocks commit until priority is chosen or mappings are left unresolved; no silent concatenation/first-wins. |
| IM-08 | RIS standard-style records with repeated AU, KW and tags in varying order | Record boundaries and occurrence order preserved; proposed mappings shown; TY is structural, not a canonical field. |
| IM-09 | RIS has one-space tag delimiter, missing ER, nested TY, orphan line, unknown tag | Supported relaxed spacing is noted; recoverable damage is reported with affected record/reason; unknown values remain in unmapped list/raw evidence. Unrecoverable boundary ambiguity rejects file. |
| IM-10 | RIS has conflicting TI/T1, PY/Y1, or multiple DOI values | Conflict is visible; requires explicit source choice or stays unmapped; no last-tag-wins. |
| IM-11 | RIS SP plus EP, SP-only full range, and already-ranged SP plus EP | First combines as specified; SP-only remains intact; ambiguous range is not doubled and requires review. |
| IM-12 | Valid PubMed XML article with nested/mixed ArticleTitle, multiple authors, labeled abstract sections, DOI and PMID | Exact text, author order, labels, identifiers and paths are retained; expected canonical mapping occurs. |
| IM-13 | PubMed XML has conflicting PubDate and ArticleDate year | Candidates and provenance are displayed; published year preference follows explicit policy or remains empty; no completion/revision date is used. |
| IM-14 | PubMed XML has mismatched DOI/PMID duplicate identifiers | No conflicting identifier is silently selected; conflict blocks that single canonical mapping and is reported. |
| IM-15 | XML has external entity/DTD URL, malformed record, DeleteCitation, and MeSH-only terms | No external access/entity expansion; safe record/file failure reported; DeleteCitation is skipped, not applied as deletion; MeSH not mapped to keywords. |
| IM-16 | Unknown RIS tag, CSV column, and nonempty PubMed XML element | Each appears in unmapped-field report with occurrence count/sample; raw provenance remains available. |
| IM-17 | Import same input twice | Two distinct append-only batches and their source records are retained; prior values are not overwritten; each batch has its own report. |
| IM-18 | Cancel preview, fail before commit, then retry | Cancel/failure leaves no partial batch/records; retry can commit cleanly once. |
| IM-19 | Valid file with all records malformed, empty file, or blank rows only | Distinguish rejected file, zero-record valid import, skipped records, and blank lines; counters are internally consistent and never misleading. |
| IM-20 | Disable network and import fixtures | Format identification, preview, mapping, commit, record inspection and report work offline; no URL fetch, external DTD fetch, telemetry, or account is required. |
| IM-21 | Re-import after mapping configuration changes | New batch captures its own mapping configuration/version; prior batch mapping and values remain unchanged. |
| IM-22 | Import filename ends `.bib` or content resembles BibTeX | Reject as unsupported v1 format with explicit message; do not attempt BibTeX parsing. |

### Required count invariants

- `records_read = records staged and committed` for a successful batch.
- `records_skipped` counts individual source citation records excluded from commit, each with exactly one primary reason; blank CSV lines and XML wrappers are not citation records.
- `records_read + records_skipped` equals identified bibliographic source record occurrences when boundaries are trustworthy. If not trustworthy, reject the file and mark totals unavailable rather than fabricate them.
- Unmapped-field counts refer to source field occurrences/records with nonempty data, not canonical records lost.
- Append import does not imply deduplication or overwrite. Every committed source record remains traceable to exactly one import occurrence/batch.

## 7. Offline, privacy, and accessibility

- Import, format parsing, mapping preview/editing, commit, batch inspection, and unmapped/skipped reporting MUST work with networking disabled. No network requests, remote parsers, analytics, cloud accounts, or external enrichment are prerequisites.
- PubMed XML DTD validation, if used, must use a locally bundled/versioned known DTD or be omitted; never fetch the DTD or any entity over the network during import. Unsupported DTD versions produce a visible compatibility warning, not remote resolution.
- Source files and parsed metadata remain on the user's device under Screening Workbench's local-first product requirement. Any future optional upload/enrichment is outside this v1 spec and requires separate explicit consent.
- Imported content is untrusted. Prevent XML external entity attacks, path traversal, script/HTML execution, and resource exhaustion. Bound file size, record count, nesting depth, and field size with a clear failure report; limits must not silently truncate records/values.
- All mapping controls, skipped/unmapped inspection, and commit/cancel actions are keyboard-operable. Focus is visible; preview tables have meaningful headers and reading order; status changes announce record counts and failures without stealing focus. These are accessibility requirements proposed from first principles, not format-standard mandates.

## 8. Decisions requiring owner confirmation / empirical validation

The following choices are explicit proposals rather than externally established requirements: supported CSV delimiter options/encoding fallbacks; alias dictionary; RIS relaxed one-space syntax and tag mappings; ambiguous-date precedence; XML DTD version support; author/keyword representation in persistence; parser size limits; malformed-input recovery policy; and exact diagnostics text. Before release, the product owner should approve the alias set and fallback policy. Test fixtures should cover actual permitted export samples without using competitor applications or UI as research sources. BibTeX remains excluded until scope is explicitly changed.

## 9. Public sources

Sources are public format standards/documentation only. Accessed 2026-10-06. Public documentation supports format structure; Screening Workbench-specific mapping and workflow rules are identified above as product proposals.

- **[S1] IETF RFC 4180, “Common Format and MIME Type for Comma-Separated Values (CSV) Files.”** Informational RFC, October 2005. Documents a common CSV format and notes variation among implementations. https://www.rfc-editor.org/rfc/rfc4180.html
- **[S2] gris, “RIS file format specification.”** Public community-maintained documentation, accessed 2026-10-06. Describes tagged records, record delimiters, repeated tags, common tag meanings and examples; not a formal standards-body specification. https://gris.readthedocs.io/en/latest/specification.html
- **[S3] RefDB Manual, Chapter 7, “Data input.”** Public documentation of RIS rules/tag mappings and examples, accessed 2026-10-06. https://refdb.sourceforge.net/manual/ch07.html. **Availability caveat:** Search results indicate the former original RefMan RIS documentation URL redirects to a general EndNote support page rather than serving the original specification; the original vendor document was not relied on as directly accessible normative text.
- **[S4] NCBI, “PubMed DTD Documentation,” current indexed DTD documentation (`pubmed_250101.dtd`).** Describes PubMed XML elements, attributes, content models and examples; NCBI notes DTD structure can change by year. https://dtd.nlm.nih.gov/ncbi/pubmed/doc/out/250101/index.html
- **[S5] NLM, “MEDLINE/PubMed XML Data Elements.”** Public element documentation for the 2018 production-year DTD; useful as a complementary description, but not a substitute for checking the DTD version of an input file. https://www.nlm.nih.gov/bsd/licensee/data_elements_doc.html

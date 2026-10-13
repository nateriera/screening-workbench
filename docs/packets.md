# Screening Workbench v1 — Reviewer packets (two-computer blind review)

**Status:** implemented 2026-10-07 (Directive B). Independent, clean-room
implementation of the behavioral pattern described by the directive as
prior art ("Evidentum, MIT") — the behavior pattern only ("a host exports
a blinded record set, a second reviewer screens it offline on another
machine, exports only their own votes, the host merges them back") was
the stated motivation. No external specification, source code, UI, or
text from any incumbent product was read, inspected, or copied to build
this feature; every format, field name, and merge rule below is an
original design decision ("Hermes's choice", per the directive), not a
transcription of someone else's implementation. This follows the same
clean-room discipline as `docs/specs/behavioral-spec-duplicate-detection.md`
and the teardown-analyst process (`docs/process/agent-prompt-teardown.md`).

Implementation: `src/screening_workbench/packets.py`. Tests: `tests/test_packets.py`
(13 tests, all passing alongside the full 227/227 suite as of this round).

## Why

Screening Workbench is local-first: there is no server, account system, or shared
database between reviewers. For a genuine two-reviewer blind screen
split across two separate machines/installs, the only viable local-first
pattern is file exchange — and the file exchanged in each direction must
not leak information the reviewer or the host isn't supposed to see yet.

## Two file formats

Both are self-contained JSON files (not a Screening Workbench `.sqlite` project file —
sending the whole database would leak every reviewer's votes).

### 1. Reviewer packet — `cull-reviewer-packet` v1 (the existing versioned wire-format identifier; unchanged for compatibility)

Produced by `packets.export_packet(conn, path, actor=...)` on the host.
One file, portable to a USB stick/email/cloud drive, containing:

The packet is an unencrypted export containing record content. The votes
file is unsigned JSON: its reviewer ID and vote timestamps are claims in
the file, not authenticated identity or proof of origin. The host should
verify who supplied a votes file before merging it. Use only a transfer
channel approved for the review's data.

```json
{
  "format": "cull-reviewer-packet",
  "format_version": 1,
  "packet_id": "packet_...",
  "exported_at": "2026-10-07T...Z",
  "exported_by": "<host actor>",
  "project": {"name": "...", "review_type": "..."},
  "criteria": {"exclusion_reasons": ["Wrong population", "..."]},
  "records": [
    {
      "occurrence_id": "occ_...",
      "batch_id": "batch_...",
      "source_id": "src_...",
      "source_name": "...",
      "source_class": "database",
      "branch_id": "branch_...",
      "branch_name": "...",
      "locator": "...",
      "fields": {"title": "...", "authors": "...", "year": "...", "...": "..."}
    }
  ]
}
```

**What is deliberately absent:** `screen_votes`, `reviewer_id`,
`decision`, `reason`, any decision timestamp, duplicate-group state,
conflict state, PRISMA counts, audit log, other reviewers' identities.
The query that builds `records` (`export_packet`) never touches
`screen_votes` at all — there is no vote data to accidentally include,
not just a field filtered out after the fact. This is the hard blind
guardrail; `tests/test_packets.py::test_export_packet_leakage_scan_zero_vote_data`
casts real votes with distinctive marker strings before exporting and
scans the raw file text to confirm none of it appears.

**Known v1 gap, named not silently dropped:** `raw_source_text` and
normalized dedup comparison keys are not carried into the packet (the
importer on B's side writes empty placeholders for them). B's copy is
screenable but does not support running dedup detection against its own
import — not needed for the packet workflow, since the packet always
ships the host's already-deduplicated active record set.

### 2. Votes export — `cull-votes-export` v1 (the existing versioned wire-format identifier; unchanged for compatibility)

Produced by `packets.export_votes(conn, path, reviewer_id=..., actor=...)`
on reviewer B's machine. One reviewer's current votes only:

```json
{
  "format": "cull-votes-export",
  "format_version": 1,
  "export_id": "votesexp_...",
  "reviewer_id": "reviewerB",
  "stage": "title_abstract",
  "exported_at": "2026-10-07T...Z",
  "votes": [
    {"occurrence_id": "occ_...", "decision": "include", "reason": null, "created_at": "2026-10-07T...Z"}
  ]
}
```

`created_at` is the **original vote timestamp**, not the export time —
required so the host's merge can apply newest-wins correctly (below).
Nothing else is included: no record content, no criteria, no other
reviewer's votes.

## Reviewer-identity lock

`packets.import_packet(conn, path, reviewer_id=...)` on a fresh database
(Directive B §2) permanently binds that database's `project_settings.locked_reviewer_id`
to the given `reviewer_id` and records `packet_imported_id`. A second
`import_packet` call on that same database — for any reviewer, including
the same one — is refused (`ValueError`). `packets.export_votes` checks
`locked_reviewer_id` and refuses to export votes under any other
identity (`PermissionError`). This is a data-integrity lock, not a UI
login; v1 has no password/account layer.

## Merge rule — newest-wins (Nate's accepted default)

`packets.merge_votes(conn, path, actor=...)` on the host (Conflicts
tab's unblinded owner view only — `PermissionError` if the caller isn't
the owner, or if the project is still blind):

For each vote in the file, per `(occurrence_id, reviewer_id)`:

1. **Unknown `occurrence_id`** (not present in the host database — a
   foreign or tampered file, or a record removed host-side since the
   packet was cut) → **quarantined**, never merged, never silently
   dropped, never aborting the rest of the merge.
2. **Invalid `decision`**, or `exclude` with no `reason` → **quarantined**
   (`invalid_decision` / `exclude_missing_reason`) — same reasoning as
   (1): a malformed row should not corrupt `screen_votes` or vanish
   without a trace.
3. Otherwise, compare the incoming vote's `created_at` against the
   host's current vote (if any) for that `(occurrence_id, reviewer_id)`
   pair: if the host's existing vote is **the same age or newer**, the
   incoming vote is **skipped as stale** — never overwritten. Only a
   strictly newer incoming vote is merged (superseding the prior one,
   same append-only pattern as every other vote write).

Quarantined rows are persisted to `quarantined_votes` (readable via
`packets.list_quarantined_votes`), not just returned and forgotten —
an owner can inspect what was rejected and why. Every merge, including
zero-effect merges, appends one `votes.merged` audit event summarizing
merged/skipped-stale/quarantined counts and the file's sha256.

**Alternative considered and rejected for v1:** routing every timestamp
collision to manual adjudication instead of newest-wins. Nate's directive
named newest-wins as his default and invited a objection; none was
raised, so newest-wins ships. If that default proves wrong in practice,
timestamp-collision routing to the Conflicts queue is a follow-up, not
a breaking change to the file format.

## Audit trail

Every one of the four actions appends an audit event via the existing
append-only `events` log (`db.append_event`), each including the
exported/imported file's sha256:

| Action | Event type | Where it's appended |
|---|---|---|
| `export_packet` | `packet.exported` | host database |
| `import_packet` | `packet.imported` | reviewer B's database |
| `export_votes` | `votes.exported` | reviewer B's database |
| `merge_votes` | `votes.merged` | host database |

## UI (historical implementation note)

This section described the initial behavior-only implementation. The
four actions are now wired into the Project menu and Conflicts tab; see
`docs/decisions.md` and `docs/ui-convergence-log.md` for dated
implementation records. The unsigned-file origin limitation above
remains applicable.

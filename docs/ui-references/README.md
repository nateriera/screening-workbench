# Screening Workbench tab reference packages

Six synthetic-only UI references created on `implementation/v2` after the Screening Workbench rename. The reference review and original UI convergence loop are complete; later application changes still need their own tests and evidence. Each package includes a self-contained 1280×800 HTML source, PNGs, numbered checklist, and Tk feasibility notes.

| Tab | Package | Primary reference focus |
|---|---|---|
| Conflicts | [conflicts](conflicts/README.md) | Unblinded adjudication evidence plus an explicitly locked blind-on state |
| PRISMA & audit | [prisma-audit](prisma-audit/README.md) | Synthetic PRISMA 2020 flow and append-only audit view |
| Duplicates | [duplicates](duplicates/README.md) | Side-by-side candidate comparison, difference cues, survivor selection, reversible actions |
| Full-text | [full-text](full-text/README.md) | Retrieval states, local PDF indicator, report-level decision/reason flow |
| Studies | [studies](studies/README.md) | Study/report grouping and canonical occurrence/branch selection |
| Maybe re-review | [maybe-re-review](maybe-re-review/README.md) | Current reviewer’s own maybe-votes only |

## Shared review contract

All record text, identifiers, votes, actors, dates, and counts in the references are invented placeholders. The checklists and 0/1/2 scoring describe the completed historical convergence process. Accessibility and blind-review integrity remain requirements for future UI changes.

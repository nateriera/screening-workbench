# Screening Workbench v1 project rules

Use these rules with the product brief and the approved behavioral specifications in `docs/specs/`.

- **Clean-room implementation:** Build only from supplied project materials and public-source specs. Do not access incumbent apps, use private/trial access, or copy proprietary UI text, labels, artwork, layouts, or code. Keep source lists and access dates with each spec.
- **Local-first and sensitive data:** All review state is local. No accounts, telemetry, cloud sync, remote model inference, or network calls during core workflows. The Julia dogfood CSV and all imported reference text are local-only; never commit corpus rows, abstracts, PDFs, databases, or record-level derivatives. Use synthetic fixtures in tests.
- **License gate:** Review actual license files and resolved package trees before adding dependencies. Follow `docs/license-audit.md`; re-audit exact resolved dependencies at integration time. Do not use GPL/AGPL dependencies without a separately explicit owner ruling.
- **Quality:** Use strict test-first development for behavior changes. Blindness, reviewer isolation, audit integrity, parser safety, and PRISMA count consistency are correctness/security boundaries. Run tests locally and report observed results only.
- **Data handling:** Persist source provenance and human decision events; distinguish human decisions from model scores. Derived counts must reconcile to underlying record/report/study state. Avoid exposing one reviewer's screening state to another while blinded.
- **Decision rights:** Nate decides scope changes, license exceptions, consequential external actions, and final acceptance. No merge/publish/release/deploy without explicit approval. Project updates should be sent in this chat.
- **Visual direction:** Use the owner-authorized original first-pass design system in `docs/design-system.md`; preserve its accessibility gates.

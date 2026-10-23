import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from screening_workbench import db, dedup, export, roles, screening, packets
from screening_workbench.importers.csv_importer import commit_csv_import, preview_csv
from screening_workbench.importers.limits import ImportLimitError, read_limited_bytes, validate_json_value
from screening_workbench.importers.pubmed_xml_importer import parse_pubmed_xml
from screening_workbench.importers.ris_importer import parse_ris


class PreReleaseGates(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.conn = db.connect(self.root / "project.sqlite")
        roles.set_owner(self.conn, "owner1")
        self.conn.execute(
            "INSERT INTO branches (branch_id, name, created_at) VALUES ('b1','b1',datetime('now'))"
        )
        self.conn.execute(
            "INSERT INTO sources (source_id, name, class, branch_id, created_at)"
            " VALUES ('s1','s1','database','b1',datetime('now'))"
        )
        self.conn.commit()
        imported = commit_csv_import(
            self.conn, "title\nSynthetic study\n", {0: "title"},
            source_id="s1", branch_id="b1", operation_id="seed", actor="owner1",
        )
        self.occurrence_id = self.conn.execute(
            "SELECT occurrence_id FROM occurrences WHERE batch_id=?", (imported.batch_id,)
        ).fetchone()["occurrence_id"]

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_dedup_candidate_pairs_are_unique_and_streamed(self):
        pairs = dedup._iter_candidate_pairs(
            ["new-a", "new-b"], ["old", "new-a", "new-b"]
        )
        self.assertEqual(
            list(pairs),
            [("new-a", "old"), ("new-a", "new-b"), ("new-b", "old")],
        )

        all_pairs = dedup._iter_candidate_pairs(None, ["a", "b", "c"])
        self.assertEqual(list(all_pairs), [("a", "b"), ("a", "c"), ("b", "c")])

    def test_pair_budget_covers_real_corpus_and_about_7000_records(self):
        self.assertEqual(dedup.MAX_PAIR_COMPARISONS, 25_000_000)
        dedup.ensure_pair_comparison_budget(self.conn, 1_576)
        dedup.ensure_pair_comparison_budget(self.conn, 7_000)

    def test_duplicate_pair_budget_aborts_without_partial_dedup_state(self):
        commit_csv_import(
            self.conn, "title,authors,year\nAnother Study,Smith,2020\nThird Study,Jones,2021\n",
            {0: "title", 1: "authors", 2: "year"}, source_id="s1", branch_id="b1",
            operation_id="budget-seed", actor="owner",
        )
        before = {
            table: self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("events", "dedup_candidates", "duplicate_merges")
        }

        with patch("screening_workbench.dedup.MAX_PAIR_COMPARISONS", 2):
            with self.assertRaises(dedup.PairComparisonLimitError):
                dedup.run_exact_and_fuzzy_detection(self.conn, "system")

        after = {
            table: self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before
        }
        self.assertEqual(after, before)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM occurrences WHERE is_active=1").fetchone()[0],
            3,
        )
        self.assertIn("No duplicate merges or review candidates were created", str(dedup.PairComparisonLimitError()))

    def test_reject_oversized_import_before_committing_any_project_state(self):
        with patch("screening_workbench.dedup.MAX_PAIR_COMPARISONS", 2):
            with self.assertRaises(dedup.PairComparisonLimitError):
                commit_csv_import(
                    self.conn,
                    "title,authors,year\nNew one,Smith,2020\nNew two,Jones,2021\n",
                    {0: "title", 1: "authors", 2: "year"}, source_id="s1", branch_id="b1",
                    operation_id="budget-seed", actor="owner",
                )

        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM occurrences").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0], 1)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0], 2)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM operations").fetchone()[0], 1)

    def test_normal_size_duplicate_detection_preserves_exact_merge_behavior(self):
        imported = commit_csv_import(
            self.conn, "title,authors,year\nSynthetic study,Smith,2020\nSynthetic study,Jones,2020\n",
            {0: "title", 1: "authors", 2: "year"}, source_id="s1", branch_id="b1",
            operation_id="normal-dedup", actor="owner",
        )

        result = dedup.run_exact_and_fuzzy_detection(
            self.conn, "system", batch_id=imported.batch_id,
        )

        self.assertEqual(result.exact_merges, 1)
        self.assertEqual(result.fuzzy_candidates_created, 0)
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM occurrences WHERE is_active=1").fetchone()[0],
            2,
        )

    def test_blind_partial_export_omits_project_wide_artifacts_and_counts(self):
        screening.cast_vote(
            self.conn, occurrence_id=self.occurrence_id, reviewer_id="reviewerA", decision="include"
        )
        screening.cast_vote(
            self.conn, occurrence_id=self.occurrence_id, reviewer_id="reviewerB",
            decision="exclude", reason="private decision",
        )

        package = export.export_package(self.conn, "reviewerA", is_blind=True)

        self.assertIn("decisions.csv", package)
        self.assertNotIn("audit-log.jsonl", package)
        self.assertNotIn("report-study-links.csv", package)
        self.assertNotIn("prisma-flow.svg", package)
        self.assertFalse(any(name.startswith("attachments/") for name in package))
        manifest = json.loads(package["manifest.json"])
        self.assertFalse(manifest["completeness"]["is_complete"])
        self.assertNotIn("counts", manifest)
        self.assertNotIn("attachments", manifest)
        combined = "\n".join(str(value) for value in package.values())
        self.assertNotIn("reviewerB", combined)
        self.assertNotIn("private decision", combined)

    def test_first_vote_activates_blind_mode_lock(self):
        roles.set_blind(self.conn, "owner1", True)
        screening.cast_vote(
            self.conn, occurrence_id=self.occurrence_id, reviewer_id="reviewerA", decision="include"
        )

        with self.assertRaises(PermissionError):
            roles.set_blind(self.conn, "owner1", False)

    def test_pubmed_xml_accepts_default_namespace(self):
        xml = (
            '<PubmedArticleSet xmlns="urn:ncbi:pubmed">'
            "<PubmedArticle><MedlineCitation><PMID>42</PMID><Article>"
            "<ArticleTitle>Namespaced record</ArticleTitle>"
            "</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"
        )

        result = parse_pubmed_xml(xml)

        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["fields"]["title"], "Namespaced record")

    def test_csv_record_limit_is_enforced(self):
        with patch("screening_workbench.importers.csv_importer.MAX_IMPORT_RECORDS", 1):
            with self.assertRaises(ImportLimitError):
                preview_csv("title\none\ntwo\n")

    def test_pubmed_xml_depth_limit_is_enforced(self):
        nested = "<x>" * 5 + "text" + "</x>" * 5
        xml = f"<PubmedArticleSet>{nested}</PubmedArticleSet>"
        with patch("screening_workbench.importers.pubmed_xml_importer.MAX_XML_DEPTH", 4):
            with self.assertRaises(ImportLimitError):
                parse_pubmed_xml(xml)

    def test_pubmed_xml_element_limit_is_enforced(self):
        xml = "<PubmedArticleSet><a/><b/><c/></PubmedArticleSet>"
        with patch("screening_workbench.importers.pubmed_xml_importer.MAX_XML_ELEMENTS", 3):
            with self.assertRaises(ImportLimitError):
                parse_pubmed_xml(xml)

    def test_ris_field_limit_is_enforced(self):
        with patch("screening_workbench.importers.ris_importer.MAX_FIELD_CHARS", 4):
            with self.assertRaises(ImportLimitError):
                parse_ris("TY  - JOUR\nTI  - title too long\nER  - \n")

    def test_json_depth_limit_is_enforced(self):
        with patch("screening_workbench.importers.limits.MAX_JSON_DEPTH", 3):
            with self.assertRaises(ImportLimitError):
                validate_json_value({"a": {"b": {"c": "too deep"}}})

    def test_bounded_file_read_rejects_oversized_input(self):
        path = self.root / "oversized.csv"
        path.write_bytes(b"12345")
        with self.assertRaises(ImportLimitError):
            read_limited_bytes(path, max_bytes=4)

    def test_ris_orphan_diagnostics_are_bounded(self):
        with patch("screening_workbench.importers.ris_importer.MAX_SKIPPED_LINES", 2):
            with self.assertRaises(ImportLimitError):
                parse_ris("orphan one\norphan two\norphan three\n")

    def test_csv_rejects_overwide_row_before_csv_reader_materializes_it(self):
        with patch("screening_workbench.importers.csv_importer.MAX_COLUMNS", 3):
            with self.assertRaises(ImportLimitError):
                preview_csv("a,b,c,d\n1,2,3,4\n")

    def test_packet_import_rejects_non_object_records_as_value_error(self):
        path = self.root / "bad-packet.json"
        path.write_text(json.dumps({
            "format": packets.PACKET_FORMAT, "format_version": 1,
            "packet_id": "p1", "records": [None],
        }), encoding="utf-8")
        with self.assertRaises(ValueError):
            packets.import_packet(self.conn, path, reviewer_id="reviewerA")

    def test_malformed_vote_rows_are_quarantined(self):
        path = self.root / "bad-votes.json"
        path.write_text(json.dumps({
            "format": packets.VOTES_FORMAT, "format_version": 1,
            "reviewer_id": "reviewerA", "votes": [None],
        }), encoding="utf-8")
        result = packets.merge_votes(self.conn, path, actor="owner1")
        self.assertEqual(result["quarantined_count"], 1)

    def test_vote_rows_with_wrong_field_types_are_quarantined(self):
        path = self.root / "bad-vote-types.json"
        path.write_text(json.dumps({
            "format": packets.VOTES_FORMAT, "format_version": 1,
            "reviewer_id": "reviewerA", "votes": [{
                "occurrence_id": ["not", "an", "id"], "decision": "include",
                "reason": ["not", "text"], "created_at": "2026-01-01T00:00:00Z",
            }],
        }), encoding="utf-8")
        result = packets.merge_votes(self.conn, path, actor="owner1")
        self.assertEqual(result["quarantined_count"], 1)

    def test_future_vote_timestamp_is_quarantined(self):
        path = self.root / "future-vote.json"
        path.write_text(json.dumps({
            "format": packets.VOTES_FORMAT, "format_version": 1,
            "reviewer_id": "reviewerA", "votes": [{
                "occurrence_id": self.occurrence_id, "decision": "include",
                "created_at": "2999-01-01T00:00:00Z",
            }],
        }), encoding="utf-8")
        result = packets.merge_votes(self.conn, path, actor="owner1")
        self.assertEqual(result["quarantined_count"], 1)
        self.assertIsNone(screening.current_vote(self.conn, self.occurrence_id, "reviewerA"))

    def test_csv_exports_escape_formula_cells_after_whitespace(self):
        screening.cast_vote(
            self.conn, occurrence_id=self.occurrence_id, reviewer_id="reviewerA",
            decision="exclude", reason="\x00 \t=HYPERLINK(\"https://example.invalid\")",
        )
        import csv
        from io import StringIO
        rows = list(csv.DictReader(StringIO(export.export_decisions_csv(
            self.conn, "owner1", is_blind=False,
        ))))
        vote = next(row for row in rows if row["reviewer_id"] == "reviewerA")
        self.assertTrue(vote["reason"].startswith("'"))


if __name__ == "__main__":
    unittest.main()

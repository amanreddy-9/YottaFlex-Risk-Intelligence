"""Part 1 verification suite: schema docs, deterministic IDs, SQLite FKs, coverage, and 2x reproducibility."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yottaflex.generator.exporter import export_world
from yottaflex.generator.world_generator import generate_world
from yottaflex.schema_spec import TABLES, write_schema_artifacts


class TestPart1Generation(unittest.TestCase):
    def test_schema_and_data_dictionary_generated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_schema_artifacts(Path(tmp))
            dd = json.loads(paths["data_dictionary_json"].read_text(encoding="utf-8"))
            entity_names = {e["entity_name"] for e in dd["entities"]}
            expected_core = {
                "Customer", "Account", "Merchant", "Device", "Transaction",
                "TransferLink", "RiskRule", "Alert", "Case", "AnalystAction",
            }
            self.assertTrue(expected_core.issubset(entity_names))
            self.assertEqual(len(dd["entities"]), len(TABLES))
            md = paths["data_dictionary_md"].read_text(encoding="utf-8")
            self.assertIn("erDiagram", md)
            self.assertIn("ground_truth.csv", md)

    def test_starter_id_conventions_sqlite_and_coverage(self) -> None:
        world = generate_world(seed=20261022, scale_name="starter")
        self.assertEqual(len(world["customers"]), 500)
        self.assertEqual(len(world["accounts"]), 700)
        self.assertEqual(len(world["transactions"]), 10_000)
        self.assertGreaterEqual(len(world["alerts"]), 90)

        self.assertRegex(world["customers"][0]["customer_id"], r"^CUS-\d{6}$")
        self.assertRegex(world["accounts"][0]["account_id"], r"^ACC-CUS-\d{6}-\d{2}$")
        self.assertRegex(world["transactions"][0]["transaction_id"], r"^TXN-2026-\d{8}$")
        self.assertRegex(world["alerts"][0]["alert_id"], r"^ALT-2026-\d{6}$")
        self.assertRegex(world["cases"][0]["case_id"], r"^CASE-2026-\d{6}$")

        gt_typos = {r["typology"] for r in world["ground_truth"]}
        self.assertTrue({
            "NORMAL", "VELOCITY_SPIKE", "NEW_DEVICE",
            "CIRCULAR_TRANSFER", "DORMANT_REACTIVATION", "FALSE_POSITIVE", "NEGATIVE_EDGE_CASE",
        }.issubset(gt_typos))

        gt_issues = {r["issue_type"] for r in world["ground_truth"]}
        self.assertTrue({
            "TXN_ON_CLOSED_ACCOUNT",
            "NEGATIVE_BALANCE_NO_OVERDRAFT",
            "UNRECONCILED_TRANSFER_LEG",
            "ORPHAN_ALERT_NO_TRIGGER",
            "DISPOSITION_PRECEDES_ALERT",
        }.issubset(gt_issues))

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "starter"
            export_world(world, out, seed=20261022, scale_name="starter", generator_command="test")
            conn = sqlite3.connect(out / "yottaflex.db")
            try:
                fk_violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
                self.assertEqual(fk_violations, [])
                integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
                self.assertEqual(integrity, "ok")
            finally:
                conn.close()

    def test_twice_reproducibility_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            w1 = generate_world(seed=20261022, scale_name="starter")
            m1 = export_world(w1, Path(tmp) / "r1", seed=20261022, scale_name="starter", generator_command="repro")
            w2 = generate_world(seed=20261022, scale_name="starter")
            m2 = export_world(w2, Path(tmp) / "r2", seed=20261022, scale_name="starter", generator_command="repro")

            self.assertEqual(m1["row_counts"], m2["row_counts"])
            self.assertEqual(m1["sha256_checksums"], m2["sha256_checksums"])


if __name__ == "__main__":
    unittest.main()

"""Part 3 verification suite: 9-check validator, quarantine catch rate, zero leakage, and evaluation metrics."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yottaflex.evaluation.harness import run_evaluation, verify_zero_leakage
from yottaflex.generator.exporter import export_world
from yottaflex.generator.world_generator import generate_world
from yottaflex.validation.validator import run_validation


class TestPart3ValidationAndEvaluation(unittest.TestCase):
    def test_zero_leakage_ast_guard(self) -> None:
        res = verify_zero_leakage(ROOT / "src")
        self.assertTrue(res["zero_leakage_verified"], f"Leakage found: {res['violations']}")
        self.assertGreaterEqual(len(res["files_inspected"]), 4)

    def test_9_check_validator_and_evaluation_harness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "starter"
            world = generate_world(seed=20261022, scale_name="starter")
            export_world(world, out, seed=20261022, scale_name="starter", generator_command="test")

            val = run_validation(out, write_reports=True)
            summary = val["summary"]
            self.assertEqual(summary["total_checks"], 9)
            self.assertEqual(summary["total_quarantined_exceptions"], 5)
            self.assertEqual(set(summary["exceptions_by_issue_type"].keys()), {
                "TXN_ON_CLOSED_ACCOUNT",
                "NEGATIVE_BALANCE_NO_OVERDRAFT",
                "UNRECONCILED_TRANSFER_LEG",
                "ORPHAN_ALERT_NO_TRIGGER",
                "DISPOSITION_PRECEDES_ALERT",
            })

            reports_dir = out / "reports"
            self.assertTrue((reports_dir / "validation_summary.json").is_file())
            self.assertTrue((reports_dir / "validation_summary.md").is_file())
            self.assertTrue((reports_dir / "quarantine_exceptions.json").is_file())

            ev = run_evaluation(out, src_root=ROOT / "src", write_reports=True)
            self.assertTrue(ev["zero_leakage"]["zero_leakage_verified"])
            self.assertTrue(ev["validation_catch_rate"]["all_issue_types_caught"])
            self.assertEqual(ev["validation_catch_rate"]["exact_entity_recall"], 1.0)

            pm = ev["prioritization_metrics"]
            self.assertGreater(pm["priority_top20pct"]["recall"], pm["fifo_top20pct"]["recall"])
            self.assertGreater(pm["priority_ndcg_at_50"], pm["fifo_ndcg_at_50"])
            self.assertGreaterEqual(pm["false_positive_suppression_rate_below_40"], 0.90)

            self.assertTrue((reports_dir / "evaluation_report.json").is_file())
            self.assertTrue((reports_dir / "evaluation_report.md").is_file())


if __name__ == "__main__":
    unittest.main()

"""Batch 3 verification suite (Functions 51-75): Transaction Sorting, 360 Detail, Pattern Signals, Export & Automated Risk Scoring."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from test_batch1_auth_dashboard_customers import _dispatch_with_headers
from yottaflex.api.server import make_handler
from yottaflex.api.service import WorkbenchService
from yottaflex.generator.exporter import export_world
from yottaflex.generator.world_generator import generate_world


def _get_json(handler_cls, path: str) -> tuple[int, dict]:
    st, _, raw = _dispatch_with_headers(handler_cls, "GET", path)
    return st, json.loads(raw.decode("utf-8"))


class TestBatch3Functions51To75(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.export_dir = Path(self.tmp.name) / "starter"
        world = generate_world(seed=20261022, scale_name="starter")
        export_world(world, self.export_dir, seed=20261022, scale_name="starter", generator_command="test")
        self.svc = WorkbenchService(self.export_dir)
        dist_dir = ROOT / "web" / "dist"
        self.handler_cls = make_handler(self.svc, dist_dir if dist_dir.is_dir() else ROOT / "web")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_functions_51_64_to_70_sorting_patterns_and_export(self) -> None:
        # 51. Sort by amount desc/asc, risk_score desc, timestamp asc/desc
        st, amt_desc = _get_json(self.handler_cls, "/api/transactions?sort_by=amount&sort_dir=desc&limit=25")
        self.assertEqual(st, 200)
        amounts_d = [r["amount"] for r in amt_desc["items"]]
        self.assertEqual(amounts_d, sorted(amounts_d, reverse=True))

        st, amt_asc = _get_json(self.handler_cls, "/api/transactions?sort_by=amount&sort_dir=asc&limit=25")
        self.assertEqual(st, 200)
        amounts_a = [r["amount"] for r in amt_asc["items"]]
        self.assertEqual(amounts_a, sorted(amounts_a))

        st, risk_desc = _get_json(self.handler_cls, "/api/transactions?sort_by=risk_score&sort_dir=desc&limit=25")
        self.assertEqual(st, 200)
        scores_d = [r["risk_score"] for r in risk_desc["items"]]
        self.assertEqual(scores_d, sorted(scores_d, reverse=True))
        self.assertGreater(scores_d[0], 0.0)

        st, ts_asc = _get_json(self.handler_cls, "/api/transactions?sort_by=occurred_at&sort_dir=asc&limit=25")
        self.assertEqual(st, 200)
        ts_a = [r["occurred_at"] for r in ts_asc["items"]]
        self.assertEqual(ts_a, sorted(ts_a))

        # 64-69. Pattern detection filters: LARGE_AMOUNT, RAPID_SUCCESSIVE, NEW_DEVICE, DORMANT_ACCOUNT, LINKED_PATTERN, VALIDATION_EXCEPTION
        for pat in (
            "LARGE_AMOUNT",
            "RAPID_SUCCESSIVE",
            "NEW_DEVICE",
            "DORMANT_ACCOUNT",
            "LINKED_PATTERN",
            "VALIDATION_EXCEPTION",
        ):
            st, pat_res = _get_json(self.handler_cls, f"/api/transactions?pattern={pat}&limit=20")
            self.assertEqual(st, 200)
            self.assertGreater(pat_res["total"], 0, f"Expected non-zero rows for pattern={pat}")
            for row in pat_res["items"]:
                self.assertIn(pat, row["pattern_flags"])

        # 70. Export filtered transaction records (CSV + JSON)
        st, hdrs, raw_csv = _dispatch_with_headers(
            self.handler_cls,
            "GET",
            "/api/transactions/export?format=csv&pattern=VALIDATION_EXCEPTION",
        )
        self.assertEqual(st, 200)
        self.assertIn("text/csv", hdrs.get("content-type", ""))
        self.assertIn("attachment;", hdrs.get("content-disposition", ""))
        csv_text = raw_csv.decode("utf-8")
        self.assertIn("transaction_id,occurred_at,account_id", csv_text)
        self.assertIn("VALIDATION_EXCEPTION", csv_text)

        st, hdrs, raw_json = _dispatch_with_headers(
            self.handler_cls,
            "GET",
            "/api/transactions/export?format=json&risk_level=HIGH",
        )
        self.assertEqual(st, 200)
        exp_json = json.loads(raw_json.decode("utf-8"))
        self.assertGreater(exp_json["exported_count"], 0)
        for item in exp_json["items"]:
            self.assertEqual(item["risk_level"], "HIGH")

    def test_functions_52_to_63_and_69_transaction_360_detail(self) -> None:
        # Pick a high-risk linked transfer txn + a validation exception txn
        st, high_res = _get_json(self.handler_cls, "/api/transactions?risk_level=HIGH&pattern=LINKED_PATTERN&limit=10")
        self.assertEqual(st, 200)
        self.assertGreater(high_res["total"], 0)
        target_txn_id = high_res["items"][0]["transaction_id"]

        st, det = _get_json(self.handler_cls, f"/api/transactions/{target_txn_id}")
        self.assertEqual(st, 200)
        txn = det["transaction"]
        self.assertEqual(txn["transaction_id"], target_txn_id)
        self.assertIn("balance_before", txn)
        self.assertIn("balance_after", txn)
        self.assertIn("balance_reconciled", txn)
        self.assertIn("counterparty_country", txn)
        self.assertGreaterEqual(txn["risk_score"], 60.0)
        self.assertEqual(txn["risk_level"], "HIGH")
        self.assertGreaterEqual(len(det["triggered_alerts"]), 1)
        self.assertEqual(len(det["rule_evaluations"]), 8)
        self.assertGreaterEqual(len(det["flag_reasons"]), 1)
        self.assertIn("account_risk", det)
        self.assertIn("customer_risk", det)
        self.assertIsInstance(det["related_transactions"], list)
        self.assertGreaterEqual(len(det["related_transactions"]), 1)

        # Also check a validation exception txn surfaces inside detail (Function 69)
        st, exc_list = _get_json(self.handler_cls, "/api/transactions?pattern=VALIDATION_EXCEPTION&limit=5")
        self.assertEqual(st, 200)
        self.assertGreater(exc_list["total"], 0)
        exc_txn_id = exc_list["items"][0]["transaction_id"]
        st, exc_det = _get_json(self.handler_cls, f"/api/transactions/{exc_txn_id}")
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(exc_det["validation_exceptions"]), 1)

        # Check a merchant + device txn surfaces merchant and device details (Functions 56-57)
        st, merch_list = _get_json(self.handler_cls, "/api/transactions?txn_type=MERCHANT_PURCHASE&limit=5")
        self.assertEqual(st, 200)
        m_txn_id = merch_list["items"][0]["transaction_id"]
        st, m_det = _get_json(self.handler_cls, f"/api/transactions/{m_txn_id}")
        self.assertEqual(st, 200)
        self.assertIsNotNone(m_det["merchant"])
        self.assertIn("merchant_name", m_det["merchant"])

    def test_functions_71_to_75_automated_risk_detection_and_scoring(self) -> None:
        # Portfolio-level risk scoring overview
        st, rs = _get_json(self.handler_cls, "/api/risk/scoring")
        self.assertEqual(st, 200)
        for key in (
            "thresholds",
            "transaction_risk_distribution",
            "account_risk_distribution",
            "customer_risk_distribution",
            "top_risk_accounts",
            "top_risk_customers",
            "rules_summary",
        ):
            self.assertIn(key, rs)
        for lvl in ("HIGH", "MEDIUM", "LOW"):
            self.assertIn(lvl, rs["transaction_risk_distribution"])
            self.assertIn(lvl, rs["account_risk_distribution"])
            self.assertIn(lvl, rs["customer_risk_distribution"])

        # Live POST /api/risk/evaluate on a simulated suspicious cross-border outflow
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/risk/evaluate",
            {
                "payload": {
                    "account_id": "ACC-CUS-000001-01",
                    "amount": 12500.0,
                    "txn_type": "WIRE_OUT",
                    "direction": "DEBIT",
                    "counterparty_country": "CY",
                }
            },
        )
        self.assertEqual(st, 200)
        sim_res = json.loads(raw.decode("utf-8"))
        self.assertGreater(sim_res["transaction_risk_score"], 0.0)
        self.assertIn(sim_res["transaction_risk_level"], ("LOW", "MEDIUM", "HIGH"))
        self.assertEqual(len(sim_res["rule_evaluations"]), 8)
        self.assertGreaterEqual(sim_res["triggered_rule_count"], 1)
        self.assertIn("risk_score", sim_res["account_risk"])
        self.assertIn("risk_score", sim_res["customer_risk"])

        # Live POST /api/risk/evaluate by existing transaction_id
        st, high_res = _get_json(self.handler_cls, "/api/transactions?risk_level=HIGH&limit=1")
        tid = high_res["items"][0]["transaction_id"]
        st, _, raw_t = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/risk/evaluate",
            {"transaction_id": tid},
        )
        self.assertEqual(st, 200)
        eval_t = json.loads(raw_t.decode("utf-8"))
        self.assertEqual(eval_t["transaction_risk_level"], "HIGH")
        self.assertGreaterEqual(eval_t["transaction_risk_score"], 60.0)

    def test_strict_auth_enforcement_cookie_and_dashboard_case_filter(self) -> None:
        # Strict require_auth handler blocks unauthenticated access and accepts Bearer & HttpOnly cookie
        dist_dir = ROOT / "web" / "dist"
        strict_cls = make_handler(self.svc, dist_dir if dist_dir.is_dir() else ROOT / "web", require_auth=True)

        for method, path, body in (
            ("GET", "/api/customers", None),
            ("GET", "/api/transactions/export?format=csv", None),
            ("GET", "/api/risk/scoring", None),
            ("POST", "/api/risk/evaluate", {"payload": {"account_id": "ACC-CUS-000001-01", "amount": 500}}),
        ):
            st, _, _ = _dispatch_with_headers(strict_cls, method, path, body=body)
            self.assertEqual(st, 401, f"Expected 401 for unauthenticated {method} {path}")

        st, login_hdrs, login_raw = _dispatch_with_headers(
            strict_cls,
            "POST",
            "/api/auth/login",
            {"email": "analyst@yottaflex.com", "password": "YottaFlex#2026"},
        )
        self.assertEqual(st, 200)
        self.assertIn("yottaflex_session=", login_hdrs.get("set-cookie", ""))
        token = json.loads(login_raw.decode("utf-8"))["token"]

        st, _, _ = _dispatch_with_headers(
            strict_cls,
            "GET",
            "/api/transactions/export?format=csv",
            extra_headers={"Cookie": f"yottaflex_session={token}"},
        )
        self.assertEqual(st, 200)

        # Dashboard case-status filter scopes both cases and transactions cleanly
        st, dash_all = _get_json(self.handler_cls, "/api/dashboard?status=ALL")
        self.assertEqual(st, 200)
        st, dash_open = _get_json(self.handler_cls, "/api/dashboard?status=OPEN")
        self.assertEqual(st, 200)
        self.assertLessEqual(dash_open["summary"]["transactions"], dash_all["summary"]["transactions"])


if __name__ == "__main__":
    unittest.main()

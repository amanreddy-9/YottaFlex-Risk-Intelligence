"""Batch 2 verification suite (Functions 26-50): Customer Risk/Export, Account Management, and Transaction Monitoring."""

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


class TestBatch2Functions26To50(unittest.TestCase):
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

    def test_functions_26_to_33_customer_transactions_devices_risk_timeline_multi_export(self) -> None:
        # 32. Identify customers associated with multiple suspicious accounts
        st, list_res = _get_json(self.handler_cls, "/api/customers?limit=50")
        self.assertEqual(st, 200)
        self.assertGreater(list_res["total"], 0)
        self.assertIn("suspicious_account_count", list_res["items"][0])

        st, multi_res = _get_json(self.handler_cls, "/api/customers?multi_suspicious=1&limit=50")
        self.assertEqual(st, 200)
        for item in multi_res["items"]:
            self.assertGreaterEqual(item["suspicious_account_count"], 2)

        # Pick a customer who has cases/alerts & transactions
        target_cid = (
            multi_res["items"][0]["customer_id"]
            if multi_res["items"]
            else next(
                (c["customer_id"] for c in list_res["items"] if c["alert_count"] > 0),
                list_res["items"][0]["customer_id"],
            )
        )

        # 26-31. Customer 360 profile: transactions (chronological), devices, alerts/cases, risk score/factors, timeline
        st, prof = _get_json(self.handler_cls, f"/api/customers/{target_cid}")
        self.assertEqual(st, 200)
        self.assertEqual(prof["customer"]["customer_id"], target_cid)
        self.assertIn("customer_risk_score", prof)
        self.assertIn("customer_risk_level", prof)
        self.assertIsInstance(prof["risk_factors"], list)
        self.assertIsInstance(prof["risk_level_timeline"], list)
        self.assertGreaterEqual(len(prof["risk_level_timeline"]), 1)
        self.assertIsInstance(prof["devices"], list)
        self.assertIsInstance(prof["alerts"], list)
        self.assertIsInstance(prof["cases"], list)

        txns = prof["transactions"]
        self.assertIsInstance(txns, list)
        if len(txns) >= 2:
            # Function 28: chronological ascending timestamps
            timestamps = [t["occurred_at"] for t in txns]
            self.assertEqual(timestamps, sorted(timestamps))

        # 33. Export customer information & investigation summary in JSON and CSV
        st, hdrs, raw_json = _dispatch_with_headers(
            self.handler_cls, "GET", f"/api/customers/{target_cid}/export?format=json"
        )
        self.assertEqual(st, 200)
        self.assertIn("attachment;", hdrs.get("content-disposition", ""))
        exported_obj = json.loads(raw_json.decode("utf-8"))
        self.assertEqual(exported_obj["customer"]["customer_id"], target_cid)
        self.assertIn("risk_factors", exported_obj)

        st, hdrs, raw_csv = _dispatch_with_headers(
            self.handler_cls, "GET", f"/api/customers/{target_cid}/export?format=csv"
        )
        self.assertEqual(st, 200)
        self.assertIn("text/csv", hdrs.get("content-type", ""))
        csv_text = raw_csv.decode("utf-8")
        self.assertIn("section,id,attribute,value", csv_text)
        self.assertIn("CUSTOMER_PROFILE", csv_text)
        self.assertIn("RISK_SUMMARY", csv_text)
        self.assertIn(target_cid, csv_text)

    def test_functions_34_to_47_account_directory_filters_and_detail(self) -> None:
        # 34. View all bank accounts
        st, all_accts = _get_json(self.handler_cls, "/api/accounts?limit=50")
        self.assertEqual(st, 200)
        self.assertGreater(all_accts["total"], 0)
        first = all_accts["items"][0]
        for field in (
            "account_id",
            "primary_customer_id",
            "customer_name",
            "status",
            "current_balance",
            "opened_at",
            "account_risk_score",
            "is_dormant_reactivated",
        ):
            self.assertIn(field, first)

        # 35. Search by account_id and customer_id
        st, by_aid = _get_json(self.handler_cls, f"/api/accounts?search={first['account_id']}")
        self.assertEqual(st, 200)
        self.assertTrue(any(a["account_id"] == first["account_id"] for a in by_aid["items"]))

        st, by_cid = _get_json(self.handler_cls, f"/api/accounts?search={first['primary_customer_id']}")
        self.assertEqual(st, 200)
        self.assertTrue(any(a["primary_customer_id"] == first["primary_customer_id"] for a in by_cid["items"]))

        # 36. Filter by status (ACTIVE, DORMANT, SUSPENDED, CLOSED, INACTIVE)
        for status_val in ("ACTIVE", "DORMANT", "CLOSED", "INACTIVE", "SUSPENDED"):
            st, filtered = _get_json(self.handler_cls, f"/api/accounts?status={status_val}")
            self.assertEqual(st, 200)
            for row in filtered["items"]:
                if status_val == "SUSPENDED":
                    self.assertEqual(row["status"], "FROZEN")
                elif status_val == "INACTIVE":
                    self.assertTrue(
                        row["status"] in ("DORMANT", "CLOSED")
                        or not row["last_activity_at"]
                        or row["last_activity_at"] < "2026-09-01T00:00:00Z"
                    )
                else:
                    self.assertEqual(row["status"], status_val)

        # 44. Identify dormant accounts that have suddenly become active
        st, dormant_react = _get_json(self.handler_cls, "/api/accounts?dormant_reactivated=1")
        self.assertEqual(st, 200)
        for row in dormant_react["items"]:
            self.assertEqual(row["is_dormant_reactivated"], 1)

        # Pick an account with alerts or transfers if present
        target_aid = next(
            (a["account_id"] for a in all_accts["items"] if a["alert_count"] > 0),
            first["account_id"],
        )

        # 37-47. Individual account detail
        st, detail = _get_json(self.handler_cls, f"/api/accounts/{target_aid}")
        self.assertEqual(st, 200)
        self.assertEqual(detail["account"]["account_id"], target_aid)
        self.assertIn("last_activity_at", detail)
        self.assertIn("account_risk_score", detail)
        self.assertIn("is_dormant_reactivated", detail)
        self.assertGreaterEqual(len(detail["holders"]), 1)
        self.assertIsInstance(detail["transactions"], list)
        self.assertIsInstance(detail["transfers"], list)
        self.assertIsInstance(detail["linked_accounts"], list)
        self.assertIsInstance(detail["alerts"], list)
        self.assertGreaterEqual(len(detail["lifecycle_events"]), 1)
        for tr in detail["transfers"]:
            self.assertIn(tr["transfer_direction"], ("INCOMING", "OUTGOING"))
            self.assertIn("counterparty_account_id", tr)

    def test_functions_48_to_50_transaction_monitoring_search_filters(self) -> None:
        # 48. View all transactions with pagination
        st, page1 = _get_json(self.handler_cls, "/api/transactions?limit=25&offset=0")
        self.assertEqual(st, 200)
        self.assertGreater(page1["total"], 25)
        self.assertEqual(len(page1["items"]), 25)

        st, page2 = _get_json(self.handler_cls, "/api/transactions?limit=25&offset=25")
        self.assertEqual(st, 200)
        self.assertEqual(len(page2["items"]), 25)
        self.assertNotEqual(page1["items"][0]["transaction_id"], page2["items"][0]["transaction_id"])

        sample = page1["items"][0]
        # 49. Search by transaction_id, account_id, customer_id
        for q in (sample["transaction_id"], sample["account_id"], sample["customer_id"]):
            st, res = _get_json(self.handler_cls, f"/api/transactions?search={q}&limit=20")
            self.assertEqual(st, 200)
            self.assertGreaterEqual(res["total"], 1)

        merchant_txn = next((t for t in page1["items"] if t.get("merchant_id")), None)
        if merchant_txn:
            st, res_m = _get_json(
                self.handler_cls, f"/api/transactions?search={merchant_txn['merchant_id']}&limit=20"
            )
            self.assertEqual(st, 200)
            self.assertGreaterEqual(res_m["total"], 1)

        # 50. Filter by date range, amount, txn_type, risk_level, status
        st, by_amt = _get_json(
            self.handler_cls,
            "/api/transactions?min_amount=100&max_amount=5000&status=SETTLED&limit=30",
        )
        self.assertEqual(st, 200)
        for t in by_amt["items"]:
            self.assertGreaterEqual(t["amount"], 100.0)
            self.assertLessEqual(t["amount"], 5000.0)
            self.assertEqual(t["status"], "SETTLED")

        st, by_risk = _get_json(self.handler_cls, "/api/transactions?risk_level=HIGH&limit=30")
        self.assertEqual(st, 200)
        for t in by_risk["items"]:
            self.assertEqual(t["risk_level"], "HIGH")

        st, by_type = _get_json(
            self.handler_cls,
            f"/api/transactions?txn_type={sample['txn_type']}&start_date=2025-01-01&end_date=2027-01-01&limit=20",
        )
        self.assertEqual(st, 200)
        for t in by_type["items"]:
            self.assertEqual(t["txn_type"], sample["txn_type"])


if __name__ == "__main__":
    unittest.main()

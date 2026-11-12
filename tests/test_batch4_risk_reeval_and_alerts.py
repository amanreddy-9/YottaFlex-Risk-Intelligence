"""Batch 4 verification suite (Functions 76-100): Rule Contributions, Integrity Detectors, Re-Evaluation, Score History & Alert Management."""

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


def _get_json(handler_cls, path: str, token: str | None = None) -> tuple[int, dict]:
    hdrs = {"Authorization": f"Bearer {token}"} if token else None
    st, _, raw = _dispatch_with_headers(handler_cls, "GET", path, extra_headers=hdrs)
    return st, json.loads(raw.decode("utf-8"))


class TestBatch4Functions76To100(unittest.TestCase):
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

    def _login(self, email: str) -> str:
        st, _, raw = _dispatch_with_headers(
            self.handler_cls, "POST", "/api/auth/login", {"email": email, "password": "YottaFlex#2026"}
        )
        self.assertEqual(st, 200)
        return json.loads(raw.decode("utf-8"))["token"]

    def test_functions_76_to_90_detectors_reevaluation_and_score_history(self) -> None:
        # 78-84. Executions, anomaly detectors & baseline score history
        st, rs = _get_json(self.handler_cls, "/api/risk/scoring")
        self.assertEqual(st, 200)
        self.assertEqual(len(rs["anomaly_detectors"]), 6)
        self.assertGreaterEqual(len(rs["execution_runs"]), 1)
        self.assertGreaterEqual(len(rs["score_history"]), 1)

        # 85-88. Integrity detectors (closed accounts, negative balance no OD, mismatched transfers, missing/inconsistent refs)
        st, integ = _get_json(self.handler_cls, "/api/risk/integrity-detectors")
        self.assertEqual(st, 200)
        self.assertGreaterEqual(integ["closed_account_txns"]["count"], 1)
        self.assertGreaterEqual(integ["negative_balance_no_overdraft"]["count"], 1)
        self.assertGreaterEqual(integ["mismatched_transfer_amounts"]["count"], 1)
        self.assertGreaterEqual(integ["missing_or_inconsistent_references"]["count"], 1)

        # 89 & 90. RBAC: Analyst gets 403 updating rule weight; Admin gets 200 and triggers re-evaluation + score history
        analyst_tok = self._login("analyst@yottaflex.com")
        admin_tok = self._login("admin@yottaflex.com")

        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/risk/rules/RULE-001",
            {"base_weight": 35},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 403)

        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/risk/rules/RULE-001",
            {"base_weight": 35, "is_active": True},
            extra_headers={"Authorization": f"Bearer {admin_tok}"},
        )
        self.assertEqual(st, 200)
        upd_res = json.loads(raw.decode("utf-8"))
        self.assertEqual(upd_res["updated_rule"]["base_weight"], 35)
        self.assertGreaterEqual(upd_res["scores_changed"], 1)
        self.assertIn("RULE_UPDATED:RULE-001", upd_res["execution_run"]["trigger_source"])

        st, exec_res = _get_json(self.handler_cls, "/api/risk/executions")
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(exec_res["execution_runs"]), 2)
        self.assertTrue(any("RULE-001" in (h.get("rule_id") or "") for h in exec_res["score_history"]))

        # Full manual re-evaluate endpoint
        st, _, raw_re = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/risk/re-evaluate",
            {"rule_id": "ALL"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        re_res = json.loads(raw_re.decode("utf-8"))
        self.assertGreater(re_res["alerts_evaluated"], 10)

    def test_functions_91_to_100_alert_directory_filters_sort_and_360_detail(self) -> None:
        # 91. View all alerts paginated
        st, all_al = _get_json(self.handler_cls, "/api/alerts?limit=25&offset=0")
        self.assertEqual(st, 200)
        self.assertGreater(all_al["total"], 25)
        self.assertEqual(len(all_al["items"]), 25)
        sample = all_al["items"][0]

        # 92. Search by alert_id, transaction_id, customer_id, account_id
        for q in (sample["alert_id"], sample["customer_id"], sample["account_id"]):
            st, s_res = _get_json(self.handler_cls, f"/api/alerts?search={q}&limit=20")
            self.assertEqual(st, 200)
            self.assertTrue(any(a["alert_id"] == sample["alert_id"] for a in s_res["items"]))

        if sample.get("primary_txn_id"):
            st, t_res = _get_json(self.handler_cls, f"/api/alerts?search={sample['primary_txn_id']}&limit=20")
            self.assertEqual(st, 200)
            self.assertGreaterEqual(t_res["total"], 1)

        # 93. Filter by severity, rule_id, status, date range
        st, f_res = _get_json(
            self.handler_cls,
            f"/api/alerts?severity={sample['severity']}&rule_id={sample['rule_id']}&status={sample['status']}&start_date=2025-01-01&end_date=2027-12-31",
        )
        self.assertEqual(st, 200)
        self.assertGreaterEqual(f_res["total"], 1)
        for item in f_res["items"]:
            self.assertEqual(item["severity"], sample["severity"])
            self.assertEqual(item["rule_id"], sample["rule_id"])
            self.assertEqual(item["status"], sample["status"])

        # 94. Sort by risk_score and priority
        st, by_risk = _get_json(self.handler_cls, "/api/alerts?sort_by=risk_score&sort_dir=desc&limit=25")
        self.assertEqual(st, 200)
        scores = [a["risk_score"] for a in by_risk["items"]]
        self.assertEqual(scores, sorted(scores, reverse=True))

        st, by_prio = _get_json(self.handler_cls, "/api/alerts?sort_by=priority&sort_dir=desc&limit=25")
        self.assertEqual(st, 200)
        prios = [a["priority_score_effective"] for a in by_prio["items"]]
        self.assertEqual(prios, sorted(prios, reverse=True))

        # 95-100. Complete Alert 360 detail (rule, triggering txn, trigger facts, supporting txns, sibling alerts, contributions)
        target_al = next((a for a in all_al["items"] if a.get("primary_txn_id")), sample)
        st, det = _get_json(self.handler_cls, f"/api/alerts/{target_al['alert_id']}")
        self.assertEqual(st, 200)
        self.assertEqual(det["alert"]["alert_id"], target_al["alert_id"])
        self.assertIsNotNone(det["rule"])
        self.assertEqual(det["rule"]["rule_id"], target_al["rule_id"])
        self.assertGreaterEqual(len(det["risk_contributions"]), 3)
        self.assertIsInstance(det["trigger_facts"], list)
        self.assertIsInstance(det["supporting_transactions"], list)
        self.assertIsInstance(det["sibling_alerts"], list)
        for sa in det["sibling_alerts"]:
            self.assertNotEqual(sa["alert_id"], target_al["alert_id"])
            self.assertTrue(
                sa["customer_id"] == det["customer"]["customer_id"] or sa["account_id"] == det["account"]["account_id"]
            )


if __name__ == "__main__":
    unittest.main()

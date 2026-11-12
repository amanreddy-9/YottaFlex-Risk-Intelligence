"""Batch 10 verification suite (Functions 226-250): Sanctions, Mule Hubs, GoAML XML, QA, Webhooks & Chain."""

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


def _req(handler_cls, method: str, path: str, body: dict | None = None, token: str | None = None) -> tuple[int, dict, bytes]:
    hdrs = {"Authorization": f"Bearer {token}"} if token else None
    st, resp_hdrs, raw = _dispatch_with_headers(handler_cls, method, path, body, extra_headers=hdrs)
    return st, resp_hdrs, raw


class TestBatch10Functions226To250(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.export_dir = Path(self.tmp.name) / "starter"
        world = generate_world(seed=20261022, scale_name="starter")
        export_world(world, self.export_dir, seed=20261022, scale_name="starter", generator_command="test")
        self.svc = WorkbenchService(self.export_dir)
        dist_dir = ROOT / "web" / "dist"
        self.handler_cls = make_handler(self.svc, dist_dir if dist_dir.is_dir() else ROOT / "web", require_auth=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _login(self, email: str) -> str:
        st, _, raw = _dispatch_with_headers(
            self.handler_cls, "POST", "/api/auth/login", {"email": email, "password": "YottaFlex#2026"}
        )
        self.assertEqual(st, 200)
        return json.loads(raw.decode("utf-8"))["token"]

    def test_functions_226_to_239_sanctions_hubs_chronology_goaml_qa_reopen(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        reviewer_tok = self._login("reviewer@yottaflex.com")

        # 226-227: Sanctions & PEP Fuzzy Screening
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/screening/sanctions",
            {"entity_type": "CUSTOMER", "entity_id": "CUS-000001", "query_name": "Korsakov Holdings", "country_code": "RU"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        scr = json.loads(raw.decode("utf-8"))
        self.assertEqual(scr["disposition"], "POTENTIAL_MATCH")

        st, _, raw = _req(self.handler_cls, "GET", "/api/screening/history", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(json.loads(raw.decode("utf-8"))["items"]), 1)

        # 228-232: Fan Hubs, Customer Chronology/Corridor, Account Burst/Transfer Matrix
        st, _, raw = _req(self.handler_cls, "GET", "/api/network/fan-hubs", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("items", json.loads(raw.decode("utf-8")))

        cust_id = self.svc.list_customers(limit=1)["items"][0]["customer_id"]
        acct_id = self.svc.list_accounts(limit=1)["items"][0]["account_id"]

        st, _, raw = _req(self.handler_cls, "GET", f"/api/customers/{cust_id}/chronology", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("items", json.loads(raw.decode("utf-8")))

        st, _, raw = _req(self.handler_cls, "GET", f"/api/customers/{cust_id}/corridor-exposure", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("corridors", json.loads(raw.decode("utf-8")))

        st, _, raw = _req(self.handler_cls, "GET", f"/api/accounts/{acct_id}/burst-profile", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("night_window_pct", json.loads(raw.decode("utf-8")))

        st, _, raw = _req(self.handler_cls, "GET", f"/api/accounts/{acct_id}/transfer-matrix", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("counterparties", json.loads(raw.decode("utf-8")))

        # 233-239: GoAML XML, Shift Handoff, Seal, Bulk Tag, Reopen RBAC, Co-occurrence & Fatigue
        case_id = self.svc.list_cases(limit=1)["items"][0]["case_id"]
        st, _, raw = _req(self.handler_cls, "POST", f"/api/cases/{case_id}/goaml-xml", {}, token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("<goaml_report", json.loads(raw.decode("utf-8"))["xml"])

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/cases/{case_id}/handoff",
            {"to_analyst": "ANL-002", "summary": "Verify wire counterparty KYC docs"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        st, _, raw = _req(self.handler_cls, "GET", f"/api/cases/{case_id}/handoffs", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(json.loads(raw.decode("utf-8"))["items"]), 1)

        st, _, raw = _req(self.handler_cls, "POST", f"/api/cases/{case_id}/evidence-seal", {}, token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(len(json.loads(raw.decode("utf-8"))["sha256_digest"]), 64)

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/cases/bulk-tag",
            {"case_ids": [case_id], "tag": "VELOCITY_WATCH"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["updated_count"], 1)

        # Reopen RBAC: Analyst 403 -> Reviewer 200
        st, _, _ = _req(
            self.handler_cls,
            "POST",
            f"/api/cases/{case_id}/reopen",
            {"rationale": "New wire evidence received"},
            token=analyst_tok,
        )
        self.assertEqual(st, 403)
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/cases/{case_id}/reopen",
            {"rationale": "New wire evidence received"},
            token=reviewer_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["new_status"], "IN_REVIEW")

        st, _, _ = _req(self.handler_cls, "GET", "/api/alerts/co-occurrence", token=analyst_tok)
        self.assertEqual(st, 200)
        st, _, _ = _req(self.handler_cls, "GET", "/api/alerts/fatigue-report", token=analyst_tok)
        self.assertEqual(st, 200)

    def test_functions_240_to_250_sim_pii_mcc_continuity_rules_qa_webhooks_chain(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        reviewer_tok = self._login("reviewer@yottaflex.com")

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/transactions/batch-simulate",
            {"min_amount": 1000, "multiplier": 1.2, "limit": 20},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertIn("total_simulated", json.loads(raw.decode("utf-8")))

        for ep in (
            "/api/customers/shared-pii",
            "/api/analytics/mcc-outliers",
            "/api/quarantine/balance-continuity",
            "/api/network/device-velocity",
            "/api/quarantine/grouped",
            "/api/audit/verify-chain",
        ):
            st, _, _ = _req(self.handler_cls, "GET", ep, token=analyst_tok)
            self.assertEqual(st, 200, f"GET {ep} failed")

        # 245: Custom rule drafts
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/risk/custom-rules",
            {"name": "High Wire Sweep", "min_amount": 3000, "channel": "WIRE", "country_code": "ALL", "description": "Test"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertIn("dry_run_matches", json.loads(raw.decode("utf-8")))

        # 247-248: QA Grade & SLA Auto-Escalate RBAC
        case_id = self.svc.list_cases(limit=1)["items"][0]["case_id"]
        st, _, _ = _req(
            self.handler_cls,
            "POST",
            f"/api/governance/qa-samples/{case_id}/grade",
            {"grade": "PASS", "score": 92, "feedback": "Clean"},
            token=analyst_tok,
        )
        self.assertEqual(st, 403)
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/governance/qa-samples/{case_id}/grade",
            {"grade": "PASS", "score": 92, "feedback": "Clean"},
            token=reviewer_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["grade"], "PASS")

        st, _, _ = _req(self.handler_cls, "POST", "/api/cases/sla-auto-escalate", {"max_escalations": 3}, token=analyst_tok)
        self.assertEqual(st, 403)
        st, _, raw = _req(self.handler_cls, "POST", "/api/cases/sla-auto-escalate", {"max_escalations": 3}, token=reviewer_tok)
        self.assertEqual(st, 200)
        self.assertIn("escalated_count", json.loads(raw.decode("utf-8")))

        # 249: Outbound Webhooks CRUD + Test Ping
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/integrations/webhooks",
            {"name": "Splunk SOC", "target_url": "https://soc.yottaflex.local/hook"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        wid = json.loads(raw.decode("utf-8"))["webhook_id"]

        st, _, raw = _req(self.handler_cls, "POST", f"/api/integrations/webhooks/{wid}/test", {}, token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["last_status"], "200_SIMULATED_OK")

        st, _, raw = _req(self.handler_cls, "DELETE", f"/api/integrations/webhooks/{wid}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(raw.decode("utf-8"))["deleted"])


if __name__ == "__main__":
    unittest.main()

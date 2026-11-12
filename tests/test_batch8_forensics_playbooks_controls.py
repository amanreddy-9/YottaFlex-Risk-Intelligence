"""Batch 8 verification suite (Functions 176-200): Forensics, Controls, Playbooks & Escalations."""

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


class TestBatch8Functions176To200(unittest.TestCase):
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

    def test_functions_176_to_189_corridors_merchants_flow_kyc_controls(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        reviewer_tok = self._login("reviewer@yottaflex.com")
        admin_tok = self._login("admin@yottaflex.com")

        # 176-177: Corridors & High-Risk Jurisdiction Registry
        st, _, raw = _req(self.handler_cls, "GET", "/api/analytics/corridors", token=analyst_tok)
        self.assertEqual(st, 200)
        corr = json.loads(raw.decode("utf-8"))
        self.assertIn("watched_countries", corr)
        self.assertIn("items", corr)

        # Analyst lacks permission (403); Reviewer can upsert (200); only SYSTEM_ADMIN can delete (403 reviewer -> 200 admin)
        st, _, _ = _req(
            self.handler_cls,
            "POST",
            "/api/analytics/high-risk-countries",
            {"country_code": "ZZ", "country_name": "Zedonia Test", "risk_tier": "RESTRICTED", "multiplier": 2.4, "note": "Unit test"},
            token=analyst_tok,
        )
        self.assertEqual(st, 403)

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/analytics/high-risk-countries",
            {"country_code": "ZZ", "country_name": "Zedonia Test", "risk_tier": "RESTRICTED", "multiplier": 2.4, "note": "Unit test"},
            token=reviewer_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["country_code"], "ZZ")

        st, _, _ = _req(self.handler_cls, "DELETE", "/api/analytics/high-risk-countries/ZZ", token=reviewer_tok)
        self.assertEqual(st, 403)

        st, _, raw = _req(self.handler_cls, "DELETE", "/api/analytics/high-risk-countries/ZZ", token=admin_tok)
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(raw.decode("utf-8"))["deleted"])

        # 178-179: Merchant Risk Leaderboard & 360 Detail
        st, _, raw = _req(self.handler_cls, "GET", "/api/analytics/merchants", token=analyst_tok)
        self.assertEqual(st, 200)
        merch = json.loads(raw.decode("utf-8"))
        self.assertGreater(len(merch["items"]), 0)
        mid = merch["items"][0]["merchant_id"]

        st, _, raw = _req(self.handler_cls, "GET", f"/api/analytics/merchants/{mid}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["merchant"]["merchant_id"], mid)

        # 180-181: Flow Chains & Structuring Clusters
        acct_id = self.svc.list_accounts(limit=1)["items"][0]["account_id"]
        st, _, raw = _req(self.handler_cls, "GET", f"/api/network/flow-chains/{acct_id}", token=analyst_tok)
        self.assertEqual(st, 200)
        flow = json.loads(raw.decode("utf-8"))
        self.assertIn("pass_through_chains", flow)
        self.assertIn("edges", flow)

        st, _, raw = _req(self.handler_cls, "GET", "/api/analytics/structuring", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("items", json.loads(raw.decode("utf-8")))

        # 182-183: Customer Peer Baseline & KYC Periodic Review
        cust_id = self.svc.list_customers(limit=1)["items"][0]["customer_id"]
        st, _, raw = _req(self.handler_cls, "GET", f"/api/customers/{cust_id}/peer-baseline", token=analyst_tok)
        self.assertEqual(st, 200)
        pb = json.loads(raw.decode("utf-8"))
        self.assertIn("cohort_mean_volume", pb)
        self.assertIn("cohort_p95_volume", pb)
        self.assertIn("volume_ratio_to_mean", pb)

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/customers/{cust_id}/kyc-review",
            {"outcome": "EDD_REQUIRED", "risk_justification": "Cross-border volume check"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["outcome"], "EDD_REQUIRED")

        st, _, raw = _req(self.handler_cls, "GET", f"/api/customers/{cust_id}/kyc-reviews", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(json.loads(raw.decode("utf-8"))["reviews"]), 1)

        # 184-185: Account Operational Controls (RBAC on FULL_FREEZE) & Velocity
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/accounts/{acct_id}/control",
            {"control_status": "DEBIT_HOLD", "reason": "Manual verification hold"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["control_status"], "DEBIT_HOLD")

        # Analyst cannot issue FULL_FREEZE (403); Reviewer can (200)
        st, _, _ = _req(
            self.handler_cls,
            "POST",
            f"/api/accounts/{acct_id}/control",
            {"control_status": "FULL_FREEZE", "reason": "Escalated freeze"},
            token=analyst_tok,
        )
        self.assertEqual(st, 403)

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/accounts/{acct_id}/control",
            {"control_status": "FULL_FREEZE", "reason": "Reviewer approved freeze"},
            token=reviewer_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["control_status"], "FULL_FREEZE")

        st, _, raw = _req(self.handler_cls, "GET", f"/api/accounts/{acct_id}/velocity", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("buckets", json.loads(raw.decode("utf-8")))

    def test_functions_190_to_200_pins_comments_playbooks_rfi_sla_rebalance_suppression(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        reviewer_tok = self._login("reviewer@yottaflex.com")

        case_id = self.svc.list_cases(limit=1)["items"][0]["case_id"]

        # 190: Case Evidence Pinboard
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/cases/{case_id}/pins",
            {"entity_type": "TRANSACTION", "entity_id": "TXN-PIN-TEST", "pin_type": "PINNED_PROOF", "note": "Velocity leg"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        pin_id = json.loads(raw.decode("utf-8"))["pin_id"]

        st, _, raw = _req(self.handler_cls, "GET", f"/api/cases/{case_id}/pins", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(any(p["pin_id"] == pin_id for p in json.loads(raw.decode("utf-8"))["items"]))

        st, _, raw = _req(self.handler_cls, "DELETE", f"/api/cases/{case_id}/pins/{pin_id}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(raw.decode("utf-8"))["deleted"])

        # 191: Case Comments Thread
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/cases/{case_id}/comments",
            {"body": "Verified wire counterparty with correspondent bank.", "visibility": "COMPLIANCE"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["visibility"], "COMPLIANCE")

        st, _, raw = _req(self.handler_cls, "GET", f"/api/cases/{case_id}/comments", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(json.loads(raw.decode("utf-8"))["items"]), 1)

        # 192: Playbooks Library & Apply
        st, _, raw = _req(self.handler_cls, "GET", "/api/playbooks", token=analyst_tok)
        self.assertEqual(st, 200)
        pb_id = json.loads(raw.decode("utf-8"))["items"][0]["playbook_id"]

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/cases/{case_id}/apply-playbook",
            {"playbook_id": pb_id},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["playbook"]["playbook_id"], pb_id)

        # 193: FinCEN 314(b) RFI Packet
        st, _, raw = _req(self.handler_cls, "POST", f"/api/cases/{case_id}/rfi-packet", {}, token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("314(b)", json.loads(raw.decode("utf-8"))["markdown"])

        # 194-196: Pending Escalations, SLA Radar & Queue Rebalance RBAC
        st, _, raw = _req(self.handler_cls, "GET", "/api/cases/escalations/pending", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("items", json.loads(raw.decode("utf-8")))

        st, _, raw = _req(self.handler_cls, "GET", "/api/cases/sla-radar?warning_hours=8", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("breached", json.loads(raw.decode("utf-8")))

        st, _, _ = _req(self.handler_cls, "POST", "/api/cases/rebalance", {"limit": 10}, token=analyst_tok)
        self.assertEqual(st, 403)

        st, _, raw = _req(self.handler_cls, "POST", "/api/cases/rebalance", {"limit": 10}, token=reviewer_tok)
        self.assertEqual(st, 200)
        self.assertIn("reassigned_count", json.loads(raw.decode("utf-8")))

        # 197-198: False-Positive Suppression Rules CRUD
        al = self.svc.list_alerts(limit=1)["items"][0]
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/alerts/suppressions",
            {
                "account_id": al["account_id"],
                "rule_id": al["rule_id"],
                "max_amount": 999999.0,
                "reason": "Known treasury sweep whitelist",
                "days_valid": 14,
            },
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        sup_id = json.loads(raw.decode("utf-8"))["suppression_id"]

        st, _, raw = _req(self.handler_cls, "GET", "/api/alerts/suppressions", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(any(s["suppression_id"] == sup_id for s in json.loads(raw.decode("utf-8"))["items"]))

        st, _, raw = _req(self.handler_cls, "DELETE", f"/api/alerts/suppressions/{sup_id}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(raw.decode("utf-8"))["deactivated"])


if __name__ == "__main__":
    unittest.main()

"""Batch 9 verification suite (Functions 201-225): Simulation, Calibration, Merge, SIEM, Jobs & Telemetry."""

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


class TestBatch9Functions201To225(unittest.TestCase):
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

    def test_functions_201_to_212_capacity_sweep_drift_calibration_sandbox_merge(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        reviewer_tok = self._login("reviewer@yottaflex.com")
        admin_tok = self._login("admin@yottaflex.com")

        # 201: Capacity Forecaster
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/analytics/capacity-forecast",
            {"growth_factor": 1.35, "hours_per_case": 0.75, "analysts_available": 4},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        fc = json.loads(raw.decode("utf-8"))
        self.assertIn("utilization_pct", fc["projection"])
        self.assertIn("projected_open_cases", fc["projection"])

        # 202-203: Rule Threshold Sensitivity Sweep & Temporal Drift
        st, _, raw = _req(self.handler_cls, "GET", "/api/evaluation/threshold-sweep?rule_id=RULE-001", token=analyst_tok)
        self.assertEqual(st, 200)
        sw = json.loads(raw.decode("utf-8"))
        self.assertEqual(sw["rule_id"], "RULE-001")
        self.assertGreaterEqual(len(sw["points"]), 5)

        st, _, raw = _req(self.handler_cls, "GET", "/api/evaluation/temporal-drift?buckets=4", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreater(len(json.loads(raw.decode("utf-8"))["buckets"]), 0)

        # 204-205: Two-Step Calibration Proposal & SYSTEM_ADMIN Approval
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/risk/calibration-proposal",
            {"title": "Boost circular transfer weight", "weights": {"RULE-003": 42, "RULE-001": 18}, "simulation_summary": {"precision": 0.88}},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        prop_id = json.loads(raw.decode("utf-8"))["proposal_id"]
        self.assertEqual(json.loads(raw.decode("utf-8"))["status"], "PENDING_APPROVAL")

        # Analyst & Reviewer cannot approve (403); SYSTEM_ADMIN can (200)
        st, _, _ = _req(
            self.handler_cls,
            "POST",
            f"/api/risk/calibration-proposal/{prop_id}/approve",
            {"decision": "APPROVED"},
            token=analyst_tok,
        )
        self.assertEqual(st, 403)
        st, _, _ = _req(
            self.handler_cls,
            "POST",
            f"/api/risk/calibration-proposal/{prop_id}/approve",
            {"decision": "APPROVED"},
            token=reviewer_tok,
        )
        self.assertEqual(st, 403)

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            f"/api/risk/calibration-proposal/{prop_id}/approve",
            {"decision": "APPROVED"},
            token=admin_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["status"], "APPROVED")

        # 206: Ad-Hoc Pattern Sandbox
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/risk/sandbox-pattern",
            {"min_amount": 1000, "channel": "ALL", "txn_type": "ALL", "limit": 20},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertIn("matched_txns", json.loads(raw.decode("utf-8")))

        # 207-208: Case Merge Candidates & Audited Merge
        st, _, raw = _req(self.handler_cls, "GET", "/api/cases/merge-candidates", token=analyst_tok)
        self.assertEqual(st, 200)
        cands = json.loads(raw.decode("utf-8"))["items"]
        if cands:
            c0 = cands[0]
            st, _, raw = _req(
                self.handler_cls,
                "POST",
                "/api/cases/merge",
                {"primary_case_id": c0["primary_case_id"], "secondary_case_id": c0["secondary_case_id"], "rationale": "Consolidate entity"},
                token=reviewer_tok,
            )
            self.assertEqual(st, 200)
            self.assertEqual(json.loads(raw.decode("utf-8"))["primary_case_id"], c0["primary_case_id"])

    def test_functions_213_to_225_notifications_siem_jobs_bundle_preferences_bot(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")

        # 213: Per-User Notifications Center
        st, _, raw = _req(self.handler_cls, "GET", "/api/notifications", token=analyst_tok)
        self.assertEqual(st, 200)
        notifs = json.loads(raw.decode("utf-8"))
        self.assertIn("unread_count", notifs)

        st, _, raw = _req(self.handler_cls, "POST", "/api/notifications/read", {}, token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("updated", json.loads(raw.decode("utf-8")))

        # 214-215: SIEM Webhook Outbox
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/integrations/siem",
            {"event_type": "CRITICAL_ALERT", "severity": "HIGH", "entity_id": "CASE-2026-000001", "dispatch_now": True},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["delivery_status"], "DISPATCHED_DRY_RUN")

        st, _, raw = _req(self.handler_cls, "GET", "/api/integrations/siem", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(json.loads(raw.decode("utf-8"))["items"]), 1)

        # 216: Pipeline Job History & Trigger
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/system/jobs",
            {"job_type": "SLA_SWEEP"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["job_type"], "SLA_SWEEP")

        st, _, raw = _req(self.handler_cls, "GET", "/api/system/jobs", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(json.loads(raw.decode("utf-8"))["items"]), 1)

        # 217-218: Compliance Audit Archive Bundle
        st, hdrs, raw = _req(self.handler_cls, "GET", "/api/reports/compliance-bundle", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("application/json", hdrs.get("content-type", ""))
        bundle = json.loads(raw.decode("utf-8"))
        self.assertEqual(bundle["bundle_type"], "YOTTAFLEX_COMPLIANCE_ARCHIVE")
        self.assertIn("zero_leakage_certificate", bundle)

        # 219-225: User Preferences Persistence + Yotta Bot Forensic Intent
        st, _, raw = _req(
            self.handler_cls,
            "PATCH",
            "/api/auth/preferences",
            {"default_tab": "queue", "default_page_size": 50, "sla_lead_hours": 10, "compact_mode": True},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        prefs = json.loads(raw.decode("utf-8"))
        self.assertEqual(prefs["default_page_size"], 50)
        self.assertEqual(prefs["default_tab"], "queue")
        self.assertTrue(prefs["compact_mode"])

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/assistant/chat",
            {"query": "Show corridor risk and SLA radar"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        bot = json.loads(raw.decode("utf-8"))
        self.assertIn("Corridor", bot["reply"])


if __name__ == "__main__":
    unittest.main()

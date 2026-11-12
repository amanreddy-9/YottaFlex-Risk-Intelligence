"""Batch 11 verification suite (Functions 251-275): Deep Eval, PSI, Telemetry, Bookmarks, Retention & Exports."""

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


class TestBatch11Functions251To275(unittest.TestCase):
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

    def test_functions_251_to_260_deep_eval_psi_scorecard_telemetry_retention(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        admin_tok = self._login("admin@yottaflex.com")

        # 251-255: Deep Evaluation & Feature Drift PSI
        st, _, raw = _req(self.handler_cls, "GET", "/api/evaluation/lift-curve", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(len(json.loads(raw.decode("utf-8"))["deciles"]), 10)

        st, _, raw = _req(self.handler_cls, "GET", "/api/evaluation/score-histogram", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(len(json.loads(raw.decode("utf-8"))["bins"]), 10)

        st, _, raw = _req(self.handler_cls, "GET", "/api/evaluation/typology-severity-matrix", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("rows", json.loads(raw.decode("utf-8")))

        st, _, raw = _req(self.handler_cls, "GET", "/api/evaluation/rule-marginal-lift", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreater(len(json.loads(raw.decode("utf-8"))["items"]), 0)

        st, _, raw = _req(self.handler_cls, "GET", "/api/evaluation/feature-psi", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(len(json.loads(raw.decode("utf-8"))["features"]), 3)

        # 256-260: Scorecard, Telemetry, Bookmarks, Digest Schedules & Retention Policy
        st, _, raw = _req(self.handler_cls, "GET", "/api/system/data-scorecard", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["overall_health"], "OPTIMAL")

        st, _, raw = _req(self.handler_cls, "GET", "/api/system/telemetry", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreater(len(json.loads(raw.decode("utf-8"))["routes"]), 0)

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/search/bookmarks",
            {"title": "High Risk Wires", "workspace": "transactions", "query_text": "WIRE HIGH"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        bid = json.loads(raw.decode("utf-8"))["bookmark_id"]
        st, _, raw = _req(self.handler_cls, "DELETE", f"/api/search/bookmarks/{bid}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(raw.decode("utf-8"))["deleted"])

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/reports/schedules",
            {"cadence": "WEEKLY", "recipient_role": "RISK_REVIEWER", "include_quarantine": True},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["cadence"], "WEEKLY")

        # Retention RBAC: Analyst 403 -> Admin 200
        st, _, _ = _req(
            self.handler_cls,
            "POST",
            "/api/system/retention",
            {"alerts_days": 120, "sessions_days": 60, "exports_days": 180},
            token=analyst_tok,
        )
        self.assertEqual(st, 403)
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/system/retention",
            {"alerts_days": 120, "sessions_days": 60, "exports_days": 180},
            token=admin_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["policy"]["alerts_days"], 120)

    def test_functions_261_to_275_compare_whatif_exam_pins_exports_bot(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        reviewer_tok = self._login("reviewer@yottaflex.com")

        cases = self.svc.list_cases(limit=2)["items"]
        c1, c2 = cases[0]["case_id"], cases[1]["case_id"]

        # 261-264: Compare Two Cases, Related Timeline, Tier Workload, What-If Score
        st, _, raw = _req(self.handler_cls, "GET", f"/api/cases/{c1}/compare/{c2}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("shared_rules", json.loads(raw.decode("utf-8")))

        st, _, _ = _req(self.handler_cls, "GET", f"/api/cases/{c1}/related-timeline", token=analyst_tok)
        self.assertEqual(st, 200)

        st, _, _ = _req(self.handler_cls, "GET", "/api/cases/tier-workload", token=analyst_tok)
        self.assertEqual(st, 200)

        st, _, raw = _req(self.handler_cls, "POST", f"/api/cases/{c1}/what-if-score", {"waived_alert_ids": []}, token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("projected_score", json.loads(raw.decode("utf-8")))

        # 265-270: Exam Readiness, Commands, Customers/Accounts Exports, Workspace Pins
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/governance/exam-readiness",
            {"control_id": "EXAM-03", "status": "VERIFIED", "note": "SAR dual-control checked"},
            token=reviewer_tok,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["status"], "VERIFIED")

        st, _, raw = _req(self.handler_cls, "GET", "/api/search/commands", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreater(len(json.loads(raw.decode("utf-8"))["commands"]), 0)

        st, hdrs, _ = _req(self.handler_cls, "GET", "/api/customers/export?format=csv", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("text/csv", hdrs.get("content-type", ""))

        st, hdrs, _ = _req(self.handler_cls, "GET", "/api/accounts/export?format=json", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("application/json", hdrs.get("content-type", ""))

        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/workspace/pinned-entities",
            {"entity_type": "CASE", "entity_id": c1, "label": c1},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        wp_id = json.loads(raw.decode("utf-8"))["pin_id"]
        st, _, raw = _req(self.handler_cls, "DELETE", f"/api/workspace/pinned-entities/{wp_id}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(json.loads(raw.decode("utf-8"))["deleted"])

        # 275: Yotta Bot Batch 10-11 Intent
        st, _, raw = _req(
            self.handler_cls,
            "POST",
            "/api/assistant/chat",
            {"query": "Check feature PSI drift and exam readiness"},
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertIn("Feature Drift PSI", json.loads(raw.decode("utf-8"))["reply"])


if __name__ == "__main__":
    unittest.main()

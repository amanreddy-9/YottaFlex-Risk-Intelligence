"""Batch 5 verification suite (Functions 101-125): Alert Triage, Case Queue Operations & Dossier SAR Readiness."""

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


class TestBatch5Functions101To125(unittest.TestCase):
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

    def test_functions_101_to_110_alert_triage_bulk_escalation_sla_export(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        st, alerts_resp = _get_json(self.handler_cls, "/api/alerts?limit=10", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(alerts_resp["items"]), 3)
        a0, a1, a2 = alerts_resp["items"][0], alerts_resp["items"][1], alerts_resp["items"][2]
        self.assertIn("age_hours", a0)
        self.assertIn("sla_breached", a0)

        # 101-104, 106, 108: Assign, transition, FP disposition + suppression + note -> audit events
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/alerts/{a0['alert_id']}/triage",
            {
                "owner_analyst_id": "ANL-001",
                "status": "ACKNOWLEDGED",
                "note": "Starting alert verification.",
            },
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        res = json.loads(raw.decode("utf-8"))
        self.assertEqual(res["owner_analyst_id"], "ANL-001")
        self.assertEqual(res["status"], "ACKNOWLEDGED")

        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/alerts/{a0['alert_id']}/triage",
            {
                "disposition": "FALSE_POSITIVE",
                "suppression_reason": "VERIFIED_PAYROLL_BONUS",
                "note": "Confirmed payroll bonus.",
            },
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)

        st, det = _get_json(self.handler_cls, f"/api/alerts/{a0['alert_id']}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(det["alert"]["status"], "FALSE_POSITIVE")
        self.assertEqual(det["triage_meta"]["suppression_reason"], "VERIFIED_PAYROLL_BONUS")
        self.assertGreaterEqual(len(det["audit_events"]), 3)

        # 105: Escalate alert to a case
        st, _, esc_raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/alerts/{a1['alert_id']}/escalate",
            {"rationale": "Escalating high-risk pattern"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 201)
        esc_res = json.loads(esc_raw.decode("utf-8"))
        self.assertTrue(esc_res["case_id"].startswith("CASE-"))
        self.assertEqual(esc_res["status"], "ESCALATED")

        # 107: Bulk alert triage
        st, _, blk_raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/alerts/bulk-triage",
            {"alert_ids": [a2["alert_id"]], "action": "UNDER_INVESTIGATION", "rationale": "Batch review"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(blk_raw.decode("utf-8"))["updated_count"], 1)

        # 109 & 110: Owner/SLA filtering & CSV/JSON export
        st, owner_filtered = _get_json(self.handler_cls, "/api/alerts?owner_analyst=ANL-001", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(any(x["alert_id"] == a0["alert_id"] for x in owner_filtered["items"]))

        st_csv, hdrs_csv, csv_bytes = _dispatch_with_headers(
            self.handler_cls, "GET", "/api/alerts/export?format=csv", extra_headers={"Authorization": f"Bearer {analyst_tok}"}
        )
        self.assertEqual(st_csv, 200)
        self.assertIn("text/csv", hdrs_csv.get("content-type", ""))
        self.assertIn(b"alert_id", csv_bytes)

    def test_functions_111_to_125_queue_ops_dossier_checklist_sar_and_watchlist(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        reviewer_tok = self._login("reviewer@yottaflex.com")

        st, q_res = _get_json(self.handler_cls, "/api/cases?sort=priority&status=OPEN", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(q_res["items"]), 2)
        c_top = q_res["items"][0]
        c_second = q_res["items"][1]

        # 119: Rank delta & FIFO rank present
        self.assertIn("priority_rank", c_top)
        self.assertIn("fifo_rank", c_top)
        self.assertIn("rank_delta", c_top)

        # 111 & 112: Assign case + RBAC Priority Override
        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{c_top['case_id']}/triage",
            {"assigned_analyst_id": "ANL-001"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)

        st_forbid, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{c_top['case_id']}/triage",
            {"override_tier": "CRITICAL", "override_score": 99.0, "override_reason": "Analyst override attempt"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st_forbid, 403)

        st_ov, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{c_top['case_id']}/triage",
            {"override_tier": "CRITICAL", "override_score": 98.5, "override_reason": "Escalated executive fraud wire risk"},
            extra_headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        self.assertEqual(st_ov, 200)

        # 113 & 118: Extended queue filter & export
        st, filt_q = _get_json(
            self.handler_cls,
            "/api/cases?assigned_analyst=ANL-001&min_exposure=1",
            token=analyst_tok,
        )
        self.assertEqual(st, 200)
        self.assertTrue(any(c["case_id"] == c_top["case_id"] for c in filt_q["items"]))

        st_qexp, _, qexp_bytes = _dispatch_with_headers(
            self.handler_cls, "GET", "/api/cases/export?format=csv", extra_headers={"Authorization": f"Bearer {analyst_tok}"}
        )
        self.assertEqual(st_qexp, 200)
        self.assertIn(b"rank_delta", qexp_bytes)

        # 115 & 116: Link and unlink alerts on Case
        st, all_al = _get_json(self.handler_cls, "/api/alerts?limit=25", token=analyst_tok)
        self.assertEqual(st, 200)
        st_dos0, dos0 = _get_json(self.handler_cls, f"/api/cases/{c_top['case_id']}", token=analyst_tok)
        self.assertEqual(st_dos0, 200)
        linked_set = {a["alert_id"] for a in dos0["alerts"]}
        extra_al = next(a["alert_id"] for a in all_al["items"] if a["alert_id"] not in linked_set)

        st_lnk, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{c_top['case_id']}/alerts",
            {"alert_id": extra_al, "mode": "link", "rationale": "Correlated customer pattern"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st_lnk, 200)

        st_unlnk, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{c_top['case_id']}/alerts",
            {"alert_id": extra_al, "mode": "unlink", "rationale": "Unrelated false match"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st_unlnk, 200)

        # 117: Bulk Case Queue claim
        st_blk_c, _, blk_c_raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/cases/bulk",
            {"case_ids": [c_second["case_id"]], "action": "CLAIM_REVIEW", "rationale": "Batch review"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st_blk_c, 200)
        self.assertEqual(json.loads(blk_c_raw.decode("utf-8"))["updated_count"], 1)

        # 121: Checklist update
        st_chk, _, chk_raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{c_top['case_id']}/checklist",
            {"rules_reviewed": True, "ledger_reconciled": True, "network_verified": True, "notes": "Verified ring hops"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st_chk, 200)
        self.assertTrue(json.loads(chk_raw.decode("utf-8"))["network_verified"])

        # 122 & 124: SAR Draft Auto-Generation + Case Investigation Packet Export
        st_sar, _, sar_raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{c_top['case_id']}/sar-draft",
            {},
            extra_headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        self.assertEqual(st_sar, 200)
        self.assertIn("SUSPICIOUS ACTIVITY REPORT", json.loads(sar_raw.decode("utf-8"))["sar_draft"])

        st_pkt, _, pkt_bytes = _dispatch_with_headers(
            self.handler_cls,
            "GET",
            f"/api/cases/{c_top['case_id']}/export?format=md",
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st_pkt, 200)
        self.assertIn(b"Investigation Dossier", pkt_bytes)

        # 125: Cross-entity Watchlist Tagging synced across Customer 360 & Dossier
        cust_id = c_top["primary_customer_id"]
        st_tag, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/watchlist-tags",
            {"entity_type": "CUSTOMER", "entity_id": cust_id, "tag": "MULE_SUSPECT", "note": "Ring controller"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st_tag, 200)
        st_prof, prof = _get_json(self.handler_cls, f"/api/customers/{cust_id}", token=analyst_tok)
        self.assertEqual(st_prof, 200)
        self.assertTrue(any(t["tag"] == "MULE_SUSPECT" for t in prof["watchlist_tags"]))

        # 123 & 120: High-Exposure (>= $25k) Closure Guard + Reviewer Close & Reopen
        high_case = next(
            (c for c in q_res["items"] if float(c["total_exposure_amount"]) >= 25000.0),
            None,
        )
        if high_case:
            st_block, _, _ = _dispatch_with_headers(
                self.handler_cls,
                "POST",
                f"/api/cases/{high_case['case_id']}/actions",
                {"analyst_id": "ANL-001", "action_type": "CONFIRM_FRAUD", "rationale": "Analyst closure test"},
                extra_headers={"Authorization": f"Bearer {analyst_tok}"},
            )
            self.assertEqual(st_block, 403)

            st_close, _, _ = _dispatch_with_headers(
                self.handler_cls,
                "POST",
                f"/api/cases/{high_case['case_id']}/actions",
                {"analyst_id": "ANL-003", "action_type": "CONFIRM_FRAUD", "rationale": "Reviewer verified fraud"},
                extra_headers={"Authorization": f"Bearer {reviewer_tok}"},
            )
            self.assertEqual(st_close, 201)

            st_reopen_forbid, _, _ = _dispatch_with_headers(
                self.handler_cls,
                "POST",
                f"/api/cases/{high_case['case_id']}/actions",
                {"analyst_id": "ANL-001", "action_type": "REOPEN_CASE", "rationale": "Analyst reopen attempt"},
                extra_headers={"Authorization": f"Bearer {analyst_tok}"},
            )
            self.assertEqual(st_reopen_forbid, 403)

            st_reopen, _, reopen_raw = _dispatch_with_headers(
                self.handler_cls,
                "POST",
                f"/api/cases/{high_case['case_id']}/actions",
                {"analyst_id": "ANL-003", "action_type": "REOPEN_CASE", "rationale": "New wire evidence received"},
                extra_headers={"Authorization": f"Bearer {reviewer_tok}"},
            )
            self.assertEqual(st_reopen, 201)
            self.assertEqual(json.loads(reopen_raw.decode("utf-8"))["new_status"], "IN_REVIEW")


if __name__ == "__main__":
    unittest.main()

"""Batch 6 verification suite (Functions 126-150): Quarantine Operations, Live Validation, Audit Ledger & Governance."""

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


class TestBatch6Functions126To150(unittest.TestCase):
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

    def test_functions_126_to_135_quarantine_triage_bulk_validation_export(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")

        # 126, 133: Enriched filtered quarantine list with exposure & review status counts
        st, qlist = _get_json(self.handler_cls, "/api/quarantine?sort_by=exposure", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(qlist["total_exceptions"], 5)
        self.assertIn("counts_by_review_status", qlist)
        self.assertIn("quarantined_exposure", qlist)

        ex0 = qlist["exceptions"][0]
        ex1 = qlist["exceptions"][1]
        ex2 = qlist["exceptions"][2]

        # 127-128, 130: Single exception disposition + immutable audit event timeline
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/quarantine/{ex0['exception_id']}/review",
            {"review_status": "REMEDIATED", "note": "Confirmed isolation from scoring.", "action_taken": "ISOLATED"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        rev = json.loads(raw.decode("utf-8"))
        self.assertEqual(rev["exception"]["review_status"], "REMEDIATED")
        self.assertGreaterEqual(len(rev["events"]), 1)

        # 129: Bulk review
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/quarantine/bulk-review",
            {"exception_ids": [ex1["exception_id"], ex2["exception_id"]], "review_status": "ACKNOWLEDGED", "note": "Batch checked"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["updated_count"], 2)

        # Filtered query verifies persistence
        st, rem = _get_json(self.handler_cls, "/api/quarantine?review_status=REMEDIATED", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(any(x["exception_id"] == ex0["exception_id"] for x in rem["exceptions"]))

        # 132: Live invariant validation check runner
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/quarantine/validate",
            {},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        val = json.loads(raw.decode("utf-8"))
        self.assertEqual(val["total_checks"], 6)

        # 134: Quarantine CSV export
        st, hdrs, raw_csv = _dispatch_with_headers(
            self.handler_cls,
            "GET",
            "/api/quarantine/export?format=csv",
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertIn("text/csv", hdrs.get("content-type", ""))
        self.assertIn(ex0["exception_id"], raw_csv.decode("utf-8"))

    def test_functions_136_to_150_audit_admin_watchlist_saved_views_and_sla(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        admin_tok = self._login("admin@yottaflex.com")

        # Trigger one quarantine review so audit stream has all record sources
        st, qlist = _get_json(self.handler_cls, "/api/quarantine", token=analyst_tok)
        ex0 = qlist["exceptions"][0]
        _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/quarantine/{ex0['exception_id']}/review",
            {"review_status": "ACKNOWLEDGED", "note": "Audit trail verification"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )

        # 136-139: Unified Audit Ledger + SHA-256 integrity hash + export
        st, audit = _get_json(self.handler_cls, "/api/audit/events?limit=30", token=admin_tok)
        self.assertEqual(st, 200)
        self.assertGreater(audit["total"], 0)
        self.assertTrue(all("integrity_hash" in ev for ev in audit["items"]))

        st, hdrs, _ = _dispatch_with_headers(
            self.handler_cls,
            "GET",
            "/api/audit/export?format=csv",
            extra_headers={"Authorization": f"Bearer {admin_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertIn("text/csv", hdrs.get("content-type", ""))

        # 140: Analyst Leaderboard
        st, lb = _get_json(self.handler_cls, "/api/audit/analyst-stats", token=admin_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(lb["analysts"]), 3)

        # 141-142, 150: RBAC Admin Users & role governance (analyst blocked -> 403, admin allowed)
        st, _ = _get_json(self.handler_cls, "/api/admin/users", token=analyst_tok)
        self.assertEqual(st, 403)
        st, users_res = _get_json(self.handler_cls, "/api/admin/users", token=admin_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(users_res["users"]), 3)

        # Update USR-001 role -> RISK_REVIEWER -> restore OPS_ANALYST
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/admin/users/USR-001/role",
            {"role": "RISK_REVIEWER"},
            extra_headers={"Authorization": f"Bearer {admin_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["user"]["role"], "RISK_REVIEWER")
        _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/admin/users/USR-001/role",
            {"role": "OPS_ANALYST"},
            extra_headers={"Authorization": f"Bearer {admin_tok}"},
        )

        # 143-144: Watchlist tag creation + centralized directory query
        st, custs = _get_json(self.handler_cls, "/api/customers?limit=1", token=analyst_tok)
        cid = custs["items"][0]["customer_id"]
        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/watchlist-tags",
            {"entity_type": "CUSTOMER", "entity_id": cid, "tag": "SANCTIONS_HIT", "note": "Governance screen"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        st, wl = _get_json(self.handler_cls, "/api/watchlist-tags?tag=SANCTIONS_HIT", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(any(x["entity_id"] == cid for x in wl["items"]))

        # 145-146: Saved filter presets create/list/delete
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/saved-views",
            {"workspace": "queue", "name": "Crit Breached", "filters": {"tier": "CRITICAL", "slaFilter": "1"}},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        vid = json.loads(raw.decode("utf-8"))["view_id"]
        st, views = _get_json(self.handler_cls, "/api/saved-views?workspace=queue", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(any(v["view_id"] == vid for v in views["items"]))
        st, _, _ = _dispatch_with_headers(
            self.handler_cls, "DELETE", f"/api/saved-views/{vid}", extra_headers={"Authorization": f"Bearer {analyst_tok}"}
        )
        self.assertEqual(st, 200)

        # 147-148, 150: SLA Policy thresholds (analyst 403, admin 200 + live effect)
        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/admin/sla-policies",
            {"updates": [{"entity_scope": "CASE", "tier": "CRITICAL", "sla_hours": 12}]},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 403)
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/admin/sla-policies",
            {"updates": [{"entity_scope": "CASE", "tier": "CRITICAL", "sla_hours": 12}]},
            extra_headers={"Authorization": f"Bearer {admin_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["map"]["CASE"]["CRITICAL"], 12)


if __name__ == "__main__":
    unittest.main()

"""Batch 7 verification suite (Functions 151-175): Evaluation Lab, Rings, SAR Lifecycle, Search & Telemetry."""

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


class TestBatch7Functions151To175(unittest.TestCase):
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

    def test_functions_151_to_159_evaluation_simulator_rules_whatif_zero_leakage(self) -> None:
        tok = self._login("analyst@yottaflex.com")

        # 152, 157: Evaluation payload includes NDCG@20 & typology percentiles + separation gap
        st, ev = _get_json(self.handler_cls, "/api/evaluation", token=tok)
        self.assertEqual(st, 200)
        self.assertIn("ndcg", ev["priority_top20"])
        self.assertIn("score_separation", ev)
        self.assertIn("p50_score", ev["typology_stats"][0])

        # 151: Custom @K% cut-off simulator
        st, sim = _get_json(self.handler_cls, "/api/evaluation/simulate-k?k_pct=30", token=tok)
        self.assertEqual(st, 200)
        self.assertEqual(sim["k_pct"], 30.0)
        self.assertIn("f1", sim["priority"])
        self.assertIn("map", sim["priority"])

        # 153: Rule-level precision attribution
        st, rp = _get_json(self.handler_cls, "/api/evaluation/rule-performance", token=tok)
        self.assertEqual(st, 200)
        self.assertEqual(len(rp["rules"]), 8)

        # 154: Non-mutating What-If simulation
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/evaluation/what-if",
            {"weight_overrides": {"RULE-003": 45, "RULE-001": 10}, "k_pct": 20},
            extra_headers={"Authorization": f"Bearer {tok}"},
        )
        self.assertEqual(st, 200)
        wi = json.loads(raw.decode("utf-8"))
        self.assertIn("simulated", wi)

        # 155-156: Live Zero-Leakage AST verification & Disk SHA-256 Manifest verifier
        st, zl = _get_json(self.handler_cls, "/api/evaluation/zero-leakage", token=tok)
        self.assertEqual(st, 200)
        self.assertTrue(zl["zero_leakage_verified"])
        self.assertEqual(zl["violations"], [])

        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/evaluation/verify-manifest",
            {},
            extra_headers={"Authorization": f"Bearer {tok}"},
        )
        self.assertEqual(st, 200)
        man = json.loads(raw.decode("utf-8"))
        self.assertTrue(man["verified"])
        self.assertGreater(man["matched_count"], 0)

        # 158: Evaluation CSV & JSON export
        st, hdrs, _ = _dispatch_with_headers(
            self.handler_cls,
            "GET",
            "/api/evaluation/export?format=csv",
            extra_headers={"Authorization": f"Bearer {tok}"},
        )
        self.assertEqual(st, 200)
        self.assertIn("text/csv", hdrs.get("content-type", ""))

    def test_functions_160_to_175_rings_sar_registry_similar_digest_search_health(self) -> None:
        analyst_tok = self._login("analyst@yottaflex.com")
        reviewer_tok = self._login("reviewer@yottaflex.com")

        # 160-162: Collusion ring detection & multi-hop entity network explorer
        st, rings = _get_json(self.handler_cls, "/api/network/rings?min_accounts=2", token=analyst_tok)
        self.assertEqual(st, 200)
        st, cases = _get_json(self.handler_cls, "/api/cases?limit=2", token=analyst_tok)
        cid = cases["items"][0]["case_id"]
        st, net = _get_json(self.handler_cls, f"/api/network/entity/{cid}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(net["node_count"], 2)

        # 164-166: SAR draft -> Registry -> Readiness Score -> Lifecycle Transitions + RBAC guard
        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{cid}/sar-draft",
            {},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        st, sreg = _get_json(self.handler_cls, "/api/sar/registry", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertTrue(any(x["case_id"] == cid and x["readiness"]["readiness_score"] >= 60 for x in sreg["items"]))

        # Analyst marks READY_FOR_FILING -> 200, Analyst tries SUBMITTED -> 403, Reviewer marks SUBMITTED -> 200
        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/sar/{cid}/status",
            {"sar_status": "READY_FOR_FILING"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/sar/{cid}/status",
            {"sar_status": "SUBMITTED"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 403)
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/sar/{cid}/status",
            {"sar_status": "SUBMITTED", "note": "FinCEN BSA filing verified"},
            extra_headers={"Authorization": f"Bearer {reviewer_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode("utf-8"))["sar_status"], "SUBMITTED")

        # 167-168: Executive Compliance Digest & Markdown download
        st, dig = _get_json(self.handler_cls, "/api/reports/executive-digest", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertIn("pillars", dig)
        st, hdrs, md = _dispatch_with_headers(
            self.handler_cls,
            "GET",
            "/api/reports/executive-digest/export?format=md",
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertIn("text/markdown", hdrs.get("content-type", ""))
        self.assertIn("YottaFlex AML Compliance", md.decode("utf-8"))

        # 169: Global Cross-Entity Search
        st, gs = _get_json(self.handler_cls, f"/api/search/global?q={cid}", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(gs["total_hits"], 1)

        # 171: Yotta Bot Governance & Collusion Ring intents
        st, _, bot_raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/assistant/chat",
            {"query": "show governance digest"},
            extra_headers={"Authorization": f"Bearer {analyst_tok}"},
        )
        self.assertEqual(st, 200)
        self.assertIn("Governance", json.loads(bot_raw.decode("utf-8"))["reply"])

        # 172: Similar Peer Cases
        st, sim_cases = _get_json(self.handler_cls, f"/api/cases/{cid}/similar", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertGreaterEqual(len(sim_cases["items"]), 1)

        # 174: System Health & Telemetry
        st, health = _get_json(self.handler_cls, "/api/system/health", token=analyst_tok)
        self.assertEqual(st, 200)
        self.assertEqual(health["status"], "HEALTHY")
        self.assertGreater(health["sqlite_index_count"], 5)


if __name__ == "__main__":
    unittest.main()

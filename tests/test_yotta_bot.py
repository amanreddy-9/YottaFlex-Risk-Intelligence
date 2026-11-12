"""Verification suite for Yotta Bot: project knowledge, live SQLite lookups, and pre-auth PII protection."""

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


class TestYottaBot(unittest.TestCase):
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

    def _ask(self, query: str, token: str | None = None) -> tuple[int, dict]:
        hdrs = {"Authorization": f"Bearer {token}"} if token else None
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/assistant/chat",
            {"query": query},
            extra_headers=hdrs,
        )
        return st, json.loads(raw.decode("utf-8"))

    def test_guest_help_and_authenticated_live_entity_lookup(self) -> None:
        # 1. Guest asks for sign-in credentials & project rules
        st, cred_res = self._ask("How do I sign in?")
        self.assertEqual(st, 200)
        self.assertIn("analyst@yottaflex.com", cred_res["reply"])
        self.assertIn("YottaFlex#2026", cred_res["reply"])

        st, rule_res = self._ask("Tell me about RULE-003")
        self.assertEqual(st, 200)
        self.assertIn("Circular Transfer Ring", rule_res["reply"])

        # 2. Guest cannot inspect specific customer PII before authenticating
        st, guard_res = self._ask("Inspect CUS-000001")
        self.assertEqual(st, 200)
        self.assertIn("sign in first", guard_res["reply"].lower())

        # 3. Sign in and verify live DB lookups across all entity types & portfolio metrics
        st, _, login_raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/auth/login",
            {"email": "analyst@yottaflex.com", "password": "YottaFlex#2026"},
        )
        self.assertEqual(st, 200)
        tok = json.loads(login_raw.decode("utf-8"))["token"]

        for q, expected_substr, expected_act_type in (
            ("Inspect CUS-000001", "CUS-000001", "customer"),
            ("Look up ACC-CUS-000001-01", "ACC-CUS-000001-01", "account"),
            ("Check TXN-2026-00000001", "TXN-2026-00000001", "txn"),
            ("What is ALT-2026-000001?", "ALT-2026-000001", "alert"),
            ("Summarize CASE-2026-000001", "CASE-2026-000001", "case"),
        ):
            st, res = self._ask(q, token=tok)
            self.assertEqual(st, 200)
            self.assertIn(expected_substr, res["reply"])
            self.assertTrue(any(a["type"] == expected_act_type for a in res["actions"]))

        for q, expected_substr in (
            ("How many customers and transactions are in the dataset?", "10,000"),
            ("Show quarantine exceptions", "TXN_ON_CLOSED_ACCOUNT"),
            ("What is priority vs fifo recall?", "Priority Top-20% Recall"),
            ("Show top priority cases", "CASE-"),
            ("hi", "Yotta Bot"),
            ("what does yottaflex do", "Explainable AML Risk"),
            ("what is dark mode", "Dark Mode"),
            ("show open cases", "CASE-"),
            ("show top accounts", "ACC-"),
            ("show top customers", "CUS-"),
            ("show critical alerts", "ALT-"),
            ("rule 3", "Circular Transfer Ring"),
        ):
            st, res = self._ask(q, token=tok)
            self.assertEqual(st, 200)
            self.assertIn(expected_substr, res["reply"])


if __name__ == "__main__":
    unittest.main()

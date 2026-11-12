"""Batch 1 verification suite (Functions 1-25): Auth/RBAC, Overview Dashboard & Export, Customer Directory & 360 Profile."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from test_part2_api_frontend import _dispatch
from yottaflex.api.server import make_handler
from yottaflex.api.service import WorkbenchService
from yottaflex.generator.exporter import export_world
from yottaflex.generator.world_generator import generate_world


def _dispatch_with_headers(
    handler_cls,
    method: str,
    path: str,
    body: dict | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    import io

    class _Sock:
        def __init__(self, req: bytes) -> None:
            self._r = io.BytesIO(req)
            self._w = io.BytesIO()

        def makefile(self, mode: str, *args, **kwargs):
            return self._r if "r" in mode else self._w

        def sendall(self, data: bytes) -> None:
            self._w.write(data)

        def close(self) -> None:
            pass

    body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
    hdr_lines = [f"{method} {path} HTTP/1.1", "Host: localhost"]
    if body is not None:
        hdr_lines.append("Content-Type: application/json")
        hdr_lines.append(f"Content-Length: {len(body_bytes)}")
    for k, v in (extra_headers or {}).items():
        hdr_lines.append(f"{k}: {v}")
    hdr_lines.append("Connection: close")
    raw_req = ("\r\n".join(hdr_lines) + "\r\n\r\n").encode("utf-8") + body_bytes
    sock = _Sock(raw_req)
    handler_cls(sock, ("127.0.0.1", 0), None)
    raw = sock._w.getvalue()
    head, payload = raw.split(b"\r\n\r\n", 1)
    lines = head.decode("utf-8").split("\r\n")
    status = int(lines[0].split(" ")[1])
    resp_hdrs: dict[str, str] = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            resp_hdrs[k.strip().lower()] = v.strip()
    return status, resp_hdrs, payload


class TestBatch1Functions1To25(unittest.TestCase):
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

    def test_functions_1_to_6_auth_rbac_profile_reset_sessions(self) -> None:
        # 1. Login as Operations Analyst
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/auth/login",
            {"email": "analyst@yottaflex.com", "password": "YottaFlex#2026"},
        )
        self.assertEqual(st, 200)
        login_res = json.loads(raw.decode())
        token = login_res["token"]
        self.assertEqual(login_res["user"]["role"], "OPS_ANALYST")
        self.assertIn("triage_alerts", login_res["user"]["permissions"])

        auth_hdr = {"Authorization": f"Bearer {token}"}

        # 3. View & edit profile
        st, _, raw = _dispatch_with_headers(self.handler_cls, "GET", "/api/auth/me", extra_headers=auth_hdr)
        self.assertEqual(st, 200)
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "PATCH",
            "/api/auth/profile",
            {"full_name": "Priya Nair-Updated", "phone": "+1-212-555-9999", "department": "AML Ops", "title": "Lead Analyst"},
            extra_headers=auth_hdr,
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode())["user"]["full_name"], "Priya Nair-Updated")

        # 5. RBAC enforcement: Analyst cannot FILE_SAR (403)
        cases = json.loads(_dispatch(self.handler_cls, "GET", "/api/cases?status=OPEN")[2].decode())["items"]
        cid = cases[0]["case_id"]
        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            f"/api/cases/{cid}/actions",
            {"analyst_id": "ANL-001", "action_type": "FILE_SAR", "rationale": "Attempt SAR as analyst"},
            extra_headers=auth_hdr,
        )
        self.assertEqual(st, 403)

        # 6. View sessions & login history
        st, _, raw = _dispatch_with_headers(self.handler_cls, "GET", "/api/auth/sessions", extra_headers=auth_hdr)
        self.assertEqual(st, 200)
        sec = json.loads(raw.decode())
        self.assertGreaterEqual(len(sec["sessions"]), 1)
        self.assertGreaterEqual(len(sec["login_history"]), 1)

        # 1. Logout invalidates token
        st, _, _ = _dispatch_with_headers(self.handler_cls, "POST", "/api/auth/logout", extra_headers=auth_hdr)
        self.assertEqual(st, 200)
        st, _, _ = _dispatch_with_headers(self.handler_cls, "GET", "/api/auth/me", extra_headers=auth_hdr)
        self.assertEqual(st, 401)

        # 2. Forgot & Reset Password flow
        st, _, raw = _dispatch_with_headers(
            self.handler_cls, "POST", "/api/auth/forgot-password", {"email": "reviewer@yottaflex.com"}
        )
        self.assertEqual(st, 200)
        code = json.loads(raw.decode())["demo_reset_code"]
        st, _, _ = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/auth/reset-password",
            {"email": "reviewer@yottaflex.com", "reset_code": code, "new_password": "NewSecurePassword#99"},
        )
        self.assertEqual(st, 200)
        st, _, raw = _dispatch_with_headers(
            self.handler_cls,
            "POST",
            "/api/auth/login",
            {"email": "reviewer@yottaflex.com", "password": "NewSecurePassword#99"},
        )
        self.assertEqual(st, 200)
        self.assertEqual(json.loads(raw.decode())["user"]["role"], "RISK_REVIEWER")

    def test_functions_7_to_19_dashboard_filters_and_export(self) -> None:
        st, _, raw = _dispatch(self.handler_cls, "GET", "/api/dashboard?period=30D&risk_level=ALL")
        self.assertEqual(st, 200)
        dash = json.loads(raw.decode())
        s = dash["summary"]
        self.assertEqual(s["customers"], 500)
        self.assertEqual(s["accounts"], 700)
        self.assertEqual(s["merchants"], 80)
        self.assertGreater(s["devices"], 600)
        self.assertGreater(s["high_risk_txns"], 0)
        self.assertGreater(len(dash["volume_series"]), 0)
        self.assertGreater(len(dash["rule_distribution"]), 0)
        self.assertGreater(len(dash["recent_suspicious_txns"]), 0)
        self.assertGreater(len(dash["top_risk_customers"]), 0)
        self.assertGreater(len(dash["top_risk_accounts"]), 0)

        st, hdrs, csv_bytes = _dispatch(self.handler_cls, "GET", "/api/dashboard/export?format=csv")
        self.assertEqual(st, 200)
        self.assertIn("text/csv", hdrs.get("content-type", ""))
        self.assertIn(b"TOP_RISK_CUSTOMER", csv_bytes)

    def test_functions_20_to_25_customers_search_filters_and_profile(self) -> None:
        st, _, raw = _dispatch(self.handler_cls, "GET", "/api/customers?kyc_tier=STANDARD&account_status=ACTIVE")
        self.assertEqual(st, 200)
        custs = json.loads(raw.decode())
        self.assertGreater(custs["total"], 10)
        sample = custs["items"][0]
        self.assertIn("@yottaflex.io", sample["email"])
        self.assertTrue(sample["phone"].startswith("+1-555-"))

        # Search by email
        st, _, raw = _dispatch(self.handler_cls, "GET", f"/api/customers?search={sample['email']}")
        self.assertEqual(st, 200)
        found = json.loads(raw.decode())
        self.assertEqual(found["items"][0]["customer_id"], sample["customer_id"])

        # Customer 360 profile + KYC + accounts
        st, _, raw = _dispatch(self.handler_cls, "GET", f"/api/customers/{sample['customer_id']}")
        self.assertEqual(st, 200)
        prof = json.loads(raw.decode())
        self.assertEqual(prof["customer"]["customer_id"], sample["customer_id"])
        self.assertIn("kyc_tier", prof["kyc_summary"])
        self.assertGreaterEqual(len(prof["accounts"]), 1)


if __name__ == "__main__":
    unittest.main()

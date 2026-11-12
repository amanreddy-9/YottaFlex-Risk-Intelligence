"""Part 2 verification suite: REST API handler, frontend static serving, graph dossier, quarantine, and live dispositions."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from yottaflex.api.server import make_handler
from yottaflex.api.service import WorkbenchService
from yottaflex.generator.exporter import export_world
from yottaflex.generator.world_generator import generate_world


class _FakeSocket:
    """In-memory socket-like wrapper to exercise BaseHTTPRequestHandler without TCP binding."""

    def __init__(self, raw_request: bytes) -> None:
        self._rfile = io.BytesIO(raw_request)
        self._wfile = io.BytesIO()

    def makefile(self, mode: str, *args, **kwargs):
        if "r" in mode:
            return self._rfile
        return self._wfile

    def sendall(self, data: bytes) -> None:
        self._wfile.write(data)

    def close(self) -> None:
        pass


def _dispatch(handler_cls, method: str, path: str, body: dict | None = None) -> tuple[int, dict[str, str], bytes]:
    body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
    headers = f"{method} {path} HTTP/1.1\r\nHost: localhost\r\n"
    if body is not None:
        headers += f"Content-Type: application/json\r\nContent-Length: {len(body_bytes)}\r\n"
    headers += "Connection: close\r\n\r\n"
    sock = _FakeSocket(headers.encode("utf-8") + body_bytes)
    handler_cls(sock, ("127.0.0.1", 0), None)
    raw = sock._wfile.getvalue()
    head, payload = raw.split(b"\r\n\r\n", 1)
    lines = head.decode("utf-8").split("\r\n")
    status = int(lines[0].split(" ")[1])
    resp_headers: dict[str, str] = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            resp_headers[k.strip().lower()] = v.strip()
    return status, resp_headers, payload


class TestPart2ApiAndFrontend(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.export_dir = Path(self.tmp.name) / "starter"
        world = generate_world(seed=20261022, scale_name="starter")
        export_world(world, self.export_dir, seed=20261022, scale_name="starter", generator_command="test")
        self.svc = WorkbenchService(self.export_dir)
        dist_dir = ROOT / "web" / "dist"
        self.web_dir = dist_dir if dist_dir.is_dir() else ROOT / "web"
        self.handler_cls = make_handler(self.svc, self.web_dir)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _get_json(self, path: str) -> dict:
        status, _, body = _dispatch(self.handler_cls, "GET", path)
        self.assertEqual(status, 200)
        return json.loads(body.decode("utf-8"))

    def test_static_frontend_assets_served(self) -> None:
        status, headers, body = _dispatch(self.handler_cls, "GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        self.assertIn(b"YottaFlex", body)

        logo_status, logo_hdrs, logo_bytes = _dispatch(self.handler_cls, "GET", "/yottaflex-logo.webp")
        self.assertEqual(logo_status, 200)
        self.assertIn("image/webp", logo_hdrs.get("content-type", ""))
        self.assertGreater(len(logo_bytes), 1000)

        assets_dir = self.web_dir / "assets"
        if assets_dir.is_dir():
            js_files = list(assets_dir.glob("*.js"))
            css_files = list(assets_dir.glob("*.css"))
            self.assertGreater(len(js_files), 0)
            self.assertGreater(len(css_files), 0)
            for asset, expected_mime in [(js_files[0], "javascript"), (css_files[0], "text/css")]:
                st, hdrs, payload = _dispatch(self.handler_cls, "GET", f"/assets/{asset.name}")
                self.assertEqual(st, 200)
                self.assertIn(expected_mime, hdrs.get("content-type", ""))
                self.assertGreater(len(payload), 1000)

    def test_overview_cases_dossier_quarantine_eval_and_live_action(self) -> None:
        ov = self._get_json("/api/overview")
        self.assertEqual(ov["seed"], 20261022)
        self.assertEqual(ov["counts"]["transactions"], 10_000)
        self.assertEqual(ov["quarantine_count"], 5)

        q = self._get_json("/api/quarantine")
        self.assertEqual(q["total_exceptions"], 5)
        self.assertEqual(set(q["counts_by_issue_type"].keys()), {
            "TXN_ON_CLOSED_ACCOUNT",
            "NEGATIVE_BALANCE_NO_OVERDRAFT",
            "UNRECONCILED_TRANSFER_LEG",
            "ORPHAN_ALERT_NO_TRIGGER",
            "DISPOSITION_PRECEDES_ALERT",
        })

        cases_resp = self._get_json("/api/cases?sort=priority&status=OPEN")
        self.assertGreater(cases_resp["total"], 5)
        top_case_id = cases_resp["items"][0]["case_id"]

        dossier = self._get_json(f"/api/cases/{top_case_id}")
        self.assertEqual(dossier["case"]["case_id"], top_case_id)
        self.assertGreater(len(dossier["graph"]["nodes"]), 1)
        self.assertGreater(len(dossier["alerts"]), 0)
        self.assertGreater(len(dossier["transactions"]), 0)
        self.assertIn("rule_severity", dossier["waterfall"])

        # Submit live immutable action
        code, _, raw = _dispatch(
            self.handler_cls,
            "POST",
            f"/api/cases/{top_case_id}/actions",
            {
                "analyst_id": "ANL-003",
                "action_type": "ESCALATE",
                "rationale": "Verified circular layering pattern across linked accounts.",
            },
        )
        res = json.loads(raw.decode("utf-8"))
        self.assertEqual(code, 201)
        self.assertEqual(res["new_status"], "ESCALATED")

        # Verify action appended immutably in dossier
        dossier_after = self._get_json(f"/api/cases/{top_case_id}")
        self.assertEqual(dossier_after["case"]["status"], "ESCALATED")
        self.assertTrue(any(a["action_type"] == "ESCALATE" for a in dossier_after["analyst_actions"]))

        # Verify premature disposition timestamp is rejected (400)
        bad_code, _, bad_raw = _dispatch(
            self.handler_cls,
            "POST",
            f"/api/cases/{top_case_id}/actions",
            {
                "analyst_id": "ANL-003",
                "action_type": "FILE_SAR",
                "rationale": "Backdated disposition test",
                "acted_at": "2026-01-01T00:00:00Z",
            },
        )
        bad_res = json.loads(bad_raw.decode("utf-8"))
        self.assertEqual(bad_code, 400)
        self.assertIn("Temporal invariant violated", bad_res["error"])

        ev = self._get_json("/api/evaluation")
        self.assertTrue(ev["negative_edge_catch_rate"]["all_types_caught"])
        self.assertGreater(ev["priority_top20"]["recall"], ev["fifo_top20"]["recall"])


if __name__ == "__main__":
    unittest.main()

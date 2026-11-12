"""Zero-dependency HTTP/REST server serving the Analyst Workbench API and static SPA."""

from __future__ import annotations

import json
import mimetypes
import threading
import time
from collections import defaultdict
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from yottaflex.api.service import WorkbenchService
from yottaflex.assistant import answer_user_query
from yottaflex.auth.auth_service import (
    AuthError,
    confirm_password_reset,
    get_session_user,
    list_sessions_and_history,
    login_user,
    logout_session,
    request_password_reset,
    revoke_user_session,
    update_profile,
)
from yottaflex.workflow.case_service import WorkflowError, submit_analyst_action
from yottaflex.workflow.triage_extensions import (
    assign_or_override_case,
    bulk_triage_alerts,
    bulk_triage_cases,
    escalate_alert_to_case,
    generate_or_save_sar_draft,
    link_or_unlink_case_alert,
    manage_watchlist_tag,
    triage_alert,
    update_case_checklist,
)


def _parse_bool_qs(qs: dict[str, list[str]], key: str) -> bool | None:
    raw = qs.get(key, [None])[0]
    if raw is None or raw == "" or raw == "ALL":
        return None
    return raw in ("1", "true", "True", "yes")


def make_handler(
    service: WorkbenchService,
    web_dir: Path,
    *,
    require_auth: bool = False,
) -> type[BaseHTTPRequestHandler]:
    """Bind service and web_dir into a ThreadingHTTPServer handler class."""
    telemetry_lock = threading.Lock()
    telemetry_routes: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"hits": 0, "errors": 0, "total_ms": 0.0, "max_ms": 0.0}
    )

    class WorkbenchHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _record_telemetry(self, status: int) -> None:
            raw_path = urlparse(getattr(self, "path", "/") or "/").path
            if not raw_path.startswith("/api/"):
                return
            t0 = getattr(self, "_req_started_at", None)
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2) if t0 is not None else 0.0
            key = f"{getattr(self, 'command', 'GET')} {raw_path}"
            with telemetry_lock:
                st = telemetry_routes[key]
                st["hits"] += 1
                if int(status) >= 400:
                    st["errors"] += 1
                st["total_ms"] += elapsed_ms
                if elapsed_ms > st["max_ms"]:
                    st["max_ms"] = elapsed_ms

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            # Concise request logging
            print(f"[api] {self.address_string()} - {format % args}")

        def _send_json(
            self,
            payload: Any,
            status: int = HTTPStatus.OK,
            extra_headers: list[tuple[str, str]] | None = None,
        ) -> None:
            self._record_telemetry(int(status))
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in extra_headers or []:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _send_static(self, rel_path: str) -> None:
            clean_rel = "index.html" if rel_path in ("", "/") else rel_path.lstrip("/")
            target = (web_dir / clean_rel).resolve()
            if not str(target).startswith(str(web_dir.resolve())) or not target.is_file():
                # Fallback to index.html for SPA routes if non-api
                fallback = (web_dir / "index.html").resolve()
                if fallback.is_file() and "." not in clean_rel:
                    target = fallback
                else:
                    self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
                    return

            mime, _ = mimetypes.guess_type(str(target))
            if target.suffix == ".js":
                mime = "application/javascript; charset=utf-8"
            elif target.suffix == ".css":
                mime = "text/css; charset=utf-8"
            elif target.suffix == ".html":
                mime = "text/html; charset=utf-8"
            elif target.suffix == ".webp":
                mime = "image/webp"
            elif target.suffix == ".png":
                mime = "image/png"
            elif target.suffix == ".svg":
                mime = "image/svg+xml"
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _bearer_token(self) -> str | None:
            auth = self.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                tok = auth[7:].strip()
                if tok:
                    return tok
            raw_cookie = self.headers.get("Cookie", "")
            if raw_cookie:
                c = SimpleCookie()
                c.load(raw_cookie)
                if "yottaflex_session" in c:
                    return c["yottaflex_session"].value
            return None

        def _require_authenticated_user(self) -> dict[str, Any] | None:
            user = get_session_user(service.db_path, self._bearer_token())
            if require_auth and not user:
                self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                return None
            return user

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            return json.loads(raw.decode("utf-8"))

        def _send_bytes(self, data: bytes, content_type: str, filename: str | None = None) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            self._req_started_at = time.perf_counter()
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)

            try:
                if path == "/api/auth/me":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                    else:
                        self._send_json({"user": user})
                elif path == "/api/auth/sessions":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                    else:
                        is_admin = user["role"] == "SYSTEM_ADMIN"
                        self._send_json(list_sessions_and_history(service.db_path, user["user_id"], include_all=is_admin))
                elif require_auth and path.startswith("/api/") and not get_session_user(service.db_path, self._bearer_token()):
                    self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                elif path == "/api/overview":
                    self._send_json(service.get_overview())
                elif path == "/api/dashboard":
                    self._send_json(
                        service.get_dashboard(
                            start_date=qs.get("start_date", [None])[0],
                            end_date=qs.get("end_date", [None])[0],
                            period=qs.get("period", ["ALL"])[0],
                            risk_level=qs.get("risk_level", ["ALL"])[0],
                            txn_type=qs.get("txn_type", ["ALL"])[0],
                            status=qs.get("status", ["ALL"])[0],
                        )
                    )
                elif path == "/api/dashboard/export":
                    fmt = qs.get("format", ["csv"])[0]
                    data, ctype, fname = service.export_dashboard_report(
                        fmt=fmt,
                        start_date=qs.get("start_date", [None])[0],
                        end_date=qs.get("end_date", [None])[0],
                        period=qs.get("period", ["ALL"])[0],
                        risk_level=qs.get("risk_level", ["ALL"])[0],
                        txn_type=qs.get("txn_type", ["ALL"])[0],
                        status=qs.get("status", ["ALL"])[0],
                    )
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/customers":
                    self._send_json(
                        service.list_customers(
                            search=qs.get("search", [None])[0],
                            kyc_tier=qs.get("kyc_tier", ["ALL"])[0],
                            risk_rating=qs.get("risk_rating", ["ALL"])[0],
                            account_status=qs.get("account_status", ["ALL"])[0],
                            multi_suspicious=qs.get("multi_suspicious", ["0"])[0] in ("1", "true", "True"),
                            limit=int(qs.get("limit", ["60"])[0]),
                            offset=int(qs.get("offset", ["0"])[0]),
                        )
                    )
                elif path.startswith("/api/customers/") and len(path.split("/")) == 5 and path.endswith("/peer-baseline"):
                    cust_id = path.split("/")[3]
                    res = service.get_customer_peer_baseline(cust_id)
                    if res is None:
                        self._send_json({"error": f"Customer '{cust_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(res)
                elif path.startswith("/api/customers/") and len(path.split("/")) == 5 and path.endswith("/kyc-reviews"):
                    cust_id = path.split("/")[3]
                    self._send_json({"customer_id": cust_id, "reviews": service.list_kyc_reviews(cust_id)})
                elif path.startswith("/api/customers/") and len(path.split("/")) == 5 and path.endswith("/export"):
                    cust_id = path.split("/")[3]
                    fmt = qs.get("format", ["csv"])[0]
                    res = service.export_customer_summary(cust_id, fmt=fmt)
                    if res is None:
                        self._send_json({"error": f"Customer '{cust_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        data, ctype, fname = res
                        self._send_bytes(data, ctype, fname)
                elif path == "/api/customers/export":
                    user = get_session_user(service.db_path, self._bearer_token())
                    data, ctype, fname = service.export_customers_directory(
                        fmt=qs.get("format", ["csv"])[0],
                        search=qs.get("search", [None])[0],
                        kyc_tier=qs.get("kyc_tier", ["ALL"])[0],
                        risk_rating=qs.get("risk_rating", ["ALL"])[0],
                        account_status=qs.get("account_status", ["ALL"])[0],
                        multi_suspicious=qs.get("multi_suspicious", ["0"])[0] in ("1", "true", "True"),
                        actor_id=user["analyst_code"] if user else "SYSTEM",
                    )
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/customers/shared-pii":
                    self._send_json(service.find_shared_pii_clusters(limit=int(qs.get("limit", ["25"])[0])))
                elif path.startswith("/api/customers/") and len(path.split("/")) == 5 and path.endswith("/chronology"):
                    cust_id = path.split("/")[3]
                    self._send_json(service.get_customer_chronology(cust_id, limit=int(qs.get("limit", ["80"])[0])))
                elif path.startswith("/api/customers/") and len(path.split("/")) == 5 and path.endswith("/corridor-exposure"):
                    cust_id = path.split("/")[3]
                    self._send_json(service.get_customer_corridor_exposure(cust_id))
                elif path.startswith("/api/customers/") and len(path.split("/")) == 4:
                    cust_id = path.split("/")[3]
                    prof = service.get_customer_profile(cust_id)
                    if prof is None:
                        self._send_json({"error": f"Customer '{cust_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(prof)
                elif path == "/api/accounts/export":
                    user = get_session_user(service.db_path, self._bearer_token())
                    data, ctype, fname = service.export_accounts_directory(
                        fmt=qs.get("format", ["csv"])[0],
                        search=qs.get("search", [None])[0],
                        status=qs.get("status", ["ALL"])[0],
                        dormant_reactivated=qs.get("dormant_reactivated", ["0"])[0] in ("1", "true", "True"),
                        actor_id=user["analyst_code"] if user else "SYSTEM",
                    )
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/accounts":
                    self._send_json(
                        service.list_accounts(
                            search=qs.get("search", [None])[0],
                            status=qs.get("status", ["ALL"])[0],
                            dormant_reactivated=qs.get("dormant_reactivated", ["0"])[0] in ("1", "true", "True"),
                            limit=int(qs.get("limit", ["60"])[0]),
                            offset=int(qs.get("offset", ["0"])[0]),
                        )
                    )
                elif path.startswith("/api/accounts/") and len(path.split("/")) == 5 and path.endswith("/control"):
                    acct_id = path.split("/")[3]
                    self._send_json(service.get_account_control(acct_id))
                elif path.startswith("/api/accounts/") and len(path.split("/")) == 5 and path.endswith("/velocity"):
                    acct_id = path.split("/")[3]
                    self._send_json(service.get_account_velocity(acct_id))
                elif path.startswith("/api/accounts/") and len(path.split("/")) == 5 and path.endswith("/burst-profile"):
                    acct_id = path.split("/")[3]
                    self._send_json(service.get_account_burst_profile(acct_id))
                elif path.startswith("/api/accounts/") and len(path.split("/")) == 5 and path.endswith("/transfer-matrix"):
                    acct_id = path.split("/")[3]
                    self._send_json(service.get_account_transfer_matrix(acct_id))
                elif path.startswith("/api/accounts/") and len(path.split("/")) == 4:
                    acct_id = path.split("/")[3]
                    acct_det = service.get_account_detail(acct_id)
                    if acct_det is None:
                        self._send_json({"error": f"Account '{acct_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(acct_det)
                elif path == "/api/transactions":
                    min_a = qs.get("min_amount", [None])[0]
                    max_a = qs.get("max_amount", [None])[0]
                    self._send_json(
                        service.list_transactions(
                            search=qs.get("search", [None])[0],
                            start_date=qs.get("start_date", [None])[0],
                            end_date=qs.get("end_date", [None])[0],
                            min_amount=float(min_a) if min_a else None,
                            max_amount=float(max_a) if max_a else None,
                            txn_type=qs.get("txn_type", ["ALL"])[0],
                            risk_level=qs.get("risk_level", ["ALL"])[0],
                            status=qs.get("status", ["ALL"])[0],
                            pattern=qs.get("pattern", ["ALL"])[0],
                            sort_by=qs.get("sort_by", ["occurred_at"])[0],
                            sort_dir=qs.get("sort_dir", ["desc"])[0],
                            limit=int(qs.get("limit", ["50"])[0]),
                            offset=int(qs.get("offset", ["0"])[0]),
                        )
                    )
                elif path == "/api/transactions/export":
                    min_a = qs.get("min_amount", [None])[0]
                    max_a = qs.get("max_amount", [None])[0]
                    fmt = qs.get("format", ["csv"])[0]
                    data, ctype, fname = service.export_transactions_report(
                        fmt=fmt,
                        search=qs.get("search", [None])[0],
                        start_date=qs.get("start_date", [None])[0],
                        end_date=qs.get("end_date", [None])[0],
                        min_amount=float(min_a) if min_a else None,
                        max_amount=float(max_a) if max_a else None,
                        txn_type=qs.get("txn_type", ["ALL"])[0],
                        risk_level=qs.get("risk_level", ["ALL"])[0],
                        status=qs.get("status", ["ALL"])[0],
                        pattern=qs.get("pattern", ["ALL"])[0],
                        sort_by=qs.get("sort_by", ["occurred_at"])[0],
                        sort_dir=qs.get("sort_dir", ["desc"])[0],
                    )
                    self._send_bytes(data, ctype, fname)
                elif path.startswith("/api/transactions/") and len(path.split("/")) == 4:
                    txn_id = path.split("/")[3]
                    txn_det = service.get_transaction_detail(txn_id)
                    if txn_det is None:
                        self._send_json({"error": f"Transaction '{txn_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(txn_det)
                elif path == "/api/risk/scoring":
                    self._send_json(service.get_risk_scoring())
                elif path == "/api/risk/integrity-detectors":
                    self._send_json(service.get_integrity_detectors())
                elif path == "/api/risk/executions":
                    self._send_json(service.get_risk_executions_and_history(entity_id=qs.get("entity_id", [None])[0]))
                elif path == "/api/risk/calibration-proposals":
                    self._send_json({"items": service.list_calibration_proposals()})
                elif path == "/api/alerts/suppressions":
                    self._send_json({"items": service.list_suppression_rules(active_only=qs.get("active_only", ["1"])[0] != "0")})
                elif path == "/api/alerts/export":
                    data, ctype, fname = service.export_alerts_report(
                        fmt=qs.get("format", ["csv"])[0],
                        search=qs.get("search", [None])[0],
                        severity=qs.get("severity", ["ALL"])[0],
                        rule_id=qs.get("rule_id", ["ALL"])[0],
                        status=qs.get("status", ["ALL"])[0],
                        owner_analyst=qs.get("owner_analyst", ["ALL"])[0],
                        sla_breached=_parse_bool_qs(qs, "sla_breached"),
                        start_date=qs.get("start_date", [None])[0],
                        end_date=qs.get("end_date", [None])[0],
                        sort_by=qs.get("sort_by", ["risk_score"])[0],
                        sort_dir=qs.get("sort_dir", ["desc"])[0],
                    )
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/alerts":
                    self._send_json(
                        service.list_alerts(
                            search=qs.get("search", [None])[0],
                            severity=qs.get("severity", ["ALL"])[0],
                            rule_id=qs.get("rule_id", ["ALL"])[0],
                            status=qs.get("status", ["ALL"])[0],
                            owner_analyst=qs.get("owner_analyst", ["ALL"])[0],
                            sla_breached=_parse_bool_qs(qs, "sla_breached"),
                            start_date=qs.get("start_date", [None])[0],
                            end_date=qs.get("end_date", [None])[0],
                            sort_by=qs.get("sort_by", ["risk_score"])[0],
                            sort_dir=qs.get("sort_dir", ["desc"])[0],
                            limit=int(qs.get("limit", ["50"])[0]),
                            offset=int(qs.get("offset", ["0"])[0]),
                        )
                    )
                elif path == "/api/alerts/co-occurrence":
                    self._send_json(service.get_alert_co_occurrence())
                elif path == "/api/alerts/fatigue-report":
                    self._send_json(service.get_alert_fatigue_report())
                elif path.startswith("/api/alerts/") and len(path.split("/")) == 4:
                    al_id = path.split("/")[3]
                    al_det = service.get_alert_detail(al_id)
                    if al_det is None:
                        self._send_json({"error": f"Alert '{al_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(al_det)
                elif path == "/api/cases/export":
                    min_e = qs.get("min_exposure", [None])[0]
                    max_e = qs.get("max_exposure", [None])[0]
                    data, ctype, fname = service.export_cases_report(
                        fmt=qs.get("format", ["csv"])[0],
                        sort=qs.get("sort", ["priority"])[0],
                        tier=qs.get("tier", [None])[0],
                        status=qs.get("status", [None])[0],
                        linkage=qs.get("linkage", [None])[0],
                        search=qs.get("search", [None])[0],
                        assigned_analyst=qs.get("assigned_analyst", [None])[0],
                        min_exposure=float(min_e) if min_e else None,
                        max_exposure=float(max_e) if max_e else None,
                        start_date=qs.get("start_date", [None])[0],
                        end_date=qs.get("end_date", [None])[0],
                        sla_breached=_parse_bool_qs(qs, "sla_breached"),
                    )
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/cases":
                    min_e = qs.get("min_exposure", [None])[0]
                    max_e = qs.get("max_exposure", [None])[0]
                    self._send_json(
                        service.list_cases(
                            sort=qs.get("sort", ["priority"])[0],
                            tier=qs.get("tier", [None])[0],
                            status=qs.get("status", [None])[0],
                            linkage=qs.get("linkage", [None])[0],
                            search=qs.get("search", [None])[0],
                            assigned_analyst=qs.get("assigned_analyst", [None])[0],
                            min_exposure=float(min_e) if min_e else None,
                            max_exposure=float(max_e) if max_e else None,
                            start_date=qs.get("start_date", [None])[0],
                            end_date=qs.get("end_date", [None])[0],
                            sla_breached=_parse_bool_qs(qs, "sla_breached"),
                            limit=int(qs.get("limit", ["150"])[0]),
                            offset=int(qs.get("offset", ["0"])[0]),
                        )
                    )
                elif path == "/api/cases/escalations/pending":
                    self._send_json(service.list_pending_escalations(limit=int(qs.get("limit", ["80"])[0])))
                elif path == "/api/cases/sla-radar":
                    self._send_json(service.get_sla_radar(warning_hours=int(qs.get("warning_hours", ["8"])[0])))
                elif path == "/api/cases/merge-candidates":
                    self._send_json(service.find_case_merge_candidates(limit=int(qs.get("limit", ["20"])[0])))
                elif len(path.strip("/").split("/")) == 4 and path.startswith("/api/cases/") and path.endswith("/pins"):
                    case_id = path.strip("/").split("/")[2]
                    self._send_json({"case_id": case_id, "items": service.list_case_pins(case_id)})
                elif len(path.strip("/").split("/")) == 4 and path.startswith("/api/cases/") and path.endswith("/comments"):
                    case_id = path.strip("/").split("/")[2]
                    self._send_json({"case_id": case_id, "items": service.list_case_comments(case_id)})
                elif len(path.strip("/").split("/")) == 4 and path.startswith("/api/cases/") and path.endswith("/export"):
                    case_id = path.strip("/").split("/")[2]
                    pkt = service.export_case_packet(case_id, fmt=qs.get("format", ["json"])[0])
                    if pkt is None:
                        self._send_json({"error": f"Case '{case_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        data, ctype, fname = pkt
                        self._send_bytes(data, ctype, fname)
                elif path == "/api/cases/tier-workload":
                    self._send_json(service.get_tier_workload_projection())
                elif path.startswith("/api/cases/") and len(path.split("/")) == 4:
                    case_id = path.split("/")[3]
                    dossier = service.get_case_dossier(case_id)
                    if dossier is None:
                        self._send_json({"error": f"Case '{case_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(dossier)
                elif path == "/api/quarantine/export":
                    data, ctype, fname = service.export_quarantine_report(
                        fmt=qs.get("format", ["csv"])[0],
                        search=qs.get("search", [None])[0],
                        issue_type=qs.get("issue_type", ["ALL"])[0],
                        severity=qs.get("severity", ["ALL"])[0],
                        review_status=qs.get("review_status", ["ALL"])[0],
                        sort_by=qs.get("sort_by", ["severity"])[0],
                    )
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/quarantine/balance-continuity":
                    self._send_json(service.check_balance_continuity(limit=int(qs.get("limit", ["25"])[0])))
                elif path == "/api/quarantine/grouped":
                    self._send_json(service.get_quarantine_grouped())
                elif len(path.strip("/").split("/")) == 3 and path.startswith("/api/quarantine/"):
                    exc_id = path.strip("/").split("/")[2]
                    detail = service.get_quarantine_detail(exc_id)
                    if detail is None:
                        self._send_json({"error": f"Quarantine exception '{exc_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(detail)
                elif path == "/api/quarantine":
                    self._send_json(
                        service.list_quarantine_exceptions_filtered(
                            search=qs.get("search", [None])[0],
                            issue_type=qs.get("issue_type", ["ALL"])[0],
                            severity=qs.get("severity", ["ALL"])[0],
                            review_status=qs.get("review_status", ["ALL"])[0],
                            sort_by=qs.get("sort_by", ["severity"])[0],
                        )
                    )
                elif path == "/api/audit/export":
                    data, ctype, fname = service.export_audit_events(
                        fmt=qs.get("format", ["csv"])[0],
                        source=qs.get("source", ["ALL"])[0],
                        actor=qs.get("actor", ["ALL"])[0],
                        entity_id=qs.get("entity_id", [None])[0],
                        search=qs.get("search", [None])[0],
                        start_date=qs.get("start_date", [None])[0],
                        end_date=qs.get("end_date", [None])[0],
                    )
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/audit/events":
                    self._send_json(
                        service.get_unified_audit_events(
                            source=qs.get("source", ["ALL"])[0],
                            actor=qs.get("actor", ["ALL"])[0],
                            entity_id=qs.get("entity_id", [None])[0],
                            search=qs.get("search", [None])[0],
                            start_date=qs.get("start_date", [None])[0],
                            end_date=qs.get("end_date", [None])[0],
                            limit=int(qs.get("limit", ["80"])[0]),
                            offset=int(qs.get("offset", ["0"])[0]),
                        )
                    )
                elif path == "/api/audit/analyst-stats":
                    self._send_json(service.get_analyst_leaderboard())
                elif path == "/api/admin/users":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and user and user["role"] not in {"SYSTEM_ADMIN", "RISK_REVIEWER"}:
                        self._send_json(
                            {"error": f"Role '{user['role']}' lacks permission to inspect user directory."},
                            HTTPStatus.FORBIDDEN,
                        )
                    else:
                        self._send_json({"users": service.list_admin_users()})
                elif path == "/api/admin/sla-policies":
                    self._send_json(service.get_sla_policies())
                elif path == "/api/watchlist-tags":
                    self._send_json(
                        service.list_watchlist_tags(
                            entity_type=qs.get("entity_type", ["ALL"])[0],
                            tag=qs.get("tag", ["ALL"])[0],
                            search=qs.get("search", [None])[0],
                            limit=int(qs.get("limit", ["200"])[0]),
                        )
                    )
                elif path == "/api/saved-views":
                    user = get_session_user(service.db_path, self._bearer_token())
                    uid = user["user_id"] if user else "USR-001"
                    self._send_json({"items": service.list_saved_views(user_id=uid, workspace=qs.get("workspace", ["ALL"])[0])})
                elif path == "/api/rules":
                    self._send_json({"rules": service.list_rules()})
                elif path == "/api/evaluation/simulate-k":
                    self._send_json(service.simulate_evaluation_cutoff(k_pct=float(qs.get("k_pct", ["20"])[0])))
                elif path == "/api/evaluation/rule-performance":
                    self._send_json(service.get_rule_performance_attribution())
                elif path == "/api/evaluation/zero-leakage":
                    self._send_json(service.check_zero_leakage_live())
                elif path == "/api/evaluation/export":
                    data, ctype, fname = service.export_evaluation_report(fmt=qs.get("format", ["json"])[0])
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/evaluation":
                    self._send_json(service.get_evaluation())
                elif path == "/api/network/rings":
                    self._send_json(
                        service.detect_collusion_rings(
                            min_accounts=int(qs.get("min_accounts", ["2"])[0]),
                            limit=int(qs.get("limit", ["20"])[0]),
                        )
                    )
                elif path == "/api/network/overview":
                    self._send_json(service.get_financial_network_overview())
                elif path == "/api/network/graph":
                    seed = qs.get("seed_id", [None])[0]
                    depth = int(qs.get("depth", ["2"])[0])
                    limit = int(qs.get("limit", ["75"])[0])
                    self._send_json(service.get_financial_network_graph(seed_id=seed, depth=depth, max_nodes=limit))
                elif path == "/api/network/entities/search":
                    q = qs.get("q", [""])[0]
                    etype = qs.get("type", ["ALL"])[0]
                    limit = int(qs.get("limit", ["15"])[0])
                    self._send_json({"items": service.search_network_entities(q, entity_type=etype, limit=limit)})
                elif path == "/api/network/paths":
                    src = qs.get("source", [""])[0]
                    dst = qs.get("dest", [""])[0]
                    depth = int(qs.get("depth", ["4"])[0])
                    self._send_json(service.trace_money_flow_path(src, dst, max_depth=depth))
                elif path == "/api/network/cycles":
                    limit = int(qs.get("limit", ["15"])[0])
                    self._send_json({"cycles": service.detect_circular_transfers(limit=limit)})
                elif path == "/api/network/patterns":
                    self._send_json(service.detect_suspicious_patterns())
                elif path == "/api/network/entity-resolution":
                    limit = int(qs.get("limit", ["30"])[0])
                    self._send_json({"items": service.resolve_entities(limit=limit)})
                elif path == "/api/network/risk-analysis":
                    seed = qs.get("seed_id", [None])[0]
                    self._send_json(service.compute_network_risk_analysis(seed_id=seed))
                elif len(path.strip("/").split("/")) == 4 and path.startswith("/api/network/entity/"):
                    ent_id = path.strip("/").split("/")[3]
                    net = service.get_entity_network(ent_id)
                    if net is None:
                        self._send_json({"error": f"Entity '{ent_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(net)
                elif path == "/api/sar/registry":
                    self._send_json(
                        service.list_sar_registry(
                            status=qs.get("status", ["ALL"])[0],
                            limit=int(qs.get("limit", ["100"])[0]),
                        )
                    )
                elif len(path.strip("/").split("/")) == 4 and path.startswith("/api/cases/") and path.endswith("/similar"):
                    case_id = path.strip("/").split("/")[2]
                    sim = service.get_similar_cases(case_id, limit=int(qs.get("limit", ["5"])[0]))
                    if sim is None:
                        self._send_json({"error": f"Case '{case_id}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(sim)
                elif path == "/api/reports/executive-digest/export":
                    data, ctype, fname = service.export_executive_digest(fmt=qs.get("format", ["md"])[0])
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/reports/executive-digest":
                    self._send_json(service.get_executive_digest())
                elif path == "/api/search/global":
                    self._send_json(
                        service.global_search(
                            query=qs.get("q", [""])[0],
                            limit_per_group=int(qs.get("limit", ["5"])[0]),
                        )
                    )
                elif path == "/api/system/health":
                    self._send_json(service.get_system_health())
                elif path == "/api/analytics/corridors":
                    self._send_json(service.get_corridor_risk_matrix(limit=int(qs.get("limit", ["80"])[0])))
                elif path == "/api/analytics/high-risk-countries":
                    self._send_json({"items": service.list_high_risk_countries()})
                elif path == "/api/analytics/merchants":
                    self._send_json(
                        service.get_merchant_leaderboard(
                            search=qs.get("search", [None])[0],
                            limit=int(qs.get("limit", ["100"])[0]),
                        )
                    )
                elif len(path.strip("/").split("/")) == 4 and path.startswith("/api/analytics/merchants/"):
                    mid = path.strip("/").split("/")[3]
                    det = service.get_merchant_detail(mid)
                    if det is None:
                        self._send_json({"error": f"Merchant '{mid}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(det)
                elif path == "/api/analytics/structuring":
                    self._send_json(
                        service.detect_structuring_clusters(
                            min_txns=int(qs.get("min_txns", ["2"])[0]),
                            limit=int(qs.get("limit", ["80"])[0]),
                        )
                    )
                elif len(path.strip("/").split("/")) == 4 and path.startswith("/api/network/flow-chains/"):
                    aid = path.strip("/").split("/")[3]
                    self._send_json(service.trace_flow_chains(aid, max_hops=int(qs.get("max_hops", ["3"])[0])))
                elif path == "/api/playbooks":
                    self._send_json({"items": service.get_playbooks()})
                elif path == "/api/audit/exports":
                    self._send_json({"items": service.list_export_history(limit=int(qs.get("limit", ["100"])[0]))})
                elif path == "/api/evaluation/threshold-sweep":
                    self._send_json(service.sweep_rule_threshold(rule_id=qs.get("rule_id", ["RULE-001"])[0]))
                elif path == "/api/evaluation/temporal-drift":
                    self._send_json(service.compute_temporal_drift(buckets=int(qs.get("buckets", ["6"])[0])))
                elif path == "/api/notifications":
                    user = get_session_user(service.db_path, self._bearer_token())
                    uid = user["user_id"] if user else "USR-001"
                    self._send_json(service.list_notifications(uid, unread_only=qs.get("unread_only", ["0"])[0] == "1"))
                elif path == "/api/integrations/siem":
                    self._send_json(service.list_siem_outbox(limit=int(qs.get("limit", ["50"])[0])))
                elif path == "/api/system/jobs":
                    self._send_json({"items": service.list_pipeline_runs(limit=int(qs.get("limit", ["30"])[0]))})
                elif path == "/api/reports/compliance-bundle":
                    user = get_session_user(service.db_path, self._bearer_token())
                    data, ctype, fname = service.export_compliance_bundle(actor_id=user["analyst_code"] if user else "SYSTEM")
                    self._send_bytes(data, ctype, fname)
                elif path == "/api/auth/preferences":
                    user = get_session_user(service.db_path, self._bearer_token())
                    uid = user["user_id"] if user else "USR-001"
                    self._send_json(service.get_user_preferences(uid))
                elif path == "/api/screening/history":
                    self._send_json({"items": service.list_screening_history(entity_id=qs.get("entity_id", [None])[0], limit=int(qs.get("limit", ["50"])[0]))})
                elif path == "/api/network/fan-hubs":
                    self._send_json(service.get_fan_in_out_hubs(limit=int(qs.get("limit", ["25"])[0])))
                elif path == "/api/network/device-velocity":
                    self._send_json(service.get_device_velocity_leaderboard(limit=int(qs.get("limit", ["25"])[0])))
                elif path == "/api/analytics/mcc-outliers":
                    self._send_json(service.detect_mcc_outliers(limit=int(qs.get("limit", ["25"])[0])))
                elif path == "/api/risk/custom-rules":
                    self._send_json({"items": service.list_custom_rule_drafts()})
                elif path == "/api/governance/qa-samples":
                    self._send_json(service.list_qa_samples(limit=int(qs.get("limit", ["20"])[0])))
                elif path == "/api/governance/exam-readiness":
                    self._send_json({"items": service.list_exam_readiness()})
                elif path == "/api/integrations/webhooks":
                    self._send_json({"items": service.list_webhooks()})
                elif path == "/api/audit/verify-chain":
                    self._send_json(service.verify_audit_chain())
                elif path == "/api/evaluation/lift-curve":
                    self._send_json(service.get_evaluation_lift_curve())
                elif path == "/api/evaluation/score-histogram":
                    self._send_json(service.get_evaluation_score_histogram())
                elif path == "/api/evaluation/typology-severity-matrix":
                    self._send_json(service.get_evaluation_typology_severity_matrix())
                elif path == "/api/evaluation/rule-marginal-lift":
                    self._send_json(service.get_evaluation_rule_marginal_lift())
                elif path == "/api/evaluation/feature-psi":
                    self._send_json(service.get_evaluation_feature_psi())
                elif path == "/api/system/data-scorecard":
                    self._send_json(service.get_data_scorecard())
                elif path == "/api/system/telemetry":
                    with telemetry_lock:
                        snapshot = [
                            {
                                "route": k,
                                "hits": v["hits"],
                                "errors": v["errors"],
                                "avg_ms": round(v["total_ms"] / max(1, v["hits"]), 2),
                                "max_ms": v["max_ms"],
                            }
                            for k, v in sorted(telemetry_routes.items(), key=lambda kv: -kv[1]["hits"])[:40]
                        ]
                    self._send_json({"routes": snapshot})
                elif path == "/api/search/bookmarks":
                    user = get_session_user(service.db_path, self._bearer_token())
                    self._send_json({"items": service.list_search_bookmarks(user["user_id"] if user else "USR-001")})
                elif path == "/api/search/commands":
                    self._send_json(
                        {
                            "commands": [
                                {"id": "queue", "label": "Open Priority Triage Queue", "shortcut": "G Q"},
                                {"id": "evaluation", "label": "Open Evaluation & PSI Drift Lab", "shortcut": "G E"},
                                {"id": "governance", "label": "Open Intelligence, QA & Telemetry", "shortcut": "G G"},
                                {"id": "quarantine", "label": "Open Quarantine Invariants", "shortcut": "G X"},
                            ]
                        }
                    )
                elif path == "/api/reports/schedules":
                    self._send_json({"items": service.list_scheduled_digests()})
                elif path == "/api/system/retention":
                    self._send_json(service.get_retention_status())
                elif path == "/api/workspace/pinned-entities":
                    user = get_session_user(service.db_path, self._bearer_token())
                    self._send_json({"items": service.list_workspace_pins(user["user_id"] if user else "USR-001")})
                elif path.startswith("/api/cases/") and len(path.strip("/").split("/")) == 4 and path.endswith("/handoffs"):
                    cid = path.strip("/").split("/")[2]
                    self._send_json({"case_id": cid, "items": service.list_case_handoffs(cid)})
                elif path.startswith("/api/cases/") and len(path.strip("/").split("/")) == 4 and path.endswith("/seals"):
                    cid = path.strip("/").split("/")[2]
                    self._send_json({"case_id": cid, "items": service.list_case_seals(cid)})
                elif path.startswith("/api/cases/") and len(path.strip("/").split("/")) == 4 and path.endswith("/related-timeline"):
                    cid = path.strip("/").split("/")[2]
                    self._send_json(service.get_related_cases_timeline(cid))
                elif path.startswith("/api/cases/") and len(path.strip("/").split("/")) == 5 and "/compare/" in path:
                    seg = path.strip("/").split("/")
                    self._send_json(service.compare_two_cases(seg[2], seg[4]))
                elif path.startswith("/api/"):
                    self._send_json({"error": "Unknown API endpoint"}, HTTPStatus.NOT_FOUND)
                else:
                    self._send_static(path)
            except Exception as exc:  # pragma: no cover
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_PATCH(self) -> None:  # noqa: N802
            self._req_started_at = time.perf_counter()
            parsed = urlparse(self.path)
            if parsed.path == "/api/auth/profile":
                user = get_session_user(service.db_path, self._bearer_token())
                if not user:
                    self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                    return
                try:
                    body = self._read_json_body()
                    updated = update_profile(
                        service.db_path,
                        user_id=user["user_id"],
                        full_name=body.get("full_name", user["full_name"]),
                        phone=body.get("phone", user["phone"]),
                        department=body.get("department", user["department"]),
                        title=body.get("title", user["title"]),
                    )
                    self._send_json({"user": updated})
                except AuthError as exc:
                    self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            elif parsed.path == "/api/auth/preferences":
                user = get_session_user(service.db_path, self._bearer_token())
                if require_auth and not user:
                    self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                    return
                body = self._read_json_body()
                res = service.update_user_preferences(
                    user_id=user["user_id"] if user else "USR-001",
                    default_tab=body.get("default_tab"),
                    default_page_size=body.get("default_page_size"),
                    sla_lead_hours=body.get("sla_lead_hours"),
                    compact_mode=body.get("compact_mode"),
                )
                self._send_json(res, HTTPStatus.OK)
            else:
                self._send_json({"error": "Endpoint not found"}, HTTPStatus.NOT_FOUND)

        def do_DELETE(self) -> None:  # noqa: N802
            self._req_started_at = time.perf_counter()
            parsed = urlparse(self.path)
            parts = parsed.path.strip("/").split("/")
            user = get_session_user(service.db_path, self._bearer_token())
            if require_auth and not user:
                self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                return
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "saved-views":
                deleted = service.delete_saved_view(
                    user_id=user["user_id"] if user else "USR-001",
                    view_id=parts[2],
                    is_admin=bool(user and user["role"] == "SYSTEM_ADMIN"),
                )
                if not deleted:
                    self._send_json({"error": "Saved view not found"}, HTTPStatus.NOT_FOUND)
                else:
                    self._send_json({"deleted": True, "view_id": parts[2]}, HTTPStatus.OK)
            elif len(parts) == 4 and parts[0] == "api" and parts[1] == "analytics" and parts[2] == "high-risk-countries":
                if user and user["role"] != "SYSTEM_ADMIN":
                    self._send_json({"error": "Only SYSTEM_ADMIN can remove watched jurisdictions"}, HTTPStatus.FORBIDDEN)
                    return
                ok = service.delete_high_risk_country(parts[3])
                self._send_json({"deleted": ok, "country_code": parts[3]}, HTTPStatus.OK if ok else HTTPStatus.NOT_FOUND)
            elif len(parts) == 5 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "pins":
                ok = service.delete_case_pin(case_id=parts[2], pin_id=parts[4])
                self._send_json({"deleted": ok, "pin_id": parts[4]}, HTTPStatus.OK if ok else HTTPStatus.NOT_FOUND)
            elif len(parts) == 4 and parts[0] == "api" and parts[1] == "alerts" and parts[2] == "suppressions":
                ok = service.deactivate_suppression_rule(parts[3])
                self._send_json({"deactivated": ok, "suppression_id": parts[3]}, HTTPStatus.OK if ok else HTTPStatus.NOT_FOUND)
            elif len(parts) == 4 and parts[0] == "api" and parts[1] == "integrations" and parts[2] == "webhooks":
                ok = service.delete_webhook(parts[3])
                self._send_json({"deleted": ok, "webhook_id": parts[3]}, HTTPStatus.OK if ok else HTTPStatus.NOT_FOUND)
            elif len(parts) == 4 and parts[0] == "api" and parts[1] == "search" and parts[2] == "bookmarks":
                ok = service.delete_search_bookmark(user["user_id"] if user else "USR-001", parts[3])
                self._send_json({"deleted": ok, "bookmark_id": parts[3]}, HTTPStatus.OK if ok else HTTPStatus.NOT_FOUND)
            elif len(parts) == 4 and parts[0] == "api" and parts[1] == "workspace" and parts[2] == "pinned-entities":
                ok = service.delete_workspace_pin(user["user_id"] if user else "USR-001", parts[3])
                self._send_json({"deleted": ok, "pin_id": parts[3]}, HTTPStatus.OK if ok else HTTPStatus.NOT_FOUND)
            else:
                self._send_json({"error": "Endpoint not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            self._req_started_at = time.perf_counter()
            parsed = urlparse(self.path)
            path = parsed.path
            parts = path.strip("/").split("/")
            try:
                if path == "/api/auth/login":
                    body = self._read_json_body()
                    res = login_user(
                        service.db_path,
                        email=body.get("email", ""),
                        password=body.get("password", ""),
                        client_ip=self.address_string(),
                        user_agent=self.headers.get("User-Agent", "YottaFlex-Web"),
                    )
                    cookie_hdr = f"yottaflex_session={res['token']}; Path=/; HttpOnly; SameSite=Lax"
                    self._send_json(res, HTTPStatus.OK, extra_headers=[("Set-Cookie", cookie_hdr)])
                    return
                if path == "/api/auth/logout":
                    tok = self._bearer_token()
                    if tok:
                        logout_session(service.db_path, tok, client_ip=self.address_string())
                    self._send_json(
                        {"status": "LOGGED_OUT"},
                        HTTPStatus.OK,
                        extra_headers=[("Set-Cookie", "yottaflex_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")],
                    )
                    return
                if path == "/api/auth/forgot-password":
                    body = self._read_json_body()
                    res = request_password_reset(service.db_path, body.get("email", ""), client_ip=self.address_string())
                    self._send_json(res)
                    return
                if path == "/api/auth/reset-password":
                    body = self._read_json_body()
                    res = confirm_password_reset(
                        service.db_path,
                        email=body.get("email", ""),
                        reset_code=body.get("reset_code", ""),
                        new_password=body.get("new_password", ""),
                        client_ip=self.address_string(),
                    )
                    self._send_json(res)
                    return
                if path == "/api/auth/sessions/revoke":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    revoke_user_session(
                        service.db_path,
                        user_id=user["user_id"],
                        session_id=body.get("session_id", ""),
                        is_admin=(user["role"] == "SYSTEM_ADMIN"),
                    )
                    self._send_json({"status": "REVOKED"})
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "actions":
                    case_id = parts[2]
                    body = self._read_json_body()
                    # Enforce RBAC when session token is provided
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    action_type = body.get("action_type", "")
                    if user:
                        if action_type == "FILE_SAR" and "file_sar" not in user["permissions"] and user["role"] != "SYSTEM_ADMIN":
                            self._send_json(
                                {"error": f"Role '{user['role']}' lacks permission 'file_sar'."},
                                HTTPStatus.FORBIDDEN,
                            )
                            return
                        if action_type == "REOPEN_CASE" and "reopen_closed_cases" not in user["permissions"] and user["role"] != "SYSTEM_ADMIN":
                            self._send_json(
                                {"error": f"Role '{user['role']}' lacks permission 'reopen_closed_cases'."},
                                HTTPStatus.FORBIDDEN,
                            )
                            return
                        if action_type in {"CONFIRM_FRAUD", "MARK_FALSE_POSITIVE"} and user["role"] == "OPS_ANALYST":
                            dos_check = service.get_case_dossier(case_id)
                            if dos_check and float(dos_check["case"]["total_exposure_amount"]) >= 25000.0:
                                self._send_json(
                                    {"error": "High-exposure cases (>= $25,000) require RISK_REVIEWER or SYSTEM_ADMIN sign-off."},
                                    HTTPStatus.FORBIDDEN,
                                )
                                return
                    result = submit_analyst_action(
                        service.db_path,
                        case_id=case_id,
                        analyst_id=body.get("analyst_id", user["analyst_code"] if user else "ANL-001"),
                        action_type=action_type,
                        rationale=body.get("rationale", ""),
                        acted_at=body.get("acted_at"),
                    )
                    self._send_json(result, HTTPStatus.CREATED)
                    return
                if path == "/api/alerts/bulk-triage":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = bulk_triage_alerts(
                        service.db_path,
                        alert_ids=list(body.get("alert_ids") or []),
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        action=str(body.get("action") or ""),
                        owner_analyst_id=body.get("owner_analyst_id"),
                        suppression_reason=body.get("suppression_reason"),
                        rationale=str(body.get("rationale") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "alerts" and parts[3] == "triage":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = triage_alert(
                        service.db_path,
                        alert_id=parts[2],
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        owner_analyst_id=body.get("owner_analyst_id"),
                        status=body.get("status"),
                        disposition=body.get("disposition"),
                        suppression_reason=body.get("suppression_reason"),
                        note=body.get("note"),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "alerts" and parts[3] == "escalate":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = escalate_alert_to_case(
                        service.db_path,
                        alert_id=parts[2],
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        target_case_id=body.get("target_case_id"),
                        rationale=str(body.get("rationale") or ""),
                    )
                    self._send_json(res, HTTPStatus.CREATED)
                    return
                if path == "/api/cases/bulk":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = bulk_triage_cases(
                        service.db_path,
                        case_ids=list(body.get("case_ids") or []),
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        actor_role=user["role"] if user else body.get("actor_role", "RISK_REVIEWER"),
                        action=str(body.get("action") or ""),
                        assigned_analyst_id=body.get("assigned_analyst_id"),
                        rationale=str(body.get("rationale") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "triage":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    if (body.get("override_tier") is not None or body.get("override_score") is not None) and user and user["role"] not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
                        self._send_json(
                            {"error": f"Role '{user['role']}' cannot override case priority."},
                            HTTPStatus.FORBIDDEN,
                        )
                        return
                    res = assign_or_override_case(
                        service.db_path,
                        case_id=parts[2],
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-003"),
                        actor_role=user["role"] if user else body.get("actor_role", "RISK_REVIEWER"),
                        assigned_analyst_id=body.get("assigned_analyst_id"),
                        override_tier=body.get("override_tier"),
                        override_score=body.get("override_score"),
                        override_reason=str(body.get("override_reason") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "alerts":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = link_or_unlink_case_alert(
                        service.db_path,
                        case_id=parts[2],
                        alert_id=str(body.get("alert_id") or ""),
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        mode=str(body.get("mode") or "link"),
                        linkage_reason=str(body.get("linkage_reason") or "MANUAL_ANALYST_LINK"),
                        rationale=str(body.get("rationale") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "checklist":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = update_case_checklist(
                        service.db_path,
                        case_id=parts[2],
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        rules_reviewed=body.get("rules_reviewed"),
                        ledger_reconciled=body.get("ledger_reconciled"),
                        network_verified=body.get("network_verified"),
                        kyc_corroborated=body.get("kyc_corroborated"),
                        notes=body.get("notes"),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "sar-draft":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    dos = service.get_case_dossier(parts[2])
                    if dos is None:
                        self._send_json({"error": f"Case '{parts[2]}' not found"}, HTTPStatus.NOT_FOUND)
                        return
                    body = self._read_json_body()
                    res = generate_or_save_sar_draft(
                        dos,
                        service.db_path,
                        case_id=parts[2],
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-003"),
                        custom_narrative=body.get("sar_draft"),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/watchlist-tags":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = manage_watchlist_tag(
                        service.db_path,
                        entity_type=str(body.get("entity_type") or ""),
                        entity_id=str(body.get("entity_id") or ""),
                        tag=str(body.get("tag") or ""),
                        note=str(body.get("note") or ""),
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        remove=bool(body.get("remove", False)),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/risk/evaluate":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.evaluate_risk(
                        transaction_id=body.get("transaction_id"),
                        payload=body.get("payload"),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/risk/re-evaluate":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.apply_rule_update_and_reevaluate(
                        rule_id=body.get("rule_id") or "ALL",
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "risk" and parts[2] == "rules":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and "configure_risk_rules" not in user["permissions"] and user["role"] != "SYSTEM_ADMIN":
                        self._send_json(
                            {"error": f"Role '{user['role']}' lacks permission 'configure_risk_rules'."},
                            HTTPStatus.FORBIDDEN,
                        )
                        return
                    body = self._read_json_body()
                    res = service.apply_rule_update_and_reevaluate(
                        rule_id=parts[3],
                        base_weight=body.get("base_weight"),
                        is_active=body.get("is_active"),
                        threshold_desc=body.get("threshold_desc"),
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ADM-001"),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/quarantine/validate":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    self._send_json(service.run_live_integrity_validation(), HTTPStatus.OK)
                    return
                if path == "/api/quarantine/bulk-review":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.bulk_review_quarantine(
                        exception_ids=list(body.get("exception_ids") or []),
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        review_status=str(body.get("review_status") or ""),
                        note=str(body.get("note") or ""),
                        action_taken=str(body.get("action_taken") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "quarantine" and parts[3] == "review":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.review_quarantine_exception(
                        exception_id=parts[2],
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-001"),
                        review_status=str(body.get("review_status") or ""),
                        note=str(body.get("note") or ""),
                        action_taken=str(body.get("action_taken") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 5 and parts[0] == "api" and parts[1] == "admin" and parts[2] == "users" and parts[4] == "role":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and user["role"] != "SYSTEM_ADMIN" and "manage_users" not in user["permissions"]:
                        self._send_json(
                            {"error": f"Role '{user['role']}' lacks permission 'manage_users'."},
                            HTTPStatus.FORBIDDEN,
                        )
                        return
                    body = self._read_json_body()
                    updated = service.update_admin_user(
                        actor_user_id=user["user_id"] if user else "USR-003",
                        target_user_id=parts[3],
                        role=body.get("role"),
                        is_active=body.get("is_active"),
                    )
                    self._send_json({"user": updated}, HTTPStatus.OK)
                    return
                if path == "/api/admin/sla-policies":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and user["role"] != "SYSTEM_ADMIN":
                        self._send_json(
                            {"error": f"Role '{user['role']}' lacks SYSTEM_ADMIN authority for SLA policies."},
                            HTTPStatus.FORBIDDEN,
                        )
                        return
                    body = self._read_json_body()
                    res = service.update_sla_policies(
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ADM-001"),
                        updates=list(body.get("updates") or []),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/saved-views":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.create_saved_view(
                        user_id=user["user_id"] if user else "USR-001",
                        workspace=str(body.get("workspace") or ""),
                        name=str(body.get("name") or ""),
                        filters=dict(body.get("filters") or {}),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/evaluation/verify-manifest":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    self._send_json(service.verify_export_manifest_integrity(), HTTPStatus.OK)
                    return
                if path == "/api/evaluation/what-if":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.run_what_if_simulation(
                        weight_overrides=dict(body.get("weight_overrides") or {}),
                        k_pct=float(body.get("k_pct") or 20.0),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "sar" and parts[3] == "status":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.transition_sar_status(
                        case_id=parts[2],
                        sar_status=str(body.get("sar_status") or ""),
                        actor_id=user["analyst_code"] if user else body.get("actor_id", "ANL-003"),
                        actor_role=user["role"] if user else body.get("actor_role", "RISK_REVIEWER"),
                        note=str(body.get("note") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/analytics/high-risk-countries":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and user["role"] not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
                        self._send_json({"error": "Requires RISK_REVIEWER or SYSTEM_ADMIN role"}, HTTPStatus.FORBIDDEN)
                        return
                    body = self._read_json_body()
                    res = service.upsert_high_risk_country(
                        country_code=str(body.get("country_code") or ""),
                        country_name=str(body.get("country_name") or ""),
                        risk_tier=str(body.get("risk_tier") or "WATCH"),
                        multiplier=float(body.get("multiplier") or 1.25),
                        note=str(body.get("note") or ""),
                        actor_id=user["analyst_code"] if user else "ADM-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/analytics/capacity-forecast":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.forecast_alert_capacity(
                        growth_factor=float(body.get("growth_factor") or 1.5),
                        hours_per_case=float(body.get("hours_per_case") or 1.5),
                        analysts_available=int(body.get("analysts_available") or 4),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "customers" and parts[3] == "kyc-review":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.submit_kyc_review(
                        customer_id=parts[2],
                        outcome=str(body.get("outcome") or "VERIFIED"),
                        risk_justification=str(body.get("risk_justification") or ""),
                        reviewer_id=user["analyst_code"] if user else "ANL-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "accounts" and parts[3] == "control":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.set_account_control(
                        account_id=parts[2],
                        control_status=str(body.get("control_status") or "NONE"),
                        reason=str(body.get("reason") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                        actor_role=user["role"] if user else "OPS_ANALYST",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/cases/rebalance":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.rebalance_queue_workload(
                        actor_id=user["analyst_code"] if user else "ANL-003",
                        actor_role=user["role"] if user else "RISK_REVIEWER",
                        limit=int(body.get("limit") or 30),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/cases/merge":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.merge_cases(
                        primary_case_id=str(body.get("primary_case_id") or ""),
                        secondary_case_id=str(body.get("secondary_case_id") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                        actor_role=user["role"] if user else "OPS_ANALYST",
                        rationale=str(body.get("rationale") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "pins":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.add_case_pin(
                        case_id=parts[2],
                        entity_type=str(body.get("entity_type") or "TRANSACTION"),
                        entity_id=str(body.get("entity_id") or ""),
                        pin_type=str(body.get("pin_type") or "PINNED_PROOF"),
                        note=str(body.get("note") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "comments":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.add_case_comment(
                        case_id=parts[2],
                        actor_id=user["analyst_code"] if user else "ANL-001",
                        actor_role=user["role"] if user else "OPS_ANALYST",
                        body=str(body.get("body") or ""),
                        visibility=str(body.get("visibility") or "INTERNAL"),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "apply-playbook":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.apply_playbook_to_case(
                        case_id=parts[2],
                        playbook_id=str(body.get("playbook_id") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                        actor_role=user["role"] if user else "OPS_ANALYST",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "rfi-packet":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    res = service.generate_rfi_packet(parts[2])
                    if res is None:
                        self._send_json({"error": f"Case '{parts[2]}' not found"}, HTTPStatus.NOT_FOUND)
                    else:
                        self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/alerts/suppressions":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.create_suppression_rule(
                        account_id=str(body.get("account_id") or ""),
                        rule_id=str(body.get("rule_id") or ""),
                        max_amount=float(body.get("max_amount") or 0),
                        reason=str(body.get("reason") or ""),
                        days_valid=int(body.get("days_valid") or 90),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/risk/calibration-proposal":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.create_calibration_proposal(
                        title=str(body.get("title") or "Calibration Proposal"),
                        weights=dict(body.get("weights") or {}),
                        simulation_summary=dict(body.get("simulation_summary") or {}),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 5 and parts[0] == "api" and parts[1] == "risk" and parts[2] == "calibration-proposal" and parts[4] == "approve":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.approve_calibration_proposal(
                        proposal_id=parts[3],
                        decision=str(body.get("decision") or "APPROVED"),
                        actor_id=user["analyst_code"] if user else "ADM-001",
                        actor_role=user["role"] if user else "SYSTEM_ADMIN",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/risk/sandbox-pattern":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.run_sandbox_pattern(
                        min_amount=float(body["min_amount"]) if body.get("min_amount") not in (None, "") else None,
                        max_amount=float(body["max_amount"]) if body.get("max_amount") not in (None, "") else None,
                        channel=str(body.get("channel") or "ALL"),
                        txn_type=str(body.get("txn_type") or "ALL"),
                        country=str(body.get("country") or "ALL"),
                        limit=int(body.get("limit") or 30),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/notifications/read":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    updated = service.mark_notifications_read(user["user_id"] if user else "USR-001", body.get("notif_id"))
                    self._send_json({"updated": updated}, HTTPStatus.OK)
                    return
                if path == "/api/integrations/siem":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.enqueue_or_dispatch_siem(
                        event_type=str(body.get("event_type") or "COMPLIANCE_ALERT"),
                        severity=str(body.get("severity") or "HIGH"),
                        entity_id=str(body.get("entity_id") or "WORKBENCH"),
                        payload=dict(body.get("payload") or {}),
                        dispatch_now=bool(body.get("dispatch_now", True)),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/system/jobs":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.run_pipeline_job(
                        job_type=str(body.get("job_type") or "VALIDATION_SCAN"),
                        actor_id=user["analyst_code"] if user else "ADM-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/assistant/chat":
                    user = get_session_user(service.db_path, self._bearer_token())
                    body = self._read_json_body()
                    res = answer_user_query(
                        service,
                        str(body.get("query") or ""),
                        authenticated_user=user,
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/screening/sanctions":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.run_sanctions_screening(
                        entity_type=str(body.get("entity_type") or "CUSTOMER"),
                        entity_id=str(body.get("entity_id") or "AD-HOC"),
                        query_name=str(body.get("query_name") or ""),
                        country_code=str(body.get("country_code") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "goaml-xml":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    self._send_json(service.generate_goaml_xml(parts[2]), HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "handoff":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.add_case_handoff(
                        case_id=parts[2],
                        from_analyst=user["analyst_code"] if user else "ANL-001",
                        to_analyst=str(body.get("to_analyst") or "ANL-002"),
                        summary=str(body.get("summary") or ""),
                        pending_actions=str(body.get("pending_actions") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "evidence-seal":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    self._send_json(service.create_case_evidence_seal(parts[2], user["analyst_code"] if user else "ANL-001"), HTTPStatus.OK)
                    return
                if path == "/api/cases/bulk-tag":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.bulk_tag_cases(
                        case_ids=list(body.get("case_ids") or []),
                        tag=str(body.get("tag") or "WATCHLIST"),
                        note=str(body.get("note") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "reopen":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and user["role"] not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
                        self._send_json({"error": "Only RISK_REVIEWER or SYSTEM_ADMIN can reopen closed cases"}, HTTPStatus.FORBIDDEN)
                        return
                    body = self._read_json_body()
                    res = service.reopen_closed_case(
                        case_id=parts[2],
                        rationale=str(body.get("rationale") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-003",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 4 and parts[0] == "api" and parts[1] == "cases" and parts[3] == "what-if-score":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.simulate_case_what_if_score(parts[2], list(body.get("waived_alert_ids") or []))
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/transactions/batch-simulate":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.batch_simulate_transactions(
                        min_amount=float(body.get("min_amount") or 1000.0),
                        multiplier=float(body.get("multiplier") or 1.15),
                        limit=int(body.get("limit") or 50),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/risk/custom-rules":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.create_custom_rule_draft(
                        name=str(body.get("name") or ""),
                        min_amount=float(body.get("min_amount") or 2000.0),
                        channel=str(body.get("channel") or "ALL"),
                        country_code=str(body.get("country_code") or "ALL"),
                        description=str(body.get("description") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 5 and parts[0] == "api" and parts[1] == "governance" and parts[2] == "qa-samples" and parts[4] == "grade":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and user["role"] not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
                        self._send_json({"error": "Only RISK_REVIEWER or SYSTEM_ADMIN can grade QA samples"}, HTTPStatus.FORBIDDEN)
                        return
                    body = self._read_json_body()
                    res = service.submit_qa_grade(
                        case_id=parts[3],
                        grade=str(body.get("grade") or "PASS"),
                        score=int(body.get("score") or 90),
                        feedback=str(body.get("feedback") or ""),
                        reviewer_id=user["analyst_code"] if user else "ANL-003",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/cases/sla-auto-escalate":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and user["role"] not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
                        self._send_json({"error": "Only RISK_REVIEWER or SYSTEM_ADMIN can trigger SLA auto-escalation"}, HTTPStatus.FORBIDDEN)
                        return
                    body = self._read_json_body()
                    res = service.run_sla_auto_escalation(
                        actor_id=user["analyst_code"] if user else "ANL-003",
                        max_escalations=int(body.get("max_escalations") or 10),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/integrations/webhooks":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.create_webhook(
                        name=str(body.get("name") or ""),
                        target_url=str(body.get("target_url") or ""),
                        actor_id=user["analyst_code"] if user else "ADM-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if len(parts) == 5 and parts[0] == "api" and parts[1] == "integrations" and parts[2] == "webhooks" and parts[4] == "test":
                    if require_auth and not get_session_user(service.db_path, self._bearer_token()):
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    self._send_json(service.test_webhook_ping(parts[3]), HTTPStatus.OK)
                    return
                if path == "/api/search/bookmarks":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.create_search_bookmark(
                        user_id=user["user_id"] if user else "USR-001",
                        title=str(body.get("title") or ""),
                        workspace=str(body.get("workspace") or "spotlight"),
                        query_text=str(body.get("query_text") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/reports/schedules":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.upsert_scheduled_digest(
                        cadence=str(body.get("cadence") or "WEEKLY"),
                        recipient_role=str(body.get("recipient_role") or "RISK_REVIEWER"),
                        include_quarantine=bool(body.get("include_quarantine", True)),
                        actor_id=user["analyst_code"] if user else "ADM-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/system/retention":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and user["role"] != "SYSTEM_ADMIN":
                        self._send_json({"error": "Only SYSTEM_ADMIN can modify retention policy"}, HTTPStatus.FORBIDDEN)
                        return
                    body = self._read_json_body()
                    res = service.update_retention_policy(
                        alerts_days=int(body.get("alerts_days") or 180),
                        sessions_days=int(body.get("sessions_days") or 90),
                        exports_days=int(body.get("exports_days") or 365),
                        actor_id=user["analyst_code"] if user else "ADM-001",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/governance/exam-readiness":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if user and user["role"] not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
                        self._send_json({"error": "Requires RISK_REVIEWER or SYSTEM_ADMIN"}, HTTPStatus.FORBIDDEN)
                        return
                    body = self._read_json_body()
                    res = service.update_exam_readiness(
                        control_id=str(body.get("control_id") or ""),
                        status=str(body.get("status") or "VERIFIED"),
                        note=str(body.get("note") or ""),
                        actor_id=user["analyst_code"] if user else "ANL-003",
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                if path == "/api/workspace/pinned-entities":
                    user = get_session_user(service.db_path, self._bearer_token())
                    if require_auth and not user:
                        self._send_json({"error": "Not authenticated"}, HTTPStatus.UNAUTHORIZED)
                        return
                    body = self._read_json_body()
                    res = service.add_workspace_pin(
                        user_id=user["user_id"] if user else "USR-001",
                        entity_type=str(body.get("entity_type") or "CASE"),
                        entity_id=str(body.get("entity_id") or ""),
                        label=str(body.get("label") or ""),
                    )
                    self._send_json(res, HTTPStatus.OK)
                    return
                self._send_json({"error": "Endpoint not found"}, HTTPStatus.NOT_FOUND)
            except PermissionError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except AuthError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.UNAUTHORIZED if "Invalid" in str(exc) else HTTPStatus.BAD_REQUEST)
            except WorkflowError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            except Exception as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    return WorkbenchHandler


def run_server(export_dir: Path, web_dir: Path, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start the Analyst Workbench HTTP server."""
    service = WorkbenchService(export_dir)
    handler_cls = make_handler(service, web_dir, require_auth=True)
    server = ThreadingHTTPServer((host, port), handler_cls)
    print(f"[yottaflex] Analyst Workbench running at http://{host}:{port} (dataset={export_dir})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[yottaflex] Server stopped.")
    finally:
        server.server_close()

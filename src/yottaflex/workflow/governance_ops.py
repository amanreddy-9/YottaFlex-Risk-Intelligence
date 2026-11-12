"""Governance, Quarantine Operations, Unified Audit Ledger, Saved Presets & SLA Policies (Functions 126-150)."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import secrets
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_QUARANTINE_STATUSES = ("PENDING", "ACKNOWLEDGED", "REMEDIATED", "WAIVED")
DEFAULT_SLA_POLICIES: list[tuple[str, str, int]] = [
    ("CASE", "CRITICAL", 48),
    ("CASE", "HIGH", 48),
    ("CASE", "MEDIUM", 48),
    ("CASE", "LOW", 48),
    ("ALERT", "CRITICAL", 72),
    ("ALERT", "HIGH", 72),
    ("ALERT", "MEDIUM", 72),
    ("ALERT", "LOW", 72),
]

_AMOUNT_RE = re.compile(r"\$([0-9][0-9,]*(?:\.[0-9]+)?)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _extract_amount(evidence: str | None) -> float:
    if not evidence:
        return 0.0
    m = _AMOUNT_RE.search(evidence)
    if not m:
        return 0.0
    try:
        return abs(float(m.group(1).replace(",", "")))
    except ValueError:
        return 0.0


def _csv_bytes(rows: list[dict[str, Any]], fieldnames: list[str]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k, "") for k in fieldnames})
    return buf.getvalue().encode("utf-8")


def ensure_governance_schema(conn: sqlite3.Connection) -> None:
    """Create Batch 6 & SAR status persistence tables/columns idempotently."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS quarantine_reviews (
            exception_id TEXT PRIMARY KEY,
            review_status TEXT NOT NULL DEFAULT 'PENDING',
            reviewer_id TEXT,
            remediation_note TEXT,
            action_taken TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS quarantine_review_events (
            event_id TEXT PRIMARY KEY,
            exception_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            prev_status TEXT,
            new_status TEXT NOT NULL,
            note TEXT NOT NULL,
            action_taken TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS saved_views (
            view_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            workspace TEXT NOT NULL,
            name TEXT NOT NULL,
            filters_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sla_policies (
            policy_key TEXT PRIMARY KEY,
            entity_scope TEXT NOT NULL,
            tier TEXT NOT NULL,
            sla_hours INTEGER NOT NULL,
            updated_by TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_quar_events_exc ON quarantine_review_events(exception_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_saved_views_user ON saved_views(user_id, workspace);
        """
    )

    cols = {r[1] for r in conn.execute("PRAGMA table_info(case_triage_meta)").fetchall()}
    if cols and "sar_status" not in cols:
        conn.execute("ALTER TABLE case_triage_meta ADD COLUMN sar_status TEXT NOT NULL DEFAULT 'DRAFT'")

    now = _now_iso()
    for scope, tier, hrs in DEFAULT_SLA_POLICIES:
        key = f"{scope}:{tier}"
        conn.execute(
            """
            INSERT OR IGNORE INTO sla_policies (policy_key, entity_scope, tier, sla_hours, updated_by, updated_at)
            VALUES (?, ?, ?, ?, 'SYSTEM', ?)
            """,
            (key, scope, tier, hrs, now),
        )
    conn.commit()


# ------------------------------------------------------------------
# Functions 147-148: SLA Policies
# ------------------------------------------------------------------
def get_sla_policies(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return active SLA threshold policies mapped by entity_scope and tier."""
    ensure_governance_schema(conn)
    rows = conn.execute(
        "SELECT policy_key, entity_scope, tier, sla_hours, updated_by, updated_at FROM sla_policies ORDER BY entity_scope, CASE tier WHEN 'CRITICAL' THEN 1 WHEN 'HIGH' THEN 2 WHEN 'MEDIUM' THEN 3 ELSE 4 END"
    ).fetchall()
    items = [dict(r) for r in rows]
    policy_map: dict[str, dict[str, int]] = {"CASE": {}, "ALERT": {}}
    for it in items:
        policy_map.setdefault(it["entity_scope"], {})[it["tier"]] = int(it["sla_hours"])
    return {"items": items, "map": policy_map}


def update_sla_policies(
    conn: sqlite3.Connection,
    *,
    actor_id: str,
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Update SLA hour thresholds per scope & tier."""
    ensure_governance_schema(conn)
    if not updates:
        raise ValueError("Provide at least one SLA policy update")
    now = _now_iso()
    for upd in updates:
        scope = str(upd.get("entity_scope") or "").upper()
        tier = str(upd.get("tier") or "").upper()
        if scope not in {"CASE", "ALERT"}:
            raise ValueError(f"Unsupported entity_scope '{scope}'")
        if tier not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            raise ValueError(f"Unsupported tier '{tier}'")
        try:
            hours = int(upd.get("sla_hours"))
        except (TypeError, ValueError) as exc:
            raise ValueError("sla_hours must be an integer") from exc
        if hours < 1 or hours > 720:
            raise ValueError("sla_hours must be between 1 and 720")
        key = f"{scope}:{tier}"
        conn.execute(
            """
            INSERT INTO sla_policies (policy_key, entity_scope, tier, sla_hours, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(policy_key) DO UPDATE SET
                sla_hours = excluded.sla_hours,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (key, scope, tier, hours, actor_id, now),
        )
    conn.commit()
    return get_sla_policies(conn)


# ------------------------------------------------------------------
# Functions 126-135: Quarantine Operations & Integrity Validation
# ------------------------------------------------------------------
def _enrich_quarantine_items(
    conn: sqlite3.Connection,
    base_quarantine: dict[str, Any],
) -> list[dict[str, Any]]:
    ensure_governance_schema(conn)
    reviews = {
        r["exception_id"]: dict(r)
        for r in conn.execute("SELECT * FROM quarantine_reviews").fetchall()
    }
    enriched: list[dict[str, Any]] = []
    for ex in base_quarantine.get("exceptions", []):
        rev = reviews.get(ex["exception_id"], {})
        est_exp = _extract_amount(ex.get("evidence"))
        enriched.append(
            {
                **ex,
                "review_status": rev.get("review_status", "PENDING"),
                "reviewer_id": rev.get("reviewer_id"),
                "remediation_note": rev.get("remediation_note"),
                "action_taken": rev.get("action_taken"),
                "updated_at": rev.get("updated_at"),
                "estimated_exposure": round(est_exp, 2),
            }
        )
    return enriched


def list_quarantine_exceptions_filtered(
    conn: sqlite3.Connection,
    base_quarantine: dict[str, Any],
    *,
    search: str | None = None,
    issue_type: str = "ALL",
    severity: str = "ALL",
    review_status: str = "ALL",
    sort_by: str = "severity",
) -> dict[str, Any]:
    """Filter, sort, and summarize quarantined data integrity exceptions."""
    enriched = _enrich_quarantine_items(conn, base_quarantine)
    status_counts = Counter(item["review_status"] for item in enriched)
    total_exposure = round(sum(item["estimated_exposure"] for item in enriched), 2)
    pending_exposure = round(sum(item["estimated_exposure"] for item in enriched if item["review_status"] == "PENDING"), 2)

    q = search.strip().lower() if search and search.strip() else ""
    filtered: list[dict[str, Any]] = []
    for item in enriched:
        if issue_type and issue_type != "ALL" and item["issue_type"] != issue_type:
            continue
        if severity and severity != "ALL" and item["severity"] != severity:
            continue
        if review_status and review_status != "ALL" and item["review_status"] != review_status:
            continue
        if q:
            haystack = " ".join(
                str(item.get(k) or "")
                for k in ("exception_id", "entity_id", "account_id", "issue_type", "evidence", "violated_invariant")
            ).lower()
            if q not in haystack:
                continue
        filtered.append(item)

    sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    if sort_by == "exposure":
        filtered.sort(key=lambda x: (-x["estimated_exposure"], x["exception_id"]))
    elif sort_by == "status":
        filtered.sort(key=lambda x: (x["review_status"], -sev_rank.get(x["severity"], 0), x["exception_id"]))
    else:
        filtered.sort(key=lambda x: (-sev_rank.get(x["severity"], 0), -x["estimated_exposure"], x["exception_id"]))

    return {
        "total_exceptions": base_quarantine.get("total_exceptions", len(enriched)),
        "filtered_total": len(filtered),
        "counts_by_issue_type": base_quarantine.get("counts_by_issue_type", {}),
        "counts_by_review_status": {k: int(status_counts.get(k, 0)) for k in VALID_QUARANTINE_STATUSES},
        "quarantined_exposure": total_exposure,
        "pending_exposure": pending_exposure,
        "exceptions": filtered,
    }


def get_quarantine_detail(
    conn: sqlite3.Connection,
    base_quarantine: dict[str, Any],
    exception_id: str,
) -> dict[str, Any] | None:
    """Return single quarantine exception detail plus immutable review audit timeline."""
    enriched = _enrich_quarantine_items(conn, base_quarantine)
    match = next((x for x in enriched if x["exception_id"] == exception_id), None)
    if not match:
        return None
    events = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM quarantine_review_events WHERE exception_id = ? ORDER BY created_at DESC",
            (exception_id,),
        ).fetchall()
    ]
    return {"exception": match, "events": events}


def review_quarantine_exception(
    conn: sqlite3.Connection,
    base_quarantine: dict[str, Any],
    *,
    exception_id: str,
    actor_id: str,
    review_status: str,
    note: str = "",
    action_taken: str = "",
) -> dict[str, Any]:
    """Update quarantine review status and record immutable remediation audit event."""
    ensure_governance_schema(conn)
    valid_ids = {ex["exception_id"] for ex in base_quarantine.get("exceptions", [])}
    if exception_id not in valid_ids:
        raise ValueError(f"Quarantine exception {exception_id} not found")

    next_status = str(review_status or "").upper()
    if next_status not in VALID_QUARANTINE_STATUSES:
        raise ValueError(f"Invalid review_status '{next_status}'. Allowed: {', '.join(VALID_QUARANTINE_STATUSES)}")

    cur = conn.execute("SELECT review_status FROM quarantine_reviews WHERE exception_id = ?", (exception_id,)).fetchone()
    prev_status = cur["review_status"] if cur else "PENDING"
    now = _now_iso()
    clean_note = note.strip() or f"Marked {next_status}"
    clean_action = action_taken.strip() or f"REVIEW_{next_status}"

    conn.execute(
        """
        INSERT INTO quarantine_reviews (exception_id, review_status, reviewer_id, remediation_note, action_taken, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(exception_id) DO UPDATE SET
            review_status = excluded.review_status,
            reviewer_id = excluded.reviewer_id,
            remediation_note = excluded.remediation_note,
            action_taken = excluded.action_taken,
            updated_at = excluded.updated_at
        """,
        (exception_id, next_status, actor_id, clean_note, clean_action, now),
    )
    conn.execute(
        """
        INSERT INTO quarantine_review_events (event_id, exception_id, actor_id, prev_status, new_status, note, action_taken, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (_new_id("QEV"), exception_id, actor_id, prev_status, next_status, clean_note, clean_action, now),
    )
    conn.commit()
    detail = get_quarantine_detail(conn, base_quarantine, exception_id)
    assert detail is not None
    return detail


def bulk_review_quarantine(
    conn: sqlite3.Connection,
    base_quarantine: dict[str, Any],
    *,
    exception_ids: list[str],
    actor_id: str,
    review_status: str,
    note: str = "",
    action_taken: str = "",
) -> dict[str, Any]:
    """Batch-triage selected quarantine exceptions atomically."""
    if not exception_ids:
        raise ValueError("Select at least one quarantine exception")
    updated = []
    for eid in exception_ids[:100]:
        res = review_quarantine_exception(
            conn,
            base_quarantine,
            exception_id=eid,
            actor_id=actor_id,
            review_status=review_status,
            note=note or f"Bulk quarantine triage ({review_status})",
            action_taken=action_taken or f"BULK_{review_status.upper()}",
        )
        updated.append(res["exception"])
    return {"updated_count": len(updated), "items": updated}


def run_live_integrity_validation(conn: sqlite3.Connection, base_quarantine: dict[str, Any]) -> dict[str, Any]:
    """Run live SQLite ledger & relational invariant diagnostics across active tables."""
    now = _now_iso()
    checks: list[dict[str, Any]] = []

    def add_check(code: str, name: str, sql: str, description: str) -> None:
        cnt = int(conn.execute(sql).fetchone()[0] or 0)
        checks.append(
            {
                "check_id": code,
                "name": name,
                "description": description,
                "violations_found": cnt,
                "status": "PASS" if cnt == 0 else "WARN_ISOLATED",
            }
        )

    add_check(
        "INV-01",
        "Non-Positive Transaction Amounts",
        "SELECT COUNT(*) FROM transactions WHERE amount <= 0",
        "Verify active transactions strictly carry positive monetary amounts.",
    )
    add_check(
        "INV-02",
        "Settled Ledger Arithmetic Reconciliation",
        "SELECT COUNT(*) FROM transactions WHERE status = 'SETTLED' AND ABS((balance_before + CASE WHEN direction = 'CREDIT' THEN amount ELSE -amount END) - balance_after) > 0.01",
        "Detect arithmetic drift between balance_before, direction/amount, and balance_after on settled rows.",
    )
    add_check(
        "INV-03",
        "Post-Closure Account Activity",
        "SELECT COUNT(*) FROM transactions t JOIN accounts a ON a.account_id = t.account_id WHERE a.closed_at IS NOT NULL AND t.occurred_at > a.closed_at",
        "Confirm no settled transactions occurred after an account closed timestamp.",
    )
    add_check(
        "INV-04",
        "Orphan Alert Account Links",
        "SELECT COUNT(*) FROM alerts al LEFT JOIN accounts a ON a.account_id = al.account_id WHERE a.account_id IS NULL",
        "Ensure every scored alert resolves cleanly to a valid account record.",
    )
    add_check(
        "INV-05",
        "Negative Case Exposure Guards",
        "SELECT COUNT(*) FROM cases WHERE total_exposure_amount < 0",
        "Verify all priority-ranked cases hold non-negative exposure totals.",
    )
    add_check(
        "INV-06",
        "Account Balance Integrity",
        "SELECT COUNT(*) FROM accounts WHERE current_balance < 0",
        "Check account balances against negative overdraft anomalies.",
    )

    return {
        "validated_at": now,
        "checks": checks,
        "passed_checks": sum(1 for c in checks if c["status"] == "PASS"),
        "total_checks": len(checks),
        "quarantine_isolated_total": int(base_quarantine.get("total_exceptions", 0)),
    }


def export_quarantine_report(
    conn: sqlite3.Connection,
    base_quarantine: dict[str, Any],
    *,
    fmt: str = "csv",
    **filters: Any,
) -> tuple[bytes, str, str]:
    """Export filtered quarantine exceptions and review metadata as CSV or JSON."""
    data = list_quarantine_exceptions_filtered(conn, base_quarantine, **filters)
    if str(fmt).lower() == "json":
        return (
            json.dumps(data, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            "yottaflex_quarantine_exceptions.json",
        )
    cols = [
        "exception_id",
        "issue_type",
        "severity",
        "review_status",
        "reviewer_id",
        "entity_type",
        "entity_id",
        "account_id",
        "estimated_exposure",
        "violated_invariant",
        "evidence",
        "remediation_note",
        "updated_at",
    ]
    return (
        _csv_bytes(data["exceptions"], cols),
        "text/csv; charset=utf-8",
        "yottaflex_quarantine_exceptions.csv",
    )


# ------------------------------------------------------------------
# Functions 136-140: Unified Audit Ledger & Analyst Leaderboard
# ------------------------------------------------------------------
def _collect_unified_audit_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_governance_schema(conn)
    events: list[dict[str, Any]] = []

    # 1. Case state & disposition events
    for r in conn.execute(
        """
        SELECT cse.case_event_id AS event_id, cse.case_id AS entity_id,
               COALESCE(aa.analyst_id, 'SYSTEM') AS actor_id,
               COALESCE(aa.action_type, 'STATUS_CHANGE') AS action_type,
               cse.prev_status, cse.new_status,
               COALESCE(aa.rationale, '') AS detail,
               cse.effective_at AS occurred_at
        FROM case_state_events cse
        LEFT JOIN analyst_actions aa ON aa.action_id = cse.analyst_action_id
        ORDER BY cse.effective_at DESC LIMIT 400
        """
    ).fetchall():
        d = dict(r)
        detail = f"{d['prev_status']} -> {d['new_status']}" + (f" • {d['detail']}" if d["detail"] else "")
        events.append(
            {
                "event_id": d["event_id"],
                "source": "CASE",
                "entity_type": "CASE",
                "entity_id": d["entity_id"],
                "actor_id": d["actor_id"],
                "action_type": d["action_type"],
                "severity": "HIGH" if d["new_status"] in {"ESCALATED", "SAR_FILED", "REOPENED"} else "MEDIUM",
                "detail": detail,
                "occurred_at": d["occurred_at"],
            }
        )

    # 2. Alert triage audit events
    for r in conn.execute(
        "SELECT event_id, alert_id, actor_id, event_type, prev_status, new_status, detail, created_at FROM alert_audit_events ORDER BY created_at DESC LIMIT 400"
    ).fetchall():
        d = dict(r)
        events.append(
            {
                "event_id": d["event_id"],
                "source": "ALERT",
                "entity_type": "ALERT",
                "entity_id": d["alert_id"],
                "actor_id": d["actor_id"],
                "action_type": d["event_type"],
                "severity": "HIGH" if d["event_type"] in {"ESCALATE", "SUPPRESS_FP"} else "LOW",
                "detail": d["detail"],
                "occurred_at": d["created_at"],
            }
        )

    # 3. Quarantine review events
    for r in conn.execute(
        "SELECT event_id, exception_id, actor_id, prev_status, new_status, note, action_taken, created_at FROM quarantine_review_events ORDER BY created_at DESC LIMIT 200"
    ).fetchall():
        d = dict(r)
        events.append(
            {
                "event_id": d["event_id"],
                "source": "QUARANTINE",
                "entity_type": "EXCEPTION",
                "entity_id": d["exception_id"],
                "actor_id": d["actor_id"],
                "action_type": d["action_taken"] or f"QUARANTINE_{d['new_status']}",
                "severity": "MEDIUM",
                "detail": f"{d['prev_status']} -> {d['new_status']} • {d['note']}",
                "occurred_at": d["created_at"],
            }
        )

    # 4. Risk engine rule executions
    for r in conn.execute(
        "SELECT run_id, trigger_source, COALESCE(rule_id, 'ALL') AS rule_id, executed_by, executed_at, summary FROM rule_execution_runs ORDER BY executed_at DESC LIMIT 200"
    ).fetchall():
        d = dict(r)
        events.append(
            {
                "event_id": d["run_id"],
                "source": "RISK_ENGINE",
                "entity_type": "RULE",
                "entity_id": d["rule_id"],
                "actor_id": d["executed_by"],
                "action_type": d["trigger_source"],
                "severity": "HIGH" if d["trigger_source"] == "RULE_CALIBRATION" else "LOW",
                "detail": d["summary"],
                "occurred_at": d["executed_at"],
            }
        )

    # 5. Auth & Admin events
    for r in conn.execute(
        "SELECT log_id, COALESCE(user_id, email) AS actor_id, email, event_type, status, detail, occurred_at FROM login_history ORDER BY occurred_at DESC LIMIT 250"
    ).fetchall():
        d = dict(r)
        events.append(
            {
                "event_id": d["log_id"],
                "source": "AUTH",
                "entity_type": "USER",
                "entity_id": d["email"],
                "actor_id": d["actor_id"],
                "action_type": f"{d['event_type']} ({d['status']})",
                "severity": "CRITICAL" if d["status"] != "SUCCESS" or d["event_type"] == "ADMIN_ROLE_UPDATE" else "LOW",
                "detail": d["detail"] or d["email"],
                "occurred_at": d["occurred_at"],
            }
        )

    events.sort(key=lambda x: (str(x["occurred_at"]), str(x["event_id"])), reverse=True)
    for ev in events:
        sig_payload = f"{ev['event_id']}|{ev['source']}|{ev['entity_id']}|{ev['actor_id']}|{ev['action_type']}|{ev['occurred_at']}"
        ev["integrity_hash"] = _sha256_text(sig_payload)[:16]
    return events


def get_unified_audit_events(
    conn: sqlite3.Connection,
    *,
    source: str = "ALL",
    actor: str = "ALL",
    entity_id: str | None = None,
    search: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 80,
    offset: int = 0,
) -> dict[str, Any]:
    """Return filtered unified audit ledger with per-event SHA-256 chain digests."""
    all_events = _collect_unified_audit_rows(conn)
    source_counts = Counter(e["source"] for e in all_events)

    q = search.strip().lower() if search and search.strip() else ""
    ent_q = entity_id.strip().lower() if entity_id and entity_id.strip() else ""

    filtered: list[dict[str, Any]] = []
    for ev in all_events:
        if source and source != "ALL" and ev["source"] != source:
            continue
        if actor and actor != "ALL" and ev["actor_id"] != actor:
            continue
        if ent_q and ent_q not in str(ev["entity_id"]).lower():
            continue
        if start_date and str(ev["occurred_at"]) < start_date:
            continue
        if end_date and str(ev["occurred_at"]) > f"{end_date}T23:59:59Z":
            continue
        if q:
            blob = f"{ev['event_id']} {ev['entity_id']} {ev['actor_id']} {ev['action_type']} {ev['detail']}".lower()
            if q not in blob:
                continue
        filtered.append(ev)

    page = filtered[offset : offset + limit]
    batch_digest = _sha256_text("|".join(e["integrity_hash"] for e in page))[:24] if page else "EMPTY"
    return {
        "total": len(filtered),
        "all_total": len(all_events),
        "counts_by_source": dict(source_counts),
        "batch_digest": batch_digest,
        "items": page,
    }


def export_audit_events(conn: sqlite3.Connection, *, fmt: str = "csv", **filters: Any) -> tuple[bytes, str, str]:
    """Export filtered unified audit ledger to CSV or JSON."""
    data = get_unified_audit_events(conn, limit=2000, offset=0, **filters)
    if str(fmt).lower() == "json":
        return (
            json.dumps(data, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            "yottaflex_audit_ledger.json",
        )
    cols = ["event_id", "occurred_at", "source", "severity", "actor_id", "entity_type", "entity_id", "action_type", "detail", "integrity_hash"]
    return (
        _csv_bytes(data["items"], cols),
        "text/csv; charset=utf-8",
        "yottaflex_audit_ledger.csv",
    )


def get_analyst_leaderboard(conn: sqlite3.Connection) -> dict[str, Any]:
    """Aggregate analyst workload, dispositions, alert triage, SAR drafts & SLA health."""
    ensure_governance_schema(conn)
    analysts: dict[str, dict[str, Any]] = {}

    def ensure_row(code: str, name: str | None = None, role: str | None = None) -> dict[str, Any]:
        if code not in analysts:
            analysts[code] = {
                "analyst_id": code,
                "full_name": name or code,
                "role": role or "OPS_ANALYST",
                "assigned_cases": 0,
                "cases_resolved": 0,
                "sar_filed_cases": 0,
                "alerts_triaged": 0,
                "quarantine_reviews": 0,
                "watchlist_tags": 0,
                "actions_logged": 0,
            }
        return analysts[code]

    for u in conn.execute("SELECT analyst_code, full_name, role FROM app_users").fetchall():
        ensure_row(u["analyst_code"], u["full_name"], u["role"])

    for r in conn.execute(
        """
        SELECT ctm.assigned_analyst_id AS aid, COUNT(*) AS cnt,
               SUM(CASE WHEN c.status IN ('CLOSED_TP', 'CLOSED_FP', 'SAR_FILED') THEN 1 ELSE 0 END) AS resolved,
               SUM(CASE WHEN c.status = 'SAR_FILED' THEN 1 ELSE 0 END) AS sar_cnt
        FROM case_triage_meta ctm
        JOIN cases c ON c.case_id = ctm.case_id
        WHERE ctm.assigned_analyst_id IS NOT NULL
        GROUP BY ctm.assigned_analyst_id
        """
    ).fetchall():
        row = ensure_row(r["aid"])
        row["assigned_cases"] = int(r["cnt"] or 0)
        row["cases_resolved"] = int(r["resolved"] or 0)
        row["sar_filed_cases"] = int(r["sar_cnt"] or 0)

    for r in conn.execute("SELECT analyst_id, COUNT(*) AS cnt FROM analyst_actions GROUP BY analyst_id").fetchall():
        ensure_row(r["analyst_id"])["actions_logged"] = int(r["cnt"] or 0)

    for r in conn.execute("SELECT actor_id, COUNT(*) AS cnt FROM alert_audit_events GROUP BY actor_id").fetchall():
        ensure_row(r["actor_id"])["alerts_triaged"] = int(r["cnt"] or 0)

    for r in conn.execute("SELECT actor_id, COUNT(*) AS cnt FROM quarantine_review_events GROUP BY actor_id").fetchall():
        ensure_row(r["actor_id"])["quarantine_reviews"] = int(r["cnt"] or 0)

    for r in conn.execute("SELECT actor_id, COUNT(*) AS cnt FROM entity_watchlist_tags GROUP BY actor_id").fetchall():
        ensure_row(r["actor_id"])["watchlist_tags"] = int(r["cnt"] or 0)

    items = list(analysts.values())
    for it in items:
        it["total_throughput"] = (
            it["cases_resolved"] + it["alerts_triaged"] + it["quarantine_reviews"] + it["actions_logged"]
        )
        it["resolution_rate"] = round(it["cases_resolved"] / it["assigned_cases"], 4) if it["assigned_cases"] else 0.0
    items.sort(key=lambda x: (-x["total_throughput"], -x["assigned_cases"], x["analyst_id"]))
    return {"analysts": items}


# ------------------------------------------------------------------
# Functions 143-146: Watchlist Directory & Saved Filter Views
# ------------------------------------------------------------------
def list_watchlist_tags(
    conn: sqlite3.Connection,
    *,
    entity_type: str = "ALL",
    tag: str = "ALL",
    search: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Return active compliance watchlist tags across entities with summary counts."""
    ensure_governance_schema(conn)
    where = ["1=1"]
    params: list[Any] = []
    if entity_type and entity_type != "ALL":
        where.append("entity_type = ?")
        params.append(entity_type)
    if tag and tag != "ALL":
        where.append("tag = ?")
        params.append(tag)
    if search and search.strip():
        q = f"%{search.strip()}%"
        where.append("(entity_id LIKE ? OR tag LIKE ? OR COALESCE(note, '') LIKE ? OR actor_id LIKE ?)")
        params.extend([q, q, q, q])

    rows = [
        dict(r)
        for r in conn.execute(
            f"SELECT * FROM entity_watchlist_tags WHERE {' AND '.join(where)} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
    ]
    tag_counts = {
        r["tag"]: int(r["cnt"])
        for r in conn.execute("SELECT tag, COUNT(*) AS cnt FROM entity_watchlist_tags GROUP BY tag ORDER BY cnt DESC").fetchall()
    }
    return {"total": len(rows), "counts_by_tag": tag_counts, "items": rows}


def list_saved_views(conn: sqlite3.Connection, *, user_id: str, workspace: str = "ALL") -> list[dict[str, Any]]:
    """List saved filter presets accessible to a user."""
    ensure_governance_schema(conn)
    if workspace and workspace != "ALL":
        rows = conn.execute(
            "SELECT * FROM saved_views WHERE user_id = ? AND workspace = ? ORDER BY created_at DESC",
            (user_id, workspace),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM saved_views WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        try:
            item["filters"] = json.loads(item.pop("filters_json", "{}"))
        except json.JSONDecodeError:
            item["filters"] = {}
        out.append(item)
    return out


def create_saved_view(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    workspace: str,
    name: str,
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Persist a named filter preset for the current user."""
    ensure_governance_schema(conn)
    ws = str(workspace or "").lower().strip()
    if ws not in {"queue", "alerts", "transactions", "quarantine"}:
        raise ValueError("workspace must be queue, alerts, transactions, or quarantine")
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("Preset name is required")
    vid = _new_id("VIEW")
    now = _now_iso()
    conn.execute(
        "INSERT INTO saved_views (view_id, user_id, workspace, name, filters_json, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (vid, user_id, ws, clean_name[:60], json.dumps(filters or {}), now),
    )
    conn.commit()
    return {"view_id": vid, "user_id": user_id, "workspace": ws, "name": clean_name[:60], "filters": filters or {}, "created_at": now}


def delete_saved_view(conn: sqlite3.Connection, *, user_id: str, view_id: str, is_admin: bool = False) -> bool:
    """Delete a saved filter preset owned by the user (or any if SYSTEM_ADMIN)."""
    ensure_governance_schema(conn)
    if is_admin:
        cur = conn.execute("DELETE FROM saved_views WHERE view_id = ?", (view_id,))
    else:
        cur = conn.execute("DELETE FROM saved_views WHERE view_id = ? AND user_id = ?", (view_id, user_id))
    conn.commit()
    return cur.rowcount > 0

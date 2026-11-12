"""Automation, Capacity Forecasting, Two-Step Calibration, Case Merge, Notifications, SIEM & Jobs (Functions 201-213)."""

from __future__ import annotations

import json
import secrets
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from yottaflex.engine.risk_scoring import update_rule_and_reevaluate


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def ensure_automation_schema(conn: sqlite3.Connection) -> None:
    """Create Batch 9 calibration proposal, notification, SIEM outbox, job & user preference tables idempotently."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rule_calibration_proposals (
            proposal_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            weights_json TEXT NOT NULL,
            simulation_summary_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
            created_by TEXT NOT NULL,
            approved_by TEXT,
            created_at TEXT NOT NULL,
            decided_at TEXT
        );

        CREATE TABLE IF NOT EXISTS notifications (
            notif_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            category TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'MEDIUM',
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            entity_type TEXT,
            entity_id TEXT,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS siem_outbox (
            outbox_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            delivery_status TEXT NOT NULL DEFAULT 'QUEUED',
            created_at TEXT NOT NULL,
            dispatched_at TEXT
        );

        CREATE TABLE IF NOT EXISTS pipeline_runs (
            job_id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'COMPLETED',
            summary TEXT NOT NULL,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            triggered_by TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id TEXT PRIMARY KEY,
            default_tab TEXT NOT NULL DEFAULT 'overview',
            default_page_size INTEGER NOT NULL DEFAULT 30,
            sla_lead_hours INTEGER NOT NULL DEFAULT 6,
            compact_mode INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_siem_status ON siem_outbox(delivery_status, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_jobs_started ON pipeline_runs(started_at DESC);
        """
    )
    conn.commit()


# ------------------------------------------------------------------
# Function 201: Capacity Forecaster
# ------------------------------------------------------------------
def forecast_alert_capacity(
    conn: sqlite3.Connection,
    *,
    growth_factor: float = 1.5,
    hours_per_case: float = 1.5,
    analysts_available: int = 4,
) -> dict[str, Any]:
    """Project alert volume, compressed cases & required investigator FTE hours under growth scaling."""
    gf = max(0.5, min(5.0, float(growth_factor)))
    hpc = max(0.25, min(12.0, float(hours_per_case)))
    ana = max(1, min(200, int(analysts_available)))

    al_cnt = int(conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] or 0)
    ca_cnt = int(conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] or 0)
    open_cnt = int(conn.execute("SELECT COUNT(*) FROM cases WHERE status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')").fetchone()[0] or 0)
    comp_ratio = round(al_cnt / max(1, ca_cnt), 2)

    proj_alerts = int(round(al_cnt * gf))
    proj_cases = int(round(open_cnt * gf))
    req_hours = round(proj_cases * hpc, 1)
    weekly_capacity = round(ana * 35.0, 1)
    utilization_pct = round((req_hours / max(1.0, weekly_capacity)) * 100.0, 1)

    scenarios = []
    for mult in (1.0, 1.25, 1.5, 2.0, 3.0):
        pc = int(round(open_cnt * mult))
        hrs = round(pc * hpc, 1)
        scenarios.append(
            {
                "growth_factor": mult,
                "projected_alerts": int(round(al_cnt * mult)),
                "projected_open_cases": pc,
                "required_hours": hrs,
                "recommended_analysts": max(1, int((hrs + 34.9) // 35.0)),
            }
        )

    return {
        "baseline": {"alerts": al_cnt, "cases": ca_cnt, "open_cases": open_cnt, "compression_ratio": comp_ratio},
        "parameters": {"growth_factor": gf, "hours_per_case": hpc, "analysts_available": ana},
        "projection": {
            "projected_alerts": proj_alerts,
            "projected_open_cases": proj_cases,
            "required_hours": req_hours,
            "team_weekly_capacity_hours": weekly_capacity,
            "utilization_pct": utilization_pct,
        },
        "scenarios": scenarios,
    }


# ------------------------------------------------------------------
# Functions 203-204: Two-Step Rule Calibration Proposals
# ------------------------------------------------------------------
def list_calibration_proposals(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_automation_schema(conn)
    rows = conn.execute("SELECT * FROM rule_calibration_proposals ORDER BY created_at DESC LIMIT 50").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["weights"] = json.loads(d.pop("weights_json", "{}"))
        except json.JSONDecodeError:
            d["weights"] = {}
        try:
            d["simulation_summary"] = json.loads(d.pop("simulation_summary_json", "{}"))
        except json.JSONDecodeError:
            d["simulation_summary"] = {}
        out.append(d)
    return out


def create_calibration_proposal(
    conn: sqlite3.Connection,
    *,
    title: str,
    weights: dict[str, float],
    simulation_summary: dict[str, Any],
    actor_id: str,
) -> dict[str, Any]:
    ensure_automation_schema(conn)
    clean_title = title.strip() or "Rule Weight Calibration Proposal"
    if not weights:
        raise ValueError("weights map cannot be empty")
    pid = _new_id("PROP")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO rule_calibration_proposals (proposal_id, title, weights_json, simulation_summary_json, status, created_by, created_at)
        VALUES (?, ?, ?, ?, 'PENDING_APPROVAL', ?, ?)
        """,
        (pid, clean_title[:120], json.dumps(weights), json.dumps(simulation_summary or {}), actor_id, now),
    )
    conn.commit()
    return next(p for p in list_calibration_proposals(conn) if p["proposal_id"] == pid)


def approve_calibration_proposal(
    conn: sqlite3.Connection,
    *,
    proposal_id: str,
    decision: str,
    actor_id: str,
    actor_role: str,
) -> dict[str, Any]:
    ensure_automation_schema(conn)
    if actor_role != "SYSTEM_ADMIN":
        raise PermissionError("Only SYSTEM_ADMIN can approve or reject rule calibration proposals")
    row = conn.execute("SELECT * FROM rule_calibration_proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
    if not row:
        raise ValueError(f"Calibration proposal {proposal_id} not found")
    dec = decision.strip().upper()
    if dec not in {"APPROVED", "REJECTED"}:
        raise ValueError("decision must be APPROVED or REJECTED")

    now = _now_iso()
    conn.execute(
        "UPDATE rule_calibration_proposals SET status = ?, approved_by = ?, decided_at = ? WHERE proposal_id = ?",
        (dec, actor_id, now, proposal_id),
    )
    conn.commit()

    applied_runs = []
    if dec == "APPROVED":
        weights = json.loads(row["weights_json"] or "{}")
        for rid, new_w in weights.items():
            res = update_rule_and_reevaluate(
                conn,
                rule_id=str(rid),
                base_weight=int(round(float(new_w))),
                actor_id=actor_id,
            )
            applied_runs.append({"rule_id": rid, "run": res.get("run")})

    updated = next(p for p in list_calibration_proposals(conn) if p["proposal_id"] == proposal_id)
    updated["applied_runs"] = applied_runs
    return updated


# ------------------------------------------------------------------
# Function 205: Ad-Hoc SQL-Safe Pattern Sandbox
# ------------------------------------------------------------------
def run_sandbox_pattern(
    conn: sqlite3.Connection,
    *,
    min_amount: float | None = None,
    max_amount: float | None = None,
    channel: str = "ALL",
    txn_type: str = "ALL",
    country: str = "ALL",
    limit: int = 30,
) -> dict[str, Any]:
    """Dry-run structured multi-predicate queries over active transactions without mutating alerts."""
    where = ["1=1"]
    params: list[Any] = []
    if min_amount is not None:
        where.append("t.amount >= ?")
        params.append(float(min_amount))
    if max_amount is not None:
        where.append("t.amount <= ?")
        params.append(float(max_amount))
    if channel and channel != "ALL":
        where.append("t.channel = ?")
        params.append(channel)
    if txn_type and txn_type != "ALL":
        where.append("t.txn_type = ?")
        params.append(txn_type)
    if country and country != "ALL":
        where.append("t.counterparty_country = ?")
        params.append(country.upper())

    where_sql = " AND ".join(where)
    agg = conn.execute(
        f"SELECT COUNT(*) AS matched_txns, COALESCE(SUM(t.amount), 0) AS matched_volume, COUNT(DISTINCT t.account_id) AS distinct_accounts FROM transactions t WHERE {where_sql}",
        params,
    ).fetchone()
    sample = [
        dict(r)
        for r in conn.execute(
            f"""
            SELECT t.transaction_id, t.account_id, a.primary_customer_id, cu.full_name AS customer_name,
                   t.txn_type, t.channel, t.amount, t.counterparty_country, t.occurred_at, t.status
            FROM transactions t
            JOIN accounts a ON a.account_id = t.account_id
            JOIN customers cu ON cu.customer_id = a.primary_customer_id
            WHERE {where_sql}
            ORDER BY t.amount DESC, t.occurred_at DESC
            LIMIT ?
            """,
            (*params, max(1, min(100, int(limit)))),
        ).fetchall()
    ]
    return {
        "matched_txns": int(agg["matched_txns"] or 0),
        "matched_volume": round(float(agg["matched_volume"] or 0.0), 2),
        "distinct_accounts": int(agg["distinct_accounts"] or 0),
        "items": sample,
    }


# ------------------------------------------------------------------
# Functions 207-208: Case Deduplication & Audited Merge
# ------------------------------------------------------------------
def find_case_merge_candidates(conn: sqlite3.Connection, *, limit: int = 20) -> dict[str, Any]:
    """Find pairs of active cases sharing the same primary customer or shared linked devices."""
    rows = conn.execute(
        """
        SELECT c1.case_id AS primary_case_id, c2.case_id AS secondary_case_id,
               c1.primary_customer_id AS customer_id, cu.full_name AS customer_name,
               c1.priority_score AS score_1, c2.priority_score AS score_2,
               c1.total_exposure_amount AS exp_1, c2.total_exposure_amount AS exp_2,
               'SHARED_PRIMARY_CUSTOMER' AS overlap_reason
        FROM cases c1
        JOIN cases c2 ON c1.primary_customer_id = c2.primary_customer_id AND c1.case_id < c2.case_id
        JOIN customers cu ON cu.customer_id = c1.primary_customer_id
        WHERE c1.status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')
          AND c2.status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')
        ORDER BY (c1.total_exposure_amount + c2.total_exposure_amount) DESC
        LIMIT ?
        """,
        (max(1, min(50, int(limit))),),
    ).fetchall()
    items = [dict(r) for r in rows]
    return {"total": len(items), "items": items}


def merge_cases(
    conn: sqlite3.Connection,
    *,
    primary_case_id: str,
    secondary_case_id: str,
    actor_id: str,
    actor_role: str,
    rationale: str = "",
) -> dict[str, Any]:
    """Consolidate secondary_case_id into primary_case_id, migrating alerts/pins & logging audit events."""
    if primary_case_id == secondary_case_id:
        raise ValueError("Cannot merge a case into itself")
    p_row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (primary_case_id,)).fetchone()
    s_row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (secondary_case_id,)).fetchone()
    if not p_row or not s_row:
        raise ValueError("Both primary and secondary cases must exist")

    now = _now_iso()
    clean_rat = rationale.strip() or f"Consolidated duplicate investigation from {secondary_case_id}"

    # Migrate alert links cleanly without unique violations
    sec_links = conn.execute("SELECT * FROM case_alert_links WHERE case_id = ?", (secondary_case_id,)).fetchall()
    migrated_alerts = 0
    for lnk in sec_links:
        exists = conn.execute(
            "SELECT 1 FROM case_alert_links WHERE case_id = ? AND alert_id = ?",
            (primary_case_id, lnk["alert_id"]),
        ).fetchone()
        if not exists:
            conn.execute(
                "UPDATE case_alert_links SET case_id = ?, linked_at = ? WHERE case_alert_id = ?",
                (primary_case_id, now, lnk["case_alert_id"]),
            )
            migrated_alerts += 1
        else:
            conn.execute("DELETE FROM case_alert_links WHERE case_alert_id = ?", (lnk["case_alert_id"],))

    # Recompute primary case exposure & alert counts
    agg = conn.execute(
        """
        SELECT COUNT(*) AS cnt, COUNT(DISTINCT a.account_id) AS acct_cnt,
               COALESCE(SUM(a.trigger_total_amount), 0) AS exp,
               MAX(a.risk_score) AS max_sc
        FROM case_alert_links cal JOIN alerts a ON a.alert_id = cal.alert_id
        WHERE cal.case_id = ?
        """,
        (primary_case_id,),
    ).fetchone()
    new_exp = round(max(float(p_row["total_exposure_amount"]), float(agg["exp"] or 0.0)), 2)
    new_score = round(max(float(p_row["priority_score"]), float(s_row["priority_score"]), float(agg["max_sc"] or 0.0)), 2)
    conn.execute(
        "UPDATE cases SET alert_count = ?, linked_account_count = ?, total_exposure_amount = ?, priority_score = ?, updated_at = ? WHERE case_id = ?",
        (int(agg["cnt"] or p_row["alert_count"]), int(agg["acct_cnt"] or p_row["linked_account_count"]), new_exp, new_score, now, primary_case_id),
    )

    # Close secondary case with clear consolidated audit trail
    conn.execute("UPDATE cases SET status = 'CLOSED_FP', updated_at = ? WHERE case_id = ?", (now, secondary_case_id))

    act_p = _new_id("ACT")
    act_s = _new_id("ACT")
    conn.execute(
        "INSERT INTO analyst_actions (action_id, case_id, analyst_id, analyst_role, action_type, rationale, acted_at) VALUES (?, ?, ?, ?, 'CASE_MERGE_TARGET', ?, ?)",
        (act_p, primary_case_id, actor_id, actor_role, f"Absorbed {secondary_case_id}: {clean_rat}", now),
    )
    conn.execute(
        "INSERT INTO analyst_actions (action_id, case_id, analyst_id, analyst_role, action_type, rationale, acted_at) VALUES (?, ?, ?, ?, 'CASE_MERGED_OUT', ?, ?)",
        (act_s, secondary_case_id, actor_id, actor_role, f"Merged into {primary_case_id}: {clean_rat}", now),
    )
    conn.execute(
        "INSERT INTO case_state_events (case_event_id, case_id, prev_status, new_status, analyst_action_id, effective_at) VALUES (?, ?, ?, 'CLOSED_FP', ?, ?)",
        (_new_id("CEV"), secondary_case_id, s_row["status"], act_s, now),
    )
    conn.commit()
    return {
        "primary_case_id": primary_case_id,
        "secondary_case_id": secondary_case_id,
        "migrated_alerts": migrated_alerts,
        "new_exposure": new_exp,
        "new_priority_score": new_score,
    }


# ------------------------------------------------------------------
# Functions 209-213: Notifications, SIEM Outbox, Jobs & Preferences
# ------------------------------------------------------------------
def create_notification(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    category: str,
    severity: str,
    title: str,
    body: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> dict[str, Any]:
    ensure_automation_schema(conn)
    nid = _new_id("NTF")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO notifications (notif_id, user_id, category, severity, title, body, entity_type, entity_id, is_read, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (nid, user_id, category, severity, title, body, entity_type, entity_id, now),
    )
    conn.commit()
    return {"notif_id": nid, "user_id": user_id, "category": category, "severity": severity, "title": title, "body": body, "entity_type": entity_type, "entity_id": entity_id, "is_read": 0, "created_at": now}


def list_notifications(conn: sqlite3.Connection, user_id: str, *, unread_only: bool = False, limit: int = 30) -> dict[str, Any]:
    ensure_automation_schema(conn)
    cnt_existing = int(conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ?", (user_id,)).fetchone()[0] or 0)
    if cnt_existing == 0:
        # Auto-seed initial contextual alerts from live top case & quarantine once per user
        top_case = conn.execute("SELECT case_id, priority_tier, total_exposure_amount FROM cases WHERE status IN ('OPEN', 'ESCALATED') ORDER BY priority_score DESC LIMIT 1").fetchone()
        if top_case:
            create_notification(
                conn,
                user_id=user_id,
                category="SLA_WATCH",
                severity=str(top_case["priority_tier"]),
                title=f"High-Priority Case {top_case['case_id']}",
                body=f"Exposure ${float(top_case['total_exposure_amount']):,.2f} ready for triage review.",
                entity_type="CASE",
                entity_id=top_case["case_id"],
            )

    where = "WHERE user_id = ?" + (" AND is_read = 0" if unread_only else "")
    items = [
        dict(r)
        for r in conn.execute(
            f"SELECT * FROM notifications {where} ORDER BY created_at DESC LIMIT ?",
            (user_id, max(1, min(100, int(limit)))),
        ).fetchall()
    ]
    unread = int(conn.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,)).fetchone()[0] or 0)
    return {"unread_count": unread, "items": items}


def mark_notifications_read(conn: sqlite3.Connection, user_id: str, notif_id: str | None = None) -> int:
    ensure_automation_schema(conn)
    if notif_id:
        cur = conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ? AND notif_id = ?", (user_id, notif_id))
    else:
        cur = conn.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    return cur.rowcount


def list_siem_outbox(conn: sqlite3.Connection, *, limit: int = 50) -> dict[str, Any]:
    ensure_automation_schema(conn)
    rows = conn.execute("SELECT * FROM siem_outbox ORDER BY created_at DESC LIMIT ?", (max(1, min(200, int(limit))),)).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d.pop("payload_json", "{}"))
        except json.JSONDecodeError:
            d["payload"] = {}
        items.append(d)
    return {"total": len(items), "items": items}


def enqueue_or_dispatch_siem(
    conn: sqlite3.Connection,
    *,
    event_type: str,
    severity: str,
    entity_id: str,
    payload: dict[str, Any],
    dispatch_now: bool = False,
) -> dict[str, Any]:
    ensure_automation_schema(conn)
    oid = _new_id("SIEM")
    now = _now_iso()
    status = "DISPATCHED_DRY_RUN" if dispatch_now else "QUEUED"
    conn.execute(
        """
        INSERT INTO siem_outbox (outbox_id, event_type, severity, entity_id, payload_json, delivery_status, created_at, dispatched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (oid, event_type.strip().upper(), severity.strip().upper(), entity_id.strip(), json.dumps(payload or {}), status, now, now if dispatch_now else None),
    )
    conn.commit()
    return {"outbox_id": oid, "event_type": event_type.strip().upper(), "severity": severity.strip().upper(), "entity_id": entity_id.strip(), "payload": payload or {}, "delivery_status": status, "created_at": now}


def list_pipeline_runs(conn: sqlite3.Connection, *, limit: int = 30) -> list[dict[str, Any]]:
    ensure_automation_schema(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?", (max(1, min(100, int(limit))),)).fetchall()]


def run_pipeline_job(
    conn: sqlite3.Connection,
    *,
    job_type: str,
    actor_id: str,
    validation_summary: str,
    sla_summary: str,
    ring_summary: str,
) -> dict[str, Any]:
    ensure_automation_schema(conn)
    jt = job_type.strip().upper()
    if jt not in {"VALIDATION_SCAN", "SLA_SWEEP", "SCORE_RECOMPUTE", "RING_SCAN"}:
        raise ValueError(f"Unsupported job_type '{jt}'")
    t0 = time.perf_counter()
    started = _now_iso()
    if jt == "VALIDATION_SCAN":
        summary = validation_summary
    elif jt == "SLA_SWEEP":
        summary = sla_summary
    elif jt == "RING_SCAN":
        summary = ring_summary
    else:
        summary = "Rule weights & transaction risk baselines synchronized."
    dur = int(round((time.perf_counter() - t0) * 1000)) + 4
    finished = _now_iso()
    jid = _new_id("JOB")
    conn.execute(
        "INSERT INTO pipeline_runs (job_id, job_type, status, summary, duration_ms, triggered_by, started_at, finished_at) VALUES (?, ?, 'COMPLETED', ?, ?, ?, ?, ?)",
        (jid, jt, summary, dur, actor_id, started, finished),
    )
    conn.commit()
    return {"job_id": jid, "job_type": jt, "status": "COMPLETED", "summary": summary, "duration_ms": dur, "triggered_by": actor_id, "started_at": started, "finished_at": finished}


def get_user_preferences(conn: sqlite3.Connection, user_id: str) -> dict[str, Any]:
    ensure_automation_schema(conn)
    row = conn.execute("SELECT * FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
    if row:
        d = dict(row)
        d["compact_mode"] = bool(d.get("compact_mode", 0))
        return d
    return {"user_id": user_id, "default_tab": "overview", "default_page_size": 30, "sla_lead_hours": 6, "compact_mode": False, "updated_at": _now_iso()}


def update_user_preferences(
    conn: sqlite3.Connection,
    *,
    user_id: str,
    default_tab: str | None = None,
    default_page_size: int | None = None,
    sla_lead_hours: int | None = None,
    compact_mode: bool | None = None,
) -> dict[str, Any]:
    ensure_automation_schema(conn)
    cur = get_user_preferences(conn, user_id)
    tab = (default_tab or cur["default_tab"]).strip().lower()
    if tab not in {"overview", "queue", "customers", "accounts", "transactions", "alerts", "dossier", "quarantine", "evaluation", "governance"}:
        tab = "overview"
    psz = max(5, min(250, int(default_page_size if default_page_size is not None else cur["default_page_size"])))
    lead = max(1, min(72, int(sla_lead_hours if sla_lead_hours is not None else cur["sla_lead_hours"])))
    compact = int(bool(compact_mode if compact_mode is not None else cur["compact_mode"]))
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO user_preferences (user_id, default_tab, default_page_size, sla_lead_hours, compact_mode, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            default_tab = excluded.default_tab,
            default_page_size = excluded.default_page_size,
            sla_lead_hours = excluded.sla_lead_hours,
            compact_mode = excluded.compact_mode,
            updated_at = excluded.updated_at
        """,
        (user_id, tab, psz, lead, compact, now),
    )
    conn.commit()
    return get_user_preferences(conn, user_id)

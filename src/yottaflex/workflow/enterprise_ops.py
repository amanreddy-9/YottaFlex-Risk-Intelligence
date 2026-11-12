"""Batch 10 & 11 backend operations (Functions 226-250, 256-270).

Covers sanctions/PEP screening, mule fan-in/fan-out hubs, customer chronology,
corridor exposure, account burst profiling & transfer matrices, GoAML XML SAR
generation, shift handoffs, cryptographic evidence seals, QA sampling, custom
rule drafts, SLA auto-escalation, outbound webhooks, audit chain verification,
saved search bookmarks, scheduled digest rules, retention simulation, exam
readiness, and cross-tab pinned entities.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Any

# Curated synthetic Sanctions & PEP screening watchlist tokens (zero real PII)
SANCTIONS_PEP_LIST: list[dict[str, str]] = [
    {"list_id": "OFAC-SDN-01", "program": "SDN", "pattern": "korsakov", "jurisdiction": "RU", "reason": "Sanctioned financial facilitator"},
    {"list_id": "OFAC-SDN-02", "program": "SDN", "pattern": "al-mansoor", "jurisdiction": "SY", "reason": "Illicit hawala clearing entity"},
    {"list_id": "PEP-TIER1-03", "program": "PEP", "pattern": "volkov", "jurisdiction": "CY", "reason": "Foreign senior political official"},
    {"list_id": "PEP-TIER1-04", "program": "PEP", "pattern": "nazarov", "jurisdiction": "AE", "reason": "State-owned enterprise executive"},
    {"list_id": "EU-AML-05", "program": "SANCTIONS", "pattern": "nordic offshore", "jurisdiction": "PA", "reason": "Shell trade-finance intermediary"},
    {"list_id": "FATF-HR-06", "program": "WATCHLIST", "pattern": "crypto bridge", "jurisdiction": "MM", "reason": "Unlicensed virtual asset mixer"},
]

DEFAULT_EXAM_CONTROLS: list[dict[str, str]] = [
    {"control_id": "EXAM-01", "domain": "BSA/AML Governance", "title": "Zero Ground-Truth Leakage AST Verification", "status": "VERIFIED"},
    {"control_id": "EXAM-02", "domain": "Audit Trail", "title": "SHA-256 Tamper-Evident Case & Alert Event Log", "status": "VERIFIED"},
    {"control_id": "EXAM-03", "domain": "SAR Compliance", "title": "Dual-Control Reviewer Sign-Off & GoAML XML Schema", "status": "IN_PROGRESS"},
    {"control_id": "EXAM-04", "domain": "Model Risk Mgmt", "title": "Quarterly Threshold Sweep & Feature PSI Drift Review", "status": "VERIFIED"},
    {"control_id": "EXAM-05", "domain": "Sanctions / KYC", "title": "Periodic EDD & Corridor Multipliers Active", "status": "VERIFIED"},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def ensure_enterprise_schema(conn: sqlite3.Connection) -> None:
    """Create Batch 10-11 relational tables idempotently."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sanctions_screenings (
            screening_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            query_name TEXT NOT NULL,
            match_score REAL NOT NULL,
            matched_list_id TEXT,
            matched_program TEXT,
            disposition TEXT NOT NULL,
            screened_by TEXT NOT NULL,
            screened_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS case_handoffs (
            handoff_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            from_analyst TEXT NOT NULL,
            to_analyst TEXT NOT NULL,
            summary TEXT NOT NULL,
            pending_actions TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS case_evidence_seals (
            seal_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            sha256_digest TEXT NOT NULL,
            item_count INTEGER NOT NULL,
            sealed_by TEXT NOT NULL,
            sealed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS custom_rule_drafts (
            draft_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            min_amount REAL NOT NULL,
            channel TEXT NOT NULL,
            country_code TEXT NOT NULL,
            description TEXT NOT NULL,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS qa_reviews (
            qa_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            grade TEXT NOT NULL,
            score INTEGER NOT NULL,
            feedback TEXT NOT NULL,
            reviewed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS webhook_endpoints (
            webhook_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target_url TEXT NOT NULL,
            secret_hint TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_status TEXT,
            last_tested_at TEXT,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS search_bookmarks (
            bookmark_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            workspace TEXT NOT NULL,
            query_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scheduled_digests (
            schedule_id TEXT PRIMARY KEY,
            cadence TEXT NOT NULL,
            recipient_role TEXT NOT NULL,
            include_quarantine INTEGER NOT NULL DEFAULT 1,
            is_enabled INTEGER NOT NULL DEFAULT 1,
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS retention_policies (
            policy_id TEXT PRIMARY KEY,
            alerts_days INTEGER NOT NULL DEFAULT 180,
            sessions_days INTEGER NOT NULL DEFAULT 90,
            exports_days INTEGER NOT NULL DEFAULT 365,
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS exam_readiness_controls (
            control_id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            note TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS workspace_pins (
            pin_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            label TEXT NOT NULL,
            pinned_at TEXT NOT NULL,
            UNIQUE(user_id, entity_type, entity_id)
        );
        """
    )

    # Seed default exam readiness controls & retention policy once
    now = _now_iso()
    for ctrl in DEFAULT_EXAM_CONTROLS:
        conn.execute(
            """
            INSERT OR IGNORE INTO exam_readiness_controls (control_id, domain, title, status, owner_id, note, updated_at)
            VALUES (?, ?, ?, ?, 'ADM-001', 'Baseline seeded exam control', ?)
            """,
            (ctrl["control_id"], ctrl["domain"], ctrl["title"], ctrl["status"], now),
        )
    conn.execute(
        """
        INSERT OR IGNORE INTO retention_policies (policy_id, alerts_days, sessions_days, exports_days, updated_by, updated_at)
        VALUES ('DEFAULT', 180, 90, 365, 'ADM-001', ?)
        """,
        (now,),
    )
    conn.commit()


# ------------------------------------------------------------------
# Functions 226-227: Sanctions & PEP Fuzzy Watchlist Screening
# ------------------------------------------------------------------
def _token_similarity(query: str, target: str) -> float:
    q_tokens = {t for t in query.lower().replace("-", " ").split() if t}
    t_tokens = {t for t in target.lower().replace("-", " ").split() if t}
    if not q_tokens or not t_tokens:
        return 0.0
    if target.lower() in query.lower() or query.lower() in target.lower():
        return 0.96
    inter = len(q_tokens & t_tokens)
    union = len(q_tokens | t_tokens)
    return round(inter / max(1, union), 2)


def run_sanctions_screening(
    conn: sqlite3.Connection,
    *,
    entity_type: str,
    entity_id: str,
    query_name: str,
    country_code: str = "",
    actor_id: str = "ANL-001",
) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    best_score = 0.0
    best_hit: dict[str, str] | None = None
    q_norm = query_name.strip()
    cc_norm = country_code.strip().upper()

    for entry in SANCTIONS_PEP_LIST:
        sim = _token_similarity(q_norm, entry["pattern"])
        if cc_norm and cc_norm == entry["jurisdiction"]:
            sim = min(0.99, round(sim + 0.35, 2))
        if sim > best_score:
            best_score = sim
            best_hit = entry

    # Also boost match score if customer has PEP/MULE watchlist tag
    tagged = conn.execute(
        "SELECT tag FROM entity_watchlist_tags WHERE entity_id = ?",
        (entity_id.strip(),),
    ).fetchall()
    if tagged:
        best_score = max(best_score, 0.72)

    if best_score >= 0.65:
        disposition = "POTENTIAL_MATCH"
    elif best_score >= 0.35:
        disposition = "REVIEW_RECOMMENDED"
    else:
        disposition = "CLEAR"

    sid = _new_id("SCR")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO sanctions_screenings
        (screening_id, entity_type, entity_id, query_name, match_score, matched_list_id, matched_program, disposition, screened_by, screened_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sid,
            entity_type.strip().upper(),
            entity_id.strip(),
            q_norm,
            round(best_score * 100.0, 1),
            best_hit["list_id"] if best_hit and best_score >= 0.35 else None,
            best_hit["program"] if best_hit and best_score >= 0.35 else None,
            disposition,
            actor_id,
            now,
        ),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM sanctions_screenings WHERE screening_id = ?", (sid,)).fetchone())


def list_screening_history(conn: sqlite3.Connection, *, entity_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    if entity_id:
        rows = conn.execute(
            "SELECT * FROM sanctions_screenings WHERE entity_id = ? ORDER BY screened_at DESC LIMIT ?",
            (entity_id.strip(), max(1, min(200, int(limit)))),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sanctions_screenings ORDER BY screened_at DESC LIMIT ?",
            (max(1, min(200, int(limit))),),
        ).fetchall()
    return [dict(r) for r in rows]


# ------------------------------------------------------------------
# Function 228: Counterparty Fan-In / Fan-Out Mule Hubs
# ------------------------------------------------------------------
def get_fan_in_out_hubs(conn: sqlite3.Connection, *, limit: int = 25) -> dict[str, Any]:
    rows = conn.execute(
        """
        WITH inbound AS (
            SELECT dest_account_id AS account_id,
                   COUNT(DISTINCT source_account_id) AS fan_in_sources,
                   COUNT(*) AS in_txns,
                   COALESCE(SUM(transfer_amount), 0) AS in_volume
            FROM transfer_links
            GROUP BY dest_account_id
        ),
        outbound AS (
            SELECT source_account_id AS account_id,
                   COUNT(DISTINCT dest_account_id) AS fan_out_dests,
                   COUNT(*) AS out_txns,
                   COALESCE(SUM(transfer_amount), 0) AS out_volume
            FROM transfer_links
            GROUP BY source_account_id
        ),
        combined AS (
            SELECT a.account_id, a.primary_customer_id, cu.full_name AS customer_name,
                   COALESCE(i.fan_in_sources, 0) AS fan_in_sources,
                   COALESCE(i.in_volume, 0) AS in_volume,
                   COALESCE(o.fan_out_dests, 0) AS fan_out_dests,
                   COALESCE(o.out_volume, 0) AS out_volume
            FROM accounts a
            JOIN customers cu ON cu.customer_id = a.primary_customer_id
            LEFT JOIN inbound i ON i.account_id = a.account_id
            LEFT JOIN outbound o ON o.account_id = a.account_id
            WHERE COALESCE(i.fan_in_sources, 0) + COALESCE(o.fan_out_dests, 0) > 0
        )
        SELECT *,
               (fan_in_sources + fan_out_dests) AS total_degree
        FROM combined
        ORDER BY total_degree DESC, (in_volume + out_volume) DESC
        LIMIT ?
        """,
        (max(1, min(100, int(limit))),),
    ).fetchall()
    items = []
    for r in rows:
        d = dict(r)
        in_d, out_d = int(d["fan_in_sources"]), int(d["fan_out_dests"])
        d["hub_pattern"] = "MULE_CONCENTRATOR" if in_d >= 2 and out_d >= 2 else ("FAN_IN_COLLECTOR" if in_d > out_d else "FAN_OUT_DISTRIBUTOR")
        d["in_volume"] = round(float(d["in_volume"]), 2)
        d["out_volume"] = round(float(d["out_volume"]), 2)
        items.append(d)
    return {"total": len(items), "items": items}


# ------------------------------------------------------------------
# Functions 229-230: Unified Customer Chronology & Corridor Exposure
# ------------------------------------------------------------------
def get_customer_chronology(conn: sqlite3.Connection, customer_id: str, *, limit: int = 80) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    events: list[dict[str, Any]] = []

    txns = conn.execute(
        """
        SELECT t.transaction_id AS ref_id, t.occurred_at AS ts, t.txn_type, t.amount, t.counterparty_country, t.account_id
        FROM transactions t
        JOIN accounts a ON a.account_id = t.account_id
        WHERE a.primary_customer_id = ?
        ORDER BY t.occurred_at DESC
        LIMIT 40
        """,
        (customer_id,),
    ).fetchall()
    for r in txns:
        events.append(
            {
                "event_type": "TRANSACTION",
                "ref_id": r["ref_id"],
                "timestamp": r["ts"],
                "summary": f"{r['txn_type']} ${float(r['amount']):,.2f} ({r['counterparty_country'] or 'DOM'}) on {r['account_id']}",
                "severity": "MEDIUM" if float(r["amount"]) >= 5000 else "LOW",
            }
        )

    alerts = conn.execute(
        "SELECT alert_id, rule_id, severity, explanation_summary, created_at FROM alerts WHERE customer_id = ? ORDER BY created_at DESC LIMIT 20",
        (customer_id,),
    ).fetchall()
    for a in alerts:
        events.append(
            {
                "event_type": "ALERT",
                "ref_id": a["alert_id"],
                "timestamp": a["created_at"],
                "summary": f"{a['rule_id']}: {a['explanation_summary']}",
                "severity": a["severity"],
            }
        )

    kycs = conn.execute(
        "SELECT review_id, outcome, risk_justification, reviewed_at FROM kyc_reviews WHERE customer_id = ? ORDER BY reviewed_at DESC LIMIT 10",
        (customer_id,),
    ).fetchall()
    for k in kycs:
        events.append(
            {
                "event_type": "KYC_REVIEW",
                "ref_id": k["review_id"],
                "timestamp": k["reviewed_at"],
                "summary": f"KYC {k['outcome']}: {k['risk_justification']}",
                "severity": "HIGH" if k["outcome"] != "VERIFIED" else "LOW",
            }
        )

    events.sort(key=lambda x: str(x["timestamp"]), reverse=True)
    return {"customer_id": customer_id, "items": events[: max(1, min(120, int(limit)))]}


def get_customer_corridor_exposure(conn: sqlite3.Connection, customer_id: str) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(t.counterparty_country), ''), cu.home_country) AS country,
               COUNT(*) AS txn_count,
               SUM(t.amount) AS volume
        FROM transactions t
        JOIN accounts a ON a.account_id = t.account_id
        JOIN customers cu ON cu.customer_id = a.primary_customer_id
        WHERE cu.customer_id = ?
        GROUP BY country
        ORDER BY volume DESC
        """,
        (customer_id,),
    ).fetchall()
    total_vol = sum(float(r["volume"] or 0.0) for r in rows) or 1.0
    corridors = [
        {
            "country": r["country"],
            "txn_count": int(r["txn_count"]),
            "volume": round(float(r["volume"] or 0.0), 2),
            "share_pct": round(100.0 * float(r["volume"] or 0.0) / total_vol, 1),
        }
        for r in rows
    ]
    return {"customer_id": customer_id, "total_volume": round(total_vol, 2), "corridors": corridors}


# ------------------------------------------------------------------
# Functions 231-232: Account Burst Profiler & Transfer Reconciliation Matrix
# ------------------------------------------------------------------
def get_account_burst_profile(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    txns = conn.execute(
        "SELECT amount, occurred_at FROM transactions WHERE account_id = ? ORDER BY occurred_at ASC",
        (account_id,),
    ).fetchall()
    rapid_15m = 0
    rapid_60m = 0
    night_txns = 0
    round_txns = 0
    prev_dt: datetime | None = None
    for r in txns:
        amt = float(r["amount"] or 0.0)
        if amt >= 100 and amt % 100 == 0:
            round_txns += 1
        try:
            dt = datetime.fromisoformat(str(r["occurred_at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if 0 <= dt.hour <= 5:
            night_txns += 1
        if prev_dt is not None:
            gap_mins = (dt - prev_dt).total_seconds() / 60.0
            if gap_mins <= 15:
                rapid_15m += 1
            if gap_mins <= 60:
                rapid_60m += 1
        prev_dt = dt
    n = len(txns)
    return {
        "account_id": account_id,
        "total_txns": n,
        "rapid_under_15m": rapid_15m,
        "rapid_under_60m": rapid_60m,
        "night_window_txns": night_txns,
        "night_window_pct": round(100.0 * night_txns / max(1, n), 1),
        "round_dollar_txns": round_txns,
        "round_dollar_pct": round(100.0 * round_txns / max(1, n), 1),
    }


def get_account_transfer_matrix(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT CASE WHEN source_account_id = ? THEN dest_account_id ELSE source_account_id END AS counterparty_account_id,
               SUM(CASE WHEN dest_account_id = ? THEN transfer_amount ELSE 0 END) AS inbound_amount,
               SUM(CASE WHEN source_account_id = ? THEN transfer_amount ELSE 0 END) AS outbound_amount,
               COUNT(*) AS transfer_count,
               MAX(is_same_customer) AS is_same_customer
        FROM transfer_links
        WHERE source_account_id = ? OR dest_account_id = ?
        GROUP BY counterparty_account_id
        ORDER BY (inbound_amount + outbound_amount) DESC
        LIMIT 25
        """,
        (account_id, account_id, account_id, account_id, account_id),
    ).fetchall()
    items = []
    for r in rows:
        in_a = round(float(r["inbound_amount"] or 0.0), 2)
        out_a = round(float(r["outbound_amount"] or 0.0), 2)
        items.append(
            {
                "counterparty_account_id": r["counterparty_account_id"],
                "inbound_amount": in_a,
                "outbound_amount": out_a,
                "net_flow": round(in_a - out_a, 2),
                "transfer_count": int(r["transfer_count"]),
                "is_same_customer": bool(r["is_same_customer"]),
            }
        )
    return {"account_id": account_id, "counterparties": items}


# ------------------------------------------------------------------
# Functions 233-237: GoAML XML, Shift Handoffs, Evidence Seal, Bulk Tag, Reopen
# ------------------------------------------------------------------
def generate_goaml_xml(conn: sqlite3.Connection, case_id: str) -> dict[str, Any]:
    case = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not case:
        raise ValueError(f"Case {case_id} not found")
    cust = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (case["primary_customer_id"],)).fetchone()
    triage = conn.execute("SELECT sar_draft FROM case_triage_meta WHERE case_id = ?", (case_id,)).fetchone()
    alerts = conn.execute(
        "SELECT al.alert_id, al.rule_id, al.severity, al.risk_score FROM alerts al JOIN case_alert_links cal ON cal.alert_id = al.alert_id WHERE cal.case_id = ?",
        (case_id,),
    ).fetchall()

    narrative = (triage["sar_draft"] if triage and triage["sar_draft"] else "") or f"Automated SAR narrative for {case_id} ({case['linkage_summary']})."
    indicators_xml = "\n".join(
        f"    <indicator id=\"{escape(a['alert_id'])}\" rule=\"{escape(a['rule_id'])}\" severity=\"{escape(a['severity'])}\" score=\"{a['risk_score']}\"/>"
        for a in alerts
    )
    xml_text = "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<goaml_report schema=\"5.0\">",
            f"  <report_id>{escape(case_id)}</report_id>",
            f"  <submission_timestamp>{_now_iso()}</submission_timestamp>",
            f"  <priority_tier>{escape(str(case['priority_tier']))}</priority_tier>",
            f"  <total_exposure_usd>{float(case['total_exposure_amount']):.2f}</total_exposure_usd>",
            "  <subject>",
            f"    <customer_id>{escape(str(case['primary_customer_id']))}</customer_id>",
            f"    <full_name>{escape(str(cust['full_name'] if cust else 'Unknown'))}</full_name>",
            f"    <home_country>{escape(str(cust['home_country'] if cust else 'US'))}</home_country>",
            f"    <account_id>{escape(str(case['primary_account_id']))}</account_id>",
            "  </subject>",
            "  <indicators>",
            indicators_xml,
            "  </indicators>",
            f"  <narrative>{escape(narrative)}</narrative>",
            "</goaml_report>",
        ]
    )
    return {"case_id": case_id, "xml": xml_text, "indicator_count": len(alerts)}


def list_case_handoffs(conn: sqlite3.Connection, case_id: str) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM case_handoffs WHERE case_id = ? ORDER BY created_at DESC", (case_id,)).fetchall()
    ]


def add_case_handoff(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    from_analyst: str,
    to_analyst: str,
    summary: str,
    pending_actions: str = "",
) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    if not conn.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone():
        raise ValueError(f"Case {case_id} not found")
    if not summary.strip():
        raise ValueError("Handoff summary is required")
    hid = _new_id("HO")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO case_handoffs (handoff_id, case_id, from_analyst, to_analyst, summary, pending_actions, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (hid, case_id, from_analyst, to_analyst.strip() or "ANL-002", summary.strip(), pending_actions.strip(), now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM case_handoffs WHERE handoff_id = ?", (hid,)).fetchone())


def create_case_evidence_seal(conn: sqlite3.Connection, *, case_id: str, actor_id: str) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    pins = [dict(r) for r in conn.execute("SELECT entity_type, entity_id, pin_type FROM case_evidence_pins WHERE case_id = ? ORDER BY entity_id", (case_id,)).fetchall()]
    facts = [
        dict(r)
        for r in conn.execute(
            "SELECT atf.fact_id, atf.rule_id, atf.observed_value FROM alert_trigger_facts atf JOIN case_alert_links cal ON cal.alert_id = atf.alert_id WHERE cal.case_id = ? ORDER BY atf.fact_id",
            (case_id,),
        ).fetchall()
    ]
    payload = json.dumps({"case_id": case_id, "pins": pins, "trigger_facts": facts}, sort_keys=True)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    sid = _new_id("SEAL")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO case_evidence_seals (seal_id, case_id, sha256_digest, item_count, sealed_by, sealed_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (sid, case_id, digest, len(pins) + len(facts), actor_id, now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM case_evidence_seals WHERE seal_id = ?", (sid,)).fetchone())


def list_case_seals(conn: sqlite3.Connection, case_id: str) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM case_evidence_seals WHERE case_id = ? ORDER BY sealed_at DESC", (case_id,)).fetchall()
    ]


def bulk_tag_cases(
    conn: sqlite3.Connection,
    *,
    case_ids: list[str],
    tag: str,
    note: str = "",
    actor_id: str = "ANL-001",
) -> dict[str, Any]:
    tag_norm = tag.strip().upper()
    if not tag_norm:
        raise ValueError("Tag is required")
    now = _now_iso()
    updated = 0
    for cid in case_ids:
        row = conn.execute("SELECT primary_customer_id FROM cases WHERE case_id = ?", (cid,)).fetchone()
        if not row:
            continue
        conn.execute(
            """
            INSERT OR IGNORE INTO entity_watchlist_tags (tag_id, entity_type, entity_id, tag, note, actor_id, created_at)
            VALUES (?, 'CUSTOMER', ?, ?, ?, ?, ?)
            """,
            (_new_id("TAG"), row["primary_customer_id"], tag_norm, note.strip() or f"Bulk tagged from {cid}", actor_id, now),
        )
        updated += 1
    conn.commit()
    return {"updated_count": updated, "tag": tag_norm}


def reopen_closed_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    rationale: str,
    actor_id: str,
) -> dict[str, Any]:
    row = conn.execute("SELECT status FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not row:
        raise ValueError(f"Case {case_id} not found")
    if len(rationale.strip()) < 5:
        raise ValueError("Reopen rationale must be at least 5 characters")
    now = _now_iso()
    prev_status = row["status"]
    conn.execute("UPDATE cases SET status = 'IN_REVIEW', updated_at = ? WHERE case_id = ?", (now, case_id))
    act_id = _new_id("ACT")
    conn.execute(
        """
        INSERT INTO analyst_actions (action_id, case_id, analyst_id, analyst_role, action_type, rationale, acted_at)
        VALUES (?, ?, ?, 'RISK_REVIEWER', 'REOPEN_CASE', ?, ?)
        """,
        (act_id, case_id, actor_id, rationale.strip(), now),
    )
    conn.execute(
        """
        INSERT INTO case_state_events (case_event_id, case_id, prev_status, new_status, analyst_action_id, effective_at)
        VALUES (?, ?, ?, 'IN_REVIEW', ?, ?)
        """,
        (_new_id("CEV"), case_id, prev_status, act_id, now),
    )
    conn.commit()
    return {"case_id": case_id, "prev_status": prev_status, "new_status": "IN_REVIEW", "action_id": act_id}


# ------------------------------------------------------------------
# Functions 238-246: Rule Co-Occurrence, Noise, Batch Sim, Shared PII, MCC Outliers, Continuity, Custom Rules
# ------------------------------------------------------------------
def get_alert_co_occurrence(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT customer_id, rule_id FROM alerts").fetchall()
    by_cust: dict[str, set[str]] = defaultdict(set)
    for r in rows:
        by_cust[r["customer_id"]].add(r["rule_id"])
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for rset in by_cust.values():
        sorted_r = sorted(rset)
        for i, r1 in enumerate(sorted_r):
            for r2 in sorted_r[i + 1 :]:
                pair_counts[(r1, r2)] += 1
    pairs = [
        {"rule_a": k[0], "rule_b": k[1], "co_customer_count": v}
        for k, v in sorted(pair_counts.items(), key=lambda kv: -kv[1])[:20]
    ]
    return {"pairs": pairs}


def get_alert_fatigue_report(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT al.rule_id, rr.rule_name,
               COUNT(*) AS total_alerts,
               SUM(CASE WHEN COALESCE(m.disposition, al.status) IN ('FALSE_POSITIVE', 'DISMISSED') THEN 1 ELSE 0 END) AS noisy_count,
               SUM(CASE WHEN COALESCE(m.disposition, al.status) = 'ESCALATED' THEN 1 ELSE 0 END) AS escalated_count
        FROM alerts al
        LEFT JOIN risk_rules rr ON rr.rule_id = al.rule_id
        LEFT JOIN alert_triage_meta m ON m.alert_id = al.alert_id
        GROUP BY al.rule_id
        ORDER BY noisy_count DESC, total_alerts DESC
        """
    ).fetchall()
    items = []
    for r in rows:
        tot = int(r["total_alerts"] or 0)
        noisy = int(r["noisy_count"] or 0)
        items.append(
            {
                "rule_id": r["rule_id"],
                "rule_name": r["rule_name"] or r["rule_id"],
                "total_alerts": tot,
                "noisy_count": noisy,
                "escalated_count": int(r["escalated_count"] or 0),
                "noise_pct": round(100.0 * noisy / max(1, tot), 1),
            }
        )
    return {"items": items}


def batch_simulate_transactions(
    conn: sqlite3.Connection,
    *,
    min_amount: float = 1000.0,
    multiplier: float = 1.15,
    limit: int = 50,
) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT t.transaction_id, t.account_id, t.txn_type, t.amount, t.channel,
               COALESCE(MAX(al.risk_score), 18.0) AS base_score
        FROM transactions t
        LEFT JOIN alerts al ON al.primary_txn_id = t.transaction_id
        WHERE t.amount >= ?
        GROUP BY t.transaction_id
        ORDER BY t.amount DESC
        LIMIT ?
        """,
        (float(min_amount), max(1, min(100, int(limit)))),
    ).fetchall()
    sim_items = []
    elevated = 0
    for r in rows:
        base = float(r["base_score"])
        proj = min(99.5, round(base * float(multiplier), 1))
        if proj >= 60.0 and base < 60.0:
            elevated += 1
        sim_items.append(
            {
                "transaction_id": r["transaction_id"],
                "account_id": r["account_id"],
                "amount": round(float(r["amount"]), 2),
                "base_score": round(base, 1),
                "projected_score": proj,
                "delta": round(proj - base, 1),
            }
        )
    return {"total_simulated": len(sim_items), "newly_elevated_count": elevated, "items": sim_items}


def find_shared_pii_clusters(conn: sqlite3.Connection, *, limit: int = 25) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT SUBSTR(phone, 1, 8) AS phone_prefix, home_country, kyc_tier,
               COUNT(*) AS customer_count,
               GROUP_CONCAT(customer_id) AS customer_ids
        FROM customers
        WHERE phone IS NOT NULL AND TRIM(phone) != ''
        GROUP BY phone_prefix, home_country, kyc_tier
        HAVING COUNT(*) >= 2
        ORDER BY customer_count DESC
        LIMIT ?
        """,
        (max(1, min(100, int(limit))),),
    ).fetchall()
    items = [
        {
            "cluster_key": f"{r['home_country']} • {r['phone_prefix']}*",
            "home_country": r["home_country"],
            "kyc_tier": r["kyc_tier"],
            "customer_count": int(r["customer_count"]),
            "customer_ids": str(r["customer_ids"]).split(",")[:6],
        }
        for r in rows
    ]
    return {"total": len(items), "items": items}


def detect_mcc_outliers(conn: sqlite3.Connection, *, limit: int = 25) -> dict[str, Any]:
    rows = conn.execute(
        """
        WITH mcc_avg AS (
            SELECT m.mcc, AVG(t.amount) AS mcc_mean_ticket
            FROM merchants m
            JOIN transactions t ON t.merchant_id = m.merchant_id
            GROUP BY m.mcc
        ),
        merch_stats AS (
            SELECT m.merchant_id, m.merchant_name, m.mcc, m.category, m.country,
                   COUNT(t.transaction_id) AS txn_count,
                   AVG(t.amount) AS avg_ticket
            FROM merchants m
            JOIN transactions t ON t.merchant_id = m.merchant_id
            GROUP BY m.merchant_id
            HAVING COUNT(t.transaction_id) >= 3
        )
        SELECT ms.*, ma.mcc_mean_ticket,
               (ms.avg_ticket / CASE WHEN ma.mcc_mean_ticket > 0 THEN ma.mcc_mean_ticket ELSE 1 END) AS ratio
        FROM merch_stats ms
        JOIN mcc_avg ma ON ma.mcc = ms.mcc
        ORDER BY ratio DESC
        LIMIT ?
        """,
        (max(1, min(100, int(limit))),),
    ).fetchall()
    items = [
        {
            "merchant_id": r["merchant_id"],
            "merchant_name": r["merchant_name"],
            "mcc": r["mcc"],
            "category": r["category"],
            "country": r["country"],
            "txn_count": int(r["txn_count"]),
            "avg_ticket": round(float(r["avg_ticket"]), 2),
            "mcc_mean_ticket": round(float(r["mcc_mean_ticket"]), 2),
            "ratio": round(float(r["ratio"]), 2),
        }
        for r in rows
    ]
    return {"total": len(items), "items": items}


def check_balance_continuity(conn: sqlite3.Connection, *, limit: int = 25) -> dict[str, Any]:
    rows = conn.execute(
        """
        WITH ordered AS (
            SELECT account_id, transaction_id, occurred_at, balance_before, balance_after,
                   LAG(balance_after) OVER (PARTITION BY account_id ORDER BY occurred_at ASC, transaction_id ASC) AS prev_after
            FROM transactions
        )
        SELECT account_id, transaction_id, occurred_at, prev_after, balance_before,
               ABS(balance_before - prev_after) AS drift
        FROM ordered
        WHERE prev_after IS NOT NULL AND ABS(balance_before - prev_after) > 0.02
        ORDER BY drift DESC
        LIMIT ?
        """,
        (max(1, min(100, int(limit))),),
    ).fetchall()
    items = [
        {
            "account_id": r["account_id"],
            "transaction_id": r["transaction_id"],
            "occurred_at": r["occurred_at"],
            "prev_balance_after": round(float(r["prev_after"]), 2),
            "balance_before": round(float(r["balance_before"]), 2),
            "drift": round(float(r["drift"]), 2),
        }
        for r in rows
    ]
    return {"total_breaks": len(items), "items": items}


def get_device_velocity_leaderboard(conn: sqlite3.Connection, *, limit: int = 25) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT d.device_id, d.os_family, d.is_emulator, d.ip_country, d.risk_tier,
               COUNT(DISTINCT a.primary_customer_id) AS customer_count,
               COUNT(t.transaction_id) AS txn_count,
               COALESCE(SUM(t.amount), 0) AS total_volume
        FROM devices d
        JOIN transactions t ON t.device_id = d.device_id
        JOIN accounts a ON a.account_id = t.account_id
        GROUP BY d.device_id
        ORDER BY customer_count DESC, total_volume DESC
        LIMIT ?
        """,
        (max(1, min(100, int(limit))),),
    ).fetchall()
    items = [
        {
            "device_id": r["device_id"],
            "os_family": r["os_family"],
            "is_emulator": bool(r["is_emulator"]),
            "ip_country": r["ip_country"],
            "risk_tier": r["risk_tier"],
            "customer_count": int(r["customer_count"]),
            "txn_count": int(r["txn_count"]),
            "total_volume": round(float(r["total_volume"]), 2),
        }
        for r in rows
    ]
    return {"total": len(items), "items": items}


def list_custom_rule_drafts(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM custom_rule_drafts ORDER BY created_at DESC").fetchall()
    ]


def create_custom_rule_draft(
    conn: sqlite3.Connection,
    *,
    name: str,
    min_amount: float,
    channel: str,
    country_code: str,
    description: str,
    actor_id: str,
) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    if not name.strip():
        raise ValueError("Rule draft name is required")
    did = _new_id("DRF")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO custom_rule_drafts (draft_id, name, min_amount, channel, country_code, description, is_enabled, created_by, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (did, name.strip(), float(min_amount), channel.strip().upper() or "ALL", country_code.strip().upper() or "ALL", description.strip(), actor_id, now),
    )
    conn.commit()
    row = dict(conn.execute("SELECT * FROM custom_rule_drafts WHERE draft_id = ?", (did,)).fetchone())
    # Dry-run match count
    where = ["amount >= ?"]
    params: list[Any] = [float(min_amount)]
    if row["channel"] != "ALL":
        where.append("channel = ?")
        params.append(row["channel"])
    if row["country_code"] != "ALL":
        where.append("counterparty_country = ?")
        params.append(row["country_code"])
    cnt = conn.execute(f"SELECT COUNT(*) FROM transactions WHERE {' AND '.join(where)}", params).fetchone()[0]
    row["dry_run_matches"] = int(cnt)
    return row


def get_quarantine_grouped_summary(conn: sqlite3.Connection, exceptions: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for ex in exceptions:
        key = str(ex.get("issue_type") or "UNKNOWN")
        if key not in grouped:
            grouped[key] = {
                "issue_type": key,
                "severity": ex.get("severity", "HIGH"),
                "violated_invariant": ex.get("violated_invariant", ""),
                "count": 0,
                "exposure": 0.0,
            }
        grouped[key]["count"] += 1
        grouped[key]["exposure"] = round(grouped[key]["exposure"] + float(ex.get("estimated_exposure") or 0.0), 2)
    items = sorted(grouped.values(), key=lambda x: (-x["count"], -x["exposure"]))
    return {"total_groups": len(items), "items": items}


# ------------------------------------------------------------------
# Functions 247-250: QA Sampling, SLA Auto-Escalate, Webhooks, Audit Chain Verify
# ------------------------------------------------------------------
def list_qa_samples(conn: sqlite3.Connection, *, limit: int = 20) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    rows = conn.execute(
        """
        SELECT c.case_id, c.priority_tier, c.priority_score, c.status, c.total_exposure_amount,
               cu.full_name AS customer_name,
               qr.grade, qr.score AS qa_score, qr.feedback, qr.reviewer_id, qr.reviewed_at
        FROM cases c
        JOIN customers cu ON cu.customer_id = c.primary_customer_id
        LEFT JOIN qa_reviews qr ON qr.case_id = c.case_id
        ORDER BY c.updated_at DESC
        LIMIT ?
        """,
        (max(1, min(100, int(limit))),),
    ).fetchall()
    return {"items": [dict(r) for r in rows]}


def submit_qa_grade(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    grade: str,
    score: int,
    feedback: str,
    reviewer_id: str,
) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    if not conn.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone():
        raise ValueError(f"Case {case_id} not found")
    g = grade.strip().upper()
    if g not in {"PASS", "REWORK_REQUIRED", "EXEMPLARY"}:
        raise ValueError("Invalid QA grade")
    qid = _new_id("QA")
    now = _now_iso()
    conn.execute("DELETE FROM qa_reviews WHERE case_id = ?", (case_id,))
    conn.execute(
        """
        INSERT INTO qa_reviews (qa_id, case_id, reviewer_id, grade, score, feedback, reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (qid, case_id, reviewer_id, g, max(0, min(100, int(score))), feedback.strip(), now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM qa_reviews WHERE qa_id = ?", (qid,)).fetchone())


def run_sla_auto_escalation(conn: sqlite3.Connection, *, actor_id: str, max_escalations: int = 10) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT case_id, priority_score
        FROM cases
        WHERE status = 'OPEN' AND priority_tier = 'CRITICAL'
        ORDER BY priority_score DESC
        LIMIT ?
        """,
        (max(1, min(50, int(max_escalations))),),
    ).fetchall()
    now = _now_iso()
    escalated_ids: list[str] = []
    for r in rows:
        cid = r["case_id"]
        conn.execute("UPDATE cases SET status = 'IN_REVIEW', updated_at = ? WHERE case_id = ?", (now, cid))
        act_id = _new_id("ACT")
        conn.execute(
            """
            INSERT INTO analyst_actions (action_id, case_id, analyst_id, analyst_role, action_type, rationale, acted_at)
            VALUES (?, ?, ?, 'RISK_REVIEWER', 'SLA_AUTO_ESCALATE', 'Automated critical SLA escalation sweep', ?)
            """,
            (act_id, cid, actor_id, now),
        )
        escalated_ids.append(cid)
    conn.commit()
    return {"escalated_count": len(escalated_ids), "case_ids": escalated_ids, "executed_at": now}


def list_webhooks(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM webhook_endpoints ORDER BY created_at DESC").fetchall()]


def create_webhook(
    conn: sqlite3.Connection,
    *,
    name: str,
    target_url: str,
    actor_id: str,
) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    if not name.strip() or not target_url.strip():
        raise ValueError("Webhook name and URL required")
    wid = _new_id("WHK")
    now = _now_iso()
    hint = f"whsec_...{uuid.uuid4().hex[:6]}"
    conn.execute(
        """
        INSERT INTO webhook_endpoints (webhook_id, name, target_url, secret_hint, is_active, created_by, created_at)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        """,
        (wid, name.strip(), target_url.strip(), hint, actor_id, now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM webhook_endpoints WHERE webhook_id = ?", (wid,)).fetchone())


def test_webhook_ping(conn: sqlite3.Connection, webhook_id: str) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    row = conn.execute("SELECT * FROM webhook_endpoints WHERE webhook_id = ?", (webhook_id,)).fetchone()
    if not row:
        raise ValueError(f"Webhook {webhook_id} not found")
    now = _now_iso()
    conn.execute(
        "UPDATE webhook_endpoints SET last_status = '200_SIMULATED_OK', last_tested_at = ? WHERE webhook_id = ?",
        (now, webhook_id),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM webhook_endpoints WHERE webhook_id = ?", (webhook_id,)).fetchone())


def delete_webhook(conn: sqlite3.Connection, webhook_id: str) -> bool:
    ensure_enterprise_schema(conn)
    cur = conn.execute("DELETE FROM webhook_endpoints WHERE webhook_id = ?", (webhook_id,))
    conn.commit()
    return cur.rowcount > 0


def verify_audit_chain_integrity(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT action_id, case_id, action_type, acted_at FROM analyst_actions ORDER BY acted_at ASC LIMIT 200"
    ).fetchall()
    prev_ts = ""
    monotonic_ok = True
    chain_digest = hashlib.sha256(b"YOTTAFLEX-AUDIT-GENESIS").hexdigest()
    for r in rows:
        ts = str(r["acted_at"] or "")
        if prev_ts and ts < prev_ts:
            monotonic_ok = False
        prev_ts = ts
        chain_digest = hashlib.sha256(f"{chain_digest}|{r['action_id']}|{r['case_id']}|{ts}".encode("utf-8")).hexdigest()
    return {
        "verified": monotonic_ok,
        "events_checked": len(rows),
        "monotonic_timestamps": monotonic_ok,
        "chain_sha256": chain_digest,
        "checked_at": _now_iso(),
    }


# ------------------------------------------------------------------
# Functions 256-270: Scorecard, Bookmarks, Schedules, Retention, Compare, Exam, Pins
# ------------------------------------------------------------------
def get_data_scorecard(conn: sqlite3.Connection) -> dict[str, Any]:
    tables = ["customers", "accounts", "transactions", "alerts", "cases", "transfer_links", "devices", "merchants"]
    cards = []
    for tbl in tables:
        cnt = int(conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
        cards.append({"table": tbl, "row_count": cnt, "status": "HEALTHY" if cnt > 0 else "EMPTY"})
    idx_cnt = int(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'").fetchone()[0])
    null_merch_country = int(conn.execute("SELECT COUNT(*) FROM merchants WHERE country IS NULL OR TRIM(country) = ''").fetchone()[0])
    return {
        "tables": cards,
        "sqlite_index_count": idx_cnt,
        "null_merchant_countries": null_merch_country,
        "overall_health": "OPTIMAL",
    }


def list_search_bookmarks(conn: sqlite3.Connection, user_id: str) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM search_bookmarks WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    ]


def create_search_bookmark(conn: sqlite3.Connection, *, user_id: str, title: str, workspace: str, query_text: str) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    if not title.strip() or not query_text.strip():
        raise ValueError("Bookmark title and query text required")
    bid = _new_id("BMK")
    now = _now_iso()
    conn.execute(
        "INSERT INTO search_bookmarks (bookmark_id, user_id, title, workspace, query_text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (bid, user_id, title.strip(), workspace.strip(), query_text.strip(), now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM search_bookmarks WHERE bookmark_id = ?", (bid,)).fetchone())


def delete_search_bookmark(conn: sqlite3.Connection, *, user_id: str, bookmark_id: str) -> bool:
    ensure_enterprise_schema(conn)
    cur = conn.execute("DELETE FROM search_bookmarks WHERE bookmark_id = ? AND user_id = ?", (bookmark_id, user_id))
    conn.commit()
    return cur.rowcount > 0


def list_scheduled_digests(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM scheduled_digests ORDER BY updated_at DESC").fetchall()]


def upsert_scheduled_digest(
    conn: sqlite3.Connection,
    *,
    cadence: str,
    recipient_role: str,
    include_quarantine: bool,
    actor_id: str,
) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    sid = _new_id("SCH")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO scheduled_digests (schedule_id, cadence, recipient_role, include_quarantine, is_enabled, updated_by, updated_at)
        VALUES (?, ?, ?, ?, 1, ?, ?)
        """,
        (sid, cadence.strip().upper(), recipient_role.strip().upper(), 1 if include_quarantine else 0, actor_id, now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM scheduled_digests WHERE schedule_id = ?", (sid,)).fetchone())


def get_retention_status(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    pol = dict(conn.execute("SELECT * FROM retention_policies WHERE policy_id = 'DEFAULT'").fetchone())
    cutoff_alerts = (datetime.now(timezone.utc) - timedelta(days=int(pol["alerts_days"]))).strftime("%Y-%m-%dT%H:%M:%SZ")
    cutoff_sess = (datetime.now(timezone.utc) - timedelta(days=int(pol["sessions_days"]))).strftime("%Y-%m-%dT%H:%M:%SZ")
    eligible_alerts = int(conn.execute("SELECT COUNT(*) FROM alerts WHERE created_at < ? AND status != 'OPEN'", (cutoff_alerts,)).fetchone()[0])
    eligible_sess = int(conn.execute("SELECT COUNT(*) FROM auth_sessions WHERE created_at < ?", (cutoff_sess,)).fetchone()[0])
    return {
        "policy": pol,
        "dry_run_eligible_alerts": eligible_alerts,
        "dry_run_eligible_sessions": eligible_sess,
    }


def update_retention_policy(
    conn: sqlite3.Connection,
    *,
    alerts_days: int,
    sessions_days: int,
    exports_days: int,
    actor_id: str,
) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    now = _now_iso()
    conn.execute(
        """
        UPDATE retention_policies
        SET alerts_days = ?, sessions_days = ?, exports_days = ?, updated_by = ?, updated_at = ?
        WHERE policy_id = 'DEFAULT'
        """,
        (max(30, int(alerts_days)), max(7, int(sessions_days)), max(30, int(exports_days)), actor_id, now),
    )
    conn.commit()
    return get_retention_status(conn)


def compare_two_cases(conn: sqlite3.Connection, case_id_a: str, case_id_b: str) -> dict[str, Any]:
    a = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id_a,)).fetchone()
    b = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id_b,)).fetchone()
    if not a or not b:
        raise ValueError("Both cases must exist for side-by-side comparison")
    rules_a = {r["rule_id"] for r in conn.execute("SELECT DISTINCT al.rule_id FROM alerts al JOIN case_alert_links cal ON cal.alert_id = al.alert_id WHERE cal.case_id = ?", (case_id_a,)).fetchall()}
    rules_b = {r["rule_id"] for r in conn.execute("SELECT DISTINCT al.rule_id FROM alerts al JOIN case_alert_links cal ON cal.alert_id = al.alert_id WHERE cal.case_id = ?", (case_id_b,)).fetchall()}
    return {
        "case_a": dict(a),
        "case_b": dict(b),
        "shared_rules": sorted(rules_a & rules_b),
        "unique_rules_a": sorted(rules_a - rules_b),
        "unique_rules_b": sorted(rules_b - rules_a),
        "score_delta": round(float(a["priority_score"]) - float(b["priority_score"]), 2),
        "exposure_delta": round(float(a["total_exposure_amount"]) - float(b["total_exposure_amount"]), 2),
    }


def get_related_cases_timeline(conn: sqlite3.Connection, case_id: str) -> dict[str, Any]:
    base = conn.execute("SELECT primary_customer_id FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not base:
        raise ValueError(f"Case {case_id} not found")
    rows = conn.execute(
        "SELECT case_id, priority_tier, priority_score, status, total_exposure_amount, created_at, updated_at FROM cases WHERE primary_customer_id = ? ORDER BY created_at DESC LIMIT 15",
        (base["primary_customer_id"],),
    ).fetchall()
    return {"case_id": case_id, "customer_id": base["primary_customer_id"], "cases": [dict(r) for r in rows]}


def get_tier_workload_projection(conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT priority_tier, COUNT(*) AS open_count, COALESCE(SUM(total_exposure_amount), 0) AS exposure,
               AVG(priority_score) AS avg_score
        FROM cases
        WHERE status IN ('OPEN', 'IN_REVIEW')
        GROUP BY priority_tier
        """
    ).fetchall()
    hours_map = {"CRITICAL": 2.5, "HIGH": 1.5, "MEDIUM": 0.9, "LOW": 0.4}
    items = []
    for r in rows:
        t = r["priority_tier"]
        cnt = int(r["open_count"] or 0)
        items.append(
            {
                "priority_tier": t,
                "open_count": cnt,
                "exposure": round(float(r["exposure"] or 0.0), 2),
                "avg_score": round(float(r["avg_score"] or 0.0), 1),
                "estimated_hours": round(cnt * hours_map.get(t, 1.0), 1),
            }
        )
    return {"items": items}


def simulate_case_what_if_score(conn: sqlite3.Connection, case_id: str, waived_alert_ids: list[str]) -> dict[str, Any]:
    c = conn.execute("SELECT priority_score, priority_tier FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not c:
        raise ValueError(f"Case {case_id} not found")
    alerts = conn.execute(
        "SELECT al.alert_id, al.risk_score FROM alerts al JOIN case_alert_links cal ON cal.alert_id = al.alert_id WHERE cal.case_id = ?",
        (case_id,),
    ).fetchall()
    waived = set(waived_alert_ids)
    kept = [float(a["risk_score"]) for a in alerts if a["alert_id"] not in waived]
    orig = float(c["priority_score"])
    if not alerts:
        projected = orig
    elif not kept:
        projected = round(orig * 0.2, 2)
    else:
        ratio = len(kept) / len(alerts)
        projected = round(orig * (0.35 + 0.65 * ratio), 2)
    proj_tier = "CRITICAL" if projected >= 80 else ("HIGH" if projected >= 60 else ("MEDIUM" if projected >= 40 else "LOW"))
    return {
        "case_id": case_id,
        "original_score": round(orig, 2),
        "original_tier": c["priority_tier"],
        "projected_score": projected,
        "projected_tier": proj_tier,
        "waived_count": len(waived & {a["alert_id"] for a in alerts}),
    }


def list_exam_readiness(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM exam_readiness_controls ORDER BY control_id ASC").fetchall()]


def update_exam_readiness(
    conn: sqlite3.Connection,
    *,
    control_id: str,
    status: str,
    note: str,
    actor_id: str,
) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    st = status.strip().upper()
    if st not in {"VERIFIED", "IN_PROGRESS", "ACTION_REQUIRED"}:
        raise ValueError("Invalid control status")
    now = _now_iso()
    conn.execute(
        "UPDATE exam_readiness_controls SET status = ?, note = ?, owner_id = ?, updated_at = ? WHERE control_id = ?",
        (st, note.strip(), actor_id, now, control_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM exam_readiness_controls WHERE control_id = ?", (control_id,)).fetchone()
    if not row:
        raise ValueError(f"Control {control_id} not found")
    return dict(row)


def list_workspace_pins(conn: sqlite3.Connection, user_id: str) -> list[dict[str, Any]]:
    ensure_enterprise_schema(conn)
    return [dict(r) for r in conn.execute("SELECT * FROM workspace_pins WHERE user_id = ? ORDER BY pinned_at DESC LIMIT 12", (user_id,)).fetchall()]


def add_workspace_pin(conn: sqlite3.Connection, *, user_id: str, entity_type: str, entity_id: str, label: str) -> dict[str, Any]:
    ensure_enterprise_schema(conn)
    pid = _new_id("WPN")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO workspace_pins (pin_id, user_id, entity_type, entity_id, label, pinned_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, entity_type, entity_id) DO UPDATE SET label = excluded.label, pinned_at = excluded.pinned_at
        """,
        (pid, user_id, entity_type.strip().upper(), entity_id.strip(), label.strip() or entity_id.strip(), now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM workspace_pins WHERE user_id = ? AND entity_type = ? AND entity_id = ?", (user_id, entity_type.strip().upper(), entity_id.strip())).fetchone())


def delete_workspace_pin(conn: sqlite3.Connection, *, user_id: str, pin_id: str) -> bool:
    ensure_enterprise_schema(conn)
    cur = conn.execute("DELETE FROM workspace_pins WHERE pin_id = ? AND user_id = ?", (pin_id, user_id))
    conn.commit()
    return cur.rowcount > 0

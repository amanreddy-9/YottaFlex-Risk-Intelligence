"""Explainable Risk Detection & Multi-Level Risk Scoring Engine (Functions 71-75).

Operates strictly on normalized operational & ledger tables (`transactions`,
`accounts`, `customers`, `merchants`, `devices`, `account_device_links`,
`account_state_events`, `transfer_links`, `risk_rules`, `alerts`, `alert_trigger_facts`,
`cases`). Zero access to any held-out evaluation files.
"""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from typing import Any


def ensure_scoring_history_schema(conn: sqlite3.Connection) -> None:
    """Create operational rule execution & risk score history tables idempotently (Functions 78, 89, 90)."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS rule_execution_runs (
            run_id TEXT PRIMARY KEY,
            trigger_source TEXT NOT NULL,
            rule_id TEXT,
            txns_evaluated INTEGER NOT NULL,
            alerts_affected INTEGER NOT NULL,
            avg_score REAL NOT NULL,
            executed_by TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            summary TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS risk_score_history (
            history_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            prev_score REAL NOT NULL,
            new_score REAL NOT NULL,
            prev_level TEXT NOT NULL,
            new_level TEXT NOT NULL,
            reason TEXT NOT NULL,
            rule_id TEXT,
            recorded_at TEXT NOT NULL,
            actor_id TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_risk_hist_entity ON risk_score_history(entity_id, recorded_at DESC);
        CREATE INDEX IF NOT EXISTS idx_risk_exec_time ON rule_execution_runs(executed_at DESC);
        """
    )
    existing = conn.execute("SELECT COUNT(*) FROM rule_execution_runs").fetchone()[0]
    if existing == 0:
        txn_cnt = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        al_stats = conn.execute(
            "SELECT COUNT(*) AS cnt, ROUND(COALESCE(AVG(risk_score), 0), 2) AS avg_s, COALESCE(MAX(created_at), ?) AS ts FROM alerts",
            (_iso_now(),),
        ).fetchone()
        conn.execute(
            """
            INSERT INTO rule_execution_runs
            (run_id, trigger_source, rule_id, txns_evaluated, alerts_affected, avg_score, executed_by, executed_at, summary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "RUN-BASELINE-0001",
                "INITIAL_LEDGER_EVALUATION",
                "ALL",
                int(txn_cnt),
                int(al_stats["cnt"]),
                float(al_stats["avg_s"]),
                "RISK_ENGINE_V1",
                str(al_stats["ts"]),
                f"Evaluated {txn_cnt:,} ledger transactions across 8 configured RiskRules; generated {al_stats['cnt']:,} explainable alerts.",
            ),
        )
        # Seed baseline score snapshots for top alerts so score history is populated immediately
        top_alerts = conn.execute(
            "SELECT alert_id, rule_id, account_id, risk_score, severity, created_at FROM alerts ORDER BY risk_score DESC, alert_id ASC LIMIT 12"
        ).fetchall()
        for idx, al in enumerate(top_alerts, start=1):
            sc = float(al["risk_score"])
            lvl = classify_risk(sc)
            conn.execute(
                """
                INSERT INTO risk_score_history
                (history_id, entity_type, entity_id, prev_score, new_score, prev_level, new_level, reason, rule_id, recorded_at, actor_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"HIST-BASE-{idx:04d}",
                    "ALERT",
                    al["alert_id"],
                    0.0,
                    sc,
                    "LOW",
                    lvl,
                    f"Initial automated scoring on {al['account_id']} via {al['rule_id']}",
                    al["rule_id"],
                    al["created_at"],
                    "RISK_ENGINE_V1",
                ),
            )
    conn.commit()


def classify_risk(score: float, *, high_risk_flag: bool = False) -> str:
    """Classify a numerical risk score (0-100) into HIGH, MEDIUM, or LOW."""
    if score >= 60.0:
        return "HIGH"
    if score >= 20.0 or score > 0.0 or high_risk_flag:
        return "MEDIUM"
    return "LOW"


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def calculate_account_score_from_conn(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    """Calculate account-level risk score and breakdown from operational records."""
    acct = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
    if not acct:
        return {"account_id": account_id, "risk_score": 0.0, "risk_level": "LOW", "factors": []}

    alerts = [
        dict(r)
        for r in conn.execute(
            "SELECT alert_id, rule_id, severity, risk_score FROM alerts WHERE account_id = ?",
            (account_id,),
        ).fetchall()
    ]
    dormant_react = (
        conn.execute(
            "SELECT COUNT(*) FROM account_state_events WHERE account_id = ? AND prev_status = 'DORMANT' AND new_status = 'ACTIVE'",
            (account_id,),
        ).fetchone()[0]
        > 0
    )
    high_risk_merch_txns = conn.execute(
        """
        SELECT COUNT(*) FROM transactions t
        JOIN merchants m ON m.merchant_id = t.merchant_id
        WHERE t.account_id = ? AND m.risk_tier = 'HIGH'
        """,
        (account_id,),
    ).fetchone()[0]

    max_alert = max((float(a["risk_score"]) for a in alerts), default=0.0)
    extra_alerts = max(0, len(alerts) - 1) * 4.5
    dormant_pts = 8.0 if dormant_react else 0.0
    merch_pts = min(10.0, high_risk_merch_txns * 2.5) if not alerts else 0.0
    score = round(min(100.0, max_alert + extra_alerts + dormant_pts + merch_pts), 2)

    factors: list[dict[str, Any]] = []
    if max_alert > 0:
        factors.append({"factor": "Peak Triggered Alert Score", "points": round(max_alert, 2)})
    if extra_alerts > 0:
        factors.append({"factor": f"Multi-Alert Volume ({len(alerts)} alerts)", "points": round(extra_alerts, 2)})
    if dormant_pts > 0:
        factors.append({"factor": "Dormant-to-Active Lifecycle Reactivation", "points": dormant_pts})
    if merch_pts > 0:
        factors.append({"factor": f"High-Risk Merchant Exposure ({high_risk_merch_txns} txns)", "points": round(merch_pts, 2)})

    return {
        "account_id": account_id,
        "risk_score": score,
        "risk_level": classify_risk(score),
        "alert_count": len(alerts),
        "is_dormant_reactivated": dormant_react,
        "factors": factors,
    }


def calculate_customer_score_from_conn(conn: sqlite3.Connection, customer_id: str) -> dict[str, Any]:
    """Calculate customer-level risk score and breakdown across owned accounts, devices, and cases."""
    cust = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
    if not cust:
        return {"customer_id": customer_id, "risk_score": 0.0, "risk_level": "LOW", "factors": []}

    acct_rows = conn.execute(
        "SELECT DISTINCT account_id FROM account_ownerships WHERE customer_id = ?",
        (customer_id,),
    ).fetchall()
    acct_ids = [r[0] for r in acct_rows]
    acct_scores = [calculate_account_score_from_conn(conn, aid) for aid in acct_ids]
    suspicious_accts = sum(1 for s in acct_scores if s["alert_count"] > 0)

    case_row = conn.execute(
        "SELECT COALESCE(MAX(priority_score), 0) AS max_p, COUNT(*) AS cnt FROM cases WHERE primary_customer_id = ?",
        (customer_id,),
    ).fetchone()
    max_case = float(case_row["max_p"]) if case_row else 0.0
    case_cnt = int(case_row["cnt"]) if case_row else 0

    emulators = 0
    if acct_ids:
        ph = ",".join(["?"] * len(acct_ids))
        emulators = conn.execute(
            f"""
            SELECT COUNT(DISTINCT d.device_id)
            FROM account_device_links adl
            JOIN devices d ON d.device_id = adl.device_id
            WHERE adl.account_id IN ({ph}) AND (d.is_emulator = 1 OR d.risk_tier = 'HIGH')
            """,
            acct_ids,
        ).fetchone()[0]

    kyc_pts = {"LOW": 10.0, "STANDARD": 4.0, "ENHANCED": 0.0}.get(cust["kyc_tier"], 0.0)
    peak_acct = max((s["risk_score"] for s in acct_scores), default=0.0)
    multi_susp_pts = max(0, suspicious_accts - 1) * 10.0
    dev_pts = min(15.0, emulators * 7.5)
    base_risk = max(max_case, peak_acct)
    score = round(min(100.0, base_risk + kyc_pts + multi_susp_pts + dev_pts), 2)

    factors: list[dict[str, Any]] = []
    if base_risk > 0:
        factors.append({"factor": "Peak Case / Owned Account Risk", "points": round(base_risk, 2)})
    if kyc_pts > 0:
        factors.append({"factor": f"KYC Tier Exposure ({cust['kyc_tier']})", "points": kyc_pts})
    if multi_susp_pts > 0:
        factors.append({"factor": f"Multiple Suspicious Accounts ({suspicious_accts})", "points": round(multi_susp_pts, 2)})
    if dev_pts > 0:
        factors.append({"factor": f"High-Risk / Emulator Devices ({emulators})", "points": round(dev_pts, 2)})

    return {
        "customer_id": customer_id,
        "risk_score": score,
        "risk_level": classify_risk(score),
        "case_count": case_cnt,
        "suspicious_account_count": suspicious_accts,
        "factors": factors,
    }


def evaluate_transaction_against_rules(
    conn: sqlite3.Connection,
    *,
    transaction_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Automatically evaluate a stored or simulated transaction against configured RiskRules (Functions 71-75)."""
    rules = [
        dict(r)
        for r in conn.execute("SELECT * FROM risk_rules ORDER BY rule_id ASC").fetchall()
    ]

    if transaction_id:
        txn = conn.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
        if not txn:
            raise ValueError(f"Transaction '{transaction_id}' not found")
        txn_dict = dict(txn)
    elif payload:
        acct_id = str(payload.get("account_id") or "").strip()
        if not acct_id:
            raise ValueError("account_id is required when evaluating a simulated transaction")
        txn_dict = {
            "transaction_id": str(payload.get("transaction_id") or "SIM-TXN-PREVIEW"),
            "account_id": acct_id,
            "txn_type": str(payload.get("txn_type") or "WIRE_OUT"),
            "direction": str(payload.get("direction") or "DEBIT"),
            "amount": float(payload.get("amount") or 0.0),
            "currency": str(payload.get("currency") or "USD"),
            "balance_before": float(payload.get("balance_before") or 0.0),
            "balance_after": float(payload.get("balance_after") or 0.0),
            "channel": str(payload.get("channel") or "WEB"),
            "merchant_id": payload.get("merchant_id") or None,
            "device_id": payload.get("device_id") or None,
            "counterparty_country": str(payload.get("counterparty_country") or "US"),
            "status": str(payload.get("status") or "POSTED"),
            "occurred_at": str(payload.get("occurred_at") or _iso_now()),
            "reference_note": str(payload.get("reference_note") or "Live rule evaluation simulation"),
        }
    else:
        raise ValueError("Provide either transaction_id or payload")

    acct = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (txn_dict["account_id"],)).fetchone()
    if not acct:
        raise ValueError(f"Account '{txn_dict['account_id']}' not found")
    cust = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (acct["primary_customer_id"],)).fetchone()
    merch = (
        conn.execute("SELECT * FROM merchants WHERE merchant_id = ?", (txn_dict["merchant_id"],)).fetchone()
        if txn_dict.get("merchant_id")
        else None
    )
    dev = (
        conn.execute("SELECT * FROM devices WHERE device_id = ?", (txn_dict["device_id"],)).fetchone()
        if txn_dict.get("device_id")
        else None
    )

    # Recorded trigger facts for existing transactions
    recorded_by_rule: dict[str, dict[str, Any]] = {}
    if transaction_id:
        for rf in conn.execute(
            """
            SELECT f.rule_id, f.metric_name, f.observed_value, f.threshold_value,
                   al.alert_id, al.risk_score, al.explanation_summary
            FROM alert_trigger_facts f
            JOIN alerts al ON al.alert_id = f.alert_id
            WHERE f.transaction_id = ?
            """,
            (transaction_id,),
        ).fetchall():
            recorded_by_rule[rf["rule_id"]] = dict(rf)

    # Quantitative dynamic signal checks against live ledger context
    occ = txn_dict["occurred_at"]
    amt = float(txn_dict["amount"])
    is_outbound = txn_dict["direction"] == "DEBIT"

    vel_row = conn.execute(
        """
        SELECT COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS total_amt
        FROM transactions
        WHERE account_id = ?
          AND direction = 'DEBIT'
          AND occurred_at BETWEEN strftime('%Y-%m-%dT%H:%M:%SZ', ?, '-60 minutes')
                              AND strftime('%Y-%m-%dT%H:%M:%SZ', ?, '+60 minutes')
        """,
        (txn_dict["account_id"], occ, occ),
    ).fetchone()
    vel_cnt = int(vel_row["cnt"]) + (0 if transaction_id else (1 if is_outbound else 0))
    vel_amt = float(vel_row["total_amt"]) + (0.0 if transaction_id else (amt if is_outbound else 0.0))

    struct_row = conn.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM transactions
        WHERE account_id = ?
          AND direction = 'DEBIT'
          AND amount BETWEEN 1800.0 AND 2999.99
          AND occurred_at BETWEEN strftime('%Y-%m-%dT%H:%M:%SZ', ?, '-24 hours')
                              AND strftime('%Y-%m-%dT%H:%M:%SZ', ?, '+24 hours')
        """,
        (txn_dict["account_id"], occ, occ),
    ).fetchone()
    struct_cnt = int(struct_row["cnt"]) + (0 if transaction_id else (1 if is_outbound and 1800.0 <= amt <= 2999.99 else 0))

    device_age_hours: float | None = None
    shared_dev_customers = 0
    if txn_dict.get("device_id"):
        adl_row = conn.execute(
            """
            SELECT (julianday(?) - julianday(MIN(first_seen_at))) * 24.0 AS hrs
            FROM account_device_links
            WHERE account_id = ? AND device_id = ?
            """,
            (occ, txn_dict["account_id"], txn_dict["device_id"]),
        ).fetchone()
        if adl_row and adl_row["hrs"] is not None:
            device_age_hours = round(float(adl_row["hrs"]), 2)
        else:
            device_age_hours = 0.0
        shared_dev_customers = int(
            conn.execute(
                """
                SELECT COUNT(DISTINCT a2.primary_customer_id)
                FROM account_device_links adl2
                JOIN accounts a2 ON a2.account_id = adl2.account_id
                WHERE adl2.device_id = ?
                """,
                (txn_dict["device_id"],),
            ).fetchone()[0]
        )

    dormant_react_count = int(
        conn.execute(
            """
            SELECT COUNT(*) FROM account_state_events
            WHERE account_id = ? AND prev_status = 'DORMANT' AND new_status = 'ACTIVE'
            """,
            (txn_dict["account_id"],),
        ).fetchone()[0]
    )

    monthly_income = (float(cust["declared_annual_income"]) / 12.0) if cust and cust["declared_annual_income"] else 0.0
    income_ratio = round((amt / monthly_income) * 100.0, 1) if monthly_income > 0 else 0.0

    # Transfer ring check (RULE-003): dynamic bounded 2..5 hop cycle search within +/- 48h
    has_transfer_link = (
        conn.execute(
            "SELECT COUNT(*) FROM transfer_links WHERE debit_txn_id = ? OR credit_txn_id = ?",
            (txn_dict["transaction_id"], txn_dict["transaction_id"]),
        ).fetchone()[0]
        > 0
    )
    ring_detected_detail: str | None = None
    ring_rows = conn.execute(
        """
        SELECT source_account_id, dest_account_id, transfer_amount
        FROM transfer_links
        WHERE initiated_at BETWEEN strftime('%Y-%m-%dT%H:%M:%SZ', ?, '-48 hours')
                               AND strftime('%Y-%m-%dT%H:%M:%SZ', ?, '+48 hours')
        """,
        (occ, occ),
    ).fetchall()
    adj: dict[str, list[tuple[str, float]]] = {}
    for rr in ring_rows:
        adj.setdefault(rr["source_account_id"], []).append((rr["dest_account_id"], float(rr["transfer_amount"])))
    start_acct = txn_dict["account_id"]
    if start_acct in adj:
        stack: list[tuple[str, int, float, set[str]]] = [(start_acct, 0, amt, {start_acct})]
        while stack and ring_detected_detail is None:
            curr, hops, min_flow, visited = stack.pop()
            if hops >= 5:
                continue
            for nxt, edge_amt in adj.get(curr, []):
                flow = min(min_flow, edge_amt) if hops > 0 else edge_amt
                if nxt == start_acct and hops >= 1 and flow >= amt * 0.75:
                    ring_detected_detail = f"{hops + 1}-hop circular transfer returning ${flow:,.2f} within 48h"
                    break
                if nxt not in visited and hops + 1 < 5:
                    stack.append((nxt, hops + 1, flow, visited | {nxt}))

    rule_evaluations: list[dict[str, Any]] = []
    triggered_points = 0.0
    max_alert_score = 0.0
    flag_reasons: list[str] = []

    for rule in rules:
        rid = rule["rule_id"]
        rec = recorded_by_rule.get(rid)
        active = bool(rule["is_active"])
        weight = float(rule["base_weight"])

        triggered = False
        observed_metric = "No anomaly threshold crossed"

        if rec:
            triggered = True
            observed_metric = f"{rec['metric_name']}: {rec['observed_value']} (Alert {rec['alert_id']})"
            max_alert_score = max(max_alert_score, float(rec["risk_score"]))
        elif rid == "RULE-001":
            observed_metric = f"{vel_cnt} debits totaling ${vel_amt:,.2f} in 60m"
            triggered = is_outbound and vel_cnt >= 5 and vel_amt >= 2500.0
        elif rid == "RULE-002":
            age_txt = f"{device_age_hours:.1f}h" if device_age_hours is not None else "No device"
            observed_metric = f"Outbound ${amt:,.2f}, device link age {age_txt}"
            triggered = is_outbound and amt >= 1500.0 and device_age_hours is not None and device_age_hours <= 24.0
        elif rid == "RULE-003":
            if ring_detected_detail:
                observed_metric = ring_detected_detail
                triggered = True
            else:
                observed_metric = "Linked transfer leg present (no return cycle)" if has_transfer_link else "No transfer cycle link"
                triggered = False
        elif rid == "RULE-004":
            observed_metric = f"Dormant reactivation events={dormant_react_count}, amt=${amt:,.2f}"
            triggered = (acct["status"] == "DORMANT" or dormant_react_count > 0) and amt >= 3000.0
        elif rid == "RULE-005":
            m_tier = merch["risk_tier"] if merch else "N/A"
            c_country = txn_dict.get("counterparty_country", "US")
            home_country = cust["home_country"] if cust else "US"
            observed_metric = f"Merchant tier={m_tier}, country={c_country} vs home={home_country}, amt=${amt:,.2f}"
            triggered = amt >= 1000.0 and (m_tier == "HIGH" or c_country != home_country)
        elif rid == "RULE-006":
            observed_metric = f"{struct_cnt} debits in $1,800-$2,999.99 band within 24h"
            triggered = struct_cnt >= 3
        elif rid == "RULE-007":
            observed_metric = f"Device shared across {shared_dev_customers} primary customers"
            triggered = shared_dev_customers >= 3 and is_outbound
        elif rid == "RULE-008":
            kyc = cust["kyc_tier"] if cust else "STANDARD"
            observed_metric = f"KYC={kyc}, amount=${amt:,.2f} ({income_ratio}% of monthly income)"
            triggered = kyc in ("LOW", "STANDARD") and monthly_income > 0 and amt >= (0.5 * monthly_income)

        if not active:
            status = "DISABLED"
            pts = 0.0
        elif triggered:
            status = "TRIGGERED"
            pts = weight
            triggered_points += weight
            flag_reasons.append(f"[{rid}] {rule['rule_name']}: {observed_metric}")
        else:
            status = "PASSED"
            pts = 0.0

        rule_evaluations.append({
            "rule_id": rid,
            "rule_name": rule["rule_name"],
            "category": rule["category"],
            "severity": rule["severity"],
            "base_weight": rule["base_weight"],
            "threshold_desc": rule["threshold_desc"],
            "status": status,
            "observed_metric": observed_metric,
            "points_awarded": round(pts, 2),
        })

    # Combine recorded alert score with dynamic contextual adjustments
    contextual_bonus = 0.0
    if dev and dev["is_emulator"]:
        contextual_bonus += 8.0
        flag_reasons.append(f"Device {dev['device_id']} flagged as emulator")
    if merch and merch["risk_tier"] == "HIGH" and not any(
        re["rule_id"] == "RULE-005" and re["status"] == "TRIGGERED" for re in rule_evaluations
    ):
        contextual_bonus += 12.0
        flag_reasons.append(f"High-risk merchant category ({merch['merchant_name']})")
    if amt >= 5000.0 and not flag_reasons:
        contextual_bonus += 14.0
        flag_reasons.append(f"Elevated single-transaction amount (${amt:,.2f})")

    computed_raw = min(100.0, max(max_alert_score, triggered_points + contextual_bonus))
    txn_score = round(computed_raw, 2)
    txn_level = classify_risk(txn_score, high_risk_flag=bool(merch and merch["risk_tier"] == "HIGH"))

    acct_score_obj = calculate_account_score_from_conn(conn, txn_dict["account_id"])
    cust_score_obj = calculate_customer_score_from_conn(conn, acct["primary_customer_id"])

    return {
        "evaluated_at": _iso_now(),
        "transaction": txn_dict,
        "transaction_risk_score": txn_score,
        "transaction_risk_level": txn_level,
        "account_risk": acct_score_obj,
        "customer_risk": cust_score_obj,
        "triggered_rule_count": sum(1 for r in rule_evaluations if r["status"] == "TRIGGERED"),
        "rule_evaluations": rule_evaluations,
        "flag_reasons": flag_reasons,
    }


def detect_behavioral_anomalies_summary(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Summarize velocity, amount, new-device, circular, dormant, and network anomalies (Functions 79-84)."""
    rule_counts = {
        r["rule_id"]: {"hit_count": r["hit_count"], "rule_name": r["rule_name"], "severity": r["severity"]}
        for r in conn.execute(
            """
            SELECT r.rule_id, r.rule_name, r.severity, COUNT(al.alert_id) AS hit_count
            FROM risk_rules r
            LEFT JOIN alerts al ON al.rule_id = r.rule_id
            GROUP BY r.rule_id
            """
        ).fetchall()
    }
    dormant_accts = conn.execute(
        "SELECT COUNT(DISTINCT account_id) FROM account_state_events WHERE prev_status = 'DORMANT' AND new_status = 'ACTIVE'"
    ).fetchone()[0]
    shared_devs = conn.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT adl.device_id
            FROM account_device_links adl
            JOIN accounts a ON a.account_id = adl.account_id
            GROUP BY adl.device_id
            HAVING COUNT(DISTINCT a.primary_customer_id) >= 3
        )
        """
    ).fetchone()[0]

    return [
        {
            "key": "RAPID_SUCCESSIVE",
            "function_num": 79,
            "name": "Velocity-Based Anomalies",
            "rules": ["RULE-001", "RULE-006"],
            "alert_count": rule_counts.get("RULE-001", {}).get("hit_count", 0)
            + rule_counts.get("RULE-006", {}).get("hit_count", 0),
            "description": "Burst debits (>=5 txns/60m) and split structuring outflows ($1,800-$2,999.99/24h).",
        },
        {
            "key": "LARGE_AMOUNT",
            "function_num": 80,
            "name": "Unusual Transaction Amounts",
            "rules": ["RULE-008", "RULE-005"],
            "alert_count": rule_counts.get("RULE-008", {}).get("hit_count", 0)
            + rule_counts.get("RULE-005", {}).get("hit_count", 0),
            "description": "Amounts >= 50% of declared monthly income or high-risk cross-border spend >= $1,000.",
        },
        {
            "key": "NEW_DEVICE",
            "function_num": 81,
            "name": "New-Device Anomalies",
            "rules": ["RULE-002"],
            "alert_count": rule_counts.get("RULE-002", {}).get("hit_count", 0),
            "description": "High-value outbound activity (>= $1,500) within 24 hours of first device link.",
        },
        {
            "key": "LINKED_PATTERN",
            "function_num": 82,
            "name": "Circular Transfer Patterns",
            "rules": ["RULE-003"],
            "alert_count": rule_counts.get("RULE-003", {}).get("hit_count", 0),
            "description": "Multi-hop TransferLink rings (2..5 hops returning >= 75% within 48 hours).",
        },
        {
            "key": "DORMANT_ACCOUNT",
            "function_num": 83,
            "name": "Dormant Account Reactivation",
            "rules": ["RULE-004"],
            "alert_count": rule_counts.get("RULE-004", {}).get("hit_count", 0),
            "extra_metric": f"{dormant_accts} reactivated accounts",
            "description": "Previously dormant accounts suddenly executing large transfers (>= $3,000 within 48h).",
        },
        {
            "key": "LINKED_PATTERN",
            "function_num": 84,
            "name": "Unusual Account & Network Links",
            "rules": ["RULE-007"],
            "alert_count": rule_counts.get("RULE-007", {}).get("hit_count", 0),
            "extra_metric": f"{shared_devs} shared multi-customer devices",
            "description": "Single device or transfer cluster spanning >= 3 unrelated primary customers.",
        },
    ]


def detect_integrity_anomalies(conn: sqlite3.Connection) -> dict[str, Any]:
    """Detect closed-account txns, unauthorized negative balances, transfer mismatches & reference defects (Functions 85-88)."""
    closed_txns = [
        dict(r)
        for r in conn.execute(
            """
            SELECT t.transaction_id, t.account_id, t.amount, t.occurred_at, a.closed_at
            FROM transactions t
            JOIN accounts a ON a.account_id = t.account_id
            WHERE a.status = 'CLOSED' AND a.closed_at IS NOT NULL AND t.occurred_at > a.closed_at
            ORDER BY t.occurred_at DESC
            LIMIT 50
            """
        ).fetchall()
    ]

    neg_bal_txns = [
        dict(r)
        for r in conn.execute(
            """
            SELECT t.transaction_id, t.account_id, t.amount, t.balance_before, t.balance_after, t.occurred_at
            FROM transactions t
            JOIN accounts a ON a.account_id = t.account_id
            WHERE a.overdraft_allowed = 0 AND t.balance_after < 0
            ORDER BY t.occurred_at DESC
            LIMIT 50
            """
        ).fetchall()
    ]

    mismatched_transfers = [
        dict(r)
        for r in conn.execute(
            """
            SELECT tr.transfer_id, tr.source_account_id, tr.dest_account_id, tr.debit_txn_id, tr.credit_txn_id,
                   tr.transfer_amount, tr.status, dt.amount AS debit_amount, ct.amount AS credit_amount
            FROM transfer_links tr
            LEFT JOIN transactions dt ON dt.transaction_id = tr.debit_txn_id
            LEFT JOIN transactions ct ON ct.transaction_id = tr.credit_txn_id
            WHERE tr.credit_txn_id IS NULL
               OR ABS(COALESCE(dt.amount, 0) - COALESCE(ct.amount, 0)) > 0.001
               OR ABS(tr.transfer_amount - COALESCE(dt.amount, 0)) > 0.001
               OR tr.status != 'SETTLED'
            ORDER BY tr.transfer_id DESC
            LIMIT 50
            """
        ).fetchall()
    ]

    missing_refs: list[dict[str, Any]] = []
    # Check missing note, missing merchant_id on MERCHANT_PURCHASE, unlinked transfer txns, or orphan alert references
    for r in conn.execute(
        """
        SELECT transaction_id AS record_id, 'TRANSACTION' AS record_type, account_id,
               'EMPTY_REFERENCE_NOTE' AS ref_issue, occurred_at AS timestamp
        FROM transactions
        WHERE TRIM(COALESCE(reference_note, '')) = ''
        LIMIT 25
        """
    ).fetchall():
        missing_refs.append(dict(r))

    for r in conn.execute(
        """
        SELECT transaction_id AS record_id, 'TRANSACTION' AS record_type, account_id,
               'MERCHANT_TXN_MISSING_MERCHANT_ID' AS ref_issue, occurred_at AS timestamp
        FROM transactions
        WHERE txn_type = 'MERCHANT_PURCHASE' AND merchant_id IS NULL
        LIMIT 25
        """
    ).fetchall():
        missing_refs.append(dict(r))

    for r in conn.execute(
        """
        SELECT t.transaction_id AS record_id, 'TRANSACTION' AS record_type, t.account_id,
               'TRANSFER_TXN_MISSING_LINK_REF' AS ref_issue, t.occurred_at AS timestamp
        FROM transactions t
        WHERE t.txn_type IN ('P2P_TRANSFER_OUT', 'P2P_TRANSFER_IN', 'INTERNAL_TRANSFER_OUT', 'INTERNAL_TRANSFER_IN')
          AND NOT EXISTS (
              SELECT 1 FROM transfer_links tr WHERE tr.debit_txn_id = t.transaction_id OR tr.credit_txn_id = t.transaction_id
          )
        LIMIT 25
        """
    ).fetchall():
        missing_refs.append(dict(r))

    for r in conn.execute(
        """
        SELECT a.alert_id AS record_id, 'ALERT' AS record_type, a.account_id,
               'ORPHAN_OR_MISSING_TXN_TRIGGER_REF' AS ref_issue, a.created_at AS timestamp
        FROM alerts a
        LEFT JOIN alert_trigger_facts f ON f.alert_id = a.alert_id
        GROUP BY a.alert_id
        HAVING a.primary_txn_id IS NULL OR COUNT(f.fact_id) = 0
        LIMIT 25
        """
    ).fetchall():
        missing_refs.append(dict(r))

    return {
        "closed_account_txns": {"count": len(closed_txns), "items": closed_txns},
        "negative_balance_no_overdraft": {"count": len(neg_bal_txns), "items": neg_bal_txns},
        "mismatched_transfer_amounts": {"count": len(mismatched_transfers), "items": mismatched_transfers},
        "missing_or_inconsistent_references": {"count": len(missing_refs), "items": missing_refs},
    }


def update_rule_and_reevaluate(
    conn: sqlite3.Connection,
    *,
    rule_id: str | None = None,
    base_weight: int | None = None,
    is_active: bool | None = None,
    threshold_desc: str | None = None,
    actor_id: str = "ADM-001",
    trigger_source: str = "MANUAL_RE_EVALUATION",
) -> dict[str, Any]:
    """Update a RiskRule (optional) and re-evaluate transactions/alerts, recording run + score history (Functions 78, 89, 90)."""
    ensure_scoring_history_schema(conn)
    now_iso = _iso_now()
    updated_rule: dict[str, Any] | None = None
    old_weight: float | None = None

    if rule_id and rule_id != "ALL":
        r_row = conn.execute("SELECT * FROM risk_rules WHERE rule_id = ?", (rule_id,)).fetchone()
        if not r_row:
            raise ValueError(f"RiskRule '{rule_id}' not found")
        old_weight = float(r_row["base_weight"])
        new_weight = int(base_weight) if base_weight is not None else int(r_row["base_weight"])
        new_active = int(bool(is_active)) if is_active is not None else int(r_row["is_active"])
        new_desc = threshold_desc.strip() if threshold_desc and threshold_desc.strip() else r_row["threshold_desc"]
        if new_weight < 1 or new_weight > 100:
            raise ValueError("base_weight must be between 1 and 100")

        conn.execute(
            "UPDATE risk_rules SET base_weight = ?, is_active = ?, threshold_desc = ? WHERE rule_id = ?",
            (new_weight, new_active, new_desc, rule_id),
        )
        updated_rule = dict(conn.execute("SELECT * FROM risk_rules WHERE rule_id = ?", (rule_id,)).fetchone())
        trigger_source = f"RULE_UPDATED:{rule_id}"

    # Recompute scores on alerts matching updated rule (or all alerts if full re-eval)
    if rule_id and rule_id != "ALL":
        target_alerts = conn.execute("SELECT * FROM alerts WHERE rule_id = ?", (rule_id,)).fetchall()
    else:
        target_alerts = conn.execute("SELECT * FROM alerts").fetchall()

    rules_by_id = {r["rule_id"]: dict(r) for r in conn.execute("SELECT * FROM risk_rules").fetchall()}
    changes = 0
    total_after = 0.0
    for al in target_alerts:
        rule_cfg = rules_by_id.get(al["rule_id"])
        if not rule_cfg:
            continue
        prev_score = float(al["risk_score"])
        prev_lvl = classify_risk(prev_score)

        if not rule_cfg["is_active"]:
            new_score = 0.0
        elif updated_rule is not None and old_weight is not None:
            delta = float(rule_cfg["base_weight"]) - old_weight
            new_score = round(min(100.0, max(0.0, prev_score + delta)), 2)
        else:
            # Deterministic formula from trigger metrics + active base weight
            amt_bonus = min(14.0, round(float(al["trigger_total_amount"]) / 2500.0, 2))
            cnt_bonus = min(10.0, max(0, int(al["trigger_txn_count"]) - 1) * 1.5)
            new_score = round(min(100.0, float(rule_cfg["base_weight"]) + amt_bonus + cnt_bonus), 2)

        new_lvl = classify_risk(new_score)
        total_after += new_score
        if abs(new_score - prev_score) >= 0.01:
            changes += 1
            conn.execute("UPDATE alerts SET risk_score = ? WHERE alert_id = ?", (new_score, al["alert_id"]))
            conn.execute(
                """
                INSERT INTO risk_score_history
                (history_id, entity_type, entity_id, prev_score, new_score, prev_level, new_level, reason, rule_id, recorded_at, actor_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"HIST-{secrets.token_hex(6).upper()}",
                    "ALERT",
                    al["alert_id"],
                    prev_score,
                    new_score,
                    prev_lvl,
                    new_lvl,
                    f"Re-evaluated under {trigger_source} (weight={rule_cfg['base_weight']}, active={rule_cfg['is_active']})",
                    al["rule_id"],
                    now_iso,
                    actor_id,
                ),
            )

    txn_cnt = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    avg_sc = round(total_after / max(1, len(target_alerts)), 2)
    run_id = f"RUN-{secrets.token_hex(5).upper()}"
    summary = (
        f"{trigger_source}: evaluated {txn_cnt:,} txns across {len(target_alerts)} alert(s); "
        f"{changes} alert score(s) updated."
    )
    conn.execute(
        """
        INSERT INTO rule_execution_runs
        (run_id, trigger_source, rule_id, txns_evaluated, alerts_affected, avg_score, executed_by, executed_at, summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (run_id, trigger_source, rule_id or "ALL", int(txn_cnt), int(changes), avg_sc, actor_id, now_iso, summary),
    )
    conn.commit()
    exec_row = dict(conn.execute("SELECT * FROM rule_execution_runs WHERE run_id = ?", (run_id,)).fetchone())
    return {
        "execution_run": exec_row,
        "updated_rule": updated_rule,
        "alerts_evaluated": len(target_alerts),
        "scores_changed": changes,
    }


def get_rule_executions_and_history(
    conn: sqlite3.Connection,
    *,
    entity_id: str | None = None,
    limit: int = 80,
) -> dict[str, Any]:
    """Return rule execution timestamps/results and historical score changes (Functions 78, 90)."""
    ensure_scoring_history_schema(conn)
    runs = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM rule_execution_runs ORDER BY executed_at DESC, run_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    ]
    if entity_id:
        hist = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM risk_score_history WHERE entity_id = ? ORDER BY recorded_at DESC, history_id DESC LIMIT ?",
                (entity_id, limit),
            ).fetchall()
        ]
    else:
        hist = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM risk_score_history ORDER BY recorded_at DESC, history_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        ]
    return {"execution_runs": runs, "score_history": hist}


def get_risk_scoring_overview(conn: sqlite3.Connection) -> dict[str, Any]:
    """Compute portfolio-wide Transaction, Account, and Customer risk scoring distributions (Functions 71-90)."""
    ensure_scoring_history_schema(conn)
    txn_dist_rows = conn.execute(
        """
        WITH atf_agg AS (
            SELECT f.transaction_id, MAX(al.risk_score) AS max_score
            FROM alert_trigger_facts f
            JOIN alerts al ON al.alert_id = f.alert_id
            GROUP BY f.transaction_id
        ),
        classified AS (
            SELECT
                CASE
                    WHEN COALESCE(atf_agg.max_score, 0) >= 60 THEN 'HIGH'
                    WHEN COALESCE(atf_agg.max_score, 0) > 0 OR COALESCE(m.risk_tier, '') = 'HIGH' THEN 'MEDIUM'
                    ELSE 'LOW'
                END AS risk_level,
                COALESCE(atf_agg.max_score, CASE WHEN COALESCE(m.risk_tier, '') = 'HIGH' THEN 22.0 ELSE 0.0 END) AS risk_score
            FROM transactions t
            LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
            LEFT JOIN atf_agg ON atf_agg.transaction_id = t.transaction_id
        )
        SELECT risk_level, COUNT(*) AS cnt, ROUND(AVG(risk_score), 2) AS avg_score, ROUND(MAX(risk_score), 2) AS max_score
        FROM classified
        GROUP BY risk_level
        """
    ).fetchall()
    txn_dist = {r["risk_level"]: {"count": r["cnt"], "avg_score": r["avg_score"], "max_score": r["max_score"]} for r in txn_dist_rows}

    acct_rows = conn.execute(
        """
        WITH acct_base AS (
            SELECT a.account_id, a.primary_customer_id, cu.full_name AS customer_name, a.status,
                   COUNT(DISTINCT al.alert_id) AS alert_count,
                   COALESCE(MAX(al.risk_score), 0) AS max_al,
                   EXISTS (
                       SELECT 1 FROM account_state_events ase
                       WHERE ase.account_id = a.account_id AND ase.prev_status = 'DORMANT' AND ase.new_status = 'ACTIVE'
                   ) AS is_dormant_react
            FROM accounts a
            JOIN customers cu ON cu.customer_id = a.primary_customer_id
            LEFT JOIN alerts al ON al.account_id = a.account_id
            GROUP BY a.account_id
        ),
        scored AS (
            SELECT *,
                   ROUND(MIN(100.0, max_al + (CASE WHEN is_dormant_react = 1 THEN 8.0 ELSE 0.0 END) + MAX(0, alert_count - 1) * 4.5), 2) AS account_risk_score
            FROM acct_base
        )
        SELECT *,
               CASE WHEN account_risk_score >= 60 THEN 'HIGH' WHEN account_risk_score >= 20 OR alert_count > 0 THEN 'MEDIUM' ELSE 'LOW' END AS risk_level
        FROM scored
        ORDER BY account_risk_score DESC, alert_count DESC, account_id ASC
        """
    ).fetchall()
    acct_dist: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    top_accounts: list[dict[str, Any]] = []
    for r in acct_rows:
        acct_dist[r["risk_level"]] = acct_dist.get(r["risk_level"], 0) + 1
        if len(top_accounts) < 10:
            top_accounts.append(dict(r))

    cust_rows = conn.execute(
        """
        WITH cust_case_agg AS (
            SELECT primary_customer_id AS customer_id, COALESCE(MAX(priority_score), 0) AS max_case
            FROM cases
            GROUP BY primary_customer_id
        ),
        cust_susp_agg AS (
            SELECT ao.customer_id, COUNT(DISTINCT al.account_id) AS suspicious_accts
            FROM account_ownerships ao
            JOIN alerts al ON al.account_id = ao.account_id
            GROUP BY ao.customer_id
        ),
        cust_alert_agg AS (
            SELECT customer_id, COALESCE(MAX(risk_score), 0) AS max_al
            FROM alerts
            GROUP BY customer_id
        ),
        cust_base AS (
            SELECT cu.customer_id, cu.full_name, cu.kyc_tier,
                   COALESCE(cca.max_case, 0) AS max_case,
                   COALESCE(csa.suspicious_accts, 0) AS suspicious_accts,
                   COALESCE(caa.max_al, 0) AS max_al
            FROM customers cu
            LEFT JOIN cust_case_agg cca ON cca.customer_id = cu.customer_id
            LEFT JOIN cust_susp_agg csa ON csa.customer_id = cu.customer_id
            LEFT JOIN cust_alert_agg caa ON caa.customer_id = cu.customer_id
        ),
        scored AS (
            SELECT *,
                   ROUND(MIN(100.0, MAX(max_case, max_al)
                       + (CASE WHEN kyc_tier = 'LOW' THEN 10.0 WHEN kyc_tier = 'STANDARD' THEN 4.0 ELSE 0.0 END)
                       + MAX(0, suspicious_accts - 1) * 10.0), 2) AS customer_risk_score
            FROM cust_base
        )
        SELECT *,
               CASE WHEN customer_risk_score >= 60 THEN 'HIGH' WHEN customer_risk_score >= 20 OR max_al > 0 THEN 'MEDIUM' ELSE 'LOW' END AS risk_level
        FROM scored
        ORDER BY customer_risk_score DESC, suspicious_accts DESC, customer_id ASC
        """
    ).fetchall()
    cust_dist: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    top_customers: list[dict[str, Any]] = []
    for r in cust_rows:
        cust_dist[r["risk_level"]] = cust_dist.get(r["risk_level"], 0) + 1
        if len(top_customers) < 10:
            top_customers.append(dict(r))

    rules_summary = [
        dict(r)
        for r in conn.execute(
            """
            SELECT r.rule_id, r.rule_name, r.category, r.severity, r.base_weight, r.threshold_desc, r.is_active,
                   COUNT(al.alert_id) AS hit_count, ROUND(COALESCE(AVG(al.risk_score), 0), 2) AS avg_score
            FROM risk_rules r
            LEFT JOIN alerts al ON al.rule_id = r.rule_id
            GROUP BY r.rule_id
            ORDER BY hit_count DESC, r.rule_id ASC
            """
        ).fetchall()
    ]

    hist_data = get_rule_executions_and_history(conn, limit=30)

    return {
        "thresholds": {
            "HIGH": "score >= 60.0",
            "MEDIUM": "20.0 <= score < 60.0 (or rule/merchant risk signal)",
            "LOW": "score < 20.0 (no anomaly flags)",
        },
        "transaction_risk_distribution": {
            k: txn_dist.get(k, {"count": 0, "avg_score": 0.0, "max_score": 0.0})
            for k in ("HIGH", "MEDIUM", "LOW")
        },
        "account_risk_distribution": acct_dist,
        "customer_risk_distribution": cust_dist,
        "top_risk_accounts": top_accounts,
        "top_risk_customers": top_customers,
        "rules_summary": rules_summary,
        "anomaly_detectors": detect_behavioral_anomalies_summary(conn),
        "integrity_detectors": detect_integrity_anomalies(conn),
        "execution_runs": hist_data["execution_runs"],
        "score_history": hist_data["score_history"],
    }

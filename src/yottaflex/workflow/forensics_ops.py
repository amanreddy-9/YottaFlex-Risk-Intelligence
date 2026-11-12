"""Deep Financial Forensics, Jurisdiction Controls, Evidence Vault, Playbooks & Suppressions (Functions 176-195)."""

from __future__ import annotations

import json
import secrets
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from yottaflex.workflow.governance_ops import get_sla_policies
from yottaflex.workflow.triage_extensions import ensure_triage_extensions_schema


DEFAULT_HIGH_RISK_COUNTRIES = [
    ("CY", "Cyprus Offshore Corridor", "WATCH", 1.25, "High-velocity shell & correspondent transit hub"),
    ("PA", "Panama Transit Jurisdiction", "RESTRICTED", 1.45, "Elevated corporate layering & bearer-share risk"),
    ("KY", "Cayman Financial Center", "WATCH", 1.20, "Cross-border offshore fund vehicle concentration"),
    ("RU", "Sanctioned Corridor East", "RESTRICTED", 1.60, "Strict sanctions & correspondent screening"),
    ("VG", "BVI Corporate Registry", "WATCH", 1.25, "Multi-layered beneficial ownership opacity"),
]

PLAYBOOKS: list[dict[str, Any]] = [
    {
        "playbook_id": "PB-STRUCTURING",
        "title": "Sub-Threshold Structuring & Smurfing SOP",
        "typology": "STRUCTURING",
        "checklist_updates": {"rules_reviewed": True, "ledger_reconciled": True},
        "steps": [
            "1. Aggregate rolling 7-day cash & near-threshold bursts ($7.5k-$9.99k) per account.",
            "2. Compare structured deposits against declared_annual_income & customer segment baseline.",
            "3. Pin supporting branch/ATM/wire receipts in Evidence Pinboard before FinCEN SAR filing.",
        ],
    },
    {
        "playbook_id": "PB-LAYERING",
        "title": "Multi-Hop Layering & Pass-Through Ring SOP",
        "typology": "LAYERING",
        "checklist_updates": {"network_verified": True, "rules_reviewed": True},
        "steps": [
            "1. Trace 24h-72h pass-through chains via Flow Chain Tracer and compute retention ratio.",
            "2. Check shared device_id fingerprints and emulator flags across source & destination owners.",
            "3. Issue DEBIT_HOLD or FULL_FREEZE control if net outflow exceeds 85% within 48 hours.",
        ],
    },
    {
        "playbook_id": "PB-DORMANT",
        "title": "Dormant Account Reactivation Surge SOP",
        "typology": "DORMANT_SURGE",
        "checklist_updates": {"kyc_corroborated": True, "ledger_reconciled": True},
        "steps": [
            "1. Verify last historical settled activity date prior to sudden high-value reactivation.",
            "2. Confirm customer KYC review freshness and device fingerprint consistency.",
            "3. Draft 314(b) correspondent RFI if counterparty country is marked WATCH/RESTRICTED.",
        ],
    },
    {
        "playbook_id": "PB-EMULATOR",
        "title": "Synthetic Device & Velocity Burst SOP",
        "typology": "VELOCITY_EMULATOR",
        "checklist_updates": {"network_verified": True, "kyc_corroborated": True},
        "steps": [
            "1. Audit all accounts sharing emulator device fingerprint in Collusion Ring Explorer.",
            "2. Check merchant category risk tier and rapid reversal / chargeback patterns.",
            "3. Tag entities with MULE_SUSPECT / HIGH_RISK_ENTITY and escalate for Reviewer sign-off.",
        ],
    },
]

VALID_ACCOUNT_CONTROLS = ("NONE", "DEBIT_HOLD", "POST_NO_DEBITS", "FULL_FREEZE")
VALID_KYC_OUTCOMES = ("VERIFIED", "EDD_REQUIRED", "OVERDUE")
VALID_PIN_TYPES = ("PINNED_PROOF", "CORROBORATING", "EXCULPATORY")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def _parse_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def ensure_forensics_schema(conn: sqlite3.Connection) -> None:
    """Create Batch 8 forensic, control, pinboard, comment, suppression & export log tables idempotently."""
    ensure_triage_extensions_schema(conn)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS high_risk_countries (
            country_code TEXT PRIMARY KEY,
            country_name TEXT NOT NULL,
            risk_tier TEXT NOT NULL DEFAULT 'WATCH',
            multiplier REAL NOT NULL DEFAULT 1.25,
            note TEXT,
            updated_by TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS kyc_reviews (
            review_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            risk_justification TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            reviewed_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS account_controls (
            account_id TEXT PRIMARY KEY,
            control_status TEXT NOT NULL DEFAULT 'NONE',
            reason TEXT,
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS case_evidence_pins (
            pin_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            pin_type TEXT NOT NULL DEFAULT 'PINNED_PROOF',
            note TEXT,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(case_id, entity_type, entity_id)
        );

        CREATE TABLE IF NOT EXISTS case_comments (
            comment_id TEXT PRIMARY KEY,
            case_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            actor_role TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'INTERNAL',
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS suppression_rules (
            suppression_id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            max_amount REAL NOT NULL,
            reason TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS export_history (
            export_id TEXT PRIMARY KEY,
            actor_id TEXT NOT NULL,
            export_type TEXT NOT NULL,
            fmt TEXT NOT NULL,
            filter_summary TEXT,
            row_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_kyc_reviews_cust ON kyc_reviews(customer_id, reviewed_at DESC);
        CREATE INDEX IF NOT EXISTS idx_case_pins_case ON case_evidence_pins(case_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_case_comments_case ON case_comments(case_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_suppression_acct ON suppression_rules(account_id, rule_id, is_active);
        CREATE INDEX IF NOT EXISTS idx_export_hist_ts ON export_history(created_at DESC);
        """
    )

    now = _now_iso()
    for code, name, tier, mult, note in DEFAULT_HIGH_RISK_COUNTRIES:
        conn.execute(
            """
            INSERT OR IGNORE INTO high_risk_countries (country_code, country_name, risk_tier, multiplier, note, updated_by, updated_at)
            VALUES (?, ?, ?, ?, ?, 'SYSTEM', ?)
            """,
            (code, name, tier, mult, note, now),
        )
    conn.commit()


# ------------------------------------------------------------------
# Functions 176-179: Corridor Risk Matrix, Jurisdictions & Merchants
# ------------------------------------------------------------------
def list_high_risk_countries(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    ensure_forensics_schema(conn)
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM high_risk_countries ORDER BY CASE risk_tier WHEN 'RESTRICTED' THEN 1 ELSE 2 END, country_code"
        ).fetchall()
    ]


def upsert_high_risk_country(
    conn: sqlite3.Connection,
    *,
    country_code: str,
    country_name: str,
    risk_tier: str,
    multiplier: float,
    note: str,
    actor_id: str,
) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    cc = country_code.strip().upper()[:4]
    if len(cc) < 2:
        raise ValueError("Country code must be 2-4 characters (e.g. CY)")
    tier = risk_tier.strip().upper()
    if tier not in {"WATCH", "RESTRICTED"}:
        raise ValueError("risk_tier must be WATCH or RESTRICTED")
    mult = max(1.0, min(5.0, float(multiplier)))
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO high_risk_countries (country_code, country_name, risk_tier, multiplier, note, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(country_code) DO UPDATE SET
            country_name = excluded.country_name,
            risk_tier = excluded.risk_tier,
            multiplier = excluded.multiplier,
            note = excluded.note,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        (cc, country_name.strip() or cc, tier, mult, note.strip(), actor_id, now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM high_risk_countries WHERE country_code = ?", (cc,)).fetchone())


def delete_high_risk_country(conn: sqlite3.Connection, country_code: str) -> bool:
    ensure_forensics_schema(conn)
    cur = conn.execute("DELETE FROM high_risk_countries WHERE country_code = ?", (country_code.strip().upper(),))
    conn.commit()
    return cur.rowcount > 0


def get_corridor_risk_matrix(conn: sqlite3.Connection, *, limit: int = 80) -> dict[str, Any]:
    """Aggregate transaction volume & alert exposure across origin -> counterparty country corridors."""
    ensure_forensics_schema(conn)
    watched = {r["country_code"]: dict(r) for r in list_high_risk_countries(conn)}
    rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(cu.home_country, ''), 'US') AS origin_country,
               COALESCE(NULLIF(t.counterparty_country, ''), 'US') AS counterparty_country,
               COUNT(*) AS txn_count,
               COALESCE(SUM(t.amount), 0) AS total_volume,
               SUM(CASE WHEN t.amount >= 5000 THEN 1 ELSE 0 END) AS high_value_txns,
               COUNT(DISTINCT al.alert_id) AS alert_count,
               COALESCE(AVG(al.risk_score), 0) AS avg_alert_score
        FROM transactions t
        JOIN accounts a ON a.account_id = t.account_id
        JOIN customers cu ON cu.customer_id = a.primary_customer_id
        LEFT JOIN alerts al ON al.primary_txn_id = t.transaction_id
        GROUP BY origin_country, counterparty_country
        ORDER BY alert_count DESC, total_volume DESC
        LIMIT ?
        """,
        (max(1, min(200, int(limit))),),
    ).fetchall()

    items: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        cc = d["counterparty_country"]
        w = watched.get(cc)
        txn_cnt = int(d["txn_count"] or 0)
        al_cnt = int(d["alert_count"] or 0)
        items.append(
            {
                "origin_country": d["origin_country"],
                "counterparty_country": cc,
                "is_cross_border": d["origin_country"] != cc,
                "jurisdiction_tier": w["risk_tier"] if w else "STANDARD",
                "jurisdiction_multiplier": float(w["multiplier"]) if w else 1.0,
                "txn_count": txn_cnt,
                "total_volume": round(float(d["total_volume"] or 0.0), 2),
                "high_value_txns": int(d["high_value_txns"] or 0),
                "alert_count": al_cnt,
                "alert_rate_pct": round((al_cnt / txn_cnt) * 100.0, 2) if txn_cnt else 0.0,
                "avg_alert_score": round(float(d["avg_alert_score"] or 0.0), 2),
            }
        )
    return {"watched_countries": list(watched.values()), "items": items}


def get_merchant_leaderboard(conn: sqlite3.Connection, *, search: str | None = None, limit: int = 100) -> dict[str, Any]:
    """Rank merchants by alert intensity, transaction volume, high-risk MCC flag & customer spread."""
    where = ["1=1"]
    params: list[Any] = []
    if search and search.strip():
        q = f"%{search.strip()}%"
        where.append("(m.merchant_id LIKE ? OR m.merchant_name LIKE ? OR m.category LIKE ? OR m.country LIKE ?)")
        params.extend([q, q, q, q])

    rows = conn.execute(
        f"""
        SELECT m.merchant_id, m.merchant_name, m.mcc, m.category, m.country, m.risk_tier, m.is_high_risk_mcc,
               COUNT(t.transaction_id) AS txn_count,
               COALESCE(SUM(t.amount), 0) AS total_volume,
               COALESCE(AVG(t.amount), 0) AS avg_ticket,
               COUNT(DISTINCT a.primary_customer_id) AS customer_spread,
               COUNT(DISTINCT al.alert_id) AS alert_count,
               COALESCE(MAX(al.risk_score), 0) AS max_alert_score
        FROM merchants m
        LEFT JOIN transactions t ON t.merchant_id = m.merchant_id
        LEFT JOIN accounts a ON a.account_id = t.account_id
        LEFT JOIN alerts al ON al.primary_txn_id = t.transaction_id
        WHERE {' AND '.join(where)}
        GROUP BY m.merchant_id
        ORDER BY alert_count DESC, m.is_high_risk_mcc DESC, total_volume DESC
        LIMIT ?
        """,
        (*params, max(1, min(300, int(limit)))),
    ).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        d["total_volume"] = round(float(d["total_volume"] or 0.0), 2)
        d["avg_ticket"] = round(float(d["avg_ticket"] or 0.0), 2)
        d["max_alert_score"] = round(float(d["max_alert_score"] or 0.0), 2)
        d["is_high_risk_mcc"] = bool(d["is_high_risk_mcc"])
        items.append(d)
    return {"total": len(items), "items": items}


def get_merchant_detail(conn: sqlite3.Connection, merchant_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM merchants WHERE merchant_id = ?", (merchant_id,)).fetchone()
    if not row:
        return None
    top_accounts = [
        dict(r)
        for r in conn.execute(
            """
            SELECT t.account_id, a.primary_customer_id, cu.full_name AS customer_name,
                   COUNT(*) AS txn_count, SUM(t.amount) AS volume, MAX(t.occurred_at) AS last_txn_at
            FROM transactions t
            JOIN accounts a ON a.account_id = t.account_id
            JOIN customers cu ON cu.customer_id = a.primary_customer_id
            WHERE t.merchant_id = ?
            GROUP BY t.account_id
            ORDER BY volume DESC LIMIT 10
            """,
            (merchant_id,),
        ).fetchall()
    ]
    recent_alerts = [
        dict(r)
        for r in conn.execute(
            """
            SELECT al.alert_id, al.rule_id, al.severity, al.risk_score, al.account_id, al.trigger_total_amount, al.created_at
            FROM alerts al
            JOIN transactions t ON t.transaction_id = al.primary_txn_id
            WHERE t.merchant_id = ?
            ORDER BY al.risk_score DESC LIMIT 12
            """,
            (merchant_id,),
        ).fetchall()
    ]
    return {"merchant": dict(row), "top_accounts": top_accounts, "recent_alerts": recent_alerts}


# ------------------------------------------------------------------
# Functions 180-185: Layering Chains, Structuring, Baseline, KYC, Controls & Velocity
# ------------------------------------------------------------------
def trace_flow_chains(conn: sqlite3.Connection, account_id: str, *, max_hops: int = 3) -> dict[str, Any]:
    """Trace multi-hop chronological pass-through transfer chains starting or passing through account_id."""
    aid = account_id.strip()
    if not aid:
        raise ValueError("account_id is required")

    links = [
        dict(r)
        for r in conn.execute(
            """
            SELECT transfer_id, source_account_id, dest_account_id, transfer_amount, is_same_customer, initiated_at
            FROM transfer_links
            WHERE source_account_id = ? OR dest_account_id = ?
            ORDER BY initiated_at ASC
            LIMIT 120
            """,
            (aid, aid),
        ).fetchall()
    ]
    chains: list[dict[str, Any]] = []
    visited = {aid}
    frontier = [aid]
    hop_edges: list[dict[str, Any]] = list(links)

    for hop in range(1, max(1, min(4, int(max_hops)))):
        next_accts = {l["dest_account_id"] for l in links if l["source_account_id"] in frontier} - visited
        if not next_accts:
            break
        ph = ",".join(["?"] * len(next_accts))
        more = [
            dict(r)
            for r in conn.execute(
                f"""
                SELECT transfer_id, source_account_id, dest_account_id, transfer_amount, is_same_customer, initiated_at
                FROM transfer_links
                WHERE source_account_id IN ({ph})
                ORDER BY initiated_at ASC LIMIT 80
                """,
                tuple(next_accts),
            ).fetchall()
        ]
        hop_edges.extend(more)
        visited.update(next_accts)
        frontier = list(next_accts)

    # Deduplicate edges and build directional chains from seed account
    seen_tid: set[str] = set()
    uniq_edges: list[dict[str, Any]] = []
    for e in hop_edges:
        if e["transfer_id"] not in seen_tid:
            seen_tid.add(e["transfer_id"])
            uniq_edges.append(e)

    inflow = sum(float(e["transfer_amount"]) for e in uniq_edges if e["dest_account_id"] == aid)
    outflow = sum(float(e["transfer_amount"]) for e in uniq_edges if e["source_account_id"] == aid)
    pass_through_ratio = round((outflow / inflow) * 100.0, 1) if inflow > 0 else 0.0

    # Assemble 2-hop pass-through sequences A -> aid -> C
    incoming_to_seed = [e for e in uniq_edges if e["dest_account_id"] == aid]
    outgoing_from_seed = [e for e in uniq_edges if e["source_account_id"] == aid]
    for inc in incoming_to_seed[:10]:
        t_in = _parse_dt(inc["initiated_at"])
        for out in outgoing_from_seed[:10]:
            t_out = _parse_dt(out["initiated_at"])
            if t_in and t_out and timedelta(0) <= (t_out - t_in) <= timedelta(hours=72):
                chains.append(
                    {
                        "path": f"{inc['source_account_id']} -> {aid} -> {out['dest_account_id']}",
                        "in_amount": round(float(inc["transfer_amount"]), 2),
                        "out_amount": round(float(out["transfer_amount"]), 2),
                        "retention_pct": round((float(out["transfer_amount"]) / max(1.0, float(inc["transfer_amount"]))) * 100.0, 1),
                        "lag_hours": round((t_out - t_in).total_seconds() / 3600.0, 1),
                    }
                )

    return {
        "root_account_id": aid,
        "total_inflow": round(inflow, 2),
        "total_outflow": round(outflow, 2),
        "pass_through_pct": pass_through_ratio,
        "edges": uniq_edges[:80],
        "pass_through_chains": chains[:20],
    }


def detect_structuring_clusters(conn: sqlite3.Connection, *, min_txns: int = 2, limit: int = 80) -> dict[str, Any]:
    """Detect accounts grouping repeated near-threshold transactions ($7,500-$9,999.99) >= $10,000 total."""
    rows = conn.execute(
        """
        SELECT t.account_id, a.primary_customer_id, cu.full_name AS customer_name,
               COUNT(*) AS burst_count,
               SUM(t.amount) AS total_structured_amount,
               MIN(t.occurred_at) AS first_at,
               MAX(t.occurred_at) AS last_at,
               AVG(t.amount) AS avg_ticket
        FROM transactions t
        JOIN accounts a ON a.account_id = t.account_id
        JOIN customers cu ON cu.customer_id = a.primary_customer_id
        WHERE t.amount >= 7500 AND t.amount < 10000
        GROUP BY t.account_id
        HAVING COUNT(*) >= ? AND SUM(t.amount) >= 10000
        ORDER BY total_structured_amount DESC, burst_count DESC
        LIMIT ?
        """,
        (max(2, int(min_txns)), max(1, min(200, int(limit)))),
    ).fetchall()

    items = []
    for r in rows:
        d = dict(r)
        d["total_structured_amount"] = round(float(d["total_structured_amount"] or 0.0), 2)
        d["avg_ticket"] = round(float(d["avg_ticket"] or 0.0), 2)
        items.append(d)
    return {"total": len(items), "items": items}


def get_customer_peer_baseline(conn: sqlite3.Connection, customer_id: str) -> dict[str, Any] | None:
    """Compare customer's txn volume & cross-border share against segment x kyc_tier cohort."""
    cust = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
    if not cust:
        return None
    cust_stats = conn.execute(
        """
        SELECT COUNT(*) AS txn_count,
               COALESCE(SUM(t.amount), 0) AS total_volume,
               COALESCE(AVG(t.amount), 0) AS avg_amount,
               SUM(CASE WHEN t.counterparty_country != COALESCE(NULLIF(cu.home_country, ''), 'US') THEN 1 ELSE 0 END) AS xborder_cnt
        FROM transactions t
        JOIN accounts a ON a.account_id = t.account_id
        JOIN customers cu ON cu.customer_id = a.primary_customer_id
        WHERE a.primary_customer_id = ?
        """,
        (customer_id,),
    ).fetchone()

    cohort_rows = conn.execute(
        """
        SELECT cu.customer_id, COALESCE(SUM(t.amount), 0) AS vol, COALESCE(AVG(t.amount), 0) AS avg_amt, COUNT(t.transaction_id) AS cnt
        FROM customers cu
        LEFT JOIN accounts a ON a.primary_customer_id = cu.customer_id
        LEFT JOIN transactions t ON t.account_id = a.account_id
        WHERE cu.segment = ? AND cu.kyc_tier = ?
        GROUP BY cu.customer_id
        LIMIT 400
        """,
        (cust["segment"], cust["kyc_tier"]),
    ).fetchall()

    vols = sorted(float(r["vol"] or 0.0) for r in cohort_rows)
    avgs = sorted(float(r["avg_amt"] or 0.0) for r in cohort_rows)
    cohort_mean_vol = round(sum(vols) / len(vols), 2) if vols else 0.0
    cohort_p95_vol = round(vols[min(len(vols) - 1, int(len(vols) * 0.95))], 2) if vols else 0.0
    cohort_mean_ticket = round(sum(avgs) / len(avgs), 2) if avgs else 0.0

    my_vol = round(float(cust_stats["total_volume"] or 0.0), 2)
    my_cnt = int(cust_stats["txn_count"] or 0)
    my_xb = int(cust_stats["xborder_cnt"] or 0)
    return {
        "customer_id": customer_id,
        "cohort": f"{cust['segment']} • {cust['kyc_tier']}",
        "cohort_sample_size": len(cohort_rows),
        "customer_volume": my_vol,
        "cohort_mean_volume": cohort_mean_vol,
        "cohort_p95_volume": cohort_p95_vol,
        "volume_ratio_to_mean": round(my_vol / max(1.0, cohort_mean_vol), 2),
        "customer_avg_ticket": round(float(cust_stats["avg_amount"] or 0.0), 2),
        "cohort_mean_ticket": cohort_mean_ticket,
        "cross_border_pct": round((my_xb / my_cnt) * 100.0, 1) if my_cnt else 0.0,
    }


def list_kyc_reviews(conn: sqlite3.Connection, customer_id: str) -> list[dict[str, Any]]:
    ensure_forensics_schema(conn)
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM kyc_reviews WHERE customer_id = ? ORDER BY reviewed_at DESC", (customer_id,)).fetchall()
    ]


def submit_kyc_review(
    conn: sqlite3.Connection,
    *,
    customer_id: str,
    outcome: str,
    risk_justification: str,
    reviewer_id: str,
) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    if not conn.execute("SELECT 1 FROM customers WHERE customer_id = ?", (customer_id,)).fetchone():
        raise ValueError(f"Customer {customer_id} not found")
    out = outcome.strip().upper()
    if out not in VALID_KYC_OUTCOMES:
        raise ValueError(f"Invalid KYC review outcome '{out}'")
    if not risk_justification.strip():
        raise ValueError("risk_justification is required")
    rid = _new_id("KYC")
    now = _now_iso()
    conn.execute(
        "INSERT INTO kyc_reviews (review_id, customer_id, outcome, risk_justification, reviewer_id, reviewed_at) VALUES (?, ?, ?, ?, ?, ?)",
        (rid, customer_id, out, risk_justification.strip(), reviewer_id, now),
    )
    if out == "VERIFIED":
        conn.execute("UPDATE customers SET kyc_verified_at = ? WHERE customer_id = ?", (now, customer_id))
    conn.commit()
    return {"review_id": rid, "customer_id": customer_id, "outcome": out, "risk_justification": risk_justification.strip(), "reviewer_id": reviewer_id, "reviewed_at": now}


def get_account_control(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    row = conn.execute("SELECT * FROM account_controls WHERE account_id = ?", (account_id,)).fetchone()
    if row:
        return dict(row)
    return {"account_id": account_id, "control_status": "NONE", "reason": None, "updated_by": None, "updated_at": None}


def set_account_control(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    control_status: str,
    reason: str,
    actor_id: str,
    actor_role: str,
) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    if not conn.execute("SELECT 1 FROM accounts WHERE account_id = ?", (account_id,)).fetchone():
        raise ValueError(f"Account {account_id} not found")
    ctrl = control_status.strip().upper()
    if ctrl not in VALID_ACCOUNT_CONTROLS:
        raise ValueError(f"Invalid control_status '{ctrl}'. Allowed: {', '.join(VALID_ACCOUNT_CONTROLS)}")
    if ctrl == "FULL_FREEZE" and actor_role not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
        raise PermissionError("FULL_FREEZE requires RISK_REVIEWER or SYSTEM_ADMIN role")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO account_controls (account_id, control_status, reason, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(account_id) DO UPDATE SET
            control_status = excluded.control_status,
            reason = excluded.reason,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        (account_id, ctrl, reason.strip() or f"Control set to {ctrl}", actor_id, now),
    )
    conn.commit()
    return get_account_control(conn, account_id)


def get_account_velocity(conn: sqlite3.Connection, account_id: str) -> dict[str, Any]:
    """Return daily credit/debit velocity buckets for Account 360 sparkline visualization."""
    rows = conn.execute(
        """
        SELECT SUBSTR(occurred_at, 1, 10) AS day,
               COUNT(*) AS txn_count,
               COALESCE(SUM(CASE WHEN direction = 'CREDIT' THEN amount ELSE 0 END), 0) AS credits,
               COALESCE(SUM(CASE WHEN direction != 'CREDIT' THEN amount ELSE 0 END), 0) AS debits
        FROM transactions
        WHERE account_id = ?
        GROUP BY day
        ORDER BY day ASC
        LIMIT 60
        """,
        (account_id,),
    ).fetchall()
    buckets = [
        {
            "day": r["day"],
            "txn_count": int(r["txn_count"] or 0),
            "credits": round(float(r["credits"] or 0.0), 2),
            "debits": round(float(r["debits"] or 0.0), 2),
        }
        for r in rows
    ]
    return {"account_id": account_id, "buckets": buckets}


# ------------------------------------------------------------------
# Functions 186-195: Pins, Escalations, Playbooks, Comments, RFI, Radar, Rebalance, Suppressions
# ------------------------------------------------------------------
def list_case_pins(conn: sqlite3.Connection, case_id: str) -> list[dict[str, Any]]:
    ensure_forensics_schema(conn)
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM case_evidence_pins WHERE case_id = ? ORDER BY created_at DESC", (case_id,)).fetchall()
    ]


def add_case_pin(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    entity_type: str,
    entity_id: str,
    pin_type: str = "PINNED_PROOF",
    note: str = "",
    actor_id: str = "ANL-001",
) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    if not conn.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone():
        raise ValueError(f"Case {case_id} not found")
    pt = pin_type.strip().upper()
    if pt not in VALID_PIN_TYPES:
        raise ValueError(f"Invalid pin_type '{pt}'")
    pid = _new_id("PIN")
    now = _now_iso()
    conn.execute(
        """
        INSERT INTO case_evidence_pins (pin_id, case_id, entity_type, entity_id, pin_type, note, actor_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id, entity_type, entity_id) DO UPDATE SET
            pin_type = excluded.pin_type,
            note = excluded.note,
            actor_id = excluded.actor_id,
            created_at = excluded.created_at
        """,
        (pid, case_id, entity_type.strip().upper(), entity_id.strip(), pt, note.strip(), actor_id, now),
    )
    conn.commit()
    return dict(
        conn.execute(
            "SELECT * FROM case_evidence_pins WHERE case_id = ? AND entity_type = ? AND entity_id = ?",
            (case_id, entity_type.strip().upper(), entity_id.strip()),
        ).fetchone()
    )


def delete_case_pin(conn: sqlite3.Connection, *, case_id: str, pin_id: str) -> bool:
    ensure_forensics_schema(conn)
    cur = conn.execute("DELETE FROM case_evidence_pins WHERE case_id = ? AND pin_id = ?", (case_id, pin_id))
    conn.commit()
    return cur.rowcount > 0


def list_case_comments(conn: sqlite3.Connection, case_id: str) -> list[dict[str, Any]]:
    ensure_forensics_schema(conn)
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM case_comments WHERE case_id = ? ORDER BY created_at DESC", (case_id,)).fetchall()
    ]


def add_case_comment(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    actor_id: str,
    actor_role: str,
    body: str,
    visibility: str = "INTERNAL",
) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    if not conn.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone():
        raise ValueError(f"Case {case_id} not found")
    clean = body.strip()
    if not clean:
        raise ValueError("Comment body cannot be empty")
    vis = visibility.strip().upper()
    if vis not in {"INTERNAL", "COMPLIANCE"}:
        vis = "INTERNAL"
    cid = _new_id("CMT")
    now = _now_iso()
    conn.execute(
        "INSERT INTO case_comments (comment_id, case_id, actor_id, actor_role, visibility, body, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (cid, case_id, actor_id, actor_role, vis, clean, now),
    )
    conn.commit()
    return {"comment_id": cid, "case_id": case_id, "actor_id": actor_id, "actor_role": actor_role, "visibility": vis, "body": clean, "created_at": now}


def get_playbooks() -> list[dict[str, Any]]:
    return PLAYBOOKS


def apply_playbook_to_case(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    playbook_id: str,
    actor_id: str,
    actor_role: str,
) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    pb = next((p for p in PLAYBOOKS if p["playbook_id"] == playbook_id), None)
    if not pb:
        raise ValueError(f"Playbook {playbook_id} not found")
    if not conn.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone():
        raise ValueError(f"Case {case_id} not found")

    now = _now_iso()
    steps_txt = f"[Playbook {pb['playbook_id']} — {pb['title']}]\n" + "\n".join(pb["steps"])
    upd = pb["checklist_updates"]
    cur = conn.execute("SELECT * FROM case_evidence_checklist WHERE case_id = ?", (case_id,)).fetchone()
    prev_notes = (cur["notes"] + "\n\n") if cur and cur["notes"] else ""
    conn.execute(
        """
        INSERT INTO case_evidence_checklist (case_id, rules_reviewed, ledger_reconciled, network_verified, kyc_corroborated, notes, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(case_id) DO UPDATE SET
            rules_reviewed = MAX(case_evidence_checklist.rules_reviewed, excluded.rules_reviewed),
            ledger_reconciled = MAX(case_evidence_checklist.ledger_reconciled, excluded.ledger_reconciled),
            network_verified = MAX(case_evidence_checklist.network_verified, excluded.network_verified),
            kyc_corroborated = MAX(case_evidence_checklist.kyc_corroborated, excluded.kyc_corroborated),
            notes = ?,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at
        """,
        (
            case_id,
            int(bool(upd.get("rules_reviewed", False))),
            int(bool(upd.get("ledger_reconciled", False))),
            int(bool(upd.get("network_verified", False))),
            int(bool(upd.get("kyc_corroborated", False))),
            steps_txt,
            actor_id,
            now,
            prev_notes + steps_txt,
        ),
    )
    add_case_comment(
        conn,
        case_id=case_id,
        actor_id=actor_id,
        actor_role=actor_role,
        visibility="COMPLIANCE",
        body=f"Applied SOP Playbook {pb['playbook_id']}: {pb['title']}",
    )
    return {"case_id": case_id, "playbook": pb, "applied_at": now}


def list_pending_escalations(conn: sqlite3.Connection, *, limit: int = 80) -> dict[str, Any]:
    """Return active cases awaiting four-eyes Reviewer/Admin sign-off (>= $25k exposure or ESCALATED)."""
    rows = [
        dict(r)
        for r in conn.execute(
            """
            SELECT c.case_id, c.primary_customer_id, cu.full_name AS customer_name,
                   c.primary_account_id, c.priority_tier, c.priority_score,
                   c.total_exposure_amount, c.status, c.created_at,
                   ctm.assigned_analyst_id
            FROM cases c
            JOIN customers cu ON cu.customer_id = c.primary_customer_id
            LEFT JOIN case_triage_meta ctm ON ctm.case_id = c.case_id
            WHERE c.status IN ('ESCALATED', 'OPEN', 'IN_REVIEW')
              AND (c.status = 'ESCALATED' OR c.total_exposure_amount >= 25000.0)
            ORDER BY CASE WHEN c.status = 'ESCALATED' THEN 1 ELSE 2 END, c.priority_score DESC, c.total_exposure_amount DESC
            LIMIT ?
            """,
            (max(1, min(200, int(limit))),),
        ).fetchall()
    ]
    return {"total": len(rows), "items": rows}


def generate_rfi_packet(conn: sqlite3.Connection, case_id: str) -> dict[str, Any] | None:
    """Synthesize structured FinCEN 314(b) / correspondent Request-for-Information packet."""
    c_row = conn.execute(
        """
        SELECT c.*, cu.full_name, cu.home_country, cu.kyc_tier, cu.segment
        FROM cases c JOIN customers cu ON cu.customer_id = c.primary_customer_id
        WHERE c.case_id = ?
        """,
        (case_id,),
    ).fetchone()
    if not c_row:
        return None
    c = dict(c_row)
    countries = [
        r["counterparty_country"]
        for r in conn.execute(
            """
            SELECT DISTINCT t.counterparty_country
            FROM transactions t
            WHERE t.account_id = ? AND COALESCE(t.counterparty_country, '') != ''
            LIMIT 10
            """,
            (c["primary_account_id"],),
        ).fetchall()
    ]
    md = "\n".join(
        [
            f"# FinCEN 314(b) / Correspondent RFI Inquiry — {case_id}",
            f"- **Generated:** {_now_iso()}",
            f"- **Subject:** {c['full_name']} (`{c['primary_customer_id']}` • {c['kyc_tier']} / {c['segment']})",
            f"- **Primary Account:** `{c['primary_account_id']}`",
            f"- **Case Exposure:** ${float(c['total_exposure_amount']):,.2f} ({c['priority_tier']} • Score {c['priority_score']})",
            f"- **Counterparty Corridors:** {', '.join(countries) or 'DOMESTIC'}",
            "",
            "## Requested Corroboration",
            "1. Confirm beneficial ownership and source-of-funds provenance for incoming correspondent wires.",
            "2. Provide device/IP session attribution for cross-border transfers within the investigation window.",
            "3. Advise whether subject entity is under active compliance monitoring or Section 314(b) notice.",
        ]
    )
    return {"case_id": case_id, "corridors": countries, "markdown": md, "generated_at": _now_iso()}


def get_sla_radar(conn: sqlite3.Connection, *, warning_hours: int = 8) -> dict[str, Any]:
    """Identify active cases near or past configured SLA targets relative to dataset watermark."""
    ref_row = conn.execute("SELECT MAX(created_at) FROM cases").fetchone()
    ref_dt = _parse_dt(ref_row[0]) if ref_row and ref_row[0] else None
    policy_map = get_sla_policies(conn)["map"].get("CASE", {})

    rows = conn.execute(
        """
        SELECT c.case_id, c.priority_tier, c.priority_score, c.status, c.total_exposure_amount, c.created_at,
               cu.full_name AS customer_name, ctm.assigned_analyst_id,
               COALESCE(ctm.priority_override_tier, c.priority_tier) AS effective_tier,
               ctm.sla_hours AS custom_sla
        FROM cases c
        JOIN customers cu ON cu.customer_id = c.primary_customer_id
        LEFT JOIN case_triage_meta ctm ON ctm.case_id = c.case_id
        WHERE c.status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')
        """
    ).fetchall()

    breached: list[dict[str, Any]] = []
    at_risk: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r)
        cdt = _parse_dt(d["created_at"])
        age_h = round(max(0.0, (ref_dt - cdt).total_seconds() / 3600.0), 1) if ref_dt and cdt else 0.0
        target = int(d["custom_sla"]) if d["custom_sla"] is not None else int(policy_map.get(d["effective_tier"], 48))
        rem_h = round(target - age_h, 1)
        item = {
            "case_id": d["case_id"],
            "customer_name": d["customer_name"],
            "priority_tier": d["effective_tier"],
            "priority_score": float(d["priority_score"]),
            "status": d["status"],
            "assigned_analyst_id": d["assigned_analyst_id"],
            "sla_target_hours": target,
            "age_hours": age_h,
            "hours_remaining": rem_h,
        }
        if rem_h <= 0:
            breached.append(item)
        elif rem_h <= float(warning_hours):
            at_risk.append(item)

    breached.sort(key=lambda x: (x["hours_remaining"], -x["priority_score"]))
    at_risk.sort(key=lambda x: (x["hours_remaining"], -x["priority_score"]))
    return {
        "breached_count": len(breached),
        "at_risk_count": len(at_risk),
        "breached": breached[:40],
        "at_risk": at_risk[:40],
    }


def rebalance_queue_workload(
    conn: sqlite3.Connection,
    *,
    actor_id: str,
    actor_role: str,
    limit: int = 30,
) -> dict[str, Any]:
    """Round-robin assign unassigned active cases across active OPS_ANALYST users."""
    if actor_role not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
        raise PermissionError("Queue workload rebalancing requires RISK_REVIEWER or SYSTEM_ADMIN role")
    analysts = [
        r["analyst_code"]
        for r in conn.execute("SELECT analyst_code FROM app_users WHERE role = 'OPS_ANALYST' AND is_active = 1 ORDER BY analyst_code").fetchall()
    ]
    if not analysts:
        analysts = ["ANL-001", "ANL-002"]

    unassigned = [
        r["case_id"]
        for r in conn.execute(
            """
            SELECT c.case_id FROM cases c
            LEFT JOIN case_triage_meta ctm ON ctm.case_id = c.case_id
            WHERE c.status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')
              AND ctm.assigned_analyst_id IS NULL
            ORDER BY c.priority_score DESC, c.total_exposure_amount DESC
            LIMIT ?
            """,
            (max(1, min(200, int(limit))),),
        ).fetchall()
    ]
    now = _now_iso()
    assignments = []
    for idx, cid in enumerate(unassigned):
        assignee = analysts[idx % len(analysts)]
        conn.execute(
            """
            INSERT INTO case_triage_meta (case_id, assigned_analyst_id, override_by, override_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                assigned_analyst_id = excluded.assigned_analyst_id,
                override_by = excluded.override_by,
                override_at = excluded.override_at
            """,
            (cid, assignee, actor_id, now),
        )
        assignments.append({"case_id": cid, "assigned_analyst_id": assignee})
    conn.commit()
    return {"reassigned_count": len(assignments), "analysts_pool": analysts, "assignments": assignments}


def list_suppression_rules(conn: sqlite3.Connection, *, active_only: bool = True) -> list[dict[str, Any]]:
    ensure_forensics_schema(conn)
    sql = "SELECT * FROM suppression_rules" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY created_at DESC"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def create_suppression_rule(
    conn: sqlite3.Connection,
    *,
    account_id: str,
    rule_id: str,
    max_amount: float,
    reason: str,
    days_valid: int = 90,
    actor_id: str = "ANL-001",
) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    if not account_id.strip() or not rule_id.strip():
        raise ValueError("account_id and rule_id are required")
    sid = _new_id("SUP")
    now_dt = datetime.now(timezone.utc)
    exp_dt = now_dt + timedelta(days=max(1, min(365, int(days_valid))))
    now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    exp = exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute(
        """
        INSERT INTO suppression_rules (suppression_id, account_id, rule_id, max_amount, reason, expires_at, created_by, created_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (sid, account_id.strip(), rule_id.strip().upper(), float(max_amount), reason.strip() or "Verified recurring activity", exp, actor_id, now),
    )
    conn.commit()
    return dict(conn.execute("SELECT * FROM suppression_rules WHERE suppression_id = ?", (sid,)).fetchone())


def deactivate_suppression_rule(conn: sqlite3.Connection, suppression_id: str) -> bool:
    ensure_forensics_schema(conn)
    cur = conn.execute("UPDATE suppression_rules SET is_active = 0 WHERE suppression_id = ?", (suppression_id,))
    conn.commit()
    return cur.rowcount > 0


def match_suppression_for_alert(suppressions: list[dict[str, Any]], alert_row: dict[str, Any]) -> str | None:
    """Return matching suppression_id if an alert is covered by an active suppression rule."""
    now = _now_iso()
    acct = alert_row.get("account_id")
    rid = alert_row.get("rule_id")
    amt = float(alert_row.get("trigger_total_amount") or 0.0)
    for s in suppressions:
        if (
            s.get("is_active") == 1
            and s.get("account_id") == acct
            and s.get("rule_id") == rid
            and amt <= float(s.get("max_amount") or 0.0)
            and str(s.get("expires_at") or "") >= now
        ):
            return str(s["suppression_id"])
    return None


def log_export_event(
    conn: sqlite3.Connection,
    *,
    actor_id: str,
    export_type: str,
    fmt: str,
    filter_summary: str = "",
    row_count: int = 0,
) -> dict[str, Any]:
    ensure_forensics_schema(conn)
    eid = _new_id("EXP")
    now = _now_iso()
    conn.execute(
        "INSERT INTO export_history (export_id, actor_id, export_type, fmt, filter_summary, row_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (eid, actor_id, export_type, fmt.upper(), filter_summary[:240], int(row_count), now),
    )
    conn.commit()
    return {"export_id": eid, "actor_id": actor_id, "export_type": export_type, "fmt": fmt.upper(), "row_count": int(row_count), "created_at": now}


def list_export_history(conn: sqlite3.Connection, *, limit: int = 100) -> list[dict[str, Any]]:
    ensure_forensics_schema(conn)
    return [
        dict(r)
        for r in conn.execute("SELECT * FROM export_history ORDER BY created_at DESC LIMIT ?", (max(1, min(300, int(limit))),)).fetchall()
    ]

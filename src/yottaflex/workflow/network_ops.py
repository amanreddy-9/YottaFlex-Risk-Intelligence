"""Entity Network Rings, SAR Registry & Filing Lifecycle, Similar Cases, Executive Digest & Search (Functions 160-174)."""

from __future__ import annotations

import json
import secrets
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yottaflex.workflow.governance_ops import ensure_governance_schema


VALID_SAR_STATUSES = ("DRAFT", "READY_FOR_FILING", "SUBMITTED")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


# ------------------------------------------------------------------
# Functions 160-163: Multi-Hop Entity Link Explorer & Risk Rings
# ------------------------------------------------------------------
def get_entity_network(conn: sqlite3.Connection, entity_id: str) -> dict[str, Any] | None:
    """Build 1-hop & 2-hop graph neighborhood across accounts, customers, devices & transfers."""
    eid = entity_id.strip()
    if not eid:
        return None

    seed_accounts: list[str] = []
    root_type = "UNKNOWN"
    root_label = eid

    if eid.startswith("CUS-"):
        cust = conn.execute("SELECT customer_id, full_name FROM customers WHERE customer_id = ?", (eid,)).fetchone()
        if not cust:
            return None
        root_type = "CUSTOMER"
        root_label = cust["full_name"]
        seed_accounts = [
            r["account_id"]
            for r in conn.execute("SELECT account_id FROM account_ownerships WHERE customer_id = ?", (eid,)).fetchall()
        ]
    elif eid.startswith("ACC-"):
        acct = conn.execute("SELECT account_id, account_type FROM accounts WHERE account_id = ?", (eid,)).fetchone()
        if not acct:
            return None
        root_type = "ACCOUNT"
        root_label = f"{acct['account_id']} ({acct['account_type']})"
        seed_accounts = [eid]
    elif eid.startswith("CASE-"):
        ca = conn.execute("SELECT case_id, primary_account_id, primary_customer_id FROM cases WHERE case_id = ?", (eid,)).fetchone()
        if not ca:
            return None
        root_type = "CASE"
        root_label = ca["case_id"]
        seed_accounts = [
            r["account_id"]
            for r in conn.execute("SELECT account_id FROM account_ownerships WHERE customer_id = ?", (ca["primary_customer_id"],)).fetchall()
        ]
        if ca["primary_account_id"] and ca["primary_account_id"] not in seed_accounts:
            seed_accounts.append(ca["primary_account_id"])
    elif eid.startswith("DEV-"):
        dev = conn.execute("SELECT device_id, os_family, risk_tier FROM devices WHERE device_id = ?", (eid,)).fetchone()
        if not dev:
            return None
        root_type = "DEVICE"
        root_label = f"{dev['device_id']} ({dev['os_family']})"
        seed_accounts = [
            r["account_id"]
            for r in conn.execute("SELECT account_id FROM account_device_links WHERE device_id = ?", (eid,)).fetchall()
        ]
    else:
        return None

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(nid: str, ntype: str, label: str, risk: str = "LOW", meta: dict[str, Any] | None = None) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": label, "risk": risk, "meta": meta or {}}

    def add_edge(src: str, dst: str, rel: str, weight: float = 0.0) -> None:
        key = (src, dst, rel)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append({"source": src, "target": dst, "relation": rel, "exposure": round(weight, 2)})

    add_node(eid, root_type, root_label, "HIGH")

    if seed_accounts:
        ph = ",".join(["?"] * len(seed_accounts))
        for r in conn.execute(
            f"""
            SELECT ao.account_id, ao.customer_id, cu.full_name, cu.risk_rating, a.status, a.current_balance
            FROM account_ownerships ao
            JOIN customers cu ON cu.customer_id = ao.customer_id
            JOIN accounts a ON a.account_id = ao.account_id
            WHERE ao.account_id IN ({ph})
            """,
            seed_accounts,
        ).fetchall():
            add_node(r["account_id"], "ACCOUNT", r["account_id"], "HIGH" if r["status"] != "ACTIVE" else "MEDIUM", {"balance": r["current_balance"]})
            add_node(r["customer_id"], "CUSTOMER", r["full_name"], r["risk_rating"])
            add_edge(r["customer_id"], r["account_id"], "OWNS", float(r["current_balance"] or 0.0))
            if root_type == "CASE":
                add_edge(eid, r["account_id"], "INVESTIGATES")

        # Shared devices (1-hop & 2-hop via other accounts using same device)
        dev_rows = conn.execute(
            f"""
            SELECT adl.account_id, adl.device_id, d.os_family, d.is_emulator, d.ip_country, d.risk_tier
            FROM account_device_links adl
            JOIN devices d ON d.device_id = adl.device_id
            WHERE adl.account_id IN ({ph})
            """,
            seed_accounts,
        ).fetchall()
        device_ids = sorted({r["device_id"] for r in dev_rows})
        for r in dev_rows:
            add_node(r["device_id"], "DEVICE", f"{r['device_id']} ({r['ip_country']})", r["risk_tier"], {"emulator": bool(r["is_emulator"])})
            add_edge(r["account_id"], r["device_id"], "USES_DEVICE")

        if device_ids:
            dph = ",".join(["?"] * len(device_ids))
            for peer in conn.execute(
                f"""
                SELECT adl.device_id, adl.account_id, cu.customer_id, cu.full_name, cu.risk_rating
                FROM account_device_links adl
                JOIN account_ownerships ao ON ao.account_id = adl.account_id
                JOIN customers cu ON cu.customer_id = ao.customer_id
                WHERE adl.device_id IN ({dph})
                LIMIT 60
                """,
                device_ids,
            ).fetchall():
                add_node(peer["account_id"], "ACCOUNT", peer["account_id"], "MEDIUM")
                add_node(peer["customer_id"], "CUSTOMER", peer["full_name"], peer["risk_rating"])
                add_edge(peer["account_id"], peer["device_id"], "SHARED_DEVICE")
                add_edge(peer["customer_id"], peer["account_id"], "OWNS")

        # Internal transfer counterparties
        for tr in conn.execute(
            f"""
            SELECT tl.source_account_id, tl.dest_account_id, SUM(tl.transfer_amount) AS vol, COUNT(*) AS cnt
            FROM transfer_links tl
            WHERE tl.source_account_id IN ({ph}) OR tl.dest_account_id IN ({ph})
            GROUP BY tl.source_account_id, tl.dest_account_id
            LIMIT 60
            """,
            (*seed_accounts, *seed_accounts),
        ).fetchall():
            add_node(tr["source_account_id"], "ACCOUNT", tr["source_account_id"], "MEDIUM")
            add_node(tr["dest_account_id"], "ACCOUNT", tr["dest_account_id"], "MEDIUM")
            add_edge(tr["source_account_id"], tr["dest_account_id"], f"TRANSFER ({tr['cnt']}x)", float(tr["vol"] or 0.0))

    total_exposure = round(sum(e["exposure"] for e in edges if "TRANSFER" in e["relation"]), 2)
    return {
        "root_id": eid,
        "root_type": root_type,
        "root_label": root_label,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "transfer_exposure": total_exposure,
        "nodes": list(nodes.values()),
        "edges": edges,
    }


def detect_collusion_rings(conn: sqlite3.Connection, *, min_accounts: int = 2, limit: int = 20) -> dict[str, Any]:
    """Detect shared-device collusion rings across distinct customers ranked by exposure & alert hit."""
    rows = conn.execute(
        """
        SELECT adl.device_id, d.os_family, d.ip_country, d.is_emulator, d.risk_tier,
               COUNT(DISTINCT adl.account_id) AS account_count,
               COUNT(DISTINCT ao.customer_id) AS customer_count,
               GROUP_CONCAT(DISTINCT ao.customer_id) AS customer_ids,
               GROUP_CONCAT(DISTINCT adl.account_id) AS account_ids
        FROM account_device_links adl
        JOIN devices d ON d.device_id = adl.device_id
        JOIN account_ownerships ao ON ao.account_id = adl.account_id
        GROUP BY adl.device_id
        HAVING COUNT(DISTINCT ao.customer_id) >= ?
        ORDER BY customer_count DESC, account_count DESC, d.is_emulator DESC
        LIMIT ?
        """,
        (max(2, int(min_accounts)), max(1, min(100, int(limit)))),
    ).fetchall()

    rings: list[dict[str, Any]] = []
    for idx, r in enumerate(rows, start=1):
        acct_ids = (r["account_ids"] or "").split(",") if r["account_ids"] else []
        cust_ids = (r["customer_ids"] or "").split(",") if r["customer_ids"] else []
        exp_row = None
        if acct_ids:
            ph = ",".join(["?"] * len(acct_ids))
            exp_row = conn.execute(
                f"""
                SELECT COUNT(DISTINCT a.alert_id) AS alert_count,
                       COALESCE(SUM(a.trigger_total_amount), 0) AS alert_exposure,
                       MAX(a.risk_score) AS max_alert_score
                FROM alerts a
                WHERE a.account_id IN ({ph})
                """,
                acct_ids,
            ).fetchone()
        rings.append(
            {
                "ring_id": f"RING-{idx:03d}",
                "device_id": r["device_id"],
                "os_family": r["os_family"],
                "ip_country": r["ip_country"],
                "is_emulator": bool(r["is_emulator"]),
                "device_risk_tier": r["risk_tier"],
                "customer_count": int(r["customer_count"]),
                "account_count": int(r["account_count"]),
                "customer_ids": cust_ids[:12],
                "account_ids": acct_ids[:12],
                "alert_count": int(exp_row["alert_count"] or 0) if exp_row else 0,
                "alert_exposure": round(float(exp_row["alert_exposure"] or 0.0), 2) if exp_row else 0.0,
                "max_alert_score": round(float(exp_row["max_alert_score"] or 0.0), 2) if exp_row else 0.0,
            }
        )

    rings.sort(key=lambda x: (-x["customer_count"], -x["alert_exposure"], x["device_id"]))
    return {"total_rings": len(rings), "rings": rings}


# ------------------------------------------------------------------
# Functions 164-166: SAR Registry, Completeness Score & Lifecycle
# ------------------------------------------------------------------
def evaluate_sar_readiness(sar_text: str | None, case_row: dict[str, Any]) -> dict[str, Any]:
    """Score SAR compliance completeness (0-100%) across 5 regulatory criteria."""
    text = (sar_text or "").strip()
    lower = text.lower()
    checks = {
        "has_subject_identity": str(case_row.get("primary_customer_id", "")).lower() in lower or "subject" in lower,
        "has_narrative_depth": len(text.split()) >= 25,
        "has_rule_citations": ("r0" in lower) or ("typology" in lower) or ("rule" in lower),
        "has_exposure_amount": ("$" in text) or ("exposure" in lower) or ("usd" in lower),
        "has_disposition_rationale": ("suspicious" in lower) or ("activity" in lower) or ("filing" in lower) or ("sar" in lower),
    }
    passed = sum(1 for v in checks.values() if v)
    score = int(round((passed / 5.0) * 100))
    return {"readiness_score": score, "passed_criteria": passed, "total_criteria": 5, "criteria": checks}


def list_sar_registry(conn: sqlite3.Connection, *, status: str = "ALL", limit: int = 100) -> dict[str, Any]:
    """List all SAR drafts & filed cases with completeness scores and lifecycle statuses."""
    ensure_governance_schema(conn)
    rows = conn.execute(
        """
        SELECT c.case_id, c.primary_customer_id, cu.full_name AS customer_name,
               c.primary_account_id, c.priority_tier, c.priority_score,
               c.total_exposure_amount, c.status AS case_status,
               ctm.assigned_analyst_id, ctm.sar_draft, ctm.sar_updated_at,
               COALESCE(ctm.sar_status, CASE WHEN c.status = 'SAR_FILED' THEN 'SUBMITTED' ELSE 'DRAFT' END) AS sar_status
        FROM cases c
        JOIN customers cu ON cu.customer_id = c.primary_customer_id
        LEFT JOIN case_triage_meta ctm ON ctm.case_id = c.case_id
        WHERE (ctm.sar_draft IS NOT NULL AND TRIM(ctm.sar_draft) != '') OR c.status = 'SAR_FILED'
        ORDER BY COALESCE(ctm.sar_updated_at, c.updated_at) DESC, c.priority_score DESC
        LIMIT ?
        """,
        (max(1, min(500, int(limit))),),
    ).fetchall()

    items: list[dict[str, Any]] = []
    counts = {"DRAFT": 0, "READY_FOR_FILING": 0, "SUBMITTED": 0}
    for r in rows:
        d = dict(r)
        st_val = d["sar_status"] if d["sar_status"] in VALID_SAR_STATUSES else "DRAFT"
        counts[st_val] = counts.get(st_val, 0) + 1
        if status and status != "ALL" and st_val != status:
            continue
        readiness = evaluate_sar_readiness(d.get("sar_draft"), d)
        items.append(
            {
                "case_id": d["case_id"],
                "customer_id": d["primary_customer_id"],
                "customer_name": d["customer_name"],
                "account_id": d["primary_account_id"],
                "priority_tier": d["priority_tier"],
                "priority_score": float(d["priority_score"]),
                "total_exposure_amount": float(d["total_exposure_amount"]),
                "case_status": d["case_status"],
                "assigned_analyst_id": d["assigned_analyst_id"],
                "sar_status": st_val,
                "sar_updated_at": d["sar_updated_at"],
                "sar_excerpt": (d.get("sar_draft") or "")[:180],
                "readiness": readiness,
            }
        )
    return {"total": len(items), "counts_by_status": counts, "items": items}


def transition_sar_status(
    conn: sqlite3.Connection,
    *,
    case_id: str,
    sar_status: str,
    actor_id: str,
    actor_role: str,
    note: str = "",
) -> dict[str, Any]:
    """Transition SAR draft lifecycle status (DRAFT -> READY_FOR_FILING -> SUBMITTED)."""
    ensure_governance_schema(conn)
    next_status = str(sar_status or "").upper()
    if next_status not in VALID_SAR_STATUSES:
        raise ValueError(f"Invalid sar_status '{next_status}'. Allowed: {', '.join(VALID_SAR_STATUSES)}")
    if next_status == "SUBMITTED" and actor_role not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
        raise PermissionError("Finalizing SAR status as SUBMITTED requires RISK_REVIEWER or SYSTEM_ADMIN role")

    case_row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not case_row:
        raise ValueError(f"Case {case_id} not found")
    meta = conn.execute("SELECT * FROM case_triage_meta WHERE case_id = ?", (case_id,)).fetchone()
    if not meta or not (meta["sar_draft"] or "").strip():
        raise ValueError("Cannot transition SAR status before a SAR narrative draft exists")

    now = _now_iso()
    conn.execute(
        "UPDATE case_triage_meta SET sar_status = ?, sar_updated_at = ? WHERE case_id = ?",
        (next_status, now, case_id),
    )

    action_id = _new_id("ACT")
    event_id = _new_id("CEV")
    conn.execute(
        """
        INSERT INTO analyst_actions (action_id, case_id, analyst_id, analyst_role, action_type, rationale, acted_at)
        VALUES (?, ?, ?, ?, 'SAR_STATUS_UPDATE', ?, ?)
        """,
        (action_id, case_id, actor_id, actor_role, note.strip() or f"SAR transitioned to {next_status}", now),
    )
    conn.execute(
        """
        INSERT INTO case_state_events (case_event_id, case_id, prev_status, new_status, analyst_action_id, effective_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (event_id, case_id, case_row["status"], "SAR_FILED" if next_status == "SUBMITTED" else case_row["status"], action_id, now),
    )
    if next_status == "SUBMITTED":
        conn.execute("UPDATE cases SET status = 'SAR_FILED', updated_at = ? WHERE case_id = ?", (now, case_id))
    conn.commit()
    return {
        "case_id": case_id,
        "sar_status": next_status,
        "sar_updated_at": now,
        "readiness": evaluate_sar_readiness(meta["sar_draft"], dict(case_row)),
    }


# ------------------------------------------------------------------
# Functions 167-170, 172-174: Digest, Global Search, Similar Cases, Telemetry
# ------------------------------------------------------------------
def get_similar_cases(conn: sqlite3.Connection, case_id: str, *, limit: int = 5) -> dict[str, Any] | None:
    """Find top peer cases sharing rule triggers and similar exposure bands."""
    target = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
    if not target:
        return None
    target_rules = {
        r["rule_id"]
        for r in conn.execute(
            """
            SELECT DISTINCT a.rule_id FROM case_alert_links cal
            JOIN alerts a ON a.alert_id = cal.alert_id
            WHERE cal.case_id = ?
            """,
            (case_id,),
        ).fetchall()
    }
    target_exp = max(1.0, float(target["total_exposure_amount"] or 1.0))

    candidates = conn.execute(
        """
        SELECT c.case_id, c.primary_customer_id, cu.full_name AS customer_name,
               c.priority_tier, c.priority_score, c.total_exposure_amount, c.status, c.linkage_summary
        FROM cases c
        JOIN customers cu ON cu.customer_id = c.primary_customer_id
        WHERE c.case_id != ?
        ORDER BY ABS(c.priority_score - ?) ASC
        LIMIT 80
        """,
        (case_id, float(target["priority_score"])),
    ).fetchall()

    cand_ids = [r["case_id"] for r in candidates]
    cand_rules: dict[str, set[str]] = defaultdict(set)
    if cand_ids:
        ph = ",".join(["?"] * len(cand_ids))
        for rr in conn.execute(
            f"""
            SELECT DISTINCT cal.case_id, a.rule_id
            FROM case_alert_links cal JOIN alerts a ON a.alert_id = cal.alert_id
            WHERE cal.case_id IN ({ph})
            """,
            cand_ids,
        ).fetchall():
            cand_rules[rr["case_id"]].add(rr["rule_id"])

    scored: list[dict[str, Any]] = []
    for r in candidates:
        cid = r["case_id"]
        rset = cand_rules.get(cid, set())
        union = target_rules | rset
        jaccard = (len(target_rules & rset) / len(union)) if union else 0.0
        exp = max(1.0, float(r["total_exposure_amount"] or 1.0))
        exp_sim = min(target_exp, exp) / max(target_exp, exp)
        score_sim = max(0.0, 1.0 - abs(float(r["priority_score"]) - float(target["priority_score"])) / 100.0)
        overall = round((0.50 * jaccard + 0.30 * exp_sim + 0.20 * score_sim) * 100.0, 1)
        scored.append(
            {
                "case_id": cid,
                "customer_id": r["primary_customer_id"],
                "customer_name": r["customer_name"],
                "priority_tier": r["priority_tier"],
                "priority_score": round(float(r["priority_score"]), 2),
                "total_exposure_amount": round(float(r["total_exposure_amount"]), 2),
                "status": r["status"],
                "shared_rules": sorted(target_rules & rset),
                "similarity_pct": overall,
            }
        )
    scored.sort(key=lambda x: (-x["similarity_pct"], -x["priority_score"]))
    return {"case_id": case_id, "items": scored[: max(1, min(12, int(limit)))]}


def global_cross_entity_search(
    conn: sqlite3.Connection,
    base_quarantine: dict[str, Any],
    *,
    query: str,
    limit_per_group: int = 5,
) -> dict[str, Any]:
    """Unified sub-second cross-entity spotlight search across Cases, Alerts, Customers, Accounts, Txns & Quarantine."""
    q_raw = query.strip()
    if not q_raw:
        return {"query": "", "total_hits": 0, "groups": {}}
    q = f"%{q_raw}%"
    lim = max(1, min(15, int(limit_per_group)))

    cases = [
        dict(r)
        for r in conn.execute(
            """
            SELECT c.case_id AS id, cu.full_name AS title,
                   c.priority_tier || ' • $' || printf('%.2f', c.total_exposure_amount) AS subtitle,
                   c.status AS badge
            FROM cases c JOIN customers cu ON cu.customer_id = c.primary_customer_id
            WHERE c.case_id LIKE ? OR c.primary_customer_id LIKE ? OR c.primary_account_id LIKE ? OR cu.full_name LIKE ?
            ORDER BY c.priority_score DESC LIMIT ?
            """,
            (q, q, q, q, lim),
        ).fetchall()
    ]
    alerts = [
        dict(r)
        for r in conn.execute(
            """
            SELECT al.alert_id AS id, al.rule_id || ' • ' || cu.full_name AS title,
                   '$' || printf('%.2f', al.trigger_total_amount) || ' • ' || al.account_id AS subtitle,
                   al.severity AS badge
            FROM alerts al JOIN customers cu ON cu.customer_id = al.customer_id
            WHERE al.alert_id LIKE ? OR al.account_id LIKE ? OR al.customer_id LIKE ? OR cu.full_name LIKE ? OR COALESCE(al.primary_txn_id, '') LIKE ?
            ORDER BY al.risk_score DESC LIMIT ?
            """,
            (q, q, q, q, q, lim),
        ).fetchall()
    ]
    customers = [
        dict(r)
        for r in conn.execute(
            """
            SELECT customer_id AS id, full_name AS title,
                   kyc_tier || ' • ' || segment || ' • ' || email AS subtitle,
                   risk_rating AS badge
            FROM customers
            WHERE customer_id LIKE ? OR full_name LIKE ? OR email LIKE ?
            LIMIT ?
            """,
            (q, q, q, lim),
        ).fetchall()
    ]
    accounts = [
        dict(r)
        for r in conn.execute(
            """
            SELECT account_id AS id, account_id || ' (' || account_type || ')' AS title,
                   'Balance $' || printf('%.2f', current_balance) || ' • ' || currency AS subtitle,
                   status AS badge
            FROM accounts
            WHERE account_id LIKE ?
            LIMIT ?
            """,
            (q, lim),
        ).fetchall()
    ]
    txns = [
        dict(r)
        for r in conn.execute(
            """
            SELECT transaction_id AS id, txn_type || ' • $' || printf('%.2f', amount) AS title,
                   account_id || ' • ' || occurred_at AS subtitle,
                   status AS badge
            FROM transactions
            WHERE transaction_id LIKE ? OR account_id LIKE ? OR COALESCE(reference_note, '') LIKE ?
            ORDER BY occurred_at DESC LIMIT ?
            """,
            (q, q, q, lim),
        ).fetchall()
    ]

    ql = q_raw.lower()
    quarantine_hits = [
        {
            "id": ex["exception_id"],
            "title": f"{ex['issue_type']} • {ex['entity_id']}",
            "subtitle": ex["violated_invariant"],
            "badge": ex["severity"],
        }
        for ex in base_quarantine.get("exceptions", [])
        if ql in ex["exception_id"].lower()
        or ql in ex["entity_id"].lower()
        or ql in ex["account_id"].lower()
        or ql in ex["issue_type"].lower()
    ][:lim]

    groups = {
        "cases": cases,
        "alerts": alerts,
        "customers": customers,
        "accounts": accounts,
        "transactions": txns,
        "quarantine": quarantine_hits,
    }
    total_hits = sum(len(v) for v in groups.values())
    return {"query": q_raw, "total_hits": total_hits, "groups": groups}


def get_executive_digest(
    conn: sqlite3.Connection,
    *,
    overview: dict[str, Any],
    quarantine_filtered: dict[str, Any],
    ring_summary: dict[str, Any],
    sar_registry: dict[str, Any],
) -> dict[str, Any]:
    """Synthesize five-pillar executive compliance digest for leadership & regulators."""
    ensure_governance_schema(conn)
    c_row = conn.execute(
        """
        SELECT COUNT(*) AS total_cases,
               SUM(CASE WHEN status IN ('CLOSED_TP', 'CLOSED_FP', 'SAR_FILED') THEN 1 ELSE 0 END) AS resolved_cases,
               COALESCE(SUM(total_exposure_amount), 0) AS total_exposure,
               COALESCE(SUM(CASE WHEN priority_tier IN ('CRITICAL', 'HIGH') THEN total_exposure_amount ELSE 0 END), 0) AS high_tier_exposure
        FROM cases
        """
    ).fetchone()
    total_cases = int(c_row["total_cases"] or 0)
    resolved_cases = int(c_row["resolved_cases"] or 0)
    total_exp = round(float(c_row["total_exposure"] or 0.0), 2)
    high_exp = round(float(c_row["high_tier_exposure"] or 0.0), 2)

    q_total = int(quarantine_filtered.get("total_exceptions", 0))
    q_pending = int(quarantine_filtered.get("counts_by_review_status", {}).get("PENDING", 0))

    return {
        "generated_at": _now_iso(),
        "scale": overview.get("scale"),
        "seed": overview.get("seed"),
        "pillars": {
            "exposure_concentration": {
                "total_case_exposure": total_exp,
                "high_critical_exposure": high_exp,
                "high_critical_share_pct": round((high_exp / total_exp) * 100.0, 1) if total_exp else 0.0,
            },
            "alert_compression": {
                "alerts": overview.get("counts", {}).get("alerts", 0),
                "cases": total_cases,
                "compression_ratio": overview.get("alert_to_case_compression", 0.0),
            },
            "case_resolution": {
                "total_cases": total_cases,
                "resolved_cases": resolved_cases,
                "resolution_pct": round((resolved_cases / total_cases) * 100.0, 1) if total_cases else 0.0,
            },
            "quarantine_shield": {
                "total_quarantined": q_total,
                "pending_review": q_pending,
                "quarantined_exposure": quarantine_filtered.get("quarantined_exposure", 0.0),
            },
            "sar_readiness": {
                "total_sar_tracked": sar_registry.get("total", 0),
                "counts_by_status": sar_registry.get("counts_by_status", {}),
                "shared_device_rings": ring_summary.get("total_rings", 0),
            },
        },
    }


def export_executive_digest(digest: dict[str, Any], *, fmt: str = "md") -> tuple[bytes, str, str]:
    """Export Executive Compliance Digest as Markdown briefing or structured JSON."""
    if str(fmt).lower() == "json":
        return json.dumps(digest, indent=2).encode("utf-8"), "application/json; charset=utf-8", "yottaflex_executive_digest.json"

    p = digest["pillars"]
    md = "\n".join(
        [
            "# YottaFlex AML Compliance & Risk Executive Digest",
            f"- **Generated:** {digest['generated_at']}",
            f"- **Dataset Scale:** `{digest.get('scale')}` (Seed `{digest.get('seed')}`)",
            "",
            "## 1. Exposure Concentration",
            f"- Total Case Exposure: **${p['exposure_concentration']['total_case_exposure']:,.2f}**",
            f"- CRITICAL + HIGH Exposure: **${p['exposure_concentration']['high_critical_exposure']:,.2f}** ({p['exposure_concentration']['high_critical_share_pct']}%)",
            "",
            "## 2. Alert-to-Case Compression",
            f"- Alerts: **{p['alert_compression']['alerts']}** -> Cases: **{p['alert_compression']['cases']}**",
            f"- Compression Ratio: **{p['alert_compression']['compression_ratio']}x**",
            "",
            "## 3. Case Resolution Progress",
            f"- Resolved Cases: **{p['case_resolution']['resolved_cases']} / {p['case_resolution']['total_cases']}** ({p['case_resolution']['resolution_pct']}%)",
            "",
            "## 4. Data Integrity Quarantine Shield",
            f"- Isolated Exceptions: **{p['quarantine_shield']['total_quarantined']}** (Pending Review: **{p['quarantine_shield']['pending_review']}**)",
            f"- Quarantined Exposure: **${p['quarantine_shield']['quarantined_exposure']:,.2f}**",
            "",
            "## 5. SAR Filing & Collusion Ring Posture",
            f"- SAR Tracked Cases: **{p['sar_readiness']['total_sar_tracked']}** ({json.dumps(p['sar_readiness']['counts_by_status'])})",
            f"- Shared-Device Rings Detected: **{p['sar_readiness']['shared_device_rings']}**",
        ]
    )
    return md.encode("utf-8"), "text/markdown; charset=utf-8", "yottaflex_executive_digest.md"


def get_system_health(conn: sqlite3.Connection, *, db_path: Path, scale: str, seed: Any) -> dict[str, Any]:
    """Return live SQLite table row counts, index count, watermark & active sessions."""
    ensure_governance_schema(conn)
    table_counts = {}
    for tbl in (
        "customers",
        "accounts",
        "transactions",
        "alerts",
        "cases",
        "analyst_actions",
        "case_state_events",
        "alert_audit_events",
        "quarantine_reviews",
        "entity_watchlist_tags",
        "saved_views",
        "app_users",
    ):
        try:
            table_counts[tbl] = int(conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
        except sqlite3.OperationalError:
            table_counts[tbl] = 0

    indexes = int(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'").fetchone()[0])
    active_sessions = int(conn.execute("SELECT COUNT(*) FROM auth_sessions WHERE revoked = 0").fetchone()[0])
    watermark = conn.execute("SELECT MAX(occurred_at) FROM transactions").fetchone()[0]
    db_size_mb = round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0.0
    return {
        "status": "HEALTHY",
        "checked_at": _now_iso(),
        "scale": scale,
        "seed": seed,
        "db_size_mb": db_size_mb,
        "sqlite_index_count": indexes,
        "active_sessions": active_sessions,
        "ledger_watermark": watermark,
        "table_counts": table_counts,
    }

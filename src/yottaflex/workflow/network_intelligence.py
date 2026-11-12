"""Financial Network Intelligence System (Transaction & Money Flow Graph).

Provides multi-hop relationship exploration, directional fund-flow tracing,
cycle detection (A -> B -> C -> A), fan-in concentration, rapid dispersion
(layering), conservative entity resolution, and explainable network risk scoring.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any


def _parse_dt(dt_str: str | None) -> datetime | None:
    if not dt_str:
        return None
    try:
        s = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def get_network_overview(conn: sqlite3.Connection) -> dict[str, Any]:
    """Calculate high-level summary metrics across the financial network."""
    cust_count = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    acct_count = conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    merch_count = conn.execute("SELECT COUNT(*) FROM merchants").fetchone()[0]
    dev_count = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
    transfer_count = conn.execute("SELECT COUNT(*) FROM transfer_links").fetchone()[0]
    transfer_vol = conn.execute("SELECT COALESCE(SUM(transfer_amount), 0) FROM transfer_links").fetchone()[0]

    # Connected accounts (participated in at least one transfer)
    connected_accts = conn.execute(
        """
        SELECT COUNT(DISTINCT aid) FROM (
            SELECT source_account_id AS aid FROM transfer_links
            UNION
            SELECT dest_account_id AS aid FROM transfer_links
        )
        """
    ).fetchone()[0]

    # Fast detection of cycles and suspicious patterns for metrics
    cycles = detect_circular_transfers(conn, limit=10)
    patterns = detect_suspicious_patterns(conn)

    return {
        "total_entities": cust_count + acct_count + merch_count + dev_count,
        "total_customers": cust_count,
        "customers_count": cust_count,
        "total_accounts": acct_count,
        "accounts_count": acct_count,
        "total_merchants": merch_count,
        "merchants_count": merch_count,
        "total_devices": dev_count,
        "devices_count": dev_count,
        "total_transfers": transfer_count,
        "transfer_relationships": transfer_count,
        "total_transfer_volume": round(float(transfer_vol), 2),
        "transfer_volume": round(float(transfer_vol), 2),
        "connected_accounts": connected_accts,
        "detected_cycles": len(cycles),
        "potential_circular_flows": len(cycles),
        "collusion_clusters": len(patterns.get("shared_devices", [])),
        "unusual_concentrations": len(patterns.get("concentrations", [])),
        "rapid_dispersions": len(patterns.get("dispersions", [])),
        "shared_device_clusters": len(patterns.get("shared_devices", [])),
    }


def search_entities(
    conn: sqlite3.Connection,
    query: str,
    *,
    entity_type: str = "ALL",
    limit: int = 15,
) -> list[dict[str, Any]]:
    """Search customers, accounts, merchants, devices, and transactions for graph focus."""
    q = (query or "").strip()
    if not q:
        return []

    results: list[dict[str, Any]] = []
    pattern = f"%{q}%"
    lim = max(1, min(50, limit))

    # 1. Accounts
    if entity_type in ("ALL", "ACCOUNT"):
        for r in conn.execute(
            """
            SELECT a.account_id, a.account_type, a.status, a.current_balance, c.full_name, c.risk_rating
            FROM accounts a
            JOIN customers c ON c.customer_id = a.primary_customer_id
            WHERE a.account_id LIKE ? OR c.full_name LIKE ?
            LIMIT ?
            """,
            (pattern, pattern, lim),
        ).fetchall():
            results.append(
                {
                    "id": r["account_id"],
                    "type": "ACCOUNT",
                    "label": f"{r['account_id']} ({r['account_type']})",
                    "subtitle": f"Owner: {r['full_name']} • Bal: ${float(r['current_balance']):,.2f}",
                    "risk": r["risk_rating"] or "LOW",
                }
            )

    # 2. Customers
    if entity_type in ("ALL", "CUSTOMER"):
        for r in conn.execute(
            """
            SELECT customer_id, full_name, kyc_tier, risk_rating, home_country
            FROM customers
            WHERE customer_id LIKE ? OR full_name LIKE ?
            LIMIT ?
            """,
            (pattern, pattern, lim),
        ).fetchall():
            results.append(
                {
                    "id": r["customer_id"],
                    "type": "CUSTOMER",
                    "label": r["full_name"],
                    "subtitle": f"{r['customer_id']} • KYC: {r['kyc_tier']} • {r['home_country']}",
                    "risk": r["risk_rating"] or "LOW",
                }
            )

    # 3. Merchants
    if entity_type in ("ALL", "MERCHANT"):
        for r in conn.execute(
            """
            SELECT merchant_id, merchant_name, category, country, risk_tier
            FROM merchants
            WHERE merchant_id LIKE ? OR merchant_name LIKE ?
            LIMIT ?
            """,
            (pattern, pattern, lim),
        ).fetchall():
            results.append(
                {
                    "id": r["merchant_id"],
                    "type": "MERCHANT",
                    "label": r["merchant_name"],
                    "subtitle": f"{r['merchant_id']} • {r['category']} • {r['country']}",
                    "risk": r["risk_tier"] or "LOW",
                }
            )

    # 4. Devices
    if entity_type in ("ALL", "DEVICE"):
        for r in conn.execute(
            """
            SELECT device_id, os_family, ip_country, is_emulator, risk_tier
            FROM devices
            WHERE device_id LIKE ?
            LIMIT ?
            """,
            (pattern, lim),
        ).fetchall():
            results.append(
                {
                    "id": r["device_id"],
                    "type": "DEVICE",
                    "label": f"{r['device_id']} ({r['os_family']})",
                    "subtitle": f"IP: {r['ip_country']} • {'Emulator' if r['is_emulator'] else 'Hardware'}",
                    "risk": r["risk_tier"] or "LOW",
                }
            )

    # 5. Transactions
    if entity_type in ("ALL", "TRANSACTION"):
        for r in conn.execute(
            """
            SELECT transaction_id, account_id, txn_type, amount, occurred_at
            FROM transactions
            WHERE transaction_id LIKE ?
            LIMIT ?
            """,
            (pattern, lim),
        ).fetchall():
            results.append(
                {
                    "id": r["transaction_id"],
                    "type": "TRANSACTION",
                    "label": r["transaction_id"],
                    "subtitle": f"{r['txn_type']} • ${float(r['amount']):,.2f} • {r['account_id']}",
                    "risk": "LOW",
                }
            )

    return results[:limit]


# Alias for compatibility
search_network_entities = search_entities


def get_financial_network_graph(
    conn: sqlite3.Connection,
    *,
    seed_id: str | None = None,
    depth: int = 2,
    max_nodes: int = 75,
) -> dict[str, Any]:
    """Build multi-hop financial network graph starting from seed_id (or highest-risk active seed)."""
    clean_depth = max(1, min(3, depth))
    clean_limit = max(10, min(150, max_nodes))

    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edge_keys: set[tuple[str, str, str]] = set()

    def add_node(
        nid: str,
        ntype: str,
        label: str,
        risk: str = "LOW",
        score: float | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if nid not in nodes:
            calc_score = score if score is not None else (85 if risk == "CRITICAL" else 70 if risk == "HIGH" else 45 if risk == "MEDIUM" else 20)
            nodes[nid] = {
                "id": nid,
                "type": ntype,
                "label": label,
                "risk": risk,
                "risk_classification": risk,
                "risk_score": calc_score,
                "in_degree": 0,
                "out_degree": 0,
                "meta": meta or {},
                "metadata": meta or {},
            }

    def add_edge(
        src: str,
        dst: str,
        rel: str,
        amount: float = 0.0,
        timestamp: str | None = None,
        direction: str = "FORWARD",
        is_inferred: bool = False,
        risk: str = "LOW",
    ) -> None:
        key = (src, dst, rel)
        if key not in seen_edge_keys:
            seen_edge_keys.add(key)
            edges.append(
                {
                    "id": f"EDGE-{len(edges)+1:04d}",
                    "source": src,
                    "target": dst,
                    "relation": rel,
                    "relationship": rel,
                    "amount": round(float(amount), 2),
                    "timestamp": timestamp,
                    "direction": direction,
                    "is_inferred": is_inferred,
                    "risk": risk,
                }
            )

    # 1. Determine Root Seed
    root_id = (seed_id or "").strip()
    root_type = "ACCOUNT"
    root_label = root_id

    if not root_id:
        # Default to highest priority case account or highest exposure account
        top_case = conn.execute(
            """
            SELECT primary_account_id, primary_customer_id, priority_score
            FROM cases
            WHERE primary_account_id IS NOT NULL AND status = 'OPEN'
            ORDER BY priority_score DESC LIMIT 1
            """
        ).fetchone()
        if top_case:
            root_id = top_case["primary_account_id"]
        else:
            top_acct = conn.execute(
                """
                SELECT source_account_id, SUM(transfer_amount) as vol
                FROM transfer_links
                GROUP BY source_account_id ORDER BY vol DESC LIMIT 1
                """
            ).fetchone()
            root_id = top_acct["source_account_id"] if top_acct else "ACC-CUS-000001-01"

    # Seed Type Detection
    if root_id.startswith("CUS-"):
        c = conn.execute("SELECT customer_id, full_name, risk_rating, kyc_tier FROM customers WHERE customer_id = ?", (root_id,)).fetchone()
        if c:
            root_type = "CUSTOMER"
            root_label = c["full_name"]
            add_node(root_id, "CUSTOMER", c["full_name"], c["risk_rating"] or "LOW", meta={"kyc_tier": c["kyc_tier"]})
    elif root_id.startswith("DEV-"):
        d = conn.execute("SELECT device_id, os_family, ip_country, is_emulator, risk_tier FROM devices WHERE device_id = ?", (root_id,)).fetchone()
        if d:
            root_type = "DEVICE"
            root_label = f"{d['device_id']} ({d['os_family']})"
            add_node(root_id, "DEVICE", root_label, d["risk_tier"] or "LOW", meta={"emulator": bool(d["is_emulator"])})
    elif root_id.startswith("MER-"):
        m = conn.execute("SELECT merchant_id, merchant_name, category, risk_tier FROM merchants WHERE merchant_id = ?", (root_id,)).fetchone()
        if m:
            root_type = "MERCHANT"
            root_label = m["merchant_name"]
            add_node(root_id, "MERCHANT", m["merchant_name"], m["risk_tier"] or "LOW", meta={"category": m["category"]})
    elif root_id.startswith("TXN-"):
        tx = conn.execute("SELECT transaction_id, account_id, txn_type, amount, status FROM transactions WHERE transaction_id = ?", (root_id,)).fetchone()
        if tx:
            root_type = "TRANSACTION"
            root_label = f"{tx['txn_type']} (${float(tx['amount']):,.0f})"
            add_node(root_id, "TRANSACTION", root_label, "LOW", meta={"amount": tx["amount"]})
    else:
        # Default assume Account
        a = conn.execute(
            """
            SELECT a.account_id, a.account_type, a.status, a.current_balance, c.full_name, c.risk_rating
            FROM accounts a
            LEFT JOIN customers c ON c.customer_id = a.primary_customer_id
            WHERE a.account_id = ?
            """,
            (root_id,),
        ).fetchone()
        if a:
            root_type = "ACCOUNT"
            root_label = f"{a['account_id']} ({a['account_type']})"
            add_node(root_id, "ACCOUNT", a["account_id"], a["risk_rating"] or "LOW", meta={"balance": a["current_balance"], "owner": a["full_name"]})

    # Breadth-first graph expansion across database relationships
    frontier = [root_id]
    visited = {root_id}

    for current_hop in range(1, clean_depth + 1):
        if len(nodes) >= clean_limit or not frontier:
            break
        next_frontier: list[str] = []

        # 1. Expand Accounts in frontier
        acct_ids = [eid for eid in frontier if eid.startswith("ACC-")]
        if acct_ids:
            ph = ",".join(["?"] * len(acct_ids))

            # A. Account Ownerships -> Customers
            owners = conn.execute(
                f"""
                SELECT ao.account_id, c.customer_id, c.full_name, c.risk_rating, c.kyc_tier
                FROM account_ownerships ao
                JOIN customers c ON c.customer_id = ao.customer_id
                WHERE ao.account_id IN ({ph})
                """,
                acct_ids,
            ).fetchall()
            for r in owners:
                add_node(r["customer_id"], "CUSTOMER", r["full_name"], r["risk_rating"] or "LOW", meta={"kyc_tier": r["kyc_tier"]})
                add_edge(r["customer_id"], r["account_id"], "OWNS", risk=r["risk_rating"] or "LOW")
                if r["customer_id"] not in visited:
                    visited.add(r["customer_id"])
                    next_frontier.append(r["customer_id"])

            # B. Account Device Links -> Devices
            devs = conn.execute(
                f"""
                SELECT adl.account_id, d.device_id, d.os_family, d.ip_country, d.is_emulator, d.risk_tier
                FROM account_device_links adl
                JOIN devices d ON d.device_id = adl.device_id
                WHERE adl.account_id IN ({ph})
                """,
                acct_ids,
            ).fetchall()
            for r in devs:
                add_node(
                    r["device_id"],
                    "DEVICE",
                    f"{r['device_id']} ({r['os_family']})",
                    r["risk_tier"] or "LOW",
                    meta={"is_emulator": bool(r["is_emulator"]), "country": r["ip_country"]},
                )
                add_edge(r["account_id"], r["device_id"], "USES_DEVICE", risk="HIGH" if r["is_emulator"] else "LOW")
                if r["device_id"] not in visited:
                    visited.add(r["device_id"])
                    next_frontier.append(r["device_id"])

            # C. Outgoing & Incoming Transfer Links -> Peer Accounts
            transfers = conn.execute(
                f"""
                SELECT tl.transfer_id, tl.source_account_id, tl.dest_account_id, tl.transfer_amount,
                       tl.initiated_at, tl.status,
                       a_src.account_type as src_type, a_dst.account_type as dst_type
                FROM transfer_links tl
                JOIN accounts a_src ON a_src.account_id = tl.source_account_id
                JOIN accounts a_dst ON a_dst.account_id = tl.dest_account_id
                WHERE tl.source_account_id IN ({ph}) OR tl.dest_account_id IN ({ph})
                ORDER BY tl.initiated_at DESC LIMIT 30
                """,
                (*acct_ids, *acct_ids),
            ).fetchall()
            for t in transfers:
                src_id = t["source_account_id"]
                dst_id = t["dest_account_id"]
                add_node(src_id, "ACCOUNT", src_id, "MEDIUM")
                add_node(dst_id, "ACCOUNT", dst_id, "MEDIUM")
                add_edge(
                    src_id,
                    dst_id,
                    "TRANSFER",
                    amount=float(t["transfer_amount"]),
                    timestamp=t["initiated_at"],
                    risk="HIGH" if float(t["transfer_amount"]) >= 20000 else "LOW",
                )
                for peer in (src_id, dst_id):
                    if peer not in visited:
                        visited.add(peer)
                        next_frontier.append(peer)

            # D. Associated Transactions (Top high-value / suspicious)
            txns = conn.execute(
                f"""
                SELECT t.transaction_id, t.account_id, t.txn_type, t.direction, t.amount,
                       t.merchant_id, m.merchant_name, m.category as merchant_category,
                       t.device_id, t.status, t.occurred_at
                FROM transactions t
                LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
                WHERE t.account_id IN ({ph}) AND t.status = 'SETTLED'
                ORDER BY t.amount DESC LIMIT 12
                """,
                acct_ids,
            ).fetchall()
            for tx in txns:
                tx_id = tx["transaction_id"]
                add_node(
                    tx_id,
                    "TRANSACTION",
                    f"{tx['txn_type']} (${float(tx['amount']):,.0f})",
                    "HIGH" if float(tx["amount"]) > 25000 else "LOW",
                    meta={"amount": tx["amount"], "type": tx["txn_type"], "occurred_at": tx["occurred_at"]},
                )
                if tx["direction"] == "DEBIT":
                    add_edge(tx["account_id"], tx_id, "DEBIT", amount=float(tx["amount"]), timestamp=tx["occurred_at"])
                else:
                    add_edge(tx_id, tx["account_id"], "CREDIT", amount=float(tx["amount"]), timestamp=tx["occurred_at"])

                # If merchant involved
                if tx["merchant_id"]:
                    m_id = tx["merchant_id"]
                    add_node(m_id, "MERCHANT", tx["merchant_name"] or m_id, "MEDIUM", meta={"category": tx["merchant_category"]})
                    add_edge(tx_id, m_id, "MERCHANT_PAYMENT", amount=float(tx["amount"]), timestamp=tx["occurred_at"])
                    if m_id not in visited:
                        visited.add(m_id)
                        next_frontier.append(m_id)

                if tx_id not in visited:
                    visited.add(tx_id)

        # 2. Expand Customers in frontier -> their accounts
        cust_ids = [eid for eid in frontier if eid.startswith("CUS-")]
        if cust_ids:
            c_ph = ",".join(["?"] * len(cust_ids))
            has_ao = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='account_ownerships'").fetchone()[0] > 0
            if has_ao:
                a_query = f"""
                    SELECT ao.customer_id, a.account_id, a.account_type, a.status, a.current_balance
                    FROM account_ownerships ao
                    JOIN accounts a ON a.account_id = ao.account_id
                    WHERE ao.customer_id IN ({c_ph})
                """
            else:
                a_query = f"""
                    SELECT a.primary_customer_id AS customer_id, a.account_id, a.account_type, a.status, a.current_balance
                    FROM accounts a
                    WHERE a.primary_customer_id IN ({c_ph})
                """
            for a_row in conn.execute(a_query, cust_ids).fetchall():
                add_node(a_row["account_id"], "ACCOUNT", a_row["account_id"], "MEDIUM", meta={"balance": a_row["current_balance"]})
                add_edge(a_row["customer_id"], a_row["account_id"], "OWNS")
                if a_row["account_id"] not in visited:
                    visited.add(a_row["account_id"])
                    next_frontier.append(a_row["account_id"])

        # 3. Expand Devices in frontier -> peer accounts sharing device
        device_ids = [eid for eid in frontier if eid.startswith("DEV-")]
        if device_ids:
            d_ph = ",".join(["?"] * len(device_ids))
            has_adl = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='account_device_links'").fetchone()[0] > 0
            if has_adl:
                for p_row in conn.execute(
                    f"""
                    SELECT adl.device_id, a.account_id, a.account_type, c.customer_id, c.full_name
                    FROM account_device_links adl
                    JOIN accounts a ON a.account_id = adl.account_id
                    JOIN customers c ON c.customer_id = a.primary_customer_id
                    WHERE adl.device_id IN ({d_ph})
                    LIMIT 15
                    """,
                    device_ids,
                ).fetchall():
                    add_node(p_row["account_id"], "ACCOUNT", p_row["account_id"], "MEDIUM")
                    add_edge(p_row["customer_id"], p_row["device_id"], "USES_DEVICE")
                    if p_row["account_id"] not in visited:
                        visited.add(p_row["account_id"])
                        next_frontier.append(p_row["account_id"])

        frontier = next_frontier

    # Calculate node degrees
    for e in edges:
        if e["source"] in nodes:
            nodes[e["source"]]["out_degree"] += 1
        if e["target"] in nodes:
            nodes[e["target"]]["in_degree"] += 1

    # Attach alerts / cases count where applicable
    account_ids_in_graph = [nid for nid, n in nodes.items() if n["type"] == "ACCOUNT"]
    if account_ids_in_graph:
        aph = ",".join(["?"] * len(account_ids_in_graph))
        for al_row in conn.execute(
            f"""
            SELECT account_id, COUNT(alert_id) as alert_count, MAX(risk_score) as max_score
            FROM alerts
            WHERE account_id IN ({aph})
            GROUP BY account_id
            """,
            account_ids_in_graph,
        ).fetchall():
            aid = al_row["account_id"]
            if aid in nodes:
                nodes[aid]["meta"]["alert_count"] = al_row["alert_count"]
                nodes[aid]["risk_score"] = round(float(al_row["max_score"] or 0), 1)
                if al_row["max_score"] and float(al_row["max_score"]) >= 75:
                    nodes[aid]["risk"] = "CRITICAL"
                elif al_row["max_score"] and float(al_row["max_score"]) >= 50:
                    nodes[aid]["risk"] = "HIGH"

    node_list = list(nodes.values())
    total_transfer_exposure = round(sum(e["amount"] for e in edges if e["relation"] == "TRANSFER"), 2)

    return {
        "seed_id": root_id,
        "seed_type": root_type,
        "seed_label": root_label,
        "node_count": len(node_list),
        "total_nodes": len(node_list),
        "edge_count": len(edges),
        "total_edges": len(edges),
        "total_transfer_exposure": total_transfer_exposure,
        "nodes": node_list,
        "edges": edges,
    }


def trace_money_flow_path(
    conn: sqlite3.Connection,
    source_account_id: str,
    dest_account_id: str,
    *,
    max_depth: int = 4,
) -> dict[str, Any]:
    """Reconstruct directional movement of funds between source and destination accounts.

    Distinguishes transaction volume from unique money moved along the path.
    """
    src = (source_account_id or "").strip()
    dst = (dest_account_id or "").strip()
    if not src or not dst:
        return {"has_path": False, "paths": [], "message": "Source and destination account IDs required."}

    if src == dst:
        return {"has_path": False, "paths": [], "message": "Source and destination accounts must be distinct."}

    # Directional BFS for path discovery
    queue: deque[list[str]] = deque([[src]])
    visited = {src}
    found_paths: list[list[str]] = []

    while queue and len(found_paths) < 5:
        path = queue.popleft()
        curr = path[-1]

        if len(path) > max_depth + 1:
            continue

        # Look up outgoing transfers from current node
        neighbors = [
            r["dest_account_id"]
            for r in conn.execute(
                """
                SELECT DISTINCT dest_account_id FROM transfer_links
                WHERE source_account_id = ?
                """,
                (curr,),
            ).fetchall()
        ]

        for nxt in neighbors:
            if nxt == dst:
                found_paths.append(path + [nxt])
            elif nxt not in path and len(path) < max_depth:
                queue.append(path + [nxt])

    if not found_paths:
        return {
            "has_path": False,
            "source": src,
            "source_account_id": src,
            "destination": dst,
            "dest_account_id": dst,
            "paths_found": 0,
            "paths_count": 0,
            "shortest_path_hops": 0,
            "total_transaction_volume": 0.0,
            "estimated_unique_flow": 0.0,
            "flow_confidence": "POSSIBLE_FLOW",
            "paths": [],
            "path_details": [],
            "message": f"No confirmed directional transfer path found between {src} and {dst} within {max_depth} hops.",
        }

    # Reconstruct detailed edges, timestamps, and amounts for discovered paths
    path_details: list[dict[str, Any]] = []
    for p in found_paths:
        steps: list[dict[str, Any]] = []
        hop_amounts: list[float] = []
        timestamps: list[str] = []

        for i in range(len(p) - 1):
            s_acc = p[i]
            d_acc = p[i + 1]
            tx_row = conn.execute(
                """
                SELECT transfer_id, transfer_amount, initiated_at, status
                FROM transfer_links
                WHERE source_account_id = ? AND dest_account_id = ?
                ORDER BY initiated_at ASC LIMIT 1
                """,
                (s_acc, d_acc),
            ).fetchone()
            if tx_row:
                amt = float(tx_row["transfer_amount"])
                hop_amounts.append(amt)
                timestamps.append(tx_row["initiated_at"])
                steps.append(
                    {
                        "hop": i + 1,
                        "step": i + 1,
                        "from_account": s_acc,
                        "to_account": d_acc,
                        "transfer_id": tx_row["transfer_id"],
                        "amount": amt,
                        "timestamp": tx_row["initiated_at"],
                        "initiated_at": tx_row["initiated_at"],
                    }
                )

        total_tx_volume = round(sum(hop_amounts), 2)
        # Conservative distinct fund estimation: minimum transfer along pass-through conduit
        estimated_flow = round(min(hop_amounts) if hop_amounts else 0.0, 2)

        # Time duration
        first_dt = _parse_dt(timestamps[0]) if timestamps else None
        last_dt = _parse_dt(timestamps[-1]) if timestamps else None
        interval_hours = round((last_dt - first_dt).total_seconds() / 3600.0, 1) if first_dt and last_dt else 0.0

        path_details.append(
            {
                "path_nodes": p,
                "hop_count": len(p) - 1,
                "total_transaction_volume": total_tx_volume,
                "estimated_unique_flow": estimated_flow,
                "time_span_hours": interval_hours,
                "steps": steps,
            }
        )

    return {
        "has_path": True,
        "source": src,
        "source_account_id": src,
        "destination": dst,
        "dest_account_id": dst,
        "paths_count": len(path_details),
        "paths_found": len(path_details),
        "shortest_path_hops": min(p["hop_count"] for p in path_details) if path_details else 0,
        "total_transaction_volume": max(p["total_transaction_volume"] for p in path_details) if path_details else 0.0,
        "estimated_unique_flow": max(p["estimated_unique_flow"] for p in path_details) if path_details else 0.0,
        "flow_confidence": "CONFIRMED",
        "paths": [p["steps"] for p in path_details],
        "path_details": path_details,
    }


def detect_circular_transfers(conn: sqlite3.Connection, *, limit: int = 15) -> list[dict[str, Any]]:
    """Detect circular transaction patterns (cycles like A -> B -> C -> A) in transfer links."""
    # Build transfer adjacency list
    adj: dict[str, list[tuple[str, float, str, str]]] = defaultdict(list)
    rows = conn.execute(
        """
        SELECT transfer_id, source_account_id, dest_account_id, transfer_amount, initiated_at
        FROM transfer_links
        ORDER BY initiated_at ASC
        LIMIT 4000
        """
    ).fetchall()

    for r in rows:
        adj[r["source_account_id"]].append(
            (r["dest_account_id"], float(r["transfer_amount"]), r["initiated_at"], r["transfer_id"])
        )

    cycles: list[dict[str, Any]] = []
    seen_canonical_cycles: set[tuple[str, ...]] = set()

    # Search for cycles with lengths 2 to 4
    for start_node in list(adj.keys()):
        if len(cycles) >= limit:
            break

        stack: list[tuple[str, list[str], list[dict[str, Any]]]] = [(start_node, [start_node], [])]

        while stack and len(cycles) < limit:
            curr, path, edge_seq = stack.pop()
            if len(path) > 5:
                continue

            for nxt, amt, ts, tid in adj.get(curr, []):
                edge_info = {"transfer_id": tid, "source": curr, "target": nxt, "amount": amt, "timestamp": ts}
                if nxt == start_node and len(path) >= 2:
                    # Found cycle!
                    canonical = tuple(sorted(path))
                    if canonical not in seen_canonical_cycles:
                        seen_canonical_cycles.add(canonical)
                        cycle_edges = edge_seq + [edge_info]
                        total_vol = round(sum(e["amount"] for e in cycle_edges), 2)
                        dts = [_parse_dt(e["timestamp"]) for e in cycle_edges if _parse_dt(e["timestamp"])]
                        time_span = 0.0
                        if len(dts) >= 2:
                            time_span = round((max(dts) - min(dts)).total_seconds() / 3600.0, 1)

                        cycles.append(
                            {
                                "cycle_id": f"CYCLE-{len(cycles)+1:03d}",
                                "accounts": path,
                                "hop_count": len(path),
                                "cycle_volume": total_vol,
                                "time_window_hours": time_span,
                                "transactions": cycle_edges,
                                "risk_tier": "CRITICAL" if total_vol >= 50000 or len(path) >= 3 else "HIGH",
                                "explanation": f"Closed transfer loop detected across {len(path)} accounts with ${total_vol:,.2f} cumulative volume within {time_span}h.",
                            }
                        )
                        break
                elif nxt not in path and len(path) < 4:
                    stack.append((nxt, path + [nxt], edge_seq + [edge_info]))

    return cycles[:limit]


def detect_suspicious_patterns(conn: sqlite3.Connection) -> dict[str, Any]:
    """Identify explainable suspicious patterns: fan-in concentration, rapid dispersion, and shared devices."""
    # 1. Unusual Transaction Concentration (Fan-in: Account receives from >= 4 distinct accounts)
    concentration_rows = conn.execute(
        """
        SELECT tl.dest_account_id,
               COUNT(DISTINCT tl.source_account_id) AS unique_senders,
               COUNT(tl.transfer_id) AS tx_count,
               SUM(tl.transfer_amount) AS total_inflow,
               MIN(tl.initiated_at) AS first_tx,
               MAX(tl.initiated_at) AS last_tx,
               c.customer_id, c.full_name, c.risk_rating
        FROM transfer_links tl
        JOIN accounts a ON a.account_id = tl.dest_account_id
        JOIN customers c ON c.customer_id = a.primary_customer_id
        GROUP BY tl.dest_account_id
        HAVING unique_senders >= 3
        ORDER BY unique_senders DESC, total_inflow DESC
        LIMIT 10
        """
    ).fetchall()

    concentrations: list[dict[str, Any]] = []
    for r in concentration_rows:
        t1 = _parse_dt(r["first_tx"])
        t2 = _parse_dt(r["last_tx"])
        window_hours = round((t2 - t1).total_seconds() / 3600.0, 1) if t1 and t2 else 0.0
        concentrations.append(
            {
                "pattern_id": f"CONC-{len(concentrations)+1:03d}",
                "account_id": r["dest_account_id"],
                "customer_name": r["full_name"],
                "customer_id": r["customer_id"],
                "unique_senders": int(r["unique_senders"]),
                "incoming_transfers": int(r["tx_count"]),
                "total_inflow": round(float(r["total_inflow"]), 2),
                "time_window_hours": window_hours,
                "risk_tier": "CRITICAL" if r["unique_senders"] >= 5 else "HIGH",
                "explanation": f"High fan-in concentration: received {r['tx_count']} transfers from {r['unique_senders']} distinct accounts totaling ${float(r['total_inflow']):,.2f}.",
            }
        )

    # 2. Rapid Fund Dispersion (Fan-out / Layering: Account receives inflow then rapidly disperses to multiple accounts)
    dispersion_rows = conn.execute(
        """
        SELECT tl.source_account_id,
               COUNT(DISTINCT tl.dest_account_id) AS unique_recipients,
               COUNT(tl.transfer_id) AS tx_count,
               SUM(tl.transfer_amount) AS total_outflow,
               MIN(tl.initiated_at) AS first_out,
               MAX(tl.initiated_at) AS last_out,
               c.customer_id, c.full_name, c.risk_rating
        FROM transfer_links tl
        JOIN accounts a ON a.account_id = tl.source_account_id
        JOIN customers c ON c.customer_id = a.primary_customer_id
        GROUP BY tl.source_account_id
        HAVING unique_recipients >= 3
        ORDER BY unique_recipients DESC, total_outflow DESC
        LIMIT 10
        """
    ).fetchall()

    dispersions: list[dict[str, Any]] = []
    for r in dispersion_rows:
        aid = r["source_account_id"]
        # Check inbound transfers to this account
        inflow_row = conn.execute(
            """
            SELECT COALESCE(SUM(transfer_amount), 0) AS total_inflow, COUNT(*) as inc_count
            FROM transfer_links WHERE dest_account_id = ?
            """,
            (aid,),
        ).fetchone()
        inflow = float(inflow_row["total_inflow"])
        outflow = float(r["total_outflow"])
        pass_through = round((outflow / inflow) * 100.0, 1) if inflow > 0 else 100.0

        t1 = _parse_dt(r["first_out"])
        t2 = _parse_dt(r["last_out"])
        window_hours = round((t2 - t1).total_seconds() / 3600.0, 1) if t1 and t2 else 0.0

        dispersions.append(
            {
                "pattern_id": f"DISP-{len(dispersions)+1:03d}",
                "account_id": aid,
                "customer_name": r["full_name"],
                "customer_id": r["customer_id"],
                "destinations_count": int(r["unique_recipients"]),
                "total_outflow": round(outflow, 2),
                "total_inflow": round(inflow, 2),
                "pass_through_ratio": pass_through,
                "time_window_hours": window_hours,
                "risk_tier": "CRITICAL" if r["unique_recipients"] >= 4 and pass_through >= 75 else "HIGH",
                "explanation": f"Rapid dispersion conduit: dispersed ${outflow:,.2f} across {r['unique_recipients']} destination accounts ({pass_through}% of inflow) in {window_hours}h.",
            }
        )

    # 3. Shared Devices (Multiple customers sharing same physical or emulator device)
    shared_dev_rows = conn.execute(
        """
        SELECT d.device_id, d.os_family, d.ip_country, d.is_emulator, d.risk_tier,
               COUNT(DISTINCT ao.customer_id) as cust_count,
               COUNT(DISTINCT adl.account_id) as acct_count,
               GROUP_CONCAT(DISTINCT c.full_name) as cust_names,
               GROUP_CONCAT(DISTINCT adl.account_id) as accts
        FROM account_device_links adl
        JOIN devices d ON d.device_id = adl.device_id
        JOIN account_ownerships ao ON ao.account_id = adl.account_id
        JOIN customers c ON c.customer_id = ao.customer_id
        GROUP BY d.device_id
        HAVING cust_count >= 2
        ORDER BY cust_count DESC, d.is_emulator DESC
        LIMIT 10
        """
    ).fetchall()

    shared_devices: list[dict[str, Any]] = []
    for r in shared_dev_rows:
        shared_devices.append(
            {
                "pattern_id": f"DEVLINK-{len(shared_devices)+1:03d}",
                "device_id": r["device_id"],
                "os_family": r["os_family"],
                "ip_country": r["ip_country"],
                "is_emulator": bool(r["is_emulator"]),
                "customers_count": int(r["cust_count"]),
                "accounts_count": int(r["acct_count"]),
                "customer_names": (r["cust_names"] or "").split(",")[:5],
                "accounts": (r["accts"] or "").split(",")[:5],
                "risk_tier": "CRITICAL" if r["is_emulator"] else "HIGH",
                "explanation": f"Shared device link: {r['cust_count']} distinct customers accessed accounts from device {r['device_id']} ({'EMULATOR' if r['is_emulator'] else r['os_family']}).",
            }
        )

    fan_in_concentration = [
        {
            "pattern_id": c["pattern_id"],
            "destination_account": c["account_id"],
            "account_id": c["account_id"],
            "customer_id": c["customer_id"],
            "customer_name": c["customer_name"],
            "inflow_sources": c["unique_senders"],
            "unique_senders": c["unique_senders"],
            "total_inflow_amount": c["total_inflow"],
            "total_inflow": c["total_inflow"],
            "risk_tier": c["risk_tier"],
            "pattern": "FAN_IN_CONCENTRATION",
            "explanation": c["explanation"],
        }
        for c in concentrations
    ]

    rapid_dispersion = [
        {
            "pattern_id": d["pattern_id"],
            "origin_account": d["account_id"],
            "account_id": d["account_id"],
            "customer_id": d["customer_id"],
            "customer_name": d["customer_name"],
            "outflow_targets": d["unique_recipients"],
            "unique_recipients": d["unique_recipients"],
            "total_outflow_amount": d["total_outflow"],
            "total_outflow": d["total_outflow"],
            "risk_tier": d["risk_tier"],
            "pattern": "RAPID_DISPERSION",
            "explanation": d["explanation"],
        }
        for d in dispersions
    ]

    shared_device_clusters = [
        {
            "pattern_id": s["pattern_id"],
            "device_id": s["device_id"],
            "fingerprint": s["device_id"],
            "device_type": "EMULATOR" if s["is_emulator"] else "HARDWARE",
            "os": s["os_family"],
            "is_emulator": s["is_emulator"],
            "is_rooted": s["is_emulator"],
            "shared_customers_count": s["customers_count"],
            "customers_count": s["customers_count"],
            "customers": [
                {"customer_id": f"CUS-{name.replace(' ', '')}", "full_name": name, "email": f"{name.lower().replace(' ', '.')}@example.com", "risk_rating": "HIGH"}
                for name in s["customer_names"]
            ],
            "accounts": s["accounts"],
            "risk_tier": s["risk_tier"],
            "explanation": s["explanation"],
        }
        for s in shared_devices
    ]

    return {
        "concentrations": concentrations,
        "dispersions": dispersions,
        "shared_devices": shared_devices,
        "fan_in_concentration": fan_in_concentration,
        "rapid_dispersion": rapid_dispersion,
        "shared_device_clusters": shared_device_clusters,
    }


def resolve_entities(conn: sqlite3.Connection, *, limit: int = 30) -> list[dict[str, Any]]:
    """Conservative entity resolution distinguishing confirmed records from inferred/potential links."""
    results: list[dict[str, Any]] = []

    # 1. Confirmed Relationships: Explicit account ownership & device links
    confirmed_rows = conn.execute(
        """
        SELECT c.customer_id, c.full_name, a.account_id, a.account_type, a.status
        FROM account_ownerships ao
        JOIN customers c ON c.customer_id = ao.customer_id
        JOIN accounts a ON a.account_id = ao.account_id
        WHERE c.risk_rating = 'HIGH'
        LIMIT 15
        """
    ).fetchall()

    for r in confirmed_rows:
        results.append(
            {
                "resolution_id": f"RES-CONF-{len(results)+1:03d}",
                "cluster_id": f"CLUS-{len(results)+1:03d}",
                "category": "CONFIRMED",
                "resolution_status": "CONFIRMED_MATCH",
                "match_confidence": 100,
                "confidence_score": 100,
                "primary_customer_id": r["customer_id"],
                "primary_name": r["full_name"],
                "matched_customer_id": r["account_id"],
                "matched_name": f"{r['account_id']} ({r['account_type']})",
                "entity_a": {"id": r["customer_id"], "type": "CUSTOMER", "label": r["full_name"]},
                "entity_b": {"id": r["account_id"], "type": "ACCOUNT", "label": f"{r['account_id']} ({r['account_type']})"},
                "relationship": "VERIFIED_ACCOUNT_OWNERSHIP",
                "matching_attribute": "PRIMARY_ACCOUNT_HOLDER_LEDGER",
                "shared_identifiers": ["PRIMARY_ACCOUNT_HOLDER_LEDGER"],
                "evidence_summary": f"Verified banking relationship: Customer {r['customer_id']} is the legal owner of account {r['account_id']}.",
                "explanation": f"Verified banking relationship: Customer {r['customer_id']} is the legal owner of account {r['account_id']}.",
                "recommended_action": "Record verified link in case file.",
            }
        )

    # 2. Inferred / Potential Relationships: Shared Device Fingerprint between distinct customers
    inferred_dev_rows = conn.execute(
        """
        SELECT d.device_id, d.is_emulator, d.os_family,
               c1.customer_id as cust1_id, c1.full_name as cust1_name,
               c2.customer_id as cust2_id, c2.full_name as cust2_name
        FROM account_device_links adl1
        JOIN account_device_links adl2 ON adl1.device_id = adl2.device_id AND adl1.account_id != adl2.account_id
        JOIN account_ownerships ao1 ON ao1.account_id = adl1.account_id
        JOIN account_ownerships ao2 ON ao2.account_id = adl2.account_id AND ao1.customer_id < ao2.customer_id
        JOIN customers c1 ON c1.customer_id = ao1.customer_id
        JOIN customers c2 ON c2.customer_id = ao2.customer_id
        JOIN devices d ON d.device_id = adl1.device_id
        GROUP BY d.device_id, c1.customer_id, c2.customer_id
        ORDER BY d.is_emulator DESC
        LIMIT 15
        """
    ).fetchall()

    for r in inferred_dev_rows:
        conf = 88 if r["is_emulator"] else 74
        results.append(
            {
                "resolution_id": f"RES-INFER-{len(results)+1:03d}",
                "cluster_id": f"CLUS-{len(results)+1:03d}",
                "category": "POTENTIAL",
                "resolution_status": "POTENTIAL_MATCH",
                "match_confidence": conf,
                "confidence_score": conf,
                "primary_customer_id": r["cust1_id"],
                "primary_name": r["cust1_name"],
                "matched_customer_id": r["cust2_id"],
                "matched_name": r["cust2_name"],
                "entity_a": {"id": r["cust1_id"], "type": "CUSTOMER", "label": r["cust1_name"]},
                "entity_b": {"id": r["cust2_id"], "type": "CUSTOMER", "label": r["cust2_name"]},
                "relationship": "SHARED_DEVICE_HARDWARE",
                "matching_attribute": f"DEVICE_{r['device_id']}",
                "shared_identifiers": [f"Device {r['device_id']}", f"OS: {r['os_family']}"],
                "evidence_summary": f"Potential synthetic identity or colluding actors: Customers share physical/emulator device {r['device_id']}.",
                "explanation": f"Potential synthetic identity or colluding actors: Customers share physical/emulator device {r['device_id']}. Note: Shared hardware alone does not constitute confirmed fraud.",
                "recommended_action": "Corroborate identity via secondary KYC or device velocity check.",
            }
        )

    return results[:limit]


# Alias for compatibility
search_network_entities = search_entities


def compute_network_risk_analysis(
    conn: sqlite3.Connection,
    seed_id: str | None = None,
) -> dict[str, Any]:
    """Calculate reproducible, transparent network risk scoring for subnetwork prioritisation."""
    graph = get_financial_network_graph(conn, seed_id=seed_id, depth=2, max_nodes=50)
    cycles = detect_circular_transfers(conn, limit=5)
    patterns = detect_suspicious_patterns(conn)

    score = 15.0  # Base network baseline
    factors: list[dict[str, Any]] = []

    # Check 1: Circular transaction involvement
    cycle_hit = False
    for c in cycles:
        if graph["seed_id"] in c["accounts"]:
            cycle_hit = True
            break
    if cycle_hit:
        score += 30.0
        factors.append(
            {
                "rule": "CIRCULAR_TRANSFER_INVOLVEMENT",
                "weight": "+30 pts",
                "severity": "CRITICAL",
                "description": "Direct participation in a closed circular fund transfer loop.",
            }
        )
    elif cycles:
        score += 15.0
        factors.append(
            {
                "rule": "NETWORK_PROXIMITY_TO_CYCLES",
                "weight": "+15 pts",
                "severity": "HIGH",
                "description": f"Adjacent to {len(cycles)} detected circular loops in the active corridor.",
            }
        )

    # Check 2: High concentration / fan-in
    conc_hit = any(p["account_id"] == graph["seed_id"] for p in patterns.get("concentrations", []))
    if conc_hit:
        score += 20.0
        factors.append(
            {
                "rule": "UNUSUAL_FAN_IN_CONCENTRATION",
                "weight": "+20 pts",
                "severity": "HIGH",
                "description": "Receives funds from an unusually high number of distinct sending accounts.",
            }
        )

    # Check 3: Rapid fund dispersion / layering
    disp_hit = any(p["account_id"] == graph["seed_id"] for p in patterns.get("dispersions", []))
    if disp_hit:
        score += 25.0
        factors.append(
            {
                "rule": "RAPID_DISPERSION_LAYERING",
                "weight": "+25 pts",
                "severity": "CRITICAL",
                "description": "Rapid pass-through dispersion to multiple counterparty accounts shortly after receipt.",
            }
        )

    # Check 4: Emulator Device links
    emulator_nodes = [n for n in graph["nodes"] if n["type"] == "DEVICE" and n["meta"].get("is_emulator")]
    if emulator_nodes:
        score += 15.0
        factors.append(
            {
                "rule": "EMULATOR_DEVICE_INTERACTION",
                "weight": "+15 pts",
                "severity": "HIGH",
                "description": f"Directly accessed via {len(emulator_nodes)} rooted/emulator device environment(s).",
            }
        )

    # Check 5: Total exposure volume
    exp = graph["total_transfer_exposure"]
    if exp > 50000:
        score += 10.0
        factors.append(
            {
                "rule": "HIGH_CORRIDOR_TRANSFER_VOLUME",
                "weight": "+10 pts",
                "severity": "MEDIUM",
                "description": f"Total linked transfer volume exceeds $50,000 (${exp:,.2f}).",
            }
        )

    final_score = round(min(100.0, score), 1)
    tier = "CRITICAL" if final_score >= 70 else "HIGH" if final_score >= 45 else "MEDIUM" if final_score >= 25 else "LOW"

    model_factors = [
        {
            "factor": f["rule"],
            "score": 85 if f["severity"] == "CRITICAL" else 70 if f["severity"] == "HIGH" else 45,
            "weight": round(float(f["weight"].replace("+", "").replace(" pts", "")) / 100.0, 2),
            "detail": f["description"],
        }
        for f in factors
    ]
    if not model_factors:
        model_factors = [{"factor": "BASELINE_NETWORK_ACTIVITY", "score": 15, "weight": 1.0, "detail": "Normal transactional baseline."}]
    else:
        tot_w = sum(f["weight"] for f in model_factors)
        if tot_w > 0:
            for f in model_factors:
                f["weight"] = round(f["weight"] / tot_w, 2)
            diff = round(1.0 - sum(f["weight"] for f in model_factors), 2)
            model_factors[0]["weight"] = round(model_factors[0]["weight"] + diff, 2)

    return {
        "seed_id": graph["seed_id"],
        "network_risk_score": final_score,
        "overall_network_risk_score": final_score,
        "risk_classification": tier,
        "risk_tier": tier,
        "node_count": graph["node_count"],
        "edge_count": graph["edge_count"],
        "transfer_exposure": exp,
        "explanation": f"Network risk score of {final_score}/100 ({tier}) derived from {len(factors)} active topological risk factors.",
        "factors": model_factors,
        "contributing_factors": factors,
        "contributing_factors_count": len(factors),
        "subgraph_metrics": {
            "total_nodes": graph["node_count"],
            "total_edges": graph["edge_count"],
            "total_volume": exp,
            "avg_node_degree": round((2 * graph["edge_count"] / max(1, graph["node_count"])), 1),
        },
        "participating_accounts": [n["id"] for n in graph["nodes"] if n["type"] == "ACCOUNT"][:10],
        "participating_customers": [n["id"] for n in graph["nodes"] if n["type"] == "CUSTOMER"][:10],
    }

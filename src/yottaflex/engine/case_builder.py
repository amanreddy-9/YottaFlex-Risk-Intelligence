"""Entity-graph case clustering and transparent explainable priority scoring."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self.parent = {x: x for x in items}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


def compute_alert_and_case_priorities(
    *,
    alerts: list[dict[str, Any]],
    alert_trigger_facts: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    customers: list[dict[str, Any]],
    account_ownerships: list[dict[str, Any]],
    account_device_links: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    merchants: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    transfer_links: list[dict[str, Any]],
    account_state_events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Group alerts into linked Cases and compute transparent decomposed priority scores.

    Returns (cases, case_alert_links, case_state_events, case_explainability_map).
    Operates strictly without ground_truth access.
    """
    if not alerts:
        return [], [], [], {}

    acct_by_id = {a["account_id"]: a for a in accounts}
    cust_by_id = {c["customer_id"]: c for c in customers}
    dev_by_id = {d["device_id"]: d for d in devices}
    merch_by_id = {m["merchant_id"]: m for m in merchants}
    txn_by_id = {t["transaction_id"]: t for t in transactions}

    facts_by_alert: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in alert_trigger_facts:
        facts_by_alert[f["alert_id"]].append(f)

    # Track account dormancy history and large payroll credits in O(N)
    dormant_accts: set[str] = {
        ev["account_id"] for ev in account_state_events if ev["new_status"] == "DORMANT"
    }
    has_large_payroll: set[str] = {
        t["account_id"]
        for t in transactions
        if t["txn_type"] == "PAYROLL_CREDIT" and float(t["amount"]) >= 5000.0
    }

    # Build entity graph over alerted accounts
    alert_ids = [a["alert_id"] for a in alerts]
    uf = _UnionFind(alert_ids)
    alerts_by_acct: dict[str, list[str]] = defaultdict(list)
    for a in alerts:
        alerts_by_acct[a["account_id"]].append(a["alert_id"])

    linkage_reasons_per_acct: dict[str, set[str]] = defaultdict(set)

    # 1. Same account alerts cluster together
    for aid, aids in alerts_by_acct.items():
        for i in range(1, len(aids)):
            uf.union(aids[0], aids[i])
        if len(aids) > 1:
            linkage_reasons_per_acct[aid].add("MULTI_RULE_ACCOUNT")

    # 2. Same customer ownership links accounts
    accts_by_cust: dict[str, list[str]] = defaultdict(list)
    for own in account_ownerships:
        if own["account_id"] in alerts_by_acct:
            accts_by_cust[own["customer_id"]].append(own["account_id"])
    for cid, c_accts in accts_by_cust.items():
        uniq = sorted(set(c_accts))
        if len(uniq) > 1:
            anchor_alert = alerts_by_acct[uniq[0]][0]
            for other_acct in uniq[1:]:
                uf.union(anchor_alert, alerts_by_acct[other_acct][0])
                linkage_reasons_per_acct[other_acct].add("SHARED_OWNERSHIP")
            linkage_reasons_per_acct[uniq[0]].add("SHARED_OWNERSHIP")

    # 3. Shared device across alerted accounts
    accts_by_dev: dict[str, list[str]] = defaultdict(list)
    for adl in account_device_links:
        if adl["account_id"] in alerts_by_acct:
            accts_by_dev[adl["device_id"]].append(adl["account_id"])
    for did, d_accts in accts_by_dev.items():
        uniq = sorted(set(d_accts))
        if len(uniq) > 1:
            anchor_alert = alerts_by_acct[uniq[0]][0]
            for other_acct in uniq[1:]:
                uf.union(anchor_alert, alerts_by_acct[other_acct][0])
                linkage_reasons_per_acct[other_acct].add("SHARED_DEVICE")
            linkage_reasons_per_acct[uniq[0]].add("SHARED_DEVICE")

    # 4. TransferLinks connecting alerted accounts
    for trl in transfer_links:
        s_aid, d_aid = trl["source_account_id"], trl["dest_account_id"]
        if s_aid in alerts_by_acct and d_aid in alerts_by_acct:
            uf.union(alerts_by_acct[s_aid][0], alerts_by_acct[d_aid][0])
            linkage_reasons_per_acct[s_aid].add("TRANSFER_RING")
            linkage_reasons_per_acct[d_aid].add("TRANSFER_RING")

    # Gather clusters
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in alerts:
        clusters[uf.find(a["alert_id"])].append(a)

    # Sort clusters deterministically by earliest alert created_at + root alert_id
    sorted_clusters = sorted(
        clusters.values(),
        key=lambda grp: (min(a["created_at"] for a in grp), min(a["alert_id"] for a in grp)),
    )

    cases_out: list[dict[str, Any]] = []
    links_out: list[dict[str, Any]] = []
    events_out: list[dict[str, Any]] = []
    explain_map: dict[str, dict[str, Any]] = {}

    link_seq = 1
    evt_seq = 1

    for c_idx, grp in enumerate(sorted_clusters, start=1):
        case_id = f"CASE-2026-{c_idx:06d}"
        grp.sort(key=lambda a: (a["created_at"], a["alert_id"]))

        linked_accounts = sorted({a["account_id"] for a in grp})
        unique_rules = sorted({a["rule_id"] for a in grp})
        created_at = grp[0]["created_at"]

        # Primary account = highest total trigger_total_amount
        acct_exposure: dict[str, float] = defaultdict(float)
        for a in grp:
            acct_exposure[a["account_id"]] += float(a["trigger_total_amount"])
        primary_acct_id = max(linked_accounts, key=lambda aid: (acct_exposure[aid], aid))
        primary_cust_id = acct_by_id[primary_acct_id]["primary_customer_id"]

        # Deduplicated transaction exposure across facts
        seen_txn_ids: set[str] = set()
        seen_trls: set[str] = set()
        for a in grp:
            if a["primary_txn_id"]:
                seen_txn_ids.add(a["primary_txn_id"])
            for f in facts_by_alert.get(a["alert_id"], []):
                if f["transaction_id"]:
                    seen_txn_ids.add(f["transaction_id"])
                if f["transfer_id"]:
                    seen_trls.add(f["transfer_id"])

        total_exposure = round(
            sum(float(txn_by_id[tid]["amount"]) for tid in seen_txn_ids if tid in txn_by_id),
            2,
        )
        if total_exposure == 0.0:
            total_exposure = round(sum(float(a["trigger_total_amount"]) for a in grp), 2)

        # Determine dominant linkage reason
        reasons: set[str] = set()
        for aid in linked_accounts:
            reasons.update(linkage_reasons_per_acct.get(aid, set()))
        if "TRANSFER_RING" in reasons or "RULE-003" in unique_rules:
            linkage_summary = "TRANSFER_RING"
        elif "SHARED_DEVICE" in reasons or "RULE-007" in unique_rules:
            linkage_summary = "SHARED_DEVICE"
        elif "SHARED_OWNERSHIP" in reasons:
            linkage_summary = "SHARED_OWNERSHIP"
        elif "MULTI_RULE_ACCOUNT" in reasons or len(unique_rules) > 1:
            linkage_summary = "MULTI_RULE_ACCOUNT"
        else:
            linkage_summary = "SINGLE_ACCOUNT_BURST"

        # --- Transparent Score Decomposition (0..100) ---
        # 1. Rule Severity Component (0..45)
        max_alert_score = max(float(a["risk_score"]) for a in grp)
        rule_diversity_bonus = min(15.0, max(0, len(unique_rules) - 1) * 6.5)
        rule_component = min(48.0, round(max_alert_score * 0.42 + rule_diversity_bonus, 2))

        # 2. Network Blast Radius Component (0..26)
        acct_spread = min(14.0, max(0, len(linked_accounts) - 1) * 4.5)
        ring_bonus = 10.0 if "RULE-003" in unique_rules else 0.0
        shared_dev_bonus = 8.0 if "RULE-007" in unique_rules else 0.0
        network_component = min(26.0, round(acct_spread + ring_bonus + shared_dev_bonus, 2))

        # 3. Financial Exposure Component (0..18)
        exposure_component = min(18.0, round((total_exposure / 1500.0) * 1.8, 2))

        # 4. Entity & Lifecycle Context Component (0..14)
        cust = cust_by_id[primary_cust_id]
        kyc_pts = {"LOW": 6.0, "STANDARD": 3.0, "ENHANCED": 0.0}[cust["kyc_tier"]]
        dormant_pts = 5.0 if any(aid in dormant_accts for aid in linked_accounts) else 0.0
        new_dev_pts = 4.0 if "RULE-002" in unique_rules else 0.0
        context_component = min(15.0, round(kyc_pts + dormant_pts + new_dev_pts, 2))

        # 5. Benign Mitigators (-24..0) — transparent false-positive suppressors
        mitigator_points = 0.0
        mitigator_reasons: list[str] = []

        # 5a. Own-account internal sweep check
        group_trls = [t for t in transfer_links if t["transfer_id"] in seen_trls]
        if group_trls and all(t["is_same_customer"] == 1 for t in group_trls) and "RULE-003" not in unique_rules:
            mitigator_points -= 22.0
            mitigator_reasons.append("All transfers are verified same-customer internal sweeps (-22.0)")

        # 5b. Low-risk / travel / education / healthcare / tax-style merchant + Enhanced KYC
        involved_txns = [txn_by_id[tid] for tid in seen_txn_ids if tid in txn_by_id]
        involved_merchants = [merch_by_id[t["merchant_id"]] for t in involved_txns if t["merchant_id"] in merch_by_id]
        benign_sectors = {"TRAVEL", "EDUCATION", "HEALTHCARE", "UTILITIES", "GROCERY"}
        if involved_merchants and all(m["category"] in benign_sectors and m["risk_tier"] != "HIGH" for m in involved_merchants):
            if cust["kyc_tier"] == "ENHANCED" or cust["segment"] == "AFFLUENT":
                mitigator_points -= 18.0
                mitigator_reasons.append("Low-risk Travel/Education/Essential MCCs on Enhanced/Affluent profile (-18.0)")
            else:
                mitigator_points -= 10.0
                mitigator_reasons.append("Low-risk Education/Essential merchant sector (-10.0)")

        # 5c. Verified recent payroll funding prior to bill/tuition pay (when no circular/mule device)
        if "RULE-003" not in unique_rules and "RULE-007" not in unique_rules and "RULE-002" not in unique_rules:
            large_payroll = any(aid in has_large_payroll for aid in linked_accounts)
            if large_payroll and (
                not involved_merchants or all(m["risk_tier"] == "LOW" for m in involved_merchants)
            ):
                mitigator_points -= 14.0
                mitigator_reasons.append("Preceded by verified large PAYROLL_CREDIT with no mule/device anomaly (-14.0)")

        raw_score = rule_component + network_component + exposure_component + context_component + mitigator_points
        priority_score = round(min(100.0, max(5.0, raw_score)), 2)

        if priority_score >= 80.0:
            priority_tier = "CRITICAL"
        elif priority_score >= 60.0:
            priority_tier = "HIGH"
        elif priority_score >= 40.0:
            priority_tier = "MEDIUM"
        else:
            priority_tier = "LOW"

        cases_out.append({
            "case_id": case_id,
            "primary_account_id": primary_acct_id,
            "primary_customer_id": primary_cust_id,
            "linkage_summary": linkage_summary,
            "linked_account_count": len(linked_accounts),
            "alert_count": len(grp),
            "total_exposure_amount": total_exposure,
            "priority_score": priority_score,
            "priority_tier": priority_tier,
            "status": "OPEN",
            "created_at": created_at,
            "updated_at": created_at,
        })

        explain_map[case_id] = {
            "case_id": case_id,
            "priority_score": priority_score,
            "priority_tier": priority_tier,
            "components": {
                "rule_severity": rule_component,
                "network_blast_radius": network_component,
                "financial_exposure": exposure_component,
                "entity_lifecycle_context": context_component,
                "benign_mitigators": round(mitigator_points, 2),
            },
            "mitigator_reasons": mitigator_reasons,
            "rules_triggered": unique_rules,
            "linked_accounts": linked_accounts,
        }

        for a in grp:
            links_out.append({
                "case_alert_id": f"CAL-2026-{link_seq:06d}",
                "case_id": case_id,
                "alert_id": a["alert_id"],
                "linkage_reason": linkage_summary,
                "linkage_key": primary_acct_id if linkage_summary != "SHARED_DEVICE" else a["account_id"],
                "linked_at": a["created_at"],
            })
            link_seq += 1

        events_out.append({
            "case_event_id": f"CSE-2026-{evt_seq:06d}",
            "case_id": case_id,
            "prev_status": None,
            "new_status": "OPEN",
            "analyst_action_id": None,
            "effective_at": created_at,
        })
        evt_seq += 1

    return cases_out, links_out, events_out, explain_map

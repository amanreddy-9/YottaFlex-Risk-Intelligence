"""Transparent RiskRule evaluator operating strictly on ledger & entity tables.

Zero ground-truth access: only evaluates Customers, Accounts, AccountOwnerships,
AccountDeviceLinks, AccountStateEvents, Merchants, Devices, Transactions,
and TransferLinks.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from yottaflex.generator.rules_catalog import RISK_RULES

RULE_MAP: dict[str, dict[str, Any]] = {r["rule_id"]: r for r in RISK_RULES}


def _parse_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evaluate_rules_on_ledger(
    *,
    customers: list[dict[str, Any]],
    accounts: list[dict[str, Any]],
    account_ownerships: list[dict[str, Any]],
    merchants: list[dict[str, Any]],
    devices: list[dict[str, Any]],
    account_device_links: list[dict[str, Any]],
    account_state_events: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    transfer_links: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate all 8 RiskRules and return derived (alerts, alert_trigger_facts)."""
    cust_by_id = {c["customer_id"]: c for c in customers}
    acct_by_id = {a["account_id"]: a for a in accounts}
    merch_by_id = {m["merchant_id"]: m for m in merchants}
    dev_by_id = {d["device_id"]: d for d in devices}

    # Index device links per (account_id, device_id) and per device_id -> customers
    adl_map: dict[tuple[str, str], dict[str, Any]] = {}
    device_customers: dict[str, set[str]] = defaultdict(set)
    for adl in account_device_links:
        adl_map[(adl["account_id"], adl["device_id"])] = adl
        acct = acct_by_id.get(adl["account_id"])
        if acct:
            device_customers[adl["device_id"]].add(acct["primary_customer_id"])

    # Index transactions by account_id (sorted by occurred_at) and by txn_id
    txns_by_acct: dict[str, list[dict[str, Any]]] = defaultdict(list)
    txn_by_id: dict[str, dict[str, Any]] = {}
    for t in transactions:
        txn_by_id[t["transaction_id"]] = t
        if t["status"] == "POSTED":
            txns_by_acct[t["account_id"]].append(t)
    for aid in txns_by_acct:
        txns_by_acct[aid].sort(key=lambda x: (x["occurred_at"], x["transaction_id"]))

    # Index transfer links by debit_txn_id and by source_account_id
    trl_by_debit: dict[str, dict[str, Any]] = {}
    trls_by_src: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trl in transfer_links:
        trl_by_debit[trl["debit_txn_id"]] = trl
        trls_by_src[trl["source_account_id"]].append(trl)

    # Index dormancy reactivation timestamps per account
    dormant_reactivations: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    events_by_acct: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in account_state_events:
        events_by_acct[ev["account_id"]].append(ev)
    for aid, evs in events_by_acct.items():
        evs.sort(key=lambda e: e["effective_at"])
        dormant_since: datetime | None = None
        for ev in evs:
            dt = _parse_dt(ev["effective_at"])
            if ev["new_status"] == "DORMANT":
                dormant_since = dt
            elif ev["prev_status"] == "DORMANT" and ev["new_status"] == "ACTIVE" and dormant_since:
                days = max(1, int((dt - dormant_since).total_seconds() // 86400))
                dormant_reactivations[aid].append((dt, days))
                dormant_since = None

    raw_alerts: list[dict[str, Any]] = []
    raw_facts_by_alert_idx: list[list[dict[str, Any]]] = []

    def add_alert(
        rule_id: str,
        account_id: str,
        primary_txn: dict[str, Any],
        supporting_txns: list[dict[str, Any]],
        facts: list[dict[str, Any]],
        risk_score: float,
        explanation: str,
        created_at: str,
    ) -> None:
        rule = RULE_MAP[rule_id]
        acct = acct_by_id[account_id]
        total_amt = round(sum(float(t["amount"]) for t in supporting_txns), 2)
        idx = len(raw_alerts)
        raw_alerts.append({
            "_sort_key": (created_at, account_id, rule_id, primary_txn["transaction_id"]),
            "rule_id": rule_id,
            "account_id": account_id,
            "customer_id": acct["primary_customer_id"],
            "primary_txn_id": primary_txn["transaction_id"],
            "severity": rule["severity"],
            "risk_score": round(min(100.0, max(0.0, risk_score)), 2),
            "trigger_txn_count": len(supporting_txns),
            "trigger_total_amount": total_amt,
            "explanation_summary": explanation,
            "status": "GROUPED",
            "created_at": created_at,
        })
        raw_facts_by_alert_idx.append(facts)

    # 1. Per-account rule evaluations (RULE-001, 002, 004, 005, 006, 008)
    for aid, acct_txns in sorted(txns_by_acct.items()):
        acct = acct_by_id[aid]
        cust = cust_by_id[acct["primary_customer_id"]]
        monthly_income = float(cust["declared_annual_income"]) / 12.0

        debits = [t for t in acct_txns if t["direction"] == "DEBIT"]
        debit_dts = [_parse_dt(t["occurred_at"]) for t in debits]

        # RULE-001: Rapid Outflow Velocity Spike (>=5 debits within 60 min totaling >= $2,500)
        i = 0
        last_r1_end: datetime | None = None
        for j in range(len(debits)):
            while debit_dts[j] - debit_dts[i] > timedelta(minutes=60):
                i += 1
            window = debits[i : j + 1]
            if len(window) >= 5:
                w_sum = sum(float(t["amount"]) for t in window)
                if w_sum >= 2500.0:
                    if last_r1_end is None or debit_dts[i] > last_r1_end:
                        last_r1_end = debit_dts[j]
                        score = RULE_MAP["RULE-001"]["base_weight"] + min(22.0, (len(window) - 4) * 4.0 + w_sum / 1000.0)
                        anchor = window[-1]
                        created = _fmt_dt(debit_dts[j] + timedelta(seconds=30))
                        facts = [
                            {
                                "transaction_id": t["transaction_id"],
                                "transfer_id": trl_by_debit[t["transaction_id"]]["transfer_id"]
                                if t["transaction_id"] in trl_by_debit
                                else None,
                                "rule_id": "RULE-001",
                                "metric_name": "window_60m_outflow_count_and_usd",
                                "observed_value": f"{len(window)} txns / ${w_sum:,.2f}",
                                "threshold_value": ">= 5 txns / >= $2,500.00 in 60m",
                                "recorded_at": created,
                            }
                            for t in window
                        ]
                        add_alert(
                            "RULE-001",
                            aid,
                            anchor,
                            window,
                            facts,
                            score,
                            f"{len(window)} outbound txns totaling ${w_sum:,.2f} within 60 minutes",
                            created,
                        )

        # RULE-006: Structuring / Split Outflows (>=3 debits in [$1,800, $2,999.99] within 24h)
        struct_txns = [t for t in debits if 1800.0 <= float(t["amount"]) <= 2999.99]
        struct_dts = [_parse_dt(t["occurred_at"]) for t in struct_txns]
        si = 0
        last_r6_end: datetime | None = None
        for sj in range(len(struct_txns)):
            while struct_dts[sj] - struct_dts[si] > timedelta(hours=24):
                si += 1
            swin = struct_txns[si : sj + 1]
            if len(swin) >= 3:
                if last_r6_end is None or struct_dts[si] > last_r6_end:
                    last_r6_end = struct_dts[sj]
                    s_sum = sum(float(t["amount"]) for t in swin)
                    score = RULE_MAP["RULE-006"]["base_weight"] + min(20.0, len(swin) * 4.0)
                    created = _fmt_dt(struct_dts[sj] + timedelta(seconds=45))
                    facts = [
                        {
                            "transaction_id": t["transaction_id"],
                            "transfer_id": trl_by_debit[t["transaction_id"]]["transfer_id"]
                            if t["transaction_id"] in trl_by_debit
                            else None,
                            "rule_id": "RULE-006",
                            "metric_name": "structured_band_txn_count_24h",
                            "observed_value": f"{len(swin)} txns (${s_sum:,.2f})",
                            "threshold_value": ">= 3 txns in [$1,800, $2,999.99] within 24h",
                            "recorded_at": created,
                        }
                        for t in swin
                    ]
                    add_alert(
                        "RULE-006",
                        aid,
                        swin[-1],
                        swin,
                        facts,
                        score,
                        f"{len(swin)} split outflows (${s_sum:,.2f}) just under $3,000 reporting band in 24h",
                        created,
                    )

        # RULE-002, RULE-005, RULE-008: Transaction-level rules (deduped per account-rule-day)
        seen_r2_days: set[str] = set()
        seen_r5_days: set[str] = set()
        seen_r8_days: set[str] = set()

        for t in acct_txns:
            t_dt = _parse_dt(t["occurred_at"])
            day_key = t["occurred_at"][:10]
            amt = float(t["amount"])

            # RULE-002: New Device High-Value Outflow
            if t["direction"] == "DEBIT" and amt >= 1500.0 and t["device_id"]:
                adl = adl_map.get((aid, t["device_id"]))
                if adl:
                    age_hours = (t_dt - _parse_dt(adl["first_seen_at"])).total_seconds() / 3600.0
                    if 0.0 <= age_hours <= 24.0 and day_key not in seen_r2_days:
                        seen_r2_days.add(day_key)
                        dev = dev_by_id[t["device_id"]]
                        bonus = 12.0 if dev["is_emulator"] or dev["risk_tier"] == "HIGH" else 6.0
                        score = RULE_MAP["RULE-002"]["base_weight"] + bonus + min(15.0, amt / 1000.0)
                        created = _fmt_dt(t_dt + timedelta(seconds=20))
                        facts = [{
                            "transaction_id": t["transaction_id"],
                            "transfer_id": trl_by_debit[t["transaction_id"]]["transfer_id"]
                            if t["transaction_id"] in trl_by_debit
                            else None,
                            "rule_id": "RULE-002",
                            "metric_name": "device_age_hours",
                            "observed_value": f"{age_hours:.2f}h (amount=${amt:,.2f})",
                            "threshold_value": "<= 24.0h and amount >= $1,500.00",
                            "recorded_at": created,
                        }]
                        add_alert(
                            "RULE-002",
                            aid,
                            t,
                            [t],
                            facts,
                            score,
                            f"New device {t['device_id']} ({age_hours:.1f}h old) executed ${amt:,.2f} outflow",
                            created,
                        )

            # RULE-005: High-Risk Cross-Border Merchant
            if t["merchant_id"] and amt >= 1000.0:
                merch = merch_by_id[t["merchant_id"]]
                is_foreign = merch["country"] != cust["home_country"]
                if (merch["risk_tier"] == "HIGH" or is_foreign) and day_key not in seen_r5_days:
                    seen_r5_days.add(day_key)
                    score = RULE_MAP["RULE-005"]["base_weight"] + (10.0 if merch["risk_tier"] == "HIGH" else 4.0) + min(12.0, amt / 1000.0)
                    created = _fmt_dt(t_dt + timedelta(seconds=25))
                    facts = [{
                        "transaction_id": t["transaction_id"],
                        "transfer_id": None,
                        "rule_id": "RULE-005",
                        "metric_name": "merchant_risk_and_country",
                        "observed_value": f"tier={merch['risk_tier']}, merch={merch['country']}, home={cust['home_country']}, amt=${amt:,.2f}",
                        "threshold_value": "tier=HIGH or foreign merchant with amt >= $1,000.00",
                        "recorded_at": created,
                    }]
                    add_alert(
                        "RULE-005",
                        aid,
                        t,
                        [t],
                        facts,
                        score,
                        f"${amt:,.2f} purchase at {merch['merchant_name']} ({merch['category']}, {merch['country']})",
                        created,
                    )

            # RULE-008: KYC Tier & Declared Income Deviation
            if cust["kyc_tier"] in ("LOW", "STANDARD") and amt >= max(2500.0, 0.50 * monthly_income):
                if day_key not in seen_r8_days:
                    seen_r8_days.add(day_key)
                    ratio = amt / max(1.0, monthly_income)
                    score = RULE_MAP["RULE-008"]["base_weight"] + min(18.0, ratio * 12.0)
                    created = _fmt_dt(t_dt + timedelta(seconds=35))
                    facts = [{
                        "transaction_id": t["transaction_id"],
                        "transfer_id": trl_by_debit[t["transaction_id"]]["transfer_id"]
                        if t["transaction_id"] in trl_by_debit
                        else None,
                        "rule_id": "RULE-008",
                        "metric_name": "txn_to_monthly_income_ratio",
                        "observed_value": f"{ratio:.2f}x (kyc={cust['kyc_tier']}, amt=${amt:,.2f})",
                        "threshold_value": ">= 0.50x monthly income on LOW/STANDARD KYC",
                        "recorded_at": created,
                    }]
                    add_alert(
                        "RULE-008",
                        aid,
                        t,
                        [t],
                        facts,
                        score,
                        f"${amt:,.2f} txn is {ratio:.2f}x monthly income on {cust['kyc_tier']} KYC profile",
                        created,
                    )

        # RULE-004: Dormant Account Sudden Reactivation
        for react_dt, dorm_days in dormant_reactivations.get(aid, []):
            window_txns = [
                t for t in acct_txns
                if react_dt <= _parse_dt(t["occurred_at"]) <= react_dt + timedelta(hours=48)
                and float(t["amount"]) >= 3000.0
            ]
            if window_txns:
                tot = sum(float(t["amount"]) for t in window_txns)
                anchor = window_txns[-1]
                created = _fmt_dt(_parse_dt(anchor["occurred_at"]) + timedelta(seconds=40))
                score = RULE_MAP["RULE-004"]["base_weight"] + min(22.0, dorm_days / 15.0 + tot / 2500.0)
                facts = [
                    {
                        "transaction_id": t["transaction_id"],
                        "transfer_id": trl_by_debit[t["transaction_id"]]["transfer_id"]
                        if t["transaction_id"] in trl_by_debit
                        else None,
                        "rule_id": "RULE-004",
                        "metric_name": "dormancy_days_and_reactivation_usd",
                        "observed_value": f"{dorm_days}d dormant / ${tot:,.2f} within 48h",
                        "threshold_value": "prior DORMANT state + >= $3,000.00 within 48h",
                        "recorded_at": created,
                    }
                    for t in window_txns
                ]
                add_alert(
                    "RULE-004",
                    aid,
                    anchor,
                    window_txns,
                    facts,
                    score,
                    f"Account dormant {dorm_days}d reactivated with ${tot:,.2f} activity in 48h",
                    created,
                )

    # 2. RULE-003: Circular Transfer Ring / Layering (2..5 hop cycles returning >=75% within 48h)
    # Use BFS/DFS bounded to depth 5 on TransferLinks ordered by time
    sorted_trls = sorted(
        [trl for trl in transfer_links if trl["status"] == "SETTLED"],
        key=lambda x: (x["initiated_at"], x["transfer_id"]),
    )
    reported_cycle_sigs: set[tuple[str, ...]] = set()
    for start_trl in sorted_trls:
        if start_trl["is_same_customer"] == 1:
            continue
        start_acct = start_trl["source_account_id"]
        start_amt = float(start_trl["transfer_amount"])
        if start_amt < 1000.0:
            continue
        start_dt = _parse_dt(start_trl["initiated_at"])

        # DFS stack: (curr_acct, path_accts, path_trls, last_dt, min_amt)
        stack: list[tuple[str, list[str], list[dict[str, Any]], datetime, float]] = [
            (start_trl["dest_account_id"], [start_acct, start_trl["dest_account_id"]], [start_trl], start_dt, start_amt)
        ]
        while stack:
            curr, p_accts, p_trls, prev_dt, min_amt = stack.pop()
            if len(p_trls) > 5:
                continue
            for nxt in trls_by_src.get(curr, []):
                if nxt["status"] != "SETTLED":
                    continue
                nxt_dt = _parse_dt(nxt["initiated_at"])
                if nxt_dt < prev_dt or nxt_dt - start_dt > timedelta(hours=48):
                    continue
                nxt_amt = float(nxt["transfer_amount"])
                if nxt_amt < 0.70 * start_amt or nxt_amt > 1.15 * start_amt:
                    continue
                dst = nxt["dest_account_id"]
                if dst == start_acct and len(p_trls) >= 2:
                    cycle_trls = p_trls + [nxt]
                    cycle_accts = sorted(set(p_accts))
                    sig = tuple(cycle_accts) + (start_trl["initiated_at"][:10],)
                    if sig in reported_cycle_sigs:
                        continue
                    ret_ratio = nxt_amt / start_amt
                    if ret_ratio >= 0.75:
                        reported_cycle_sigs.add(sig)
                        # Create alert on each participating account in the ring
                        created = _fmt_dt(nxt_dt + timedelta(seconds=60))
                        ring_txns = [txn_by_id[tr["debit_txn_id"]] for tr in cycle_trls if tr["debit_txn_id"] in txn_by_id]
                        for tr in cycle_trls:
                            src_aid = tr["source_account_id"]
                            d_txn = txn_by_id[tr["debit_txn_id"]]
                            score = RULE_MAP["RULE-003"]["base_weight"] + min(28.0, len(cycle_trls) * 5.0 + start_amt / 1500.0)
                            facts = [
                                {
                                    "transaction_id": txn_by_id[c_tr["debit_txn_id"]]["transaction_id"],
                                    "transfer_id": c_tr["transfer_id"],
                                    "rule_id": "RULE-003",
                                    "metric_name": "circular_cycle_hops_and_return_ratio",
                                    "observed_value": f"{len(cycle_trls)} hops, return={ret_ratio:.2%}",
                                    "threshold_value": "2..5 hops returning >= 75% within 48h",
                                    "recorded_at": created,
                                }
                                for c_tr in cycle_trls
                            ]
                            add_alert(
                                "RULE-003",
                                src_aid,
                                d_txn,
                                ring_txns,
                                facts,
                                score,
                                f"{len(cycle_trls)}-hop circular transfer ring returning {ret_ratio:.0%} (${start_amt:,.2f}) within 48h",
                                created,
                            )
                        break
                elif dst not in p_accts and len(p_trls) < 5:
                    stack.append((dst, p_accts + [dst], p_trls + [nxt], nxt_dt, min(min_amt, nxt_amt)))

    # 3. RULE-007: Shared Device Across Unrelated Customers (>=3 distinct customers)
    for did, cust_set in sorted(device_customers.items()):
        if len(cust_set) < 3:
            continue
        # Find outbound transactions on this device
        dev_txns = [
            t for t in transactions
            if t["device_id"] == did and t["direction"] == "DEBIT" and t["status"] == "POSTED"
        ]
        dev_txns.sort(key=lambda x: (x["occurred_at"], x["transaction_id"]))
        if not dev_txns:
            continue
        latest = dev_txns[-1]
        created = _fmt_dt(_parse_dt(latest["occurred_at"]) + timedelta(seconds=50))
        by_acct: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for t in dev_txns:
            by_acct[t["account_id"]].append(t)
        for aid, a_txns in sorted(by_acct.items()):
            anchor = a_txns[-1]
            score = RULE_MAP["RULE-007"]["base_weight"] + min(24.0, len(cust_set) * 5.0)
            facts = [
                {
                    "transaction_id": t["transaction_id"],
                    "transfer_id": trl_by_debit[t["transaction_id"]]["transfer_id"]
                    if t["transaction_id"] in trl_by_debit
                    else None,
                    "rule_id": "RULE-007",
                    "metric_name": "distinct_customers_on_device",
                    "observed_value": f"{len(cust_set)} customers sharing {did}",
                    "threshold_value": ">= 3 unrelated customers on single device",
                    "recorded_at": created,
                }
                for t in a_txns
            ]
            add_alert(
                "RULE-007",
                aid,
                anchor,
                a_txns,
                facts,
                score,
                f"Device {did} shared across {len(cust_set)} unrelated customers",
                created,
            )

    # Sort deterministically and assign final ALT-2026-XXXXXX & ATF-2026-XXXXXX IDs
    indexed = list(zip(raw_alerts, raw_facts_by_alert_idx))
    indexed.sort(key=lambda pair: pair[0]["_sort_key"])

    alerts_out: list[dict[str, Any]] = []
    facts_out: list[dict[str, Any]] = []
    fact_seq = 1
    for a_idx, (alert, facts) in enumerate(indexed, start=1):
        alert_id = f"ALT-2026-{a_idx:06d}"
        clean_alert = {k: v for k, v in alert.items() if k != "_sort_key"}
        clean_alert["alert_id"] = alert_id
        alerts_out.append(clean_alert)
        for f in facts:
            facts_out.append({
                "fact_id": f"ATF-2026-{fact_seq:06d}",
                "alert_id": alert_id,
                **f,
            })
            fact_seq += 1

    return alerts_out, facts_out

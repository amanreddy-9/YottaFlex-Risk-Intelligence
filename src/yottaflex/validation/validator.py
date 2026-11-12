"""9-check data integrity, ledger reconciliation, and exception quarantine validator.

Operates strictly on exported input tables (zero ground_truth access).
Routes every failing record into QuarantineException rather than crashing
or allowing corrupted rows into downstream scoring.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yottaflex.schema_spec import ENUMS, TABLES
from yottaflex.workflow.case_service import ALLOWED_TRANSITIONS

_TABLE_SPEC_MAP = {t.table_name: t for t in TABLES}

_ACCOUNT_ALLOWED_TRANSITIONS: dict[str | None, set[str]] = {
    None: {"ACTIVE"},
    "ACTIVE": {"DORMANT", "FROZEN", "CLOSED"},
    "DORMANT": {"ACTIVE", "FROZEN", "CLOSED"},
    "FROZEN": {"ACTIVE", "CLOSED"},
    "CLOSED": set(),
}


def _parse_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _load_json_tables(export_dir: Path) -> dict[str, list[dict[str, Any]]]:
    json_dir = export_dir / "json"
    tables: dict[str, list[dict[str, Any]]] = {}
    for tbl in TABLES:
        p = json_dir / f"{tbl.table_name}.json"
        if not p.exists():
            raise FileNotFoundError(f"Missing table export: {p}")
        tables[tbl.table_name] = json.loads(p.read_text(encoding="utf-8"))
    return tables


def run_validation(export_dir: Path, *, write_reports: bool = True) -> dict[str, Any]:
    """Execute all 9 formal integrity checks and quarantine violations."""
    data = _load_json_tables(export_dir)
    quarantine: list[dict[str, Any]] = []
    check_results: list[dict[str, Any]] = []

    def add_exc(
        check_name: str,
        issue_type: str,
        severity: str,
        entity_type: str,
        entity_id: str,
        account_id: str | None,
        invariant: str,
        evidence: str,
        remediation: str,
    ) -> None:
        quarantine.append({
            "exception_id": f"QEXC-{len(quarantine) + 1:05d}",
            "check_name": check_name,
            "issue_type": issue_type,
            "severity": severity,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "account_id": account_id or "N/A",
            "violated_invariant": invariant,
            "evidence": evidence,
            "remediation": remediation,
        })

    # Index PK sets for FK checks
    pk_sets: dict[str, set[str]] = {}

    # ------------------------------------------------------------------
    # Check 1: PK Uniqueness & ID Nomenclature Regex
    # ------------------------------------------------------------------
    c1_errs = 0
    for tbl in TABLES:
        rows = data[tbl.table_name]
        pk_col = tbl.primary_key
        pat = re.compile(tbl.id_pattern)
        seen: set[str] = set()
        for r in rows:
            pk_val = str(r.get(pk_col, ""))
            if not pat.match(pk_val):
                c1_errs += 1
                add_exc(
                    "pk_and_id_format",
                    "INVALID_ID_FORMAT",
                    "HIGH",
                    tbl.entity_name.upper(),
                    pk_val,
                    r.get("account_id"),
                    f"{tbl.table_name}.{pk_col} must match {tbl.id_pattern}",
                    f"Observed '{pk_val}'",
                    "Reject malformed primary key at ingestion.",
                )
            if pk_val in seen:
                c1_errs += 1
                add_exc(
                    "pk_and_id_format",
                    "DUPLICATE_PRIMARY_KEY",
                    "CRITICAL",
                    tbl.entity_name.upper(),
                    pk_val,
                    r.get("account_id"),
                    f"{tbl.table_name}.{pk_col} must be unique",
                    f"Duplicate PK '{pk_val}'",
                    "Deduplicate or reject duplicate record.",
                )
            seen.add(pk_val)
        pk_sets[tbl.table_name] = seen
    check_results.append({
        "check_id": 1,
        "name": "PK Uniqueness & ID Nomenclature Regex",
        "records_checked": sum(len(data[t.table_name]) for t in TABLES),
        "violations": c1_errs,
        "status": "PASS" if c1_errs == 0 else "FAIL",
    })

    # ------------------------------------------------------------------
    # Check 2: FK Referential Integrity
    # ------------------------------------------------------------------
    c2_errs = 0
    fk_count = 0
    for tbl in TABLES:
        fk_fields = [f for f in tbl.fields if f.fk]
        if not fk_fields:
            continue
        for r in data[tbl.table_name]:
            pk_val = str(r.get(tbl.primary_key, ""))
            for f in fk_fields:
                val = r.get(f.name)
                if val is None:
                    continue
                fk_count += 1
                ref_tbl, _ = f.fk.split(".")
                if str(val) not in pk_sets[ref_tbl]:
                    c2_errs += 1
                    add_exc(
                        "fk_integrity",
                        "BROKEN_FOREIGN_KEY",
                        "CRITICAL",
                        tbl.entity_name.upper(),
                        pk_val,
                        r.get("account_id"),
                        f"{tbl.table_name}.{f.name} -> {f.fk}",
                        f"Missing parent '{val}' in {ref_tbl}",
                        "Reject orphan child record until parent exists.",
                    )
    check_results.append({
        "check_id": 2,
        "name": "Foreign-Key Referential Integrity",
        "records_checked": fk_count,
        "violations": c2_errs,
        "status": "PASS" if c2_errs == 0 else "FAIL",
    })

    # ------------------------------------------------------------------
    # Check 3: Allowed Enums & Numeric Bounds
    # ------------------------------------------------------------------
    c3_errs = 0
    c3_checked = 0
    enum_checks: list[tuple[str, str, set[str]]] = [
        ("customers", "kyc_tier", set(ENUMS["kyc_tier"])),
        ("customers", "risk_rating", set(ENUMS["customer_risk_rating"])),
        ("customers", "status", set(ENUMS["customer_status"])),
        ("accounts", "account_type", set(ENUMS["account_type"])),
        ("accounts", "status", set(ENUMS["account_status"])),
        ("account_ownerships", "ownership_role", set(ENUMS["ownership_role"])),
        ("devices", "os_family", set(ENUMS["device_os"])),
        ("devices", "risk_tier", set(ENUMS["device_risk_tier"])),
        ("merchants", "risk_tier", set(ENUMS["merchant_risk_tier"])),
        ("transactions", "txn_type", set(ENUMS["txn_type"])),
        ("transactions", "direction", set(ENUMS["txn_direction"])),
        ("transactions", "channel", set(ENUMS["txn_channel"])),
        ("transactions", "status", set(ENUMS["txn_status"])),
        ("transfer_links", "status", set(ENUMS["transfer_status"])),
        ("risk_rules", "category", set(ENUMS["rule_category"])),
        ("risk_rules", "severity", set(ENUMS["severity"])),
        ("alerts", "severity", set(ENUMS["severity"])),
        ("alerts", "status", set(ENUMS["alert_status"])),
        ("cases", "priority_tier", set(ENUMS["severity"])),
        ("cases", "status", set(ENUMS["case_status"])),
        ("analyst_actions", "action_type", set(ENUMS["analyst_action_type"])),
    ]
    for tbl_name, col, allowed in enum_checks:
        pk_col = _TABLE_SPEC_MAP[tbl_name].primary_key
        for r in data[tbl_name]:
            c3_checked += 1
            if r.get(col) not in allowed:
                c3_errs += 1
                add_exc(
                    "enum_and_bounds",
                    "INVALID_ENUM",
                    "HIGH",
                    tbl_name.upper(),
                    str(r.get(pk_col)),
                    r.get("account_id"),
                    f"{tbl_name}.{col} must be in {sorted(allowed)}",
                    f"Observed '{r.get(col)}'",
                    "Normalize or reject invalid enum value.",
                )
    for t in data["transactions"]:
        c3_checked += 1
        if float(t["amount"]) <= 0:
            c3_errs += 1
            add_exc(
                "enum_and_bounds",
                "NON_POSITIVE_AMOUNT",
                "HIGH",
                "TRANSACTION",
                t["transaction_id"],
                t["account_id"],
                "transactions.amount > 0",
                f"amount={t['amount']}",
                "Reject non-positive transaction amount.",
            )
    check_results.append({
        "check_id": 3,
        "name": "Allowed Enums & Numeric Domain Bounds",
        "records_checked": c3_checked,
        "violations": c3_errs,
        "status": "PASS" if c3_errs == 0 else "FAIL",
    })

    # Pre-index core lookups
    cust_by_id = {c["customer_id"]: c for c in data["customers"]}
    acct_by_id = {a["account_id"]: a for a in data["accounts"]}
    txn_by_id = {t["transaction_id"]: t for t in data["transactions"]}
    alert_by_id = {a["alert_id"]: a for a in data["alerts"]}

    # ------------------------------------------------------------------
    # Check 4: Temporal Ordering & Disposition-After-Alert Invariant
    # ------------------------------------------------------------------
    c4_errs = 0
    c4_checked = 0
    for c in data["customers"]:
        c4_checked += 1
        if _parse_dt(c["kyc_verified_at"]) < _parse_dt(c["created_at"]):
            c4_errs += 1
            add_exc(
                "temporal_ordering",
                "KYC_BEFORE_CUSTOMER",
                "HIGH",
                "CUSTOMER",
                c["customer_id"],
                None,
                "kyc_verified_at >= created_at",
                f"kyc={c['kyc_verified_at']} < created={c['created_at']}",
                "Audit KYC verification timestamp.",
            )

    for a in data["accounts"]:
        c4_checked += 1
        cust = cust_by_id.get(a["primary_customer_id"])
        if cust and _parse_dt(a["opened_at"]) < _parse_dt(cust["created_at"]):
            c4_errs += 1
            add_exc(
                "temporal_ordering",
                "ACCOUNT_OPENED_BEFORE_CUSTOMER",
                "HIGH",
                "ACCOUNT",
                a["account_id"],
                a["account_id"],
                "account.opened_at >= customer.created_at",
                f"opened={a['opened_at']} < cust={cust['created_at']}",
                "Reconcile onboarding timestamps.",
            )

    # Check AnalystAction.acted_at >= earliest linked alert created_at
    case_alerts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cal in data["case_alert_links"]:
        al = alert_by_id.get(cal["alert_id"])
        if al:
            case_alerts[cal["case_id"]].append(al)

    case_by_id = {c["case_id"]: c for c in data["cases"]}
    for act in data["analyst_actions"]:
        c4_checked += 1
        c_alerts = case_alerts.get(act["case_id"], [])
        if c_alerts:
            earliest_alert_ts = min(a["created_at"] for a in c_alerts)
            if _parse_dt(act["acted_at"]) < _parse_dt(earliest_alert_ts):
                c4_errs += 1
                add_exc(
                    "temporal_ordering",
                    "DISPOSITION_PRECEDES_ALERT",
                    "HIGH",
                    "ANALYST_ACTION",
                    act["action_id"],
                    case_by_id.get(act["case_id"], {}).get("primary_account_id"),
                    "AnalystAction.acted_at >= earliest linked Alert.created_at",
                    f"Action {act['action_type']} on {act['case_id']} at {act['acted_at']} precedes alert {earliest_alert_ts}",
                    "Invalidate premature disposition and reopen case for compliant review.",
                )
    check_results.append({
        "check_id": 4,
        "name": "Temporal & Disposition-After-Alert Ordering",
        "records_checked": c4_checked,
        "violations": c4_errs,
        "status": "PASS" if c4_errs == 0 else "FAIL",
    })

    # ------------------------------------------------------------------
    # Check 5: Running Balance Arithmetic & Overdraft Policy
    # ------------------------------------------------------------------
    c5_errs = 0
    txns_by_acct: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in data["transactions"]:
        txns_by_acct[t["account_id"]].append(t)

    for aid, acct in acct_by_id.items():
        acct_txns = sorted(txns_by_acct.get(aid, []), key=lambda x: (x["occurred_at"], x["transaction_id"]))
        expected_bal = float(acct["opening_balance"])
        od_allowed = int(acct["overdraft_allowed"])
        od_limit = float(acct["overdraft_limit"])
        for t in acct_txns:
            bb = float(t["balance_before"])
            ba = float(t["balance_after"])
            amt = float(t["amount"])
            signed = amt if t["direction"] == "CREDIT" else -amt
            if abs(bb - expected_bal) > 0.02 or abs((bb + signed) - ba) > 0.02:
                c5_errs += 1
                add_exc(
                    "ledger_reconciliation",
                    "BALANCE_ARITHMETIC_MISMATCH",
                    "CRITICAL",
                    "TRANSACTION",
                    t["transaction_id"],
                    aid,
                    "balance_before == prev_balance_after and balance_before + signed_amount == balance_after",
                    f"expected_before={expected_bal:.2f}, got before={bb:.2f}, after={ba:.2f}",
                    "Recompute ledger sequence and hold posting.",
                )
            expected_bal = ba
            min_allowed = -od_limit if od_allowed == 1 else 0.0
            if ba < min_allowed - 0.01:
                c5_errs += 1
                add_exc(
                    "ledger_reconciliation",
                    "NEGATIVE_BALANCE_NO_OVERDRAFT",
                    "CRITICAL",
                    "TRANSACTION",
                    t["transaction_id"],
                    aid,
                    "balance_after >= 0 when overdraft_allowed = 0",
                    f"Debit of ${amt:,.2f} moved balance {bb:,.2f} -> {ba:,.2f} (overdraft_allowed={od_allowed})",
                    "Freeze ledger posting and escalate to reconciliation ops.",
                )
        if abs(expected_bal - float(acct["current_balance"])) > 0.02:
            c5_errs += 1
            add_exc(
                "ledger_reconciliation",
                "ACCOUNT_BALANCE_MISMATCH",
                "CRITICAL",
                "ACCOUNT",
                aid,
                aid,
                "account.current_balance == final ledger balance_after",
                f"account={acct['current_balance']}, ledger_final={expected_bal:.2f}",
                "Reconcile account ending balance.",
            )
    check_results.append({
        "check_id": 5,
        "name": "Running Balance & Overdraft Reconciliation",
        "records_checked": len(data["transactions"]) + len(acct_by_id),
        "violations": c5_errs,
        "status": "PASS" if c5_errs == 0 else "FAIL",
    })

    # ------------------------------------------------------------------
    # Check 6: Account Status & Post-Closure Enforcement
    # ------------------------------------------------------------------
    c6_errs = 0
    for t in data["transactions"]:
        acct = acct_by_id.get(t["account_id"])
        if acct and acct["status"] == "CLOSED" and acct["closed_at"]:
            if _parse_dt(t["occurred_at"]) > _parse_dt(acct["closed_at"]):
                c6_errs += 1
                add_exc(
                    "closed_account_enforcement",
                    "TXN_ON_CLOSED_ACCOUNT",
                    "HIGH",
                    "TRANSACTION",
                    t["transaction_id"],
                    t["account_id"],
                    "Transaction occurred_at must precede account closed_at",
                    f"Txn at {t['occurred_at']} (${float(t['amount']):,.2f}) after closed_at {acct['closed_at']}",
                    "Quarantine transaction from scoring & audit settlement channel.",
                )
    check_results.append({
        "check_id": 6,
        "name": "Closed-Account Posting Enforcement",
        "records_checked": len(data["transactions"]),
        "violations": c6_errs,
        "status": "PASS" if c6_errs == 0 else "FAIL",
    })

    # ------------------------------------------------------------------
    # Check 7: Transfer-Leg Double-Entry Reconciliation
    # ------------------------------------------------------------------
    c7_errs = 0
    for trl in data["transfer_links"]:
        d_txn = txn_by_id.get(trl["debit_txn_id"])
        c_txn = txn_by_id.get(trl["credit_txn_id"]) if trl["credit_txn_id"] else None
        if (
            trl["status"] != "SETTLED"
            or c_txn is None
            or d_txn is None
            or abs(float(d_txn["amount"]) - float(c_txn["amount"])) > 0.01
            or abs(float(d_txn["amount"]) - float(trl["transfer_amount"])) > 0.01
        ):
            c7_errs += 1
            add_exc(
                "transfer_reconciliation",
                "UNRECONCILED_TRANSFER_LEG",
                "CRITICAL",
                "TRANSFER_LINK",
                trl["transfer_id"],
                trl["source_account_id"],
                "TransferLink must have matching SETTLED debit & credit legs",
                f"status={trl['status']}, debit={d_txn['amount'] if d_txn else None}, credit_txn={trl['credit_txn_id']}, credit={c_txn['amount'] if c_txn else None}",
                "Hold settlement & reconcile missing/mismatched counterparty leg.",
            )
    check_results.append({
        "check_id": 7,
        "name": "Transfer-Leg Double-Entry Reconciliation",
        "records_checked": len(data["transfer_links"]),
        "violations": c7_errs,
        "status": "PASS" if c7_errs == 0 else "FAIL",
    })

    # ------------------------------------------------------------------
    # Check 8: Alert Trigger Fact Traceability
    # ------------------------------------------------------------------
    c8_errs = 0
    facts_by_alert: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for f in data["alert_trigger_facts"]:
        facts_by_alert[f["alert_id"]].append(f)

    for al in data["alerts"]:
        f_list = facts_by_alert.get(al["alert_id"], [])
        if al["primary_txn_id"] is None or len(f_list) == 0:
            c8_errs += 1
            add_exc(
                "alert_traceability",
                "ORPHAN_ALERT_NO_TRIGGER",
                "MEDIUM",
                "ALERT",
                al["alert_id"],
                al["account_id"],
                "Every Alert must reference primary_txn_id and >= 1 AlertTriggerFact",
                f"primary_txn_id={al['primary_txn_id']}, fact_count={len(f_list)}, rule={al['rule_id']}",
                "Quarantine unsubstantiated alert; audit rule ingestion pipeline.",
            )
    check_results.append({
        "check_id": 8,
        "name": "Alert Trigger Fact Traceability",
        "records_checked": len(data["alerts"]),
        "violations": c8_errs,
        "status": "PASS" if c8_errs == 0 else "FAIL",
    })

    # ------------------------------------------------------------------
    # Check 9: Lifecycle State Transitions & Duplicate Checks
    # ------------------------------------------------------------------
    c9_errs = 0
    c9_checked = 0

    # Account state transition sequence
    ase_by_acct: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in data["account_state_events"]:
        ase_by_acct[ev["account_id"]].append(ev)
    for aid, evs in ase_by_acct.items():
        evs.sort(key=lambda e: (e["effective_at"], e["event_id"]))
        for ev in evs:
            c9_checked += 1
            if ev["new_status"] not in _ACCOUNT_ALLOWED_TRANSITIONS.get(ev["prev_status"], set()):
                c9_errs += 1
                add_exc(
                    "lifecycle_and_duplicates",
                    "ILLEGAL_ACCOUNT_TRANSITION",
                    "HIGH",
                    "ACCOUNT_STATE_EVENT",
                    ev["event_id"],
                    aid,
                    "AccountStateEvent must follow legal lifecycle graph",
                    f"{ev['prev_status']} -> {ev['new_status']}",
                    "Audit account lifecycle event log.",
                )

    # Case state transition sequence
    cse_by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ev in data["case_state_events"]:
        cse_by_case[ev["case_id"]].append(ev)
    for cid, evs in cse_by_case.items():
        evs.sort(key=lambda e: (e["effective_at"], e["case_event_id"]))
        for ev in evs:
            c9_checked += 1
            prev_s = ev["prev_status"]
            new_s = ev["new_status"]
            if prev_s is None:
                if new_s != "OPEN":
                    c9_errs += 1
            elif new_s not in ALLOWED_TRANSITIONS.get(prev_s, set()):
                c9_errs += 1
                add_exc(
                    "lifecycle_and_duplicates",
                    "ILLEGAL_CASE_TRANSITION",
                    "HIGH",
                    "CASE_STATE_EVENT",
                    ev["case_event_id"],
                    case_by_id.get(cid, {}).get("primary_account_id"),
                    "CaseStateEvent must follow legal workflow state machine",
                    f"{prev_s} -> {new_s}",
                    "Review out-of-order case transition.",
                )

    # Duplicate unique bridge checks (TransferLink.debit_txn_id, CaseAlertLink.alert_id)
    seen_deb: set[str] = set()
    for trl in data["transfer_links"]:
        c9_checked += 1
        if trl["debit_txn_id"] in seen_deb:
            c9_errs += 1
            add_exc(
                "lifecycle_and_duplicates",
                "DUPLICATE_TRANSFER_DEBIT",
                "HIGH",
                "TRANSFER_LINK",
                trl["transfer_id"],
                trl["source_account_id"],
                "TransferLink.debit_txn_id must be unique",
                f"Duplicate debit_txn_id {trl['debit_txn_id']}",
                "Deduplicate transfer link.",
            )
        seen_deb.add(trl["debit_txn_id"])

    seen_cal_al: set[str] = set()
    for cal in data["case_alert_links"]:
        c9_checked += 1
        if cal["alert_id"] in seen_cal_al:
            c9_errs += 1
            add_exc(
                "lifecycle_and_duplicates",
                "DUPLICATE_ALERT_ASSIGNMENT",
                "MEDIUM",
                "CASE_ALERT_LINK",
                cal["case_alert_id"],
                None,
                "Each Alert may belong to at most one Case",
                f"Duplicate alert_id {cal['alert_id']}",
                "Merge duplicate case link.",
            )
        seen_cal_al.add(cal["alert_id"])

    check_results.append({
        "check_id": 9,
        "name": "Lifecycle Transitions & Bridge Uniqueness",
        "records_checked": c9_checked,
        "violations": c9_errs,
        "status": "PASS" if c9_errs == 0 else "FAIL",
    })

    by_issue: dict[str, int] = defaultdict(int)
    for q in quarantine:
        by_issue[q["issue_type"]] += 1

    summary = {
        "export_dir": str(export_dir),
        "total_checks": len(check_results),
        "checks_passed_clean": sum(1 for c in check_results if c["status"] == "PASS"),
        "checks_with_quarantined_violations": sum(1 for c in check_results if c["violations"] > 0),
        "total_quarantined_exceptions": len(quarantine),
        "exceptions_by_issue_type": dict(by_issue),
        "checks": check_results,
    }

    if write_reports:
        reports_dir = export_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        (reports_dir / "quarantine_exceptions.json").write_text(json.dumps(quarantine, indent=2) + "\n", encoding="utf-8")

        md_lines = [
            "# YottaFlex Integrity & Reconciliation Validation Summary",
            "",
            f"- **Dataset:** `{export_dir}`",
            f"- **Checks Executed:** `{len(check_results)}`",
            f"- **Total Quarantined Exceptions:** `{len(quarantine)}`",
            "",
            "## Check Matrix",
            "",
            "| # | Validation Check | Records Checked | Violations Caught | Status |",
            "| :---: | :--- | ---: | ---: | :---: |",
        ]
        for cr in check_results:
            md_lines.append(
                f"| {cr['check_id']} | {cr['name']} | {cr['records_checked']:,} | {cr['violations']} | **{cr['status']}** |"
            )
        md_lines.extend([
            "",
            "## Quarantined Exceptions by Issue Type",
            "",
            "| Issue Type | Count |",
            "| :--- | ---: |",
        ])
        for itype, cnt in sorted(by_issue.items()):
            md_lines.append(f"| `{itype}` | {cnt} |")
        md_lines.append("")
        (reports_dir / "validation_summary.md").write_text("\n".join(md_lines), encoding="utf-8")

    return {"summary": summary, "quarantine": quarantine}

"""SQLite-backed analytical query & dossier service for the Analyst Workbench."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from yottaflex.auth.auth_service import ensure_auth_schema, list_admin_users, update_admin_user
from yottaflex.engine.risk_scoring import (
    detect_integrity_anomalies,
    ensure_scoring_history_schema,
    evaluate_transaction_against_rules,
    get_risk_scoring_overview,
    get_rule_executions_and_history,
    update_rule_and_reevaluate,
)
from yottaflex.evaluation.calibration_ops import (
    compute_feature_psi,
    compute_lift_curve,
    compute_rule_marginal_lift,
    compute_score_histogram,
    compute_temporal_drift,
    compute_typology_severity_matrix,
    sweep_rule_threshold,
)
from yottaflex.evaluation.harness import _ndcg_at_k
from yottaflex.evaluation.intelligence_ops import (
    check_live_zero_leakage,
    enrich_typology_percentiles,
    export_evaluation_report,
    get_rule_performance_attribution,
    run_what_if_rule_simulation,
    simulate_queue_cutoff,
    verify_export_manifest,
)
from yottaflex.workflow.automation_ops import (
    approve_calibration_proposal,
    create_calibration_proposal,
    create_notification,
    ensure_automation_schema,
    enqueue_or_dispatch_siem,
    find_case_merge_candidates,
    forecast_alert_capacity,
    get_user_preferences,
    list_calibration_proposals,
    list_notifications,
    list_pipeline_runs,
    list_siem_outbox,
    mark_notifications_read,
    merge_cases,
    run_pipeline_job,
    run_sandbox_pattern,
    update_user_preferences,
)
from yottaflex.workflow.forensics_ops import (
    add_case_comment,
    add_case_pin,
    apply_playbook_to_case,
    create_suppression_rule,
    deactivate_suppression_rule,
    delete_case_pin,
    delete_high_risk_country,
    detect_structuring_clusters,
    ensure_forensics_schema,
    generate_rfi_packet,
    get_account_control,
    get_account_velocity,
    get_corridor_risk_matrix,
    get_customer_peer_baseline,
    get_merchant_detail,
    get_merchant_leaderboard,
    get_playbooks,
    get_sla_radar,
    list_case_comments,
    list_case_pins,
    list_export_history,
    list_high_risk_countries,
    list_kyc_reviews,
    list_pending_escalations,
    list_suppression_rules,
    log_export_event,
    match_suppression_for_alert,
    rebalance_queue_workload,
    set_account_control,
    submit_kyc_review,
    trace_flow_chains,
    upsert_high_risk_country,
)
from yottaflex.workflow.governance_ops import (
    bulk_review_quarantine,
    create_saved_view,
    delete_saved_view,
    ensure_governance_schema,
    export_audit_events,
    export_quarantine_report,
    get_analyst_leaderboard,
    get_quarantine_detail,
    get_sla_policies,
    get_unified_audit_events,
    list_quarantine_exceptions_filtered,
    list_saved_views,
    list_watchlist_tags,
    review_quarantine_exception,
    run_live_integrity_validation,
    update_sla_policies,
)
from yottaflex.workflow.network_ops import (
    detect_collusion_rings,
    export_executive_digest,
    get_entity_network,
    get_executive_digest,
    get_similar_cases,
    get_system_health,
    global_cross_entity_search,
    list_sar_registry,
    transition_sar_status,
)
from yottaflex.workflow.network_intelligence import (
    compute_network_risk_analysis,
    detect_circular_transfers,
    detect_suspicious_patterns,
    get_financial_network_graph,
    get_network_overview as get_financial_network_overview,
    resolve_entities,
    search_entities as search_network_entities,
    trace_money_flow_path,
)
from yottaflex.workflow.triage_extensions import ensure_triage_extensions_schema
from yottaflex.workflow.enterprise_ops import (
    add_case_handoff,
    add_workspace_pin,
    batch_simulate_transactions,
    bulk_tag_cases,
    check_balance_continuity,
    compare_two_cases,
    create_case_evidence_seal,
    create_custom_rule_draft,
    create_search_bookmark,
    create_webhook,
    delete_search_bookmark,
    delete_webhook,
    delete_workspace_pin,
    detect_mcc_outliers,
    ensure_enterprise_schema,
    find_shared_pii_clusters,
    generate_goaml_xml,
    get_account_burst_profile,
    get_account_transfer_matrix,
    get_alert_co_occurrence,
    get_alert_fatigue_report,
    get_customer_chronology,
    get_customer_corridor_exposure,
    get_data_scorecard,
    get_device_velocity_leaderboard,
    get_fan_in_out_hubs,
    get_quarantine_grouped_summary,
    get_related_cases_timeline,
    get_retention_status,
    get_tier_workload_projection,
    list_case_handoffs,
    list_case_seals,
    list_custom_rule_drafts,
    list_exam_readiness,
    list_qa_samples,
    list_scheduled_digests,
    list_screening_history,
    list_search_bookmarks,
    list_webhooks,
    list_workspace_pins,
    reopen_closed_case,
    run_sanctions_screening,
    run_sla_auto_escalation,
    simulate_case_what_if_score,
    submit_qa_grade,
    test_webhook_ping,
    update_exam_readiness,
    update_retention_policy,
    upsert_scheduled_digest,
    verify_audit_chain_integrity,
)


def _parse_iso_dt(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _sla_metrics(created_at: str | None, ref_dt: datetime | None, sla_hours: int, is_active: bool) -> tuple[float, bool]:
    c_dt = _parse_iso_dt(created_at)
    if not c_dt or not ref_dt:
        return 0.0, False
    age_h = round(max(0.0, (ref_dt - c_dt).total_seconds() / 3600.0), 1)
    breached = bool(is_active and age_h > float(sla_hours))
    return age_h, breached


class WorkbenchService:
    """Queries yottaflex.db cleanly; ground_truth is only read inside get_evaluation()."""

    def __init__(self, export_dir: Path) -> None:
        self.export_dir = export_dir.resolve()
        self.db_path = self.export_dir / "yottaflex.db"
        self.manifest_path = self.export_dir / "manifest.json"
        self.gt_path = self.export_dir / "ground_truth" / "ground_truth.json"
        if not self.db_path.exists():
            schema_sql_path = self.export_dir / "sql" / "schema.sql"
            seed_sql_path = self.export_dir / "sql" / "seed.sql"
            if schema_sql_path.exists() and seed_sql_path.exists():
                conn = sqlite3.connect(self.db_path)
                try:
                    conn.execute("PRAGMA foreign_keys = OFF;")
                    conn.executescript(schema_sql_path.read_text(encoding="utf-8"))
                    conn.executescript(seed_sql_path.read_text(encoding="utf-8"))
                    conn.execute("PRAGMA foreign_keys = ON;")
                    conn.commit()
                finally:
                    conn.close()
            else:
                raise FileNotFoundError(f"SQLite database not found at {self.db_path}")
        ensure_auth_schema(self.db_path)
        self._ensure_perf_indexes()

    def _ensure_perf_indexes(self) -> None:
        """Create non-mutating query indexes idempotently for 100k+ row responsiveness."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(
                """
                CREATE INDEX IF NOT EXISTS idx_alert_facts_txn ON alert_trigger_facts(transaction_id);
                CREATE INDEX IF NOT EXISTS idx_transfer_links_debit ON transfer_links(debit_txn_id);
                CREATE INDEX IF NOT EXISTS idx_transfer_links_credit ON transfer_links(credit_txn_id);
                CREATE INDEX IF NOT EXISTS idx_acct_state_events_acct ON account_state_events(account_id, prev_status, new_status);
                CREATE INDEX IF NOT EXISTS idx_acct_ownerships_cust ON account_ownerships(customer_id, account_id);
                CREATE INDEX IF NOT EXISTS idx_alerts_cust ON alerts(customer_id, account_id);
                CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts(rule_id);
                CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_transactions_occurred ON transactions(occurred_at DESC, transaction_id DESC);
                CREATE INDEX IF NOT EXISTS idx_transactions_amount ON transactions(amount DESC, transaction_id DESC);
                """
            )
            conn.row_factory = sqlite3.Row
            ensure_scoring_history_schema(conn)
            ensure_triage_extensions_schema(conn)
            ensure_governance_schema(conn)
            ensure_forensics_schema(conn)
            ensure_automation_schema(conn)
            ensure_enterprise_schema(conn)
            conn.commit()
        finally:
            conn.close()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Dynamic Quarantine / Invariant Scanner (Zero Ground-Truth Access)
    # ------------------------------------------------------------------
    def get_quarantine_exceptions(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            exceptions: list[dict[str, Any]] = []

            # 1. TXN_ON_CLOSED_ACCOUNT
            rows = conn.execute(
                """
                SELECT t.transaction_id, t.account_id, t.occurred_at, t.amount, a.closed_at
                FROM transactions t
                JOIN accounts a ON a.account_id = t.account_id
                WHERE a.status = 'CLOSED' AND a.closed_at IS NOT NULL AND t.occurred_at > a.closed_at
                ORDER BY t.occurred_at
                """
            ).fetchall()
            for r in rows:
                exceptions.append({
                    "exception_id": f"EXC-CLOSED-{r['transaction_id']}",
                    "issue_type": "TXN_ON_CLOSED_ACCOUNT",
                    "severity": "HIGH",
                    "entity_type": "TRANSACTION",
                    "entity_id": r["transaction_id"],
                    "account_id": r["account_id"],
                    "violated_invariant": "Transaction occurred_at must precede account closed_at",
                    "evidence": f"Txn occurred {r['occurred_at']} (${r['amount']:,.2f}) after account closed at {r['closed_at']}",
                    "remediation": "Quarantine transaction from scoring & alert settlement ops.",
                })

            # 2. NEGATIVE_BALANCE_NO_OVERDRAFT
            rows = conn.execute(
                """
                SELECT t.transaction_id, t.account_id, t.occurred_at, t.amount, t.balance_before, t.balance_after,
                       a.overdraft_allowed, a.overdraft_limit
                FROM transactions t
                JOIN accounts a ON a.account_id = t.account_id
                WHERE a.overdraft_allowed = 0 AND t.balance_after < 0
                ORDER BY t.occurred_at
                """
            ).fetchall()
            for r in rows:
                exceptions.append({
                    "exception_id": f"EXC-NEGOD-{r['transaction_id']}",
                    "issue_type": "NEGATIVE_BALANCE_NO_OVERDRAFT",
                    "severity": "CRITICAL",
                    "entity_type": "TRANSACTION",
                    "entity_id": r["transaction_id"],
                    "account_id": r["account_id"],
                    "violated_invariant": "balance_after >= 0 when overdraft_allowed = 0",
                    "evidence": f"Debit of ${r['amount']:,.2f} moved balance {r['balance_before']:,.2f} -> {r['balance_after']:,.2f} with overdraft_allowed=0",
                    "remediation": "Freeze ledger posting and escalate to reconciliation ops.",
                })

            # 3. UNRECONCILED_TRANSFER_LEG
            rows = conn.execute(
                """
                SELECT tr.transfer_id, tr.source_account_id, tr.dest_account_id, tr.transfer_amount, tr.status,
                       tr.debit_txn_id, tr.credit_txn_id,
                       dt.amount AS debit_amt, ct.amount AS credit_amt
                FROM transfer_links tr
                LEFT JOIN transactions dt ON dt.transaction_id = tr.debit_txn_id
                LEFT JOIN transactions ct ON ct.transaction_id = tr.credit_txn_id
                WHERE tr.credit_txn_id IS NULL
                   OR ABS(COALESCE(dt.amount, 0) - COALESCE(ct.amount, 0)) > 0.001
                   OR tr.status != 'SETTLED'
                ORDER BY tr.transfer_id
                """
            ).fetchall()
            for r in rows:
                exceptions.append({
                    "exception_id": f"EXC-TRL-{r['transfer_id']}",
                    "issue_type": "UNRECONCILED_TRANSFER_LEG",
                    "severity": "CRITICAL",
                    "entity_type": "TRANSFER_LINK",
                    "entity_id": r["transfer_id"],
                    "account_id": r["source_account_id"],
                    "violated_invariant": "Double-entry transfer legs must exist and debit_amt == credit_amt",
                    "evidence": f"status={r['status']}, debit_amt={r['debit_amt']}, credit_txn={r['credit_txn_id']}, credit_amt={r['credit_amt']}",
                    "remediation": "Hold settlement & reconcile missing/mismatched counterparty leg.",
                })

            # 4. ORPHAN_ALERT_NO_TRIGGER
            rows = conn.execute(
                """
                SELECT a.alert_id, a.account_id, a.rule_id, a.primary_txn_id, a.trigger_txn_count, a.created_at,
                       COUNT(f.fact_id) AS fact_count
                FROM alerts a
                LEFT JOIN alert_trigger_facts f ON f.alert_id = a.alert_id
                GROUP BY a.alert_id
                HAVING a.primary_txn_id IS NULL OR fact_count = 0
                ORDER BY a.alert_id
                """
            ).fetchall()
            for r in rows:
                exceptions.append({
                    "exception_id": f"EXC-ORPHAN-{r['alert_id']}",
                    "issue_type": "ORPHAN_ALERT_NO_TRIGGER",
                    "severity": "MEDIUM",
                    "entity_type": "ALERT",
                    "entity_id": r["alert_id"],
                    "account_id": r["account_id"],
                    "violated_invariant": "Every alert must reference >= 1 triggering transaction & AlertTriggerFact",
                    "evidence": f"primary_txn_id={r['primary_txn_id']}, fact_count={r['fact_count']}, rule={r['rule_id']}",
                    "remediation": "Quarantine unsubstantiated alert; audit rule ingestion pipeline.",
                })

            # 5. DISPOSITION_PRECEDES_ALERT
            rows = conn.execute(
                """
                SELECT aa.action_id, aa.case_id, aa.action_type, aa.acted_at,
                       MIN(al.created_at) AS earliest_alert_at, c.primary_account_id
                FROM analyst_actions aa
                JOIN cases c ON c.case_id = aa.case_id
                JOIN case_alert_links cal ON cal.case_id = aa.case_id
                JOIN alerts al ON al.alert_id = cal.alert_id
                GROUP BY aa.action_id
                HAVING aa.acted_at < earliest_alert_at
                ORDER BY aa.action_id
                """
            ).fetchall()
            for r in rows:
                exceptions.append({
                    "exception_id": f"EXC-TIME-{r['action_id']}",
                    "issue_type": "DISPOSITION_PRECEDES_ALERT",
                    "severity": "HIGH",
                    "entity_type": "ANALYST_ACTION",
                    "entity_id": r["action_id"],
                    "account_id": r["primary_account_id"],
                    "violated_invariant": "AnalystAction.acted_at must be >= linked Alert.created_at",
                    "evidence": f"Action {r['action_type']} on {r['case_id']} at {r['acted_at']} precedes alert {r['earliest_alert_at']}",
                    "remediation": "Invalidate premature disposition and reopen case for compliant review.",
                })

            by_type: dict[str, int] = defaultdict(int)
            for ex in exceptions:
                by_type[ex["issue_type"]] += 1

            return {
                "total_exceptions": len(exceptions),
                "counts_by_issue_type": dict(by_type),
                "exceptions": exceptions,
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Transparent Score Decomposition Helper (Zero Ground Truth)
    # ------------------------------------------------------------------
    def _explain_case_row(self, conn: sqlite3.Connection, case_row: sqlite3.Row) -> dict[str, Any]:
        cid = case_row["case_id"]
        alerts = conn.execute(
            """
            SELECT a.*, r.rule_name, r.category AS rule_category
            FROM alerts a
            JOIN case_alert_links cal ON cal.alert_id = a.alert_id
            JOIN risk_rules r ON r.rule_id = a.rule_id
            WHERE cal.case_id = ?
            ORDER BY a.created_at, a.alert_id
            """,
            (cid,),
        ).fetchall()

        cust = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (case_row["primary_customer_id"],)
        ).fetchone()

        unique_rules = sorted({a["rule_id"] for a in alerts})
        max_alert_score = max((float(a["risk_score"]) for a in alerts), default=0.0)
        rule_diversity_bonus = min(15.0, max(0, len(unique_rules) - 1) * 6.5)
        rule_component = min(48.0, round(max_alert_score * 0.42 + rule_diversity_bonus, 2))

        linked_accts = sorted({a["account_id"] for a in alerts})
        acct_spread = min(14.0, max(0, len(linked_accts) - 1) * 4.5)
        ring_bonus = 10.0 if "RULE-003" in unique_rules else 0.0
        shared_dev_bonus = 8.0 if "RULE-007" in unique_rules else 0.0
        network_component = min(26.0, round(acct_spread + ring_bonus + shared_dev_bonus, 2))

        exposure_component = min(18.0, round((float(case_row["total_exposure_amount"]) / 1500.0) * 1.8, 2))

        kyc_tier = cust["kyc_tier"] if cust else "STANDARD"
        kyc_pts = {"LOW": 6.0, "STANDARD": 3.0, "ENHANCED": 0.0}.get(kyc_tier, 3.0)
        dormant_cnt = conn.execute(
            f"""
            SELECT COUNT(*) FROM account_state_events
            WHERE new_status = 'DORMANT' AND account_id IN ({",".join(["?"] * len(linked_accts))})
            """,
            linked_accts,
        ).fetchone()[0] if linked_accts else 0
        dormant_pts = 5.0 if dormant_cnt > 0 else 0.0
        new_dev_pts = 4.0 if "RULE-002" in unique_rules else 0.0
        context_component = min(15.0, round(kyc_pts + dormant_pts + new_dev_pts, 2))

        positive_sum = round(rule_component + network_component + exposure_component + context_component, 2)
        mitigator = round(float(case_row["priority_score"]) - positive_sum, 2)
        if mitigator > 0:
            mitigator = 0.0

        return {
            "rule_severity": rule_component,
            "network_blast_radius": network_component,
            "financial_exposure": exposure_component,
            "entity_lifecycle_context": context_component,
            "benign_mitigators": mitigator,
            "rules_triggered": unique_rules,
        }

    # ------------------------------------------------------------------
    # Overview & Case Queue
    # ------------------------------------------------------------------
    def get_overview(self) -> dict[str, Any]:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8")) if self.manifest_path.exists() else {}
        conn = self._conn()
        try:
            counts = {
                "customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
                "accounts": conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
                "merchants": conn.execute("SELECT COUNT(*) FROM merchants").fetchone()[0],
                "devices": conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
                "transactions": conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
                "transfer_links": conn.execute("SELECT COUNT(*) FROM transfer_links").fetchone()[0],
                "alerts": conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0],
                "cases": conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0],
                "pure_open_cases": conn.execute("SELECT COUNT(*) FROM cases WHERE status = 'OPEN'").fetchone()[0],
                "under_investigation_cases": conn.execute("SELECT COUNT(*) FROM cases WHERE status = 'IN_REVIEW'").fetchone()[0],
                "escalated_cases": conn.execute("SELECT COUNT(*) FROM cases WHERE status = 'ESCALATED'").fetchone()[0],
                "open_cases": conn.execute("SELECT COUNT(*) FROM cases WHERE status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')").fetchone()[0],
                "closed_cases": conn.execute("SELECT COUNT(*) FROM cases WHERE status IN ('SAR_FILED', 'CLOSED_CONFIRMED_FRAUD', 'CLOSED_FALSE_POSITIVE')").fetchone()[0],
                "total_case_exposure": round(conn.execute("SELECT COALESCE(SUM(total_exposure_amount), 0) FROM cases").fetchone()[0], 2),
            }
            tier_rows = conn.execute("SELECT priority_tier, COUNT(*) AS cnt FROM cases GROUP BY priority_tier").fetchall()
            tier_dist = {r["priority_tier"]: r["cnt"] for r in tier_rows}
            status_rows = conn.execute("SELECT status, COUNT(*) AS cnt FROM cases GROUP BY status").fetchall()
            status_dist = {r["status"]: r["cnt"] for r in status_rows}

            compression = round(counts["alerts"] / max(1, counts["cases"]), 2)
            quarantine = self.get_quarantine_exceptions()

            return {
                "seed": manifest.get("seed"),
                "scale": manifest.get("scale"),
                "schema_version": manifest.get("schema_version"),
                "counts": counts,
                "alert_to_case_compression": compression,
                "tier_distribution": tier_dist,
                "status_distribution": status_dist,
                "quarantine_count": quarantine["total_exceptions"],
            }
        finally:
            conn.close()

    def list_cases(
        self,
        *,
        sort: str = "priority",
        tier: str | None = None,
        status: str | None = None,
        linkage: str | None = None,
        search: str | None = None,
        assigned_analyst: str | None = None,
        min_exposure: float | None = None,
        max_exposure: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        sla_breached: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            ref_row = conn.execute("SELECT MAX(created_at) FROM cases").fetchone()
            ref_dt = _parse_iso_dt(ref_row[0]) if ref_row and ref_row[0] else None
            sla_policy_map = get_sla_policies(conn)["map"].get("CASE", {})

            where = ["1=1"]
            params: list[Any] = []
            if tier and tier != "ALL":
                where.append("COALESCE(ctm.priority_override_tier, c.priority_tier) = ?")
                params.append(tier)
            if status and status != "ALL":
                if status == "ACTIVE_QUEUE":
                    where.append("c.status IN ('OPEN', 'IN_REVIEW', 'ESCALATED')")
                else:
                    where.append("c.status = ?")
                    params.append(status)
            if linkage and linkage != "ALL":
                where.append("c.linkage_summary = ?")
                params.append(linkage)
            if assigned_analyst and assigned_analyst != "ALL":
                if assigned_analyst == "UNASSIGNED":
                    where.append("ctm.assigned_analyst_id IS NULL")
                else:
                    where.append("ctm.assigned_analyst_id = ?")
                    params.append(assigned_analyst)
            if min_exposure is not None:
                where.append("c.total_exposure_amount >= ?")
                params.append(float(min_exposure))
            if max_exposure is not None:
                where.append("c.total_exposure_amount <= ?")
                params.append(float(max_exposure))
            if start_date:
                where.append("c.created_at >= ?")
                params.append(f"{start_date}T00:00:00Z" if len(start_date) == 10 else start_date)
            if end_date:
                where.append("c.created_at <= ?")
                params.append(f"{end_date}T23:59:59Z" if len(end_date) == 10 else end_date)
            if search:
                q = f"%{search.strip()}%"
                where.append("(c.case_id LIKE ? OR c.primary_account_id LIKE ? OR c.primary_customer_id LIKE ? OR cu.full_name LIKE ?)")
                params.extend([q, q, q, q])

            where_sql = " AND ".join(where)
            order_sql = (
                "c.created_at ASC, c.case_id ASC"
                if sort == "fifo"
                else "COALESCE(ctm.priority_override_score, c.priority_score) DESC, c.total_exposure_amount DESC, c.case_id ASC"
            )

            rank_cte = """
                WITH ranked_cases AS (
                    SELECT c.case_id,
                           RANK() OVER (ORDER BY COALESCE(ctm2.priority_override_score, c.priority_score) DESC, c.total_exposure_amount DESC, c.case_id ASC) AS priority_rank,
                           RANK() OVER (ORDER BY c.created_at ASC, c.case_id ASC) AS fifo_rank
                    FROM cases c
                    LEFT JOIN case_triage_meta ctm2 ON ctm2.case_id = c.case_id
                )
            """

            rows = conn.execute(
                f"""
                {rank_cte}
                SELECT c.*, cu.full_name AS customer_name, cu.kyc_tier, cu.segment, cu.home_country,
                       ctm.assigned_analyst_id,
                       ctm.priority_override_tier,
                       ctm.priority_override_score,
                       ctm.override_reason,
                       COALESCE(ctm.sla_hours, 48) AS sla_hours,
                       COALESCE(ctm.priority_override_tier, c.priority_tier) AS effective_priority_tier,
                       COALESCE(ctm.priority_override_score, c.priority_score) AS effective_priority_score,
                       ctm.sla_hours AS custom_sla_hours,
                       rc.priority_rank,
                       rc.fifo_rank,
                       (rc.fifo_rank - rc.priority_rank) AS rank_delta
                FROM cases c
                JOIN customers cu ON cu.customer_id = c.primary_customer_id
                JOIN ranked_cases rc ON rc.case_id = c.case_id
                LEFT JOIN case_triage_meta ctm ON ctm.case_id = c.case_id
                WHERE {where_sql}
                ORDER BY {order_sql}
                """,
                params,
            ).fetchall()

            enriched_all: list[dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                is_active = item["status"] in {"OPEN", "IN_REVIEW", "ESCALATED"}
                tier_key = str(item.get("effective_priority_tier") or item.get("priority_tier") or "MEDIUM")
                policy_hrs = int(sla_policy_map.get(tier_key, 48))
                eff_sla = int(item["custom_sla_hours"]) if item.get("custom_sla_hours") is not None else policy_hrs
                item["sla_hours"] = eff_sla
                item.pop("custom_sla_hours", None)
                age_h, breached = _sla_metrics(item["created_at"], ref_dt, eff_sla, is_active)
                item["age_hours"] = age_h
                item["sla_breached"] = breached
                item["requires_reviewer_signoff"] = float(item["total_exposure_amount"]) >= 25000.0
                if sla_breached is True and not breached:
                    continue
                if sla_breached is False and breached:
                    continue
                enriched_all.append(item)

            total = len(enriched_all)
            page_items = enriched_all[offset : offset + limit]

            # Pre-fetch rules per case for fast queue pills
            case_ids = [r["case_id"] for r in page_items]
            rules_by_case: dict[str, list[str]] = defaultdict(list)
            if case_ids:
                ph = ",".join(["?"] * len(case_ids))
                r_rows = conn.execute(
                    f"""
                    SELECT DISTINCT cal.case_id, a.rule_id
                    FROM case_alert_links cal
                    JOIN alerts a ON a.alert_id = cal.alert_id
                    WHERE cal.case_id IN ({ph})
                    ORDER BY a.rule_id
                    """,
                    case_ids,
                ).fetchall()
                for rr in r_rows:
                    rules_by_case[rr["case_id"]].append(rr["rule_id"])

            items = []
            for idx, item in enumerate(page_items, start=offset + 1):
                item["queue_rank"] = idx
                item["rules_triggered"] = rules_by_case.get(item["case_id"], [])
                items.append(item)

            return {"total": total, "sort": sort, "items": items}
        finally:
            conn.close()

    def export_cases_report(self, *, fmt: str = "csv", **filters: Any) -> tuple[bytes, str, str]:
        data = self.list_cases(limit=5000, offset=0, **filters)
        if fmt == "json":
            return json.dumps(data, indent=2).encode("utf-8"), "application/json; charset=utf-8", "yottaflex_cases.json"
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([
            "case_id", "queue_rank", "priority_rank", "fifo_rank", "rank_delta",
            "status", "effective_priority_tier", "effective_priority_score",
            "customer_id", "customer_name", "primary_account_id", "total_exposure_amount",
            "alert_count", "assigned_analyst_id", "age_hours", "sla_breached", "created_at",
        ])
        for c in data["items"]:
            w.writerow([
                c["case_id"], c["queue_rank"], c["priority_rank"], c["fifo_rank"], c["rank_delta"],
                c["status"], c["effective_priority_tier"], c["effective_priority_score"],
                c["primary_customer_id"], c["customer_name"], c["primary_account_id"], c["total_exposure_amount"],
                c["alert_count"], c.get("assigned_analyst_id") or "", c["age_hours"], c["sla_breached"], c["created_at"],
            ])
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "yottaflex_cases.csv"

    # ------------------------------------------------------------------
    # Full Case Investigation Dossier + Network Subgraph + Reconciled Ledger
    # ------------------------------------------------------------------
    def get_case_dossier(self, case_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            case_row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
            if not case_row:
                return None

            waterfall = self._explain_case_row(conn, case_row)

            alerts = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT a.*, r.rule_name, r.category, r.threshold_desc, r.base_weight, cal.linkage_reason
                    FROM alerts a
                    JOIN case_alert_links cal ON cal.alert_id = a.alert_id
                    JOIN risk_rules r ON r.rule_id = a.rule_id
                    WHERE cal.case_id = ?
                    ORDER BY a.risk_score DESC, a.created_at
                    """,
                    (case_id,),
                ).fetchall()
            ]
            alert_ids = [a["alert_id"] for a in alerts]

            facts: list[dict[str, Any]] = []
            if alert_ids:
                ph = ",".join(["?"] * len(alert_ids))
                facts = [
                    dict(r)
                    for r in conn.execute(
                        f"SELECT * FROM alert_trigger_facts WHERE alert_id IN ({ph}) ORDER BY fact_id",
                        alert_ids,
                    ).fetchall()
                ]

            linked_acct_ids = sorted({a["account_id"] for a in alerts} | {case_row["primary_account_id"]})
            ph_a = ",".join(["?"] * len(linked_acct_ids))

            accounts = [
                dict(r) for r in conn.execute(f"SELECT * FROM accounts WHERE account_id IN ({ph_a})", linked_acct_ids).fetchall()
            ]
            ownerships = [
                dict(r)
                for r in conn.execute(
                    f"""
                    SELECT ao.*, c.full_name, c.kyc_tier, c.segment, c.home_country, c.risk_rating
                    FROM account_ownerships ao
                    JOIN customers c ON c.customer_id = ao.customer_id
                    WHERE ao.account_id IN ({ph_a})
                    """,
                    linked_acct_ids,
                ).fetchall()
            ]
            cust_ids = sorted({o["customer_id"] for o in ownerships})
            ph_c = ",".join(["?"] * len(cust_ids))
            customers = [
                dict(r) for r in conn.execute(f"SELECT * FROM customers WHERE customer_id IN ({ph_c})", cust_ids).fetchall()
            ]

            device_links = [
                dict(r)
                for r in conn.execute(
                    f"""
                    SELECT adl.*, d.os_family, d.is_emulator, d.ip_country, d.risk_tier AS device_risk_tier
                    FROM account_device_links adl
                    JOIN devices d ON d.device_id = adl.device_id
                    WHERE adl.account_id IN ({ph_a})
                    """,
                    linked_acct_ids,
                ).fetchall()
            ]

            account_events = [
                dict(r)
                for r in conn.execute(
                    f"SELECT * FROM account_state_events WHERE account_id IN ({ph_a}) ORDER BY effective_at, event_id",
                    linked_acct_ids,
                ).fetchall()
            ]

            # Ledger transactions across linked accounts (most recent 150 for crisp UI + reconciliation check)
            ledger_rows = [
                dict(r)
                for r in conn.execute(
                    f"""
                    SELECT t.*, m.merchant_name, m.category AS merchant_category, m.risk_tier AS merchant_risk_tier
                    FROM transactions t
                    LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
                    WHERE t.account_id IN ({ph_a})
                    ORDER BY t.occurred_at ASC, t.transaction_id ASC
                    """,
                    linked_acct_ids,
                ).fetchall()
            ]
            # Verify running reconciliation flag per txn
            acct_closed_at = {a["account_id"]: a["closed_at"] for a in accounts if a["status"] == "CLOSED" and a["closed_at"]}
            acct_od = {a["account_id"]: a["overdraft_allowed"] for a in accounts}
            for tx in ledger_rows:
                signed = tx["amount"] if tx["direction"] == "CREDIT" else -tx["amount"]
                arith_ok = abs((tx["balance_before"] + signed) - tx["balance_after"]) < 0.015
                closed_ok = True
                if tx["account_id"] in acct_closed_at and tx["occurred_at"] > acct_closed_at[tx["account_id"]]:
                    closed_ok = False
                od_ok = not (acct_od.get(tx["account_id"], 1) == 0 and tx["balance_after"] < 0)
                tx["reconciled_ok"] = arith_ok and closed_ok and od_ok

            transfers = [
                dict(r)
                for r in conn.execute(
                    f"""
                    SELECT * FROM transfer_links
                    WHERE source_account_id IN ({ph_a}) OR dest_account_id IN ({ph_a})
                    ORDER BY initiated_at ASC
                    """,
                    linked_acct_ids + linked_acct_ids,
                ).fetchall()
            ]

            # Expand neighbor accounts from transfers for complete ring visibility
            neighbor_accts = sorted(
                {tr["source_account_id"] for tr in transfers} | {tr["dest_account_id"] for tr in transfers}
            )

            # Build Network Graph (Nodes + Edges)
            nodes: list[dict[str, Any]] = []
            seen_nodes: set[str] = set()

            for c in customers:
                nid = c["customer_id"]
                if nid not in seen_nodes:
                    seen_nodes.add(nid)
                    nodes.append({
                        "id": nid,
                        "type": "CUSTOMER",
                        "label": c["full_name"],
                        "sublabel": f"{c['kyc_tier']} KYC • {c['home_country']}",
                        "risk": c["risk_rating"],
                    })

            for aid in sorted(set(linked_acct_ids) | set(neighbor_accts)):
                if aid not in seen_nodes:
                    seen_nodes.add(aid)
                    ar = acct_row = next((a for a in accounts if a["account_id"] == aid), None)
                    nodes.append({
                        "id": aid,
                        "type": "ACCOUNT",
                        "label": aid,
                        "sublabel": f"{ar['account_type']} • ${ar['current_balance']:,.0f}" if ar else "External Linked Account",
                        "risk": "HIGH" if aid in linked_acct_ids else "LOW",
                        "is_primary": aid == case_row["primary_account_id"],
                    })

            for dl in device_links:
                did = dl["device_id"]
                if did not in seen_nodes:
                    seen_nodes.add(did)
                    nodes.append({
                        "id": did,
                        "type": "DEVICE",
                        "label": did,
                        "sublabel": f"{dl['os_family']}{' • EMULATOR' if dl['is_emulator'] else ''}",
                        "risk": dl["device_risk_tier"],
                    })

            # High-value or triggering merchants
            fact_txn_ids = {f["transaction_id"] for f in facts}
            for tx in ledger_rows:
                if tx["merchant_id"] and (tx["transaction_id"] in fact_txn_ids or tx["merchant_risk_tier"] == "HIGH"):
                    mid = tx["merchant_id"]
                    if mid not in seen_nodes:
                        seen_nodes.add(mid)
                        nodes.append({
                            "id": mid,
                            "type": "MERCHANT",
                            "label": tx["merchant_name"] or mid,
                            "sublabel": f"{tx['merchant_category']} • {tx['counterparty_country']}",
                            "risk": tx["merchant_risk_tier"] or "LOW",
                        })

            edges: list[dict[str, Any]] = []
            for o in ownerships:
                edges.append({
                    "source": o["customer_id"],
                    "target": o["account_id"],
                    "type": "OWNS",
                    "label": o["ownership_role"],
                })
            for dl in device_links:
                edges.append({
                    "source": dl["account_id"],
                    "target": dl["device_id"],
                    "type": "USES_DEVICE",
                    "label": "TRUSTED" if dl["is_trusted"] else "NEW/UNTRUSTED",
                })
            for tr in transfers:
                edges.append({
                    "source": tr["source_account_id"],
                    "target": tr["dest_account_id"],
                    "type": "TRANSFER",
                    "label": f"${tr['transfer_amount']:,.0f}",
                    "amount": tr["transfer_amount"],
                    "status": tr["status"],
                })
            seen_m_edge: set[tuple[str, str]] = set()
            for tx in ledger_rows:
                if tx["merchant_id"] and tx["merchant_id"] in seen_nodes:
                    key = (tx["account_id"], tx["merchant_id"])
                    if key not in seen_m_edge:
                        seen_m_edge.add(key)
                        edges.append({
                            "source": tx["account_id"],
                            "target": tx["merchant_id"],
                            "type": "MERCHANT_TXN",
                            "label": f"${tx['amount']:,.0f}",
                        })

            actions = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM analyst_actions WHERE case_id = ? ORDER BY acted_at ASC, action_id ASC",
                    (case_id,),
                ).fetchall()
            ]
            case_events = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM case_state_events WHERE case_id = ? ORDER BY effective_at ASC, case_event_id ASC",
                    (case_id,),
                ).fetchall()
            ]

            meta_row = conn.execute("SELECT * FROM case_triage_meta WHERE case_id = ?", (case_id,)).fetchone()
            triage_meta = dict(meta_row) if meta_row else {
                "case_id": case_id,
                "assigned_analyst_id": None,
                "priority_override_tier": None,
                "priority_override_score": None,
                "override_reason": None,
                "override_by": None,
                "override_at": None,
                "sla_hours": 48,
                "sar_draft": None,
                "sar_updated_at": None,
            }
            chk_row = conn.execute("SELECT * FROM case_evidence_checklist WHERE case_id = ?", (case_id,)).fetchone()
            checklist = (
                {
                    "case_id": case_id,
                    "rules_reviewed": bool(chk_row["rules_reviewed"]),
                    "ledger_reconciled": bool(chk_row["ledger_reconciled"]),
                    "network_verified": bool(chk_row["network_verified"]),
                    "kyc_corroborated": bool(chk_row["kyc_corroborated"]),
                    "notes": chk_row["notes"] or "",
                    "updated_by": chk_row["updated_by"],
                    "updated_at": chk_row["updated_at"],
                }
                if chk_row
                else {
                    "case_id": case_id,
                    "rules_reviewed": False,
                    "ledger_reconciled": False,
                    "network_verified": False,
                    "kyc_corroborated": False,
                    "notes": "",
                    "updated_by": None,
                    "updated_at": None,
                }
            )
            watchlist_tags = [
                dict(r)
                for r in conn.execute(
                    f"""
                    SELECT * FROM entity_watchlist_tags
                    WHERE (entity_type = 'CUSTOMER' AND entity_id IN ({ph_c}))
                       OR (entity_type = 'ACCOUNT' AND entity_id IN ({ph_a}))
                    ORDER BY created_at DESC
                    """,
                    cust_ids + linked_acct_ids,
                ).fetchall()
            ]
            ref_row = conn.execute("SELECT MAX(created_at) FROM cases").fetchone()
            ref_dt = _parse_iso_dt(ref_row[0]) if ref_row and ref_row[0] else None
            sla_policy_map = get_sla_policies(conn)["map"].get("CASE", {})
            is_active = case_row["status"] in {"OPEN", "IN_REVIEW", "ESCALATED"}
            age_h, sla_breached = _sla_metrics(case_row["created_at"], ref_dt, int(triage_meta.get("sla_hours") or 48), is_active)

            case_dict = dict(case_row)
            case_dict["effective_priority_tier"] = triage_meta.get("priority_override_tier") or case_dict["priority_tier"]
            case_dict["effective_priority_score"] = (
                triage_meta["priority_override_score"]
                if triage_meta.get("priority_override_score") is not None
                else case_dict["priority_score"]
            )
            case_dict["assigned_analyst_id"] = triage_meta.get("assigned_analyst_id")
            case_dict["age_hours"] = age_h
            case_dict["sla_breached"] = sla_breached
            case_dict["requires_reviewer_signoff"] = float(case_dict["total_exposure_amount"]) >= 25000.0

            return {
                "case": case_dict,
                "waterfall": waterfall,
                "alerts": alerts,
                "trigger_facts": facts,
                "customers": customers,
                "accounts": accounts,
                "account_ownerships": ownerships,
                "device_links": device_links,
                "account_state_events": account_events,
                "transfers": transfers,
                "transactions": ledger_rows[-120:],
                "total_ledger_txns": len(ledger_rows),
                "graph": {"nodes": nodes, "edges": edges},
                "analyst_actions": actions,
                "case_state_events": case_events,
                "triage_meta": triage_meta,
                "checklist": checklist,
                "watchlist_tags": watchlist_tags,
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Batch 6 (Functions 126-150): Quarantine Ops, Audit Ledger & Governance
    # ------------------------------------------------------------------
    def list_quarantine_exceptions_filtered(self, **filters: Any) -> dict[str, Any]:
        base = self.get_quarantine_exceptions()
        conn = self._conn()
        try:
            return list_quarantine_exceptions_filtered(conn, base, **filters)
        finally:
            conn.close()

    def get_quarantine_detail(self, exception_id: str) -> dict[str, Any] | None:
        base = self.get_quarantine_exceptions()
        conn = self._conn()
        try:
            return get_quarantine_detail(conn, base, exception_id)
        finally:
            conn.close()

    def review_quarantine_exception(self, **kwargs: Any) -> dict[str, Any]:
        base = self.get_quarantine_exceptions()
        conn = self._conn()
        try:
            return review_quarantine_exception(conn, base, **kwargs)
        finally:
            conn.close()

    def bulk_review_quarantine(self, **kwargs: Any) -> dict[str, Any]:
        base = self.get_quarantine_exceptions()
        conn = self._conn()
        try:
            return bulk_review_quarantine(conn, base, **kwargs)
        finally:
            conn.close()

    def run_live_integrity_validation(self) -> dict[str, Any]:
        base = self.get_quarantine_exceptions()
        conn = self._conn()
        try:
            return run_live_integrity_validation(conn, base)
        finally:
            conn.close()

    def export_quarantine_report(self, *, fmt: str = "csv", **filters: Any) -> tuple[bytes, str, str]:
        base = self.get_quarantine_exceptions()
        conn = self._conn()
        try:
            return export_quarantine_report(conn, base, fmt=fmt, **filters)
        finally:
            conn.close()

    def get_unified_audit_events(self, **filters: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_unified_audit_events(conn, **filters)
        finally:
            conn.close()

    def export_audit_events(self, *, fmt: str = "csv", **filters: Any) -> tuple[bytes, str, str]:
        conn = self._conn()
        try:
            return export_audit_events(conn, fmt=fmt, **filters)
        finally:
            conn.close()

    def get_analyst_leaderboard(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_analyst_leaderboard(conn)
        finally:
            conn.close()

    def list_admin_users(self) -> list[dict[str, Any]]:
        return list_admin_users(self.db_path)

    def update_admin_user(self, **kwargs: Any) -> dict[str, Any]:
        return update_admin_user(self.db_path, **kwargs)

    def list_watchlist_tags(self, **filters: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return list_watchlist_tags(conn, **filters)
        finally:
            conn.close()

    def list_saved_views(self, *, user_id: str, workspace: str = "ALL") -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_saved_views(conn, user_id=user_id, workspace=workspace)
        finally:
            conn.close()

    def create_saved_view(self, *, user_id: str, workspace: str, name: str, filters: dict[str, Any]) -> dict[str, Any]:
        conn = self._conn()
        try:
            return create_saved_view(conn, user_id=user_id, workspace=workspace, name=name, filters=filters)
        finally:
            conn.close()

    def delete_saved_view(self, *, user_id: str, view_id: str, is_admin: bool = False) -> bool:
        conn = self._conn()
        try:
            return delete_saved_view(conn, user_id=user_id, view_id=view_id, is_admin=is_admin)
        finally:
            conn.close()

    def get_sla_policies(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_sla_policies(conn)
        finally:
            conn.close()

    def update_sla_policies(self, *, actor_id: str, updates: list[dict[str, Any]]) -> dict[str, Any]:
        conn = self._conn()
        try:
            return update_sla_policies(conn, actor_id=actor_id, updates=updates)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Batch 7 (Functions 151-175): Evaluation Lab, Rings, SAR Registry & Search
    # ------------------------------------------------------------------
    def simulate_evaluation_cutoff(self, *, k_pct: float = 20.0) -> dict[str, Any]:
        conn = self._conn()
        try:
            return simulate_queue_cutoff(conn, self.gt_path, k_pct=k_pct)
        finally:
            conn.close()

    def get_rule_performance_attribution(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_rule_performance_attribution(conn, self.gt_path)
        finally:
            conn.close()

    def run_what_if_simulation(self, *, weight_overrides: dict[str, float], k_pct: float = 20.0) -> dict[str, Any]:
        conn = self._conn()
        try:
            return run_what_if_rule_simulation(conn, self.gt_path, weight_overrides=weight_overrides, k_pct=k_pct)
        finally:
            conn.close()

    def check_zero_leakage_live(self) -> dict[str, Any]:
        src_root = Path(__file__).resolve().parents[2]
        return check_live_zero_leakage(src_root)

    def verify_export_manifest_integrity(self) -> dict[str, Any]:
        return verify_export_manifest(self.export_dir)

    def export_evaluation_report(self, *, fmt: str = "json") -> tuple[bytes, str, str]:
        ev = self.get_evaluation()
        rp = self.get_rule_performance_attribution()
        return export_evaluation_report(ev, rp, fmt=fmt)

    def get_entity_network(self, entity_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            return get_entity_network(conn, entity_id)
        finally:
            conn.close()

    def detect_collusion_rings(self, *, min_accounts: int = 2, limit: int = 20) -> dict[str, Any]:
        conn = self._conn()
        try:
            return detect_collusion_rings(conn, min_accounts=min_accounts, limit=limit)
        finally:
            conn.close()

    def get_financial_network_overview(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_financial_network_overview(conn)
        finally:
            conn.close()

    def search_network_entities(self, query: str, *, entity_type: str = "ALL", limit: int = 15) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return search_network_entities(conn, query, entity_type=entity_type, limit=limit)
        finally:
            conn.close()

    def get_financial_network_graph(self, *, seed_id: str | None = None, depth: int = 2, max_nodes: int = 75) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_financial_network_graph(conn, seed_id=seed_id, depth=depth, max_nodes=max_nodes)
        finally:
            conn.close()

    def trace_money_flow_path(self, source_account_id: str, dest_account_id: str, *, max_depth: int = 4) -> dict[str, Any]:
        conn = self._conn()
        try:
            return trace_money_flow_path(conn, source_account_id, dest_account_id, max_depth=max_depth)
        finally:
            conn.close()

    def detect_circular_transfers(self, *, limit: int = 15) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return detect_circular_transfers(conn, limit=limit)
        finally:
            conn.close()

    def detect_suspicious_patterns(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return detect_suspicious_patterns(conn)
        finally:
            conn.close()

    def resolve_entities(self, *, limit: int = 30) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return resolve_entities(conn, limit=limit)
        finally:
            conn.close()

    def compute_network_risk_analysis(self, *, seed_id: str | None = None) -> dict[str, Any]:
        conn = self._conn()
        try:
            return compute_network_risk_analysis(conn, seed_id=seed_id)
        finally:
            conn.close()

    def list_sar_registry(self, *, status: str = "ALL", limit: int = 100) -> dict[str, Any]:
        conn = self._conn()
        try:
            return list_sar_registry(conn, status=status, limit=limit)
        finally:
            conn.close()

    def transition_sar_status(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return transition_sar_status(conn, **kwargs)
        finally:
            conn.close()

    def get_similar_cases(self, case_id: str, *, limit: int = 5) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            return get_similar_cases(conn, case_id, limit=limit)
        finally:
            conn.close()

    def global_search(self, *, query: str, limit_per_group: int = 5) -> dict[str, Any]:
        base = self.get_quarantine_exceptions()
        conn = self._conn()
        try:
            return global_cross_entity_search(conn, base, query=query, limit_per_group=limit_per_group)
        finally:
            conn.close()

    def get_executive_digest(self) -> dict[str, Any]:
        ov = self.get_overview()
        qf = self.list_quarantine_exceptions_filtered()
        rings = self.detect_collusion_rings(limit=15)
        sars = self.list_sar_registry()
        conn = self._conn()
        try:
            return get_executive_digest(conn, overview=ov, quarantine_filtered=qf, ring_summary=rings, sar_registry=sars)
        finally:
            conn.close()

    def export_executive_digest(self, *, fmt: str = "md") -> tuple[bytes, str, str]:
        return export_executive_digest(self.get_executive_digest(), fmt=fmt)

    def get_system_health(self) -> dict[str, Any]:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8")) if self.manifest_path.exists() else {}
        conn = self._conn()
        try:
            return get_system_health(
                conn,
                db_path=self.db_path,
                scale=str(manifest.get("scale", "unknown")),
                seed=manifest.get("seed"),
            )
        finally:
            conn.close()

    def export_case_packet(self, case_id: str, *, fmt: str = "json") -> tuple[bytes, str, str] | None:
        dos = self.get_case_dossier(case_id)
        if dos is None:
            return None
        if fmt == "md":
            c = dos["case"]
            lines = [
                f"# Investigation Dossier: {c['case_id']}",
                f"- **Status:** {c['status']} | **Priority:** {c['effective_priority_tier']} ({c['effective_priority_score']})",
                f"- **Exposure:** ${float(c['total_exposure_amount']):,.2f} across {c['alert_count']} alerts & {c['linked_account_count']} accounts",
                f"- **Assignee:** {c.get('assigned_analyst_id') or 'UNASSIGNED'} | **Reviewer Sign-Off Required:** {c['requires_reviewer_signoff']}",
                "",
                "## Linked Alerts",
            ]
            for a in dos["alerts"]:
                lines.append(f"- `{a['alert_id']}` [{a['rule_id']} • {a['severity']} • {a['risk_score']:.1f}]: {a['explanation_summary']}")
            lines.append("")
            lines.append("## Analyst Audit Trail")
            for act in dos["analyst_actions"]:
                lines.append(f"- {act['acted_at']} | {act['analyst_id']} ({act['analyst_role']}) | `{act['action_type']}`: {act['rationale']}")
            if dos["triage_meta"].get("sar_draft"):
                lines.append("")
                lines.append("## SAR Narrative Draft")
                lines.append(dos["triage_meta"]["sar_draft"])
            return "\n".join(lines).encode("utf-8"), "text/markdown; charset=utf-8", f"{case_id}_packet.md"
        return json.dumps(dos, indent=2).encode("utf-8"), "application/json; charset=utf-8", f"{case_id}_packet.json"

    # ------------------------------------------------------------------
    # Rules & Evaluation / Reproducibility Scorecard
    # ------------------------------------------------------------------
    def list_rules(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            rows = conn.execute(
                """
                SELECT r.*, COUNT(a.alert_id) AS hit_count,
                       ROUND(COALESCE(AVG(a.risk_score), 0), 2) AS avg_alert_score
                FROM risk_rules r
                LEFT JOIN alerts a ON a.rule_id = r.rule_id
                GROUP BY r.rule_id
                ORDER BY r.rule_id
                """
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_evaluation(self) -> dict[str, Any]:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8")) if self.manifest_path.exists() else {}
        gt_rows = json.loads(self.gt_path.read_text(encoding="utf-8")) if self.gt_path.exists() else []
        case_gt = {r["entity_id"]: r for r in gt_rows if r["entity_type"] == "CASE"}

        conn = self._conn()
        try:
            all_cases = [dict(r) for r in conn.execute("SELECT * FROM cases").fetchall()]
        finally:
            conn.close()

        ranked_prio = sorted(all_cases, key=lambda c: (-float(c["priority_score"]), -float(c["total_exposure_amount"]), c["case_id"]))
        ranked_fifo = sorted(all_cases, key=lambda c: (c["created_at"], c["case_id"]))

        total_tp = sum(1 for c in all_cases if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False))
        total_fp = sum(1 for c in all_cases if c["case_id"] in case_gt and not case_gt[c["case_id"]]["is_true_positive_risk"])

        def queue_metrics(ordered: list[dict[str, Any]], pct: float) -> dict[str, Any]:
            k = max(1, int(round(len(ordered) * pct)))
            top = ordered[:k]
            tp = sum(1 for c in top if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False))
            prec = round(tp / k, 4) if k else 0.0
            rec = round(tp / total_tp, 4) if total_tp else 0.0
            return {"k": k, "tp": tp, "precision": prec, "recall": rec}

        lift_curve = []
        for pct in (0.10, 0.20, 0.30, 0.50, 0.75, 1.00):
            p_m = queue_metrics(ranked_prio, pct)
            f_m = queue_metrics(ranked_fifo, pct)
            lift_curve.append({
                "queue_pct": int(pct * 100),
                "priority_recall": p_m["recall"],
                "priority_precision": p_m["precision"],
                "fifo_recall": f_m["recall"],
                "fifo_precision": f_m["precision"],
            })

        # Typology breakdown
        by_typ: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for c in all_cases:
            gt = case_gt.get(c["case_id"])
            t = gt["typology"] if gt else "ORPHAN_INJECTED"
            by_typ[t].append(c)

        typology_stats = []
        for t, grp in sorted(by_typ.items()):
            scores = [float(c["priority_score"]) for c in grp]
            top_half = sum(1 for c in grp if float(c["priority_score"]) >= 40.0)
            typology_stats.append({
                "typology": t,
                "case_count": len(grp),
                "avg_priority_score": round(sum(scores) / len(scores), 2),
                "min_score": round(min(scores), 2),
                "max_score": round(max(scores), 2),
                "above_medium_threshold": top_half,
                "is_risk_typology": bool(case_gt.get(grp[0]["case_id"], {}).get("is_true_positive_risk", False)),
            })

        quarantine = self.get_quarantine_exceptions()
        gt_edges = [r for r in gt_rows if r["typology"] == "NEGATIVE_EDGE_CASE"]
        expected_issues = {r["issue_type"] for r in gt_edges}
        caught_issues = set(quarantine["counts_by_issue_type"].keys())

        rels_prio = [1 if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False) else 0 for c in ranked_prio]
        rels_fifo = [1 if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False) else 0 for c in ranked_fifo]
        prio20 = queue_metrics(ranked_prio, 0.20)
        fifo20 = queue_metrics(ranked_fifo, 0.20)
        prio20["ndcg"] = _ndcg_at_k(rels_prio, prio20["k"])
        fifo20["ndcg"] = _ndcg_at_k(rels_fifo, fifo20["k"])
        perc_info = enrich_typology_percentiles(typology_stats, all_cases, case_gt)

        return {
            "total_cases": len(all_cases),
            "true_positive_cases": total_tp,
            "false_positive_cases": total_fp,
            "priority_top20": prio20,
            "fifo_top20": fifo20,
            "priority_top50_cases": {
                "tp": sum(1 for c in ranked_prio[:50] if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False)),
                "precision": round(
                    sum(1 for c in ranked_prio[:50] if case_gt.get(c["case_id"], {}).get("is_true_positive_risk", False))
                    / max(1, min(50, len(ranked_prio))),
                    4,
                ),
                "ndcg": _ndcg_at_k(rels_prio, min(50, len(ranked_prio))),
            },
            "lift_curve": lift_curve,
            "typology_stats": perc_info["typology_stats"],
            "score_separation": {
                "tp_mean_score": perc_info["tp_mean_score"],
                "fp_mean_score": perc_info["fp_mean_score"],
                "separation_gap": perc_info["separation_gap"],
            },
            "negative_edge_catch_rate": {
                "injected_count": len(gt_edges),
                "caught_count": quarantine["total_exceptions"],
                "expected_issue_types": sorted(expected_issues),
                "caught_issue_types": sorted(caught_issues),
                "all_types_caught": expected_issues.issubset(caught_issues),
            },
            "manifest": manifest,
        }

    # ------------------------------------------------------------------
    # Batch 1 (Functions 7-19): Interactive Filterable Dashboard & Export
    # ------------------------------------------------------------------
    def get_dashboard(
        self,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        period: str = "ALL",
        risk_level: str = "ALL",
        txn_type: str = "ALL",
        status: str = "ALL",
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            # Determine date bounds from period if explicit start_date not given
            eff_start = start_date
            eff_end = end_date
            if not eff_start and period in ("7D", "30D", "90D"):
                max_row = conn.execute("SELECT MAX(occurred_at) FROM transactions").fetchone()
                anchor_str = max_row[0] if max_row and max_row[0] else "2026-10-28T23:59:59Z"
                anchor_dt = datetime.fromisoformat(anchor_str.replace("Z", "+00:00")).astimezone(timezone.utc)
                days = {"7D": 7, "30D": 30, "90D": 90}[period]
                eff_start = (anchor_dt - timedelta(days=days)).strftime("%Y-%m-%d")

            # Build indexed alert score lookup per transaction via temp view / CTE
            txn_where = ["1=1"]
            txn_params: list[Any] = []
            if eff_start:
                txn_where.append("t.occurred_at >= ?")
                txn_params.append(f"{eff_start}T00:00:00Z" if len(eff_start) == 10 else eff_start)
            if eff_end:
                txn_where.append("t.occurred_at <= ?")
                txn_params.append(f"{eff_end}T23:59:59Z" if len(eff_end) == 10 else eff_end)
            if txn_type and txn_type != "ALL":
                txn_where.append("t.txn_type = ?")
                txn_params.append(txn_type)
            if status and status != "ALL":
                if status in ("POSTED", "REVERSED", "FAILED"):
                    txn_where.append("t.status = ?")
                    txn_params.append(status)
                else:
                    txn_where.append("t.account_id IN (SELECT primary_account_id FROM cases WHERE status = ?)")
                    txn_params.append(status)

            txn_where_sql = " AND ".join(txn_where)

            # Aggregate risk level per transaction cleanly
            risk_expr = """
                CASE
                    WHEN COALESCE(atf_agg.max_score, 0) >= 60 THEN 'HIGH'
                    WHEN COALESCE(atf_agg.max_score, 0) > 0 OR COALESCE(m.risk_tier, '') = 'HIGH' THEN 'MEDIUM'
                    ELSE 'LOW'
                END
            """

            risk_filter_sql = ""
            if risk_level and risk_level != "ALL":
                risk_filter_sql = f" AND ({risk_expr}) = ?"
                txn_params.append(risk_level)

            agg_cte = f"""
                WITH atf_agg AS (
                    SELECT f.transaction_id, MAX(a.risk_score) AS max_score, MIN(a.rule_id) AS top_rule_id
                    FROM alert_trigger_facts f
                    JOIN alerts a ON a.alert_id = f.alert_id
                    GROUP BY f.transaction_id
                ),
                filtered_txns AS (
                    SELECT t.*,
                           COALESCE(atf_agg.max_score, 0) AS txn_risk_score,
                           atf_agg.top_rule_id,
                           ({risk_expr}) AS risk_level
                    FROM transactions t
                    LEFT JOIN atf_agg ON atf_agg.transaction_id = t.transaction_id
                    LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
                    WHERE {txn_where_sql} {risk_filter_sql}
                )
            """

            # 1. Transaction Risk Counts & Volume
            risk_rows = conn.execute(
                agg_cte + "SELECT risk_level, COUNT(*) AS cnt, COALESCE(SUM(amount), 0) AS vol FROM filtered_txns GROUP BY risk_level",
                txn_params,
            ).fetchall()
            risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
            total_volume = 0.0
            total_filtered_txns = 0
            for rr in risk_rows:
                risk_counts[rr["risk_level"]] = rr["cnt"]
                total_volume += float(rr["vol"])
                total_filtered_txns += int(rr["cnt"])

            # 2. Time-series transaction volume & suspicious trends (grouped by week or day depending on span)
            series_rows = conn.execute(
                agg_cte
                + """
                SELECT SUBSTR(occurred_at, 1, 10) AS day,
                       COUNT(*) AS txn_count,
                       ROUND(COALESCE(SUM(amount), 0), 2) AS volume_usd,
                       SUM(CASE WHEN risk_level IN ('HIGH', 'MEDIUM') THEN 1 ELSE 0 END) AS suspicious_count
                FROM filtered_txns
                GROUP BY day
                ORDER BY day ASC
                """,
                txn_params,
            ).fetchall()

            # Downsample daily into crisp <= 36 buckets if > 40 days for ultra-clean charts
            raw_series = [dict(r) for r in series_rows]
            if len(raw_series) > 40:
                bucket_size = max(2, len(raw_series) // 30)
                volume_series = []
                for idx in range(0, len(raw_series), bucket_size):
                    chunk = raw_series[idx : idx + bucket_size]
                    volume_series.append({
                        "label": chunk[0]["day"][5:],
                        "start_day": chunk[0]["day"],
                        "end_day": chunk[-1]["day"],
                        "txn_count": sum(x["txn_count"] for x in chunk),
                        "volume_usd": round(sum(x["volume_usd"] for x in chunk), 2),
                        "suspicious_count": sum(x["suspicious_count"] for x in chunk),
                    })
            else:
                volume_series = [
                    {
                        "label": r["day"][5:],
                        "start_day": r["day"],
                        "end_day": r["day"],
                        "txn_count": r["txn_count"],
                        "volume_usd": r["volume_usd"],
                        "suspicious_count": r["suspicious_count"],
                    }
                    for r in raw_series
                ]

            # 3. Recent Suspicious Transactions
            recent_suspicious_txns = [
                dict(r)
                for r in conn.execute(
                    agg_cte
                    + """
                    SELECT ft.transaction_id, ft.account_id, a.primary_customer_id AS customer_id,
                           c.full_name AS customer_name, ft.txn_type, ft.direction, ft.amount,
                           ft.channel, ft.occurred_at, ft.txn_risk_score AS risk_score,
                           ft.risk_level, ft.top_rule_id AS rule_id
                    FROM filtered_txns ft
                    JOIN accounts a ON a.account_id = ft.account_id
                    JOIN customers c ON c.customer_id = a.primary_customer_id
                    WHERE ft.risk_level IN ('HIGH', 'MEDIUM')
                    ORDER BY ft.occurred_at DESC, ft.txn_risk_score DESC
                    LIMIT 12
                    """,
                    txn_params,
                ).fetchall()
            ]

            # 4. Entity & Case summary counts (respecting date/status filters where applicable)
            case_where = ["1=1"]
            case_params: list[Any] = []
            if eff_start:
                case_where.append("created_at >= ?")
                case_params.append(f"{eff_start}T00:00:00Z" if len(eff_start) == 10 else eff_start)
            if eff_end:
                case_where.append("created_at <= ?")
                case_params.append(f"{eff_end}T23:59:59Z" if len(eff_end) == 10 else eff_end)
            if status and status != "ALL" and status not in ("POSTED", "REVERSED", "FAILED"):
                case_where.append("status = ?")
                case_params.append(status)
            case_where_sql = " AND ".join(case_where)

            case_status_rows = conn.execute(
                f"SELECT status, COUNT(*) AS cnt FROM cases WHERE {case_where_sql} GROUP BY status",
                case_params,
            ).fetchall()
            cs_map = {r["status"]: r["cnt"] for r in case_status_rows}

            case_tier_rows = conn.execute(
                f"SELECT priority_tier, COUNT(*) AS cnt FROM cases WHERE {case_where_sql} GROUP BY priority_tier",
                case_params,
            ).fetchall()
            ct_map = {r["priority_tier"]: r["cnt"] for r in case_tier_rows}

            # 5. Rule-wise alert distribution
            alert_where = ["1=1"]
            alert_params: list[Any] = []
            if eff_start:
                alert_where.append("a.created_at >= ?")
                alert_params.append(f"{eff_start}T00:00:00Z" if len(eff_start) == 10 else eff_start)
            if eff_end:
                alert_where.append("a.created_at <= ?")
                alert_params.append(f"{eff_end}T23:59:59Z" if len(eff_end) == 10 else eff_end)
            alert_where_sql = " AND ".join(alert_where)

            rule_dist = [
                dict(r)
                for r in conn.execute(
                    f"""
                    SELECT r.rule_id, r.rule_name, r.category, r.severity,
                           COUNT(a.alert_id) AS alert_count,
                           ROUND(COALESCE(AVG(a.risk_score), 0), 1) AS avg_score
                    FROM risk_rules r
                    LEFT JOIN alerts a ON a.rule_id = r.rule_id AND {alert_where_sql}
                    GROUP BY r.rule_id
                    ORDER BY alert_count DESC, r.rule_id ASC
                    """,
                    alert_params,
                ).fetchall()
            ]

            # 6. Recent Alerts & Case Activities Feed
            recent_alerts = [
                dict(r)
                for r in conn.execute(
                    f"""
                    SELECT a.alert_id, a.rule_id, r.rule_name, a.account_id, a.customer_id,
                           a.severity, a.risk_score, a.trigger_total_amount, a.created_at, a.status,
                           'ALERT' AS feed_type
                    FROM alerts a
                    JOIN risk_rules r ON r.rule_id = a.rule_id
                    WHERE {alert_where_sql}
                    ORDER BY a.created_at DESC, a.alert_id DESC
                    LIMIT 8
                    """,
                    alert_params,
                ).fetchall()
            ]
            recent_case_events = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT cse.case_event_id AS id, cse.case_id, cse.prev_status, cse.new_status,
                           cse.effective_at AS occurred_at, aa.analyst_id, aa.action_type, aa.rationale,
                           'CASE_EVENT' AS feed_type
                    FROM case_state_events cse
                    LEFT JOIN analyst_actions aa ON aa.action_id = cse.analyst_action_id
                    ORDER BY cse.effective_at DESC, cse.case_event_id DESC
                    LIMIT 8
                    """
                ).fetchall()
            ]

            # 7. Top High-Risk Customers & Accounts
            top_customers = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT cu.customer_id, cu.full_name, cu.email, cu.kyc_tier, cu.risk_rating,
                           COUNT(DISTINCT c.case_id) AS case_count,
                           MAX(c.priority_score) AS max_priority_score,
                           ROUND(SUM(c.total_exposure_amount), 2) AS total_exposure
                    FROM customers cu
                    JOIN cases c ON c.primary_customer_id = cu.customer_id
                    GROUP BY cu.customer_id
                    ORDER BY max_priority_score DESC, total_exposure DESC
                    LIMIT 8
                    """
                ).fetchall()
            ]
            top_accounts = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT a.account_id, a.primary_customer_id AS customer_id, cu.full_name AS customer_name,
                           a.account_type, a.status, a.current_balance,
                           COUNT(DISTINCT al.alert_id) AS alert_count,
                           MAX(al.risk_score) AS max_risk_score,
                           ROUND(SUM(al.trigger_total_amount), 2) AS alert_exposure
                    FROM accounts a
                    JOIN customers cu ON cu.customer_id = a.primary_customer_id
                    JOIN alerts al ON al.account_id = a.account_id
                    GROUP BY a.account_id
                    ORDER BY max_risk_score DESC, alert_exposure DESC
                    LIMIT 8
                    """
                ).fetchall()
            ]

            summary = {
                "customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
                "accounts": conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0],
                "merchants": conn.execute("SELECT COUNT(*) FROM merchants").fetchone()[0],
                "devices": conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
                "transactions": total_filtered_txns,
                "total_volume_usd": round(total_volume, 2),
                "alerts": sum(r["alert_count"] for r in rule_dist),
                "cases": sum(cs_map.values()),
                "high_risk_txns": risk_counts["HIGH"],
                "medium_risk_txns": risk_counts["MEDIUM"],
                "low_risk_txns": risk_counts["LOW"],
                "open_cases": cs_map.get("OPEN", 0),
                "under_investigation_cases": cs_map.get("IN_REVIEW", 0),
                "escalated_cases": cs_map.get("ESCALATED", 0),
                "closed_cases": (
                    cs_map.get("SAR_FILED", 0)
                    + cs_map.get("CLOSED_CONFIRMED_FRAUD", 0)
                    + cs_map.get("CLOSED_FALSE_POSITIVE", 0)
                ),
            }

            return {
                "filters": {
                    "start_date": eff_start,
                    "end_date": eff_end,
                    "period": period,
                    "risk_level": risk_level,
                    "txn_type": txn_type,
                    "status": status,
                },
                "summary": summary,
                "case_tier_distribution": ct_map,
                "volume_series": volume_series,
                "rule_distribution": rule_dist,
                "recent_suspicious_txns": recent_suspicious_txns,
                "recent_alerts": recent_alerts,
                "recent_case_events": recent_case_events,
                "top_risk_customers": top_customers,
                "top_risk_accounts": top_accounts,
            }
        finally:
            conn.close()

    def export_dashboard_report(self, *, fmt: str = "csv", **filters: Any) -> tuple[bytes, str, str]:
        dash = self.get_dashboard(**filters)
        if fmt == "json":
            return json.dumps(dash, indent=2).encode("utf-8"), "application/json; charset=utf-8", "yottaflex_dashboard_report.json"

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["section", "metric_or_id", "detail", "value"])
        for k, v in dash["summary"].items():
            writer.writerow(["SUMMARY", k, "Dashboard KPI", v])
        for r in dash["rule_distribution"]:
            writer.writerow(["RULE_DISTRIBUTION", r["rule_id"], r["rule_name"], r["alert_count"]])
        for c in dash["top_risk_customers"]:
            writer.writerow(["TOP_RISK_CUSTOMER", c["customer_id"], f"{c['full_name']} ({c['kyc_tier']})", c["max_priority_score"]])
        for a in dash["top_risk_accounts"]:
            writer.writerow(["TOP_RISK_ACCOUNT", a["account_id"], f"{a['customer_name']} ({a['status']})", a["max_risk_score"]])
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "yottaflex_dashboard_report.csv"

    # ------------------------------------------------------------------
    # Batch 1 (Functions 20-25): Customer Directory & 360 Profile
    # ------------------------------------------------------------------
    def list_customers(
        self,
        *,
        search: str | None = None,
        kyc_tier: str = "ALL",
        risk_rating: str = "ALL",
        account_status: str = "ALL",
        multi_suspicious: bool = False,
        limit: int = 60,
        offset: int = 0,
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            where = ["1=1"]
            params: list[Any] = []
            if kyc_tier and kyc_tier != "ALL":
                where.append("cu.kyc_tier = ?")
                params.append(kyc_tier)
            if risk_rating and risk_rating != "ALL":
                where.append("cu.risk_rating = ?")
                params.append(risk_rating)
            if account_status and account_status != "ALL":
                if account_status == "SUSPENDED":
                    where.append(
                        "EXISTS (SELECT 1 FROM account_ownerships ao2 JOIN accounts a2 ON a2.account_id = ao2.account_id WHERE ao2.customer_id = cu.customer_id AND a2.status = 'FROZEN')"
                    )
                elif account_status == "INACTIVE":
                    where.append(
                        "EXISTS (SELECT 1 FROM account_ownerships ao2 JOIN accounts a2 ON a2.account_id = ao2.account_id WHERE ao2.customer_id = cu.customer_id AND a2.status IN ('DORMANT', 'CLOSED'))"
                    )
                else:
                    where.append(
                        "EXISTS (SELECT 1 FROM account_ownerships ao2 JOIN accounts a2 ON a2.account_id = ao2.account_id WHERE ao2.customer_id = cu.customer_id AND a2.status = ?)"
                    )
                    params.append(account_status)
            if multi_suspicious:
                where.append("COALESCE(susp_agg.suspicious_account_count, 0) >= 2")
            if search and search.strip():
                q = f"%{search.strip()}%"
                where.append(
                    """
                    (cu.customer_id LIKE ? OR cu.full_name LIKE ? OR cu.email LIKE ? OR cu.phone LIKE ? OR cu.home_country LIKE ?
                     OR EXISTS (
                         SELECT 1 FROM account_ownerships ao3
                         WHERE ao3.customer_id = cu.customer_id AND ao3.account_id LIKE ?
                     ))
                    """
                )
                params.extend([q, q, q, q, q, q])

            where_sql = " AND ".join(where)
            cte = """
                WITH acct_agg AS (
                    SELECT ao.customer_id,
                           COUNT(DISTINCT ao.account_id) AS account_count,
                           ROUND(COALESCE(SUM(a.current_balance), 0), 2) AS total_balance
                    FROM account_ownerships ao
                    JOIN accounts a ON a.account_id = ao.account_id
                    GROUP BY ao.customer_id
                ),
                susp_agg AS (
                    SELECT ao_s.customer_id, COUNT(DISTINCT al_s.account_id) AS suspicious_account_count
                    FROM account_ownerships ao_s
                    JOIN alerts al_s ON al_s.account_id = ao_s.account_id
                    GROUP BY ao_s.customer_id
                ),
                al_agg AS (
                    SELECT customer_id, COUNT(*) AS alert_count FROM alerts GROUP BY customer_id
                ),
                case_agg AS (
                    SELECT primary_customer_id AS customer_id, COUNT(*) AS case_count, COALESCE(MAX(priority_score), 0) AS max_case_score
                    FROM cases
                    GROUP BY primary_customer_id
                )
            """
            base_from = """
                FROM customers cu
                LEFT JOIN acct_agg ON acct_agg.customer_id = cu.customer_id
                LEFT JOIN susp_agg ON susp_agg.customer_id = cu.customer_id
                LEFT JOIN al_agg ON al_agg.customer_id = cu.customer_id
                LEFT JOIN case_agg ON case_agg.customer_id = cu.customer_id
            """
            total = conn.execute(f"{cte} SELECT COUNT(*) {base_from} WHERE {where_sql}", params).fetchone()[0]

            rows = conn.execute(
                f"""
                {cte}
                SELECT cu.*,
                       COALESCE(acct_agg.account_count, 0) AS account_count,
                       COALESCE(susp_agg.suspicious_account_count, 0) AS suspicious_account_count,
                       COALESCE(acct_agg.total_balance, 0) AS total_balance,
                       COALESCE(al_agg.alert_count, 0) AS alert_count,
                       COALESCE(case_agg.case_count, 0) AS case_count,
                       COALESCE(case_agg.max_case_score, 0) AS max_case_score
                {base_from}
                WHERE {where_sql}
                ORDER BY suspicious_account_count DESC, max_case_score DESC, alert_count DESC, cu.customer_id ASC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()

            return {"total": total, "items": [dict(r) for r in rows]}
        finally:
            conn.close()

    def get_customer_profile(self, customer_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            cust = conn.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,)).fetchone()
            if not cust:
                return None

            accounts = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT a.*, ao.ownership_role, ao.ownership_pct, ao.effective_from, ao.effective_to,
                           (SELECT MAX(t.occurred_at) FROM transactions t WHERE t.account_id = a.account_id) AS last_activity_at,
                           (SELECT COUNT(*) FROM alerts al WHERE al.account_id = a.account_id) AS alert_count
                    FROM account_ownerships ao
                    JOIN accounts a ON a.account_id = ao.account_id
                    WHERE ao.customer_id = ?
                    ORDER BY ao.ownership_role ASC, a.account_id ASC
                    """,
                    (customer_id,),
                ).fetchall()
            ]

            acct_ids = [a["account_id"] for a in accounts]
            alerts: list[dict[str, Any]] = []
            transactions: list[dict[str, Any]] = []
            devices: list[dict[str, Any]] = []
            acct_events: list[dict[str, Any]] = []

            if acct_ids:
                ph = ",".join(["?"] * len(acct_ids))
                alerts = [
                    dict(r)
                    for r in conn.execute(
                        f"""
                        SELECT al.*, r.rule_name, r.category
                        FROM alerts al
                        JOIN risk_rules r ON r.rule_id = al.rule_id
                        WHERE al.customer_id = ? OR al.account_id IN ({ph})
                        ORDER BY al.created_at DESC
                        LIMIT 60
                        """,
                        [customer_id] + acct_ids,
                    ).fetchall()
                ]
                transactions = [
                    dict(r)
                    for r in conn.execute(
                        f"""
                        SELECT t.*, m.merchant_name, m.category AS merchant_category, m.risk_tier AS merchant_risk_tier,
                               COALESCE((
                                   SELECT MAX(al.risk_score)
                                   FROM alert_trigger_facts atf JOIN alerts al ON al.alert_id = atf.alert_id
                                   WHERE atf.transaction_id = t.transaction_id
                               ), 0) AS txn_risk_score
                        FROM transactions t
                        LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
                        WHERE t.account_id IN ({ph})
                        ORDER BY t.occurred_at ASC, t.transaction_id ASC
                        LIMIT 300
                        """,
                        acct_ids,
                    ).fetchall()
                ]
                devices = [
                    dict(r)
                    for r in conn.execute(
                        f"""
                        SELECT DISTINCT d.*, adl.account_id, adl.first_seen_at, adl.last_seen_at, adl.is_trusted
                        FROM account_device_links adl
                        JOIN devices d ON d.device_id = adl.device_id
                        WHERE adl.account_id IN ({ph})
                        ORDER BY adl.first_seen_at DESC
                        """,
                        acct_ids,
                    ).fetchall()
                ]
                acct_events = [
                    dict(r)
                    for r in conn.execute(
                        f"SELECT * FROM account_state_events WHERE account_id IN ({ph}) ORDER BY effective_at ASC",
                        acct_ids,
                    ).fetchall()
                ]

            cases = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM cases WHERE primary_customer_id = ? ORDER BY priority_score DESC, created_at DESC",
                    (customer_id,),
                ).fetchall()
            ]

            # Function 30: Transparent customer risk score & contributing factors
            suspicious_acct_ids = {al["account_id"] for al in alerts}
            suspicious_account_count = len(suspicious_acct_ids)
            max_case_score = max((float(c["priority_score"]) for c in cases), default=0.0)
            max_alert_score = max((float(a["risk_score"]) for a in alerts), default=0.0)
            untrusted_devs = sum(1 for d in devices if d["is_trusted"] == 0 or d["is_emulator"] == 1)
            dormant_reactivations = sum(
                1 for ev in acct_events if ev["prev_status"] == "DORMANT" and ev["new_status"] == "ACTIVE"
            )

            kyc_pts = {"LOW": 14.0, "STANDARD": 7.0, "ENHANCED": 2.0}.get(cust["kyc_tier"], 7.0)
            alert_pts = min(38.0, round(max_alert_score * 0.42 + len(alerts) * 2.5, 2))
            case_pts = min(22.0, round(max_case_score * 0.25, 2))
            multi_acct_pts = 12.0 if suspicious_account_count >= 2 else (4.0 if suspicious_account_count == 1 and len(accounts) >= 2 else 0.0)
            dev_pts = min(10.0, untrusted_devs * 5.0)
            dorm_pts = min(8.0, dormant_reactivations * 8.0)

            customer_risk_score = round(min(100.0, kyc_pts + alert_pts + case_pts + multi_acct_pts + dev_pts + dorm_pts), 2)
            risk_factors = [
                {"factor": "KYC & Onboarding Profile", "points": kyc_pts, "detail": f"KYC Tier: {cust['kyc_tier']} (Onboarding rating: {cust['risk_rating']})"},
                {"factor": "Alert Triggers & Severity", "points": alert_pts, "detail": f"{len(alerts)} alert(s), max alert score {max_alert_score:.1f}"},
                {"factor": "Linked Investigation Cases", "points": case_pts, "detail": f"{len(cases)} case(s), peak case priority {max_case_score:.1f}"},
                {"factor": "Multi-Account Spread", "points": multi_acct_pts, "detail": f"{suspicious_account_count} suspicious account(s) across {len(accounts)} owned"},
                {"factor": "Untrusted / Emulator Devices", "points": dev_pts, "detail": f"{untrusted_devs} untrusted or emulator device link(s)"},
                {"factor": "Dormant Account Reactivation", "points": dorm_pts, "detail": f"{dormant_reactivations} dormancy reactivation event(s)"},
            ]

            # Function 31: Chronological risk level changes over time
            def _lvl(sc: float) -> str:
                return "HIGH" if sc >= 60 else ("MEDIUM" if sc >= 30 else "LOW")

            base_sc = {"LOW": 12.0, "MEDIUM": 35.0, "HIGH": 65.0}.get(cust["risk_rating"], 15.0)
            risk_timeline: list[dict[str, Any]] = [
                {
                    "timestamp": cust["created_at"],
                    "event": "Customer Onboarded",
                    "risk_score": base_sc,
                    "risk_level": cust["risk_rating"],
                    "detail": f"Initial onboarding rating ({cust['segment']} / {cust['kyc_tier']} KYC)",
                }
            ]
            for ev in acct_events:
                if ev["prev_status"] == "DORMANT" and ev["new_status"] == "ACTIVE":
                    base_sc = min(100.0, base_sc + 18.0)
                    risk_timeline.append({
                        "timestamp": ev["effective_at"],
                        "event": f"Dormant Reactivation ({ev['account_id']})",
                        "risk_score": round(base_sc, 1),
                        "risk_level": _lvl(base_sc),
                        "detail": "Account transitioned DORMANT -> ACTIVE",
                    })
            for al in sorted(alerts, key=lambda x: x["created_at"]):
                base_sc = min(100.0, max(base_sc, float(al["risk_score"])))
                risk_timeline.append({
                    "timestamp": al["created_at"],
                    "event": f"Alert {al['alert_id']} ({al['rule_id']})",
                    "risk_score": round(base_sc, 1),
                    "risk_level": _lvl(base_sc),
                    "detail": al["explanation_summary"],
                })
            for ca in sorted(cases, key=lambda x: x["updated_at"]):
                if ca["status"] == "CLOSED_FALSE_POSITIVE":
                    base_sc = max(10.0, round(base_sc * 0.45, 1))
                    risk_timeline.append({
                        "timestamp": ca["updated_at"],
                        "event": f"Case {ca['case_id']} Closed (False Positive)",
                        "risk_score": base_sc,
                        "risk_level": _lvl(base_sc),
                        "detail": "Risk mitigated after analyst disposition",
                    })
                elif ca["status"] in ("ESCALATED", "SAR_FILED", "CLOSED_CONFIRMED_FRAUD"):
                    base_sc = min(100.0, max(base_sc, float(ca["priority_score"])))
                    risk_timeline.append({
                        "timestamp": ca["updated_at"],
                        "event": f"Case {ca['case_id']} -> {ca['status']}",
                        "risk_score": round(base_sc, 1),
                        "risk_level": _lvl(base_sc),
                        "detail": "Elevated by analyst/compliance disposition",
                    })
            risk_timeline.sort(key=lambda x: x["timestamp"])

            acct_ids_for_tags = [a["account_id"] for a in accounts]
            if acct_ids_for_tags:
                ph_tags = ",".join(["?"] * len(acct_ids_for_tags))
                cust_tags = [
                    dict(r)
                    for r in conn.execute(
                        f"""
                        SELECT * FROM entity_watchlist_tags
                        WHERE (entity_type = 'CUSTOMER' AND entity_id = ?)
                           OR (entity_type = 'ACCOUNT' AND entity_id IN ({ph_tags}))
                        ORDER BY created_at DESC
                        """,
                        [customer_id] + acct_ids_for_tags,
                    ).fetchall()
                ]
            else:
                cust_tags = [
                    dict(r)
                    for r in conn.execute(
                        "SELECT * FROM entity_watchlist_tags WHERE entity_type = 'CUSTOMER' AND entity_id = ? ORDER BY created_at DESC",
                        (customer_id,),
                    ).fetchall()
                ]

            return {
                "customer": dict(cust),
                "kyc_summary": {
                    "kyc_tier": cust["kyc_tier"],
                    "kyc_verified_at": cust["kyc_verified_at"],
                    "declared_annual_income": cust["declared_annual_income"],
                    "risk_rating": cust["risk_rating"],
                    "status": cust["status"],
                },
                "customer_risk_score": customer_risk_score,
                "customer_risk_level": _lvl(customer_risk_score),
                "suspicious_account_count": suspicious_account_count,
                "has_multiple_suspicious_accounts": suspicious_account_count >= 2 or (len(accounts) >= 2 and len(alerts) > 0),
                "risk_factors": risk_factors,
                "risk_level_timeline": risk_timeline,
                "accounts": accounts,
                "transactions": transactions,
                "alerts": alerts,
                "cases": cases,
                "devices": devices,
                "watchlist_tags": cust_tags,
            }
        finally:
            conn.close()

    def export_customer_summary(self, customer_id: str, *, fmt: str = "csv") -> tuple[bytes, str, str] | None:
        prof = self.get_customer_profile(customer_id)
        if prof is None:
            return None
        if fmt == "json":
            return (
                json.dumps(prof, indent=2).encode("utf-8"),
                "application/json; charset=utf-8",
                f"{customer_id}_investigation_summary.json",
            )
        buf = io.StringIO()
        w = csv.writer(buf)
        c = prof["customer"]
        w.writerow(["section", "id", "attribute", "value"])
        for field in ("customer_id", "full_name", "email", "phone", "segment", "kyc_tier", "kyc_verified_at", "declared_annual_income", "home_country", "risk_rating", "status"):
            w.writerow(["CUSTOMER_PROFILE", c["customer_id"], field, c[field]])
        w.writerow(["RISK_SUMMARY", c["customer_id"], "customer_risk_score", prof["customer_risk_score"]])
        w.writerow(["RISK_SUMMARY", c["customer_id"], "suspicious_account_count", prof["suspicious_account_count"]])
        for a in prof["accounts"]:
            w.writerow(["ACCOUNT", a["account_id"], f"{a['account_type']} ({a['status']})", a["current_balance"]])
        for al in prof["alerts"]:
            w.writerow(["ALERT", al["alert_id"], f"{al['rule_id']} ({al['severity']})", al["risk_score"]])
        for ca in prof["cases"]:
            w.writerow(["CASE", ca["case_id"], f"{ca['status']} ({ca['priority_tier']})", ca["priority_score"]])
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", f"{customer_id}_investigation_summary.csv"

    # ------------------------------------------------------------------
    # Batch 2 (Functions 34-47): Account Directory & Account 360 Detail
    # ------------------------------------------------------------------
    def list_accounts(
        self,
        *,
        search: str | None = None,
        status: str = "ALL",
        dormant_reactivated: bool = False,
        limit: int = 60,
        offset: int = 0,
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            where = ["1=1"]
            params: list[Any] = []
            if status and status != "ALL":
                if status == "SUSPENDED":
                    where.append("a.status = 'FROZEN'")
                elif status == "INACTIVE":
                    where.append(
                        """
                        (a.status IN ('DORMANT', 'CLOSED') OR NOT EXISTS (
                            SELECT 1 FROM transactions ti WHERE ti.account_id = a.account_id AND ti.occurred_at >= '2026-09-01T00:00:00Z'
                        ))
                        """
                    )
                else:
                    where.append("a.status = ?")
                    params.append(status)

            if dormant_reactivated:
                where.append(
                    """
                    EXISTS (
                        SELECT 1 FROM account_state_events ase
                        WHERE ase.account_id = a.account_id AND ase.prev_status = 'DORMANT' AND ase.new_status = 'ACTIVE'
                    )
                    """
                )

            if search and search.strip():
                q = f"%{search.strip()}%"
                where.append(
                    """
                    (a.account_id LIKE ? OR a.primary_customer_id LIKE ? OR cu.full_name LIKE ?
                     OR EXISTS (
                         SELECT 1 FROM account_ownerships ao2 WHERE ao2.account_id = a.account_id AND ao2.customer_id LIKE ?
                     ))
                    """
                )
                params.extend([q, q, q, q])

            where_sql = " AND ".join(where)
            total = conn.execute(
                f"SELECT COUNT(*) FROM accounts a JOIN customers cu ON cu.customer_id = a.primary_customer_id WHERE {where_sql}",
                params,
            ).fetchone()[0]

            rows = conn.execute(
                f"""
                SELECT a.*, cu.full_name AS customer_name, cu.kyc_tier,
                       (SELECT MAX(t.occurred_at) FROM transactions t WHERE t.account_id = a.account_id) AS last_activity_at,
                       (SELECT COUNT(*) FROM transactions t WHERE t.account_id = a.account_id) AS txn_count,
                       (SELECT COUNT(*) FROM alerts al WHERE al.account_id = a.account_id) AS alert_count,
                       (SELECT COALESCE(MAX(al.risk_score), 0) FROM alerts al WHERE al.account_id = a.account_id) AS account_risk_score,
                       EXISTS (
                           SELECT 1 FROM account_state_events ase
                           WHERE ase.account_id = a.account_id AND ase.prev_status = 'DORMANT' AND ase.new_status = 'ACTIVE'
                       ) AS is_dormant_reactivated
                FROM accounts a
                JOIN customers cu ON cu.customer_id = a.primary_customer_id
                WHERE {where_sql}
                ORDER BY account_risk_score DESC, alert_count DESC, a.account_id ASC
                LIMIT ? OFFSET ?
                """,
                params + [limit, offset],
            ).fetchall()

            return {"total": total, "items": [dict(r) for r in rows]}
        finally:
            conn.close()

    def get_account_detail(self, account_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            acct = conn.execute("SELECT * FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
            if not acct:
                return None

            holders = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ao.*, c.full_name, c.email, c.phone, c.kyc_tier, c.segment, c.risk_rating, c.home_country
                    FROM account_ownerships ao
                    JOIN customers c ON c.customer_id = ao.customer_id
                    WHERE ao.account_id = ?
                    ORDER BY ao.ownership_role ASC
                    """,
                    (account_id,),
                ).fetchall()
            ]

            transactions = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT t.*, m.merchant_name, m.category AS merchant_category,
                           COALESCE((
                               SELECT MAX(al.risk_score)
                               FROM alert_trigger_facts atf JOIN alerts al ON al.alert_id = atf.alert_id
                               WHERE atf.transaction_id = t.transaction_id
                           ), 0) AS txn_risk_score
                    FROM transactions t
                    LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
                    WHERE t.account_id = ?
                    ORDER BY t.occurred_at ASC, t.transaction_id ASC
                    """,
                    (account_id,),
                ).fetchall()
            ]
            last_activity_at = transactions[-1]["occurred_at"] if transactions else None

            transfers = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT tr.*,
                           CASE WHEN tr.source_account_id = ? THEN 'OUTGOING' ELSE 'INCOMING' END AS transfer_direction,
                           CASE WHEN tr.source_account_id = ? THEN tr.dest_account_id ELSE tr.source_account_id END AS counterparty_account_id
                    FROM transfer_links tr
                    WHERE tr.source_account_id = ? OR tr.dest_account_id = ?
                    ORDER BY tr.initiated_at DESC
                    """,
                    (account_id, account_id, account_id, account_id),
                ).fetchall()
            ]

            # Accounts linked through common customers or transfer relationships
            holder_cids = [h["customer_id"] for h in holders]
            linked_accounts: list[dict[str, Any]] = []
            seen_linked: set[str] = {account_id}
            if holder_cids:
                ph_c = ",".join(["?"] * len(holder_cids))
                for r in conn.execute(
                    f"""
                    SELECT DISTINCT a.*, c.full_name AS owner_name, 'COMMON_CUSTOMER' AS link_relation
                    FROM account_ownerships ao
                    JOIN accounts a ON a.account_id = ao.account_id
                    JOIN customers c ON c.customer_id = a.primary_customer_id
                    WHERE ao.customer_id IN ({ph_c}) AND a.account_id != ?
                    """,
                    holder_cids + [account_id],
                ).fetchall():
                    d = dict(r)
                    seen_linked.add(d["account_id"])
                    linked_accounts.append(d)

            transfer_cp_ids = sorted({tr["counterparty_account_id"] for tr in transfers if tr["counterparty_account_id"] not in seen_linked})
            if transfer_cp_ids:
                ph_t = ",".join(["?"] * len(transfer_cp_ids))
                for r in conn.execute(
                    f"""
                    SELECT a.*, c.full_name AS owner_name, 'TRANSFER_RELATIONSHIP' AS link_relation
                    FROM accounts a
                    JOIN customers c ON c.customer_id = a.primary_customer_id
                    WHERE a.account_id IN ({ph_t})
                    """,
                    transfer_cp_ids,
                ).fetchall():
                    linked_accounts.append(dict(r))

            alerts = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT al.*, r.rule_name, r.category
                    FROM alerts al
                    JOIN risk_rules r ON r.rule_id = al.rule_id
                    WHERE al.account_id = ?
                    ORDER BY al.created_at DESC
                    """,
                    (account_id,),
                ).fetchall()
            ]

            lifecycle_events = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM account_state_events WHERE account_id = ? ORDER BY effective_at ASC, event_id ASC",
                    (account_id,),
                ).fetchall()
            ]
            is_dormant_reactivated = any(
                ev["prev_status"] == "DORMANT" and ev["new_status"] == "ACTIVE" for ev in lifecycle_events
            )

            max_al = max((float(a["risk_score"]) for a in alerts), default=0.0)
            acct_risk_score = round(min(100.0, max_al + (8.0 if is_dormant_reactivated else 0.0) + max(0, len(alerts) - 1) * 4.5), 2)

            return {
                "account": dict(acct),
                "last_activity_at": last_activity_at,
                "account_risk_score": acct_risk_score,
                "is_dormant_reactivated": is_dormant_reactivated,
                "holders": holders,
                "transactions": transactions[-250:],
                "total_transactions": len(transactions),
                "transfers": transfers,
                "linked_accounts": linked_accounts,
                "alerts": alerts,
                "lifecycle_events": lifecycle_events,
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Batch 2 & 3 (Functions 48-70): Transaction Monitoring, 360 Detail, Pattern Detection & Export
    # ------------------------------------------------------------------
    def _build_transactions_query(
        self,
        *,
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        txn_type: str = "ALL",
        risk_level: str = "ALL",
        status: str = "ALL",
        pattern: str = "ALL",
        sort_by: str = "occurred_at",
        sort_dir: str = "desc",
    ) -> tuple[str, str, str, str, str, list[Any]]:
        where = ["1=1"]
        params: list[Any] = []
        if start_date:
            where.append("t.occurred_at >= ?")
            params.append(f"{start_date}T00:00:00Z" if len(start_date) == 10 else start_date)
        if end_date:
            where.append("t.occurred_at <= ?")
            params.append(f"{end_date}T23:59:59Z" if len(end_date) == 10 else end_date)
        if min_amount is not None:
            where.append("t.amount >= ?")
            params.append(min_amount)
        if max_amount is not None:
            where.append("t.amount <= ?")
            params.append(max_amount)
        if txn_type and txn_type != "ALL":
            where.append("t.txn_type = ?")
            params.append(txn_type)
        if status and status != "ALL":
            where.append("t.status = ?")
            params.append(status)
        if search and search.strip():
            q = f"%{search.strip()}%"
            where.append(
                """
                (t.transaction_id LIKE ? OR t.account_id LIKE ? OR a.primary_customer_id LIKE ?
                 OR COALESCE(t.merchant_id, '') LIKE ? OR cu.full_name LIKE ? OR COALESCE(m.merchant_name, '') LIKE ?)
                """
            )
            params.extend([q, q, q, q, q, q])

        risk_expr = """
            CASE
                WHEN COALESCE(atf_agg.max_score, 0) >= 60 THEN 'HIGH'
                WHEN COALESCE(atf_agg.max_score, 0) > 0 OR COALESCE(m.risk_tier, '') = 'HIGH' THEN 'MEDIUM'
                ELSE 'LOW'
            END
        """
        if risk_level and risk_level != "ALL":
            where.append(f"({risk_expr}) = ?")
            params.append(risk_level)

        ctes = [
            """
            atf_agg AS (
                SELECT f.transaction_id,
                       MAX(al.risk_score) AS max_score,
                       MIN(al.rule_id) AS top_rule_id,
                       GROUP_CONCAT(DISTINCT al.rule_id) AS triggered_rule_ids,
                       MAX(CASE WHEN al.rule_id IN ('RULE-001', 'RULE-006') THEN 1 ELSE 0 END) AS has_vel_rule,
                       MAX(CASE WHEN al.rule_id = 'RULE-002' THEN 1 ELSE 0 END) AS has_dev_rule,
                       MAX(CASE WHEN al.rule_id = 'RULE-004' THEN 1 ELSE 0 END) AS has_dorm_rule
                FROM alert_trigger_facts f
                JOIN alerts al ON al.alert_id = f.alert_id
                GROUP BY f.transaction_id
            )
            """
        ]
        extra_joins = ""

        if pattern == "LARGE_AMOUNT":
            where.append("(t.amount >= 2500 OR (cu.declared_annual_income > 0 AND t.amount >= (cu.declared_annual_income / 12.0) * 0.5))")
        elif pattern == "RAPID_SUCCESSIVE":
            ctes.append(
                """
                rapid_txn_ids AS (
                    SELECT transaction_id FROM (
                        SELECT transaction_id, occurred_at,
                               LAG(occurred_at) OVER (PARTITION BY account_id ORDER BY occurred_at, transaction_id) AS prev_ts,
                               LEAD(occurred_at) OVER (PARTITION BY account_id ORDER BY occurred_at, transaction_id) AS next_ts
                        FROM transactions
                    )
                    WHERE (prev_ts IS NOT NULL AND (julianday(occurred_at) - julianday(prev_ts)) * 1440.0 <= 60.0)
                       OR (next_ts IS NOT NULL AND (julianday(next_ts) - julianday(occurred_at)) * 1440.0 <= 60.0)
                    UNION
                    SELECT f.transaction_id FROM alert_trigger_facts f
                    JOIN alerts al ON al.alert_id = f.alert_id
                    WHERE al.rule_id IN ('RULE-001', 'RULE-006')
                )
                """
            )
            extra_joins += " JOIN rapid_txn_ids rti ON rti.transaction_id = t.transaction_id"
        elif pattern == "NEW_DEVICE":
            ctes.append(
                """
                adl_agg AS (
                    SELECT account_id, device_id, MIN(first_seen_at) AS first_seen_at
                    FROM account_device_links
                    GROUP BY account_id, device_id
                )
                """
            )
            extra_joins += " LEFT JOIN adl_agg ON adl_agg.account_id = t.account_id AND adl_agg.device_id = t.device_id"
            where.append(
                """
                (COALESCE(atf_agg.has_dev_rule, 0) = 1 OR (
                    t.device_id IS NOT NULL AND adl_agg.first_seen_at IS NOT NULL
                    AND (julianday(t.occurred_at) - julianday(adl_agg.first_seen_at)) BETWEEN 0.0 AND 1.0
                ))
                """
            )
        elif pattern == "DORMANT_ACCOUNT":
            ctes.append(
                """
                dormant_accts AS (
                    SELECT DISTINCT account_id FROM account_state_events
                    WHERE prev_status = 'DORMANT' AND new_status = 'ACTIVE'
                )
                """
            )
            extra_joins += " LEFT JOIN dormant_accts da ON da.account_id = t.account_id"
            where.append("(a.status = 'DORMANT' OR da.account_id IS NOT NULL OR COALESCE(atf_agg.has_dorm_rule, 0) = 1)")
        elif pattern == "LINKED_PATTERN":
            ctes.append(
                """
                flagged_accts AS (SELECT DISTINCT account_id FROM alerts),
                linked_txn_ids AS (
                    SELECT f.transaction_id FROM alert_trigger_facts f
                    JOIN alerts al ON al.alert_id = f.alert_id
                    WHERE al.rule_id IN ('RULE-003', 'RULE-007')
                    UNION
                    SELECT trl.debit_txn_id FROM transfer_links trl
                    WHERE trl.source_account_id IN (SELECT account_id FROM flagged_accts)
                       OR trl.dest_account_id IN (SELECT account_id FROM flagged_accts)
                    UNION
                    SELECT trl.credit_txn_id FROM transfer_links trl
                    WHERE trl.credit_txn_id IS NOT NULL
                      AND (trl.source_account_id IN (SELECT account_id FROM flagged_accts)
                           OR trl.dest_account_id IN (SELECT account_id FROM flagged_accts))
                )
                """
            )
            extra_joins += " JOIN linked_txn_ids lti ON lti.transaction_id = t.transaction_id"
        elif pattern == "VALIDATION_EXCEPTION":
            ctes.append(
                """
                unrec_trls AS (
                    SELECT tr_e.debit_txn_id, tr_e.credit_txn_id
                    FROM transfer_links tr_e
                    LEFT JOIN transactions dt_e ON dt_e.transaction_id = tr_e.debit_txn_id
                    LEFT JOIN transactions ct_e ON ct_e.transaction_id = tr_e.credit_txn_id
                    WHERE tr_e.credit_txn_id IS NULL
                       OR ABS(COALESCE(dt_e.amount, 0) - COALESCE(ct_e.amount, 0)) > 0.001
                       OR tr_e.status != 'SETTLED'
                ),
                exc_txn_ids AS (
                    SELECT t_c.transaction_id FROM transactions t_c
                    JOIN accounts a_c ON a_c.account_id = t_c.account_id
                    WHERE a_c.status = 'CLOSED' AND a_c.closed_at IS NOT NULL AND t_c.occurred_at > a_c.closed_at
                    UNION
                    SELECT t_n.transaction_id FROM transactions t_n
                    JOIN accounts a_n ON a_n.account_id = t_n.account_id
                    WHERE a_n.overdraft_allowed = 0 AND t_n.balance_after < 0
                    UNION
                    SELECT debit_txn_id FROM unrec_trls WHERE debit_txn_id IS NOT NULL
                    UNION
                    SELECT credit_txn_id FROM unrec_trls WHERE credit_txn_id IS NOT NULL
                )
                """
            )
            extra_joins += " JOIN exc_txn_ids eti ON eti.transaction_id = t.transaction_id"

        sort_col_map = {
            "occurred_at": "t.occurred_at",
            "timestamp": "t.occurred_at",
            "amount": "t.amount",
            "risk_score": "risk_score",
        }
        order_col = sort_col_map.get(sort_by, "t.occurred_at")
        order_dir = "ASC" if str(sort_dir).lower() == "asc" else "DESC"

        cte = "WITH " + ",\n".join(ctes)
        base_from = f"""
            FROM transactions t
            JOIN accounts a ON a.account_id = t.account_id
            JOIN customers cu ON cu.customer_id = a.primary_customer_id
            LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
            LEFT JOIN atf_agg ON atf_agg.transaction_id = t.transaction_id
            {extra_joins}
        """
        select_cols = f"""
            t.*, a.primary_customer_id AS customer_id, cu.full_name AS customer_name,
            cu.declared_annual_income AS _annual_income, a.status AS _acct_status, a.closed_at AS _closed_at,
            a.overdraft_allowed AS _overdraft_allowed,
            m.merchant_name, m.category AS merchant_category,
            COALESCE(atf_agg.max_score, 0) AS risk_score,
            atf_agg.top_rule_id,
            atf_agg.triggered_rule_ids,
            ({risk_expr}) AS risk_level
        """
        return cte, base_from, select_cols, " AND ".join(where), f"{order_col} {order_dir}, t.transaction_id DESC", params

    def _enrich_txn_rows(self, conn: sqlite3.Connection, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        """Attach triggered_rules, pattern_flags, and validation exception status cleanly to the paged/exported rows."""
        if not rows:
            return []

        items = [dict(r) for r in rows]
        dormant_accts = {
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT account_id FROM account_state_events WHERE prev_status = 'DORMANT' AND new_status = 'ACTIVE'"
            ).fetchall()
        }
        flagged_accts = {r[0] for r in conn.execute("SELECT DISTINCT account_id FROM alerts").fetchall()}
        unrec_rows = conn.execute(
            """
            SELECT tr_e.debit_txn_id, tr_e.credit_txn_id
            FROM transfer_links tr_e
            LEFT JOIN transactions dt_e ON dt_e.transaction_id = tr_e.debit_txn_id
            LEFT JOIN transactions ct_e ON ct_e.transaction_id = tr_e.credit_txn_id
            WHERE tr_e.credit_txn_id IS NULL
               OR ABS(COALESCE(dt_e.amount, 0) - COALESCE(ct_e.amount, 0)) > 0.001
               OR tr_e.status != 'SETTLED'
            """
        ).fetchall()
        unrec_txn_ids: set[str] = set()
        for ur in unrec_rows:
            if ur[0]:
                unrec_txn_ids.add(ur[0])
            if ur[1]:
                unrec_txn_ids.add(ur[1])

        adl_first: dict[tuple[str, str], str] = {}
        for r in conn.execute(
            "SELECT account_id, device_id, MIN(first_seen_at) AS first_seen_at FROM account_device_links GROUP BY account_id, device_id"
        ).fetchall():
            adl_first[(r[0], r[1])] = r[2]

        txn_ids = [d["transaction_id"] for d in items]
        linked_set: set[str] = set()
        # Batch transfer-link check for returned transaction IDs using indexes
        for i in range(0, len(txn_ids), 400):
            chunk = txn_ids[i : i + 400]
            ph = ",".join(["?"] * len(chunk))
            for tr in conn.execute(
                f"""
                SELECT debit_txn_id, credit_txn_id, source_account_id, dest_account_id
                FROM transfer_links
                WHERE debit_txn_id IN ({ph}) OR credit_txn_id IN ({ph})
                """,
                chunk + chunk,
            ).fetchall():
                if tr[2] in flagged_accts or tr[3] in flagged_accts:
                    if tr[0]:
                        linked_set.add(tr[0])
                    if tr[1]:
                        linked_set.add(tr[1])

        for d in items:
            tid = d["transaction_id"]
            aid = d["account_id"]
            did = d.get("device_id")
            occ = d["occurred_at"]
            amt = float(d["amount"])
            annual_inc = float(d.pop("_annual_income", 0) or 0)
            acct_status = d.pop("_acct_status", "ACTIVE")
            closed_at = d.pop("_closed_at", None)
            overdraft_allowed = d.pop("_overdraft_allowed", 1)
            raw_rules = d.pop("triggered_rule_ids", None)
            rules = [r for r in str(raw_rules).split(",") if r] if raw_rules else []

            flags: list[str] = []
            if amt >= 2500.0 or (annual_inc > 0 and amt >= (annual_inc / 12.0) * 0.5):
                flags.append("LARGE_AMOUNT")

            has_vel_rule = any(r in ("RULE-001", "RULE-006") for r in rules)
            if has_vel_rule:
                flags.append("RAPID_SUCCESSIVE")
            elif len(items) <= 200:
                # Indexed 60-min neighbor lookup only on page-sized batches
                has_near = conn.execute(
                    """
                    SELECT 1 FROM transactions t2
                    WHERE t2.account_id = ? AND t2.transaction_id != ?
                      AND t2.occurred_at BETWEEN strftime('%Y-%m-%dT%H:%M:%SZ', ?, '-60 minutes')
                                             AND strftime('%Y-%m-%dT%H:%M:%SZ', ?, '+60 minutes')
                    LIMIT 1
                    """,
                    (aid, tid, occ, occ),
                ).fetchone()
                if has_near:
                    flags.append("RAPID_SUCCESSIVE")

            is_new_dev = "RULE-002" in rules
            if not is_new_dev and did and (aid, did) in adl_first:
                occ_dt = datetime.fromisoformat(occ.replace("Z", "+00:00"))
                fs_dt = datetime.fromisoformat(adl_first[(aid, did)].replace("Z", "+00:00"))
                if 0.0 <= (occ_dt - fs_dt).total_seconds() <= 86400.0:
                    is_new_dev = True
            if is_new_dev:
                flags.append("NEW_DEVICE")

            if acct_status == "DORMANT" or aid in dormant_accts or "RULE-004" in rules:
                flags.append("DORMANT_ACCOUNT")

            if any(r in ("RULE-003", "RULE-007") for r in rules) or tid in linked_set:
                flags.append("LINKED_PATTERN")

            has_exc = (
                (acct_status == "CLOSED" and bool(closed_at) and occ > str(closed_at))
                or (not overdraft_allowed and float(d["balance_after"]) < 0.0)
                or (tid in unrec_txn_ids)
            )
            if has_exc:
                flags.append("VALIDATION_EXCEPTION")

            d["triggered_rules"] = rules
            d["pattern_flags"] = flags
            d["has_validation_exception"] = has_exc
        return items

    def list_transactions(
        self,
        *,
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        txn_type: str = "ALL",
        risk_level: str = "ALL",
        status: str = "ALL",
        pattern: str = "ALL",
        sort_by: str = "occurred_at",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            cte, base_from, select_cols, where_sql, order_sql, params = self._build_transactions_query(
                search=search,
                start_date=start_date,
                end_date=end_date,
                min_amount=min_amount,
                max_amount=max_amount,
                txn_type=txn_type,
                risk_level=risk_level,
                status=status,
                pattern=pattern,
                sort_by=sort_by,
                sort_dir=sort_dir,
            )
            total = conn.execute(f"{cte} SELECT COUNT(*) {base_from} WHERE {where_sql}", params).fetchone()[0]
            rows = conn.execute(
                f"{cte} SELECT {select_cols} {base_from} WHERE {where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?",
                params + [limit, offset],
            ).fetchall()
            return {"total": total, "items": self._enrich_txn_rows(conn, rows)}
        finally:
            conn.close()

    def get_transaction_detail(self, transaction_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            txn_row = conn.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transaction_id,)).fetchone()
            if not txn_row:
                return None

            eval_res = evaluate_transaction_against_rules(conn, transaction_id=transaction_id)
            acct = dict(conn.execute("SELECT * FROM accounts WHERE account_id = ?", (txn_row["account_id"],)).fetchone())
            cust = dict(conn.execute("SELECT * FROM customers WHERE customer_id = ?", (acct["primary_customer_id"],)).fetchone())

            merchant = None
            if txn_row["merchant_id"]:
                m_row = conn.execute("SELECT * FROM merchants WHERE merchant_id = ?", (txn_row["merchant_id"],)).fetchone()
                if m_row:
                    merchant = dict(m_row)
                    m_stats = conn.execute(
                        "SELECT COUNT(*) AS txn_count, ROUND(COALESCE(AVG(amount), 0), 2) AS avg_amount FROM transactions WHERE merchant_id = ?",
                        (txn_row["merchant_id"],),
                    ).fetchone()
                    merchant["txn_count"] = m_stats["txn_count"]
                    merchant["avg_amount"] = m_stats["avg_amount"]

            device = None
            if txn_row["device_id"]:
                d_row = conn.execute("SELECT * FROM devices WHERE device_id = ?", (txn_row["device_id"],)).fetchone()
                if d_row:
                    device = dict(d_row)
                    adl = conn.execute(
                        "SELECT first_seen_at, last_seen_at, is_trusted FROM account_device_links WHERE account_id = ? AND device_id = ? ORDER BY first_seen_at ASC LIMIT 1",
                        (txn_row["account_id"], txn_row["device_id"]),
                    ).fetchone()
                    if adl:
                        device.update(dict(adl))
                    device["shared_customer_count"] = conn.execute(
                        """
                        SELECT COUNT(DISTINCT a2.primary_customer_id)
                        FROM account_device_links adl2
                        JOIN accounts a2 ON a2.account_id = adl2.account_id
                        WHERE adl2.device_id = ?
                        """,
                        (txn_row["device_id"],),
                    ).fetchone()[0]

            # Linked transfer & origin/destination accounts (Functions 58-59)
            trl_row = conn.execute(
                """
                SELECT tr.*, cu_s.full_name AS source_owner_name, cu_d.full_name AS dest_owner_name
                FROM transfer_links tr
                JOIN accounts a_s ON a_s.account_id = tr.source_account_id
                JOIN customers cu_s ON cu_s.customer_id = a_s.primary_customer_id
                JOIN accounts a_d ON a_d.account_id = tr.dest_account_id
                JOIN customers cu_d ON cu_d.customer_id = a_d.primary_customer_id
                WHERE tr.debit_txn_id = ? OR tr.credit_txn_id = ?
                LIMIT 1
                """,
                (transaction_id, transaction_id),
            ).fetchone()
            transfer_link: dict[str, Any] | None = None
            linked_transfers: list[dict[str, Any]] = []
            if trl_row:
                transfer_link = dict(trl_row)
                if transfer_link.get("debit_txn_id"):
                    dt = conn.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transfer_link["debit_txn_id"],)).fetchone()
                    transfer_link["debit_txn"] = dict(dt) if dt else None
                if transfer_link.get("credit_txn_id"):
                    ct = conn.execute("SELECT * FROM transactions WHERE transaction_id = ?", (transfer_link["credit_txn_id"],)).fetchone()
                    transfer_link["credit_txn"] = dict(ct) if ct else None
                linked_transfers = [
                    dict(r)
                    for r in conn.execute(
                        """
                        SELECT tr2.*, cu_s.full_name AS source_owner_name, cu_d.full_name AS dest_owner_name
                        FROM transfer_links tr2
                        JOIN accounts a_s ON a_s.account_id = tr2.source_account_id
                        JOIN customers cu_s ON cu_s.customer_id = a_s.primary_customer_id
                        JOIN accounts a_d ON a_d.account_id = tr2.dest_account_id
                        JOIN customers cu_d ON cu_d.customer_id = a_d.primary_customer_id
                        WHERE (tr2.source_account_id IN (?, ?) OR tr2.dest_account_id IN (?, ?))
                          AND tr2.transfer_id != ?
                        ORDER BY tr2.initiated_at ASC
                        LIMIT 25
                        """,
                        (
                            transfer_link["source_account_id"],
                            transfer_link["dest_account_id"],
                            transfer_link["source_account_id"],
                            transfer_link["dest_account_id"],
                            transfer_link["transfer_id"],
                        ),
                    ).fetchall()
                ]

            # Triggered rules & alerts (Functions 61-62)
            triggered_alerts = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT DISTINCT al.*, r.rule_name, r.category, r.base_weight, r.threshold_desc,
                           f.metric_name, f.observed_value, f.threshold_value
                    FROM alert_trigger_facts f
                    JOIN alerts al ON al.alert_id = f.alert_id
                    JOIN risk_rules r ON r.rule_id = al.rule_id
                    WHERE f.transaction_id = ? OR al.primary_txn_id = ?
                    ORDER BY al.risk_score DESC, al.alert_id ASC
                    """,
                    (transaction_id, transaction_id),
                ).fetchall()
            ]

            # Related transactions from same customer/account (Function 63)
            related_txns = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT t.*, a2.primary_customer_id AS customer_id, m2.merchant_name
                    FROM transactions t
                    JOIN accounts a2 ON a2.account_id = t.account_id
                    LEFT JOIN merchants m2 ON m2.merchant_id = t.merchant_id
                    WHERE a2.primary_customer_id = ? AND t.transaction_id != ?
                    ORDER BY ABS(julianday(t.occurred_at) - julianday(?)) ASC, t.occurred_at DESC
                    LIMIT 25
                    """,
                    (cust["customer_id"], transaction_id, txn_row["occurred_at"]),
                ).fetchall()
            ]

            # Matching processing/validation exceptions (Function 69)
            all_exc = self.get_quarantine_exceptions()["exceptions"]
            matching_exc = [
                ex
                for ex in all_exc
                if ex["entity_id"] == transaction_id
                or (transfer_link and ex["entity_id"] == transfer_link["transfer_id"])
            ]

            signed_amt = float(txn_row["amount"]) if txn_row["direction"] == "CREDIT" else -float(txn_row["amount"])
            balance_delta = round(float(txn_row["balance_after"]) - float(txn_row["balance_before"]), 2)
            balance_reconciled = abs(balance_delta - round(signed_amt, 2)) <= 0.02

            txn_out = dict(txn_row)
            txn_out["signed_amount"] = round(signed_amt, 2)
            txn_out["balance_delta"] = balance_delta
            txn_out["balance_reconciled"] = balance_reconciled
            txn_out["is_cross_border"] = txn_row["counterparty_country"] != cust["home_country"]
            txn_out["risk_score"] = eval_res["transaction_risk_score"]
            txn_out["risk_level"] = eval_res["transaction_risk_level"]

            return {
                "transaction": txn_out,
                "account": acct,
                "customer": cust,
                "merchant": merchant,
                "device": device,
                "transfer_link": transfer_link,
                "linked_transfers": linked_transfers,
                "triggered_alerts": triggered_alerts,
                "rule_evaluations": eval_res["rule_evaluations"],
                "flag_reasons": eval_res["flag_reasons"],
                "account_risk": eval_res["account_risk"],
                "customer_risk": eval_res["customer_risk"],
                "related_transactions": related_txns,
                "validation_exceptions": matching_exc,
            }
        finally:
            conn.close()

    def export_transactions_report(
        self,
        *,
        fmt: str = "csv",
        search: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        txn_type: str = "ALL",
        risk_level: str = "ALL",
        status: str = "ALL",
        pattern: str = "ALL",
        sort_by: str = "occurred_at",
        sort_dir: str = "desc",
    ) -> tuple[bytes, str, str]:
        res = self.list_transactions(
            search=search,
            start_date=start_date,
            end_date=end_date,
            min_amount=min_amount,
            max_amount=max_amount,
            txn_type=txn_type,
            risk_level=risk_level,
            status=status,
            pattern=pattern,
            sort_by=sort_by,
            sort_dir=sort_dir,
            limit=50000,
            offset=0,
        )
        items = res["items"]
        if fmt == "json":
            payload = {
                "exported_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "total": res["total"],
                "exported_count": len(items),
                "filters": {
                    "search": search,
                    "start_date": start_date,
                    "end_date": end_date,
                    "min_amount": min_amount,
                    "max_amount": max_amount,
                    "txn_type": txn_type,
                    "risk_level": risk_level,
                    "status": status,
                    "pattern": pattern,
                    "sort_by": sort_by,
                    "sort_dir": sort_dir,
                },
                "items": items,
            }
            return json.dumps(payload, indent=2).encode("utf-8"), "application/json", "yottaflex_transactions_export.json"

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "transaction_id",
            "occurred_at",
            "account_id",
            "customer_id",
            "customer_name",
            "txn_type",
            "direction",
            "amount",
            "currency",
            "balance_before",
            "balance_after",
            "channel",
            "merchant_id",
            "merchant_name",
            "device_id",
            "counterparty_country",
            "status",
            "risk_score",
            "risk_level",
            "triggered_rules",
            "pattern_flags",
            "has_validation_exception",
            "reference_note",
        ])
        for tx in items:
            writer.writerow([
                tx["transaction_id"],
                tx["occurred_at"],
                tx["account_id"],
                tx["customer_id"],
                tx["customer_name"],
                tx["txn_type"],
                tx["direction"],
                tx["amount"],
                tx["currency"],
                tx["balance_before"],
                tx["balance_after"],
                tx["channel"],
                tx.get("merchant_id") or "",
                tx.get("merchant_name") or "",
                tx.get("device_id") or "",
                tx["counterparty_country"],
                tx["status"],
                tx["risk_score"],
                tx["risk_level"],
                ";".join(tx.get("triggered_rules", [])),
                ";".join(tx.get("pattern_flags", [])),
                tx.get("has_validation_exception", False),
                tx["reference_note"],
            ])
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "yottaflex_transactions_export.csv"

    # ------------------------------------------------------------------
    # Batch 3 (Functions 71-75): Risk Detection & Risk Scoring Endpoints
    # ------------------------------------------------------------------
    def get_risk_scoring(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_risk_scoring_overview(conn)
        finally:
            conn.close()

    def evaluate_risk(self, *, transaction_id: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        conn = self._conn()
        try:
            return evaluate_transaction_against_rules(conn, transaction_id=transaction_id, payload=payload)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Batch 4 (Functions 76-100): Rule Re-Evaluation, Score History, Integrity Detectors & Alert Management
    # ------------------------------------------------------------------
    def get_integrity_detectors(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return detect_integrity_anomalies(conn)
        finally:
            conn.close()

    def get_risk_executions_and_history(self, *, entity_id: str | None = None) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_rule_executions_and_history(conn, entity_id=entity_id, limit=80)
        finally:
            conn.close()

    def apply_rule_update_and_reevaluate(
        self,
        *,
        rule_id: str | None = None,
        base_weight: int | None = None,
        is_active: bool | None = None,
        threshold_desc: str | None = None,
        actor_id: str = "ADM-001",
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            return update_rule_and_reevaluate(
                conn,
                rule_id=rule_id,
                base_weight=base_weight,
                is_active=is_active,
                threshold_desc=threshold_desc,
                actor_id=actor_id,
            )
        finally:
            conn.close()

    def list_alerts(
        self,
        *,
        search: str | None = None,
        severity: str = "ALL",
        rule_id: str = "ALL",
        status: str = "ALL",
        owner_analyst: str = "ALL",
        sla_breached: bool | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        sort_by: str = "risk_score",
        sort_dir: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        conn = self._conn()
        try:
            ref_row = conn.execute("SELECT MAX(created_at) FROM alerts").fetchone()
            ref_dt = _parse_iso_dt(ref_row[0]) if ref_row and ref_row[0] else None
            alert_sla_map = get_sla_policies(conn)["map"].get("ALERT", {})

            where = ["1=1"]
            params: list[Any] = []
            if severity and severity != "ALL":
                where.append("al.severity = ?")
                params.append(severity)
            if rule_id and rule_id != "ALL":
                where.append("al.rule_id = ?")
                params.append(rule_id)
            if status and status != "ALL":
                where.append("al.status = ?")
                params.append(status)
            if owner_analyst and owner_analyst != "ALL":
                if owner_analyst == "UNASSIGNED":
                    where.append("atm.owner_analyst_id IS NULL")
                else:
                    where.append("atm.owner_analyst_id = ?")
                    params.append(owner_analyst)
            if start_date:
                where.append("al.created_at >= ?")
                params.append(f"{start_date}T00:00:00Z" if len(start_date) == 10 else start_date)
            if end_date:
                where.append("al.created_at <= ?")
                params.append(f"{end_date}T23:59:59Z" if len(end_date) == 10 else end_date)
            if search and search.strip():
                q = f"%{search.strip()}%"
                where.append(
                    """
                    (al.alert_id LIKE ?
                     OR COALESCE(al.primary_txn_id, '') LIKE ?
                     OR al.customer_id LIKE ?
                     OR al.account_id LIKE ?
                     OR cu.full_name LIKE ?
                     OR EXISTS (
                         SELECT 1 FROM alert_trigger_facts atf2
                         WHERE atf2.alert_id = al.alert_id AND atf2.transaction_id LIKE ?
                     ))
                    """
                )
                params.extend([q, q, q, q, q, q])

            where_sql = " AND ".join(where)
            base_cte = """
                WITH case_link_agg AS (
                    SELECT cal.alert_id,
                           MIN(cal.case_id) AS case_id,
                           MAX(ca.priority_score) AS case_priority_score,
                           MAX(ca.priority_tier) AS case_priority_tier
                    FROM case_alert_links cal
                    JOIN cases ca ON ca.case_id = cal.case_id
                    GROUP BY cal.alert_id
                )
            """
            base_from = """
                FROM alerts al
                JOIN risk_rules rr ON rr.rule_id = al.rule_id
                JOIN customers cu ON cu.customer_id = al.customer_id
                LEFT JOIN case_link_agg cla ON cla.alert_id = al.alert_id
                LEFT JOIN alert_triage_meta atm ON atm.alert_id = al.alert_id
            """

            sort_dir_sql = "ASC" if str(sort_dir).lower() == "asc" else "DESC"
            if sort_by == "priority":
                order_sql = f"priority_score_effective {sort_dir_sql}, severity_rank {sort_dir_sql}, al.alert_id DESC"
            elif sort_by == "created_at":
                order_sql = f"al.created_at {sort_dir_sql}, al.alert_id DESC"
            else:
                order_sql = f"al.risk_score {sort_dir_sql}, al.alert_id DESC"

            rows = conn.execute(
                f"""
                {base_cte}
                SELECT al.*, rr.rule_name, rr.category AS rule_category, rr.base_weight, rr.threshold_desc,
                       cu.full_name AS customer_name,
                       cla.case_id,
                       cla.case_priority_score,
                       cla.case_priority_tier,
                       atm.owner_analyst_id,
                       atm.disposition,
                       atm.suppression_reason,
                       atm.sla_hours AS custom_sla_hours,
                       COALESCE(atm.sla_hours, 72) AS sla_hours,
                       COALESCE(cla.case_priority_score, al.risk_score) AS priority_score_effective,
                       CASE al.severity
                           WHEN 'CRITICAL' THEN 4
                           WHEN 'HIGH' THEN 3
                           WHEN 'MEDIUM' THEN 2
                           ELSE 1
                       END AS severity_rank
                {base_from}
                WHERE {where_sql}
                ORDER BY {order_sql}
                """,
                params,
            ).fetchall()

            active_suppressions = list_suppression_rules(conn, active_only=True)
            filtered: list[dict[str, Any]] = []
            for r in rows:
                item = dict(r)
                is_active = item["status"] in {"OPEN", "GROUPED", "ACKNOWLEDGED", "UNDER_INVESTIGATION", "ESCALATED"}
                policy_hrs = int(alert_sla_map.get(str(item.get("severity") or "MEDIUM"), 72))
                eff_sla = int(item["custom_sla_hours"]) if item.get("custom_sla_hours") is not None else policy_hrs
                item["sla_hours"] = eff_sla
                item.pop("custom_sla_hours", None)
                age_h, breached = _sla_metrics(item["created_at"], ref_dt, eff_sla, is_active)
                item["age_hours"] = age_h
                item["sla_breached"] = breached
                item["matched_suppression_id"] = match_suppression_for_alert(active_suppressions, item)
                if sla_breached is True and not breached:
                    continue
                if sla_breached is False and breached:
                    continue
                filtered.append(item)

            return {"total": len(filtered), "items": filtered[offset : offset + limit]}
        finally:
            conn.close()

    def export_alerts_report(self, *, fmt: str = "csv", **filters: Any) -> tuple[bytes, str, str]:
        data = self.list_alerts(limit=5000, offset=0, **filters)
        if fmt == "json":
            return json.dumps(data, indent=2).encode("utf-8"), "application/json; charset=utf-8", "yottaflex_alerts.json"
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([
            "alert_id", "rule_id", "rule_name", "severity", "risk_score", "priority_score_effective",
            "status", "disposition", "owner_analyst_id", "customer_id", "customer_name",
            "account_id", "trigger_total_amount", "case_id", "age_hours", "sla_breached", "created_at",
        ])
        for a in data["items"]:
            w.writerow([
                a["alert_id"], a["rule_id"], a["rule_name"], a["severity"], a["risk_score"], a["priority_score_effective"],
                a["status"], a.get("disposition") or "", a.get("owner_analyst_id") or "", a["customer_id"], a["customer_name"],
                a["account_id"], a["trigger_total_amount"], a.get("case_id") or "", a["age_hours"], a["sla_breached"], a["created_at"],
            ])
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "yottaflex_alerts.csv"

    def get_alert_detail(self, alert_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            al_row = conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
            if not al_row:
                return None
            alert = dict(al_row)

            rule_row = conn.execute("SELECT * FROM risk_rules WHERE rule_id = ?", (alert["rule_id"],)).fetchone()
            rule = dict(rule_row) if rule_row else None
            cust = dict(conn.execute("SELECT * FROM customers WHERE customer_id = ?", (alert["customer_id"],)).fetchone())
            acct = dict(conn.execute("SELECT * FROM accounts WHERE account_id = ?", (alert["account_id"],)).fetchone())

            primary_txn = None
            if alert.get("primary_txn_id"):
                pt = conn.execute(
                    """
                    SELECT t.*, m.merchant_name, m.category AS merchant_category
                    FROM transactions t
                    LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
                    WHERE t.transaction_id = ?
                    """,
                    (alert["primary_txn_id"],),
                ).fetchone()
                if pt:
                    primary_txn = dict(pt)

            trigger_facts = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT f.*, t.txn_type, t.direction, t.amount, t.occurred_at, t.channel, t.device_id, t.counterparty_country
                    FROM alert_trigger_facts f
                    LEFT JOIN transactions t ON t.transaction_id = f.transaction_id
                    WHERE f.alert_id = ?
                    ORDER BY f.recorded_at ASC, f.fact_id ASC
                    """,
                    (alert_id,),
                ).fetchall()
            ]

            linked_cases = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT ca.*, cal.linkage_reason, cal.linkage_key, cal.linked_at
                    FROM case_alert_links cal
                    JOIN cases ca ON ca.case_id = cal.case_id
                    WHERE cal.alert_id = ?
                    ORDER BY ca.priority_score DESC
                    """,
                    (alert_id,),
                ).fetchall()
            ]

            # Supporting related transactions on same account within +/- 48h of alert creation (Function 99)
            supporting_txns = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT t.*, m.merchant_name
                    FROM transactions t
                    LEFT JOIN merchants m ON m.merchant_id = t.merchant_id
                    WHERE t.account_id = ?
                      AND t.occurred_at BETWEEN strftime('%Y-%m-%dT%H:%M:%SZ', ?, '-48 hours')
                                             AND strftime('%Y-%m-%dT%H:%M:%SZ', ?, '+48 hours')
                    ORDER BY t.occurred_at DESC, t.transaction_id DESC
                    LIMIT 30
                    """,
                    (alert["account_id"], alert["created_at"], alert["created_at"]),
                ).fetchall()
            ]

            # Other alerts associated with same customer or account (Function 100)
            sibling_alerts = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT al.*, rr.rule_name
                    FROM alerts al
                    JOIN risk_rules rr ON rr.rule_id = al.rule_id
                    WHERE (al.customer_id = ? OR al.account_id = ?) AND al.alert_id != ?
                    ORDER BY al.risk_score DESC, al.created_at DESC
                    LIMIT 40
                    """,
                    (alert["customer_id"], alert["account_id"], alert_id),
                ).fetchall()
            ]

            # Function 76: individual risk contribution breakdown
            base_w = float(rule["base_weight"]) if rule else 0.0
            total_sc = float(alert["risk_score"])
            cnt_contrib = round(min(10.0, max(0, int(alert["trigger_txn_count"]) - 1) * 1.5), 2)
            amt_contrib = round(max(0.0, total_sc - base_w - cnt_contrib), 2)
            risk_contributions = [
                {
                    "component": f"{rule['rule_id'] if rule else alert['rule_id']} Base Rule Weight",
                    "points": round(base_w, 2),
                    "detail": rule["threshold_desc"] if rule else "",
                },
                {
                    "component": f"Trigger Frequency ({alert['trigger_txn_count']} txns)",
                    "points": cnt_contrib,
                    "detail": "Multi-event recurrence multiplier",
                },
                {
                    "component": f"Exposure Severity (${float(alert['trigger_total_amount']):,.2f})",
                    "points": amt_contrib,
                    "detail": "Transaction / exposure escalation factor",
                },
            ]

            hist_data = get_rule_executions_and_history(conn, entity_id=alert_id, limit=25)
            meta_row = conn.execute("SELECT * FROM alert_triage_meta WHERE alert_id = ?", (alert_id,)).fetchone()
            triage_meta = dict(meta_row) if meta_row else {
                "alert_id": alert_id,
                "owner_analyst_id": None,
                "disposition": None,
                "suppression_reason": None,
                "sla_hours": 72,
                "updated_at": None,
            }
            audit_events = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM alert_audit_events WHERE alert_id = ? ORDER BY created_at DESC, event_id DESC",
                    (alert_id,),
                ).fetchall()
            ]
            watchlist_tags = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT * FROM entity_watchlist_tags
                    WHERE (entity_type = 'CUSTOMER' AND entity_id = ?)
                       OR (entity_type = 'ACCOUNT' AND entity_id = ?)
                    ORDER BY created_at DESC
                    """,
                    (alert["customer_id"], alert["account_id"]),
                ).fetchall()
            ]
            ref_row = conn.execute("SELECT MAX(created_at) FROM alerts").fetchone()
            ref_dt = _parse_iso_dt(ref_row[0]) if ref_row and ref_row[0] else None
            alert_sla_map = get_sla_policies(conn)["map"].get("ALERT", {})
            is_active = alert["status"] in {"OPEN", "GROUPED", "ACKNOWLEDGED", "UNDER_INVESTIGATION", "ESCALATED"}
            age_h, sla_breached = _sla_metrics(alert["created_at"], ref_dt, int(triage_meta.get("sla_hours") or 72), is_active)
            alert["age_hours"] = age_h
            alert["sla_breached"] = sla_breached

            return {
                "alert": alert,
                "rule": rule,
                "customer": cust,
                "account": acct,
                "primary_transaction": primary_txn,
                "trigger_facts": trigger_facts,
                "linked_cases": linked_cases,
                "supporting_transactions": supporting_txns,
                "sibling_alerts": sibling_alerts,
                "risk_contributions": risk_contributions,
                "score_history": hist_data["score_history"],
                "triage_meta": triage_meta,
                "audit_events": audit_events,
                "watchlist_tags": watchlist_tags,
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Batch 8 (Functions 176-200): Forensics, Jurisdictions, Controls & Vault
    # ------------------------------------------------------------------
    def get_corridor_risk_matrix(self, *, limit: int = 80) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_corridor_risk_matrix(conn, limit=limit)
        finally:
            conn.close()

    def list_high_risk_countries(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_high_risk_countries(conn)
        finally:
            conn.close()

    def upsert_high_risk_country(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return upsert_high_risk_country(conn, **kwargs)
        finally:
            conn.close()

    def delete_high_risk_country(self, country_code: str) -> bool:
        conn = self._conn()
        try:
            return delete_high_risk_country(conn, country_code)
        finally:
            conn.close()

    def get_merchant_leaderboard(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_merchant_leaderboard(conn, **kwargs)
        finally:
            conn.close()

    def get_merchant_detail(self, merchant_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            return get_merchant_detail(conn, merchant_id)
        finally:
            conn.close()

    def trace_flow_chains(self, account_id: str, *, max_hops: int = 3) -> dict[str, Any]:
        conn = self._conn()
        try:
            return trace_flow_chains(conn, account_id, max_hops=max_hops)
        finally:
            conn.close()

    def detect_structuring_clusters(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return detect_structuring_clusters(conn, **kwargs)
        finally:
            conn.close()

    def get_customer_peer_baseline(self, customer_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            return get_customer_peer_baseline(conn, customer_id)
        finally:
            conn.close()

    def list_kyc_reviews(self, customer_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_kyc_reviews(conn, customer_id)
        finally:
            conn.close()

    def submit_kyc_review(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return submit_kyc_review(conn, **kwargs)
        finally:
            conn.close()

    def get_account_control(self, account_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_account_control(conn, account_id)
        finally:
            conn.close()

    def set_account_control(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            res = set_account_control(conn, **kwargs)
            if res.get("control_status") == "FULL_FREEZE":
                enqueue_or_dispatch_siem(
                    conn,
                    event_type="ACCOUNT_FULL_FREEZE",
                    severity="CRITICAL",
                    entity_id=res["account_id"],
                    payload=res,
                )
            return res
        finally:
            conn.close()

    def get_account_velocity(self, account_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_account_velocity(conn, account_id)
        finally:
            conn.close()

    def list_case_pins(self, case_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_case_pins(conn, case_id)
        finally:
            conn.close()

    def add_case_pin(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return add_case_pin(conn, **kwargs)
        finally:
            conn.close()

    def delete_case_pin(self, *, case_id: str, pin_id: str) -> bool:
        conn = self._conn()
        try:
            return delete_case_pin(conn, case_id=case_id, pin_id=pin_id)
        finally:
            conn.close()

    def list_case_comments(self, case_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_case_comments(conn, case_id)
        finally:
            conn.close()

    def add_case_comment(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return add_case_comment(conn, **kwargs)
        finally:
            conn.close()

    def get_playbooks(self) -> list[dict[str, Any]]:
        return get_playbooks()

    def apply_playbook_to_case(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return apply_playbook_to_case(conn, **kwargs)
        finally:
            conn.close()

    def list_pending_escalations(self, *, limit: int = 80) -> dict[str, Any]:
        conn = self._conn()
        try:
            return list_pending_escalations(conn, limit=limit)
        finally:
            conn.close()

    def generate_rfi_packet(self, case_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            return generate_rfi_packet(conn, case_id)
        finally:
            conn.close()

    def get_sla_radar(self, *, warning_hours: int = 8) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_sla_radar(conn, warning_hours=warning_hours)
        finally:
            conn.close()

    def rebalance_queue_workload(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return rebalance_queue_workload(conn, **kwargs)
        finally:
            conn.close()

    def list_suppression_rules(self, *, active_only: bool = True) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_suppression_rules(conn, active_only=active_only)
        finally:
            conn.close()

    def create_suppression_rule(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return create_suppression_rule(conn, **kwargs)
        finally:
            conn.close()

    def deactivate_suppression_rule(self, suppression_id: str) -> bool:
        conn = self._conn()
        try:
            return deactivate_suppression_rule(conn, suppression_id)
        finally:
            conn.close()

    def log_export_event(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return log_export_event(conn, **kwargs)
        finally:
            conn.close()

    def list_export_history(self, *, limit: int = 100) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_export_history(conn, limit=limit)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Batch 9 (Functions 201-225): Calibration, Merge, SIEM, Jobs & Prefs
    # ------------------------------------------------------------------
    def forecast_alert_capacity(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return forecast_alert_capacity(conn, **kwargs)
        finally:
            conn.close()

    def sweep_rule_threshold(self, *, rule_id: str = "RULE-001") -> dict[str, Any]:
        conn = self._conn()
        try:
            return sweep_rule_threshold(conn, self.gt_path, rule_id=rule_id)
        finally:
            conn.close()

    def compute_temporal_drift(self, *, buckets: int = 6) -> dict[str, Any]:
        conn = self._conn()
        try:
            return compute_temporal_drift(conn, self.gt_path, buckets=buckets)
        finally:
            conn.close()

    def list_calibration_proposals(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_calibration_proposals(conn)
        finally:
            conn.close()

    def create_calibration_proposal(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return create_calibration_proposal(conn, **kwargs)
        finally:
            conn.close()

    def approve_calibration_proposal(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return approve_calibration_proposal(conn, **kwargs)
        finally:
            conn.close()

    def run_sandbox_pattern(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return run_sandbox_pattern(conn, **kwargs)
        finally:
            conn.close()

    def find_case_merge_candidates(self, *, limit: int = 20) -> dict[str, Any]:
        conn = self._conn()
        try:
            return find_case_merge_candidates(conn, limit=limit)
        finally:
            conn.close()

    def merge_cases(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return merge_cases(conn, **kwargs)
        finally:
            conn.close()

    def list_notifications(self, user_id: str, *, unread_only: bool = False) -> dict[str, Any]:
        conn = self._conn()
        try:
            return list_notifications(conn, user_id, unread_only=unread_only)
        finally:
            conn.close()

    def mark_notifications_read(self, user_id: str, notif_id: str | None = None) -> int:
        conn = self._conn()
        try:
            return mark_notifications_read(conn, user_id, notif_id)
        finally:
            conn.close()

    def list_siem_outbox(self, *, limit: int = 50) -> dict[str, Any]:
        conn = self._conn()
        try:
            return list_siem_outbox(conn, limit=limit)
        finally:
            conn.close()

    def enqueue_or_dispatch_siem(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return enqueue_or_dispatch_siem(conn, **kwargs)
        finally:
            conn.close()

    def list_pipeline_runs(self, *, limit: int = 30) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_pipeline_runs(conn, limit=limit)
        finally:
            conn.close()

    def run_pipeline_job(self, *, job_type: str, actor_id: str) -> dict[str, Any]:
        val = self.run_live_integrity_validation()
        radar = self.get_sla_radar()
        rings = self.detect_collusion_rings(limit=10)
        conn = self._conn()
        try:
            return run_pipeline_job(
                conn,
                job_type=job_type,
                actor_id=actor_id,
                validation_summary=f"{val['passed_checks']}/{val['total_checks']} invariants passed ({val['quarantine_isolated_total']} quarantined)",
                sla_summary=f"{radar['breached_count']} breached, {radar['at_risk_count']} at risk (<8h)",
                ring_summary=f"{rings['total_rings']} multi-customer shared-device rings detected",
            )
        finally:
            conn.close()

    def export_compliance_bundle(self, *, actor_id: str = "SYSTEM") -> tuple[bytes, str, str]:
        digest = self.get_executive_digest()
        audit = self.get_unified_audit_events(limit=50)
        zl = self.check_zero_leakage_live()
        manifest = self.verify_export_manifest_integrity()
        bundle = {
            "bundle_type": "YOTTAFLEX_COMPLIANCE_ARCHIVE",
            "executive_digest": digest,
            "zero_leakage_certificate": zl,
            "manifest_integrity": manifest,
            "recent_audit_events": audit["items"],
            "batch_digest": audit["batch_digest"],
        }
        self.log_export_event(
            actor_id=actor_id,
            export_type="COMPLIANCE_BUNDLE",
            fmt="JSON",
            filter_summary="Executive Digest + Audit + Manifest + AST Proof",
            row_count=len(audit["items"]),
        )
        return (
            json.dumps(bundle, indent=2).encode("utf-8"),
            "application/json; charset=utf-8",
            "yottaflex_compliance_bundle.json",
        )

    def get_user_preferences(self, user_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_user_preferences(conn, user_id)
        finally:
            conn.close()

    def update_user_preferences(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return update_user_preferences(conn, **kwargs)
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Batch 10 & 11: Functions 226-275 Enterprise Intelligence & Deep Eval
    # ------------------------------------------------------------------
    def run_sanctions_screening(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return run_sanctions_screening(conn, **kwargs)
        finally:
            conn.close()

    def list_screening_history(self, entity_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_screening_history(conn, entity_id=entity_id, limit=limit)
        finally:
            conn.close()

    def get_fan_in_out_hubs(self, limit: int = 25) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_fan_in_out_hubs(conn, limit=limit)
        finally:
            conn.close()

    def get_customer_chronology(self, customer_id: str, limit: int = 80) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_customer_chronology(conn, customer_id, limit=limit)
        finally:
            conn.close()

    def get_customer_corridor_exposure(self, customer_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_customer_corridor_exposure(conn, customer_id)
        finally:
            conn.close()

    def get_account_burst_profile(self, account_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_account_burst_profile(conn, account_id)
        finally:
            conn.close()

    def get_account_transfer_matrix(self, account_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_account_transfer_matrix(conn, account_id)
        finally:
            conn.close()

    def generate_goaml_xml(self, case_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return generate_goaml_xml(conn, case_id)
        finally:
            conn.close()

    def list_case_handoffs(self, case_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_case_handoffs(conn, case_id)
        finally:
            conn.close()

    def add_case_handoff(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return add_case_handoff(conn, **kwargs)
        finally:
            conn.close()

    def create_case_evidence_seal(self, case_id: str, actor_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return create_case_evidence_seal(conn, case_id=case_id, actor_id=actor_id)
        finally:
            conn.close()

    def list_case_seals(self, case_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_case_seals(conn, case_id)
        finally:
            conn.close()

    def bulk_tag_cases(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return bulk_tag_cases(conn, **kwargs)
        finally:
            conn.close()

    def reopen_closed_case(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return reopen_closed_case(conn, **kwargs)
        finally:
            conn.close()

    def get_alert_co_occurrence(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_alert_co_occurrence(conn)
        finally:
            conn.close()

    def get_alert_fatigue_report(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_alert_fatigue_report(conn)
        finally:
            conn.close()

    def batch_simulate_transactions(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return batch_simulate_transactions(conn, **kwargs)
        finally:
            conn.close()

    def find_shared_pii_clusters(self, limit: int = 25) -> dict[str, Any]:
        conn = self._conn()
        try:
            return find_shared_pii_clusters(conn, limit=limit)
        finally:
            conn.close()

    def detect_mcc_outliers(self, limit: int = 25) -> dict[str, Any]:
        conn = self._conn()
        try:
            return detect_mcc_outliers(conn, limit=limit)
        finally:
            conn.close()

    def check_balance_continuity(self, limit: int = 25) -> dict[str, Any]:
        conn = self._conn()
        try:
            return check_balance_continuity(conn, limit=limit)
        finally:
            conn.close()

    def get_device_velocity_leaderboard(self, limit: int = 25) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_device_velocity_leaderboard(conn, limit=limit)
        finally:
            conn.close()

    def list_custom_rule_drafts(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_custom_rule_drafts(conn)
        finally:
            conn.close()

    def create_custom_rule_draft(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return create_custom_rule_draft(conn, **kwargs)
        finally:
            conn.close()

    def get_quarantine_grouped(self) -> dict[str, Any]:
        q = self.list_quarantine_exceptions_filtered()
        conn = self._conn()
        try:
            return get_quarantine_grouped_summary(conn, q.get("items", []))
        finally:
            conn.close()

    def list_qa_samples(self, limit: int = 20) -> dict[str, Any]:
        conn = self._conn()
        try:
            return list_qa_samples(conn, limit=limit)
        finally:
            conn.close()

    def submit_qa_grade(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return submit_qa_grade(conn, **kwargs)
        finally:
            conn.close()

    def run_sla_auto_escalation(self, actor_id: str, max_escalations: int = 10) -> dict[str, Any]:
        conn = self._conn()
        try:
            res = run_sla_auto_escalation(conn, actor_id=actor_id, max_escalations=max_escalations)
            if res["escalated_count"] > 0:
                create_notification(
                    conn,
                    user_id="USR-001",
                    category="SLA_SWEEP",
                    severity="CRITICAL",
                    title=f"SLA Auto-Escalation: {res['escalated_count']} Critical Case(s)",
                    body=f"Moved {', '.join(res['case_ids'][:3])} to IN_REVIEW",
                    entity_type="case",
                    entity_id=res["case_ids"][0],
                )
            return res
        finally:
            conn.close()

    def list_webhooks(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_webhooks(conn)
        finally:
            conn.close()

    def create_webhook(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return create_webhook(conn, **kwargs)
        finally:
            conn.close()

    def test_webhook_ping(self, webhook_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return test_webhook_ping(conn, webhook_id)
        finally:
            conn.close()

    def delete_webhook(self, webhook_id: str) -> bool:
        conn = self._conn()
        try:
            return delete_webhook(conn, webhook_id)
        finally:
            conn.close()

    def verify_audit_chain(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return verify_audit_chain_integrity(conn)
        finally:
            conn.close()

    def get_evaluation_lift_curve(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return compute_lift_curve(conn, self.gt_path)
        finally:
            conn.close()

    def get_evaluation_score_histogram(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return compute_score_histogram(conn, self.gt_path)
        finally:
            conn.close()

    def get_evaluation_typology_severity_matrix(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return compute_typology_severity_matrix(conn, self.gt_path)
        finally:
            conn.close()

    def get_evaluation_rule_marginal_lift(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return compute_rule_marginal_lift(conn, self.gt_path)
        finally:
            conn.close()

    def get_evaluation_feature_psi(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return compute_feature_psi(conn)
        finally:
            conn.close()

    def get_data_scorecard(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_data_scorecard(conn)
        finally:
            conn.close()

    def list_search_bookmarks(self, user_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_search_bookmarks(conn, user_id)
        finally:
            conn.close()

    def create_search_bookmark(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return create_search_bookmark(conn, **kwargs)
        finally:
            conn.close()

    def delete_search_bookmark(self, user_id: str, bookmark_id: str) -> bool:
        conn = self._conn()
        try:
            return delete_search_bookmark(conn, user_id=user_id, bookmark_id=bookmark_id)
        finally:
            conn.close()

    def list_scheduled_digests(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_scheduled_digests(conn)
        finally:
            conn.close()

    def upsert_scheduled_digest(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return upsert_scheduled_digest(conn, **kwargs)
        finally:
            conn.close()

    def get_retention_status(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_retention_status(conn)
        finally:
            conn.close()

    def update_retention_policy(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return update_retention_policy(conn, **kwargs)
        finally:
            conn.close()

    def compare_two_cases(self, case_id_a: str, case_id_b: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return compare_two_cases(conn, case_id_a, case_id_b)
        finally:
            conn.close()

    def get_related_cases_timeline(self, case_id: str) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_related_cases_timeline(conn, case_id)
        finally:
            conn.close()

    def get_tier_workload_projection(self) -> dict[str, Any]:
        conn = self._conn()
        try:
            return get_tier_workload_projection(conn)
        finally:
            conn.close()

    def simulate_case_what_if_score(self, case_id: str, waived_alert_ids: list[str]) -> dict[str, Any]:
        conn = self._conn()
        try:
            return simulate_case_what_if_score(conn, case_id, waived_alert_ids)
        finally:
            conn.close()

    def list_exam_readiness(self) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_exam_readiness(conn)
        finally:
            conn.close()

    def update_exam_readiness(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return update_exam_readiness(conn, **kwargs)
        finally:
            conn.close()

    def list_workspace_pins(self, user_id: str) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            return list_workspace_pins(conn, user_id)
        finally:
            conn.close()

    def add_workspace_pin(self, **kwargs: Any) -> dict[str, Any]:
        conn = self._conn()
        try:
            return add_workspace_pin(conn, **kwargs)
        finally:
            conn.close()

    def delete_workspace_pin(self, user_id: str, pin_id: str) -> bool:
        conn = self._conn()
        try:
            return delete_workspace_pin(conn, user_id=user_id, pin_id=pin_id)
        finally:
            conn.close()

    def export_customers_directory(
        self,
        *,
        fmt: str = "csv",
        search: str | None = None,
        kyc_tier: str = "ALL",
        risk_rating: str = "ALL",
        account_status: str = "ALL",
        multi_suspicious: bool = False,
        actor_id: str = "SYSTEM",
    ) -> tuple[bytes, str, str]:
        res = self.list_customers(
            search=search,
            kyc_tier=kyc_tier,
            risk_rating=risk_rating,
            account_status=account_status,
            multi_suspicious=multi_suspicious,
            limit=500,
            offset=0,
        )
        items = res["items"]
        self.log_export_event(
            actor_id=actor_id,
            export_type="CUSTOMERS_DIRECTORY",
            fmt=fmt.upper(),
            filter_summary=f"kyc={kyc_tier},risk={risk_rating}",
            row_count=len(items),
        )
        if fmt.lower() == "json":
            return (
                json.dumps({"total": res["total"], "items": items}, indent=2).encode("utf-8"),
                "application/json; charset=utf-8",
                "yottaflex_customers_directory.json",
            )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["customer_id", "full_name", "email", "segment", "kyc_tier", "risk_rating", "home_country", "account_count", "alert_count", "case_count"])
        for it in items:
            writer.writerow([it["customer_id"], it["full_name"], it["email"], it["segment"], it["kyc_tier"], it["risk_rating"], it["home_country"], it["account_count"], it["alert_count"], it["case_count"]])
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "yottaflex_customers_directory.csv"

    def export_accounts_directory(
        self,
        *,
        fmt: str = "csv",
        search: str | None = None,
        status: str = "ALL",
        dormant_reactivated: bool = False,
        actor_id: str = "SYSTEM",
    ) -> tuple[bytes, str, str]:
        res = self.list_accounts(
            search=search,
            status=status,
            dormant_reactivated=dormant_reactivated,
            limit=500,
            offset=0,
        )
        items = res["items"]
        self.log_export_event(
            actor_id=actor_id,
            export_type="ACCOUNTS_DIRECTORY",
            fmt=fmt.upper(),
            filter_summary=f"status={status},dormant={dormant_reactivated}",
            row_count=len(items),
        )
        if fmt.lower() == "json":
            return (
                json.dumps({"total": res["total"], "items": items}, indent=2).encode("utf-8"),
                "application/json; charset=utf-8",
                "yottaflex_accounts_directory.json",
            )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["account_id", "primary_customer_id", "customer_name", "account_type", "status", "current_balance", "txn_count", "alert_count", "is_dormant_reactivated"])
        for it in items:
            writer.writerow([it["account_id"], it["primary_customer_id"], it["customer_name"], it["account_type"], it["status"], it["current_balance"], it["txn_count"], it["alert_count"], it["is_dormant_reactivated"]])
        return buf.getvalue().encode("utf-8"), "text/csv; charset=utf-8", "yottaflex_accounts_directory.csv"

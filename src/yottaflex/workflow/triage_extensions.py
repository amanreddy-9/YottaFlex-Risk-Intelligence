"""SQLite extensions for Functions 101-125: Alert Triage, Case Queue Operations, Checklist, SAR Draft & Watchlist Tags."""

from __future__ import annotations

import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from yottaflex.workflow.case_service import ANALYST_ROLES, WorkflowError, submit_analyst_action

VALID_ALERT_STATUSES = {
    "OPEN",
    "GROUPED",
    "ACKNOWLEDGED",
    "UNDER_INVESTIGATION",
    "ESCALATED",
    "FALSE_POSITIVE",
    "DISMISSED",
    "RESOLVED",
}

ALERT_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"ACKNOWLEDGED", "UNDER_INVESTIGATION", "ESCALATED", "FALSE_POSITIVE", "DISMISSED", "RESOLVED", "GROUPED"},
    "GROUPED": {"ACKNOWLEDGED", "UNDER_INVESTIGATION", "ESCALATED", "FALSE_POSITIVE", "DISMISSED", "RESOLVED"},
    "ACKNOWLEDGED": {"UNDER_INVESTIGATION", "ESCALATED", "FALSE_POSITIVE", "DISMISSED", "RESOLVED", "GROUPED"},
    "UNDER_INVESTIGATION": {"ESCALATED", "FALSE_POSITIVE", "DISMISSED", "RESOLVED", "ACKNOWLEDGED", "GROUPED"},
    "ESCALATED": {"UNDER_INVESTIGATION", "FALSE_POSITIVE", "DISMISSED", "RESOLVED", "GROUPED"},
    "FALSE_POSITIVE": {"UNDER_INVESTIGATION", "ESCALATED", "ACKNOWLEDGED"},
    "DISMISSED": {"UNDER_INVESTIGATION", "ACKNOWLEDGED"},
    "RESOLVED": {"UNDER_INVESTIGATION"},
}

WATCHLIST_TAGS = {
    "PEP_WATCH",
    "MULE_SUSPECT",
    "STRUCTURING_REPEAT",
    "VELOCITY_WATCH",
    "VERIFIED_PAYROLL",
    "HIGH_RISK_ENTITY",
    "SANCTIONS_HIT",
    "INTERNAL_WATCH",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4).upper()}"


def ensure_triage_extensions_schema(conn: sqlite3.Connection) -> None:
    """Create non-destructive operational triage tables idempotently."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS alert_triage_meta (
            alert_id TEXT PRIMARY KEY,
            owner_analyst_id TEXT,
            disposition TEXT,
            suppression_reason TEXT,
            sla_hours INTEGER NOT NULL DEFAULT 72,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS alert_audit_events (
            event_id TEXT PRIMARY KEY,
            alert_id TEXT NOT NULL,
            actor_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            prev_status TEXT,
            new_status TEXT,
            detail TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS case_triage_meta (
            case_id TEXT PRIMARY KEY,
            assigned_analyst_id TEXT,
            priority_override_tier TEXT,
            priority_override_score REAL,
            override_reason TEXT,
            override_by TEXT,
            override_at TEXT,
            sla_hours INTEGER NOT NULL DEFAULT 48,
            sar_draft TEXT,
            sar_updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS case_evidence_checklist (
            case_id TEXT PRIMARY KEY,
            rules_reviewed INTEGER NOT NULL DEFAULT 0,
            ledger_reconciled INTEGER NOT NULL DEFAULT 0,
            network_verified INTEGER NOT NULL DEFAULT 0,
            kyc_corroborated INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            updated_by TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS entity_watchlist_tags (
            tag_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            note TEXT,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(entity_type, entity_id, tag)
        );

        CREATE INDEX IF NOT EXISTS idx_alert_audit_alert ON alert_audit_events(alert_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_watchlist_entity ON entity_watchlist_tags(entity_type, entity_id);
        """
    )


def _log_alert_event(
    conn: sqlite3.Connection,
    *,
    alert_id: str,
    actor_id: str,
    event_type: str,
    prev_status: str | None,
    new_status: str | None,
    detail: str,
    now_ts: str,
) -> dict[str, Any]:
    ev_id = _new_id("AEV")
    conn.execute(
        """
        INSERT INTO alert_audit_events (event_id, alert_id, actor_id, event_type, prev_status, new_status, detail, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ev_id, alert_id, actor_id, event_type, prev_status, new_status, detail, now_ts),
    )
    return {
        "event_id": ev_id,
        "alert_id": alert_id,
        "actor_id": actor_id,
        "event_type": event_type,
        "prev_status": prev_status,
        "new_status": new_status,
        "detail": detail,
        "created_at": now_ts,
    }


def _recalc_case_metrics(conn: sqlite3.Connection, case_id: str, now_ts: str) -> None:
    agg = conn.execute(
        """
        SELECT COUNT(DISTINCT cal.alert_id) AS cnt,
               COUNT(DISTINCT al.account_id) AS acct_cnt,
               COALESCE(ROUND(SUM(al.trigger_total_amount), 2), 0.0) AS exp
        FROM case_alert_links cal
        JOIN alerts al ON al.alert_id = cal.alert_id
        WHERE cal.case_id = ?
        """,
        (case_id,),
    ).fetchone()
    conn.execute(
        """
        UPDATE cases
        SET alert_count = ?, linked_account_count = ?, total_exposure_amount = ?, updated_at = ?
        WHERE case_id = ?
        """,
        (
            int(agg["cnt"] or 0),
            max(1, int(agg["acct_cnt"] or 1)),
            float(agg["exp"] or 0.0),
            now_ts,
            case_id,
        ),
    )


def triage_alert(
    db_path: Path,
    *,
    alert_id: str,
    actor_id: str,
    owner_analyst_id: str | None = None,
    status: str | None = None,
    disposition: str | None = None,
    suppression_reason: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Update alert owner, status, FP/TP disposition, suppression feedback, or add note."""
    now_ts = _now_iso()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_triage_extensions_schema(conn)
        al = conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
        if not al:
            raise WorkflowError(f"Alert '{alert_id}' not found.")

        prev_status = al["status"]
        new_status = prev_status
        meta = conn.execute("SELECT * FROM alert_triage_meta WHERE alert_id = ?", (alert_id,)).fetchone()
        cur_owner = meta["owner_analyst_id"] if meta else None
        cur_disp = meta["disposition"] if meta else None
        cur_supp = meta["suppression_reason"] if meta else None

        events: list[dict[str, Any]] = []

        if owner_analyst_id is not None:
            owner_clean = owner_analyst_id.strip() or None
            if owner_clean and owner_clean not in ANALYST_ROLES:
                raise WorkflowError(f"Unknown analyst_id '{owner_clean}'.")
            cur_owner = owner_clean
            events.append(
                _log_alert_event(
                    conn,
                    alert_id=alert_id,
                    actor_id=actor_id,
                    event_type="ALERT_ASSIGNED",
                    prev_status=prev_status,
                    new_status=new_status,
                    detail=f"Assigned alert owner to {owner_clean or 'UNASSIGNED'}",
                    now_ts=now_ts,
                )
            )

        if disposition is not None:
            disp_u = disposition.strip().upper()
            if disp_u not in {"TRUE_POSITIVE", "FALSE_POSITIVE", "BENIGN_PATTERN", "NEEDS_MORE_INFO"}:
                raise WorkflowError(f"Unsupported disposition '{disposition}'.")
            cur_disp = disp_u
            if status is None:
                if disp_u in {"FALSE_POSITIVE", "BENIGN_PATTERN"}:
                    status = "FALSE_POSITIVE"
                elif disp_u == "TRUE_POSITIVE":
                    status = "ESCALATED"

        if suppression_reason is not None and suppression_reason.strip():
            cur_supp = suppression_reason.strip()

        if status is not None and status.strip():
            cand = status.strip().upper()
            if cand not in VALID_ALERT_STATUSES:
                raise WorkflowError(f"Invalid alert status '{cand}'.")
            if cand != prev_status:
                allowed = ALERT_TRANSITIONS.get(prev_status, VALID_ALERT_STATUSES)
                if cand not in allowed:
                    raise WorkflowError(f"Illegal alert transition '{prev_status}' -> '{cand}'.")
                new_status = cand
                conn.execute("UPDATE alerts SET status = ? WHERE alert_id = ?", (new_status, alert_id))
                events.append(
                    _log_alert_event(
                        conn,
                        alert_id=alert_id,
                        actor_id=actor_id,
                        event_type="ALERT_STATUS",
                        prev_status=prev_status,
                        new_status=new_status,
                        detail=f"Status changed {prev_status} -> {new_status}"
                        + (f" ({cur_disp})" if cur_disp else "")
                        + (f" | Suppression: {cur_supp}" if cur_supp else ""),
                        now_ts=now_ts,
                    )
                )

        if note and note.strip():
            events.append(
                _log_alert_event(
                    conn,
                    alert_id=alert_id,
                    actor_id=actor_id,
                    event_type="ALERT_NOTE",
                    prev_status=new_status,
                    new_status=new_status,
                    detail=note.strip(),
                    now_ts=now_ts,
                )
            )
        elif disposition and not events:
            events.append(
                _log_alert_event(
                    conn,
                    alert_id=alert_id,
                    actor_id=actor_id,
                    event_type="ALERT_DISPOSITION",
                    prev_status=new_status,
                    new_status=new_status,
                    detail=f"Disposition set to {cur_disp}" + (f" | {cur_supp}" if cur_supp else ""),
                    now_ts=now_ts,
                )
            )

        if not events and not (suppression_reason and suppression_reason.strip()):
            raise WorkflowError("No triage update supplied.")

        conn.execute(
            """
            INSERT INTO alert_triage_meta (alert_id, owner_analyst_id, disposition, suppression_reason, sla_hours, updated_at)
            VALUES (?, ?, ?, ?, 72, ?)
            ON CONFLICT(alert_id) DO UPDATE SET
                owner_analyst_id = excluded.owner_analyst_id,
                disposition = excluded.disposition,
                suppression_reason = excluded.suppression_reason,
                updated_at = excluded.updated_at
            """,
            (alert_id, cur_owner, cur_disp, cur_supp, now_ts),
        )
        conn.commit()
        return {
            "alert_id": alert_id,
            "status": new_status,
            "owner_analyst_id": cur_owner,
            "disposition": cur_disp,
            "suppression_reason": cur_supp,
            "events": events,
        }
    finally:
        conn.close()


def bulk_triage_alerts(
    db_path: Path,
    *,
    alert_ids: list[str],
    actor_id: str,
    action: str,
    owner_analyst_id: str | None = None,
    suppression_reason: str | None = None,
    rationale: str = "",
) -> dict[str, Any]:
    """Batch acknowledge, assign, investigate, or dismiss selected alerts."""
    if not alert_ids:
        raise WorkflowError("Select at least one alert for bulk triage.")
    act = action.strip().upper()
    updated: list[str] = []
    skipped: list[dict[str, str]] = []
    for aid in alert_ids:
        try:
            if act == "ACKNOWLEDGE":
                triage_alert(db_path, alert_id=aid, actor_id=actor_id, status="ACKNOWLEDGED", note=rationale or "Bulk acknowledged")
            elif act == "UNDER_INVESTIGATION":
                triage_alert(db_path, alert_id=aid, actor_id=actor_id, status="UNDER_INVESTIGATION", note=rationale or "Bulk claimed for investigation")
            elif act == "ASSIGN":
                triage_alert(db_path, alert_id=aid, actor_id=actor_id, owner_analyst_id=owner_analyst_id or actor_id, note=rationale or None)
            elif act == "DISMISS_FP":
                triage_alert(
                    db_path,
                    alert_id=aid,
                    actor_id=actor_id,
                    status="FALSE_POSITIVE",
                    disposition="FALSE_POSITIVE",
                    suppression_reason=suppression_reason or rationale or "Bulk benign triage",
                    note=rationale or "Bulk marked false positive",
                )
            elif act == "ESCALATE":
                triage_alert(db_path, alert_id=aid, actor_id=actor_id, status="ESCALATED", disposition="TRUE_POSITIVE", note=rationale or "Bulk escalated")
            else:
                raise WorkflowError(f"Unsupported bulk alert action '{action}'.")
            updated.append(aid)
        except WorkflowError as exc:
            skipped.append({"alert_id": aid, "reason": str(exc)})
    return {"action": act, "updated_count": len(updated), "updated": updated, "skipped": skipped}


def escalate_alert_to_case(
    db_path: Path,
    *,
    alert_id: str,
    actor_id: str,
    target_case_id: str | None = None,
    rationale: str = "",
) -> dict[str, Any]:
    """Promote an alert into an existing Case or create a new investigation Case."""
    now_ts = _now_iso()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_triage_extensions_schema(conn)
        al = conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
        if not al:
            raise WorkflowError(f"Alert '{alert_id}' not found.")

        created_new = False
        case_id = target_case_id.strip() if target_case_id and target_case_id.strip() else None

        if case_id:
            ca = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
            if not ca:
                raise WorkflowError(f"Target case '{case_id}' not found.")
        else:
            existing = conn.execute(
                "SELECT case_id FROM case_alert_links WHERE alert_id = ? LIMIT 1",
                (alert_id,),
            ).fetchone()
            if existing:
                case_id = existing["case_id"]
            else:
                row = conn.execute("SELECT MAX(case_id) FROM cases WHERE case_id LIKE 'CASE-2026-%'").fetchone()
                next_num = (int(row[0].split("-")[-1]) + 1) if (row and row[0]) else 1
                case_id = f"CASE-2026-{next_num:06d}"
                score = round(min(99.0, float(al["risk_score"]) + 8.0), 2)
                tier = "CRITICAL" if score >= 80 else ("HIGH" if score >= 60 else ("MEDIUM" if score >= 40 else "LOW"))
                conn.execute(
                    """
                    INSERT INTO cases (
                        case_id, primary_account_id, primary_customer_id, linkage_summary,
                        linked_account_count, alert_count, total_exposure_amount,
                        priority_score, priority_tier, status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?, 'OPEN', ?, ?)
                    """,
                    (
                        case_id,
                        al["account_id"],
                        al["customer_id"],
                        f"ESCALATED_{al['rule_id']}",
                        float(al["trigger_total_amount"]),
                        score,
                        tier,
                        now_ts,
                        now_ts,
                    ),
                )
                created_new = True

        link_exists = conn.execute(
            "SELECT 1 FROM case_alert_links WHERE case_id = ? AND alert_id = ?",
            (case_id, alert_id),
        ).fetchone()
        if not link_exists:
            cal_row = conn.execute("SELECT MAX(case_alert_id) FROM case_alert_links WHERE case_alert_id LIKE 'CAL-2026-%'").fetchone()
            cal_num = (int(cal_row[0].split("-")[-1]) + 1) if (cal_row and cal_row[0]) else 1
            conn.execute(
                """
                INSERT INTO case_alert_links (case_alert_id, case_id, alert_id, linkage_reason, linkage_key, linked_at)
                VALUES (?, ?, ?, 'ALERT_ESCALATION', ?, ?)
                """,
                (f"CAL-2026-{cal_num:06d}", case_id, alert_id, al["account_id"], now_ts),
            )
            _recalc_case_metrics(conn, case_id, now_ts)

        prev_status = al["status"]
        conn.execute("UPDATE alerts SET status = 'ESCALATED' WHERE alert_id = ?", (alert_id,))
        _log_alert_event(
            conn,
            alert_id=alert_id,
            actor_id=actor_id,
            event_type="ALERT_ESCALATED_TO_CASE",
            prev_status=prev_status,
            new_status="ESCALATED",
            detail=f"Linked to {case_id}" + (f" — {rationale.strip()}" if rationale.strip() else ""),
            now_ts=now_ts,
        )
        conn.commit()
        return {"alert_id": alert_id, "case_id": case_id, "created_new_case": created_new, "status": "ESCALATED"}
    finally:
        conn.close()


def assign_or_override_case(
    db_path: Path,
    *,
    case_id: str,
    actor_id: str,
    actor_role: str,
    assigned_analyst_id: str | None = None,
    override_tier: str | None = None,
    override_score: float | None = None,
    override_reason: str = "",
) -> dict[str, Any]:
    """Assign case ownership and/or apply RBAC-guarded priority override."""
    now_ts = _now_iso()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_triage_extensions_schema(conn)
        ca = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not ca:
            raise WorkflowError(f"Case '{case_id}' not found.")

        meta = conn.execute("SELECT * FROM case_triage_meta WHERE case_id = ?", (case_id,)).fetchone()
        cur_assignee = meta["assigned_analyst_id"] if meta else None
        cur_tier = meta["priority_override_tier"] if meta else None
        cur_score = meta["priority_override_score"] if meta else None
        cur_reason = meta["override_reason"] if meta else None
        cur_by = meta["override_by"] if meta else None
        cur_at = meta["override_at"] if meta else None

        notes: list[str] = []
        if assigned_analyst_id is not None:
            clean_a = assigned_analyst_id.strip() or None
            if clean_a and clean_a not in ANALYST_ROLES:
                raise WorkflowError(f"Unknown analyst_id '{clean_a}'.")
            cur_assignee = clean_a
            notes.append(f"Assigned case owner -> {clean_a or 'UNASSIGNED'}")

        if override_tier is not None or override_score is not None:
            if actor_role not in {"RISK_REVIEWER", "SYSTEM_ADMIN"}:
                raise WorkflowError("Only RISK_REVIEWER or SYSTEM_ADMIN can override case priority.")
            if not override_reason.strip():
                raise WorkflowError("Priority override requires a non-empty audit reason.")
            if override_tier is not None:
                tier_u = override_tier.strip().upper()
                if tier_u not in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
                    raise WorkflowError(f"Invalid priority_tier '{override_tier}'.")
                cur_tier = tier_u
            if override_score is not None:
                sc = float(override_score)
                if sc < 0 or sc > 100:
                    raise WorkflowError("override_score must be between 0 and 100.")
                cur_score = round(sc, 2)
            cur_reason = override_reason.strip()
            cur_by = actor_id
            cur_at = now_ts
            notes.append(f"Priority override ({cur_tier or ca['priority_tier']}, {cur_score if cur_score is not None else ca['priority_score']}): {cur_reason}")

        if not notes:
            raise WorkflowError("Provide assigned_analyst_id or priority override values.")

        conn.execute(
            """
            INSERT INTO case_triage_meta (
                case_id, assigned_analyst_id, priority_override_tier, priority_override_score,
                override_reason, override_by, override_at, sla_hours
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 48)
            ON CONFLICT(case_id) DO UPDATE SET
                assigned_analyst_id = excluded.assigned_analyst_id,
                priority_override_tier = excluded.priority_override_tier,
                priority_override_score = excluded.priority_override_score,
                override_reason = excluded.override_reason,
                override_by = excluded.override_by,
                override_at = excluded.override_at
            """,
            (case_id, cur_assignee, cur_tier, cur_score, cur_reason, cur_by, cur_at),
        )
        conn.commit()
    finally:
        conn.close()

    submit_analyst_action(
        db_path,
        case_id=case_id,
        analyst_id=actor_id if actor_id in ANALYST_ROLES else "ANL-003",
        action_type="ADD_NOTE",
        rationale=" | ".join(notes),
    )
    return {
        "case_id": case_id,
        "assigned_analyst_id": cur_assignee,
        "priority_override_tier": cur_tier,
        "priority_override_score": cur_score,
        "override_reason": cur_reason,
    }


def link_or_unlink_case_alert(
    db_path: Path,
    *,
    case_id: str,
    alert_id: str,
    actor_id: str,
    mode: str = "link",
    linkage_reason: str = "MANUAL_ANALYST_LINK",
    rationale: str = "",
) -> dict[str, Any]:
    """Attach or detach an Alert from a Case while preserving >=1 alert invariant."""
    now_ts = _now_iso()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_triage_extensions_schema(conn)
        ca = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        al = conn.execute("SELECT * FROM alerts WHERE alert_id = ?", (alert_id,)).fetchone()
        if not ca:
            raise WorkflowError(f"Case '{case_id}' not found.")
        if not al:
            raise WorkflowError(f"Alert '{alert_id}' not found.")

        mode_l = mode.strip().lower()
        existing = conn.execute(
            "SELECT case_alert_id FROM case_alert_links WHERE case_id = ? AND alert_id = ?",
            (case_id, alert_id),
        ).fetchone()

        if mode_l == "link":
            if existing:
                raise WorkflowError(f"Alert '{alert_id}' is already linked to '{case_id}'.")
            cal_row = conn.execute("SELECT MAX(case_alert_id) FROM case_alert_links WHERE case_alert_id LIKE 'CAL-2026-%'").fetchone()
            cal_num = (int(cal_row[0].split("-")[-1]) + 1) if (cal_row and cal_row[0]) else 1
            conn.execute(
                """
                INSERT INTO case_alert_links (case_alert_id, case_id, alert_id, linkage_reason, linkage_key, linked_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (f"CAL-2026-{cal_num:06d}", case_id, alert_id, linkage_reason or "MANUAL_ANALYST_LINK", al["account_id"], now_ts),
            )
            if al["status"] == "OPEN":
                conn.execute("UPDATE alerts SET status = 'GROUPED' WHERE alert_id = ?", (alert_id,))
            _log_alert_event(
                conn,
                alert_id=alert_id,
                actor_id=actor_id,
                event_type="LINKED_TO_CASE",
                prev_status=al["status"],
                new_status="GROUPED" if al["status"] == "OPEN" else al["status"],
                detail=f"Linked to {case_id}" + (f": {rationale.strip()}" if rationale.strip() else ""),
                now_ts=now_ts,
            )
            audit_note = f"Linked alert {alert_id} ({linkage_reason}). {rationale.strip()}".strip()
        elif mode_l == "unlink":
            if not existing:
                raise WorkflowError(f"Alert '{alert_id}' is not linked to '{case_id}'.")
            cnt_row = conn.execute("SELECT COUNT(*) FROM case_alert_links WHERE case_id = ?", (case_id,)).fetchone()
            if int(cnt_row[0]) <= 1:
                raise WorkflowError("Cannot unlink the final remaining alert from a case.")
            conn.execute("DELETE FROM case_alert_links WHERE case_id = ? AND alert_id = ?", (case_id, alert_id))
            _log_alert_event(
                conn,
                alert_id=alert_id,
                actor_id=actor_id,
                event_type="UNLINKED_FROM_CASE",
                prev_status=al["status"],
                new_status=al["status"],
                detail=f"Unlinked from {case_id}" + (f": {rationale.strip()}" if rationale.strip() else ""),
                now_ts=now_ts,
            )
            audit_note = f"Unlinked alert {alert_id}. {rationale.strip()}".strip()
        else:
            raise WorkflowError(f"Unsupported mode '{mode}'.")

        _recalc_case_metrics(conn, case_id, now_ts)
        updated_case = dict(conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone())
        conn.commit()
    finally:
        conn.close()

    submit_analyst_action(
        db_path,
        case_id=case_id,
        analyst_id=actor_id if actor_id in ANALYST_ROLES else "ANL-003",
        action_type="ADD_NOTE",
        rationale=audit_note,
    )
    return {"case_id": case_id, "alert_id": alert_id, "mode": mode_l, "case": updated_case}


def bulk_triage_cases(
    db_path: Path,
    *,
    case_ids: list[str],
    actor_id: str,
    actor_role: str,
    action: str,
    assigned_analyst_id: str | None = None,
    rationale: str = "",
) -> dict[str, Any]:
    """Batch claim, escalate, or assign selected cases in the triage queue."""
    if not case_ids:
        raise WorkflowError("Select at least one case for bulk queue action.")
    act = action.strip().upper()
    updated: list[str] = []
    skipped: list[dict[str, str]] = []
    safe_actor = actor_id if actor_id in ANALYST_ROLES else "ANL-003"
    for cid in case_ids:
        try:
            if act == "ASSIGN":
                assign_or_override_case(
                    db_path,
                    case_id=cid,
                    actor_id=safe_actor,
                    actor_role=actor_role,
                    assigned_analyst_id=assigned_analyst_id or safe_actor,
                )
            elif act in {"CLAIM_REVIEW", "ESCALATE"}:
                submit_analyst_action(
                    db_path,
                    case_id=cid,
                    analyst_id=safe_actor,
                    action_type=act,
                    rationale=rationale.strip() or f"Bulk queue action: {act}",
                )
            else:
                raise WorkflowError(f"Unsupported bulk case action '{action}'.")
            updated.append(cid)
        except WorkflowError as exc:
            skipped.append({"case_id": cid, "reason": str(exc)})
    return {"action": act, "updated_count": len(updated), "updated": updated, "skipped": skipped}


def update_case_checklist(
    db_path: Path,
    *,
    case_id: str,
    actor_id: str,
    rules_reviewed: bool | None = None,
    ledger_reconciled: bool | None = None,
    network_verified: bool | None = None,
    kyc_corroborated: bool | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Persist structured Dossier evidence checklist completion state."""
    now_ts = _now_iso()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_triage_extensions_schema(conn)
        if not conn.execute("SELECT 1 FROM cases WHERE case_id = ?", (case_id,)).fetchone():
            raise WorkflowError(f"Case '{case_id}' not found.")
        cur = conn.execute("SELECT * FROM case_evidence_checklist WHERE case_id = ?", (case_id,)).fetchone()
        state = {
            "rules_reviewed": int(bool(rules_reviewed)) if rules_reviewed is not None else (int(cur["rules_reviewed"]) if cur else 0),
            "ledger_reconciled": int(bool(ledger_reconciled)) if ledger_reconciled is not None else (int(cur["ledger_reconciled"]) if cur else 0),
            "network_verified": int(bool(network_verified)) if network_verified is not None else (int(cur["network_verified"]) if cur else 0),
            "kyc_corroborated": int(bool(kyc_corroborated)) if kyc_corroborated is not None else (int(cur["kyc_corroborated"]) if cur else 0),
            "notes": notes.strip() if notes is not None else (cur["notes"] if cur else ""),
        }
        conn.execute(
            """
            INSERT INTO case_evidence_checklist (
                case_id, rules_reviewed, ledger_reconciled, network_verified, kyc_corroborated, notes, updated_by, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                rules_reviewed = excluded.rules_reviewed,
                ledger_reconciled = excluded.ledger_reconciled,
                network_verified = excluded.network_verified,
                kyc_corroborated = excluded.kyc_corroborated,
                notes = excluded.notes,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (
                case_id,
                state["rules_reviewed"],
                state["ledger_reconciled"],
                state["network_verified"],
                state["kyc_corroborated"],
                state["notes"],
                actor_id,
                now_ts,
            ),
        )
        conn.commit()
        return {
            "case_id": case_id,
            "rules_reviewed": bool(state["rules_reviewed"]),
            "ledger_reconciled": bool(state["ledger_reconciled"]),
            "network_verified": bool(state["network_verified"]),
            "kyc_corroborated": bool(state["kyc_corroborated"]),
            "notes": state["notes"] or "",
            "updated_by": actor_id,
            "updated_at": now_ts,
        }
    finally:
        conn.close()


def generate_or_save_sar_draft(
    dossier: dict[str, Any],
    db_path: Path,
    *,
    case_id: str,
    actor_id: str,
    custom_narrative: str | None = None,
) -> dict[str, Any]:
    """Generate structured SAR compliance narrative from live dossier or save analyst edits."""
    now_ts = _now_iso()
    if custom_narrative is not None and custom_narrative.strip():
        narrative = custom_narrative.strip()
    else:
        c = dossier["case"]
        cust_lines = ", ".join(f"{cu['full_name']} ({cu['customer_id']}, KYC {cu['kyc_tier']})" for cu in dossier["customers"][:5])
        acct_lines = ", ".join(f"{a['account_id']} ({a['status']})" for a in dossier["accounts"][:6])
        rule_lines = "\n".join(
            f"- {al['alert_id']} [{al['rule_id']} • {al['severity']} • {al['risk_score']:.1f}]: {al['explanation_summary']}"
            for al in dossier["alerts"][:8]
        )
        txns = dossier["transactions"]
        window = f"{txns[-1]['occurred_at']} to {txns[0]['occurred_at']}" if txns else c["created_at"]
        narrative = (
            f"SUSPICIOUS ACTIVITY REPORT (SAR) DRAFT — {c['case_id']}\n"
            f"Generated By: {actor_id} | Generated At: {now_ts}\n"
            f"Priority Tier: {c['priority_tier']} (Score {c['priority_score']:.2f}) | Linkage: {c['linkage_summary']}\n"
            f"Total Observed Exposure: ${float(c['total_exposure_amount']):,.2f} across {c['linked_account_count']} account(s) and {c['alert_count']} alert(s)\n"
            f"Activity Window: {window}\n\n"
            f"1. SUBJECT(S) & LINKED ACCOUNTS\n"
            f"Subjects: {cust_lines or c['primary_customer_id']}\n"
            f"Accounts: {acct_lines or c['primary_account_id']}\n\n"
            f"2. DETECTED BEHAVIORAL INDICATORS\n"
            f"{rule_lines}\n\n"
            f"3. ANALYST ASSESSMENT & DISPOSITION RECOMMENDATION\n"
            f"Automated rule correlation and entity-graph linkage identified anomalous fund movement inconsistent with expected customer baseline. "
            f"Pending compliance reviewer verification and FinCEN BSA filing sign-off."
        )

    conn = sqlite3.connect(db_path)
    try:
        ensure_triage_extensions_schema(conn)
        conn.execute(
            """
            INSERT INTO case_triage_meta (case_id, sla_hours, sar_draft, sar_updated_at)
            VALUES (?, 48, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                sar_draft = excluded.sar_draft,
                sar_updated_at = excluded.sar_updated_at
            """,
            (case_id, narrative, now_ts),
        )
        conn.commit()
    finally:
        conn.close()
    return {"case_id": case_id, "sar_draft": narrative, "sar_updated_at": now_ts}


def manage_watchlist_tag(
    db_path: Path,
    *,
    entity_type: str,
    entity_id: str,
    tag: str,
    note: str = "",
    actor_id: str,
    remove: bool = False,
) -> dict[str, Any]:
    """Attach or remove a cross-entity compliance watchlist tag on a Customer or Account."""
    et = entity_type.strip().upper()
    if et not in {"CUSTOMER", "ACCOUNT"}:
        raise WorkflowError("entity_type must be CUSTOMER or ACCOUNT.")
    tg = tag.strip().upper()
    if tg not in WATCHLIST_TAGS:
        raise WorkflowError(f"Unsupported watchlist tag '{tag}'. Allowed: {sorted(WATCHLIST_TAGS)}")

    now_ts = _now_iso()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        ensure_triage_extensions_schema(conn)
        if remove:
            conn.execute(
                "DELETE FROM entity_watchlist_tags WHERE entity_type = ? AND entity_id = ? AND tag = ?",
                (et, entity_id, tg),
            )
        else:
            conn.execute(
                """
                INSERT INTO entity_watchlist_tags (tag_id, entity_type, entity_id, tag, note, actor_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_type, entity_id, tag) DO UPDATE SET
                    note = excluded.note,
                    actor_id = excluded.actor_id,
                    created_at = excluded.created_at
                """,
                (_new_id("TAG"), et, entity_id, tg, note.strip(), actor_id, now_ts),
            )
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM entity_watchlist_tags WHERE entity_type = ? AND entity_id = ? ORDER BY created_at DESC",
                (et, entity_id),
            ).fetchall()
        ]
        conn.commit()
        return {"entity_type": et, "entity_id": entity_id, "tags": rows}
    finally:
        conn.close()

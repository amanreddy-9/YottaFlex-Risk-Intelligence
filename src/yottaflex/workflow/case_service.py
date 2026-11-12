"""Immutable analyst disposition workflow backed by SQLite.

Enforces legal Case lifecycle transitions and temporal invariants
(dispositions must never precede linked alert creation timestamps),
appending AnalystAction and CaseStateEvent records without overwriting history.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTION_TO_STATUS: dict[str, str | None] = {
    "CLAIM_REVIEW": "IN_REVIEW",
    "ESCALATE": "ESCALATED",
    "FILE_SAR": "SAR_FILED",
    "CONFIRM_FRAUD": "CLOSED_CONFIRMED_FRAUD",
    "MARK_FALSE_POSITIVE": "CLOSED_FALSE_POSITIVE",
    "REOPEN_CASE": "IN_REVIEW",
    "ADD_NOTE": None,
}

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "OPEN": {"IN_REVIEW", "ESCALATED", "SAR_FILED", "CLOSED_CONFIRMED_FRAUD", "CLOSED_FALSE_POSITIVE"},
    "IN_REVIEW": {"ESCALATED", "SAR_FILED", "CLOSED_CONFIRMED_FRAUD", "CLOSED_FALSE_POSITIVE"},
    "ESCALATED": {"SAR_FILED", "CLOSED_CONFIRMED_FRAUD", "CLOSED_FALSE_POSITIVE"},
    "SAR_FILED": {"IN_REVIEW"},
    "CLOSED_CONFIRMED_FRAUD": {"IN_REVIEW"},
    "CLOSED_FALSE_POSITIVE": {"IN_REVIEW"},
}

ANALYST_ROLES: dict[str, str] = {
    "ANL-001": "OPS_ANALYST",
    "ANL-002": "OPS_ANALYST",
    "ANL-003": "RISK_REVIEWER",
    "ANL-004": "COMPLIANCE_OFFICER",
    "ADM-001": "SYSTEM_ADMIN",
}


class WorkflowError(ValueError):
    """Raised when an analyst action violates workflow or temporal invariants."""


def _parse_dt(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


def _next_seq_id(conn: sqlite3.Connection, table: str, id_col: str, prefix: str) -> str:
    row = conn.execute(f"SELECT MAX({id_col}) FROM {table} WHERE {id_col} LIKE ?", (f"{prefix}%",)).fetchone()
    max_id = row[0] if row and row[0] else None
    if not max_id:
        return f"{prefix}000001"
    num = int(max_id.split("-")[-1]) + 1
    return f"{prefix}{num:06d}"


def submit_analyst_action(
    db_path: Path,
    *,
    case_id: str,
    analyst_id: str,
    action_type: str,
    rationale: str,
    acted_at: str | None = None,
) -> dict[str, Any]:
    """Validate and persist an immutable AnalystAction (+ CaseStateEvent if status changes)."""
    if action_type not in ACTION_TO_STATUS:
        raise WorkflowError(f"Unsupported action_type '{action_type}'.")
    if not rationale or not rationale.strip():
        raise WorkflowError("Rationale must be a non-empty audit justification.")
    if analyst_id not in ANALYST_ROLES:
        raise WorkflowError(f"Unknown analyst_id '{analyst_id}'.")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        case_row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        if not case_row:
            raise WorkflowError(f"Case '{case_id}' not found.")

        current_status = case_row["status"]
        target_status = ACTION_TO_STATUS[action_type]

        if target_status is not None:
            if target_status == current_status:
                raise WorkflowError(f"Case '{case_id}' is already in status '{current_status}'.")
            if target_status not in ALLOWED_TRANSITIONS.get(current_status, set()):
                raise WorkflowError(
                    f"Illegal transition from '{current_status}' to '{target_status}' via '{action_type}'."
                )

        # Determine valid timestamp (must be >= max linked alert created_at and >= latest event)
        alert_max_row = conn.execute(
            """
            SELECT MAX(a.created_at) AS max_alert_ts
            FROM alerts a
            JOIN case_alert_links cal ON cal.alert_id = a.alert_id
            WHERE cal.case_id = ?
            """,
            (case_id,),
        ).fetchone()
        max_alert_ts = alert_max_row["max_alert_ts"] if alert_max_row else None

        ev_max_row = conn.execute(
            "SELECT MAX(effective_at) AS max_ev_ts FROM case_state_events WHERE case_id = ?",
            (case_id,),
        ).fetchone()
        max_ev_ts = ev_max_row["max_ev_ts"] if ev_max_row else None

        if acted_at is None:
            # Anchor deterministically after latest existing event / alert
            anchors = [_parse_dt(t) for t in (max_alert_ts, max_ev_ts) if t]
            base_dt = max(anchors) if anchors else datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            chosen_dt = now_dt if now_dt > base_dt else base_dt
            if chosen_dt <= base_dt:
                from datetime import timedelta
                chosen_dt = base_dt + timedelta(minutes=1)
            acted_at = chosen_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            acted_dt = _parse_dt(acted_at)
            if max_alert_ts and acted_dt < _parse_dt(max_alert_ts):
                raise WorkflowError(
                    f"Temporal invariant violated: disposition {acted_at} precedes alert creation {max_alert_ts}."
                )
            if max_ev_ts and acted_dt < _parse_dt(max_ev_ts):
                raise WorkflowError(
                    f"Temporal invariant violated: action {acted_at} precedes latest case event {max_ev_ts}."
                )

        action_id = _next_seq_id(conn, "analyst_actions", "action_id", "ACT-2026-")
        analyst_role = ANALYST_ROLES[analyst_id]

        conn.execute(
            """
            INSERT INTO analyst_actions (action_id, case_id, analyst_id, analyst_role, action_type, rationale, acted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (action_id, case_id, analyst_id, analyst_role, action_type, rationale.strip(), acted_at),
        )

        case_event = None
        if target_status is not None:
            cse_id = _next_seq_id(conn, "case_state_events", "case_event_id", "CSE-2026-")
            conn.execute(
                """
                INSERT INTO case_state_events (case_event_id, case_id, prev_status, new_status, analyst_action_id, effective_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (cse_id, case_id, current_status, target_status, action_id, acted_at),
            )
            conn.execute(
                "UPDATE cases SET status = ?, updated_at = ? WHERE case_id = ?",
                (target_status, acted_at, case_id),
            )
            if target_status == "CLOSED_FALSE_POSITIVE":
                conn.execute(
                    """
                    UPDATE alerts SET status = 'DISMISSED'
                    WHERE alert_id IN (SELECT alert_id FROM case_alert_links WHERE case_id = ?)
                    """,
                    (case_id,),
                )
            elif target_status == "CLOSED_CONFIRMED_FRAUD":
                conn.execute(
                    """
                    UPDATE alerts SET status = 'RESOLVED'
                    WHERE alert_id IN (SELECT alert_id FROM case_alert_links WHERE case_id = ?)
                    """,
                    (case_id,),
                )
            case_event = {
                "case_event_id": cse_id,
                "case_id": case_id,
                "prev_status": current_status,
                "new_status": target_status,
                "analyst_action_id": action_id,
                "effective_at": acted_at,
            }

        conn.commit()
        return {
            "action": {
                "action_id": action_id,
                "case_id": case_id,
                "analyst_id": analyst_id,
                "analyst_role": analyst_role,
                "action_type": action_type,
                "rationale": rationale.strip(),
                "acted_at": acted_at,
            },
            "case_state_event": case_event,
            "new_status": target_status or current_status,
        }
    finally:
        conn.close()

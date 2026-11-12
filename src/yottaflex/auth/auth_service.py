"""SQLite-backed authentication, RBAC permissions, password reset, and login history."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROLE_PERMISSIONS: dict[str, list[str]] = {
    "OPS_ANALYST": [
        "view_dashboard",
        "view_customers",
        "view_accounts",
        "view_transactions",
        "triage_alerts",
        "investigate_cases",
        "submit_disposition",
        "export_reports",
    ],
    "RISK_REVIEWER": [
        "view_dashboard",
        "view_customers",
        "view_accounts",
        "view_transactions",
        "review_escalations",
        "approve_dispositions",
        "file_sar",
        "reopen_closed_cases",
        "export_reports",
    ],
    "SYSTEM_ADMIN": [
        "view_dashboard",
        "view_customers",
        "view_accounts",
        "view_transactions",
        "manage_users",
        "configure_risk_rules",
        "run_data_generation",
        "run_validation",
        "view_audit_logs",
        "export_reports",
    ],
}

DEFAULT_USERS = [
    ("USR-001", "analyst@yottaflex.com", "Priya Nair", "OPS_ANALYST", "ANL-001", "Financial Crime Operations", "Senior AML Analyst", "+1-212-555-0141", "YottaFlex#2026"),
    ("USR-002", "reviewer@yottaflex.com", "Marcus Vance", "RISK_REVIEWER", "ANL-003", "Compliance & Risk Oversight", "VP Compliance Reviewer", "+1-212-555-0188", "YottaFlex#2026"),
    ("USR-003", "admin@yottaflex.com", "Elena Rostova", "SYSTEM_ADMIN", "ADM-001", "Platform Engineering & Governance", "Principal Risk Architect", "+1-212-555-0199", "YottaFlex#2026"),
]


class AuthError(ValueError):
    """Raised on authentication, authorization, or reset failures."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash_password(password: str, salt: str | None = None) -> str:
    use_salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), use_salt.encode("utf-8"), 120_000).hex()
    return f"pbkdf2_sha256${use_salt}${dk}"


def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        _, salt, expected_dk = stored_hash.split("$", 2)
    except ValueError:
        return False
    computed = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000).hex()
    return hmac.compare_digest(computed, expected_dk)


def ensure_auth_schema(db_path: Path) -> None:
    """Create auth tables if missing and seed default role accounts."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                user_id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                full_name TEXT NOT NULL,
                role TEXT NOT NULL,
                analyst_code TEXT NOT NULL,
                department TEXT NOT NULL,
                title TEXT NOT NULL,
                phone TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
                session_id TEXT PRIMARY KEY,
                token_hash TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                client_ip TEXT NOT NULL,
                user_agent TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES app_users(user_id)
            );
            CREATE TABLE IF NOT EXISTS login_history (
                log_id TEXT PRIMARY KEY,
                user_id TEXT,
                email TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                client_ip TEXT NOT NULL,
                user_agent TEXT NOT NULL,
                detail TEXT NOT NULL,
                occurred_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                reset_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                reset_code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES app_users(user_id)
            );
            """
        )
        now = _now_iso()
        for uid, email, name, role, acode, dept, title, phone, raw_pw in DEFAULT_USERS:
            exists = conn.execute("SELECT 1 FROM app_users WHERE user_id = ?", (uid,)).fetchone()
            if not exists:
                # Deterministic salt for initial seeded accounts so tests stay clean
                salt = hashlib.sha256(f"yottaflex-salt-{uid}".encode()).hexdigest()[:32]
                pw_hash = _hash_password(raw_pw, salt=salt)
                conn.execute(
                    """
                    INSERT INTO app_users (user_id, email, full_name, role, analyst_code, department, title, phone, password_hash, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (uid, email, name, role, acode, dept, title, phone, pw_hash, now, now),
                )
        conn.commit()
    finally:
        conn.close()


def _sanitize_user(row: sqlite3.Row) -> dict[str, Any]:
    role = row["role"]
    return {
        "user_id": row["user_id"],
        "email": row["email"],
        "full_name": row["full_name"],
        "role": role,
        "analyst_code": row["analyst_code"],
        "department": row["department"],
        "title": row["title"],
        "phone": row["phone"],
        "is_active": bool(row["is_active"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "permissions": ROLE_PERMISSIONS.get(role, []),
    }


def _log_auth_event(
    conn: sqlite3.Connection,
    *,
    user_id: str | None,
    email: str,
    event_type: str,
    status: str,
    client_ip: str,
    user_agent: str,
    detail: str,
) -> None:
    log_id = f"LOG-{secrets.token_hex(6).upper()}"
    conn.execute(
        """
        INSERT INTO login_history (log_id, user_id, email, event_type, status, client_ip, user_agent, detail, occurred_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (log_id, user_id, email, event_type, status, client_ip, user_agent, detail, _now_iso()),
    )


def login_user(
    db_path: Path,
    *,
    email: str,
    password: str,
    client_ip: str = "127.0.0.1",
    user_agent: str = "YottaFlex-Web",
) -> dict[str, Any]:
    ensure_auth_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM app_users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
        if not row or not row["is_active"] or not _verify_password(password, row["password_hash"]):
            _log_auth_event(
                conn,
                user_id=row["user_id"] if row else None,
                email=email.strip(),
                event_type="LOGIN",
                status="FAILED",
                client_ip=client_ip,
                user_agent=user_agent,
                detail="Invalid credentials or inactive account",
            )
            conn.commit()
            raise AuthError("Invalid email or password.")

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        session_id = f"SES-{secrets.token_hex(6).upper()}"
        now_dt = datetime.now(timezone.utc)
        exp_dt = now_dt + timedelta(hours=12)

        conn.execute(
            """
            INSERT INTO auth_sessions (session_id, token_hash, user_id, client_ip, user_agent, created_at, expires_at, revoked)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                session_id,
                token_hash,
                row["user_id"],
                client_ip,
                user_agent[:120],
                now_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            ),
        )
        _log_auth_event(
            conn,
            user_id=row["user_id"],
            email=row["email"],
            event_type="LOGIN",
            status="SUCCESS",
            client_ip=client_ip,
            user_agent=user_agent[:120],
            detail=f"Authenticated as {row['role']} (session {session_id})",
        )
        conn.commit()
        return {
            "token": raw_token,
            "session_id": session_id,
            "expires_at": exp_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "user": _sanitize_user(row),
        }
    finally:
        conn.close()


def get_session_user(db_path: Path, token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    ensure_auth_schema(db_path)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT u.*, s.session_id, s.expires_at, s.revoked
            FROM auth_sessions s
            JOIN app_users u ON u.user_id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if not row or row["revoked"] or not row["is_active"]:
            return None
        exp = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
        if exp < datetime.now(timezone.utc):
            return None
        user = _sanitize_user(row)
        user["current_session_id"] = row["session_id"]
        return user
    finally:
        conn.close()


def logout_session(db_path: Path, token: str, client_ip: str = "127.0.0.1", user_agent: str = "YottaFlex-Web") -> None:
    ensure_auth_schema(db_path)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            """
            SELECT s.session_id, u.user_id, u.email
            FROM auth_sessions s JOIN app_users u ON u.user_id = s.user_id
            WHERE s.token_hash = ?
            """,
            (token_hash,),
        ).fetchone()
        if row:
            conn.execute("UPDATE auth_sessions SET revoked = 1 WHERE session_id = ?", (row["session_id"],))
            _log_auth_event(
                conn,
                user_id=row["user_id"],
                email=row["email"],
                event_type="LOGOUT",
                status="SUCCESS",
                client_ip=client_ip,
                user_agent=user_agent[:120],
                detail=f"Signed out session {row['session_id']}",
            )
            conn.commit()
    finally:
        conn.close()


def request_password_reset(db_path: Path, email: str, client_ip: str = "127.0.0.1") -> dict[str, Any]:
    ensure_auth_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM app_users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
        if not row:
            raise AuthError(f"No user registered for '{email}'.")
        code = f"{secrets.randbelow(900000) + 100000}"
        reset_id = f"RST-{secrets.token_hex(5).upper()}"
        exp = (datetime.now(timezone.utc) + timedelta(minutes=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT INTO password_reset_tokens (reset_id, user_id, reset_code, expires_at, used) VALUES (?, ?, ?, ?, 0)",
            (reset_id, row["user_id"], code, exp),
        )
        _log_auth_event(
            conn,
            user_id=row["user_id"],
            email=row["email"],
            event_type="PASSWORD_RESET_REQUEST",
            status="SUCCESS",
            client_ip=client_ip,
            user_agent="YottaFlex-Auth",
            detail=f"Issued 15m reset code ({reset_id})",
        )
        conn.commit()
        return {
            "reset_id": reset_id,
            "email": row["email"],
            "expires_at": exp,
            "demo_reset_code": code,
        }
    finally:
        conn.close()


def confirm_password_reset(
    db_path: Path, *, email: str, reset_code: str, new_password: str, client_ip: str = "127.0.0.1"
) -> dict[str, Any]:
    if len(new_password) < 8:
        raise AuthError("New password must be at least 8 characters.")
    ensure_auth_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM app_users WHERE LOWER(email) = LOWER(?)", (email.strip(),)).fetchone()
        if not row:
            raise AuthError("Account not found.")
        tok = conn.execute(
            """
            SELECT * FROM password_reset_tokens
            WHERE user_id = ? AND reset_code = ? AND used = 0
            ORDER BY expires_at DESC LIMIT 1
            """,
            (row["user_id"], reset_code.strip()),
        ).fetchone()
        if not tok:
            raise AuthError("Invalid or already used reset code.")
        if datetime.fromisoformat(tok["expires_at"].replace("Z", "+00:00")) < datetime.now(timezone.utc):
            raise AuthError("Reset code has expired.")

        new_hash = _hash_password(new_password)
        now = _now_iso()
        conn.execute("UPDATE app_users SET password_hash = ?, updated_at = ? WHERE user_id = ?", (new_hash, now, row["user_id"]))
        conn.execute("UPDATE password_reset_tokens SET used = 1 WHERE reset_id = ?", (tok["reset_id"],))
        conn.execute("UPDATE auth_sessions SET revoked = 1 WHERE user_id = ?", (row["user_id"],))
        _log_auth_event(
            conn,
            user_id=row["user_id"],
            email=row["email"],
            event_type="PASSWORD_RESET",
            status="SUCCESS",
            client_ip=client_ip,
            user_agent="YottaFlex-Auth",
            detail="Password updated and prior sessions revoked",
        )
        conn.commit()
        return {"email": row["email"], "status": "PASSWORD_UPDATED"}
    finally:
        conn.close()


def update_profile(
    db_path: Path, *, user_id: str, full_name: str, phone: str, department: str, title: str
) -> dict[str, Any]:
    if not full_name.strip():
        raise AuthError("Full name cannot be empty.")
    ensure_auth_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        now = _now_iso()
        conn.execute(
            """
            UPDATE app_users
            SET full_name = ?, phone = ?, department = ?, title = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (full_name.strip(), phone.strip(), department.strip(), title.strip(), now, user_id),
        )
        _log_auth_event(
            conn,
            user_id=user_id,
            email=conn.execute("SELECT email FROM app_users WHERE user_id = ?", (user_id,)).fetchone()["email"],
            event_type="PROFILE_UPDATE",
            status="SUCCESS",
            client_ip="127.0.0.1",
            user_agent="YottaFlex-Web",
            detail="Updated personal profile metadata",
        )
        conn.commit()
        row = conn.execute("SELECT * FROM app_users WHERE user_id = ?", (user_id,)).fetchone()
        return _sanitize_user(row)
    finally:
        conn.close()


def list_sessions_and_history(db_path: Path, user_id: str, include_all: bool = False) -> dict[str, Any]:
    ensure_auth_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if include_all:
            sessions = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT s.session_id, s.user_id, u.email, u.role, s.client_ip, s.user_agent, s.created_at, s.expires_at, s.revoked
                    FROM auth_sessions s JOIN app_users u ON u.user_id = s.user_id
                    ORDER BY s.created_at DESC LIMIT 40
                    """
                ).fetchall()
            ]
            history = [
                dict(r)
                for r in conn.execute("SELECT * FROM login_history ORDER BY occurred_at DESC LIMIT 60").fetchall()
            ]
        else:
            sessions = [
                dict(r)
                for r in conn.execute(
                    """
                    SELECT s.session_id, s.user_id, u.email, u.role, s.client_ip, s.user_agent, s.created_at, s.expires_at, s.revoked
                    FROM auth_sessions s JOIN app_users u ON u.user_id = s.user_id
                    WHERE s.user_id = ?
                    ORDER BY s.created_at DESC LIMIT 25
                    """,
                    (user_id,),
                ).fetchall()
            ]
            history = [
                dict(r)
                for r in conn.execute(
                    "SELECT * FROM login_history WHERE user_id = ? ORDER BY occurred_at DESC LIMIT 40",
                    (user_id,),
                ).fetchall()
            ]
        return {"sessions": sessions, "login_history": history}
    finally:
        conn.close()


def revoke_user_session(db_path: Path, *, user_id: str, session_id: str, is_admin: bool = False) -> None:
    ensure_auth_schema(db_path)
    conn = sqlite3.connect(db_path)
    try:
        if is_admin:
            conn.execute("UPDATE auth_sessions SET revoked = 1 WHERE session_id = ?", (session_id,))
        else:
            conn.execute("UPDATE auth_sessions SET revoked = 1 WHERE session_id = ? AND user_id = ?", (session_id, user_id))
        conn.commit()
    finally:
        conn.close()


def list_admin_users(db_path: Path) -> list[dict[str, Any]]:
    """Return all workbench users with active session counts and last login timestamps."""
    ensure_auth_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT u.*,
                   (SELECT COUNT(*) FROM auth_sessions s WHERE s.user_id = u.user_id AND s.revoked = 0) AS active_sessions,
                   (SELECT MAX(lh.occurred_at) FROM login_history lh WHERE lh.user_id = u.user_id AND lh.status = 'SUCCESS') AS last_login_at
            FROM app_users u
            ORDER BY CASE u.role WHEN 'SYSTEM_ADMIN' THEN 1 WHEN 'RISK_REVIEWER' THEN 2 ELSE 3 END, u.user_id
            """
        ).fetchall()
        out: list[dict[str, Any]] = []
        for r in rows:
            item = _sanitize_user(r)
            item["active_sessions"] = int(r["active_sessions"] or 0)
            item["last_login_at"] = r["last_login_at"]
            out.append(item)
        return out
    finally:
        conn.close()


def update_admin_user(
    db_path: Path,
    *,
    actor_user_id: str,
    target_user_id: str,
    role: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any]:
    """Allow SYSTEM_ADMIN to update a user's RBAC role or active lock state with audit log."""
    ensure_auth_schema(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM app_users WHERE user_id = ?", (target_user_id,)).fetchone()
        if not row:
            raise AuthError(f"User {target_user_id} not found")
        if target_user_id == actor_user_id and is_active is False:
            raise AuthError("Administrators cannot deactivate their own active account")
        if target_user_id == actor_user_id and role is not None and role != row["role"]:
            raise AuthError("Administrators cannot change their own active role")

        next_role = str(role).upper() if role is not None else row["role"]
        if next_role not in ROLE_PERMISSIONS:
            raise AuthError(f"Unsupported role '{next_role}'. Choose OPS_ANALYST, RISK_REVIEWER, or SYSTEM_ADMIN.")
        next_active = int(bool(is_active)) if is_active is not None else int(row["is_active"])
        now = _now_iso()

        conn.execute(
            "UPDATE app_users SET role = ?, is_active = ?, updated_at = ? WHERE user_id = ?",
            (next_role, next_active, now, target_user_id),
        )
        if next_active == 0:
            conn.execute("UPDATE auth_sessions SET revoked = 1 WHERE user_id = ?", (target_user_id,))
        _log_auth_event(
            conn,
            user_id=target_user_id,
            email=row["email"],
            event_type="ADMIN_ROLE_UPDATE",
            status="SUCCESS",
            client_ip="127.0.0.1",
            user_agent="YottaFlex-Governance",
            detail=f"Updated by {actor_user_id}: role={next_role}, is_active={bool(next_active)}",
        )
        conn.commit()
        updated = conn.execute("SELECT * FROM app_users WHERE user_id = ?", (target_user_id,)).fetchone()
        return _sanitize_user(updated)
    finally:
        conn.close()

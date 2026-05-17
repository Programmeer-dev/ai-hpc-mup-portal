"""In-app notifikacije + opciono e-mail slanje preko SMTP.

Tabela `notifications` se kreira lazy-no kad je potrebno.
E-mail slanje je omogućeno samo ako su definisani SMTP env vari:
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM
"""

from __future__ import annotations

import logging
import os
import smtplib
import sqlite3
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional


BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "mup_data.db"

logger = logging.getLogger("dms_portal.notifications")


def _get_conn() -> sqlite3.Connection:
    return sqlite3.connect(str(DB_PATH))


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            request_id INTEGER,
            title TEXT NOT NULL,
            body TEXT,
            created_at TEXT NOT NULL,
            read_at TEXT
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_notifications_username_read "
        "ON notifications(username, read_at)"
    )
    conn.commit()


def notify(
    username: str,
    title: str,
    body: str = "",
    request_id: Optional[int] = None,
    email: Optional[str] = None,
) -> int:
    """Kreira in-app notifikaciju i opcioni e-mail.

    Vraća id notifikacije; -1 ako username nedostaje.
    """
    if not username:
        return -1

    conn = _get_conn()
    try:
        _ensure_table(conn)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO notifications (username, request_id, title, body, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, request_id, title, body, datetime.now().isoformat()),
        )
        notification_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    if email:
        _try_send_email(email, title, body)

    return notification_id


def list_notifications(username: str, only_unread: bool = False, limit: int = 30) -> List[dict]:
    if not username:
        return []

    conn = _get_conn()
    try:
        _ensure_table(conn)
        cur = conn.cursor()
        query = (
            "SELECT id, request_id, title, body, created_at, read_at "
            "FROM notifications WHERE username = ?"
        )
        params = [username]
        if only_unread:
            query += " AND read_at IS NULL"
        query += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        rows = cur.execute(query, params).fetchall()
    finally:
        conn.close()

    return [
        {
            "id": row[0],
            "request_id": row[1],
            "title": row[2],
            "body": row[3],
            "created_at": row[4],
            "read_at": row[5],
        }
        for row in rows
    ]


def unread_count(username: str) -> int:
    if not username:
        return 0
    conn = _get_conn()
    try:
        _ensure_table(conn)
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM notifications WHERE username = ? AND read_at IS NULL",
            (username,),
        )
        return int(cur.fetchone()[0])
    finally:
        conn.close()


def mark_all_read(username: str) -> int:
    if not username:
        return 0
    now = datetime.now().isoformat()
    conn = _get_conn()
    try:
        _ensure_table(conn)
        cur = conn.cursor()
        cur.execute(
            "UPDATE notifications SET read_at = ? WHERE username = ? AND read_at IS NULL",
            (now, username),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def _try_send_email(to_email: str, subject: str, body: str) -> bool:
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", user)

    if not all([host, port, user, password, sender, to_email]):
        # SMTP nije konfigurisan — preskačemo tiho (in-app notifikacija je već zabilježena)
        return False

    try:
        msg = MIMEText(body or "", "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email

        with smtplib.SMTP(host, int(port), timeout=8) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(sender, [to_email], msg.as_string())
        logger.info("Email sent to=%s subject=%s", to_email, subject)
        return True
    except Exception:
        logger.exception("Email slanje neuspjelo to=%s", to_email)
        return False

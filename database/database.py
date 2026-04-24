# database.py
import hashlib
import json
import sqlite3
from pathlib import Path
import bcrypt
from datetime import datetime
import os
from typing import Optional

# Get the directory where this file is located
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "data" / "mup_data.db"

# Ensure data directory exists
os.makedirs(BASE_DIR / "data", exist_ok=True)

def get_conn():
    return sqlite3.connect(str(DB_PATH))

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Tabela za korisnike
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        email TEXT,
        city TEXT,
        id_card_number TEXT,
        role TEXT DEFAULT 'citizen',
        is_admin INTEGER DEFAULT 0
    );
    """)
    
    # Dodaj kolonu city ako ne postoji (za postojeće baze)
    try:
        cur.execute("ALTER TABLE users ADD COLUMN city TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # kolona već postoji
    
    # Dodaj kolonu id_card_number ako ne postoji
    try:
        cur.execute("ALTER TABLE users ADD COLUMN id_card_number TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # kolona već postoji

    # Dodaj kolonu role ako ne postoji
    try:
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'citizen'")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Dodaj kolonu is_admin ako ne postoji
    try:
        cur.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    # Tabela za servise (npr. licna karta)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS services (
        name TEXT PRIMARY KEY,
        documents TEXT,
        fee_eur REAL,
        payment_info TEXT,
        processing_days INTEGER
    );
    """)

    # Tabela za MUP centre
    cur.execute("""
    CREATE TABLE IF NOT EXISTS centers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        working_hours TEXT,
        lat REAL,
        lon REAL
    );
    """)

    # Tabela za istoriju upita
    cur.execute("""
    CREATE TABLE IF NOT EXISTS queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        query TEXT,
        service TEXT,
        created_at TEXT
    );
    """)

    # Tabela za podnesene DMS zahtjeve (audit log u glavnoj bazi)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS request_submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER,
        username TEXT NOT NULL,
        request_type TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # Tabela za persistent sesije (remember me)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL,
        revoked INTEGER DEFAULT 0
    );
    """)

    # Indeksi za najčešće upite
    cur.execute("CREATE INDEX IF NOT EXISTS idx_queries_username ON queries(username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_queries_created_at ON queries(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_request_submissions_username ON request_submissions(username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_request_submissions_created_at ON request_submissions(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_username ON user_sessions(username)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at)")

    conn.commit()
    conn.close()


def _hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_user(username, password, email, role="citizen", is_admin=False):
    conn = get_conn()
    cur = conn.cursor()
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    try:
        with conn:
            cur.execute(
                "INSERT INTO users (username, password_hash, email, role, is_admin) VALUES (?, ?, ?, ?, ?)",
                (username, hashed, email, role, 1 if is_admin else 0),
            )
    except sqlite3.IntegrityError:
        return False  # korisnik već postoji
    finally:
        conn.close()
    return True

def authenticate_user(username, password):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if row:
        return bcrypt.checkpw(password.encode("utf-8"), row[0])
    return False

def get_user_email(username):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT email FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

def get_user_city(username):
    """Vraća grad korisnika"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT city FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_user_role(username):
    """Vraća rolu korisnika."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT role FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else "citizen"


def is_user_admin(username):
    """Provjerava da li korisnik ima admin privilegije."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT is_admin, role FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    is_admin_flag = bool(row[0]) if row[0] is not None else False
    role = (row[1] or "").lower()
    return is_admin_flag or role in ["admin", "officer"]

def set_user_city(username, city):
    """Postavlja grad korisnika"""
    conn = get_conn()
    cur = conn.cursor()
    with conn:
        cur.execute("UPDATE users SET city = ? WHERE username = ?", (city, username))
    conn.close()
    return True

def save_query(username, query, service):
    """Sačuvaj upit korisnika u bazu"""
    conn = get_conn()
    cur = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with conn:
        cur.execute(
            "INSERT INTO queries (username, query, service, created_at) VALUES (?, ?, ?, ?)",
            (username, query, service, created_at)
        )
    conn.close()
    return True


def save_request_submission(username, request_id, request_type, status):
    """Sačuvaj podneseni zahtjev korisnika u glavnu bazu (audit log)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS request_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            username TEXT NOT NULL,
            request_type TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with conn:
        cur.execute(
            """
            INSERT INTO request_submissions (request_id, username, request_type, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (request_id, username, request_type, status, created_at)
        )
    conn.close()
    return True


def create_user_session(username: str, token: str, expires_at: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    token_hash = _hash_session_token(token)
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with conn:
        cur.execute(
            """
            INSERT INTO user_sessions (username, token_hash, expires_at, created_at, revoked)
            VALUES (?, ?, ?, ?, 0)
            """,
            (username, token_hash, expires_at, created_at),
        )
    conn.close()
    return True


def validate_user_session(username: str, token: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    token_hash = _hash_session_token(token)
    cur.execute(
        """
        SELECT expires_at, revoked
        FROM user_sessions
        WHERE username = ? AND token_hash = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (username, token_hash),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return False

    expires_at, revoked = row
    if revoked:
        return False

    try:
        expires_dt = datetime.fromisoformat(expires_at)
    except ValueError:
        return False

    return datetime.now() <= expires_dt


def revoke_user_session(username: str, token: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    token_hash = _hash_session_token(token)
    with conn:
        cur.execute(
            "UPDATE user_sessions SET revoked = 1 WHERE username = ? AND token_hash = ?",
            (username, token_hash),
        )
    conn.close()


def revoke_all_user_sessions(username: str, except_token: Optional[str] = None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    with conn:
        if except_token:
            token_hash = _hash_session_token(except_token)
            cur.execute(
                "UPDATE user_sessions SET revoked = 1 WHERE username = ? AND token_hash != ?",
                (username, token_hash),
            )
        else:
            cur.execute(
                "UPDATE user_sessions SET revoked = 1 WHERE username = ?",
                (username,),
            )
    conn.close()


def cleanup_expired_sessions() -> int:
    conn = get_conn()
    cur = conn.cursor()
    now_text = datetime.now().isoformat()
    with conn:
        cur.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now_text,))
        deleted = cur.rowcount
    conn.close()
    return int(deleted or 0)


def get_user_request_submissions(username, limit=50):
    """Vrati listu podnesenih zahtjeva korisnika iz audit log tabele."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT request_id, request_type, status, created_at
        FROM request_submissions
        WHERE username = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (username, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "request_id": request_id,
            "request_type": request_type,
            "status": status,
            "created_at": created_at,
        }
        for request_id, request_type, status, created_at in rows
    ]

def get_user_queries(username, limit=10):
    """Preuzmi historiju upita korisnika"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT query, service, created_at FROM queries WHERE username = ? ORDER BY created_at DESC LIMIT ?",
        (username, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return [{"query": q, "service": s, "created_at": c} for q, s, c in rows]

def set_id_card_number(username, id_card_number):
    """Čuva broj lične karte za korisnika"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET id_card_number = ? WHERE username = ?", (id_card_number, username))
    conn.commit()
    conn.close()

def get_id_card_number(username):
    """Vraća broj lične karte korisnika"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id_card_number FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else None

import json

def get_all_services():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name, documents, fee_eur, payment_info, processing_days FROM services")
    rows = cur.fetchall()
    conn.close()
    services = {}
    for name, docs, fee, pay, days in rows:
        services[name] = {
            "dokumenta": json.loads(docs),
            "taksa_eur": fee,
            "uplata": pay,
            "rok_izrade_dana": days,
            "alias": []  # dodatno ako koristiš alias logiku u detekciji
        }
    return services

def get_all_centers():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name, working_hours, lat, lon FROM centers")
    rows = cur.fetchall()
    conn.close()
    return [
        {"naziv": name, "radno_vrijeme": time, "lat": lat, "lon": lon}
        for name, time, lat, lon in rows
    ]

# ============================================
# ANALYTICS FUNKCIJE
# ============================================

def get_service_stats():
    """
    Vraća statistiku po uslugama - koliko puta je svaka usluga pretražena
    OBJAŠNJENJE: Brojimo koliko puta se pojavljuje svaki servis u 'queries' tabeli
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT service, COUNT(*) as count 
        FROM queries 
        WHERE service IS NOT NULL 
        GROUP BY service 
        ORDER BY count DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"service": s, "count": c} for s, c in rows]

def get_queries_by_city():
    """
    Vraća broj upita po gradovima (iz users.city)
    OBJAŠNJENJE: JOIN queries sa users da dobijem grad svakog korisnika
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.city, COUNT(q.id) as count 
        FROM queries q
        JOIN users u ON q.username = u.username
        WHERE u.city IS NOT NULL
        GROUP BY u.city
        ORDER BY count DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"city": c, "count": cnt} for c, cnt in rows]

def get_queries_by_time():
    """
    Vraća broj upita po satima dana
    OBJAŠNJENJE: Izvlačim sat iz created_at timestampa i grupiram
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT 
            CAST(strftime('%H', created_at) AS INTEGER) as hour,
            COUNT(*) as count
        FROM queries
        GROUP BY hour
        ORDER BY hour
    """)
    rows = cur.fetchall()
    conn.close()
    return [{"hour": h, "count": c} for h, c in rows]

def get_total_stats():
    """
    Vraća ukupne statistike sistema
    OBJAŠNJENJE: Brojimo ukupno korisnika i upita
    """
    conn = get_conn()
    cur = conn.cursor()
    
    # Ukupno korisnika
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]
    
    # Ukupno upita
    cur.execute("SELECT COUNT(*) FROM queries")
    total_queries = cur.fetchone()[0]
    
    # Upiti danas
    from datetime import date
    today = date.today().strftime('%Y-%m-%d')
    cur.execute("SELECT COUNT(*) FROM queries WHERE DATE(created_at) = ?", (today,))
    queries_today = cur.fetchone()[0]
    
    # Najaktivniji korisnik
    cur.execute("""
        SELECT username, COUNT(*) as count 
        FROM queries 
        GROUP BY username 
        ORDER BY count DESC 
        LIMIT 1
    """)
    top_user_row = cur.fetchone()
    top_user = top_user_row[0] if top_user_row else "N/A"
    
    conn.close()
    
    return {
        "total_users": total_users,
        "total_queries": total_queries,
        "queries_today": queries_today,
        "top_user": top_user
    }

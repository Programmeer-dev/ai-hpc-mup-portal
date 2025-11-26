# database.py
import sqlite3, json
from pathlib import Path
import bcrypt
from datetime import datetime
import os

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
        id_card_number TEXT
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

    conn.commit()
    conn.close()

def create_user(username, password, email):
    conn = get_conn()
    cur = conn.cursor()
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    try:
        cur.execute("INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)",
                    (username, hashed, email))
        conn.commit()
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

def set_user_city(username, city):
    """Postavlja grad korisnika"""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET city = ? WHERE username = ?", (city, username))
    conn.commit()
    conn.close()
    return True

def save_query(username, query, service):
    """Sačuvaj upit korisnika u bazu"""
    conn = get_conn()
    cur = conn.cursor()
    from datetime import datetime
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute(
        "INSERT INTO queries (username, query, service, created_at) VALUES (?, ?, ?, ?)",
        (username, query, service, created_at)
    )
    conn.commit()
    conn.close()
    return True

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

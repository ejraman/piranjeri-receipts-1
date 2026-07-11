"""
db.py — Neon PostgreSQL data-access layer for Piranjeri Trust receipts app
Place this file alongside app.py in the repo root.

Streamlit Secrets format:
  [neon]
  dsn = "postgresql://neondb_owner:PASSWORD@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
"""

import streamlit as st
import psycopg2
import psycopg2.extras
from contextlib import contextmanager
from datetime import datetime

# ── Connection with auto-reconnect ───────────────────────────────

def _new_connection():
    dsn  = st.secrets["neon"]["dsn"]
    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = False
    return conn

def _get_connection():
    """Return a live connection, reconnecting if closed or broken."""
    if "neon_conn" not in st.session_state or st.session_state["neon_conn"] is None:
        st.session_state["neon_conn"] = _new_connection()
    else:
        conn = st.session_state["neon_conn"]
        try:
            # ping — if connection is dead this raises an error
            conn.cursor().execute("SELECT 1")
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            st.session_state["neon_conn"] = _new_connection()
    return st.session_state["neon_conn"]

@contextmanager
def _cursor():
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise

def test_connection():
    with _cursor() as cur:
        cur.execute("SELECT 1")

# ── Serial counter ────────────────────────────────────────────────

def next_serial_for_fy(fy: str) -> str:
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO serial_counter (fy, count)
            VALUES (%s, 1)
            ON CONFLICT (fy) DO UPDATE
                SET count = serial_counter.count + 1
            RETURNING count
        """, (fy,))
        count = cur.fetchone()["count"]
    return f"{count:03d}/{fy}"

def reset_serial_counter(fy: str, start_from: int):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO serial_counter (fy, count)
            VALUES (%s, %s)
            ON CONFLICT (fy) DO UPDATE SET count = EXCLUDED.count
        """, (fy, start_from))

# ── Donors ────────────────────────────────────────────────────────

def get_all_donors() -> list:
    with _cursor() as cur:
        cur.execute("SELECT * FROM donors ORDER BY name ASC")
        return [dict(r) for r in cur.fetchall()]

def create_donor(name: str, mobile: str):
    with _cursor() as cur:
        cur.execute(
            "INSERT INTO donors (name, mobile) VALUES (%s, %s)",
            (name, mobile)
        )

def update_donor(old_name: str, old_mobile: str, new_name: str, new_mobile: str):
    with _cursor() as cur:
        cur.execute("""
            UPDATE donors SET name = %s, mobile = %s
            WHERE name = %s AND mobile = %s
        """, (new_name, new_mobile, old_name, old_mobile))

# ── Receipts ──────────────────────────────────────────────────────

def save_receipt(record: dict):
    with _cursor() as cur:
        cur.execute("""
            INSERT INTO receipts
                (serial, name, mobile, amount, purpose, payment,
                 cheque_number, issue_date, credit_date, issued_by, pdf_file, status)
            VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')
        """, (
            record["serial"],
            record["name"],
            record.get("mobile", ""),
            float(record["amount"]),
            record.get("purpose", ""),
            record.get("payment", ""),
            record.get("cheque_number", ""),
            record["issue_date"],
            record.get("credit_date", ""),
            record.get("user", ""),
            record.get("pdf_file", ""),
        ))

def load_history() -> list:
    with _cursor() as cur:
        cur.execute("SELECT * FROM receipts ORDER BY issue_date DESC, serial DESC")
        rows = cur.fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["user"] = d.get("issued_by", "")
        for field in ("issue_date", "credit_date", "cancelled_at"):
            if d.get(field) and not isinstance(d[field], str):
                d[field] = str(d[field])
        result.append(d)
    return result

def cancel_receipt(serial: str, cancelled_by: str, reason: str):
    with _cursor() as cur:
        cur.execute("""
            UPDATE receipts
            SET status        = 'CANCELLED',
                cancelled_by  = %s,
                cancelled_at  = %s,
                cancel_reason = %s
            WHERE serial = %s AND status = 'ACTIVE'
        """, (cancelled_by, datetime.now().isoformat(), reason, serial))

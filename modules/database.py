"""
MODULE — SQLite Database Manager for Sessions & Complaint Drafts
Complies with data minimization, session handling, and persistence.
Tables:
  - sessions: tracks session lifecycle (intake -> draft_ready -> confirmed -> classified)
  - messages: preserves conversation transcript
  - complaint_drafts: stores structured entities, user edits, and final classification results
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "complaints.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'hi',
            status TEXT NOT NULL DEFAULT 'intake'
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        );

        CREATE TABLE IF NOT EXISTS complaint_drafts (
            session_id TEXT PRIMARY KEY,
            incident_summary TEXT,
            incident_date TEXT,
            platform TEXT,
            lost_amount REAL,
            payment_method TEXT,
            bank_name TEXT,
            utr_number TEXT,
            suspect_identifier TEXT,
            evidence_notes TEXT,
            formal_narrative TEXT,
            is_confirmed INTEGER DEFAULT 0,
            confirmed_at TEXT,
            predicted_category TEXT,
            confidence REAL,
            decision_margin REAL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id)
        );
        """)
    conn.close()

def create_or_get_session(session_id: str, language: str = "hi") -> Dict[str, Any]:
    init_db()
    conn = get_db_connection()
    with conn:
        row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
        if not row:
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO sessions (session_id, created_at, language, status) VALUES (?, ?, ?, 'intake')",
                (session_id, now, language)
            )
            return {"session_id": session_id, "created_at": now, "language": language, "status": "intake"}
        return dict(row)

def save_message(session_id: str, role: str, content: str):
    conn = get_db_connection()
    with conn:
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now)
        )

def get_session_history(session_id: str) -> List[Dict[str, str]]:
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
        (session_id,)
    ).fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]

def save_complaint_draft(session_id: str, draft: Dict[str, Any]):
    init_db()
    conn = get_db_connection()
    now = datetime.now().isoformat()
    with conn:
        conn.execute("""
        INSERT INTO complaint_drafts (
            session_id, incident_summary, incident_date, platform,
            lost_amount, payment_method, bank_name, utr_number,
            suspect_identifier, evidence_notes, formal_narrative,
            updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(session_id) DO UPDATE SET
            incident_summary = coalesce(excluded.incident_summary, complaint_drafts.incident_summary),
            incident_date = coalesce(excluded.incident_date, complaint_drafts.incident_date),
            platform = coalesce(excluded.platform, complaint_drafts.platform),
            lost_amount = coalesce(excluded.lost_amount, complaint_drafts.lost_amount),
            payment_method = coalesce(excluded.payment_method, complaint_drafts.payment_method),
            bank_name = coalesce(excluded.bank_name, complaint_drafts.bank_name),
            utr_number = coalesce(excluded.utr_number, complaint_drafts.utr_number),
            suspect_identifier = coalesce(excluded.suspect_identifier, complaint_drafts.suspect_identifier),
            evidence_notes = coalesce(excluded.evidence_notes, complaint_drafts.evidence_notes),
            formal_narrative = coalesce(excluded.formal_narrative, complaint_drafts.formal_narrative),
            updated_at = excluded.updated_at
        """, (
            session_id,
            draft.get("incident_summary"),
            draft.get("incident_date"),
            draft.get("platform"),
            draft.get("lost_amount"),
            draft.get("payment_method"),
            draft.get("bank_name"),
            draft.get("utr_number"),
            draft.get("suspect_identifier"),
            draft.get("evidence_notes"),
            draft.get("formal_narrative"),
            now
        ))

def get_complaint_draft(session_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM complaint_drafts WHERE session_id = ?", (session_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def confirm_and_classify_draft(
    session_id: str,
    user_edited_narrative: str,
    predicted_category: str,
    confidence: float,
    decision_margin: float
):
    conn = get_db_connection()
    now = datetime.now().isoformat()
    with conn:
        conn.execute("""
        UPDATE complaint_drafts SET
            formal_narrative = ?,
            is_confirmed = 1,
            confirmed_at = ?,
            predicted_category = ?,
            confidence = ?,
            decision_margin = ?,
            updated_at = ?
        WHERE session_id = ?
        """, (
            user_edited_narrative,
            now,
            predicted_category,
            confidence,
            decision_margin,
            now,
            session_id
        ))
        conn.execute("UPDATE sessions SET status = 'classified' WHERE session_id = ?", (session_id,))

def reset_session(session_id: str):
    conn = get_db_connection()
    with conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM complaint_drafts WHERE session_id = ?", (session_id,))
        conn.execute("UPDATE sessions SET status = 'intake' WHERE session_id = ?", (session_id,))

if __name__ == "__main__":
    init_db()
    print("SQLite database initialized successfully at:", DB_PATH)

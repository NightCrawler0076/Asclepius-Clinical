"""
SQLite database models and initialization.
"""

import sqlite3
import os

from config import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS doctors (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            specialty   TEXT DEFAULT '',
            clinic_name TEXT DEFAULT '',
            phone       TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS patients (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            age         INTEGER,
            sex         TEXT DEFAULT '',
            phone       TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS consultations (
            id          TEXT PRIMARY KEY,
            doctor_id   TEXT NOT NULL REFERENCES doctors(id),
            patient_id  TEXT REFERENCES patients(id),
            audio_path  TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now')),
            status      TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS transcripts (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            consultation_id TEXT NOT NULL REFERENCES consultations(id),
            text            TEXT NOT NULL,
            language        TEXT DEFAULT '',
            model_used      TEXT DEFAULT '',
            segments_json   TEXT DEFAULT '[]',
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS prescriptions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            consultation_id TEXT NOT NULL REFERENCES consultations(id),
            data_json       TEXT NOT NULL,
            status          TEXT DEFAULT 'draft',
            created_at      TEXT DEFAULT (datetime('now')),
            confirmed_at    TEXT
        );

        CREATE TABLE IF NOT EXISTS sync_queue (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type     TEXT NOT NULL,
            entity_id       TEXT NOT NULL,
            action          TEXT DEFAULT 'create',
            payload_json    TEXT NOT NULL,
            status          TEXT DEFAULT 'pending',
            attempts        INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now')),
            last_attempt_at TEXT
        );
    """)
    # Seed default Doctor 1 and Patient 1 if empty
    doc_count = conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]
    if doc_count == 0:
        conn.execute(
            "INSERT INTO doctors (id, name, specialty, clinic_name, phone) VALUES (?, ?, ?, ?, ?)",
            ("DOC-001", "Doctor 1", "General Medicine", "City Clinic", "+91 9876543210"),
        )

    pat_count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    if pat_count == 0:
        conn.execute(
            "INSERT INTO patients (id, name, age, sex, phone) VALUES (?, ?, ?, ?, ?)",
            ("PAT-001", "Patient 1", 35, "M", "+91 9876543211"),
        )

    conn.commit()
    conn.close()

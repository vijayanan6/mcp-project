"""
database.py — SQLite persistence layer

Replaces in-memory dicts in mcp_server.py and api.py with a real database.
Uses Python's built-in sqlite3 — no extra packages needed.

Tables:
  notes    — stores user notes (replaces `notes: dict` in mcp_server.py)
  sessions — stores chat history (replaces `sessions: dict` in api.py)
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

# Database file lives in the project root
DB_PATH = Path(__file__).parent / "data.db"


def get_connection() -> sqlite3.Connection:
    """Open a connection with row_factory so rows behave like dicts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't exist. Safe to call on every startup."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                title      TEXT PRIMARY KEY,
                content    TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                messages   TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()


# ── Notes CRUD ────────────────────────────────────────────────────────────────

def note_save(title: str, content: str) -> None:
    """Insert or replace a note."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO notes (title, content, created_at) VALUES (?, ?, ?)",
            (title, content, datetime.now().isoformat()),
        )
        conn.commit()


def note_get(title: str) -> dict | None:
    """Return a note dict or None if not found."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM notes WHERE title = ?", (title,)).fetchone()
        return dict(row) if row else None


def note_list() -> list[str]:
    """Return all note titles sorted alphabetically."""
    with get_connection() as conn:
        rows = conn.execute("SELECT title FROM notes ORDER BY title").fetchall()
        return [row["title"] for row in rows]


def note_delete(title: str) -> bool:
    """Delete a note. Returns True if it existed."""
    with get_connection() as conn:
        result = conn.execute("DELETE FROM notes WHERE title = ?", (title,))
        conn.commit()
        return result.rowcount > 0


# ── Sessions CRUD ─────────────────────────────────────────────────────────────

def session_get(session_id: str) -> list:
    """Return message history for a session, or empty list if new."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT messages FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return json.loads(row["messages"]) if row else []


def session_save(session_id: str, messages: list) -> None:
    """Insert or update a session's message history."""
    now = datetime.now().isoformat()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sessions (session_id, messages, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET messages = ?, updated_at = ?
            """,
            (session_id, json.dumps(messages), now, now, json.dumps(messages), now),
        )
        conn.commit()


def session_list() -> list[dict]:
    """Return all sessions with id and last updated time."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT session_id, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def session_delete(session_id: str) -> bool:
    """Delete a session. Returns True if it existed."""
    with get_connection() as conn:
        result = conn.execute(
            "DELETE FROM sessions WHERE session_id = ?", (session_id,)
        )
        conn.commit()
        return result.rowcount > 0

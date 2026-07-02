"""
database.py — SQLite persistence layer

Replaces in-memory dicts in mcp_server.py and api.py with a real database.
Uses Python's built-in sqlite3 — no extra packages needed.

Tables:
  notes      — stores user notes (replaces `notes: dict` in mcp_server.py)
  sessions   — stores chat history (replaces `sessions: dict` in api.py)
  usage_logs — stores token usage and estimated cost per message
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS usage_logs (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id          TEXT NOT NULL,
                model               TEXT NOT NULL,
                input_tokens        INTEGER NOT NULL DEFAULT 0,
                cache_write_tokens  INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens   INTEGER NOT NULL DEFAULT 0,
                output_tokens       INTEGER NOT NULL DEFAULT 0,
                estimated_cost_usd  REAL NOT NULL DEFAULT 0,
                created_at          TEXT NOT NULL
            )
        """)
        conn.commit()


# ── Pricing (USD per 1K tokens) ───────────────────────────────────────────────

_PRICING = {
    "claude-haiku-4-5": {
        "input": 0.0008, "cache_write": 0.001, "cache_read": 0.00008, "output": 0.004
    },
    "claude-sonnet-4-6": {
        "input": 0.003, "cache_write": 0.00375, "cache_read": 0.0003, "output": 0.015
    },
}

def _estimate_cost(model: str, input_tokens: int, cache_write: int, cache_read: int, output_tokens: int) -> float:
    """Estimate cost in USD based on token counts and model pricing."""
    p = _PRICING.get(model, _PRICING["claude-sonnet-4-6"])
    return (
        input_tokens      / 1000 * p["input"] +
        cache_write       / 1000 * p["cache_write"] +
        cache_read        / 1000 * p["cache_read"] +
        output_tokens     / 1000 * p["output"]
    )


# ── Usage Logs ────────────────────────────────────────────────────────────────

def usage_log(session_id: str, model: str, input_tokens: int, cache_write: int, cache_read: int, output_tokens: int) -> None:
    """Save token usage for one message turn."""
    cost = _estimate_cost(model, input_tokens, cache_write, cache_read, output_tokens)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO usage_logs
              (session_id, model, input_tokens, cache_write_tokens, cache_read_tokens, output_tokens, estimated_cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, model, input_tokens, cache_write, cache_read, output_tokens, cost, datetime.now().isoformat()),
        )
        conn.commit()


def usage_summary() -> dict:
    """Return aggregated usage stats — total tokens, cost, and per-day breakdown."""
    with get_connection() as conn:
        totals = conn.execute("""
            SELECT
                COUNT(*)                        AS total_requests,
                SUM(input_tokens)               AS total_input,
                SUM(cache_write_tokens)         AS total_cache_write,
                SUM(cache_read_tokens)          AS total_cache_read,
                SUM(output_tokens)              AS total_output,
                SUM(estimated_cost_usd)         AS total_cost_usd,
                MIN(created_at)                 AS first_request,
                MAX(created_at)                 AS last_request
            FROM usage_logs
        """).fetchone()

        by_model = conn.execute("""
            SELECT model,
                   COUNT(*)                 AS requests,
                   SUM(estimated_cost_usd)  AS cost_usd
            FROM usage_logs
            GROUP BY model
            ORDER BY cost_usd DESC
        """).fetchall()

        by_day = conn.execute("""
            SELECT DATE(created_at)          AS day,
                   COUNT(*)                  AS requests,
                   SUM(estimated_cost_usd)   AS cost_usd
            FROM usage_logs
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14
        """).fetchall()

    return {
        "totals": dict(totals) if totals else {},
        "by_model": [dict(r) for r in by_model],
        "by_day": [dict(r) for r in by_day],
    }


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

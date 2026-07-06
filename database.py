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
                project             TEXT NOT NULL DEFAULT 'mcp-project',
                session_id          TEXT NOT NULL,
                model               TEXT NOT NULL,
                input_tokens        INTEGER NOT NULL DEFAULT 0,
                cache_write_tokens  INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens   INTEGER NOT NULL DEFAULT 0,
                output_tokens       INTEGER NOT NULL DEFAULT 0,
                estimated_cost_usd  REAL NOT NULL DEFAULT 0,
                tools_used          TEXT NOT NULL DEFAULT '[]',
                created_at          TEXT NOT NULL
            )
        """)
        # migrate existing databases that predate these columns
        for col, definition in [
            ("tools_used", "TEXT NOT NULL DEFAULT '[]'"),
            ("project",    "TEXT NOT NULL DEFAULT 'mcp-project'"),
        ]:
            try:
                conn.execute(f"ALTER TABLE usage_logs ADD COLUMN {col} {definition}")
                conn.commit()
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS credit_config (
                id                  INTEGER PRIMARY KEY CHECK (id = 1),
                starting_balance    REAL NOT NULL DEFAULT 0,
                alert_threshold     REAL NOT NULL DEFAULT 1.0,
                updated_at          TEXT NOT NULL
            )
        """)
        # migrate existing databases that predate the reset-period columns
        for col, definition in [
            ("period_start",          "TEXT"),
            ("prev_period_start",     "TEXT"),
            ("prev_period_end",       "TEXT"),
            ("prev_period_cost_usd",  "REAL NOT NULL DEFAULT 0"),
            ("prev_period_days",      "INTEGER NOT NULL DEFAULT 0"),
        ]:
            try:
                conn.execute(f"ALTER TABLE credit_config ADD COLUMN {col} {definition}")
                conn.commit()
            except Exception:
                pass
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

def usage_log(session_id: str, model: str, input_tokens: int, cache_write: int, cache_read: int, output_tokens: int, tools: list[str] | None = None, project: str = "mcp-project") -> None:
    """Save token usage for one message turn."""
    cost = _estimate_cost(model, input_tokens, cache_write, cache_read, output_tokens)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO usage_logs
              (project, session_id, model, input_tokens, cache_write_tokens, cache_read_tokens, output_tokens, estimated_cost_usd, tools_used, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (project, session_id, model, input_tokens, cache_write, cache_read, output_tokens, cost, json.dumps(tools or []), datetime.now().isoformat()),
        )
        conn.commit()


def usage_summary(project: str | None = None) -> dict:
    """Return aggregated usage stats. Pass project name to filter to one project."""
    where  = "WHERE project = ?" if project else ""
    params = (project,)          if project else ()
    with get_connection() as conn:
        totals = conn.execute(f"""
            SELECT
                COUNT(*)                        AS total_requests,
                SUM(input_tokens)               AS total_input,
                SUM(cache_write_tokens)         AS total_cache_write,
                SUM(cache_read_tokens)          AS total_cache_read,
                SUM(output_tokens)              AS total_output,
                SUM(estimated_cost_usd)         AS total_cost_usd,
                MIN(created_at)                 AS first_request,
                MAX(created_at)                 AS last_request
            FROM usage_logs {where}
        """, params).fetchone()

        by_model = conn.execute(f"""
            SELECT model,
                   COUNT(*)                 AS requests,
                   SUM(estimated_cost_usd)  AS cost_usd
            FROM usage_logs {where}
            GROUP BY model
            ORDER BY cost_usd DESC
        """, params).fetchall()

        by_day = conn.execute(f"""
            SELECT DATE(created_at)          AS day,
                   COUNT(*)                  AS requests,
                   SUM(estimated_cost_usd)   AS cost_usd
            FROM usage_logs {where}
            GROUP BY day
            ORDER BY day DESC
            LIMIT 14
        """, params).fetchall()

        by_session = conn.execute(f"""
            SELECT session_id,
                   COUNT(*)                 AS requests,
                   SUM(estimated_cost_usd)  AS cost_usd,
                   MIN(created_at)          AS first_at,
                   MAX(created_at)          AS last_at
            FROM usage_logs {where}
            GROUP BY session_id
            ORDER BY cost_usd DESC
            LIMIT 10
        """, params).fetchall()

        by_tool = conn.execute(f"""
            SELECT
                json_each.value             AS tool_name,
                COUNT(*)                    AS calls,
                SUM(ul.estimated_cost_usd)  AS cost_usd,
                AVG(ul.estimated_cost_usd)  AS avg_cost_usd
            FROM usage_logs ul, json_each(ul.tools_used)
            {where.replace('WHERE', 'WHERE ul.project = ? AND') if project else ''}
            GROUP BY json_each.value
            ORDER BY calls DESC
        """, params).fetchall()

        by_project = conn.execute("""
            SELECT project,
                   COUNT(*)                 AS requests,
                   SUM(estimated_cost_usd)  AS cost_usd,
                   MAX(created_at)          AS last_at
            FROM usage_logs
            GROUP BY project
            ORDER BY cost_usd DESC
        """).fetchall()

    return {
        "totals":     dict(totals) if totals else {},
        "by_model":   [dict(r) for r in by_model],
        "by_day":     [dict(r) for r in by_day],
        "by_session": [dict(r) for r in by_session],
        "by_tool":    [dict(r) for r in by_tool],
        "by_project": [dict(r) for r in by_project],
    }


# ── Credit Config ─────────────────────────────────────────────────────────────

def credit_get() -> dict:
    """Return stored credit config or defaults."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM credit_config WHERE id = 1").fetchone()
        if row:
            return dict(row)
        return {
            "starting_balance": 0.0, "alert_threshold": 1.0, "period_start": None,
            "prev_period_start": None, "prev_period_end": None,
            "prev_period_cost_usd": 0.0, "prev_period_days": 0,
        }


def _period_spend(conn, period_start: str | None, project: str | None) -> tuple[float, int]:
    """Sum cost and count distinct active days in usage_logs, optionally since period_start / for one project."""
    where_parts, params = [], []
    if period_start:
        where_parts.append("created_at >= ?")
        params.append(period_start)
    if project:
        where_parts.append("project = ?")
        params.append(project)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    row = conn.execute(f"""
        SELECT SUM(estimated_cost_usd) AS cost_usd, COUNT(DISTINCT DATE(created_at)) AS active_days
        FROM usage_logs {where}
    """, params).fetchone()
    return (row["cost_usd"] or 0.0), (row["active_days"] or 0)


def credit_status(project: str | None = None) -> dict:
    """Credit config plus spend/active-days for the *current* tracking period (since last reset, or all-time if never reset)."""
    cfg = credit_get()
    with get_connection() as conn:
        cost_usd, active_days = _period_spend(conn, cfg.get("period_start"), project)
    cfg["period_cost_usd"] = cost_usd
    cfg["period_active_days"] = active_days
    return cfg


def credit_set(starting_balance: float, alert_threshold: float = 1.0, reset: bool = False) -> None:
    """Save or update the starting credit balance and alert threshold.

    If reset=True, snapshot the outgoing period's spend/days into prev_period_* columns
    (global, not project-scoped — a real balance top-up applies to the whole account) and
    start a new period from now. Never touches usage_logs — historical charts are unaffected.
    """
    now = datetime.now().isoformat()
    with get_connection() as conn:
        if reset:
            old_row = conn.execute("SELECT period_start FROM credit_config WHERE id = 1").fetchone()
            old_period_start = old_row["period_start"] if old_row else None
            prev_cost, prev_days = _period_spend(conn, old_period_start, project=None)
            conn.execute("""
                INSERT INTO credit_config
                  (id, starting_balance, alert_threshold, period_start,
                   prev_period_start, prev_period_end, prev_period_cost_usd, prev_period_days, updated_at)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    starting_balance = ?, alert_threshold = ?, period_start = ?,
                    prev_period_start = ?, prev_period_end = ?, prev_period_cost_usd = ?, prev_period_days = ?, updated_at = ?
            """, (
                starting_balance, alert_threshold, now, old_period_start, now, prev_cost, prev_days, now,
                starting_balance, alert_threshold, now, old_period_start, now, prev_cost, prev_days, now,
            ))
        else:
            conn.execute("""
                INSERT INTO credit_config (id, starting_balance, alert_threshold, updated_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET starting_balance = ?, alert_threshold = ?, updated_at = ?
            """, (starting_balance, alert_threshold, now, starting_balance, alert_threshold, now))
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

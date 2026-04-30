"""
database.py — SQLite persistence layer
Thread-safe via WAL mode. Stores the full brief JSON alongside indexed columns.
"""

import sqlite3
import json
import logging
from typing import List, Optional
from models import TradeBrief

log = logging.getLogger('fx_agent.db')


def _connect(db_file: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_file, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_file: str = 'fx_agent.db') -> None:
    with _connect(db_file) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS briefs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                pair         TEXT    NOT NULL,
                generated_at TEXT    NOT NULL,
                status       TEXT    NOT NULL DEFAULT 'pending_approval',
                confidence   INTEGER NOT NULL,
                direction    TEXT    NOT NULL,
                full_json    TEXT    NOT NULL,
                UNIQUE(pair, generated_at)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pair ON briefs(pair)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_generated_at ON briefs(generated_at)')
    log.info(f"Database initialised: {db_file}")


def save_brief(brief: TradeBrief, db_file: str = 'fx_agent.db') -> None:
    direction = brief.trade_setup.direction if brief.trade_setup else 'Neutral'
    try:
        with _connect(db_file) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO briefs VALUES (NULL,?,?,?,?,?,?)',
                (
                    brief.pair,
                    brief.generated_at,
                    brief.status,
                    brief.confidence,
                    direction,
                    brief.model_dump_json(),
                )
            )
        log.info(f"Saved brief: {brief.pair} | {direction} | {brief.confidence}%")
    except sqlite3.Error as e:
        log.error(f"DB save error for {brief.pair}: {e}")


def get_latest_briefs(db_file: str = 'fx_agent.db', limit: int = 20) -> List[dict]:
    """Return the most recent briefs as dicts (parsed from full_json)."""
    try:
        with _connect(db_file) as conn:
            rows = conn.execute(
                'SELECT full_json FROM briefs ORDER BY generated_at DESC LIMIT ?',
                (limit,)
            ).fetchall()
        return [json.loads(r['full_json']) for r in rows]
    except sqlite3.Error as e:
        log.error(f"DB read error: {e}")
        return []


def get_briefs_for_pair(pair: str, db_file: str = 'fx_agent.db', limit: int = 10) -> List[dict]:
    """Return recent briefs for a specific pair."""
    try:
        with _connect(db_file) as conn:
            rows = conn.execute(
                'SELECT full_json FROM briefs WHERE pair=? ORDER BY generated_at DESC LIMIT ?',
                (pair, limit)
            ).fetchall()
        return [json.loads(r['full_json']) for r in rows]
    except sqlite3.Error as e:
        log.error(f"DB read error for {pair}: {e}")
        return []

import os
import sqlite3
import logging
from datetime import datetime, timezone
from models import TradeBrief

log = logging.getLogger("fx_db")

# Configurable path — point to a persistent disk on Render, or /tmp for ephemeral
DB_FILE = os.getenv("DB_PATH", "/tmp/fx_agent.db")


def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS briefs (
                pair         TEXT,
                generated_at TEXT,
                status       TEXT,
                confidence   INTEGER,
                direction    TEXT,
                full_json    TEXT,
                reviewed_at  TEXT,
                review_note  TEXT,
                PRIMARY KEY (pair, generated_at)
            )
        """)
        # Index for fast status queries (approval workflow)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_briefs_status ON briefs (status)
        """)
        conn.commit()


def save_brief(brief: TradeBrief):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT OR REPLACE INTO briefs
                (pair, generated_at, status, confidence, direction, full_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            brief.pair,
            brief.generated_at,
            brief.status,
            brief.confidence,
            brief.trade_setup.direction,
            brief.model_dump_json(),
        ))
        conn.commit()
    log.info(f"Saved brief: {brief.pair} [{brief.status}]")


def update_brief_status(pair: str, generated_at: str, new_status: str, note: str = "") -> bool:
    """Flip the approval status of a brief. Returns True if a row was updated."""
    reviewed_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        cur = conn.execute("""
            UPDATE briefs
               SET status = ?, reviewed_at = ?, review_note = ?
             WHERE pair = ? AND generated_at = ?
        """, (new_status, reviewed_at, note, pair, generated_at))
        conn.commit()
        updated = cur.rowcount > 0
    if updated:
        log.info(f"Status updated: {pair} → {new_status}")
    else:
        log.warning(f"No matching brief found for {pair} / {generated_at}")
    return updated


def load_briefs(status: str | None = None) -> list[dict]:
    """Return briefs from the DB, optionally filtered by status."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        if status:
            rows = conn.execute(
                "SELECT full_json FROM briefs WHERE status = ? ORDER BY generated_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT full_json FROM briefs ORDER BY generated_at DESC"
            ).fetchall()
    import json
    return [json.loads(r["full_json"]) for r in rows]

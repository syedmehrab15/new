import sqlite3
import json
import logging
from models import TradeBrief

log = logging.getLogger("fx_db")
DB_FILE = "fx_agent.db"

def init_db():
    """Initializes the SQLite database with the briefs table."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS briefs (
                pair TEXT,
                generated_at TEXT,
                status TEXT,
                confidence INTEGER,
                direction TEXT,
                full_json TEXT,
                PRIMARY KEY (pair, generated_at)
            )
        """)
        conn.commit()

def save_brief(brief: TradeBrief):
    """Saves a validated Pydantic brief to the database."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("""
            INSERT INTO briefs (pair, generated_at, status, confidence, direction, full_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            brief.pair,
            brief.generated_at,
            brief.status,
            brief.confidence,
            brief.trade_setup.direction,
            brief.model_dump_json()
        ))
        conn.commit()

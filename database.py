import sqlite3, json
from models import TradeBrief

DB_FILE = 'fx_agent.db'

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS briefs (pair TEXT, generated_at TEXT, status TEXT, confidence INTEGER, direction TEXT, full_json TEXT, PRIMARY KEY (pair, generated_at))')

def save_brief(brief: TradeBrief):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute('INSERT INTO briefs VALUES (?,?,?,?,?,?)', (brief.pair, brief.generated_at, brief.status, brief.confidence, brief.trade_setup.direction if brief.trade_setup else 'Neutral', brief.model_dump_json()))

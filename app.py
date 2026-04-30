"""
app.py — Flask web server + APScheduler
Exposes the stored trade briefs over HTTP and runs scheduled market scans.
"""

import logging
import os
import threading

from flask import Flask, jsonify, abort

from config import Config
from database import init_db, get_latest_briefs, get_briefs_for_pair

log = logging.getLogger('fx_agent.app')

app = Flask(__name__)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def health():
    return jsonify({'status': 'ok', 'service': 'FX Agent'})


@app.route('/briefs')
def briefs_list():
    """Return the 20 most recent trade briefs across all pairs."""
    data = get_latest_briefs(Config.DB_FILE, limit=20)
    return jsonify(data)


@app.route('/briefs/<path:pair>')
def briefs_for_pair(pair: str):
    """Return the 10 most recent briefs for a specific pair, e.g. /briefs/EUR%2FUSD"""
    pair = pair.upper().replace('-', '/')
    data = get_briefs_for_pair(pair, Config.DB_FILE, limit=10)
    if not data:
        abort(404, description=f"No briefs found for {pair}")
    return jsonify(data)


# ── Scheduler ─────────────────────────────────────────────────────────────────

def _start_scheduler():
    """
    Run the market scan on a background thread at the configured interval.
    We deliberately do NOT import agent at module level to avoid circular imports.
    """
    import time
    from agent import run_full_market_scan

    def loop():
        while True:
            try:
                log.info("Scheduler: triggering market scan…")
                run_full_market_scan()
            except Exception as e:
                log.error(f"Scheduler error: {e}")
            time.sleep(Config.SCAN_INTERVAL_SECONDS)

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    log.info(f"Scheduler started — interval: {Config.SCAN_INTERVAL_SECONDS}s")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s — %(message)s'
    )
    init_db(Config.DB_FILE)

    # Only start scheduler if API keys are present
    if Config.ANTHROPIC_API_KEY and Config.TWELVE_DATA_API_KEY:
        _start_scheduler()
    else:
        log.warning("API keys missing — scheduler disabled. Set env vars to enable.")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

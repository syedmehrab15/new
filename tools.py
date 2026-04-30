"""
tools.py — Market Data Gatherer
Fetches live price + indicators from Twelve Data.
Falls back to mock data if the API key is absent (useful for local dev / testing).
"""

import logging
import time
from datetime import datetime, timezone

import requests

log = logging.getLogger('fx_agent.tools')

BASE_URL = 'https://api.twelvedata.com'
INTERVAL  = '1h'


def _get(endpoint: str, params: dict, api_key: str) -> dict:
    params['apikey'] = api_key
    params['format'] = 'JSON'
    try:
        r = requests.get(f'{BASE_URL}/{endpoint}', params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get('status') == 'error':
            log.warning(f"Twelve Data error [{endpoint}]: {data.get('message')}")
            return {}
        return data
    except requests.RequestException as e:
        log.error(f"HTTP error [{endpoint}]: {e}")
        return {}


def _safe_float(data: dict, *keys) -> float | None:
    """Drill into nested dict safely and return float or None."""
    val = data
    for k in keys:
        if not isinstance(val, dict):
            return None
        val = val.get(k)
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def gather_market_context(pair: str, api_key: str | None = None) -> dict | None:
    """
    Fetch live market data for a currency pair.
    Returns a context dict consumed by agent.py, or None on critical failure.
    Falls back to mock data when api_key is None (dev/test mode).
    """
    if not api_key:
        log.warning(f"No API key — using mock data for {pair}")
        return _mock_context(pair)

    symbol = pair.replace('/', '')

    # ── Price ────────────────────────────────────────────────────────────────
    price_data = _get('price', {'symbol': pair}, api_key)
    price = price_data.get('price')
    if not price:
        log.error(f"Could not fetch price for {pair}. Skipping.")
        return None
    time.sleep(0.5)   # respect free-tier rate limit

    # ── RSI (14, 1h) ─────────────────────────────────────────────────────────
    rsi_data = _get('rsi', {'symbol': pair, 'interval': INTERVAL,
                             'time_period': 14, 'outputsize': 1}, api_key)
    rsi = _safe_float(rsi_data, 'values', 0, 'rsi') if 'values' in rsi_data else None
    time.sleep(0.5)

    # ── ATR (14, 1h) ─────────────────────────────────────────────────────────
    atr_data = _get('atr', {'symbol': pair, 'interval': INTERVAL,
                              'time_period': 14, 'outputsize': 1}, api_key)
    atr = _safe_float(atr_data, 'values', 0, 'atr') if 'values' in atr_data else None
    time.sleep(0.5)

    # ── EMA 50 (1h) ──────────────────────────────────────────────────────────
    ema50_data = _get('ema', {'symbol': pair, 'interval': INTERVAL,
                               'time_period': 50, 'outputsize': 1}, api_key)
    ema50 = _safe_float(ema50_data, 'values', 0, 'ema') if 'values' in ema50_data else None
    time.sleep(0.5)

    # ── EMA 200 (1h) ─────────────────────────────────────────────────────────
    ema200_data = _get('ema', {'symbol': pair, 'interval': INTERVAL,
                                'time_period': 200, 'outputsize': 1}, api_key)
    ema200 = _safe_float(ema200_data, 'values', 0, 'ema') if 'values' in ema200_data else None
    time.sleep(0.5)

    # ── Trend label ──────────────────────────────────────────────────────────
    p = float(price)
    trend = 'Neutral'
    if ema50 and ema200:
        if p > ema50 > ema200:
            trend = 'Bullish'
        elif p < ema50 < ema200:
            trend = 'Bearish'

    return {
        'pair': pair,
        'price': price,
        'indicators': {
            'trend':  trend,
            'rsi':    rsi   or 50.0,
            'atr':    atr   or 0.0050,
            'ema_50': ema50,
            'ema_200': ema200,
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
    }


def _mock_context(pair: str) -> dict:
    """Deterministic mock — used when no API key is available."""
    mock_prices = {
        'EUR/USD': '1.0850', 'GBP/USD': '1.2700', 'USD/JPY': '154.50',
        'AUD/USD': '0.6450', 'USD/CAD': '1.3600', 'EUR/JPY': '167.60',
    }
    price = mock_prices.get(pair, '1.1000')
    return {
        'pair': pair,
        'price': price,
        'indicators': {
            'trend': 'Bullish', 'rsi': 52.0, 'atr': 0.0055,
            'ema_50': float(price) * 0.999,
            'ema_200': float(price) * 0.995,
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        '_mock': True,
    }

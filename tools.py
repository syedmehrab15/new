import requests
import random
from datetime import datetime, timezone

import dateutil.parser

CB_RATES = {
    "USD": {"rate": 4.375, "bias": "Dovish-leaning",   "next_move": "Cut — Jun/Sep 2026", "cb": "Federal Reserve"},
    "EUR": {"rate": 2.00,  "bias": "Neutral / On Hold","next_move": "No change 2026",     "cb": "ECB"},
    "GBP": {"rate": 3.75,  "bias": "Mildly Dovish",    "next_move": "Further cuts 2026",  "cb": "Bank of England"},
    "JPY": {"rate": 0.75,  "bias": "Hawkish outlier",  "next_move": "Hike — Jun 2026",    "cb": "Bank of Japan"},
    "CHF": {"rate": 0.25,  "bias": "Neutral",          "next_move": "No change",           "cb": "SNB"},
    "AUD": {"rate": 4.10,  "bias": "Neutral",          "next_move": "Hold",                "cb": "RBA"},
    "NZD": {"rate": 3.50,  "bias": "Mildly Dovish",    "next_move": "Cut possible",        "cb": "RBNZ"},
    "CAD": {"rate": 2.75,  "bias": "Dovish",           "next_move": "Hold or cut",         "cb": "Bank of Canada"},
}

SESSION_WINDOWS = {
    "Tokyo":    {"open": 0,  "close": 9},
    "London":   {"open": 8,  "close": 17},
    "New York": {"open": 13, "close": 22},
}


# ---------------------------------------------------------------------------
# OHLCV FETCH  (real API with synthetic fallback)
# ---------------------------------------------------------------------------

def fetch_ohlcv(pair: str, api_key: str = "demo", outputsize: int = 20) -> list[dict] | None:
    symbol = pair.replace("/", "")

    if api_key and api_key != "demo":
        try:
            r = requests.get(
                "https://api.twelvedata.com/time_series",
                params={"symbol": symbol, "interval": "1day",
                        "outputsize": outputsize, "apikey": api_key, "format": "JSON"},
                timeout=10,
            )
            data = r.json()
            if "values" in data:
                candles = data["values"]
                # Freshness guard — reject data older than 6 hours
                latest_ts = dateutil.parser.parse(candles[0]["datetime"])
                if latest_ts.tzinfo is None:
                    latest_ts = latest_ts.replace(tzinfo=timezone.utc)
                hours_old = (datetime.now(timezone.utc) - latest_ts).total_seconds() / 3600
                if hours_old > 6:
                    print(f"WARNING: {pair} data is {hours_old:.1f}h old — skipping.")
                    return None
                return candles
        except Exception as e:
            print(f"Twelve Data fetch failed for {pair}: {e} — falling back to synthetic data.")

    # Synthetic fallback — deterministic per pair for reproducible tests
    random.seed(hash(pair) % (2**32))
    base = {"EUR/USD": 1.145, "GBP/USD": 1.325, "USD/JPY": 148.5,
            "GBP/JPY": 196.8, "AUD/USD": 0.638, "USD/CHF": 0.901,
            "USD/CAD": 1.382, "EUR/JPY": 163.0}.get(pair, 1.0)
    candles = []
    for i in range(outputsize):
        spread = base * 0.007
        o = base + random.uniform(-spread, spread)
        h = o + abs(random.uniform(0, spread))
        l = o - abs(random.uniform(0, spread))
        c = random.uniform(l, h)
        candles.append({
            "datetime": datetime.now(timezone.utc).isoformat(),
            "open": str(round(o, 5)), "high": str(round(h, 5)),
            "low":  str(round(l, 5)), "close": str(round(c, 5)),
        })
        base = c
    return candles


# ---------------------------------------------------------------------------
# SESSION CLOCK
# ---------------------------------------------------------------------------

def get_session_context() -> dict:
    hour = datetime.now(timezone.utc).hour
    active = [name for name, w in SESSION_WINDOWS.items() if w["open"] <= hour < w["close"]]

    if "London" in active and "New York" in active:
        note = "London/NY overlap — maximum liquidity. Institutional flow dominant. Best entry window."
    elif "London" in active:
        note = "London session — high EUR/GBP volume. Trend day likely."
    elif "New York" in active:
        note = "New York session — USD-driven. Watch 14:00–16:00 UTC for fixing flows."
    elif "Tokyo" in active:
        note = "Tokyo session — JPY/AUD active. Thin liquidity on EUR/USD."
    else:
        note = "Inter-session gap — low liquidity. Fake-outs common. Avoid breakout entries."

    return {
        "utc_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "active_sessions": active or ["Inter-session gap"],
        "liquidity_note": note,
    }


# ---------------------------------------------------------------------------
# ATR CALCULATOR  (14-period daily)
# ---------------------------------------------------------------------------

def calculate_atr(pair: str, api_key: str = "demo", period: int = 14) -> dict:
    candles = fetch_ohlcv(pair, api_key=api_key, outputsize=period + 5)
    if not candles or len(candles) < period + 1:
        return {"error": "Insufficient data for ATR", "pair": pair}

    pip_mult = 100 if "JPY" in pair else 10000
    trs = []
    for i in range(1, len(candles)):
        try:
            h, l, pc = float(candles[i]["high"]), float(candles[i]["low"]), float(candles[i - 1]["close"])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        except (ValueError, KeyError):
            continue

    if len(trs) < period:
        return {"error": "ATR calc failed", "pair": pair}

    atr_price = sum(trs[-period:]) / period
    atr_pips  = round(atr_price * pip_mult, 1)
    price     = float(candles[0]["close"])

    return {
        "pair": pair,
        "atr_pips": atr_pips,
        "atr_price": round(atr_price, 6),
        "current_price": round(price, 5),
        "recommended_stop_pips": round(atr_pips * 1.2, 1),
        "tight_stop_pips": round(atr_pips * 0.8, 1),
    }


# ---------------------------------------------------------------------------
# PIVOT LEVEL DETECTOR  (classic floor pivots from yesterday's candle)
# ---------------------------------------------------------------------------

def calculate_pivots(pair: str, api_key: str = "demo") -> dict:
    candles = fetch_ohlcv(pair, api_key=api_key, outputsize=3)
    if not candles or len(candles) < 2:
        return {"error": "No data for pivots", "pair": pair}

    try:
        prev = candles[1]
        H, L, C = float(prev["high"]), float(prev["low"]), float(prev["close"])
    except (IndexError, KeyError, ValueError):
        return {"error": "Bad candle data", "pair": pair}

    dp = 3 if "JPY" in pair else 5
    fmt = lambda v: round(v, dp)

    PP = (H + L + C) / 3
    return {
        "pair": pair,
        "PP": fmt(PP),
        "R1": fmt(2 * PP - L),
        "R2": fmt(PP + H - L),
        "R3": fmt(H + 2 * (PP - L)),
        "S1": fmt(2 * PP - H),
        "S2": fmt(PP - (H - L)),
        "S3": fmt(L - 2 * (H - PP)),
    }


# ---------------------------------------------------------------------------
# CENTRAL BANK BIAS
# ---------------------------------------------------------------------------

def get_cb_bias(pair: str) -> dict:
    parts = pair.upper().replace("-", "/").split("/")
    if len(parts) != 2:
        return {"error": f"Cannot parse pair: {pair}"}
    b_ccy, q_ccy = parts
    b = CB_RATES.get(b_ccy, {"rate": None, "bias": "Unknown", "next_move": "Unknown", "cb": "Unknown"})
    q = CB_RATES.get(q_ccy, {"rate": None, "bias": "Unknown", "next_move": "Unknown", "cb": "Unknown"})

    diff = round(b["rate"] - q["rate"], 3) if b["rate"] and q["rate"] else None
    if diff is None:
        carry = "Insufficient rate data."
    elif diff > 0:
        carry = f"{b_ccy} yields {diff:.2f}% more. Long {pair} earns positive carry."
    elif diff < 0:
        carry = f"{q_ccy} yields {abs(diff):.2f}% more. Long {pair} is a carry drag — needs strong momentum."
    else:
        carry = "Rate differential flat. Carry neutral."

    return {
        "pair": pair,
        "base":  {"currency": b_ccy, "cb": b["cb"], "rate": b["rate"], "bias": b["bias"], "next_move": b["next_move"]},
        "quote": {"currency": q_ccy, "cb": q["cb"], "rate": q["rate"], "bias": q["bias"], "next_move": q["next_move"]},
        "rate_differential_pct": diff,
        "carry_note": carry,
    }


# ---------------------------------------------------------------------------
# AGGREGATE
# ---------------------------------------------------------------------------

def gather_market_context(pair: str, api_key: str = "demo") -> dict:
    return {
        "session": get_session_context(),
        "atr":     calculate_atr(pair, api_key=api_key),
        "pivots":  calculate_pivots(pair, api_key=api_key),
        "cb_bias": get_cb_bias(pair),
    }

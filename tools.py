import requests
import time
import dateutil.parser
from datetime import datetime, timezone

def fetch_ohlcv(pair, api_key="demo"):
    """Fetches price data and enforces a 6-hour freshness safeguard."""
    # Note: In production, this would call Twelve Data or similar API
    # For this implementation, we simulate the API response structure
    mock_data = {
        "values": [
            {
                "datetime": datetime.now(timezone.utc).isoformat(),
                "close": "1.0850" if "EUR" in pair else "1.2500"
            }
        ]
    }
    
    if "values" in mock_data:
        candles = mock_data["values"]
        latest_candle_time = dateutil.parser.parse(candles[0]["datetime"])
        
        if latest_candle_time.tzinfo is None:
             latest_candle_time = latest_candle_time.replace(tzinfo=timezone.utc)

        hours_old = (datetime.now(timezone.utc) - latest_candle_time).total_seconds() / 3600

        if hours_old > 6:
            print(f"CRITICAL: Data for {pair} is {hours_old:.1f} hours old. Aborting.")
            return None

        return candles
    return None

def gather_market_context(pair, api_key="demo"):
    """Simulates gathering full technical context for the agent."""
    return {
        'pair': pair,
        'session': {'name': 'London/NY Overlap', 'volatility': 'High'},
        'price': '1.0850' if 'EUR' in pair else '1.2500',
        'change_24h': '+0.45%',
        'rsi': '58',
        'atr': '0.0075',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

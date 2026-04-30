import os

class Config:
    ANTHROPIC_API_KEY   = os.getenv('ANTHROPIC_API_KEY')
    TWELVE_DATA_API_KEY = os.getenv('TWELVE_DATA_API_KEY')
    SLACK_WEBHOOK_URL   = os.getenv('SLACK_WEBHOOK_URL')        # optional
    MODEL               = 'claude-sonnet-4-5'
    DB_FILE             = os.getenv('DB_FILE', 'fx_agent.db')

    # How often to run a full market scan (seconds)
    SCAN_INTERVAL_SECONDS = int(os.getenv('SCAN_INTERVAL_SECONDS', 3600))

    # Strategy weights (must sum conceptually — weights are relative)
    STRATEGY_WEIGHTS = {
        'TrendFollowing_EMA': 0.6,
        'MeanReversion_RSI':  0.4,
    }

    # Risk management defaults
    ATR_STOP_MULTIPLIER   = float(os.getenv('ATR_STOP_MULTIPLIER', 1.5))
    ATR_TARGET_MULTIPLIER = float(os.getenv('ATR_TARGET_MULTIPLIER', 3.0))

    # Twelve Data rate-limit guard (free tier = 8 req/min)
    API_CALL_DELAY = float(os.getenv('API_CALL_DELAY', 8.0))

    @classmethod
    def validate(cls):
        missing = []
        if not cls.ANTHROPIC_API_KEY:
            missing.append('ANTHROPIC_API_KEY')
        if not cls.TWELVE_DATA_API_KEY:
            missing.append('TWELVE_DATA_API_KEY')
        if missing:
            raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")

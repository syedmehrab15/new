from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

class KeyLevels(BaseModel):
    resistance: List[str]
    support: List[str]

class TradeSetup(BaseModel):
    direction: str = Field(pattern="^(Long|Short|Neutral)$")
    entry: str
    stop_loss: str
    take_profit_1: str
    risk_reward: str
    stop_atr_ratio: str

class TradeBrief(BaseModel):
    pair: str
    macro_bias: str
    confidence: int = Field(ge=0, le=100)
    session_context: str
    interest_rate_differential: str
    risk_environment: str
    key_levels: KeyLevels
    trade_setup: TradeSetup
    carry_trade_note: str
    veterans_warning: str
    correlation_warning: Optional[str] = None

    # Internal metadata fields
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = Field(default="pending_approval")

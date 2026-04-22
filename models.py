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
    stop_loss_pips: float
    take_profit_1: str
    take_profit_2: Optional[str] = None
    risk_reward: str
    atr_daily_pips: Optional[float] = None
    stop_atr_ratio: Optional[str] = None


class TradeBrief(BaseModel):
    pair: str
    macro_bias: str
    bias_strength: str = Field(pattern="^(High|Medium|Low)$")
    confidence: int = Field(ge=0, le=100)
    session_context: str
    interest_rate_differential: str
    risk_environment: str = Field(pattern="^(Risk-On|Risk-Off|Mixed)$")
    key_levels: KeyLevels
    trade_setup: TradeSetup
    carry_trade_note: str
    veterans_warning: str
    correlation_warning: Optional[str] = None

    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    status: str = Field(default="pending_approval")

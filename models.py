from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timezone

class KeyLevels(BaseModel):
    resistance: List[str]
    support: List[str]

class Signal(BaseModel):
    strategy_name: str
    direction: str = Field(pattern='^(Long|Short|Neutral)$')
    confidence: int = Field(ge=0, le=100)
    rationale: str

class TradeSetup(BaseModel):
    direction: str = Field(pattern='^(Long|Short|Neutral)$')
    entry: str
    stop_loss: str
    take_profit_1: str
    risk_reward: str
    stop_atr_ratio: float
    atr_value: float

class TradeBrief(BaseModel):
    pair: str
    macro_bias: str
    confidence: int = Field(ge=0, le=100)
    signals: List[Signal] = Field(default_factory=list)
    trade_setup: Optional[TradeSetup] = None
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = Field(default='pending_approval')

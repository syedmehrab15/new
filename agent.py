"""
agent.py — FX Agent Orchestrator
Runs a multi-strategy Claude analysis pipeline for each currency pair,
aggregates signals with confidence weighting, and persists structured TradeBriefs.
"""

import json
import logging
import time

import anthropic
import requests

from config import Config
from models import TradeBrief, Signal, TradeSetup, KeyLevels
from database import init_db, save_brief
from tools import gather_market_context
from prompts import SYSTEM_PROMPT, DEFAULT_PAIRS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s — %(message)s'
)
log = logging.getLogger('fx_agent')

# ── Tool schema (forces Claude to return structured JSON) ─────────────────────
TRADE_BRIEF_TOOL = {
    'name': 'submit_trade_brief',
    'description': 'Submit a standardised trade brief based on market analysis.',
    'input_schema': TradeBrief.model_json_schema(),
}


# ── Aggregator ────────────────────────────────────────────────────────────────
class Aggregator:
    @staticmethod
    def calculate_consensus(signals: list[Signal]) -> tuple[str, int]:
        """
        Weighted consensus that accounts for both strategy weight and
        per-signal confidence.  Returns (direction, consensus_confidence).
        """
        weighted_score = 0.0
        total_weight   = 0.0

        for sig in signals:
            strategy_w  = Config.STRATEGY_WEIGHTS.get(sig.strategy_name, 0.5)
            confidence_w = sig.confidence / 100.0
            combined_w   = strategy_w * confidence_w
            val = 1 if sig.direction == 'Long' else (-1 if sig.direction == 'Short' else 0)
            weighted_score += val * combined_w
            total_weight   += combined_w

        if total_weight == 0:
            return 'Neutral', 0

        normalised = weighted_score / total_weight

        if abs(normalised) < 0.2:
            return 'Neutral', 0

        direction  = 'Long' if normalised > 0 else 'Short'
        confidence = int(min(abs(normalised) * 100, 100))
        return direction, confidence


# ── Claude API call ───────────────────────────────────────────────────────────
def analyze_with_claude(
    pair: str,
    ctx: dict,
    strategy_type: str,
    client: anthropic.Anthropic,
) -> Signal:
    """
    Calls Claude to generate a single strategy signal.
    Uses tool_choice to force structured output via submit_trade_brief.
    """
    prompt = (
        f"Analyse {pair} using a {strategy_type} strategy.\n"
        f"Market data: {json.dumps(ctx, indent=2)}"
    )

    try:
        response = client.messages.create(
            model=Config.MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=[TRADE_BRIEF_TOOL],
            tool_choice={'type': 'tool', 'name': 'submit_trade_brief'},
            messages=[{'role': 'user', 'content': prompt}],
        )

        # Find the tool_use block
        tool_block = next(
            (b for b in response.content if b.type == 'tool_use'), None
        )
        if not tool_block:
            raise ValueError("No tool_use block in response")

        inp = tool_block.input
        return Signal(
            strategy_name=strategy_type,
            direction=inp.get('trade_setup', {}).get('direction', 'Neutral'),
            confidence=inp.get('confidence', 50),
            rationale=inp.get('macro_bias', 'AI generated signal'),
        )

    except Exception as e:
        log.error(f"Claude error [{pair} / {strategy_type}]: {e}")
        return Signal(
            strategy_name=strategy_type,
            direction='Neutral',
            confidence=0,
            rationale=f'API error: {e}',
        )


# ── ATR-based risk management ─────────────────────────────────────────────────
def build_trade_setup(direction: str, ctx: dict) -> TradeSetup:
    price = float(ctx['price'])
    atr   = float(ctx['indicators'].get('atr') or 0.0050)
    stop_mult   = Config.ATR_STOP_MULTIPLIER
    target_mult = Config.ATR_TARGET_MULTIPLIER

    if direction == 'Long':
        stop_loss   = price - (stop_mult   * atr)
        take_profit = price + (target_mult * atr)
    elif direction == 'Short':
        stop_loss   = price + (stop_mult   * atr)
        take_profit = price - (target_mult * atr)
    else:
        stop_loss   = price
        take_profit = price

    rr = target_mult / stop_mult  # e.g. 3.0/1.5 = 1:2
    return TradeSetup(
        direction=direction,
        entry=str(round(price, 5)),
        stop_loss=str(round(stop_loss, 5)),
        take_profit_1=str(round(take_profit, 5)),
        risk_reward=f'1:{rr:.1f}',
        stop_atr_ratio=stop_mult,
        atr_value=atr,
    )


# ── Slack notification ────────────────────────────────────────────────────────
def send_slack_alert(brief: TradeBrief) -> None:
    url = Config.SLACK_WEBHOOK_URL
    if not url:
        return
    direction = brief.trade_setup.direction if brief.trade_setup else 'Neutral'
    emoji = '🟢' if direction == 'Long' else ('🔴' if direction == 'Short' else '⚪')
    text = (
        f"{emoji} *FX Signal — {brief.pair}*\n"
        f"> Direction: *{direction}* | Confidence: *{brief.confidence}%*\n"
        f"> {brief.macro_bias}\n"
        f"> Entry: `{brief.trade_setup.entry if brief.trade_setup else 'N/A'}` | "
        f"SL: `{brief.trade_setup.stop_loss if brief.trade_setup else 'N/A'}` | "
        f"TP: `{brief.trade_setup.take_profit_1 if brief.trade_setup else 'N/A'}`"
    )
    try:
        requests.post(url, json={'text': text}, timeout=5)
    except Exception as e:
        log.warning(f"Slack alert failed: {e}")


# ── Main scan ────────────────────────────────────────────────────────────────
def run_full_market_scan() -> None:
    init_db(Config.DB_FILE)
    Config.validate()

    client = anthropic.Anthropic(api_key=Config.ANTHROPIC_API_KEY)
    log.info(f"Starting market scan — {len(DEFAULT_PAIRS)} pairs")

    for pair in DEFAULT_PAIRS:
        log.info(f"── Analysing {pair} ──")

        ctx = gather_market_context(pair, Config.TWELVE_DATA_API_KEY)
        if not ctx:
            log.warning(f"Skipping {pair} — no market data")
            continue

        # Multi-strategy Claude calls
        signals = [
            analyze_with_claude(pair, ctx, 'TrendFollowing_EMA', client),
            analyze_with_claude(pair, ctx, 'MeanReversion_RSI',  client),
        ]

        direction, confidence = Aggregator.calculate_consensus(signals)
        setup = build_trade_setup(direction, ctx)

        brief = TradeBrief(
            pair=pair,
            macro_bias=(
                f"Consensus from {len(signals)} strategy agents. "
                f"Trend: {ctx['indicators']['trend']} | "
                f"RSI: {ctx['indicators']['rsi']:.1f} | "
                f"ATR: {ctx['indicators']['atr']:.5f}"
            ),
            confidence=confidence,
            signals=signals,
            trade_setup=setup,
        )

        save_brief(brief, Config.DB_FILE)
        send_slack_alert(brief)

        log.info(
            f"✓ {pair} → {direction} ({confidence}%) | "
            f"Entry {setup.entry} SL {setup.stop_loss} TP {setup.take_profit_1}"
        )

        # Rate-limit guard between pairs
        time.sleep(Config.API_CALL_DELAY)

    log.info("Market scan complete.")


if __name__ == '__main__':
    run_full_market_scan()

import os
import json
import time
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import ValidationError

from models import TradeBrief
from prompts import SYSTEM_PROMPT, DEFAULT_PAIRS
from database import init_db, save_brief
from tools import gather_market_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fx_agent")

TWELVE_DATA_KEY = os.getenv("TWELVE_DATA_API_KEY", "demo")

MODEL = "claude-sonnet-4-5-20250929"

TRADE_BRIEF_TOOL = {
    "name": "submit_trade_brief",
    "description": "Submits a strictly formatted FX trade brief.",
    "input_schema": TradeBrief.model_json_schema(),
}


# FIX: retry wrapper — handles 529 overload and transient 5xx errors
@retry(
    retry=retry_if_exception_type(anthropic.APIStatusError),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _call_claude(client: anthropic.Anthropic, ctx: dict) -> anthropic.types.Message:
    return client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[TRADE_BRIEF_TOOL],
        tool_choice={"type": "tool", "name": "submit_trade_brief"},
        messages=[{
            "role": "user",
            "content": f"Analyze this market data and submit a trade brief:\n{json.dumps(ctx)}",
        }],
    )


def analyze_pair(pair: str, client: anthropic.Anthropic) -> TradeBrief | None:
    log.info(f"Analyzing {pair}...")
    ctx = gather_market_context(pair, TWELVE_DATA_KEY)

    try:
        response = _call_claude(client, ctx)
    except anthropic.APIStatusError as e:
        log.error(f"  ✗ {pair} — API error after retries: {e.status_code} {e.message}")
        return None
    except Exception as e:
        log.error(f"  ✗ {pair} — Unexpected error: {e}")
        return None

    # FIX: explicit warning when Claude returns no tool_use block
    tool_block = next(
        (c for c in response.content if c.type == "tool_use" and c.name == "submit_trade_brief"),
        None,
    )
    if tool_block is None:
        log.warning(
            f"  ✗ {pair} — Claude did not return a tool_use block. "
            f"Stop reason: {response.stop_reason}. "
            f"Content types: {[c.type for c in response.content]}"
        )
        return None

    try:
        brief = TradeBrief(**tool_block.input)
        log.info(f"  ✓ {pair} — {brief.trade_setup.direction} | Confidence: {brief.confidence}%")
        return brief
    except ValidationError as ve:
        log.error(f"  ✗ {pair} — Pydantic validation failed:\n{ve}")
        return None


def run_analysis(pairs: list[str] = None):
    init_db()
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        log.error("CRITICAL: ANTHROPIC_API_KEY environment variable is not set.")
        return []

    client = anthropic.Anthropic(api_key=key)
    pairs_to_run = pairs or DEFAULT_PAIRS
    results = []

    log.info(f"Starting analysis — {len(pairs_to_run)} pair(s) | Model: {MODEL}")
    for i, pair in enumerate(pairs_to_run):
        brief = analyze_pair(pair, client)
        if brief:
            save_brief(brief)
            results.append(brief)
        if i < len(pairs_to_run) - 1:
            time.sleep(1)

    log.info(f"Run complete: {len(results)}/{len(pairs_to_run)} briefs generated.")
    return results


if __name__ == "__main__":
    run_analysis()

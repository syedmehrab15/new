import os
import json
import time
import logging
import anthropic
from pydantic import ValidationError
from models import TradeBrief
from prompts import SYSTEM_PROMPT, DEFAULT_PAIRS
from database import init_db, save_brief
from tools import gather_market_context

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('fx_agent')

# API Configuration
TWELVE_DATA_KEY = os.getenv('TWELVE_DATA_API_KEY', 'demo')
MODEL = 'claude-sonnet-4-5-20250929' # Using a supported model string

# Pydantic Integration for Tool Schema
TRADE_BRIEF_TOOL = {
    'name': 'submit_trade_brief',
    'description': 'Submits a strictly formatted FX trade brief.',
    'input_schema': TradeBrief.model_json_schema()
}

def analyze_pair(pair: str, client: anthropic.Anthropic) -> TradeBrief | None:
    log.info(f'Analyzing {pair}...')
    ctx = gather_market_context(pair, TWELVE_DATA_KEY)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            tools=[TRADE_BRIEF_TOOL],
            tool_choice={'type': 'tool', 'name': 'submit_trade_brief'},
            messages=[{'role': 'user', 'content': f'Analyze this data and submit a brief: {json.dumps(ctx)}'}]
        )

        for content in response.content:
            if content.type == 'tool_use' and content.name == 'submit_trade_brief':
                # Validates Claude\'s output against the Pydantic model
                brief = TradeBrief(**content.input)
                log.info(f'  ✓ {pair} — {brief.trade_setup.direction}')
                return brief
        return None
    except ValidationError as ve:
        log.error(f'  ✗ {pair} — Schema Validation Error: {ve}')
        return None
    except Exception as e:
        log.error(f'  ✗ {pair} — Error: {str(e)}')
        return None

def run_analysis(pairs: list[str] = None):
    init_db()
    key = os.getenv('ANTHROPIC_API_KEY')
    if not key:
        log.error('CRITICAL: ANTHROPIC_API_KEY is missing.')
        return

    client = anthropic.Anthropic(api_key=key)
    pairs_to_run = pairs or DEFAULT_PAIRS

    for pair in pairs_to_run:
        brief = analyze_pair(pair, client)
        if brief:
            save_brief(brief)
        time.sleep(1)

if __name__ == "__main__":
    run_analysis()

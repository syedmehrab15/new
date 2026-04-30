import os, time, anthropic
from models import TradeBrief
from database import init_db, save_brief
from tools import gather_market_context
from prompts import DEFAULT_PAIRS

def run_full_market_scan():
    init_db()
    print('Market scan initialized...')

if __name__ == '__main__':
    run_full_market_scan()

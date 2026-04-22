import os
import anthropic
from flask import Flask, render_template_string, request
from agent import analyze_pair
from database import save_brief
from prompts import DEFAULT_PAIRS

app = Flask(__name__)

# Production Configuration
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>FX Trade AI - Production</title>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 20px; background: #f8f9fa; }
        .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); display: inline-block; max-width: 500px; width: 100%; }
        h2 { color: #2c3e50; margin-bottom: 25px; }
        select, button { width: 100%; padding: 14px; margin: 12px 0; border-radius: 8px; border: 1px solid #ddd; font-size: 16px; box-sizing: border-box; }
        button { background: #007bff; color: white; border: none; font-weight: bold; cursor: pointer; transition: background 0.2s; }
        button:hover { background: #0056b3; }
        .result { text-align: left; margin-top: 30px; padding: 20px; border-top: 2px solid #f1f1f1; border-radius: 0 0 8px 8px; background: #fff; }
        .stat-row { display: flex; justify-content: space-between; margin-bottom: 10px; }
        .label { font-weight: bold; color: #666; }
        .value { color: #333; }
        .bias { font-style: italic; color: #555; background: #fdfdfe; padding: 10px; border-left: 4px solid #007bff; margin: 15px 0; }
    </style>
</head>
<body>
    <div class='card'>
        <h2>📈 FX Production Agent</h2>
        <form method='POST'>
            <select name='pair'>
                {% for p in pairs %}<option value='{{p}}' {% if p == selected_pair %}selected{% endif %}>{{p}}</option>{% endfor %}
            </select>
            <button type='submit'>Run Expert Analysis</button>
        </form>
        {% if brief %}
        <div class='result'>
            <div class='stat-row'><span class='label'>Pair:</span> <span class='value'>{{brief.pair}}</span></div>
            <div class='stat-row'><span class='label'>Direction:</span> <span class='value' style='color:{{"green" if brief.trade_setup.direction == "Long" else "red"}}'>{{brief.trade_setup.direction}}</span></div>
            <div class='stat-row'><span class='label'>Confidence:</span> <span class='value'>{{brief.confidence}}%</span></div>
            <div class='bias'>{{brief.macro_bias}}</div>
            <div class='stat-row'><span class='label'>Entry:</span> <span class='value'>{{brief.trade_setup.entry}}</span></div>
            <div class='stat-row'><span class='label'>Stop Loss:</span> <span class='value'>{{brief.trade_setup.stop_loss}}</span></div>
            <div class='stat-row'><span class='label'>Target:</span> <span class='value'>{{brief.trade_setup.take_profit_1}}</span></div>
        </div>
        {% endif %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def home():
    brief = None
    pair = None
    if request.method == 'POST':
        pair = request.form.get('pair')
        if not ANTHROPIC_API_KEY:
            return "Error: ANTHROPIC_API_KEY environment variable not set.", 500
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        brief = analyze_pair(pair, client)
        if brief:
            save_brief(brief)
            
    return render_template_string(HTML_TEMPLATE, pairs=DEFAULT_PAIRS, brief=brief, selected_pair=pair)

if __name__ == '__main__':
    # Bind to PORT provided by environment (Render/Heroku standard)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
"

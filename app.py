import os
import anthropic
from flask import Flask, render_template_string, request, jsonify

from agent import analyze_pair
from database import init_db, save_brief, update_brief_status, load_briefs
from prompts import DEFAULT_PAIRS

app = Flask(__name__)
init_db()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# FIX: initialise once at module level — not on every request
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>FX Trade AI</title>
    <meta name='viewport' content='width=device-width, initial-scale=1'>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
        .card { background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.07); padding: 28px; max-width: 540px; margin: 0 auto; }
        h2 { color: #1a1a2e; margin: 0 0 20px; font-size: 20px; }
        select, button { width: 100%; padding: 12px 14px; margin: 8px 0; border-radius: 8px; border: 1px solid #ddd; font-size: 15px; }
        button { background: #2563eb; color: #fff; border: none; font-weight: 600; cursor: pointer; }
        button:hover { background: #1d4ed8; }
        button:disabled { background: #93c5fd; cursor: not-allowed; }
        .result { margin-top: 24px; border-top: 1px solid #f0f0f0; padding-top: 20px; }
        .row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; border-bottom: 1px solid #fafafa; }
        .label { color: #6b7280; font-weight: 500; }
        .long  { color: #16a34a; font-weight: 600; }
        .short { color: #dc2626; font-weight: 600; }
        .bias { background: #f0f7ff; border-left: 3px solid #2563eb; padding: 10px 14px; margin: 14px 0; font-size: 13px; color: #374151; border-radius: 0 6px 6px 0; }
        .warn { background: #fffbeb; border-left: 3px solid #f59e0b; padding: 10px 14px; margin: 10px 0; font-size: 13px; color: #374151; border-radius: 0 6px 6px 0; }
        .approve-row { display: flex; gap: 8px; margin-top: 16px; }
        .approve-row button { margin: 0; font-size: 13px; padding: 8px; }
        .btn-approve { background: #16a34a; }
        .btn-approve:hover { background: #15803d; }
        .btn-reject  { background: #dc2626; }
        .btn-reject:hover  { background: #b91c1c; }
        .status-badge { font-size: 12px; padding: 3px 10px; border-radius: 20px; font-weight: 600; display: inline-block; margin-top: 8px; }
        .pending  { background: #fef3c7; color: #92400e; }
        .approved { background: #d1fae5; color: #065f46; }
        .rejected { background: #fee2e2; color: #991b1b; }
        .error { color: #dc2626; padding: 12px; background: #fee2e2; border-radius: 8px; margin-top: 12px; font-size: 14px; }
    </style>
</head>
<body>
<div class='card'>
    <h2>FX Production Agent</h2>
    <form method='POST'>
        <select name='pair'>
            {% for p in pairs %}<option value='{{p}}' {% if p == selected %}selected{% endif %}>{{p}}</option>{% endfor %}
        </select>
        <button type='submit'>Run Expert Analysis</button>
    </form>

    {% if error %}
    <div class='error'>{{ error }}</div>
    {% endif %}

    {% if brief %}
    <div class='result'>
        <div class='row'><span class='label'>Pair</span><span>{{ brief.pair }}</span></div>
        <div class='row'>
            <span class='label'>Direction</span>
            <span class='{{ "long" if brief.trade_setup.direction == "Long" else "short" }}'>
                {{ brief.trade_setup.direction }}
            </span>
        </div>
        <div class='row'><span class='label'>Confidence</span><span>{{ brief.confidence }}%</span></div>
        <div class='row'><span class='label'>Bias strength</span><span>{{ brief.bias_strength }}</span></div>
        <div class='row'><span class='label'>Risk environment</span><span>{{ brief.risk_environment }}</span></div>
        <div class='bias'>{{ brief.macro_bias }}</div>
        <div class='row'><span class='label'>Entry</span><span>{{ brief.trade_setup.entry }}</span></div>
        <div class='row'><span class='label'>Stop loss</span><span>{{ brief.trade_setup.stop_loss }} ({{ brief.trade_setup.stop_loss_pips }} pips)</span></div>
        <div class='row'><span class='label'>TP1</span><span>{{ brief.trade_setup.take_profit_1 }}</span></div>
        {% if brief.trade_setup.take_profit_2 %}
        <div class='row'><span class='label'>TP2</span><span>{{ brief.trade_setup.take_profit_2 }}</span></div>
        {% endif %}
        <div class='row'><span class='label'>R/R</span><span>{{ brief.trade_setup.risk_reward }}</span></div>
        <div class='warn'>{{ brief.veterans_warning }}</div>
        <span class='status-badge {{ brief.status }}'>{{ brief.status.replace("_", " ") }}</span>

        <div class='approve-row'>
            <button class='btn-approve'
                onclick="updateStatus('{{ brief.pair }}', '{{ brief.generated_at }}', 'approved')">
                Approve
            </button>
            <button class='btn-reject'
                onclick="updateStatus('{{ brief.pair }}', '{{ brief.generated_at }}', 'rejected')">
                Reject
            </button>
        </div>
    </div>
    {% endif %}
</div>

<script>
async function updateStatus(pair, generatedAt, newStatus) {
    const res = await fetch('/approve', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({pair, generated_at: generatedAt, status: newStatus})
    });
    const data = await res.json();
    if (data.ok) {
        document.querySelector('.status-badge').textContent = newStatus.replace('_', ' ');
        document.querySelector('.status-badge').className = 'status-badge ' + newStatus;
    } else {
        alert('Update failed: ' + (data.error || 'unknown error'));
    }
}
</script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def home():
    brief = None
    error = None
    selected = None

    if request.method == "POST":
        selected = request.form.get("pair")
        if not client:
            error = "ANTHROPIC_API_KEY is not configured."
        else:
            result = analyze_pair(selected, client)
            if result:
                save_brief(result)
                brief = result.model_dump()
            else:
                error = f"Analysis failed for {selected}. Check server logs."

    return render_template_string(
        HTML_TEMPLATE,
        pairs=DEFAULT_PAIRS,
        brief=brief,
        selected=selected,
        error=error,
    )


@app.route("/approve", methods=["POST"])
def approve():
    """Approve or reject a brief from the web UI."""
    data = request.get_json(force=True)
    pair         = data.get("pair")
    generated_at = data.get("generated_at")
    status       = data.get("status")

    if not all([pair, generated_at, status]):
        return jsonify({"ok": False, "error": "Missing fields"}), 400
    if status not in ("approved", "rejected"):
        return jsonify({"ok": False, "error": "Invalid status"}), 400

    updated = update_brief_status(pair, generated_at, status, note="Updated via web UI")
    if updated:
        return jsonify({"ok": True, "status": status})
    return jsonify({"ok": False, "error": "Brief not found"}), 404


@app.route("/briefs")
def briefs_list():
    """Simple JSON endpoint for the audit log."""
    status = request.args.get("status")  # ?status=approved
    return jsonify(load_briefs(status=status))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

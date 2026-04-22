# 📈 Production FX Trading Agent

This is a production-grade FX analysis agent that uses Claude (Anthropic) to generate trade briefs based on market data. It features Pydantic validation, a thread-safe SQLite database, and a Flask web interface.

## 🚀 Deployment to Render

To deploy this application to [Render](https://render.com):

1.  **Create a Web Service**: Point Render to your GitHub repository containing these files.
2.  **Environment Variables**: Navigate to the **Settings** tab in your Render dashboard, find the **Environment Variables** section, and add:
    *   `ANTHROPIC_API_KEY`: Your official Anthropic API key.
3.  **Build & Start**: Render will automatically detect the `Procfile` and use `gunicorn app:app` to start the server.

## 🛠️ Project Structure

*   `app.py`: The Flask web application entry point.
*   `agent.py`: Orchestrator for analyzing currency pairs using AI.
*   `models.py`: Pydantic schemas for strict data validation.
*   `database.py`: SQLite logic for thread-safe storage of trade briefs.
*   `tools.py`: Data fetching logic with stale-data safeguards.
*   `prompts.py`: System instructions and configuration.
*   `requirements.txt`: Python dependencies.

## 💻 Local Testing

To run the app locally for testing:

1.  Install dependencies: `pip install -r requirements.txt`
2.  Set your API key: `export ANTHROPIC_API_KEY='your-key-here'` (Linux/Mac) or `set ANTHROPIC_API_KEY='your-key-here'` (Windows).
3.  Run the server: `python app.py`
4.  Open `http://localhost:5000` in your browser.

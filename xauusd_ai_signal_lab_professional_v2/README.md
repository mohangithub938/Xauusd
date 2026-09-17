# XAUUSD AI Signal Lab — Professional Dashboard + AI Copilot

## What this build includes

This build keeps the true BiQuote SignalR tick-stream engine and upgrades the front end into a professional dark trading dashboard.

### Live market engine
- BiQuote SignalR XAUUSD tick stream
- Persistent background stream with reconnects
- Local 1-minute candle builder from incoming ticks
- 5m / 15m / 1H / 4H aggregation
- Multi-timeframe strategy confirmation
- Technical indicators, structure and regime detection
- Deterministic Entry / SL / TP calculation
- SCALP R:R remains exactly 1:2

### Professional dashboard
- Dark, card-based trading terminal layout
- Live stream status and tick counter
- Price, signal, score and regime KPI strip
- Main candlestick chart with EMA/VWAP
- Recorded BUY/SELL markers from the signal journal
- Signal cockpit with Entry / SL / TP / R:R
- Signal Radar showing recent qualified signals
- Separate Overview, AI Copilot, Signal Journal and Backtest tabs

### AI Copilot
Use the **AI Copilot** tab to ask questions using Groq, grounded in the current app state and the latest recorded signal journal.

Examples:
- "Did I miss any strong signals recently?"
- "Why is the app showing WAIT right now?"
- "What was the last qualified signal?"
- "What changed in the last few recorded signals?"
- "Explain the current XAUUSD setup in simple terms."

The copilot explicitly distinguishes between recorded signals and signals that cannot be verified because they happened before the app was running or were never recorded.

### Automatic Groq + Gmail
When automatic Gmail alerts are enabled and a new strong BUY/SELL signal qualifies:
1. Python calculates the signal and fixed trade levels.
2. Groq automatically explains the structured snapshot.
3. Gmail sends the technical signal plus Groq explanation.

The manual `Generate Groq analysis now` button from older builds is no longer required for alerting. The AI Copilot is the main interactive AI interface.

## Run on Windows

```powershell
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
python preflight.py
streamlit run app/ui/dashboard.py
```

Or double-click `run_app.bat`.

## Configuration

You can enter credentials in the sidebar, or place them in `.env` using `.env.example`.

- `GROQ_API_KEY`
- `GROQ_MODEL`
- `GMAIL_SENDER`
- `GMAIL_APP_PASSWORD`
- `GMAIL_RECIPIENT`

Gmail uses a Google App Password.

## Important limits

- The feed is BiQuote XAUUSD, not the user's VolNex execution feed. Compare prices with VolNex before relying on signals.
- The application does not place trades.
- The signal score is a rule-strength score, not a calibrated win probability.
- The journal only contains signals recorded by this app; the copilot cannot prove an unrecorded historical signal was missed.
- Backtesting is a simplified research tool and is not proof of future performance.


## Professional UI v2
Light theme with dedicated Market, Signals, AI Copilot, Backtest and Settings workspaces. The SignalR tick stream remains independent from dashboard refresh.

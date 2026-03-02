# Crypto Dream Bot

Python-based cryptocurrency trading bot and live dashboard using CoinSpot.

## Setup

1. **Activate virtual environment:**
   ```bash
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # macOS/Linux
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure API credentials in `.env`:**
   ```env
   COINSPOT_API_KEY=your-api-key
   COINSPOT_API_SECRET=your-secret
   OPENAI_API_KEY=your-openai-key
   FLASK_SECRET_KEY=your-secret-key
   FLASK_DEBUG=0
   ```

## Running

```bash
python main.py
```

Then open `http://127.0.0.1:5000`.

## Deploy on Render (24/7)

This repo includes a Render Blueprint file at `render.yaml`.

1. Push this repository to GitHub.
2. In Render, create a **New Blueprint** and select the repo.
3. Set secret env vars in Render:
   - `COINSPOT_API_KEY`
   - `COINSPOT_API_SECRET`
   - `OPENAI_API_KEY`
4. Deploy.

Production start command:

```bash
gunicorn --worker-class eventlet --workers 1 --bind 0.0.0.0:$PORT main:app
```

Notes:
- Background price stream + auto-trading loop start automatically at runtime.
- `logs/trades/order_events.jsonl` is persisted via Render disk mount (`/opt/render/project/src/logs`).
- Keep `FLASK_DEBUG=0` in production.

## Features

- Real-time price monitoring (BTC, ETH, SOL)
- Portfolio balance tracking
- Live and manual trading via CoinSpot
- Auto-trading strategy with socket status updates
- Live order history panel (bot/manual events + open orders)

## Files

- `main.py` - Main trading bot
- `coinspot.py` - CoinSpot API client
- `frontend/` - Dashboard UI
- `logs/trades/order_events.jsonl` - Persisted bot/manual order events

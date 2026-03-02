import os
import json
import requests
import xml.etree.ElementTree as ET

# -----------------------
# Standard imports
# -----------------------
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Union, Any

from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from coinspot import CoinSpot

# OpenAI v1 SDK
from openai import OpenAI, APIConnectionError, APITimeoutError

# Load environment variables
load_dotenv()

print("=== Crypto Dream Bot Startup ===")

# -----------------------
# OpenAI setup & check
# -----------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client: OpenAI | None = None

if OPENAI_API_KEY:
    try:
        # Reads key from env automatically
        openai_client = OpenAI(timeout=20, max_retries=2)
        openai_client.models.list()  # lightweight health check
        print("✓ OpenAI API key loaded and working.")
    except (APIConnectionError, APITimeoutError) as e:
        print(f"× OpenAI API network error: {e}")
    except Exception as e:
        print(f"× OpenAI API error: {e}")
else:
    print("× OPENAI_API_KEY not set.")

# -----------------------
# CoinSpot setup & check
# -----------------------
COINSPOT_API_KEY = os.getenv("COINSPOT_API_KEY")
COINSPOT_API_SECRET = os.getenv("COINSPOT_API_SECRET")
coinspot: CoinSpot | None = None

if COINSPOT_API_KEY and COINSPOT_API_SECRET:
    try:
        coinspot = CoinSpot(COINSPOT_API_KEY, COINSPOT_API_SECRET)
        # Lightweight private check
        test_bal = coinspot.my_balances()
        status = str(test_bal.get("status", "")).lower() if isinstance(test_bal, dict) else ""
        has_balances = isinstance(test_bal, dict) and isinstance(test_bal.get("balance"), dict)
        has_balances = has_balances or (isinstance(test_bal, dict) and isinstance(test_bal.get("balances"), dict))
        if status == "ok" and has_balances:
            print("✓ CoinSpot API key loaded and working.")
        else:
            message = test_bal.get("message", "Unexpected response") if isinstance(test_bal, dict) else "Unexpected response"
            print(f"× CoinSpot API check failed: {message}")
    except Exception as e:
        print(f"× CoinSpot API error: {e}")
        coinspot = None
else:
    print("× COINSPOT_API_KEY or COINSPOT_API_SECRET not set.")
    coinspot = None

print("=== Startup checks complete ===\n")

# -----------------------
# Flask / Socket.IO app
# -----------------------

# Serve static files from 'frontend/static' directory
app = Flask(__name__, static_folder="frontend/static", static_url_path="/static")
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")

socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",
    logger=True,
    engineio_logger=False,
)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


BOT_AUTO_TRADE_ENABLED = env_bool("BOT_AUTO_TRADE_ENABLED", True)
BOT_PAIR = os.getenv("BOT_PAIR", "BTC/AUD").upper()
BOT_SHORT_WINDOW = int(os.getenv("BOT_SHORT_WINDOW", "4"))
BOT_LONG_WINDOW = int(os.getenv("BOT_LONG_WINDOW", "12"))
BOT_SIGNAL_BPS = float(os.getenv("BOT_SIGNAL_BPS", "8"))
BOT_COOLDOWN_SECONDS = int(os.getenv("BOT_COOLDOWN_SECONDS", "120"))
BOT_BASE_AMOUNT = float(os.getenv("BOT_BASE_AMOUNT", "0.00005"))
BOT_TRADE_SIZE_AUD = float(os.getenv("TRADE_SIZE", "0") or 0)
BOT_MAX_TICKS = 200

bot_state: Dict[str, Any] = {
    "ticks": [],
    "position": "flat",
    "last_action_ts": 0,
}
recent_order_events: deque[Dict[str, Any]] = deque(maxlen=120)
ORDER_EVENTS_FILE = Path("logs/trades/order_events.jsonl")


def ensure_order_events_file():
    ORDER_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not ORDER_EVENTS_FILE.exists():
        ORDER_EVENTS_FILE.touch()


def append_order_event_to_disk(event: Dict[str, Any]):
    ensure_order_events_file()
    with ORDER_EVENTS_FILE.open("a", encoding="utf-8") as file_handle:
        file_handle.write(json.dumps(event, separators=(",", ":")) + "\n")


def load_recent_order_events_from_disk(limit: int = 120):
    ensure_order_events_file()
    try:
        lines = ORDER_EVENTS_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            if not line.strip():
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                recent_order_events.append(payload)
    except Exception as e:
        print(f"Order events load error: {e}")


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def utc_now_str(with_suffix: bool = False) -> str:
    base = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    return f"{base} UTC" if with_suffix else base


def parse_order_sort_ts(value: Any) -> int:
    if not value:
        return 0

    text = str(value).strip()
    if text.isdigit():
        raw = int(text)
        if raw > 10_000_000_000:
            return int(raw / 1000)
        return raw

    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.strptime(text, fmt).timestamp())
        except ValueError:
            continue
    return 0


def normalize_order_entry(entry: Dict[str, Any], fallback_market: str = "BTC/AUD") -> Dict[str, Any]:
    raw_time = (
        entry.get("transactionDate")
        or entry.get("date")
        or entry.get("time")
        or entry.get("solddate")
        or entry.get("created")
        or ""
    )
    market = str(entry.get("market") or fallback_market).upper()
    side = str(entry.get("type") or entry.get("side") or entry.get("ordertype") or "").lower()
    if side not in {"buy", "sell"}:
        side = "unknown"
    amount = to_float(entry.get("amount") or entry.get("coinamount") or entry.get("qty") or entry.get("volume"), 0.0)
    rate = to_float(entry.get("rate") or entry.get("audrate") or entry.get("price"), 0.0)
    total = to_float(entry.get("total") or entry.get("totalaud") or entry.get("total_aud"), amount * rate)
    status = str(entry.get("status") or "filled").lower()

    sort_ts = parse_order_sort_ts(raw_time)
    display_time = datetime.fromtimestamp(sort_ts).strftime("%Y-%m-%d %H:%M:%S") if sort_ts > 0 else str(raw_time)

    return {
        "time": display_time,
        "sort_ts": sort_ts,
        "side": side,
        "market": market,
        "amount": amount,
        "rate": rate,
        "total_aud": total,
        "status": status,
        "source": "coinspot",
    }


def record_order_event(result: Dict[str, Any], source: str):
    market = str(result.get("pair") or BOT_PAIR or "BTC/AUD").upper()
    side = str(result.get("side") or "").lower()
    if side not in {"buy", "sell"}:
        side = "unknown"
    amount = to_float(result.get("amount"), 0.0)
    status = str(result.get("status") or "unknown").lower()
    now_ts = int(time.time())

    event = {
        "time": utc_now_str(),
        "sort_ts": now_ts,
        "side": side,
        "market": market,
        "amount": amount,
        "rate": 0.0,
        "total_aud": 0.0,
        "status": status,
        "source": source,
    }
    recent_order_events.appendleft(event)
    try:
        append_order_event_to_disk(event)
    except Exception as e:
        print(f"Order event persist error: {e}")


def extract_balance_map(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}

    if isinstance(payload.get("balance"), dict):
        return payload["balance"]

    if isinstance(payload.get("balances"), dict):
        return payload["balances"]

    return {}


load_recent_order_events_from_disk(limit=120)


def coerce_balance_amount(raw_balance: Any) -> float:
    if isinstance(raw_balance, (int, float, str)):
        return float(raw_balance)

    if isinstance(raw_balance, dict):
        for key in ("balance", "available", "amount", "total"):
            value = raw_balance.get(key)
            if value is None:
                continue
            return float(value)

    raise ValueError(f"Unsupported balance shape: {raw_balance}")

# -----------------------
# Helpers
# -----------------------
def get_prices() -> Dict[str, Union[float, str]]:
    """Fetch public spot prices from CoinSpot. Strict live mode: no synthetic fallback prices."""
    try:
        data = CoinSpot.latest()  # public endpoint via library
        return {
            "BTC/AUD": float(data["prices"]["btc"]["bid"]),
            "ETH/AUD": float(data["prices"]["eth"]["bid"]),
            "SOL/AUD": float(data["prices"]["sol"]["bid"]),
            "source": "coinspot",
        }
    except Exception as e:
        print(f"Price fetch error: {e}")
        return {
            "source": "unavailable",
            "error": "CoinSpot live feed unavailable",
        }


def emit_bot_status(status: str, message: str):
    socketio.emit(
        "bot_status",
        {
            "status": status,
            "message": message,
            "time": utc_now_str(with_suffix=True),
        },
    )


def calculate_trade_amount(price: float) -> float:
    if BOT_TRADE_SIZE_AUD > 0 and price > 0:
        amount = BOT_TRADE_SIZE_AUD / price
        return round(max(amount, BOT_BASE_AMOUNT), 8)
    return round(BOT_BASE_AMOUNT, 8)


def execute_trade(pair: str, side: str, amount: float, reason: str, price: float = 0.0) -> Dict[str, Any]:
    if coinspot is None:
        return {"status": "error", "message": "CoinSpot API is not configured."}

    symbol = str(pair).split("/")[0].upper()
    if amount <= 0:
        return {"status": "error", "message": "Amount must be greater than 0."}

    if side == "buy":
        details = coinspot.my_buy(symbol, amount, price)
    elif side == "sell":
        details = coinspot.my_sell(symbol, amount, price)
    else:
        return {"status": "error", "message": "Invalid side (expected 'buy' or 'sell')."}

    return {
        "status": "filled",
        "details": details,
        "pair": pair,
        "side": side,
        "amount": amount,
        "reason": reason,
    }


def maybe_run_bot_strategy(prices: Dict[str, Union[float, str]]):
    if not BOT_AUTO_TRADE_ENABLED:
        return

    if coinspot is None:
        return

    if prices.get("source") != "coinspot":
        emit_bot_status("waiting", "Skipping signal: CoinSpot live feed unavailable")
        return

    latest_price = float(prices.get(BOT_PAIR, 0) or 0)
    if latest_price <= 0:
        emit_bot_status("waiting", f"Skipping signal: {BOT_PAIR} price unavailable")
        return

    ticks: list[float] = bot_state["ticks"]
    ticks.append(latest_price)
    if len(ticks) > BOT_MAX_TICKS:
        ticks.pop(0)

    if len(ticks) < BOT_LONG_WINDOW:
        emit_bot_status("warming", f"Collecting ticks {len(ticks)}/{BOT_LONG_WINDOW}")
        return

    short_window = max(2, min(BOT_SHORT_WINDOW, BOT_LONG_WINDOW - 1))
    short_ma = sum(ticks[-short_window:]) / short_window
    long_ma = sum(ticks[-BOT_LONG_WINDOW:]) / BOT_LONG_WINDOW
    diff_ratio = (short_ma - long_ma) / max(long_ma, 1e-9)

    now_ts = int(time.time())
    if now_ts - int(bot_state["last_action_ts"]) < BOT_COOLDOWN_SECONDS:
        emit_bot_status("cooldown", f"Cooling down ({BOT_COOLDOWN_SECONDS}s window)")
        return

    threshold = BOT_SIGNAL_BPS / 10000
    action = None
    if diff_ratio >= threshold and bot_state["position"] == "flat":
        action = "buy"
    elif diff_ratio <= -threshold and bot_state["position"] == "long":
        action = "sell"

    if action is None:
        emit_bot_status("watching", f"No signal | short={short_ma:.2f} long={long_ma:.2f}")
        return

    amount = calculate_trade_amount(latest_price)
    reason = f"MA signal short={short_ma:.2f}, long={long_ma:.2f}, diff={diff_ratio * 100:.3f}%"

    try:
        result = execute_trade(BOT_PAIR, action, amount, reason)
        record_order_event(result, "bot")
        socketio.emit("order_result", result)
        if result.get("status") == "filled":
            bot_state["position"] = "long" if action == "buy" else "flat"
            bot_state["last_action_ts"] = now_ts
            emit_bot_status("traded", f"{action.upper()} {amount} {BOT_PAIR} | {reason}")
        else:
            emit_bot_status("error", f"Trade error: {result.get('message', 'Unknown error')}")
    except Exception as e:
        failed = {"status": "error", "message": str(e), "reason": reason, "pair": BOT_PAIR, "side": action, "amount": amount}
        record_order_event(failed, "bot")
        socketio.emit("order_result", failed)
        emit_bot_status("error", f"Trade exception: {e}")


def stream_prices():
    while True:
        prices = get_prices()
        socketio.emit("price_update", {**prices, "timestamp": int(time.time())})
        maybe_run_bot_strategy(prices)
        time.sleep(10)


def ensure_background_stream_started():
    if app.config.get("PRICE_THREAD_STARTED"):
        return
    threading.Thread(target=stream_prices, daemon=True).start()
    app.config["PRICE_THREAD_STARTED"] = True


def fetch_crypto_news(limit: int = 6) -> list[dict[str, str]]:
    """Fetch recent crypto headlines from public RSS feeds."""
    feeds = [
        {"url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "source": "CoinDesk"},
        {"url": "https://cointelegraph.com/rss", "source": "Cointelegraph"},
    ]
    headlines: list[dict[str, str]] = []
    seen_titles: set[str] = set()

    for feed in feeds:
        feed_url = feed["url"]
        try:
            response = requests.get(feed_url, timeout=6)
            response.raise_for_status()
            root = ET.fromstring(response.content)

            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                headlines.append(
                    {
                        "title": title,
                        "url": link,
                        "source": feed["source"],
                    }
                )
                if len(headlines) >= limit:
                    return headlines
        except Exception as e:
            print(f"News feed error ({feed_url}): {e}")

    return headlines

# -----------------------
# Routes
# -----------------------
@app.route("/")
def index():
    ensure_background_stream_started()
    from flask import send_from_directory
    return send_from_directory("frontend", "index.html")

@app.route("/test")
def test_page():
    return render_template("test.html")

@app.route("/api/balance", methods=["GET"])
def get_live_balance():
    try:
        if coinspot is None:
            return jsonify({"success": False, "error": "CoinSpot API is not configured."}), 500

        balances = coinspot.my_balances()
        if not isinstance(balances, dict):
            return jsonify({"success": False, "error": "Unexpected CoinSpot response type."}), 502

        status = str(balances.get("status", "")).lower()
        if status and status != "ok":
            message = balances.get("message", "CoinSpot balance request failed.")
            return jsonify({"success": False, "error": f"CoinSpot: {message}"}), 502

        balance_map = extract_balance_map(balances)
        if not balance_map:
            return jsonify({"success": False, "error": "CoinSpot returned no balance data."}), 502

        result: Dict[str, Dict[str, float]] = {}
        for k, v in balance_map.items():
            symbol = str(k).upper()
            try:
                amount = coerce_balance_amount(v)
            except (TypeError, ValueError):
                continue

            if amount <= 0:
                continue

            if symbol == "AUD":
                value_aud = amount
            else:
                try:
                    price_info = coinspot.quote_buy(symbol.lower(), 1)
                    quote_raw = price_info.get("quote") if isinstance(price_info, dict) else 0
                    price = to_float(quote_raw, 0.0)
                except Exception as e:
                    print(f"Failed to get quote for {symbol}: {e}")
                    price = 0.0
                value_aud = amount * price
            result[symbol] = {"amount": amount, "value_aud": round(value_aud, 2)}

        total_value_aud = round(sum(asset["value_aud"] for asset in result.values()), 2)
        return jsonify({"success": True, "balances": result, "total_value_aud": total_value_aud}), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/news", methods=["GET"])
def get_crypto_news():
    try:
        headlines = fetch_crypto_news(limit=8)
        return jsonify(
            {
                "success": True,
                "headlines": headlines,
                "updated_at": utc_now_str(with_suffix=True),
            }
        ), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "headlines": []}), 500


@app.route("/api/order-history", methods=["GET"])
def get_order_history():
    orders: list[Dict[str, Any]] = list(recent_order_events)

    if coinspot is not None:
        try:
            payload = coinspot.my_orders()
            if isinstance(payload, dict) and str(payload.get("status", "")).lower() == "ok":
                for key, side in (("buyorders", "buy"), ("sellorders", "sell")):
                    open_orders = payload.get(key)
                    if not isinstance(open_orders, list):
                        continue
                    for entry in open_orders[:40]:
                        if not isinstance(entry, dict):
                            continue
                        market = str(entry.get("market") or BOT_PAIR).upper()
                        amount = to_float(entry.get("amount") or entry.get("coinamount"), 0.0)
                        rate = to_float(entry.get("rate") or entry.get("audrate"), 0.0)
                        total = to_float(entry.get("total") or entry.get("totalaud"), amount * rate)
                        raw_time = entry.get("created") or entry.get("date") or ""
                        sort_ts = parse_order_sort_ts(raw_time)

                        orders.append(
                            {
                                "time": datetime.fromtimestamp(sort_ts).strftime("%Y-%m-%d %H:%M:%S") if sort_ts > 0 else str(raw_time),
                                "sort_ts": sort_ts,
                                "side": side,
                                "market": market,
                                "amount": amount,
                                "rate": rate,
                                "total_aud": total,
                                "status": "open",
                                "source": "coinspot-open",
                            }
                        )
        except Exception as e:
            print(f"Order history fetch error (my_orders): {e}")

    sorted_orders = sorted(orders, key=lambda item: item.get("sort_ts", 0), reverse=True)
    return jsonify({
        "success": True,
        "orders": sorted_orders[:40],
        "updated_at": utc_now_str(with_suffix=True),
        "source_note": "Shows bot/manual order events plus your account open orders. Market-wide public trades are excluded.",
    }), 200

@app.route("/api/ask", methods=["POST"])
def ask_openai():
    try:
        data = request.get_json(silent=True) or {}
        prompt = str(data.get("prompt", "")).strip()
        if not prompt:
            return {"error": "No prompt provided"}, 400
        if openai_client is None:
            return {"error": "OpenAI client not configured"}, 500

        prices = get_prices()
        news_headlines = fetch_crypto_news(limit=6)
        news_block = "\n".join(
            [f"- {headline.get('title', 'Untitled')} ({headline.get('source', 'Unknown source')})" for headline in news_headlines]
        ) or "- No fresh headlines available."
        utc_now = utc_now_str(with_suffix=True)

        system_prompt = (
            "You are a crypto trading decision-support analyst for Crypto Dream Bot. "
            "Use both current price context and news headlines to explain potential market impact. "
            "Be concise, practical, and risk-aware. "
            "Do not promise outcomes. "
            "Always return exactly these sections:\n"
            "1) Market Snapshot\n"
            "2) News Impact\n"
            "3) Trade Bias (Bullish/Bearish/Neutral + confidence %)\n"
            "4) Risk Controls (entry/stop/position sizing guidance)\n"
            "5) Suggested Next Action\n"
            "End with: 'Not financial advice.'"
        )

        user_context = (
            f"Time: {utc_now}\n"
            f"Current prices: BTC/AUD={prices.get('BTC/AUD')}, ETH/AUD={prices.get('ETH/AUD')}, source={prices.get('source')}\n"
            f"Recent crypto headlines:\n{news_block}\n\n"
            f"User request: {prompt}"
        )

        # Use a modern lightweight model
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context},
            ],
            max_tokens=450,
            temperature=0.35,
        )
        answer = resp.choices[0].message.content
        return {"response": answer}
    except (APIConnectionError, APITimeoutError) as e:
        return {"error": f"OpenAI network error: {e}"}, 502
    except Exception as e:
        return {"error": str(e)}, 500

# -----------------------
# Socket.IO events
# -----------------------
@socketio.on("connect")
def handle_connect():
    ensure_background_stream_started()
    emit("connection_response", {"status": "connected", "prices": get_prices()})

@socketio.on("place_order")
def handle_order(order_data: Dict[str, Any]):
    try:
        pair = str(order_data["pair"]).upper()
        amount = float(order_data["amount"])
        side = str(order_data["side"]).lower()
        price = float(order_data.get("price", 0) or 0)

        result = execute_trade(pair, side, amount, "manual-order", price)
        record_order_event(result, "manual")
        emit("order_result", result)
    except Exception as e:
        failed = {"status": "error", "message": str(e), "pair": str(order_data.get("pair", "BTC/AUD")).upper(), "side": str(order_data.get("side", "")).lower(), "amount": to_float(order_data.get("amount"), 0.0)}
        record_order_event(failed, "manual")
        emit("order_result", failed)

# -----------------------
# Entrypoint
# -----------------------
if __name__ == "__main__":
    ensure_background_stream_started()
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1",
        use_reloader=False,
    )

import hmac
import json
import os
from time import time
from hashlib import sha512
from typing import Generator, Any, Optional

import requests
from flask import Flask, jsonify
import logging

app = Flask(__name__)

logger = logging.getLogger(__name__)


class CoinSpot:
    # The endpoint for the API
    API_ENDPOINT = "https://www.coinspot.com.au:443/api/"

    """Sets up the user's API key and secret.

    Args:
        key: Your API key generated from the settings page.
        sign: The POST data is to be signed using your secret key
              according to HMAC-SHA512 method.
    """

    def __init__(self, key: str, secret: str):
        self.key = key
        self.secret = secret.encode()

    """Yields the input, resulting in Transfer-Encoding: chunked while
    using the requests library.

    Args:
        data: Data to make generator for.

    Returns:
        A generator containing the data provided.
    """

    def _chunker(self, data: bytes) -> Generator[bytes, None, None]:
        yield data

    """Forms a request to the private API using the path and data provided,
    automatically including a nonce and signature for the data.

    Args:
        path: API endpoint to interact with.
        data (optional): Data to send with request.

    Returns:
        A Response instance.
    """

    def _request(self, path: str, data: Optional[dict[str, Any]] = None):
        if data is None:
            data = {}

        data["nonce"] = int(time() * 1000)
        json_data = json.dumps(data, separators=(",", ":")).encode()

        response = requests.post(
            self.API_ENDPOINT + path,
            data=self._chunker(json_data),
            headers={
                "Content-Type": "application/json",
                "sign": hmac.new(self.secret, json_data, sha512).hexdigest(),
                "key": self.key,
            },
        )
        return response.json()

    """Latest Prices

    Returns:
        status: ok, error
        prices: object containing one property for each coin
                with the latest prices for that coin
    """

    @staticmethod
    def latest():
        return requests.get("https://www.coinspot.com.au/pubapi/latest").json()

    """List Open Orders

    Args:
        cointype: the coin shortname, example value 'BTC', 'LTC', 'DOGE'

    Returns:
        status: ok, error
        buyorders: array containing all the open buy orders
        sellorders: array containing all the open sell orders
    """

    def orders(self, cointype: str):
        return self._request("orders", {"cointype": cointype})

    """List Order History

    Args:
        cointype: the coin shortname, example value 'BTC', 'LTC', 'DOGE'

    Returns:
        status: ok, error
        orders: list of the last 1000 completed orders
    """

    def orders_history(self, cointype: str):
        return self._request("orders/history", {"cointype": cointype})

    """List My Balances

    Returns:
        status: ok, error
        balances: object containing one property for each coin
                  with your balance for that coin.
    """

    def my_balances(self):
        return self._request("my/balances")

    """List My Orders
    A list of your open orders by coin type, it will
    return a maximum of 100 results

    Returns:
        status: ok, error
        buyorders: array containing all your buy orders
        sellorders: array containing all your sell orders
    """

    def my_orders(self):
        return self._request("my/orders")

    """Place Buy Order

    Args:
        cointype: the coin shortname, example value 'BTC', 'LTC', 'DOGE'
        amount: the amount of coins you want to buy,
                max precision 8 decimal places
        rate: the rate in AUD you are willing to pay,
              max precision 6 decimal places

    Returns:
        status: ok, error
    """

    def my_buy(self, cointype: str, amount: float, rate: float):
        return self._request(
            "my/buy", {"cointype": cointype, "amount": amount, "rate": rate}
        )

    """Cancel Buy Order

    Args:
        id: the id of the order to cancel

    Returns:
        status: ok, error
    """

    def my_buy_cancel(self, _id: str):
        return self._request("my/buy/cancel", {"id": _id})

    """Place Sell Order

    Args:
        cointype: the coin shortname, example value 'BTC', 'LTC', 'DOGE'
        amount: the amount of coins you want to sell,
                max precision 8 decimal places
        rate: the rate in AUD you are willing to sell for,
              max precision 6 decimal places

    Returns:
        status: ok, error
    """

    def my_sell(self, cointype: str, amount: float, rate: float):
        return self._request(
            "my/sell", {"cointype": cointype, "amount": amount, "rate": rate}
        )

    """Cancel Sell Order

    Args:
        id: the id of the order to cancel

    Returns:
        status: ok, error
    """

    def my_sell_cancel(self, _id: str):
        return self._request("my/sell/cancel", {"id": _id})

    """Deposit Coins

    Args:
        cointype: the coin shortname, example value 'BTC', 'LTC', 'DOGE'

    Returns:
        status: ok, error
        address: your deposit address for the coin
    """

    def my_coin_deposit(self, cointype: str):
        return self._request("my/coin/deposit", {"cointype": cointype})

    """Send Coins

    Args:
        cointype: the coin shortname, example value 'BTC', 'LTC', 'DOGE'
        address: the address to send coins to
        amount: the amount of coins to send

    Returns:
        status: ok, error
    """

    def my_coin_send(self, cointype: str, address: str, amount: float):
        return self._request(
            "my/coin/send", {"cointype": cointype, "address": address, "amount": amount}
        )

    """Quick Buy Quote

    Args:
        cointype: the coin shortname, example value 'BTC', 'LTC', 'DOGE'
        amount: the amount of coins to buy

    Returns:
        status: ok, error
        quote: the rate per coin
        timeframe: estimate hours to wait for trade to complete
                   (0 = immediate trade)
    """

    def quote_buy(self, cointype: str, amount: float):
        return self._request("quote/buy", {"cointype": cointype, "amount": amount})

    """Quick Sell Quote

    Args:
        cointype: the coin shortname, example value 'BTC', 'LTC', 'DOGE'
        amount: the amount of coins to sell

    Returns:
        status: ok, error
        quote: the rate per coin
        timeframe: estimate hours to wait for trade to complete
                   (0 = immediate trade)
    """

    def quote_sell(self, cointype: str, amount: float):
        return self._request("quote/sell", {"cointype": cointype, "amount": amount})


@app.route("/api/balance", methods=["GET"])
def get_live_balance():
    try:
        coinspot = CoinSpot(
            os.environ["COINSPOT_API_KEY"], os.environ["COINSPOT_API_SECRET"]
        )
        balances = coinspot.my_balances()
        result = {}
        for k, v in balances["balance"].items():
            symbol = k.upper()
            amount = float(v)
            if symbol == "AUD":
                value_aud = amount
            else:
                # Use quote_buy for price lookup
                price_info = coinspot.quote_buy(symbol.lower(), 1)
                price = float(price_info.get("quote", 0))
                value_aud = amount * price
            result[symbol] = {
                "amount": amount,
                "value_aud": round(value_aud, 2),
            }
        total_value_aud = sum(asset["value_aud"] for asset in result.values())
        return (
            jsonify(
                {
                    "success": True,
                    "balances": result,
                    "total_value_aud": total_value_aud,
                }
            ),
            200,
        )
    except Exception as e:
        logger.error(f"Error getting CoinSpot balance: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

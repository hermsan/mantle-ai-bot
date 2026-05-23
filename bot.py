import os
import time
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import telebot
from dotenv import load_dotenv
from google import genai

print("🚀 MANTLE AI BOT v5 STARTED")

# ==================================================
# LOAD ENV
# ==================================================
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

RPC_URL = "https://rpc.mantle.xyz"

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN missing")
    exit()

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY missing")
    exit()

# ==================================================
# INIT
# ==================================================
bot = telebot.TeleBot(
    TELEGRAM_TOKEN.strip(),
    parse_mode="HTML"
)

ai_client = genai.Client(
    api_key=GEMINI_API_KEY.strip()
)

session = requests.Session()

# ==================================================
# HELPERS
# ==================================================
def rpc_call(method, params=None):
    try:
        if params is None:
            params = []

        response = session.post(
            RPC_URL,
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1
            },
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        return data

    except Exception as e:
        print("RPC ERROR:", e)
        return {"result": None}


def get_prices():
    try:
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=mantle,bitcoin,ethereum"
            "&vs_currencies=usd"
        )

        response = session.get(url, timeout=10)

        return response.json()

    except Exception as e:
        print("PRICE ERROR:", e)
        return {}


def is_valid_address(address):
    return address.startswith("0x") and len(address) == 42


def is_valid_tx(txhash):
    return txhash.startswith("0x") and len(txhash) == 66


# ==================================================
# AI
# ==================================================
def ask_ai(prompt):
    try:
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        if hasattr(response, "text") and response.text:
            return response.text.strip()

        return "No AI response."

    except Exception as e:
        print("AI ERROR:", e)

        text = str(e).lower()

        if "quota" in text:
            return (
                "⚠️ Gemini quota reached.\n"
                "Please try again later."
            )

        return (
            "⚠️ AI temporarily unavailable.\n"
            "Blockchain commands still active."
        )

# ==================================================
# COMMANDS
# ==================================================
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        """
🚀 <b>Mantle AI Assistant</b>

Available Commands:

/help
/block
/gas
/price
/wallet 0xaddress
/portfolio 0xaddress
/tx hash
/analyze hash
/risk hash

You can also ask normal questions.
"""
    )


@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.reply_to(
        message,
        """
📚 Commands:

/block
/gas
/price
/wallet 0xaddress
/portfolio 0xaddress
/tx hash
/analyze hash
/risk hash
"""
    )

# ==================================================
# BLOCK
# ==================================================
@bot.message_handler(commands=["block"])
def block(message):
    res = rpc_call("eth_blockNumber")

    if not res.get("result"):
        bot.reply_to(message, "❌ Unable to fetch block.")
        return

    block_num = int(res["result"], 16)

    bot.reply_to(
        message,
        f"⛓ Latest Mantle Block:\n\n<b>{block_num:,}</b>"
    )

# ==================================================
# GAS
# ==================================================
@bot.message_handler(commands=["gas"])
def gas(message):
    res = rpc_call("eth_gasPrice")

    if not res.get("result"):
        bot.reply_to(message, "❌ Unable to fetch gas.")
        return

    gwei = int(res["result"], 16) / 1e9

    bot.reply_to(
        message,
        f"⛽ Current Gas:\n\n<b>{gwei:.2f} Gwei</b>"
    )

# ==================================================
# PRICE
# ==================================================
@bot.message_handler(commands=["price"])
def price(message):
    p = get_prices()

    mnt = p.get("mantle", {}).get("usd", 0)
    btc = p.get("bitcoin", {}).get("usd", 0)
    eth = p.get("ethereum", {}).get("usd", 0)

    bot.reply_to(
        message,
        f"""
💰 <b>Live Prices</b>

MNT: ${mnt}
BTC: ${btc}
ETH: ${eth}
"""
    )

# ==================================================
# WALLET
# ==================================================
@bot.message_handler(commands=["wallet"])
def wallet(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use:\n/wallet 0xaddress")
            return

        address = parts[1].strip()

        if not is_valid_address(address):
            bot.reply_to(message, "❌ Invalid wallet address.")
            return

        res = rpc_call(
            "eth_getBalance",
            [address, "latest"]
        )

        if not res.get("result"):
            bot.reply_to(message, "Wallet not found.")
            return

        balance = int(res["result"], 16) / 1e18

        bot.reply_to(
            message,
            f"""
👛 <b>Wallet Balance</b>

Address:
<code>{address}</code>

Balance:
<b>{balance:.6f} MNT</b>
"""
        )

    except Exception as e:
        print("WALLET ERROR:", e)
        bot.reply_to(message, "Wallet lookup failed.")

# ==================================================
# PORTFOLIO
# ==================================================
@bot.message_handler(commands=["portfolio"])
def portfolio(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use:\n/portfolio 0xaddress")
            return

        address = parts[1].strip()

        if not is_valid_address(address):
            bot.reply_to(message, "❌ Invalid address.")
            return

        res = rpc_call(
            "eth_getBalance",
            [address, "latest"]
        )

        if not res.get("result"):
            bot.reply_to(message, "Address not found.")
            return

        balance = int(res["result"], 16) / 1e18

        prices = get_prices()
        mnt_price = prices.get("mantle", {}).get("usd", 0)

        usd = balance * mnt_price

        bot.reply_to(
            message,
            f"""
📊 <b>Portfolio</b>

MNT:
{balance:.6f}

USD Value:
${usd:.2f}
"""
        )

    except Exception as e:
        print("PORTFOLIO ERROR:", e)
        bot.reply_to(message, "Portfolio failed.")

# ==================================================
# TX
# ==================================================
@bot.message_handler(commands=["tx"])
def tx(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use:\n/tx hash")
            return

        txhash = parts[1].strip()

        if not is_valid_tx(txhash):
            bot.reply_to(message, "❌ Invalid tx hash.")
            return

        res = rpc_call(
            "eth_getTransactionByHash",
            [txhash]
        )

        tx = res.get("result")

        if not tx:
            bot.reply_to(message, "Transaction not found.")
            return

        bot.reply_to(
            message,
            f"""
📦 <b>Transaction</b>

From:
<code>{tx.get('from')}</code>

To:
<code>{tx.get('to')}</code>
"""
        )

    except Exception as e:
        print("TX ERROR:", e)
        bot.reply_to(message, "Transaction lookup failed.")

# ==================================================
# ANALYZE
# ==================================================
@bot.message_handler(commands=["analyze"])
def analyze(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use:\n/analyze hash")
            return

        txhash = parts[1].strip()

        if not is_valid_tx(txhash):
            bot.reply_to(message, "❌ Invalid tx hash.")
            return

        res = rpc_call(
            "eth_getTransactionByHash",
            [txhash]
        )

        tx = res.get("result")

        if not tx:
            bot.reply_to(message, "Transaction not found.")
            return

        bot.send_chat_action(
            message.chat.id,
            "typing"
        )

        prompt = f"""
Analyze this blockchain transaction.

From: {tx.get('from')}
To: {tx.get('to')}
Value: {tx.get('value')}
Gas: {tx.get('gas')}

Explain:
1. Purpose
2. Possible usage
3. Risk level

Answer in English.
"""

        answer = ask_ai(prompt)

        bot.reply_to(message, answer[:3500])

    except Exception as e:
        print("ANALYZE ERROR:", e)
        bot.reply_to(message, "Analyze failed.")

# ==================================================
# RISK
# ==================================================
@bot.message_handler(commands=["risk"])
def risk(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use:\n/risk hash")
            return

        txhash = parts[1].strip()

        if not is_valid_tx(txhash):
            bot.reply_to(message, "❌ Invalid tx hash.")
            return

        res = rpc_call(
            "eth_getTransactionByHash",
            [txhash]
        )

        tx = res.get("result")

        if not tx:
            bot.reply_to(message, "Transaction not found.")
            return

        prompt = f"""
Analyze blockchain transaction risk.

From: {tx.get('from')}
To: {tx.get('to')}
Value: {tx.get('value')}

Classify:
LOW / MEDIUM / HIGH

Explain shortly.
"""

        answer = ask_ai(prompt)

        bot.reply_to(message, answer[:3500])

    except Exception as e:
        print("RISK ERROR:", e)
        bot.reply_to(message, "Risk analysis failed.")

# ==================================================
# GENERAL CHAT
# ==================================================
@bot.message_handler(func=lambda m: True)
def general_chat(message):
    try:
        bot.send_chat_action(
            message.chat.id,
            "typing"
        )

        prices = get_prices()

        mnt = prices.get("mantle", {}).get("usd", 0)

        prompt = f"""
You are a smart AI assistant.

Rules:
- Answer any topic
- If blockchain related, act as expert
- Prioritize Mantle ecosystem
- Always answer in English
- Current MNT price is ${mnt}

User:
{message.text}
"""

        answer = ask_ai(prompt)

        bot.reply_to(message, answer[:3500])

    except Exception as e:
        print("CHAT ERROR:", e)
        bot.reply_to(message, "⚠️ System busy.")

# ==================================================
# HEALTH SERVER
# ==================================================
class HealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(
            b"Mantle AI Bot Running"
        )

    def log_message(self, format, *args):
        return


def run_server():
    HTTPServer(
        ("0.0.0.0", 7860),
        HealthServer
    ).serve_forever()

# ==================================================
# MAIN
# ==================================================
if __name__ == "__main__":

    threading.Thread(
        target=run_server,
        daemon=True
    ).start()

    print("✅ BOT ONLINE")

    while True:
        try:
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True
            )

        except Exception as e:
            print("🔄 RECONNECT:", e)
            time.sleep(10)
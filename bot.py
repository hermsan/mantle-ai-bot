import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import telebot
from dotenv import load_dotenv
import google.generativeai as genai

print("🚀 MANTLE AI BOT v7 STARTED")

# ==================================================
# LOAD ENV
# ==================================================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

RPC_URL = "https://rpc.mantle.xyz"

# ==================================================
# CHECK ENV
# ==================================================
if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN missing")
    exit()

if not GEMINI_API_KEY:
    print("❌ GEMINI_API_KEY missing")
    exit()

print("✅ ENV Loaded")
print("✅ GEMINI KEY DETECTED")

# ==================================================
# INIT BOT
# ==================================================
bot = telebot.TeleBot(
    TELEGRAM_TOKEN.strip(),
    parse_mode="HTML"
)

session = requests.Session()

# ==================================================
# GEMINI SETUP
# ==================================================
model = None

def setup_gemini():
    global model

    try:
        genai.configure(
            api_key=GEMINI_API_KEY.strip()
        )

        # MODEL PALING STABIL UNTUK HUGGING FACE
        model = genai.GenerativeModel(
            "gemini-1.5-flash-latest"
        )

        print("✅ Gemini AI Ready")

    except Exception as e:
        print("❌ GEMINI SETUP ERROR:", e)
        model = None

setup_gemini()

# ==================================================
# RPC HELPER
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

        return response.json()

    except Exception as e:
        print("RPC ERROR:", e)

        return {
            "result": None
        }

# ==================================================
# PRICE HELPER
# ==================================================
def get_prices():
    try:
        url = (
            "https://api.coingecko.com/api/v3/simple/price"
            "?ids=mantle,bitcoin,ethereum"
            "&vs_currencies=usd"
        )

        response = session.get(
            url,
            timeout=10
        )

        return response.json()

    except Exception as e:
        print("PRICE ERROR:", e)
        return {}

# ==================================================
# VALIDATORS
# ==================================================
def is_valid_address(address):
    return (
        address.startswith("0x")
        and len(address) == 42
    )

def is_valid_tx(txhash):
    return (
        txhash.startswith("0x")
        and len(txhash) == 66
    )

# ==================================================
# AI FUNCTION
# ==================================================
def ask_ai(prompt):
    global model

    try:
        if model is None:
            setup_gemini()

        if model is None:
            return (
                "⚠️ AI unavailable.\n"
                "Please try again later."
            )

        response = model.generate_content(
            prompt
        )

        if response:
            text = getattr(response, "text", "")

            if text:
                return text.strip()

        return "No AI response."

    except Exception as e:
        print("AI ERROR:", e)

        error_text = str(e).lower()

        # AUTO RECONNECT GEMINI
        if (
            "429" in error_text
            or "quota" in error_text
        ):
            return (
                "⚠️ Gemini quota reached.\n"
                "Please try again later."
            )

        if (
            "api key" in error_text
            or "permission" in error_text
        ):
            return (
                "❌ Gemini API Key invalid."
            )

        # RESET MODEL
        model = None

        return (
            "⚠️ AI temporarily unavailable.\n"
            "Blockchain commands still active."
        )

# ==================================================
# START
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

# ==================================================
# HELP
# ==================================================
@bot.message_handler(commands=["help"])
def help_cmd(message):

    bot.reply_to(
        message,
        """
📚 <b>Commands</b>

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

    res = rpc_call(
        "eth_blockNumber"
    )

    if not res.get("result"):

        bot.reply_to(
            message,
            "❌ Unable to fetch block."
        )

        return

    block_num = int(
        res["result"],
        16
    )

    bot.reply_to(
        message,
        f"""
⛓ <b>Latest Mantle Block</b>

<b>{block_num:,}</b>
"""
    )

# ==================================================
# GAS
# ==================================================
@bot.message_handler(commands=["gas"])
def gas(message):

    res = rpc_call(
        "eth_gasPrice"
    )

    if not res.get("result"):

        bot.reply_to(
            message,
            "❌ Unable to fetch gas."
        )

        return

    gwei = int(
        res["result"],
        16
    ) / 1e9

    bot.reply_to(
        message,
        f"""
⛽ <b>Current Gas</b>

<b>{gwei:.2f} Gwei</b>
"""
    )

# ==================================================
# PRICE
# ==================================================
@bot.message_handler(commands=["price"])
def price(message):

    p = get_prices()

    mnt = p.get(
        "mantle",
        {}
    ).get("usd", 0)

    btc = p.get(
        "bitcoin",
        {}
    ).get("usd", 0)

    eth = p.get(
        "ethereum",
        {}
    ).get("usd", 0)

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
        parts = message.text.split(
            maxsplit=1
        )

        if len(parts) < 2:

            bot.reply_to(
                message,
                "Use:\n/wallet 0xaddress"
            )

            return

        address = parts[1].strip()

        if not is_valid_address(address):

            bot.reply_to(
                message,
                "❌ Invalid wallet address."
            )

            return

        res = rpc_call(
            "eth_getBalance",
            [address, "latest"]
        )

        if not res.get("result"):

            bot.reply_to(
                message,
                "Wallet not found."
            )

            return

        balance = int(
            res["result"],
            16
        ) / 1e18

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

        bot.reply_to(
            message,
            "Wallet lookup failed."
        )

# ==================================================
# PORTFOLIO
# ==================================================
@bot.message_handler(commands=["portfolio"])
def portfolio(message):

    try:
        parts = message.text.split(
            maxsplit=1
        )

        if len(parts) < 2:

            bot.reply_to(
                message,
                "Use:\n/portfolio 0xaddress"
            )

            return

        address = parts[1].strip()

        if not is_valid_address(address):

            bot.reply_to(
                message,
                "❌ Invalid address."
            )

            return

        res = rpc_call(
            "eth_getBalance",
            [address, "latest"]
        )

        if not res.get("result"):

            bot.reply_to(
                message,
                "Address not found."
            )

            return

        balance = int(
            res["result"],
            16
        ) / 1e18

        prices = get_prices()

        mnt_price = prices.get(
            "mantle",
            {}
        ).get("usd", 0)

        usd_value = balance * mnt_price

        bot.reply_to(
            message,
            f"""
📊 <b>Portfolio</b>

MNT:
{balance:.6f}

USD Value:
${usd_value:.2f}
"""
        )

    except Exception as e:
        print("PORTFOLIO ERROR:", e)

        bot.reply_to(
            message,
            "Portfolio failed."
        )

# ==================================================
# TX
# ==================================================
@bot.message_handler(commands=["tx"])
def tx(message):

    try:
        parts = message.text.split(
            maxsplit=1
        )

        if len(parts) < 2:

            bot.reply_to(
                message,
                "Use:\n/tx hash"
            )

            return

        txhash = parts[1].strip()

        if not is_valid_tx(txhash):

            bot.reply_to(
                message,
                "❌ Invalid tx hash."
            )

            return

        res = rpc_call(
            "eth_getTransactionByHash",
            [txhash]
        )

        tx_data = res.get("result")

        if not tx_data:

            bot.reply_to(
                message,
                "Transaction not found."
            )

            return

        bot.reply_to(
            message,
            f"""
📦 <b>Transaction</b>

From:
<code>{tx_data.get('from')}</code>

To:
<code>{tx_data.get('to')}</code>
"""
        )

    except Exception as e:
        print("TX ERROR:", e)

        bot.reply_to(
            message,
            "Transaction lookup failed."
        )

# ==================================================
# ANALYZE
# ==================================================
@bot.message_handler(commands=["analyze"])
def analyze(message):

    try:
        parts = message.text.split(
            maxsplit=1
        )

        if len(parts) < 2:

            bot.reply_to(
                message,
                "Use:\n/analyze hash"
            )

            return

        txhash = parts[1].strip()

        if not is_valid_tx(txhash):

            bot.reply_to(
                message,
                "❌ Invalid tx hash."
            )

            return

        res = rpc_call(
            "eth_getTransactionByHash",
            [txhash]
        )

        tx_data = res.get("result")

        if not tx_data:

            bot.reply_to(
                message,
                "Transaction not found."
            )

            return

        bot.send_chat_action(
            message.chat.id,
            "typing"
        )

        prompt = f"""
Analyze this Mantle blockchain transaction.

From: {tx_data.get('from')}
To: {tx_data.get('to')}
Value: {tx_data.get('value')}
Gas: {tx_data.get('gas')}

Explain:
- purpose
- possible usage
- risk level

Answer shortly in English.
"""

        answer = ask_ai(prompt)

        bot.reply_to(
            message,
            answer[:3500]
        )

    except Exception as e:
        print("ANALYZE ERROR:", e)

        bot.reply_to(
            message,
            "Analyze failed."
        )

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

        mnt = prices.get(
            "mantle",
            {}
        ).get("usd", 0)

        prompt = f"""
You are Mantle AI Assistant.

Rules:
- Always answer in English
- Keep answers short
- Prioritize blockchain and Mantle ecosystem
- Current MNT price is ${mnt}

User:
{message.text}
"""

        answer = ask_ai(prompt)

        bot.reply_to(
            message,
            answer[:3500]
        )

    except Exception as e:
        print("CHAT ERROR:", e)

        bot.reply_to(
            message,
            "⚠️ System busy."
        )

# ==================================================
# HEALTH SERVER
# ==================================================
class HealthServer(
    BaseHTTPRequestHandler
):

    def do_GET(self):

        self.send_response(200)
        self.end_headers()

        self.wfile.write(
            b"Mantle AI Bot Active"
        )

    def log_message(
        self,
        format,
        *args
    ):
        return

# ==================================================
# RUN HEALTH SERVER
# ==================================================
def run_server():

    PORT = int(
        os.environ.get(
            "PORT",
            7860
        )
    )

    HTTPServer(
        ("0.0.0.0", PORT),
        HealthServer
    ).serve_forever()

# ==================================================
# MAIN LOOP
# ==================================================
if __name__ == "__main__":

    threading.Thread(
        target=run_server,
        daemon=True
    ).start()

    print("✅ BOT ONLINE")

    while True:

        try:
            print(
                "🚀 Mantle AI Bot Running..."
            )

            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=15,
                skip_pending=True
            )

        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError
        ) as e:

            print(
                "Telegram connection lost:",
                e
            )

            time.sleep(5)

        except Exception as e:

            print(
                "MAIN LOOP ERROR:",
                e
            )

            time.sleep(5)
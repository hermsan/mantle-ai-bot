import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests
import telebot

from dotenv import load_dotenv
from google import genai

print("🚀 MANTLE AI BOT v12 STARTED")

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

# ==================================================
# SESSION
# ==================================================
session = requests.Session()

# ==================================================
# TELEGRAM BOT
# ==================================================
bot = telebot.TeleBot(
    TELEGRAM_TOKEN.strip(),
    parse_mode="HTML"
)

# ==================================================
# GEMINI CLIENT
# ==================================================
client = None

def setup_gemini():

    global client

    try:

        client = genai.Client(
            api_key=GEMINI_API_KEY.strip()
        )

        print("✅ Gemini Connected")

    except Exception as e:

        print("❌ GEMINI SETUP ERROR:")
        print(e)

        client = None

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
            timeout=20
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
            timeout=15
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
# GEMINI AI
# ==================================================
def ask_ai(prompt):

    global client

    try:

        if client is None:
            setup_gemini()

        if client is None:
            return "⚠️ AI unavailable."

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        # SAFE RESPONSE
        text = getattr(response, "text", None)

        if text:
            return text.strip()

        return "⚠️ Empty AI response."

    except Exception as e:

        print("AI ERROR:")
        print(e)

        error = str(e).lower()

        # QUOTA LIMIT
        if "429" in error:
            return (
                "⚠️ Gemini quota reached.\n"
                "Please wait a few minutes."
            )

        # INVALID API KEY
        if "api key" in error:
            return "❌ Invalid Gemini API Key."

        # MODEL ERROR
        if "404" in error or "not found" in error:
            return "❌ Gemini model unavailable."

        # AUTO RECONNECT
        client = None

        return "⚠️ AI temporarily unavailable."

# ==================================================
# START
# ==================================================
@bot.message_handler(commands=["start"])
def start(message):

    bot.reply_to(
        message,
        """
🚀 <b>Mantle AI Assistant</b>

Commands:

/help
/block
/gas
/price
/wallet 0xaddress
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
📚 Commands

/block
/gas
/price
/wallet 0xaddress
"""
    )

# ==================================================
# BLOCK
# ==================================================
@bot.message_handler(commands=["block"])
def block(message):

    res = rpc_call("eth_blockNumber")

    if not res.get("result"):

        bot.reply_to(
            message,
            "❌ Failed fetch block."
        )

        return

    block_number = int(
        res["result"],
        16
    )

    bot.reply_to(
        message,
        f"⛓ Latest Block:\n\n{block_number:,}"
    )

# ==================================================
# GAS
# ==================================================
@bot.message_handler(commands=["gas"])
def gas(message):

    res = rpc_call("eth_gasPrice")

    if not res.get("result"):

        bot.reply_to(
            message,
            "❌ Failed fetch gas."
        )

        return

    gwei = int(
        res["result"],
        16
    ) / 1e9

    bot.reply_to(
        message,
        f"⛽ Gas:\n\n{gwei:.2f} Gwei"
    )

# ==================================================
# PRICE
# ==================================================
@bot.message_handler(commands=["price"])
def price(message):

    prices = get_prices()

    mnt = prices.get(
        "mantle",
        {}
    ).get("usd", 0)

    btc = prices.get(
        "bitcoin",
        {}
    ).get("usd", 0)

    eth = prices.get(
        "ethereum",
        {}
    ).get("usd", 0)

    bot.reply_to(
        message,
        f"""
💰 Prices

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
👛 Wallet

{address}

Balance:
{balance:.6f} MNT
"""
        )

    except Exception as e:

        print("WALLET ERROR:", e)

        bot.reply_to(
            message,
            "Wallet failed."
        )

# ==================================================
# CHAT AI
# ==================================================
@bot.message_handler(func=lambda m: True)
def chat(message):

    try:

        bot.send_chat_action(
            message.chat.id,
            "typing"
        )

        answer = ask_ai(message.text)

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
class HealthServer(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.end_headers()

        self.wfile.write(
            b"Bot Active"
        )

    def log_message(self, format, *args):
        return

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

            bot.remove_webhook()

            time.sleep(2)

            print("🚀 Bot Polling...")

            bot.infinity_polling(
                timeout=30,
                long_polling_timeout=15,
                skip_pending=True
            )

        except Exception as e:

            print("MAIN LOOP ERROR:")
            print(e)

            # TELEGRAM 409
            if "409" in str(e):
                print("⚠️ Another bot instance running.")
                time.sleep(10)

            else:
                time.sleep(5)
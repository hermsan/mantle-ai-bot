import os
import time
import threading
import requests
from pathlib import Path
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from google import genai

print("🚀 MANTLE AI BOT v4 STARTED")

# =========================
# ENV
# =========================
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RPC_URL = "https://rpc.mantle.xyz"

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("❌ Missing TELEGRAM_TOKEN / GEMINI_API_KEY")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN.strip())
ai_client = genai.Client(api_key=GEMINI_API_KEY.strip())

# =========================
# HELPERS
# =========================
def rpc_call(method, params=None):
    try:
        if params is None:
            params = []

        r = requests.post(
            RPC_URL,
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1
            },
            timeout=10
        )

        r.raise_for_status()
        return r.json()

    except:
        return {"result": None}

def get_prices():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=mantle,bitcoin,ethereum&vs_currencies=usd"
        return requests.get(url, timeout=5).json()
    except:
        return {}

def ask_ai(prompt):
    try:
        response = ai_client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )

        if hasattr(response, "text") and response.text:
            return response.text.strip()

        return "No response."

    except Exception as e:
        print("AI ERROR:", e)

        # fallback jika quota habis
        return (
            "⚠️ Gemini quota reached.\n"
            "Please try again later.\n"
            "Core blockchain commands still active:\n"
            "/price /block /gas /wallet"
        )

# =========================
# COMMANDS
# =========================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "🚀 Mantle AI Assistant\n\n"
        "/help\n"
        "/block\n"
        "/gas\n"
        "/wallet 0xaddress\n"
        "/portfolio 0xaddress\n"
        "/tx hash\n"
        "/analyze hash\n"
        "/risk hash\n"
        "/price\n\n"
        "You can also ask normal questions."
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(
        message,
        "/block\n"
        "/gas\n"
        "/wallet 0xaddress\n"
        "/portfolio 0xaddress\n"
        "/tx hash\n"
        "/analyze hash\n"
        "/risk hash\n"
        "/price"
    )

# =========================
# BLOCK
# =========================
@bot.message_handler(commands=['block'])
def block(message):
    res = rpc_call("eth_blockNumber")

    if not res.get("result"):
        bot.reply_to(message, "Block unavailable.")
        return

    num = int(res["result"], 16)
    bot.reply_to(message, f"Latest block:\n{num:,}")

# =========================
# GAS
# =========================
@bot.message_handler(commands=['gas'])
def gas(message):
    res = rpc_call("eth_gasPrice")

    if not res.get("result"):
        bot.reply_to(message, "Gas unavailable.")
        return

    gwei = int(res["result"], 16) / 1e9
    bot.reply_to(message, f"Gas:\n{gwei:.2f} Gwei")

# =========================
# PRICE
# =========================
@bot.message_handler(commands=['price'])
def price(message):
    p = get_prices()

    mnt = p.get("mantle", {}).get("usd", 0)
    btc = p.get("bitcoin", {}).get("usd", 0)
    eth = p.get("ethereum", {}).get("usd", 0)

    bot.reply_to(
        message,
        f"Live Prices\n\nMNT: ${mnt}\nBTC: ${btc}\nETH: ${eth}"
    )

# =========================
# WALLET
# =========================
@bot.message_handler(commands=['wallet'])
def wallet(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use: /wallet 0xaddress")
            return

        address = parts[1].strip()

        res = rpc_call("eth_getBalance", [address, "latest"])

        if not res.get("result"):
            bot.reply_to(message, "Wallet not found.")
            return

        bal = int(res["result"], 16) / 1e18

        bot.reply_to(
            message,
            f"Address:\n{address}\n\nBalance:\n{bal:.6f} MNT"
        )

    except:
        bot.reply_to(message, "Wallet error.")

# =========================
# PORTFOLIO
# =========================
@bot.message_handler(commands=['portfolio'])
def portfolio(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use: /portfolio 0xaddress")
            return

        address = parts[1].strip()

        res = rpc_call("eth_getBalance", [address, "latest"])

        if not res.get("result"):
            bot.reply_to(message, "Address not found.")
            return

        bal = int(res["result"], 16) / 1e18
        p = get_prices()
        mnt = p.get("mantle", {}).get("usd", 0)

        usd = bal * mnt

        bot.reply_to(
            message,
            f"MNT: {bal:.6f}\nUSD: ${usd:.2f}"
        )

    except:
        bot.reply_to(message, "Portfolio error.")

# =========================
# TX
# =========================
@bot.message_handler(commands=['tx'])
def tx(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use: /tx hash")
            return

        txhash = parts[1].strip()
        res = rpc_call("eth_getTransactionByHash", [txhash])

        if res.get("result") is None:
            bot.reply_to(message, "Transaction not found.")
            return

        t = res["result"]

        bot.reply_to(
            message,
            f"From:\n{t.get('from')}\n\nTo:\n{t.get('to')}"
        )

    except:
        bot.reply_to(message, "TX error.")

# =========================
# ANALYZE
# =========================
@bot.message_handler(commands=['analyze'])
def analyze(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use: /analyze hash")
            return

        txhash = parts[1].strip()
        res = rpc_call("eth_getTransactionByHash", [txhash])

        if res.get("result") is None:
            bot.reply_to(message, "Transaction not found.")
            return

        t = res["result"]

        prompt = f"""
Analyze Mantle transaction.

From: {t.get('from')}
To: {t.get('to')}
Value: {t.get('value')}
Gas: {t.get('gas')}

Explain simply.
"""

        bot.reply_to(message, ask_ai(prompt)[:3500])

    except:
        bot.reply_to(message, "Analyze error.")

# =========================
# GENERAL CHAT
# =========================
@bot.message_handler(func=lambda m: True)
def chat(message):
    try:
        bot.send_chat_action(message.chat.id, "typing")

        prices = get_prices()
        mnt = prices.get("mantle", {}).get("usd", 0)

        prompt = f"""
You are intelligent AI assistant.

Rules:
- Answer any topic.
- If blockchain, act as expert.
- If Mantle related, prioritize Mantle.
- Always answer in English.
- Current MNT price: ${mnt}

User:
{message.text}
"""

        answer = ask_ai(prompt)

        bot.reply_to(message, answer[:3500])

    except:
        bot.reply_to(message, "System busy.")

# =========================
# HEALTH SERVER
# =========================
class HealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Mantle Bot Running")

    def log_message(self, format, *args):
        return

def run_server():
    HTTPServer(("0.0.0.0", 7860), HealthServer).serve_forever()

# =========================
# RUN
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()

    print("✅ Bot online")

    while True:
        try:
            bot.infinity_polling(
                timeout=60,
                long_polling_timeout=60,
                skip_pending=True
            )

        except Exception as e:
            print("Reconnect:", e)
            time.sleep(10)
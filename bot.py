import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
import google.generativeai as genai

# =========================
# CONFIG
# =========================
import os

from dotenv import load_dotenv
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RPC_URL = "https://rpc.mantle.xyz"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
genai.configure(api_key=GEMINI_API_KEY)

# =========================
# AUTO SELECT GEMINI MODEL
# =========================
model = None

def setup_model():
    global model

    try:
        print("Searching available Gemini models...")

        available = []

        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                available.append(m.name)
                print("✓", m.name)

        if not available:
            print("No models available")
            return

        selected = "models/gemini-flash-lite-latest"
        print("Using:", selected)

        model = genai.GenerativeModel(selected)

    except Exception as e:
        print("Gemini setup failed:", e)

setup_model()

# =========================
# RPC HELPER
# =========================
def rpc_call(method, params=None):
    if params is None:
        params = []

    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }

    r = requests.post(RPC_URL, json=payload, timeout=10)
    r.raise_for_status()
    return r.json()

# =========================
# START / HELP
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
        "/tx hash\n"
        "/analyze hash"
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(
        message,
        "Commands:\n"
        "/block\n"
        "/gas\n"
        "/wallet 0xaddress\n"
        "/tx hash\n"
        "/analyze hash"
    )

# =========================
# BLOCK
# =========================
@bot.message_handler(commands=['block'])
def block(message):
    try:
        res = rpc_call("eth_blockNumber")
        block_number = int(res["result"], 16)

        bot.reply_to(
            message,
            f"🧱 Latest Mantle Block:\n{block_number:,}"
        )

    except Exception as e:
        bot.reply_to(message, f"Block error: {e}")

# =========================
# GAS
# =========================
@bot.message_handler(commands=['gas'])
def gas(message):
    try:
        res = rpc_call("eth_gasPrice")
        gas_wei = int(res["result"], 16)
        gwei = gas_wei / 1e9

        bot.reply_to(
            message,
            f"⛽ Current Gas Price:\n{gwei:.2f} Gwei"
        )

    except Exception as e:
        bot.reply_to(message, f"Gas error: {e}")

# =========================
# WALLET
# =========================
@bot.message_handler(commands=['wallet'])
def wallet(message):
    try:
        parts = message.text.split()

        if len(parts) < 2:
            bot.reply_to(message, "Usage:\n/wallet 0xaddress")
            return

        address = parts[1].strip()

        if not address.startswith("0x") or len(address) != 42:
            bot.reply_to(message, "Invalid wallet address")
            return

        res = rpc_call("eth_getBalance", [address, "latest"])
        balance = int(res["result"], 16) / 1e18

        bot.reply_to(
            message,
            f"💰 Wallet Balance\n{address}\n\n{balance:.6f} MNT"
        )

    except Exception as e:
        bot.reply_to(message, f"Wallet error: {e}")

# =========================
# TX
# =========================
@bot.message_handler(commands=['tx'])
def tx(message):
    try:
        parts = message.text.split()

        if len(parts) < 2:
            bot.reply_to(message, "Usage:\n/tx hash")
            return

        txhash = parts[1].strip()

        res = rpc_call("eth_getTransactionByHash", [txhash])

        if res.get("result") is None:
            bot.reply_to(message, "Transaction not found")
            return

        tx = res["result"]

        bot.reply_to(
            message,
            f"📦 Transaction Found\n\n"
            f"From:\n{tx.get('from')}\n\n"
            f"To:\n{tx.get('to')}"
        )

    except Exception as e:
        bot.reply_to(message, f"TX error: {e}")

# =========================
# ANALYZE
# =========================
@bot.message_handler(commands=['analyze'])
def analyze_tx(message):
    try:
        if model is None:
            bot.reply_to(message, "AI unavailable")
            return

        parts = message.text.split()

        if len(parts) < 2:
            bot.reply_to(message, "Usage:\n/analyze hash")
            return

        txhash = parts[1].strip()

        res = rpc_call("eth_getTransactionByHash", [txhash])

        if res.get("result") is None:
            bot.reply_to(message, "Transaction not found")
            return

        tx = res["result"]

        prompt = f"""
Explain this Mantle blockchain transaction in English.

Describe:
- sender
- receiver
- technical meaning
- possible purpose

From: {tx.get('from')}
To: {tx.get('to')}
Value: {tx.get('value')}
Gas: {tx.get('gas')}
"""

        response = model.generate_content(prompt)

        if response.text:
            bot.reply_to(message, response.text[:3500])
        else:
            bot.reply_to(message, "No analysis available")

    except Exception as e:
        bot.reply_to(message, f"Analyze error: {e}")

# =========================
# AI CHAT
# =========================
@bot.message_handler(func=lambda m: True)
def chat_ai(message):
    try:
        print("Message:", message.text)

        if model is None:
            bot.reply_to(message, "AI unavailable")
            return

        bot.send_chat_action(message.chat.id, "typing")

        prompt = f"""
You are Mantle AI Assistant.

Rules:
- Always answer in English.
- Keep answers short and useful.
- Focus on blockchain, crypto, wallets, DeFi, Mantle ecosystem.
- Never answer in Indonesian.

User:
{message.text}
"""

        response = model.generate_content(prompt)

        if response.text:
            bot.reply_to(message, response.text[:3500])
        else:
            bot.reply_to(message, "No response")

    except Exception as e:
        print(e)

        if "429" in str(e):
            bot.reply_to(message, "AI is busy. Please try again shortly.")
        else:
            bot.reply_to(message, "AI error")

# =========================
# WEB SERVER
# =========================
class FakeServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Mantle AI Bot Active")

    def log_message(self, format, *args):
        return

def run_server():
    HTTPServer(("0.0.0.0", 7860), FakeServer).serve_forever()

# =========================
# RUN
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()

    print("Mantle AI Bot Running...")
    print("Telegram ready...")

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print("Polling error:", e)
            time.sleep(10)
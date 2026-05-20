import os
import time
import threading
import requests
from pathlib import Path
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from google import genai

print("🚀 MANTLE AI BOT v3 STARTED")

# ==================================================
# ENV
# ==================================================
env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RPC_URL = "https://rpc.mantle.xyz"

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("❌ Missing TELEGRAM_TOKEN or GEMINI_API_KEY")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN.strip(), parse_mode=None)
ai_client = genai.Client(api_key=GEMINI_API_KEY.strip())

# ==================================================
# HELPERS
# ==================================================
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
            timeout=12
        )

        r.raise_for_status()
        return r.json()

    except Exception:
        return {"result": None}

def get_prices():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=mantle,bitcoin,ethereum&vs_currencies=usd"
        return requests.get(url, timeout=6).json()
    except:
        return {}

def ask_ai(prompt):
    try:
        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = getattr(response, "text", None)

        if text:
            return text.strip()

        return "No response."

    except Exception as e:
        return f"AI error: {str(e)[:120]}"

# ==================================================
# COMMANDS
# ==================================================
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
        "/analyze hash\n"
        "/portfolio 0xaddress\n"
        "/risk hash\n"
        "/price"
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(
        message,
        "Available:\n"
        "/block\n"
        "/gas\n"
        "/wallet 0xaddress\n"
        "/tx hash\n"
        "/analyze hash\n"
        "/portfolio 0xaddress\n"
        "/risk hash\n"
        "/price"
    )

# ==================================================
# BLOCK
# ==================================================
@bot.message_handler(commands=['block'])
def block(message):
    res = rpc_call("eth_blockNumber")

    if not res.get("result"):
        bot.reply_to(message, "Unable to fetch block.")
        return

    block_num = int(res["result"], 16)
    bot.reply_to(message, f"Latest block:\n{block_num:,}")

# ==================================================
# GAS
# ==================================================
@bot.message_handler(commands=['gas'])
def gas(message):
    res = rpc_call("eth_gasPrice")

    if not res.get("result"):
        bot.reply_to(message, "Unable to fetch gas.")
        return

    gwei = int(res["result"], 16) / 1e9
    bot.reply_to(message, f"Gas:\n{gwei:.2f} Gwei")

# ==================================================
# PRICE
# ==================================================
@bot.message_handler(commands=['price'])
def price(message):
    p = get_prices()

    mnt = p.get("mantle", {}).get("usd", 0)
    btc = p.get("bitcoin", {}).get("usd", 0)
    eth = p.get("ethereum", {}).get("usd", 0)

    bot.reply_to(
        message,
        f"Live Prices\n\n"
        f"MNT: ${mnt}\n"
        f"BTC: ${btc}\n"
        f"ETH: ${eth}"
    )

# ==================================================
# WALLET
# ==================================================
@bot.message_handler(commands=['wallet'])
def wallet(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use: /wallet 0xaddress")
            return

        address = parts[1].strip()

        if not address.startswith("0x") or len(address) != 42:
            bot.reply_to(message, "Invalid address")
            return

        res = rpc_call("eth_getBalance", [address, "latest"])

        if not res.get("result"):
            bot.reply_to(message, "Wallet not found.")
            return

        balance = int(res["result"], 16) / 1e18

        bot.reply_to(
            message,
            f"Wallet:\n{address}\n\nBalance:\n{balance:.6f} MNT"
        )

    except:
        bot.reply_to(message, "Wallet check failed.")

# ==================================================
# PORTFOLIO
# ==================================================
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

        balance = int(res["result"], 16) / 1e18

        p = get_prices()
        mnt_price = p.get("mantle", {}).get("usd", 0)
        usd = balance * mnt_price

        bot.reply_to(
            message,
            f"Portfolio\n\n"
            f"MNT: {balance:.6f}\n"
            f"USD: ${usd:.2f}"
        )

    except:
        bot.reply_to(message, "Portfolio failed.")

# ==================================================
# TX
# ==================================================
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
            f"Transaction\n\n"
            f"From:\n{t.get('from')}\n\n"
            f"To:\n{t.get('to')}"
        )

    except:
        bot.reply_to(message, "Transaction lookup failed.")

# ==================================================
# ANALYZE
# ==================================================
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

        bot.send_chat_action(message.chat.id, "typing")

        prompt = f"""
You are Mantle blockchain expert.

Always answer in English.

Analyze this transaction:

From: {t.get('from')}
To: {t.get('to')}
Value: {t.get('value')}
Gas: {t.get('gas')}

Explain:
1. transaction purpose
2. possible usage
3. risk
"""

        bot.reply_to(message, ask_ai(prompt)[:3500])

    except:
        bot.reply_to(message, "Analyze failed.")

# ==================================================
# RISK
# ==================================================
@bot.message_handler(commands=['risk'])
def risk(message):
    try:
        parts = message.text.split(maxsplit=1)

        if len(parts) < 2:
            bot.reply_to(message, "Use: /risk hash")
            return

        txhash = parts[1].strip()

        res = rpc_call("eth_getTransactionByHash", [txhash])

        if res.get("result") is None:
            bot.reply_to(message, "Transaction not found.")
            return

        t = res["result"]

        prompt = f"""
Analyze security risk.

Always answer English.

From: {t.get('from')}
To: {t.get('to')}
Value: {t.get('value')}
Gas: {t.get('gas')}

Classify:
LOW / MEDIUM / HIGH

Explain shortly.
"""

        bot.reply_to(message, ask_ai(prompt)[:3500])

    except:
        bot.reply_to(message, "Risk check failed.")

# ==================================================
# AI CHAT
# ==================================================
@bot.message_handler(func=lambda m: True)
def chat(message):
    try:
        bot.send_chat_action(message.chat.id, "typing")

        prices = get_prices()
        mnt = prices.get("mantle", {}).get("usd", 0)

        prompt = f"""
You are Mantle AI Assistant.

Rules:
- Always answer in English
- Focus on Mantle ecosystem
- Blockchain assistant
- Explain clearly
- Current MNT price = ${mnt}

User message:
{message.text}
"""

        answer = ask_ai(prompt)

        bot.reply_to(message, answer[:3500])

    except:
        bot.reply_to(message, "System busy.")

# ==================================================
# HEALTH SERVER
# ==================================================
class HealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Mantle AI Running")

    def log_message(self, format, *args):
        return

def run_server():
    HTTPServer(("0.0.0.0", 7860), HealthServer).serve_forever()

# ==================================================
# RUN
# ==================================================
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()

    print("✅ Bot online")

    while True:
        try:
            bot.infinity_polling(
                skip_pending=True,
                timeout=25,
                long_polling_timeout=25
            )

        except Exception as e:
            print("Reconnect:", e)
            time.sleep(5)
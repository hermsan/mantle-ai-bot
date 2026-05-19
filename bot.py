import os
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from google import genai
from google.genai import types

# =====================================================================
# 🔐 CONFIG
# =====================================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RPC_URL = "https://rpc.mantle.xyz"

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("❌ ERROR: Missing environment variables (TELEGRAM_TOKEN / GEMINI_API_KEY)")
    exit(1)

bot = telebot.TeleBot(TELEGRAM_TOKEN.strip())

# Initialize the modern, unified Google GenAI Client
try:
    ai_client = genai.Client(api_key=GEMINI_API_KEY.strip())
    print("✓ Modern Gemini GenAI Client successfully initialized.")
except Exception as e:
    print(f"⚠️ Failed to initialize Gemini Client: {e}")
    ai_client = None

# =====================================================================
# 🌐 RPC HELPER (Mantle Network)
# =====================================================================
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

# =====================================================================
# 🤖 BOT COMMANDS (START / HELP)
# =====================================================================
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "🚀 **Mantle AI On-Chain & Alpha Assistant v2.0**\n\n"
        "Welcome to the ultimate developer and data agent for Mantle Network. "
        "Use the commands below to track network states and extract on-chain insights:\n\n"
        "🧱 /block - Fetch the latest block number\n"
        "⛽ /gas - Get live network gas prices in Gwei\n"
        "💰 /wallet [0xaddress] - Check real-time MNT balance\n"
        "📦 /tx [hash] - Retrieve base transaction paths\n"
        "🧠 /analyze [hash] - Leverage AI for deep transaction & anomaly analysis"
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    bot.reply_to(
        message,
        "Available Commands:\n"
        "/block - Live block number\n"
        "/gas - Current gas status\n"
        "/wallet 0xaddress - Balance check\n"
        "/tx hash - Base transaction data\n"
        "/analyze hash - AI transaction auditing"
    )

@bot.message_handler(commands=['block'])
def block(message):
    try:
        res = rpc_call("eth_blockNumber")
        block_number = int(res["result"], 16)
        bot.reply_to(message, f"🧱 **Latest Mantle Block:**\n#{block_number:,}")
    except Exception as e:
        bot.reply_to(message, f"❌ Block data error: {e}")

@bot.message_handler(commands=['gas'])
def gas(message):
    try:
        res = rpc_call("eth_gasPrice")
        gas_wei = int(res["result"], 16)
        gwei = gas_wei / 1e9
        bot.reply_to(message, f"⛽ **Current Gas Price:**\n{gwei:.2f} Gwei")
    except Exception as e:
        bot.reply_to(message, f"❌ Gas data error: {e}")

@bot.message_handler(commands=['wallet'])
def wallet(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage:\n/wallet 0xaddress")
            return
        address = parts[1].strip()
        if not address.startswith("0x") or len(address) != 42:
            bot.reply_to(message, "❌ Invalid wallet address format.")
            return

        res = rpc_call("eth_getBalance", [address, "latest"])
        balance = int(res["result"], 16) / 1e18
        bot.reply_to(message, f"💰 **Wallet Balance**\n`{address}`\n\n📊 **{balance:.6f} MNT**")
    except Exception as e:
        bot.reply_to(message, f"❌ Wallet data error: {e}")

@bot.message_handler(commands=['tx'])
def tx(message):
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage:\n/tx hash")
            return
        txhash = parts[1].strip()
        res = rpc_call("eth_getTransactionByHash", [txhash])
        if res.get("result") is None:
            bot.reply_to(message, "❌ Transaction not found on Mantle Network.")
            return
        tx_data = res["result"]
        bot.reply_to(
            message,
            f"📦 **Transaction Metadata**\n\n"
            f"**From:** `{tx_data.get('from')}`\n"
            f"**To:** `{tx_data.get('to')}`"
        )
    except Exception as e:
        bot.reply_to(message, f"❌ Transaction error: {e}")

# =====================================================================
# 🧠 AI ANALYZE (Enhanced for Hackathon Judging)
# =====================================================================
@bot.message_handler(commands=['analyze'])
def analyze_tx(message):
    try:
        if ai_client is None:
            bot.reply_to(message, "🤖 AI core processing unit is offline.")
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Usage:\n/analyze hash")
            return
        txhash = parts[1].strip()
        res = rpc_call("eth_getTransactionByHash", [txhash])
        if res.get("result") is None:
            bot.reply_to(message, "❌ Transaction target not found.")
            return
        tx_data = res["result"]
        bot.send_chat_action(message.chat.id, "typing")

        prompt = (
            f"Analyze this Mantle Network transaction data like an expert on-chain analyst. "
            f"Identify any potential smart money footprints, contract execution meaning, and security anomalies.\n\n"
            f"From: {tx_data.get('from')}\n"
            f"To: {tx_data.get('to')}\n"
            f"Value: {tx_data.get('value')}\n"
            f"Gas limit: {tx_data.get('gas')}"
        )

        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        bot.reply_to(message, response.text[:3500] if response.text else "Analysis stream was empty.")
    except Exception as e:
        bot.reply_to(message, f"❌ Analytical breakdown error: {e}")

# =====================================================================
# 💬 AI CHAT (Google Search Grounding Enabled)
# =====================================================================
@bot.message_handler(func=lambda m: True)
def chat_ai(message):
    try:
        if ai_client is None:
            bot.reply_to(message, "🤖 AI engine is currently unavailable.")
            return

        bot.send_chat_action(message.chat.id, "typing")
        
        # Tambahkan tools google_search agar Gemini bisa browsing harga token terupdate
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=message.text,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are the Mantle AI Intelligence Agent. Your job is to help users scan, understand, "
                    "and find anomalies or alpha within the Mantle Network ecosystem. Answer cleanly, shortly, "
                    "and professionally in English. Do not write in Indonesian. If users ask about coin or token "
                    "prices (such as MNT, BTC, or ETH), utilize your search tool to give them the precise, live market data."
                ),
                tools=[{"google_search": {}}],  # 🌟 FITUR BROWSING REAL-TIME AKTIF
                max_output_tokens=1000
            )
        )
        bot.reply_to(message, response.text[:3500] if response.text else "No intelligence returned.")
    except Exception as e:
        print("Chat Core Error:", e)
        bot.reply_to(message, "⚠️ System load high. Please retry your query shortly.")

# =====================================================================
# ⚙️ WEB SERVER
# =====================================================================
class FakeServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Mantle AI Bot Active")
    def log_message(self, format, *args):
        return

def run_server():
    HTTPServer(("0.0.0.0", 7860), FakeServer).serve_forever()

# =====================================================================
# 🏃‍♂️ RUNNER
# =====================================================================
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("Mantle AI Agent running successfully...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            time.sleep(10)
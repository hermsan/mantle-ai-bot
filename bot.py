import os
import time
import threading
import requests
from pathlib import Path
from dotenv import load_dotenv
from http.server import BaseHTTPRequestHandler, HTTPServer
import telebot
from google import genai
from google.genai import types

# =====================================================================
# 🟢 ENVIRONMENT INITIALIZATION
# =====================================================================
# Load environment variables from the root .env file
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

# =====================================================================
# 🔐 SYSTEM CONFIGURATION
# =====================================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RPC_URL = "https://rpc.mantle.xyz"

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("❌ ERROR: Missing environment variables (TELEGRAM_TOKEN / GEMINI_API_KEY)")
    exit(1)

# Initialize Telegram Bot Instance
bot = telebot.TeleBot(TELEGRAM_TOKEN.strip())

# Initialize Modern Google GenAI Unified Client
try:
    ai_client = genai.Client(api_key=GEMINI_API_KEY.strip())
    print("✓ Modern Gemini GenAI Client successfully initialized.")
except Exception as e:
    print(f"⚠️ Failed to initialize Gemini Client: {e}")
    ai_client = None

# =====================================================================
# 🌐 MANTLE NETWORK RPC HELPER
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
# 🤖 TELEGRAM BOT CORE COMMANDS
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
# 🧠 AI ON-CHAIN AUDITING Agent
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
# 💬 AI NATURAL CHAT INTERACTION (With Hardcoded Price Fetcher Bypass)
# =====================================================================
@bot.message_handler(func=lambda m: True)
def chat_ai(message):
    try:
        if ai_client is None:
            bot.reply_to(message, "🤖 AI engine is currently unavailable.")
            return

        bot.send_chat_action(message.chat.id, "typing")
        user_text = message.text.lower()
        price_info = ""

        # 🚀 TRICK BYPASS: Cek mandiri jika pengguna menanyakan harga token
        if "price" in user_text or "harga" in user_text:
            try:
                # Tembak langsung ke API CoinGecko Publik (Tanpa API Key, 100% Gratis & Live)
                url = "https://api.coingecko.com/api/v3/simple/price?ids=mantle,bitcoin,ethereum&vs_currencies=usd"
                res = requests.get(url, timeout=5).json()
                
                mnt_p = res.get("mantle", {}).get("usd", 0)
                btc_p = res.get("bitcoin", {}).get("usd", 0)
                eth_p = res.get("ethereum", {}).get("usd", 0)
                
                price_info = (
                    f"\n\n📊 [LIVE MARKET DATA ATTACHED BY MANTLE AGENT]:\n"
                    f"• Mantle (MNT): ${mnt_p:,.3f} USD\n"
                    f"• Bitcoin (BTC): ${btc_p:,.2f} USD\n"
                    f"• Ethereum (ETH): ${eth_p:,.2f} USD\n"
                    f"Please ingest this live data to answer the user's query precisely."
                )
            except Exception as e:
                print("Price API Fetch Error:", e)

        # Gabungkan pertanyaan user dengan data harga live agar dibaca oleh Gemini
        final_prompt = message.text + price_info

        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=final_prompt,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are the Mantle AI Intelligence Agent. Your job is to help users scan, understand, "
                    "and find anomalies or alpha within the Mantle Network ecosystem. Answer cleanly, shortly, "
                    "and professionally in English. Do not write in Indonesian. If the live market data is attached "
                    "in the prompt, use that data to give the exact current prices to the user with a professional breakdown."
                ),
                max_output_tokens=1000
            )
        )
        bot.reply_to(message, response.text[:3500] if response.text else "No intelligence returned.")
    except Exception as e:
        print("Chat Core Error:", e)
        bot.reply_to(message, "⚠️ System load high. Please retry your query shortly.")

# =====================================================================
# ⚙️ HEALTH CHECK WEB SERVER
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
# 🏃‍♂️ RUNNER (Anti-Crash Infinite Loop Protection)
# =====================================================================
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("✓ Mantle AI Agent system is initialized.")
    print("🚀 Bot is now actively monitoring Mantle Network...")
    
    while True:
        try:
            # skip_pending=True ignores flooded backlogs while the bot was recovering
            bot.infinity_polling(timeout=20, long_polling_timeout=20, skip_pending=True)
        except Exception as e:
            print(f"⚠️ TeleBot Connection Glitch: {e}. Reconnecting in 5 seconds...")
            time.sleep(5)
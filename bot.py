import os
import time
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
import telebot
from dotenv import load_dotenv

# Hubungkan ke modul helper eksternal
import helpers

print("🚀 MANTLE AI BOT v15 STARTED")

# Muat Environment Variables
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_TOKEN or not GEMINI_API_KEY:
    print("❌ CREDENTIALS MISSING")
    exit()

print("✅ ENV Loaded")

# Inisialisasi Bot Telegram
bot = telebot.TeleBot(
    TELEGRAM_TOKEN.strip(),
    parse_mode="HTML",
    threaded=True
)

# Nyalakan Mesin AI dari Modul Helper
helpers.setup_gemini(GEMINI_API_KEY)

# ==================================================
# BOT COMMAND HANDLERS
# ==================================================
@bot.message_handler(commands=["start"])
def start(message):
    bot.reply_to(
        message,
        "🚀 <b>Mantle AI Assistant</b>\n\nAvailable Commands:\n\n/help\n/block\n/gas\n/price\n/wallet 0xaddress\n\nYou can also chat with AI."
    )

@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.reply_to(
        message,
        "📚 <b>Commands</b>\n\n/block\n/gas\n/price\n/wallet 0xaddress"
    )

@bot.message_handler(commands=["block"])
def block(message):
    res = helpers.rpc_call("eth_blockNumber")
    if not res.get("result"):
        bot.reply_to(message, "❌ Failed fetch block.")
        return
    block_number = int(res["result"], 16)
    bot.reply_to(message, f"⛓ <b>Latest Mantle Block</b>\n\n{block_number:,}")

@bot.message_handler(commands=["gas"])
def gas(message):
    res = helpers.rpc_call("eth_gasPrice")
    if not res.get("result"):
        bot.reply_to(message, "❌ Failed fetch gas.")
        return
    gwei = int(res["result"], 16) / 1e9
    bot.reply_to(message, f"⛽ <b>Current Gas</b>\n\n{gwei:.2f} Gwei")

@bot.message_handler(commands=["price"])
def price(message):
    prices = helpers.get_prices()
    mnt = prices.get("mantle", {}).get("usd", 0)
    btc = prices.get("bitcoin", {}).get("usd", 0)
    eth = prices.get("ethereum", {}).get("usd", 0)
    bot.reply_to(message, f"💰 <b>Crypto Prices</b>\n\nMNT: ${mnt}\nBTC: ${btc}\nETH: ${eth}")

@bot.message_handler(commands=["wallet"])
def wallet(message):
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "Use:\n/wallet 0xaddress")
            return
        
        address = parts[1].strip()
        if not helpers.is_valid_address(address):
            bot.reply_to(message, "❌ Invalid wallet address.")
            return

        res = helpers.rpc_call("eth_getBalance", [address, "latest"])
        if not res.get("result"):
            bot.reply_to(message, "Wallet not found.")
            return

        balance = int(res["result"], 16) / 1e18
        bot.reply_to(message, f"👛 <b>Wallet Balance</b>\n\n<code>{address}</code>\n\nBalance:\n<b>{balance:.6f} MNT</b>")
    except Exception as e:
        bot.reply_to(message, "❌ Wallet lookup failed.")

@bot.message_handler(func=lambda m: True)
def chat(message):
    try:
        bot.send_chat_action(message.chat.id, "typing")
        prompt = f"You are Mantle AI Assistant.\n\nRules:\n- Answer shortly\n- Focus on crypto and blockchain\n- Friendly response\n\nUser:\n{message.text}"
        answer = helpers.ask_ai(prompt)
        bot.reply_to(message, answer[:3500])
    except Exception as e:
        bot.reply_to(message, "⚠️ System busy.")

# ==================================================
# HEALTH CHECK SERVER
# ==================================================
class HealthServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Active")
    def log_message(self, format, *args): return

def run_server():
    try:
        PORT = int(os.environ.get("PORT", 7860))
        server = HTTPServer(("0.0.0.0", PORT), HealthServer)
        print(f"🌐 Health server running on {PORT}")
        server.serve_forever()
    except Exception as e:
        print("SERVER ERROR:", e)

# ==================================================
# MAIN LOOP WITH RECONNECT ENGINE
# ==================================================
if __name__ == "__main__":
    threading.Thread(target=run_server, daemon=True).start()
    print("✅ BOT ONLINE")

    while True:
        try:
            print("🚀 Bot Polling...")
            bot.remove_webhook()
            time.sleep(2)
            bot.infinity_polling(
                timeout=20,
                long_polling_timeout=10,
                skip_pending=True,
                allowed_updates=["message"]
            )
        except KeyboardInterrupt:
            print("🛑 Bot stopped manually.")
            break
        except Exception as e:
            print("MAIN LOOP ERROR:", e)
            if "409" in str(e):
                print("⚠️ Another bot instance running. Sleeping 15s...")
                time.sleep(15)
            else:
                time.sleep(5)
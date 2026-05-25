import time
import requests
import google.generativeai as genai

RPC_URL = "https://rpc.mantle.xyz"
session = requests.Session()
session.headers.update({"User-Agent": "MantleAI/1.0"})

# State manajemen global untuk AI
last_ai_request = 0
quota_block_until = 0

def setup_gemini(api_key):
    try:
        # Menggunakan library generasi stabil guna menghindari masalah kuota concurrency cloud
        genai.configure(api_key=api_key.strip())
        print("✅ Gemini Connected")
        return True
    except Exception as e:
        print("❌ GEMINI SETUP ERROR:", e)
        return False

def rpc_call(method, params=None):
    try:
        if params is None: params = []
        response = session.post(
            RPC_URL,
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
            timeout=20
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("RPC ERROR:", e)
        return {"result": None}

def get_prices():
    try:
        response = session.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=mantle,bitcoin,ethereum&vs_currencies=usd",
            timeout=20
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("PRICE ERROR:", e)
        return {}

def is_valid_address(address):
    return isinstance(address, str) and address.startswith("0x") and len(address) == 42

def is_valid_tx(txhash):
    return isinstance(txhash, str) and txhash.startswith("0x") and len(txhash) == 66

def ask_ai(prompt):
    global last_ai_request, quota_block_until
    try:
        now = time.time()

        # 1. QUOTA COOLDOWN PROTECTION
        if now < quota_block_until:
            wait_time = int(quota_block_until - now)
            return f"⚠️ Gemini cooldown active.\nPlease wait {wait_time}s."

        # 2. ANTI SPAM RATELIMIT (5 SECONDS)
        cooldown = 5
        if now - last_ai_request < cooldown:
            remaining = int(cooldown - (now - last_ai_request)) + 1
            return f"⚠️ Please wait {remaining}s before next AI request."

        last_ai_request = now

        # 3. RUN MODEL (Dialihkan ke 1.5-flash demi ketahanan Kuota Free Tier)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        if response and response.text:
            return response.text.strip()
        return "⚠️ Empty AI response."

    except Exception as e:
        print("AI ERROR:", e)
        error = str(e).lower()

        if "429" in error or "quota" in error or "resource_exhausted" in error:
            print("⚠️ QUOTA LIMIT DETECTED")
            quota_block_until = time.time() + 60
            return "⚠️ Gemini quota reached.\nPlease wait 1 minute."
        
        if "api key" in error or "permission" in error or "unauthorized" in error:
            return "❌ Invalid Gemini API Key."
            
        if "404" in error or "not found" in error:
            return "❌ Gemini model unavailable."
            
        if "connection" in error or "timeout" in error:
            return "⚠️ Network error."

        return "⚠️ AI temporarily unavailable."
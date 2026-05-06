"""Validate the 3 active sub-account API keys against Binance."""
import sys, os, hmac, hashlib, time
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()
import requests

BASE = "https://api.binance.com"

def check_key(label, key, secret):
    print(f"  {label:12s}", end=" ", flush=True)
    params = {"timestamp": str(int(time.time() * 1000))}
    query = "&".join(f"{k}={v}" for k, v in params.items())
    sig = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    url = f"{BASE}/api/v3/account?{query}&signature={sig}"
    try:
        r = requests.get(url, headers={"X-MBX-APIKEY": key}, timeout=15)
        if r.status_code == 200:
            data = r.json()
            bals = [b for b in data.get("balances", []) if float(b.get("free",0)) > 0 or float(b.get("locked",0)) > 0]
            print(f"OK  canTrade={data.get('canTrade')}  assets={len(bals)}")
            return True
        else:
            err = r.json()
            print(f"FAIL  {err.get('code')}: {err.get('msg','?')}")
            return False
    except Exception as e:
        print(f"ERROR  {e}")
        return False

print("=" * 50)
print("Sub-Account API Key Validation")
print("=" * 50)
print()

keys = [
    ("Dorothy",  os.environ.get("DOROTHY_API_KEY","").strip("'"), os.environ.get("DOROTHY_API_SECRET","").strip("'")),
    ("Masha",    os.environ.get("MASHA_API_KEY","").strip("'"),   os.environ.get("MASHA_API_SECRET","").strip("'")),
    ("BlueChip", os.environ.get("BLUECHIP_API_KEY","").strip("'"),os.environ.get("BLUECHIP_API_SECRET","").strip("'")),
]

ok = 0
for label, key, secret in keys:
    if not key or not secret:
        print(f"  {label:12s} MISSING (no env vars)")
        continue
    if check_key(label, key, secret):
        ok += 1
    time.sleep(0.5)

print(f"\nResult: {ok}/{len(keys)} keys validated")

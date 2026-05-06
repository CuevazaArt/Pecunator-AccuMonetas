"""Create 3 new Binance virtual sub-accounts (alphanumeric names only)."""
import sys, os, time, json, hmac, hashlib
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

import requests

API_KEY = os.environ.get("PECUNATOR_BINANCE_API_KEY", "").strip()
API_SECRET = os.environ.get("PECUNATOR_BINANCE_API_SECRET", "").strip()
BASE = "https://api.binance.com"

def signed_request(method, path, params=None):
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    signature = hmac.new(
        API_SECRET.encode(), query.encode(), hashlib.sha256
    ).hexdigest()
    query += f"&signature={signature}"
    headers = {"X-MBX-APIKEY": API_KEY}
    url = f"{BASE}{path}?{query}"
    if method == "GET":
        return requests.get(url, headers=headers, timeout=30)
    return requests.post(url, headers=headers, timeout=30)

# Names: only lowercase alphanumeric (no underscores, no special chars)
BOTS = [
    ("dorothybot",   "Trend-following scalper"),
    ("mashabot",     "DCA range bot"),
    ("thusneldabot", "Opportunistic multi-symbol"),
]

print("=" * 60)
print("PECUNATOR - Sub-Account Creation")
print("=" * 60)
print()

print("[0] Current sub-accounts:")
r = signed_request("GET", "/sapi/v1/sub-account/list")
if r.status_code == 200:
    for s in r.json().get("subAccounts", []):
        print(f"  - {s.get('email','?')}")
print()

created = []
for tag, desc in BOTS:
    print(f"  Creating '{tag}' ({desc})...", end=" ", flush=True)
    r = signed_request("POST", "/sapi/v1/sub-account/virtualSubAccount", {
        "subAccountString": tag,
    })
    if r.status_code == 200:
        email = r.json().get("email", "?")
        print(f"OK -> {email}")
        created.append({"tag": tag, "email": email, "desc": desc})
    else:
        try:
            err = r.json()
            print(f"FAILED ({err.get('code')}: {err.get('msg')})")
        except:
            print(f"FAILED (HTTP {r.status_code})")
    time.sleep(1.5)

print()
if created:
    print(f"[OK] Created {len(created)} sub-account(s):")
    for c in created:
        print(f"  {c['tag']} -> {c['email']} ({c['desc']})")
    
    # Save
    outpath = "runtime/data/subaccounts_created.json"
    os.makedirs(os.path.dirname(outpath), exist_ok=True)
    with open(outpath, "w", encoding="utf-8") as f:
        json.dump({"created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "accounts": created}, f, indent=2)
    print(f"\n  Saved to: {outpath}")

# Final listing
print("\n[FINAL] All sub-accounts:")
r = signed_request("GET", "/sapi/v1/sub-account/list")
if r.status_code == 200:
    for s in r.json().get("subAccounts", []):
        print(f"  - {s.get('email','?')}")

print("""
========================================
NEXT STEPS (you do manually in Binance):
========================================

1. Go to: https://www.binance.com/en/sub-account/management
   Verify dorothybot, mashabot, thusneldabot appear.

2. For EACH sub-account, create API key:
   Sub-Account -> API Management -> Create

   ENABLE:
     [x] Spot Trading
     [x] IP Restriction (your home/server IP)
   
   DISABLE (security):
     [ ] Futures
     [ ] Margin  
     [ ] Withdrawals
     [ ] Internal Transfer

3. Copy each key+secret and share with me.
   I'll store them in the encrypted vault.

4. NEVER enable withdrawals on sub-account keys.
""")

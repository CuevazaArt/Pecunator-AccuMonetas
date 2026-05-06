"""Check Binance VIP level, sub-account eligibility, and existing sub-accounts.

Requires clean PECUNATOR_BINANCE_API_KEY and PECUNATOR_BINANCE_API_SECRET in .env
"""
import sys, os
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

from binance.client import Client
from binance.exceptions import BinanceAPIException

key = os.environ.get("PECUNATOR_BINANCE_API_KEY", "").strip()
secret = os.environ.get("PECUNATOR_BINANCE_API_SECRET", "").strip()

if not key or not secret:
    print("ERROR: Missing PECUNATOR_BINANCE_API_KEY or PECUNATOR_BINANCE_API_SECRET in .env")
    sys.exit(1)

# Sanity check on secret (should be 64 chars, alphanumeric)
if len(secret) > 80 or "&" in secret:
    print(f"[!]  WARNING: API SECRET looks corrupted (len={len(secret)}, contains shell artifacts)")
    print(f"   First 20 chars: {secret[:20]}...")
    print(f"   Last  20 chars: ...{secret[-20:]}")
    print()
    # Try to extract the real secret (first 64 alnum chars)
    clean = ""
    for c in secret:
        if c.isalnum():
            clean += c
        else:
            break
    if len(clean) == 64:
        print(f"   Auto-cleaned to {len(clean)} chars: {clean[:10]}...{clean[-10:]}")
        secret = clean
    else:
        print(f"   Could not auto-clean (got {len(clean)} chars). Please fix .env manually.")
        sys.exit(1)

print("=" * 60)
print("PECUNATOR — Binance Account Diagnostics")
print("=" * 60)
print()

client = Client(key, secret, requests_params={"timeout": 30})

# 1. Account Info (VIP level, permissions)
print("[1/4] Account Info...")
try:
    acct = client.get_account()
    print(f"  Account Type:    {acct.get('accountType', '?')}")
    print(f"  Can Trade:       {acct.get('canTrade', '?')}")
    print(f"  Can Withdraw:    {acct.get('canWithdraw', '?')}")
    print(f"  Can Deposit:     {acct.get('canDeposit', '?')}")
    print(f"  Maker Commission:{acct.get('makerCommission', '?')}")
    print(f"  Taker Commission:{acct.get('takerCommission', '?')}")
    
    # Count assets with balance
    bals = [b for b in acct.get("balances", []) if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0]
    print(f"  Assets w/balance: {len(bals)}")
    
    # Check BNB balance (for VIP level)
    bnb = next((b for b in acct.get("balances", []) if b.get("asset") == "BNB"), None)
    if bnb:
        bnb_total = float(bnb.get("free", 0)) + float(bnb.get("locked", 0))
        print(f"  BNB Balance:     {bnb_total:.4f} BNB (need ≥25 for VIP 1)")
    else:
        print(f"  BNB Balance:     0 (need ≥25 for VIP 1)")
except BinanceAPIException as e:
    print(f"  ERROR: {e.code} — {e.message}")
except Exception as e:
    print(f"  ERROR: {e}")

# 2. API Key Permissions 
print()
print("[2/4] API Key Permissions...")
try:
    perms = client.get_account_api_permissions()
    print(f"  IP Restrict:     {perms.get('ipRestrict', '?')}")
    print(f"  Create Time:     {perms.get('createTime', '?')}")
    print(f"  Enable Withdrawals: {perms.get('enableWithdrawals', '?')}")
    print(f"  Enable Internal Transfer: {perms.get('enableInternalTransfer', '?')}")
    print(f"  Permits Sub-Account Transfer: {perms.get('permitsUniversalTransfer', '?')}")
    print(f"  Enable Spot & Margin: {perms.get('enableSpotAndMarginTrading', '?')}")
    print(f"  Enable Futures:  {perms.get('enableFutures', '?')}")
    # Show trading authority
    ta = perms.get('tradingAuthorityExpirationTime', None)
    if ta:
        print(f"  Trading Auth Exp: {ta}")
except BinanceAPIException as e:
    print(f"  ERROR: {e.code} — {e.message}")
except Exception as e:
    print(f"  ERROR: {e}")

# 3. Sub-account list (requires sub-account management permission)
print()
print("[3/4] Existing Sub-Accounts...")
try:
    subs = client.get_sub_account_list()
    sub_list = subs.get("subAccounts", [])
    if sub_list:
        print(f"  [OK] Found {len(sub_list)} sub-account(s):")
        for s in sub_list:
            email = s.get("email", "?")
            status = s.get("status", "?") 
            create = s.get("createTime", "?")
            verified = s.get("isSubUserEnabled", "?")
            print(f"     • {email}  status={status}  created={create}  enabled={verified}")
    else:
        print("  No sub-accounts found.")
except BinanceAPIException as e:
    if e.code == -1002:
        print("  [X] API key does NOT have sub-account permissions")
    elif e.code == -9000:
        print("  [X] Sub-account feature NOT available (need VIP 1+ or corporate account)")
    else:
        print(f"  ERROR: {e.code} — {e.message}")
except Exception as e:
    print(f"  ERROR: {e}")

# 4. Trading volume (30d) — for VIP estimation
print()
print("[4/4] 30-Day Trade Volume (VIP estimation)...")
try:
    # Get recent trades for BTC pair to estimate volume
    from datetime import datetime, timedelta, timezone
    import time
    
    # Use the account trade list endpoint
    trades_btc = client.get_my_trades(symbol="BTCUSDT", limit=100)
    trades_eth = client.get_my_trades(symbol="ETHUSDT", limit=100)
    
    now_ms = int(time.time() * 1000)
    thirty_days_ms = now_ms - (30 * 24 * 60 * 60 * 1000)
    
    recent_btc = [t for t in trades_btc if int(t.get("time", 0)) > thirty_days_ms]
    recent_eth = [t for t in trades_eth if int(t.get("time", 0)) > thirty_days_ms]
    
    vol_btc = sum(float(t.get("quoteQty", 0)) for t in recent_btc)
    vol_eth = sum(float(t.get("quoteQty", 0)) for t in recent_eth)
    
    print(f"  BTCUSDT 30d volume: ${vol_btc:,.2f}")
    print(f"  ETHUSDT 30d volume: ${vol_eth:,.2f}")
    print(f"  Partial total:      ${vol_btc + vol_eth:,.2f}")
    print(f"  (Note: VIP 1 requires >$1M 30d volume across ALL pairs, or ≥25 BNB)")
    
except BinanceAPIException as e:
    print(f"  ERROR: {e.code} — {e.message}")
except Exception as e:
    print(f"  ERROR: {e}")

print()
print("=" * 60)
print("DIAGNOSTICS COMPLETE")
print("=" * 60)

# Cleanup
try:
    client.session.close()
except:
    pass

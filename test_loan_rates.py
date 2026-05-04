import config, json
from binance.client import Client

client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

STABLES = {"USDT","USDC","BUSD","FDUSD","USDS","DAI","TUSD","PYUSD","USDE"}

print("=== FLEXIBLE LOAN LOANABLE DATA (all) ===")
try:
    res = client.margin_v2_get_loan_flexible_loanable_data()
    print(json.dumps(res, indent=2)[:4000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== CRYPTO LOAN LOANABLE DATA (v1) ===")
try:
    res = client.margin_v1_get_loan_loanable_data()
    # filter stables
    rows = [r for r in res.get("rows",[]) if r.get("loanCoin","") in STABLES]
    print(json.dumps({"total": len(rows), "rows": rows[:5]}, indent=2)[:3000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== FLEXIBLE LOAN REPAY RATE ===")
try:
    res = client.margin_v2_get_loan_flexible_repay_rate(loanCoin="USDT", collateralCoin="BTC")
    print(json.dumps(res, indent=2)[:2000])
except Exception as e:
    print(f"Error: {e}")

import config, json, time
from binance.client import Client

client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

# Deposits/withdrawals need startTime/endTime (90 day windows max)
# Let's try with explicit time range
end_ts = int(time.time() * 1000)
start_ts = end_ts - (90 * 24 * 3600 * 1000)

print("=== DEPOSITS (last 90 days) ===")
try:
    res = client.get_deposit_history(startTime=start_ts, endTime=end_ts)
    print(f"Count: {len(res)}")
    if res:
        print(json.dumps(res[:2], indent=2)[:800])
except Exception as e:
    print(f"Error: {e}")

print("\n=== WITHDRAWALS (last 90 days) ===")
try:
    res = client.get_withdraw_history(startTime=start_ts, endTime=end_ts)
    print(f"Count: {len(res)}")
    if res:
        print(json.dumps(res[:2], indent=2)[:800])
except Exception as e:
    print(f"Error: {e}")

# Find dividend method
div_methods = [m for m in dir(client) if 'dividend' in m.lower() or 'dist' in m.lower() or 'airdrop' in m.lower()]
print(f"\nDividend methods: {div_methods}")

# Universal transfer history
transfer_methods = [m for m in dir(client) if 'transfer' in m.lower() or 'universal' in m.lower()]
print(f"Transfer methods: {transfer_methods}")

# Dust history
dust_methods = [m for m in dir(client) if 'dust' in m.lower()]
print(f"Dust methods: {dust_methods}")

# Try margin_v1 for loan liquidation history specifically
print("\n=== MARGIN LOAN INCOME (type=liquidation) ===")
try:
    # asset param is optional, type 1=borrowing, 2=repayment, 3=interest, 4=liquidation
    res = client.margin_v1_get_loan_income(type="liquidation", limit=10, startTime=start_ts)
    print(json.dumps(res, indent=2)[:1500])
except Exception as e:
    print(f"Error: {e}")

# Flexible loan LTV adjustments = forced liquidations
print("\n=== LTV ADJUSTMENT HISTORY ===")
try:
    res = client.margin_v2_get_loan_flexible_ltv_adjustment_history(current=1, limit=5, startTime=start_ts)
    print(json.dumps(res, indent=2)[:1500])
except Exception as e:
    print(f"Error: {e}")

# Earn redemption history  
print("\n=== EARN REDEMPTION HISTORY (limit 3) ===")
try:
    res = client.margin_v1_get_simple_earn_flexible_history_redemption_record(size=3, current=1)
    print(json.dumps(res, indent=2)[:1500])
except Exception as e:
    print(f"Error: {e}")

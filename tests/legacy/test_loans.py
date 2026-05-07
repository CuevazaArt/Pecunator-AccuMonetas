import config, json, inspect
from binance.client import Client

client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

# Test crypto loan ongoing orders
print("=== CRYPTO LOAN ONGOING ===")
try:
    res = client.margin_v1_get_loan_ongoing_orders(loanCoin="", current=1, limit=10)
    print(json.dumps(res, indent=2)[:2000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== CRYPTO LOAN BORROW HISTORY ===")
try:
    res = client.margin_v1_get_loan_borrow_history(current=1, limit=5)
    print(json.dumps(res, indent=2)[:2000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== CRYPTO LOAN REPAY HISTORY ===")
try:
    res = client.margin_v1_get_loan_repay_history(current=1, limit=5)
    print(json.dumps(res, indent=2)[:2000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== CRYPTO LOAN INCOME ===")
try:
    res = client.margin_v1_get_loan_income(limit=5)
    print(json.dumps(res, indent=2)[:2000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== FLEXIBLE LOAN ONGOING ===")
try:
    res = client.margin_v2_get_loan_flexible_ongoing_orders(current=1, limit=5)
    print(json.dumps(res, indent=2)[:2000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== FLEXIBLE LOAN BORROW HISTORY ===")
try:
    res = client.margin_v2_get_loan_flexible_borrow_history(current=1, limit=5)
    print(json.dumps(res, indent=2)[:2000])
except Exception as e:
    print(f"Error: {e}")

print("\n=== FLEXIBLE LOAN REPAY HISTORY ===")
try:
    res = client.margin_v2_get_loan_flexible_repay_history(current=1, limit=5)
    print(json.dumps(res, indent=2)[:2000])
except Exception as e:
    print(f"Error: {e}")

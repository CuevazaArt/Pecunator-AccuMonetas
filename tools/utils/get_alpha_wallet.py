import sys
import os
from pathlib import Path

# Fix encoding for Windows console to prevent charmap errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Add current directory to be able to import runtime
sys.path.append(str(Path(__file__).parent.absolute()))

from binance.client import Client

def main():
    try:
        import config
        api_key = config.api_key
        api_secret = config.api_secret
        print("Credentials loaded from config.py.")
    except ImportError:
        print("Error: config.py with credentials not found.")
        return
    except AttributeError:
        print("Error: config.py does not have 'api_key' or 'api_secret'.")
        return
        
    print("Connecting to Binance...")
    
    try:
        # Use binance-python client
        client = Client(api_key, api_secret)
        account = client.get_account()
        
        balances = account.get("balances", [])
        tickers = client.get_all_tickers()
        prices = {t["symbol"]: float(t["price"]) for t in tickers}
        
        active_balances = []
        total_wallet_usdt = 0.0
        
        for b in balances:
            free_qty = float(b.get("free", 0))
            if free_qty > 0:
                asset = b["asset"]
                price = 0.0
                if asset == "USDT":
                    price = 1.0
                elif asset + "USDT" in prices:
                    price = prices[asset + "USDT"]
                elif asset.startswith("LD") and asset[2:] + "USDT" in prices:
                    price = prices[asset[2:] + "USDT"]
                elif asset + "BTC" in prices:
                    price = prices[asset + "BTC"] * prices.get("BTCUSDT", 0.0)
                
                value_usdt = free_qty * price
                total_wallet_usdt += value_usdt
                
                active_balances.append({
                    "asset": asset,
                    "free": b["free"],
                    "value_usdt": value_usdt
                })
        
        # Sort by USDT value (descending)
        active_balances.sort(key=lambda x: x["value_usdt"], reverse=True)
        
        print(f"\n--- 'Alpha' Wallet Balances (Assets: {len(active_balances)}) ---")
        print(f"{'Asset':<15} | {'Balance':<20} | {'Value (USDT)':<20}")
        print("-" * 60)
        for b in active_balances:
            usdt_str = f"${b['value_usdt']:.2f}"
            print(f"{b['asset']:<15} | {b['free']:<20} | {usdt_str:<20}")
            
        print("-" * 60)
        print(f"Estimated Wallet Total: ${total_wallet_usdt:.2f} USDT")
            
    except Exception as e:
        print(f"Error fetching Binance account info: {e}")

if __name__ == "__main__":
    main()

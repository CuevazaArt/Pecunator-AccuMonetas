import sys
import time
from decimal import Decimal
from binance.client import Client
from binance.exceptions import BinanceAPIException
import config

def format_to_string(val, step_size_str):
    val = Decimal(str(val))
    step_size = Decimal(str(step_size_str))
    # Avoid division by zero if step_size is 0
    if step_size == 0:
        return str(val)
        
    remainder = val % step_size
    rounded = val - remainder
    s = f"{rounded.quantize(step_size):f}"
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    # Add 30-second timeout to avoid network errors when downloading all tickers
    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
    print("Fetching account and market information (this may take a moment)...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            account = client.get_account()
            balances = account.get("balances", [])
            
            exchange_info = client.get_exchange_info()
            symbols_info = {s["symbol"]: s for s in exchange_info["symbols"]}
            
            tickers = client.get_all_tickers()
            prices = {t["symbol"]: float(t["price"]) for t in tickers}
            break # If successful, exit the loop
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed due to network error: {e}. Retrying in 3 seconds...")
                time.sleep(3)
            else:
                print(f"Error connecting to Binance after several attempts: {e}")
                return
        
    tradeable_balances = [b for b in balances if float(b["free"]) > 0]
    
    print(f"Looking for assets to place a Limit Sell order (x30 profit)...")
    print("-" * 60)
    
    orders_placed = 0
    
    for b in tradeable_balances:
        asset = b["asset"]
        qty = float(b["free"])
        
        if asset == "USDT":
            continue
            
        symbol = asset + "USDT"
        
        # Check if symbol exists
        if symbol not in symbols_info:
            if asset.startswith("LD"):
                print(f"Skipping {asset}: Asset is in Binance Earn (LD). Must be redeemed to Spot to trade.")
            else:
                print(f"Skipping {asset}: Pair {symbol} does not exist in Spot.")
            continue
            
        if symbols_info[symbol]["status"] != "TRADING":
            print(f"Skipping {symbol}: Pair is not enabled for trading.")
            continue
            
        current_price = prices.get(symbol)
        if not current_price:
            print(f"Skipping {symbol}: Could not retrieve current price.")
            continue
            
        # Target price at 3000% (x30)
        target_price = current_price * 30.0
        
        # Extract Binance filters for this pair (LOT_SIZE, PRICE_FILTER, NOTIONAL)
        filters = {f["filterType"]: f for f in symbols_info[symbol]["filters"]}
        
        tick_size = filters.get("PRICE_FILTER", {}).get("tickSize", "0")
        step_size = filters.get("LOT_SIZE", {}).get("stepSize", "0")
        
        # Binance uses NOTIONAL or MIN_NOTIONAL
        min_notional = float(filters.get("NOTIONAL", {}).get("minNotional", 0))
        if min_notional == 0:
            min_notional = float(filters.get("MIN_NOTIONAL", {}).get("minNotional", 10.0))
            
        # Format the price and quantity according to exchange rules to avoid "Filter failure" errors
        price_str = format_to_string(target_price, tick_size)
        qty_str = format_to_string(qty, step_size)
        
        # Value validations
        order_value = float(qty_str) * float(price_str)
        if order_value < min_notional:
            print(f"Skipping {symbol}: Expected total value ({order_value:.2f} USDT) is below Binance minimum ({min_notional} USDT).")
            continue
            
        if float(qty_str) <= 0:
            print(f"Skipping {symbol}: Quantity is too small for the allowed step.")
            continue
            
        print(f"Attempting to place LIMIT SELL {symbol}: Qty={qty_str}, Price={price_str} USDT")
        try:
            order = client.order_limit_sell(
                symbol=symbol,
                quantity=qty_str,
                price=price_str
            )
            print(f"  -> Success! Order placed. ID: {order.get('orderId')}")
            orders_placed += 1
        except BinanceAPIException as e:
            print(f"  -> Error API: {e}")
        except Exception as e:
            print(f"  -> Unexpected Error: {e}")
            
        # Wait 1 second to avoid stressing the API
        time.sleep(1.0)
        
    print("-" * 60)
    print(f"Process completed. Orders successfully placed: {orders_placed}")

if __name__ == "__main__":
    main()

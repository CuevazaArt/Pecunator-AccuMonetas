import sys
import time
import config
from binance.client import Client
from binance.exceptions import BinanceAPIException

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    client = Client(config.api_key, config.api_secret)
    print("Fetching positions in Binance Simple Earn (Flexible)...")
    
    positions = []
    current_page = 1
    while True:
        try:
            res = client.get_simple_earn_flexible_product_position(current=current_page, size=100)
            rows = res.get("rows", [])
            if not rows:
                break
            positions.extend(rows)
            if len(positions) >= res.get("total", 0):
                break
            current_page += 1
        except Exception as e:
            print(f"Error fetching positions: {e}")
            break
            
    # Filter positions with funds that allow redemption
    tradeable = [p for p in positions if float(p.get("totalAmount", 0)) > 0 and p.get("canRedeem") is True]
    
    print(f"Found {len(tradeable)} assets in Flexible Earn ready to redeem to Spot.")
    print("-" * 60)
    
    redeemed_count = 0
    for p in tradeable:
        asset = p["asset"]
        product_id = p["productId"]
        amount = p["totalAmount"]
        
        print(f"Attempting to redeem {amount} of {asset} to Spot...")
        try:
            # First attempt with redeemAll
            res = client.redeem_simple_earn_flexible_product(
                productId=product_id,
                redeemAll=True
            )
            print(f"  -> Success! {asset} redeemed to Spot.")
            redeemed_count += 1
        except BinanceAPIException as e:
            # If redeemAll=True fails, sometimes the API prefers amount to be passed directly
            try:
                res = client.redeem_simple_earn_flexible_product(
                    productId=product_id,
                    amount=amount
                )
                print(f"  -> Success with exact amount! {asset} redeemed to Spot.")
                redeemed_count += 1
            except Exception as e2:
                print(f"  -> Binance API Error: {e2}")
        except Exception as e:
            print(f"  -> Unexpected Error: {e}")
            
        # Wait 1 second to avoid stressing the Binance API
        time.sleep(1.0)
        
    print("-" * 60)
    print(f"Process completed. Total assets redeemed to Spot: {redeemed_count}")
    print("\nDone! You can now run 'place_30x_orders.py' again to place the sell orders.")

if __name__ == "__main__":
    main()

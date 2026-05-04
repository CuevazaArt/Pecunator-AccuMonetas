import sys
import time
import config
from binance.client import Client
from binance.exceptions import BinanceAPIException

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        
    client = Client(config.api_key, config.api_secret)
    print("Obteniendo posiciones en Binance Simple Earn (Flexible)...")
    
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
            print(f"Error obteniendo posiciones: {e}")
            break
            
    # Filtrar posiciones con fondos y que permitan redención
    tradeable = [p for p in positions if float(p.get("totalAmount", 0)) > 0 and p.get("canRedeem") is True]
    
    print(f"Se encontraron {len(tradeable)} activos en Earn Flexible listos para redimir a Spot.")
    print("-" * 60)
    
    redeemed_count = 0
    for p in tradeable:
        asset = p["asset"]
        product_id = p["productId"]
        amount = p["totalAmount"]
        
        print(f"Intentando redimir {amount} de {asset} a Spot...")
        try:
            # Primero intentamos con redeemAll
            res = client.redeem_simple_earn_flexible_product(
                productId=product_id,
                redeemAll=True
            )
            print(f"  -> ¡Éxito! {asset} redimido a Spot.")
            redeemed_count += 1
        except BinanceAPIException as e:
            # Si redeemAll=True falla, a veces la API prefiere que se pase el amount directamente
            try:
                res = client.redeem_simple_earn_flexible_product(
                    productId=product_id,
                    amount=amount
                )
                print(f"  -> ¡Éxito con cantidad exacta! {asset} redimido a Spot.")
                redeemed_count += 1
            except Exception as e2:
                print(f"  -> Error API Binance: {e2}")
        except Exception as e:
            print(f"  -> Error Inesperado: {e}")
            
        # Esperar 1 segundo para no estresar la API de Binance
        time.sleep(1.0)
        
    print("-" * 60)
    print(f"Proceso finalizado. Total activos redimidos a Spot: {redeemed_count}")
    print("\n¡Listo! Ahora puedes ejecutar 'place_30x_orders.py' nuevamente para colocar las órdenes de venta.")

if __name__ == "__main__":
    main()

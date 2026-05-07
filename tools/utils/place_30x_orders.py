import sys
import time
from decimal import Decimal
from binance.client import Client
from binance.exceptions import BinanceAPIException
import config

def format_to_string(val, step_size_str):
    val = Decimal(str(val))
    step_size = Decimal(str(step_size_str))
    # Evitar division by zero si step_size es 0
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
        
    # Agregamos timeout de 30 segundos para evitar errores de red al descargar todos los tickers
    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
    print("Obteniendo información de la cuenta y mercado (puede tardar un momento)...")
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            account = client.get_account()
            balances = account.get("balances", [])
            
            exchange_info = client.get_exchange_info()
            symbols_info = {s["symbol"]: s for s in exchange_info["symbols"]}
            
            tickers = client.get_all_tickers()
            prices = {t["symbol"]: float(t["price"]) for t in tickers}
            break # Si funciona, salimos del bucle
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Intento {attempt + 1} falló por error de red: {e}. Reintentando en 3 segundos...")
                time.sleep(3)
            else:
                print(f"Error conectando a Binance tras varios intentos: {e}")
                return
        
    tradeable_balances = [b for b in balances if float(b["free"]) > 0]
    
    print(f"Buscando activos para colocar orden Limit de Venta (x30 de ganancia)...")
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
                print(f"Saltando {asset}: Activo en Binance Earn (LD). Debe redimirse a Spot para ser tradeado.")
            else:
                print(f"Saltando {asset}: No existe el par {symbol} en Spot.")
            continue
            
        if symbols_info[symbol]["status"] != "TRADING":
            print(f"Saltando {symbol}: El par no está habilitado para trading.")
            continue
            
        current_price = prices.get(symbol)
        if not current_price:
            print(f"Saltando {symbol}: No se pudo obtener el precio actual.")
            continue
            
        # Precio objetivo a 3000% (x30)
        target_price = current_price * 30.0
        
        # Extraer filtros de Binance para ese par (LOT_SIZE, PRICE_FILTER, NOTIONAL)
        filters = {f["filterType"]: f for f in symbols_info[symbol]["filters"]}
        
        tick_size = filters.get("PRICE_FILTER", {}).get("tickSize", "0")
        step_size = filters.get("LOT_SIZE", {}).get("stepSize", "0")
        
        # Binance utiliza NOTIONAL o MIN_NOTIONAL
        min_notional = float(filters.get("NOTIONAL", {}).get("minNotional", 0))
        if min_notional == 0:
            min_notional = float(filters.get("MIN_NOTIONAL", {}).get("minNotional", 10.0))
            
        # Formatear el precio y la cantidad según las reglas del exchange para evitar errores "Filter failure"
        price_str = format_to_string(target_price, tick_size)
        qty_str = format_to_string(qty, step_size)
        
        # Validaciones de valor
        order_value = float(qty_str) * float(price_str)
        if order_value < min_notional:
            print(f"Saltando {symbol}: Valor total esperado ({order_value:.2f} USDT) es menor al mínimo de Binance ({min_notional} USDT).")
            continue
            
        if float(qty_str) <= 0:
            print(f"Saltando {symbol}: Cantidad es demasiado pequeña para el salto permitido.")
            continue
            
        print(f"Intentando colocar VENTA LIMIT {symbol}: Cantidad={qty_str}, Precio={price_str} USDT")
        try:
            order = client.order_limit_sell(
                symbol=symbol,
                quantity=qty_str,
                price=price_str
            )
            print(f"  -> ¡Éxito! Orden colocada. ID: {order.get('orderId')}")
            orders_placed += 1
        except BinanceAPIException as e:
            print(f"  -> Error API: {e}")
        except Exception as e:
            print(f"  -> Error Inesperado: {e}")
            
        # Esperar 1 segundo para no estresar la API
        time.sleep(1.0)
        
    print("-" * 60)
    print(f"Proceso finalizado. Órdenes colocadas exitosamente: {orders_placed}")

if __name__ == "__main__":
    main()

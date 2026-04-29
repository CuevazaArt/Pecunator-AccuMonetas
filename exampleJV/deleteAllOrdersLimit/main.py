import config
from binance.client import Client

api_key = config.api_key
api_secret = config.api_secret
client = Client(api_key, api_secret)

# Define la moneda de cotización
quote_currency = "USDT"

try:
    # Obtiene todos los saldos de la cuenta spot
    account_info = client.get_account()
    try:
        # Itera sobre cada activo en la cuenta spot
        for asset in account_info['balances']:
            # Si el balance libre + locked del activo es mayor a 0
            try:
                if (float(asset['free']) + float(asset['locked'])) > 0 and asset['asset'] != quote_currency:
                    # Forma el símbolo de trading concatenando el activo con la moneda de cotización
                    symbol = asset['asset'] + quote_currency
                    print(symbol)

                    # Obtiene todas las órdenes abiertas para el símbolo de trading
                    open_orders = client.get_open_orders(symbol=symbol)

                    # Cancela cada orden abierta
                    for order in open_orders:
                        result = client.cancel_order(
                            symbol=order['symbol'],
                            orderId=order['orderId']
                        )
                        print(f"Orden {order['orderId']} cancelada: {result}")
            except Exception as e:
                print(f"Ocurrió un error: {e}")
    except Exception as e:
        print(f"Ocurrió un error: {e}")

except Exception as e:
    print(f"Ocurrió un error: {e}")

from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.client import Client
from decimal import Decimal, ROUND_DOWN
import config

# Importante revisar que claves API estan configuradas antes de ejecutar.
# Recuerda que antes de ejecutar este script se debe apagar todos los bots que coloquen ordenes o abran posiciones en la cuenta o habra conflictos o comportamientos inesperados o perdidas financieras

# Configuración del cliente de Binance
api_key = config.api_key
api_secret = config.api_secret
client = Client(api_key, api_secret)

# Define el activo final al que se convertirán los balances
assetFinal = "USDT"


# Función para cancelar órdenes abiertas de un símbolo
def cancelar_ordenes_abiertas(client, symbol):
	try:
		# Obtiene todas las órdenes abiertas para el símbolo
		open_orders = client.get_open_orders(symbol=symbol)
		for order in open_orders:
			result = client.cancel_order(
				symbol=symbol,
				orderId=order['orderId']
			)
			print(f"Orden {order['orderId']} cancelada para {symbol}.")
	except Exception as e:
		print(f"Error al cancelar órdenes para {symbol}: {e}")


# Función para obtener el formato permitido por los filtros del mercado
def obtener_cantidad_formateada(client, symbol, cantidad):
	try:
		# Obtiene información del símbolo
		symbol_info = client.get_symbol_info(symbol)
		if not symbol_info:
			print(f"No se encontró información para el símbolo {symbol}.")
			return None

		# Busca el filtro 'LOT_SIZE'
		for filtro in symbol_info['filters']:
			if filtro['filterType'] == 'LOT_SIZE':
				min_qty = Decimal(filtro['minQty'])
				step_size = Decimal(filtro['stepSize'])

				# Ajusta la cantidad a los múltiplos permitidos por stepSize
				cantidad_ajustada = (cantidad // step_size) * step_size
				return cantidad_ajustada if cantidad_ajustada >= min_qty else None

	except Exception as e:
		print(f"Error al obtener cantidad formateada para {symbol}: {e}")
		return None


# Función principal para vender todos los activos hacia el activo final
def ejecutar_red_button(client, assetFinal):
	try:
		# Obtiene balances de la cuenta spot
		account_info = client.get_account()
		for asset in account_info['balances']:
			free_balance = Decimal(asset['free'])
			if free_balance > 0 and asset['asset'] != assetFinal:
				symbol = asset['asset'] + assetFinal

				# Cancela órdenes abiertas para el símbolo
				cancelar_ordenes_abiertas(client, symbol)

				# Ajusta la cantidad al formato permitido
				cantidad_formateada = obtener_cantidad_formateada(client, symbol, free_balance)
				if cantidad_formateada:
					# Realiza la venta a mercado
					try:
						order = client.order_market_sell(
							symbol=symbol,
							quantity=str(cantidad_formateada)
						)
						print(f"Vendidos {cantidad_formateada} {asset['asset']} al mercado. Detalles: {order}")
					except BinanceAPIException as e:
						print(f"Error en la venta de {asset['asset']}: {e}")
				else:
					print(f"Cantidad insuficiente para operar con {symbol}.")
	except Exception as e:
		print(f"Error al ejecutar el RedButton: {e}")


# Llamada a la función principal
if __name__ == "__main__":
	confirmar = input("¿Estás seguro de que las claves API son las correctas y quieres ejecutar el RedButton? (si/no): ")
	if confirmar.lower() == "si":
		ejecutar_red_button(client, assetFinal)
	else:
		print("Ejecución cancelada.")

# -*- coding: utf-8 -*
from binance.exceptions import BinanceAPIException, BinanceOrderException
from binance.client import Client
from datetime import datetime, timedelta
from decimal import Decimal, getcontext,  ROUND_DOWN, ROUND_UP
import config
import csv
import time
import os
import subprocess
import json

# Crear cliente
api_key = config.api_key
api_secret = config.api_secret
client = Client(api_key, api_secret)


#modulo para cancelar todas las ordenes limit abiertas
try:
    # Obtiene todas las órdenes abiertas
    open_orders = client.get_open_orders()

    # Itera sobre cada orden abierta
    for order in open_orders:
        # Si la orden es una orden limit
        if order['type'] == 'LIMIT':
            # Cancela la orden
            result = client.cancel_order(
                symbol=order['symbol'],
                orderId=order['orderId']
            )
            print(f"Orden {order['orderId']} cancelada: {result}")
except Exception as e:
    print(f"Ocurrió un error: {e}")


#modulo para obtener el balance total en spot de la cuenta
# Define la moneda de cotización
quote_currency = "USDT"

try:
    # Obtiene todos los saldos de la cuenta spot
    account_info = client.get_account()

    total_balance_in_usdt = 0.0

    # Itera sobre cada activo en la cuenta spot
    for asset in account_info['balances']:
        # Si el balance libre + locked del activo es mayor a 0
        if (float(asset['free']) + float(asset['locked'])) > 0:
            # Forma el símbolo de trading concatenando el activo con la moneda de cotización
            symbol = asset['asset'] + quote_currency

            # Obtiene el precio actual del activo en USDT
            try:
                price_info = client.get_symbol_ticker(symbol=symbol)
                price_in_usdt = float(price_info['price'])

                # Calcula el balance del activo en USDT y lo suma al balance total
                asset_balance_in_usdt = (float(asset['free']) + float(asset['locked'])) * price_in_usdt
                total_balance_in_usdt += asset_balance_in_usdt
            except Exception as e:
                print(f"No se pudo obtener el precio para el símbolo {symbol}: {e}")

    print(f"Balance total en {quote_currency}: {total_balance_in_usdt}")
except Exception as e:
    print(f"Ocurrió un error: {e}")


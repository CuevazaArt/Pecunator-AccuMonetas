import os
import sys

import time
import httpx
from binance.client import Client
from dotenv import load_dotenv

project_root = os.path.abspath('.')
load_dotenv(os.path.join(project_root, '.env'))
api_key = os.environ.get('PECUNATOR_BINANCE_API_KEY')
api_secret = os.environ.get('PECUNATOR_BINANCE_API_SECRET')

client = Client(api_key, api_secret)
try:
    server_time = client.get_server_time()['serverTime']
    local_time = int(time.time() * 1000)
    client.timestamp_offset = server_time - local_time
except Exception as e:
    pass

print('Revisando ordenes abiertas en Binance...')
orders = client.get_open_orders()
for o in orders:
    print('  - ' + o['symbol'] + ' ' + o['side'] + ' QTY:' + o['origQty'] + ' @ ' + o['price'])
print('Total ordenes: ' + str(len(orders)))

BASE = 'http://127.0.0.1:8000'

def start_bot(path, tag, config):
    try:
        r = httpx.post(f'{BASE}{path}', json={'tag': tag, **config}, timeout=30)
        bot_id = r.json().get('bot_id', '')
        if bot_id:
            r_start = httpx.post(f'{BASE}{path}/{bot_id}/start', json={}, timeout=10)
            if r_start.status_code == 200:
                print('INICIADO: ' + tag)
            else:
                print('ERROR al iniciar ' + tag)
    except Exception as e:
        print('Fallo al crear ' + tag)

print('\nLanzando Thusnelda (2 instancias)...')
start_bot('/api/v1/thusnelda/bots', 'Thus-Basket1', {'symbols_csv': 'PEPEUSDT,SUIUSDT', 'loop_interval_sec': 8, 'simulated': False, 'trading_enabled': True})
start_bot('/api/v1/thusnelda/bots', 'Thus-Basket2', {'symbols_csv': 'INJUSDT,FETUSDT', 'loop_interval_sec': 12, 'simulated': False, 'trading_enabled': True})

# Masha: staggered 5-8s for mid-frequency wave
print('\nLanzando Masha (5 instancias)...')
masha_loops = [5, 6, 7, 8, 5]
for sym, loop in zip(['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'AVAXUSDT'], masha_loops):
    start_bot('/api/v1/masha/bots', f'Masha-{sym}', {'symbol': sym, 'loop_interval_sec': loop, 'simulated': False, 'trading_enabled': True})
    time.sleep(0.5)

# Dorothy: spread 4-7s for organic high-frequency oscillation
print('\nLanzando Dorothy (10 instancias)...')
dorothy_syms = ['XRPUSDT', 'ADAUSDT', 'DOTUSDT', 'LINKUSDT', 'DOGEUSDT', 'LTCUSDT', 'ATOMUSDT', 'NEARUSDT', 'MATICUSDT', 'UNIUSDT']
dorothy_loops = [4, 5, 6, 4, 7, 5, 6, 7, 4, 5]
for sym, loop in zip(dorothy_syms, dorothy_loops):
    start_bot('/api/v1/hub/bots', f'Dorothy-{sym}', {'symbol': sym, 'loop_interval_sec': loop, 'quote_order_qty': '10', 'profit_factor': '0.05', 'stop_loss_pct': '0.15', 'simulated': False, 'trading_enabled': True})
    time.sleep(0.5)

print('\n17 bots creados exitosamente.')

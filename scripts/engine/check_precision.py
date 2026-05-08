"""Check Binance exchange filters for target symbols."""
from binance.client import Client
from dotenv import load_dotenv
import os, time

load_dotenv()
c = Client(os.environ['PECUNATOR_BINANCE_API_KEY'], os.environ['PECUNATOR_BINANCE_API_SECRET'])
try:
    st = c.get_server_time()['serverTime']
    c.timestamp_offset = st - int(time.time()*1000)
except:
    pass

info = c.get_exchange_info()
targets = ['XRPUSDT','ADAUSDT','DOTUSDT','LINKUSDT','DOGEUSDT','LTCUSDT','ATOMUSDT','NEARUSDT','MATICUSDT','UNIUSDT']

print(f"{'Symbol':12s} {'tickSize':14s} {'priceDec':8s} {'stepSize':14s} {'qtyDec':6s}")
print("-" * 60)

for s in info['symbols']:
    if s['symbol'] in targets:
        tick = step = ''
        pdec = qdec = 0
        for f in s['filters']:
            if f['filterType'] == 'PRICE_FILTER':
                tick = f['tickSize']
                pdec = len(tick.rstrip('0').split('.')[1]) if '.' in tick else 0
            if f['filterType'] == 'LOT_SIZE':
                step = f['stepSize']
                qdec = len(step.rstrip('0').split('.')[1]) if '.' in step else 0
        print(f"{s['symbol']:12s} {tick:14s} {pdec:<8d} {step:14s} {qdec:<6d}")

print()
print("Dorothy default:  price_decimals=4, qty_decimals=8")
print()
print("MISMATCHES (bot default vs Binance requirement):")
for s in info['symbols']:
    if s['symbol'] in targets:
        for f in s['filters']:
            if f['filterType'] == 'PRICE_FILTER':
                tick = f['tickSize']
                pdec = len(tick.rstrip('0').split('.')[1]) if '.' in tick else 0
                if pdec != 4:
                    print(f"  PRICE_FILTER: {s['symbol']} needs {pdec} decimals (bot uses 4)")
            if f['filterType'] == 'LOT_SIZE':
                step = f['stepSize']
                qdec = len(step.rstrip('0').split('.')[1]) if '.' in step else 0
                if qdec != 8:
                    print(f"  LOT_SIZE:     {s['symbol']} needs {qdec} decimals (bot uses 8)")

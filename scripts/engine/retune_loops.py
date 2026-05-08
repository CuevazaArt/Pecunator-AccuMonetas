"""Hot-retune loop intervals on running bots for oscillator diversity."""
import httpx

BASE = 'http://127.0.0.1:8000'

# Dorothy bots: varied 4-7s for organic high-frequency oscillation
dorothy_loops = {
    'XRPUSDT': 4, 'ADAUSDT': 5, 'DOTUSDT': 6, 'LINKUSDT': 4,
    'DOGEUSDT': 7, 'LTCUSDT': 5, 'ATOMUSDT': 6, 'NEARUSDT': 7,
    'MATICUSDT': 4, 'UNIUSDT': 5,
}
bots = httpx.get(f'{BASE}/api/v1/hub/bots').json()['bots']
for b in bots:
    sym = b['symbol']
    bid = b['bot_id']
    new_loop = dorothy_loops.get(sym, 5)
    r = httpx.patch(f'{BASE}/api/v1/hub/bots/{bid}', json={'loop_interval_sec': new_loop}, timeout=10)
    print(f'  Dorothy {sym} -> {new_loop}s ({r.status_code})')

# Masha bots: staggered 5-8s for mid-frequency wave
masha_loops = {
    'BTCUSDT': 5, 'ETHUSDT': 6, 'BNBUSDT': 7, 'SOLUSDT': 8, 'AVAXUSDT': 5,
}
bots = httpx.get(f'{BASE}/api/v1/masha/bots').json()['bots']
for b in bots:
    sym = b['symbol']
    bid = b['bot_id']
    new_loop = masha_loops.get(sym, 6)
    r = httpx.patch(f'{BASE}/api/v1/masha/bots/{bid}', json={'loop_interval_sec': new_loop}, timeout=10)
    print(f'  Masha {sym} -> {new_loop}s ({r.status_code})')

# Thusnelda: 8s and 12s for low-frequency undulation
bots = httpx.get(f'{BASE}/api/v1/thusnelda/bots').json()['bots']
thus_loops = [8, 12]
for i, b in enumerate(bots):
    bid = b['bot_id']
    tag = b['tag']
    new_loop = thus_loops[i] if i < len(thus_loops) else 10
    r = httpx.patch(f'{BASE}/api/v1/thusnelda/bots/{bid}', json={'loop_interval_sec': new_loop}, timeout=10)
    print(f'  Thusnelda {tag} -> {new_loop}s ({r.status_code})')

print('\nDone. Intervals diversified.')

"""Search for PRICE_FILTER and other Binance filter errors in bot logs."""
import httpx
import json

BASE = 'http://127.0.0.1:8000'

FILTER_KEYWORDS = ['PRICE_FILTER', 'LOT_SIZE', 'MIN_NOTIONAL', 'Filter failure', 
                   'filter', 'PERCENT_PRICE', 'precision', 'decimal']

bots = httpx.get(f'{BASE}/api/v1/hub/bots').json()['bots']
found = []

for b in bots:
    bid = b['bot_id']
    tag = b['tag']
    logs = httpx.get(f'{BASE}/api/v1/hub/bots/{bid}/logs?limit=300').json()
    rows = logs.get('logs', [])
    
    for r in rows:
        msg = r.get('message', '')
        payload = json.dumps(r.get('payload', {})) if r.get('payload') else ''
        combined = msg + ' ' + payload
        
        for kw in FILTER_KEYWORDS:
            if kw.lower() in combined.lower():
                found.append({
                    'bot': tag,
                    'ts': r.get('ts_utc', ''),
                    'level': r.get('level', ''),
                    'msg': msg,
                    'payload': payload[:400] if payload else '',
                })
                break

# Also search for common error patterns
error_types = {}
for b in bots:
    bid = b['bot_id']
    tag = b['tag']
    logs = httpx.get(f'{BASE}/api/v1/hub/bots/{bid}/logs?limit=300').json()
    rows = logs.get('logs', [])
    for r in rows:
        level = r.get('level', '')
        msg = r.get('message', '')
        if level == 'ERROR':
            # Normalize the error message
            key = msg[:100]
            if key not in error_types:
                error_types[key] = {'count': 0, 'bots': set(), 'full_msg': msg, 'sample_payload': ''}
            error_types[key]['count'] += 1
            error_types[key]['bots'].add(tag)
            if r.get('payload') and not error_types[key]['sample_payload']:
                error_types[key]['sample_payload'] = json.dumps(r['payload'])[:500]

print("=" * 80)
print("FILTER-RELATED ERRORS")
print("=" * 80)
if found:
    for f in found:
        print(f"\n  [{f['level']}] {f['bot']} @ {f['ts']}")
        print(f"    msg: {f['msg']}")
        if f['payload']:
            print(f"    payload: {f['payload']}")
else:
    print("  (no PRICE_FILTER/LOT_SIZE errors found in bot logs)")

print()
print("=" * 80)
print("ALL ERROR-LEVEL ENTRIES (deduplicated)")
print("=" * 80)
for key, info in sorted(error_types.items(), key=lambda x: -x[1]['count']):
    print(f"\n  [x{info['count']}] {info['full_msg']}")
    print(f"    Bots: {', '.join(sorted(info['bots']))}")
    if info['sample_payload']:
        print(f"    Payload: {info['sample_payload']}")

# Check last_error from bot state
print()
print("=" * 80)
print("CURRENT last_error PER BOT")
print("=" * 80)
for b in bots:
    tag = b['tag']
    err = b.get('last_error') or '(none)'
    rep = b.get('last_report', {})
    dec = rep.get('decision', '-')
    print(f"  {tag:24s} decision={dec:20s} last_error={err}")

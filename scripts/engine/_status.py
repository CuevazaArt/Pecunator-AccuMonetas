import httpx
s = httpx.get("http://127.0.0.1:8000/api/v1/gateway/snapshot", timeout=5).json()
f = httpx.get("http://127.0.0.1:8000/api-fuse/status", timeout=5).json()
h = httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=5).json()
w = s.get("used_weight_1m")
wl = s.get("weight_limit_1m")
pct = round(w / wl * 100, 1) if w and wl else 0
print(f"Weight: {w}/{wl} ({pct}%)")
print(f"Fuse: tripped={f.get('tripped')} streak={f.get('consecutive_streak')} cooldown={f.get('current_cooldown_sec')}s")
print(f"Bots: {h.get('total_running')} running")

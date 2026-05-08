import httpx
# Check cache stats
try:
    r = httpx.get("http://127.0.0.1:8000/api/v1/cache/status", timeout=5)
    c = r.json()
    print(f"Cache hits: {c.get('hits')}, misses: {c.get('misses')}, fetches: {c.get('fetches')}")
    print(f"Hit rate: {c.get('hit_rate_pct')}%")
    print(f"Weight saved: {c.get('weight_saved')}")
    print(f"Active entries: {c.get('entries_active')}")
except Exception as e:
    print(f"Cache status error: {e}")

# Check health deep
try:
    r = httpx.get("http://127.0.0.1:8000/api/v1/health/deep", timeout=5)
    h = r.json()
    for key in sorted(h.keys()):
        val = h[key]
        if isinstance(val, dict):
            print(f"  {key}: {dict(list(val.items())[:5])}")
        else:
            print(f"  {key}: {val}")
except Exception as e:
    print(f"Health error: {e}")

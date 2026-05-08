"""Clean up duplicate bots and normalize the fleet.

Target state:
- Dorothy: keep all unique symbols (remove true duplicates)
- Masha: keep all unique symbols (remove true duplicates)  
- Thusnelda: keep ONLY 1 instance (the most recent basket)
"""
import httpx, json

BASE = "http://127.0.0.1:8000"

def _get(path):
    return httpx.get(f"{BASE}{path}", timeout=10).json()

def _delete(path):
    return httpx.delete(f"{BASE}{path}", timeout=10)

def _stop(path):
    return httpx.post(f"{BASE}{path}", json={}, timeout=10)

def dedup_hub(path, label, keep_field="tag"):
    """Remove duplicate bots, keeping the first of each unique tag."""
    data = _get(path)
    bots = data.get("bots", [])
    print(f"\n-- {label}: {len(bots)} total --")
    
    seen = {}
    to_delete = []
    for b in bots:
        key = b.get(keep_field, b.get("bot_id"))
        bid = b["bot_id"]
        tag = b.get("tag", bid)
        if key in seen:
            to_delete.append((bid, tag, "duplicate"))
        else:
            seen[key] = bid
            print(f"  [KEEP] {tag} ({bid})")
    
    for bid, tag, reason in to_delete:
        try:
            _stop(f"{path}/{bid}/stop")
        except Exception:
            pass
        try:
            _delete(f"{path}/{bid}")
            print(f"  [DEL]  {tag} ({bid}) - {reason}")
        except Exception as e:
            print(f"  [FAIL] {tag} ({bid}) - {e}")
    
    remaining = _get(path)
    print(f"  Result: {len(remaining.get('bots', []))} bots remaining")

def cleanup_thusnelda():
    """Keep only 1 Thusnelda — the most complete basket."""
    data = _get("/api/v1/thusnelda/bots")
    bots = data.get("bots", [])
    print(f"\n-- Thusnelda: {len(bots)} total --")
    
    if len(bots) <= 1:
        print("  Already 1 or fewer, nothing to do")
        return
    
    # Keep the one with most symbols
    best = max(bots, key=lambda b: len(b.get("symbols_csv", "").split(",")))
    best_id = best["bot_id"]
    print(f"  [KEEP] {best.get('tag')} ({best_id}) - symbols: {best.get('symbols_csv')}")
    
    for b in bots:
        bid = b["bot_id"]
        if bid == best_id:
            continue
        tag = b.get("tag", bid)
        try:
            _stop(f"/api/v1/thusnelda/bots/{bid}/stop")
        except Exception:
            pass
        try:
            _delete(f"/api/v1/thusnelda/bots/{bid}")
            print(f"  [DEL]  {tag} ({bid})")
        except Exception as e:
            print(f"  [FAIL] {tag} ({bid}) - {e}")
    
    remaining = _get("/api/v1/thusnelda/bots")
    print(f"  Result: {len(remaining.get('bots', []))} Thusnelda remaining")

def main():
    print("=" * 60)
    print("FLEET CLEANUP — Deduplicate & Normalize")
    print("=" * 60)
    
    dedup_hub("/api/v1/hub/bots", "Dorothy")
    dedup_hub("/api/v1/masha/bots", "Masha")
    cleanup_thusnelda()
    
    # Final count
    d = len(_get("/api/v1/hub/bots").get("bots", []))
    m = len(_get("/api/v1/masha/bots").get("bots", []))
    t = len(_get("/api/v1/thusnelda/bots").get("bots", []))
    print(f"\n{'='*60}")
    print(f"FINAL: Dorothy={d}, Masha={m}, Thusnelda={t}, Total={d+m+t}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

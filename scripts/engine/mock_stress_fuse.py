import time
import httpx

BASE = "http://127.0.0.1:8000"

def _inject(weight: int):
    try:
        httpx.post(f"{BASE}/api/v1/weight-governor/inject", json={"weight": weight})
    except Exception as e:
        print(f"Inject error: {e}")

def _fuse_status():
    try:
        return httpx.get(f"{BASE}/api-fuse/status").json()
    except Exception:
        return {}

def main():
    print("🚀 Iniciando Fake Stress Test para activar el fusible...")
    current_weight = 4000
    while True:
        current_weight += 300
        print(f"💉 Inyectando peso artificial: {current_weight}")
        _inject(current_weight)
        
        status = _fuse_status()
        tripped = status.get("tripped", False)
        
        if tripped:
            print(f"💥 ¡FUSIBLE ACTIVADO! Cooldown: {status.get('remaining_cooldown_sec')}s")
            break
            
        time.sleep(0.5)

if __name__ == "__main__":
    main()

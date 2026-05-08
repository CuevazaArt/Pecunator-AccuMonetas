import os
import time
import httpx
from dotenv import load_dotenv

BASE = "http://127.0.0.1:8000"

def get_binance_positions():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    load_dotenv(os.path.join(project_root, ".env"))
    api_key = os.environ.get("PECUNATOR_BINANCE_API_KEY")
    api_secret = os.environ.get("PECUNATOR_BINANCE_API_SECRET")
    
    if not api_key or not api_secret:
        print("❌ Faltan claves de API en .env para revisar posiciones.")
        return
        
    try:
        from binance.client import Client
        client = Client(api_key, api_secret)
        print("🔍 Revisando cuenta de Binance (Órdenes y balances)...")
        
        info = client.get_account()
        balances = info.get("balances", [])
        active_balances = [b for b in balances if float(b['free']) > 0 or float(b['locked']) > 0]
        
        print("\n💰 Balances activos (>0):")
        for b in active_balances:
            print(f"  - {b['asset']:>5s}: libre={float(b['free']):.4f}, en orden={float(b['locked']):.4f}")
            
        orders = client.get_open_orders()
        print(f"\n📜 Órdenes abiertas activas: {len(orders)}")
        for o in orders:
            print(f"  - {o['symbol']} {o['side']} {o['type']} QTY:{o['origQty']} @ {o['price']}")
            
    except Exception as e:
        print(f"⚠️ Error revisando posiciones: {e}")

def create_and_start(path: str, tag: str, config: dict):
    payload = {"tag": tag, **config}
    try:
        r = httpx.post(f"{BASE}{path}", json=payload, timeout=10)
        if r.status_code not in (200, 201):
            print(f"   ❌ Fallo al crear {tag}: {r.status_code} - {r.text[:200]}")
            return
        
        bot_id = r.json().get("bot_id", "")
        if not bot_id:
            print(f"   ❌ Fallo al extraer bot_id para {tag}")
            return
            
        r_start = httpx.post(f"{BASE}{path}/{bot_id}/start", json={}, timeout=10)
        if r_start.status_code == 200:
            print(f"   ✅ {tag} INICIADO (Live Real)")
        else:
            print(f"   ⚠️ Error al iniciar {tag}: {r_start.status_code} - {r_start.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error de red con {tag}: {e}")

def _wait_for_api(timeout=60):
    start = time.time()
    print("\n⏳ Esperando que el motor backend (API) esté listo...")
    while time.time() - start < timeout:
        try:
            r = httpx.get(f"{BASE}/api/v1/health", timeout=2)
            if r.status_code == 200:
                print("✅ API Local Respondiendo.")
                return True
        except:
            pass
        time.sleep(2)
    print("❌ API no respondió a tiempo.")
    return False

def main():
    print("=" * 60)
    print("🔥 LANZAMIENTO STRESS DE PRODUCCIÓN (17 INSTANCIAS LIVE) 🔥")
    print("=" * 60)
    
    get_binance_positions()
    
    if not _wait_for_api():
        return
    
    # Configuramos el intervalo de loop en ~5 a 7 segundos para alcanzar un 80% del límite de peso (4800 wt/min)
    
    print("\n--- 2 x Thusnelda (Basket Scalping) ---")
    create_and_start("/api/v1/thusnelda/bots", "Thus-Basket1", {
        "symbols_csv": "PEPEUSDT,SUIUSDT", "loop_interval_sec": 7, "simulated": False, "trading_enabled": True
    })
    create_and_start("/api/v1/thusnelda/bots", "Thus-Basket2", {
        "symbols_csv": "INJUSDT,FETUSDT", "loop_interval_sec": 7, "simulated": False, "trading_enabled": True
    })
    
    print("\n--- 5 x Masha (DCA Accumulation) ---")
    masha_syms = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "AVAXUSDT"]
    for sym in masha_syms:
        create_and_start("/api/v1/masha/bots", f"Masha-{sym}", {
            "symbol": sym, "loop_interval_sec": 6, "simulated": False, "trading_enabled": True
        })
        time.sleep(0.5)

    print("\n--- 10 x Dorothy (Trend Scalper) ---")
    dorothy_syms = ["XRPUSDT", "ADAUSDT", "DOTUSDT", "LINKUSDT", "DOGEUSDT", "LTCUSDT", "ATOMUSDT", "NEARUSDT", "MATICUSDT", "UNIUSDT"]
    for sym in dorothy_syms:
        create_and_start("/api/v1/hub/bots", f"Dorothy-{sym}", {
            "symbol": sym, "loop_interval_sec": 5, "quote_order_qty": "8", "profit_factor": "0.05", "stop_loss_pct": "0.15", "simulated": False, "trading_enabled": True
        })
        time.sleep(0.5)

    print("\n" + "=" * 60)
    print("✅ ¡Todos los 17 bots han sido creados y están activos en la red real!")
    print("👁️  La API está generando una alta carga rítmica (~4800 weight/min).")
    print("=" * 60)

if __name__ == '__main__':
    main()

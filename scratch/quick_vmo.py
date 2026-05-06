import asyncio
from runtime.modules.vision.config import get_vmo_config
from runtime.modules.vision.observer import VMObserver

async def main():
    cfg = get_vmo_config()
    # Override for quick test
    cfg.symbols = ["BTCUSDT"]
    obs = VMObserver(cfg)
    res = await obs.run_cycle()
    print("--- REPORTE VMO ---")
    for r in res:
        print(f"[{r.symbol} / {r.timeframe}] -> {r.regime} (Bot: {r.recommended_bot})")
        print(f"Confianza: {r.confidence:.2f} | Riesgo: {r.risk_level}")
        print(f"Notas IA: {r.notes}\n")

if __name__ == "__main__":
    asyncio.run(main())

import sys
import time
import config
from binance.client import Client

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
    print("Cargando portafolio...\n")

    # Obtener datos base
    account = client.get_account()
    balances = account.get("balances", [])

    # Posiciones en Earn
    earn_positions = []
    page = 1
    while True:
        try:
            res = client.get_simple_earn_flexible_product_position(current=page, size=100)
            rows = res.get("rows", [])
            if not rows:
                break
            earn_positions.extend(rows)
            if len(earn_positions) >= res.get("total", 0):
                break
            page += 1
        except:
            break

    # Locked earn
    locked_positions = []
    page = 1
    while True:
        try:
            res = client.get_simple_earn_locked_product_position(current=page, size=100)
            rows = res.get("rows", [])
            if not rows:
                break
            locked_positions.extend(rows)
            if len(locked_positions) >= res.get("total", 0):
                break
            page += 1
        except:
            break

    # Consolidar holdings
    holdings = {}
    for b in balances:
        asset = b["asset"]
        qty = float(b.get("free", 0)) + float(b.get("locked", 0))
        if qty > 0:
            clean = asset[2:] if asset.startswith("LD") else asset
            holdings[clean] = holdings.get(clean, 0.0) + qty

    for ep in earn_positions:
        asset = ep["asset"]
        qty = float(ep.get("totalAmount", 0))
        if qty > 0:
            holdings[asset] = holdings.get(asset, 0.0) + qty

    for ep in locked_positions:
        asset = ep.get("asset", "")
        qty = float(ep.get("amount", 0))
        if qty > 0:
            holdings[asset] = holdings.get(asset, 0.0) + qty

    # Precios
    tickers = client.get_all_tickers()
    prices = {t["symbol"]: float(t["price"]) for t in tickers}

    exchange_info = client.get_exchange_info()
    valid_symbols = {s["symbol"] for s in exchange_info["symbols"] if s["status"] == "TRADING"}

    # Analizar cada activo
    rows = []
    total_count = len(holdings)
    i = 0

    for asset, qty in holdings.items():
        i += 1
        symbol = asset + "USDT"

        if asset == "USDT":
            rows.append({
                "asset": "USDT",
                "qty": qty,
                "buy_price": 1.0,
                "current_price": 1.0,
                "value_usdt": qty,
                "pnl_pct": 0.0,
                "location": "Spot"
            })
            continue

        if symbol not in valid_symbols:
            continue

        current_price = prices.get(symbol, 0)
        if current_price == 0:
            continue

        sys.stderr.write(f"\r  Procesando {i}/{total_count}: {asset}...          ")
        sys.stderr.flush()

        # Precio promedio de compra
        avg_buy_price = 0.0
        total_buy_qty = 0.0
        total_buy_cost = 0.0
        try:
            trades = client.get_my_trades(symbol=symbol, limit=100)
            buys = [t for t in trades if t.get("isBuyer")]
            if buys:
                for t in buys:
                    tq = float(t["qty"])
                    tp = float(t["price"])
                    total_buy_qty += tq
                    total_buy_cost += tq * tp
                if total_buy_qty > 0:
                    avg_buy_price = total_buy_cost / total_buy_qty
        except:
            pass

        time.sleep(0.25)

        value_usdt = qty * current_price
        pnl_pct = 0.0
        if avg_buy_price > 0:
            pnl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100

        # Ubicación
        in_earn = asset in [ep["asset"] for ep in earn_positions]
        in_locked = asset in [ep.get("asset", "") for ep in locked_positions]
        if in_locked:
            location = "Locked"
        elif in_earn:
            location = "Earn"
        else:
            location = "Spot"

        rows.append({
            "asset": asset,
            "qty": qty,
            "buy_price": avg_buy_price,
            "current_price": current_price,
            "value_usdt": value_usdt,
            "pnl_pct": pnl_pct,
            "location": location
        })

    sys.stderr.write(f"\r  Listo. {len(rows)} activos procesados.                    \n")
    sys.stderr.flush()

    # Ordenar por valor USDT descendente
    rows.sort(key=lambda x: x["value_usdt"], reverse=True)

    total_value = sum(r["value_usdt"] for r in rows)
    with_cost = [r for r in rows if r["buy_price"] > 0 and r["asset"] != "USDT"]
    total_cost = sum(r["qty"] * r["buy_price"] for r in with_cost)
    total_current_val = sum(r["value_usdt"] for r in with_cost)

    # Imprimir tabla
    print()
    print("┌────────────┬──────────────────┬────────────┬────────────┬────────────┬──────────┬────────┐")
    print("│ Asset      │ Cantidad         │ P. Compra  │ P. Actual  │ Valor USD  │   P&L %  │ Ubic.  │")
    print("├────────────┼──────────────────┼────────────┼────────────┼────────────┼──────────┼────────┤")

    for r in rows:
        asset = r["asset"][:10]
        qty_str = f"{r['qty']:.4f}" if r["qty"] < 10000 else f"{r['qty']:.0f}"
        
        if r["buy_price"] == 0:
            buy_str = "    N/A   "
        elif r["buy_price"] < 0.01:
            buy_str = f"${r['buy_price']:.8f}"[:10]
        elif r["buy_price"] < 1:
            buy_str = f"${r['buy_price']:.6f}"
        else:
            buy_str = f"${r['buy_price']:.4f}"

        if r["current_price"] < 0.01:
            cur_str = f"${r['current_price']:.8f}"[:10]
        elif r["current_price"] < 1:
            cur_str = f"${r['current_price']:.6f}"
        else:
            cur_str = f"${r['current_price']:.4f}"

        val_str = f"${r['value_usdt']:.2f}"

        if r["buy_price"] > 0 and r["asset"] != "USDT":
            pnl = r["pnl_pct"]
            if pnl >= 0:
                pnl_str = f"+{pnl:.1f}%"
            else:
                pnl_str = f"{pnl:.1f}%"
            # Visual indicator
            if pnl >= 50:
                pnl_str = f"🟢{pnl_str}"
            elif pnl >= 0:
                pnl_str = f"🟡{pnl_str}"
            elif pnl > -30:
                pnl_str = f"🟠{pnl_str}"
            else:
                pnl_str = f"🔴{pnl_str}"
        else:
            pnl_str = "   ---  "

        loc = r["location"]

        print(f"│ {asset:<10} │ {qty_str:>16} │ {buy_str:>10} │ {cur_str:>10} │ {val_str:>10} │ {pnl_str:>8} │ {loc:<6} │")

    print("└────────────┴──────────────────┴────────────┴────────────┴────────────┴──────────┴────────┘")

    # Totales
    print()
    print(f"  💰 Valor Total del Portafolio:  ${total_value:.2f} USDT")
    if total_cost > 0:
        global_pnl = ((total_current_val - total_cost) / total_cost) * 100
        print(f"  💵 Total Invertido (compras):   ${total_cost:.2f} USDT")
        print(f"  📊 P&L Neto Global:            {global_pnl:+.2f}%")
        print(f"  📉 Pérdida/Ganancia Neta:      ${total_current_val - total_cost:+.2f} USDT")

    # Conteos rápidos
    winners = [r for r in with_cost if r["pnl_pct"] > 0]
    losers = [r for r in with_cost if r["pnl_pct"] < 0]
    print(f"\n  ✅ En ganancia: {len(winners)} activos")
    print(f"  ❌ En pérdida:  {len(losers)} activos")

if __name__ == "__main__":
    main()

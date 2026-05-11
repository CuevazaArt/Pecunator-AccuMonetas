import sys
import time
import json
from datetime import datetime, timezone
from binance.client import Client
from binance.exceptions import BinanceAPIException
import config

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

    print("=" * 90)
    print("  PECUNATOR - Alpha Profitability Monitor")
    print("  Analyzing: Buy price vs Current price + Market Momentum")
    print("=" * 90)
    print("\nFetching account data...")

    # =========================================================================
    # 1) Fetch balances with funds
    # =========================================================================
    account = client.get_account()
    balances = account.get("balances", [])

    # Fetch Earn positions too
    earn_positions = []
    current_page = 1
    while True:
        try:
            res = client.get_simple_earn_flexible_product_position(current=current_page, size=100)
            rows = res.get("rows", [])
            if not rows:
                break
            earn_positions.extend(rows)
            if len(earn_positions) >= res.get("total", 0):
                break
            current_page += 1
        except:
            break

    # Combine balances: Spot + Earn
    asset_holdings = {}
    for b in balances:
        asset = b["asset"]
        qty = float(b.get("free", 0)) + float(b.get("locked", 0))
        if qty > 0 and asset != "USDT":
            clean = asset[2:] if asset.startswith("LD") else asset
            if clean not in asset_holdings:
                asset_holdings[clean] = 0.0
            asset_holdings[clean] += qty

    for ep in earn_positions:
        asset = ep["asset"]
        qty = float(ep.get("totalAmount", 0))
        if qty > 0 and asset != "USDT":
            if asset not in asset_holdings:
                asset_holdings[asset] = 0.0
            asset_holdings[asset] += qty

    # =========================================================================
    # 2) Fetch current prices
    # =========================================================================
    tickers = client.get_all_tickers()
    prices = {t["symbol"]: float(t["price"]) for t in tickers}

    # =========================================================================
    # 3) Fetch exchange info to know which pairs exist
    # =========================================================================
    exchange_info = client.get_exchange_info()
    valid_symbols = {s["symbol"] for s in exchange_info["symbols"] if s["status"] == "TRADING"}

    # =========================================================================
    # 4) For each asset: calculate average buy price + momentum
    # =========================================================================
    results = []
    total_assets = len(asset_holdings)
    processed = 0

    for asset, total_qty in asset_holdings.items():
        symbol = asset + "USDT"
        if symbol not in valid_symbols:
            continue

        current_price = prices.get(symbol, 0)
        if current_price == 0:
            continue

        processed += 1
        sys.stdout.write(f"\r  Analizando {processed}/{total_assets}: {asset}...          ")
        sys.stdout.flush()

        # --- Average buy price (from historical trades) ---
        avg_buy_price = 0.0
        total_buy_qty = 0.0
        total_buy_cost = 0.0
        buy_date = None

        try:
            trades = client.get_my_trades(symbol=symbol, limit=50)
            # Solo considerar compras (isBuyer=True)
            buys = [t for t in trades if t.get("isBuyer")]
            if buys:
                for t in buys:
                    qty = float(t["qty"])
                    price = float(t["price"])
                    total_buy_qty += qty
                    total_buy_cost += qty * price
                # Date of the first buy
                buy_date = datetime.fromtimestamp(buys[0]["time"] / 1000, tz=timezone.utc)

                if total_buy_qty > 0:
                    avg_buy_price = total_buy_cost / total_buy_qty
        except:
            pass

        time.sleep(0.2)  # Rate limit

        # --- Momentum: 24h, 7d variation and recent speed ---
        price_change_24h = 0.0
        price_change_7d = 0.0
        volatility_1h = 0.0
        trend_direction = "→"

        try:
            # 1-hour klines (last 24)
            klines_1h = client.get_klines(symbol=symbol, interval="1h", limit=24)
            if len(klines_1h) >= 2:
                open_24h = float(klines_1h[0][1])
                close_now = float(klines_1h[-1][4])
                if open_24h > 0:
                    price_change_24h = ((close_now - open_24h) / open_24h) * 100

                # Last-hour volatility (high-low vs close)
                last_candle = klines_1h[-1]
                high_1h = float(last_candle[2])
                low_1h = float(last_candle[3])
                close_1h = float(last_candle[4])
                if close_1h > 0:
                    volatility_1h = ((high_1h - low_1h) / close_1h) * 100

                # Trend: compare last 3 candles
                if len(klines_1h) >= 3:
                    closes = [float(k[4]) for k in klines_1h[-3:]]
                    if closes[-1] > closes[-2] > closes[-3]:
                        trend_direction = "🚀"  # Rising strongly
                    elif closes[-1] > closes[-2]:
                        trend_direction = "📈"  # Rising
                    elif closes[-1] < closes[-2] < closes[-3]:
                        trend_direction = "📉"  # Falling strongly
                    elif closes[-1] < closes[-2]:
                        trend_direction = "⬇️"  # Falling
                    else:
                        trend_direction = "→"  # Sideways
        except:
            pass

        try:
            # Daily klines (last 7 days)
            klines_1d = client.get_klines(symbol=symbol, interval="1d", limit=7)
            if len(klines_1d) >= 2:
                open_7d = float(klines_1d[0][1])
                close_now_d = float(klines_1d[-1][4])
                if open_7d > 0:
                    price_change_7d = ((close_now_d - open_7d) / open_7d) * 100
        except:
            pass

        time.sleep(0.3)  # Rate limit

        # --- Calculate P&L ---
        pnl_pct = 0.0
        if avg_buy_price > 0:
            pnl_pct = ((current_price - avg_buy_price) / avg_buy_price) * 100

        value_usdt = total_qty * current_price

        # --- Action signal ---
        signal = ""
        if pnl_pct >= 100:
            signal = "🔥 SELL (>100% profit)"
        elif pnl_pct >= 50:
            signal = "⚡ Consider partial sell"
        elif pnl_pct >= 20 and price_change_24h < -5:
            signal = "⚠️ Profit declining, protect"
        elif price_change_24h >= 15:
            signal = "🚀 ACTIVE PUMP - watch for peak"
        elif price_change_24h >= 8:
            signal = "📈 Strong rise today"
        elif price_change_24h <= -10:
            signal = "📉 Strong drop today"
        elif pnl_pct < -30:
            signal = "💀 Significant loss"
        elif avg_buy_price == 0:
            signal = "❓ No buy history"

        results.append({
            "asset": asset,
            "qty": total_qty,
            "buy_price": avg_buy_price,
            "buy_date": buy_date,
            "current_price": current_price,
            "value_usdt": value_usdt,
            "pnl_pct": pnl_pct,
            "change_24h": price_change_24h,
            "change_7d": price_change_7d,
            "volatility_1h": volatility_1h,
            "trend": trend_direction,
            "signal": signal,
        })

    print(f"\r  Analysis complete: {processed} assets processed.              ")

    # =========================================================================
    # 5) Sort by P&L descending
    # =========================================================================
    # Separate: with buy history vs without history
    with_history = [r for r in results if r["buy_price"] > 0]
    without_history = [r for r in results if r["buy_price"] == 0]

    with_history.sort(key=lambda x: x["pnl_pct"], reverse=True)
    without_history.sort(key=lambda x: x["value_usdt"], reverse=True)

    # =========================================================================
    # 6) Print report
    # =========================================================================
    total_value = sum(r["value_usdt"] for r in results)
    total_cost = sum(r["qty"] * r["buy_price"] for r in with_history)
    total_current = sum(r["value_usdt"] for r in with_history)

    print("\n" + "=" * 120)
    print("  ASSETS WITH BUY HISTORY (P&L calculated)")
    print("=" * 120)
    print(f"{'Asset':<10} {'Buy':>10} {'Current':>10} {'P&L':>8} {'24h':>7} {'7d':>7} {'Vol1h':>6} {'Trend':>5} {'Value$':>10}  Signal")
    print("-" * 120)

    for r in with_history:
        buy_str = f"${r['buy_price']:.6f}" if r['buy_price'] < 1 else f"${r['buy_price']:.4f}"
        cur_str = f"${r['current_price']:.6f}" if r['current_price'] < 1 else f"${r['current_price']:.4f}"
        pnl_str = f"{r['pnl_pct']:+.1f}%"
        c24_str = f"{r['change_24h']:+.1f}%"
        c7d_str = f"{r['change_7d']:+.1f}%"
        vol_str = f"{r['volatility_1h']:.1f}%"
        val_str = f"${r['value_usdt']:.2f}"

        # Color indicators via text
        pnl_indicator = "🟢" if r['pnl_pct'] > 0 else "🔴" if r['pnl_pct'] < 0 else "⚪"

        print(f"{r['asset']:<10} {buy_str:>10} {cur_str:>10} {pnl_indicator}{pnl_str:>7} {c24_str:>7} {c7d_str:>7} {vol_str:>6} {r['trend']:>5} {val_str:>10}  {r['signal']}")

    if without_history:
        print("\n" + "=" * 120)
        print("  ASSETS WITHOUT BUY HISTORY (possibly airdrops, earn rewards, or Alpha)")
        print("=" * 120)
        print(f"{'Asset':<10} {'Current':>10} {'24h':>7} {'7d':>7} {'Vol1h':>6} {'Trend':>5} {'Value$':>10}  Signal")
        print("-" * 120)

        for r in without_history:
            cur_str = f"${r['current_price']:.6f}" if r['current_price'] < 1 else f"${r['current_price']:.4f}"
            c24_str = f"{r['change_24h']:+.1f}%"
            c7d_str = f"{r['change_7d']:+.1f}%"
            vol_str = f"{r['volatility_1h']:.1f}%"
            val_str = f"${r['value_usdt']:.2f}"

            print(f"{r['asset']:<10} {cur_str:>10} {c24_str:>7} {c7d_str:>7} {vol_str:>6} {r['trend']:>5} {val_str:>10}  {r['signal']}")

    # =========================================================================
    # 7) Final summary
    # =========================================================================
    print("\n" + "=" * 120)
    print("  SUMMARY")
    print("=" * 120)
    print(f"  Total portfolio value:    ${total_value:.2f} USDT")
    if total_cost > 0:
        global_pnl = ((total_current - total_cost) / total_cost) * 100
        print(f"  Total buy cost:        ${total_cost:.2f} USDT")
        print(f"  Global P&L:                   {global_pnl:+.2f}%")

    # Alertas principales
    pumps = [r for r in results if r["change_24h"] >= 10]
    dumps = [r for r in results if r["change_24h"] <= -10]
    big_winners = [r for r in with_history if r["pnl_pct"] >= 50]
    big_losers = [r for r in with_history if r["pnl_pct"] <= -30]

    if pumps:
        pump_list = ", ".join(r["asset"] + " (" + f"{r['change_24h']:+.1f}%)" for r in pumps)
        print(f"\n  🚀 ACTIVE PUMPS (>10% in 24h): {pump_list}")
    if dumps:
        dump_list = ", ".join(r["asset"] + " (" + f"{r['change_24h']:+.1f}%)" for r in dumps)
        print(f"  📉 ACTIVE DUMPS (<-10% in 24h): {dump_list}")
    if big_winners:
        win_list = ", ".join(r["asset"] + " (" + f"{r['pnl_pct']:+.1f}%)" for r in big_winners)
        print(f"  🔥 BIG WINNERS (>50% P&L): {win_list}")
    if big_losers:
        lose_list = ", ".join(r["asset"] + " (" + f"{r['pnl_pct']:+.1f}%)" for r in big_losers)
        print(f"  💀 BIG LOSERS (<-30% P&L): {lose_list}")

    print("\n" + "=" * 120)

if __name__ == "__main__":
    main()

import sys
import time
import json
from datetime import datetime, timezone, timedelta
from binance.client import Client
import config

def ts_to_date(ts_ms):
    return datetime.fromtimestamp(int(ts_ms)/1000, tz=timezone.utc).strftime("%Y-%m-%d")

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
    now_ts = int(time.time() * 1000)
    three_years_ago = now_ts - (1095 * 24 * 3600 * 1000)

    sys.stderr.write("FASE 1: Datos base...\n")
    account = client.get_account()
    balances = account.get("balances", [])
    tickers = client.get_all_tickers()
    prices = {t["symbol"]: float(t["price"]) for t in tickers}
    exchange_info = client.get_exchange_info()
    trading_symbols = [s["symbol"] for s in exchange_info["symbols"] if s["status"] == "TRADING" and s["symbol"].endswith("USDT")]

    # Collect assets that user has/had
    held_assets = set()
    for b in balances:
        if float(b.get("free",0)) + float(b.get("locked",0)) > 0:
            clean = b["asset"][2:] if b["asset"].startswith("LD") else b["asset"]
            held_assets.add(clean)

    relevant_symbols = [s for s in trading_symbols if s.replace("USDT","") in held_assets]
    sys.stderr.write(f"  {len(relevant_symbols)} pares relevantes encontrados.\n")
    time.sleep(1)

    # FASE 2: Trades Spot
    sys.stderr.write("FASE 2: Historial de trades spot...\n")
    all_trades = []
    batch_size = 40
    for i in range(0, len(relevant_symbols), batch_size):
        batch = relevant_symbols[i:i+batch_size]
        for sym in batch:
            try:
                trades = client.get_my_trades(symbol=sym, limit=1000)
                # Filter by time
                trades = [t for t in trades if t["time"] >= three_years_ago]
                for t in trades:
                    t["_symbol"] = sym
                all_trades.extend(trades)
            except:
                pass
            time.sleep(0.15)
        sys.stderr.write(f"  Lote {i//batch_size+1}/{(len(relevant_symbols)//batch_size)+1} completado ({len(all_trades)} trades)\n")
        if i + batch_size < len(relevant_symbols):
            time.sleep(5)

    # FASE 3: Préstamos
    sys.stderr.write("FASE 3: Historial de préstamos...\n")
    borrows, repays, ltv_adj = [], [], []
    page = 1
    while True:
        try:
            res = client.margin_v2_get_loan_flexible_borrow_history(current=page, limit=100, startTime=three_years_ago)
            rows = res.get("rows", [])
            if not rows: break
            borrows.extend(rows)
            if len(borrows) >= res.get("total", 0): break
            page += 1
        except: break
    time.sleep(1)

    page = 1
    while True:
        try:
            res = client.margin_v2_get_loan_flexible_repay_history(current=page, limit=100, startTime=three_years_ago)
            rows = res.get("rows", [])
            if not rows: break
            repays.extend(rows)
            if len(repays) >= res.get("total", 0): break
            page += 1
        except: break
    time.sleep(1)

    page = 1
    while True:
        try:
            res = client.margin_v2_get_loan_flexible_ltv_adjustment_history(current=page, limit=100, startTime=three_years_ago)
            rows = res.get("rows", [])
            if not rows: break
            ltv_adj.extend(rows)
            if len(ltv_adj) >= res.get("total", 0): break
            page += 1
        except: break
    time.sleep(1)

    ongoing_loans = []
    page = 1
    while True:
        try:
            res = client.margin_v2_get_loan_flexible_ongoing_orders(current=page, limit=100)
            rows = res.get("rows",[])
            if not rows: break
            ongoing_loans.extend(rows)
            if len(ongoing_loans) >= res.get("total",0): break
            page += 1
        except: break

    # FASE 4: Earn
    sys.stderr.write("FASE 4: Historial de Earn...\n")
    earn_subs, earn_redeems = [], []
    page = 1
    while True:
        try:
            res = client.margin_v1_get_simple_earn_flexible_history_subscription_record(current=page, size=100, startTime=three_years_ago)
            rows = res.get("rows",[])
            if not rows: break
            earn_subs.extend(rows)
            if len(earn_subs) >= res.get("total",0): break
            page += 1
        except: break
    time.sleep(1)

    page = 1
    while True:
        try:
            res = client.margin_v1_get_simple_earn_flexible_history_redemption_record(current=page, size=100, startTime=three_years_ago)
            rows = res.get("rows",[])
            if not rows: break
            earn_redeems.extend(rows)
            if len(earn_redeems) >= res.get("total",0): break
            page += 1
        except: break
    time.sleep(1)

    # FASE 5: Conversiones
    sys.stderr.write("FASE 5: Conversiones y otros...\n")
    converts = []
    window = 90 * 24 * 3600 * 1000
    cursor = three_years_ago
    while cursor < now_ts:
        end = min(cursor + window, now_ts)
        try:
            res = client.get_convert_trade_history(startTime=cursor, endTime=end, limit=1000)
            items = res.get("list", [])
            converts.extend(items)
        except: pass
        cursor = end
        time.sleep(0.5)

    # Dividends
    dividends = []
    try:
        res = client.get_asset_dividend_history(limit=500, startTime=three_years_ago)
        dividends = res.get("rows", [])
    except: pass

    # Dust log
    dust_log = []
    try:
        res = client.get_dust_log(startTime=three_years_ago)
        dust_log = res.get("results", {}).get("rows", []) if isinstance(res, dict) else []
    except: pass

    # Deposits & Withdrawals (90 day windows)
    deposits, withdrawals = [], []
    cursor = three_years_ago
    while cursor < now_ts:
        end = min(cursor + window, now_ts)
        try:
            res = client.get_deposit_history(startTime=cursor, endTime=end)
            if isinstance(res, list): deposits.extend(res)
        except: pass
        try:
            res = client.get_withdraw_history(startTime=cursor, endTime=end)
            if isinstance(res, list): withdrawals.extend(res)
        except: pass
        cursor = end
        time.sleep(0.5)

    sys.stderr.write("Generando reporte...\n")

    # ===================== ANÁLISIS =====================
    # Trades por tipo
    buys = [t for t in all_trades if t.get("isBuyer")]
    sells = [t for t in all_trades if not t.get("isBuyer")]

    total_buy_cost = sum(float(t["quoteQty"]) for t in buys)
    total_sell_revenue = sum(float(t["quoteQty"]) for t in sells)
    total_commission_usdt = 0
    for t in all_trades:
        comm = float(t.get("commission", 0))
        comm_asset = t.get("commissionAsset", "")
        if comm_asset == "USDT":
            total_commission_usdt += comm
        elif comm_asset + "USDT" in prices:
            total_commission_usdt += comm * prices[comm_asset + "USDT"]

    # P&L por activo
    asset_pnl = {}
    for t in all_trades:
        sym = t["_symbol"]
        asset = sym.replace("USDT", "")
        if asset not in asset_pnl:
            asset_pnl[asset] = {"bought": 0, "sold": 0, "qty_bought": 0, "qty_sold": 0, "trades": 0}
        qty = float(t["quoteQty"])
        asset_pnl[asset]["trades"] += 1
        if t.get("isBuyer"):
            asset_pnl[asset]["bought"] += qty
            asset_pnl[asset]["qty_bought"] += float(t["qty"])
        else:
            asset_pnl[asset]["sold"] += qty
            asset_pnl[asset]["qty_sold"] += float(t["qty"])

    # Préstamos
    total_borrowed = sum(float(b.get("initialLoanAmount", 0)) for b in borrows)
    total_repaid = sum(float(r.get("repayAmount", 0)) for r in repays)
    total_ongoing_debt = sum(float(l.get("totalDebt", 0)) for l in ongoing_loans)
    interest_estimated = total_ongoing_debt + total_repaid - total_borrowed

    # Colateral perdido (repays con collateralReturn = 0 implica liquidación parcial)
    forced_liquidations = [r for r in repays if float(r.get("collateralReturn", 0)) == 0 and float(r.get("repayAmount", 0)) > 0]
    forced_liq_total = sum(float(r.get("repayAmount", 0)) for r in forced_liquidations)

    # Conversiones
    convert_cost = sum(float(c.get("fromAmount",0)) for c in converts if c.get("fromAsset") == "USDT")
    convert_revenue = sum(float(c.get("toAmount",0)) for c in converts if c.get("toAsset") == "USDT")

    # Deposits/Withdrawals
    deposit_usdt = 0
    for d in deposits:
        amt = float(d.get("amount", 0))
        coin = d.get("coin", "")
        if coin == "USDT": deposit_usdt += amt
        elif coin + "USDT" in prices: deposit_usdt += amt * prices[coin + "USDT"]

    withdraw_usdt = 0
    for w in withdrawals:
        amt = float(w.get("amount", 0))
        coin = w.get("coin", "")
        if coin == "USDT": withdraw_usdt += amt
        elif coin + "USDT" in prices: withdraw_usdt += amt * prices[coin + "USDT"]

    # Valor actual del portafolio
    current_portfolio = 0
    for b in balances:
        asset = b["asset"]
        qty = float(b.get("free",0)) + float(b.get("locked",0))
        if qty > 0:
            if asset == "USDT": current_portfolio += qty
            elif asset + "USDT" in prices: current_portfolio += qty * prices[asset + "USDT"]

    # ===================== REPORTE =====================
    print("=" * 110)
    print("  PECUNATOR - AUDITORÍA FINANCIERA COMPLETA")
    print(f"  Período: {ts_to_date(three_years_ago)} → {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 110)

    print("\n┌─────────────────────────────────────────────────────────────────┐")
    print("│                    RESUMEN EJECUTIVO                           │")
    print("├─────────────────────────────────────┬─────────────────────────┤")
    print(f"│ Compras Spot (total gastado)        │ ${total_buy_cost:>20,.2f} │")
    print(f"│ Ventas Spot (total recibido)        │ ${total_sell_revenue:>20,.2f} │")
    print(f"│ P&L Spot (ventas - compras)         │ ${total_sell_revenue - total_buy_cost:>+20,.2f} │")
    print(f"│ Comisiones pagadas (est.)           │ ${total_commission_usdt:>20,.2f} │")
    print(f"│ Préstamos tomados                   │ ${total_borrowed:>20,.2f} │")
    print(f"│ Préstamos pagados                   │ ${total_repaid:>20,.2f} │")
    print(f"│ Deuda pendiente                     │ ${total_ongoing_debt:>20,.2f} │")
    print(f"│ Intereses pagados (est.)            │ ${max(interest_estimated,0):>20,.2f} │")
    print(f"│ Liquidaciones forzadas (pago sin    │                         │")
    print(f"│   devolución de colateral)          │ ${forced_liq_total:>20,.2f} │")
    print(f"│ Depósitos recibidos                 │ ${deposit_usdt:>20,.2f} │")
    print(f"│ Retiros enviados                    │ ${withdraw_usdt:>20,.2f} │")
    print(f"│ Conversiones (USDT gastado)         │ ${convert_cost:>20,.2f} │")
    print(f"│ Conversiones (USDT recibido)        │ ${convert_revenue:>20,.2f} │")
    print(f"│ Valor actual del portafolio         │ ${current_portfolio:>20,.2f} │")
    print("├─────────────────────────────────────┼─────────────────────────┤")
    net_result = current_portfolio + total_sell_revenue + withdraw_usdt - total_buy_cost - deposit_usdt - total_ongoing_debt
    print(f"│ RESULTADO NETO ESTIMADO             │ ${net_result:>+20,.2f} │")
    print("└─────────────────────────────────────┴─────────────────────────┘")

    # TOP ACTIVOS POR P&L
    print("\n" + "=" * 110)
    print("  DETALLE POR ACTIVO (Spot Trades)")
    print("=" * 110)
    print(f"{'Asset':<10} {'Comprado$':>12} {'Vendido$':>12} {'P&L Spot':>12} {'#Trades':>8} {'Holding$':>12} {'P&L Total':>12}")
    print("-" * 110)

    sorted_assets = sorted(asset_pnl.items(), key=lambda x: x[1]["sold"] - x[1]["bought"], reverse=True)
    for asset, data in sorted_assets:
        spot_pnl = data["sold"] - data["bought"]
        # Current holding value
        remaining = data["qty_bought"] - data["qty_sold"]
        cur_price = prices.get(asset + "USDT", 0)
        holding_val = max(remaining, 0) * cur_price
        total_pnl = spot_pnl + holding_val

        indicator = "🟢" if total_pnl > 0 else "🔴"
        print(f"{asset:<10} ${data['bought']:>10,.2f} ${data['sold']:>10,.2f} ${spot_pnl:>+10,.2f} {data['trades']:>8} ${holding_val:>10,.2f} {indicator}${total_pnl:>+9,.2f}")

    # PRÉSTAMOS DETALLE
    print("\n" + "=" * 110)
    print("  HISTORIAL DE PRÉSTAMOS")
    print("=" * 110)
    print(f"  Total préstamos tomados:           {len(borrows)}")
    print(f"  Total pagos realizados:            {len(repays)}")
    print(f"  Ajustes LTV (colateral añadido):   {len(ltv_adj)}")
    print(f"  Pagos sin devolución de colateral: {len(forced_liquidations)}")

    if forced_liquidations:
        print(f"\n  ⚠️  PAGOS SIN DEVOLUCIÓN DE COLATERAL (posibles liquidaciones parciales):")
        print(f"  {'Moneda':>8} {'Colateral':>10} {'Monto Pagado':>14} {'Fecha':>12}")
        for r in sorted(forced_liquidations, key=lambda x: float(x.get("repayAmount",0)), reverse=True)[:20]:
            print(f"  {r.get('loanCoin','?'):>8} {r.get('collateralCoin','?'):>10} ${float(r.get('repayAmount',0)):>12,.4f} {ts_to_date(r.get('repayTime',0)):>12}")

    if ltv_adj:
        print(f"\n  📊 AJUSTES DE LTV (colateral forzado a añadir):")
        for a in ltv_adj:
            col_coin = a.get("collateralCoin","?")
            col_amt = float(a.get("collateralAmount", 0))
            col_val = col_amt * prices.get(col_coin + "USDT", 0)
            pre_ltv = float(a.get("preLTV",0))*100
            aft_ltv = float(a.get("afterLTV",0))*100
            print(f"  {col_coin:>8} | {col_amt:>12.4f} (~${col_val:.2f}) | LTV: {pre_ltv:.1f}% → {aft_ltv:.1f}% | {ts_to_date(a.get('adjustTime',0))}")

    # EARN
    print("\n" + "=" * 110)
    print("  ACTIVIDAD EN EARN")
    print("=" * 110)
    print(f"  Suscripciones registradas:  {len(earn_subs)}")
    print(f"  Redenciones registradas:    {len(earn_redeems)}")

    # CONVERSIONES
    if converts:
        print("\n" + "=" * 110)
        print("  CONVERSIONES RÁPIDAS")
        print("=" * 110)
        print(f"  Total conversiones: {len(converts)}")
        print(f"  USDT gastado en conversiones: ${convert_cost:.2f}")
        print(f"  USDT recibido de conversiones: ${convert_revenue:.2f}")

    # DIVIDENDOS
    if dividends:
        print("\n" + "=" * 110)
        print("  AIRDROPS / DIVIDENDOS")
        print("=" * 110)
        div_total = 0
        for d in dividends:
            amt = float(d.get("amount",0))
            asset = d.get("asset","?")
            p = prices.get(asset + "USDT", 0)
            div_total += amt * p
        print(f"  Dividendos recibidos: {len(dividends)}")
        print(f"  Valor estimado actual: ${div_total:.2f} USDT")

    # ANÁLISIS FINAL
    print("\n" + "=" * 110)
    print("  DIAGNÓSTICO: ¿QUÉ HICISTE BIEN Y QUÉ MAL?")
    print("=" * 110)

    winners = [(a, d) for a, d in sorted_assets if d["sold"] - d["bought"] > 0]
    losers = [(a, d) for a, d in sorted_assets if d["sold"] - d["bought"] < 0]

    print(f"\n  ✅ LO QUE HICISTE BIEN:")
    if winners:
        win_total = sum(d["sold"]-d["bought"] for _,d in winners)
        print(f"     - {len(winners)} activos vendiste con ganancia, generando ${win_total:,.2f} USDT")
        top3 = winners[:3]
        for a, d in top3:
            print(f"       🏆 {a}: +${d['sold']-d['bought']:,.2f}")
    if earn_subs:
        print(f"     - Usaste Earn activamente ({len(earn_subs)} suscripciones), generando rendimiento pasivo")

    print(f"\n  ❌ LO QUE HICISTE MAL:")
    if losers:
        loss_total = sum(d["sold"]-d["bought"] for _,d in losers)
        print(f"     - {len(losers)} activos vendiste con pérdida, perdiendo ${abs(loss_total):,.2f} USDT")
        worst3 = losers[-3:]
        for a, d in worst3:
            print(f"       💀 {a}: ${d['sold']-d['bought']:,.2f}")

    if total_borrowed > 0:
        print(f"     - Tomaste ${total_borrowed:,.2f} en préstamos. Intereses acumulados: ~${max(interest_estimated,0):,.2f}")
    if forced_liquidations:
        print(f"     - {len(forced_liquidations)} pagos forzados sin devolución de colateral (${forced_liq_total:,.2f} USDT)")
    if total_commission_usdt > 10:
        print(f"     - Comisiones de trading acumuladas: ${total_commission_usdt:,.2f}")

    print(f"\n  📋 LECCIONES DETECTADAS:")
    if total_borrowed > total_buy_cost * 0.3:
        print(f"     ⚠️  Sobreexposición a préstamos: prestaste ${total_borrowed:,.2f} vs compraste ${total_buy_cost:,.2f}")
        print(f"        Regla sugerida: No prestar más del 20% del valor del portafolio.")
    if len(losers) > len(winners) * 2:
        print(f"     ⚠️  Ratio de acierto bajo: {len(winners)} ganadores vs {len(losers)} perdedores")
        print(f"        Regla sugerida: Implementar stop-loss automáticos al -15%.")
    if forced_liquidations:
        print(f"     ⚠️  Liquidaciones forzadas detectadas: el LTV subió demasiado sin intervención.")
        print(f"        Regla sugerida: Monitorear LTV diario, actuar si pasa del 65%.")

    print(f"\n{'=' * 110}")
    print(f"  Datos recopilados: {len(all_trades)} trades, {len(borrows)} préstamos,")
    print(f"  {len(repays)} pagos, {len(earn_subs)} suscripciones earn, {len(converts)} conversiones")
    print(f"{'=' * 110}")

if __name__ == "__main__":
    main()

import sys
import time
import json
from datetime import datetime, timezone, timedelta
from binance.client import Client
import config

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
    sys.stderr.write("Cargando datos de préstamos...\n")

    tickers = client.get_all_tickers()
    prices = {t["symbol"]: float(t["price"]) for t in tickers}

    # =========================================================================
    # 1) PRÉSTAMOS ACTIVOS (Flexible Loans)
    # =========================================================================
    ongoing = []
    page = 1
    while True:
        try:
            res = client.margin_v2_get_loan_flexible_ongoing_orders(current=page, limit=100)
            rows = res.get("rows", [])
            if not rows:
                break
            ongoing.extend(rows)
            if len(ongoing) >= res.get("total", 0):
                break
            page += 1
        except Exception as e:
            sys.stderr.write(f"Error obteniendo préstamos activos: {e}\n")
            break

    # =========================================================================
    # 2) HISTORIAL DE PRÉSTAMOS (Borrow History) - últimos 2 años
    # =========================================================================
    two_years_ago = int((datetime.now(timezone.utc) - timedelta(days=730)).timestamp() * 1000)

    borrows = []
    page = 1
    while True:
        try:
            res = client.margin_v2_get_loan_flexible_borrow_history(
                current=page, limit=100, startTime=two_years_ago
            )
            rows = res.get("rows", [])
            if not rows:
                break
            borrows.extend(rows)
            if len(borrows) >= res.get("total", 0):
                break
            page += 1
        except Exception as e:
            sys.stderr.write(f"Error obteniendo historial de préstamos: {e}\n")
            break

    # =========================================================================
    # 3) HISTORIAL DE PAGOS (Repay History) - últimos 2 años
    # =========================================================================
    repays = []
    page = 1
    while True:
        try:
            res = client.margin_v2_get_loan_flexible_repay_history(
                current=page, limit=100, startTime=two_years_ago
            )
            rows = res.get("rows", [])
            if not rows:
                break
            repays.extend(rows)
            if len(repays) >= res.get("total", 0):
                break
            page += 1
        except Exception as e:
            sys.stderr.write(f"Error obteniendo historial de pagos: {e}\n")
            break

    # =========================================================================
    # 4) HISTORIAL DE AJUSTES LTV - últimos 2 años
    # =========================================================================
    ltv_adjustments = []
    page = 1
    while True:
        try:
            res = client.margin_v2_get_loan_flexible_ltv_adjustment_history(
                current=page, limit=100, startTime=two_years_ago
            )
            rows = res.get("rows", [])
            if not rows:
                break
            ltv_adjustments.extend(rows)
            if len(ltv_adjustments) >= res.get("total", 0):
                break
            page += 1
        except Exception as e:
            # This endpoint may not exist or may fail, that's okay
            break

    # =========================================================================
    # IMPRIMIR REPORTE
    # =========================================================================
    print("=" * 110)
    print("  PECUNATOR - Reporte de Préstamos (Crypto Loans)")
    print(f"  Período: {datetime.fromtimestamp(two_years_ago/1000).strftime('%Y-%m-%d')} → {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 110)

    # ------- SECCIÓN 1: PRÉSTAMOS ACTIVOS -------
    print("\n┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐")
    print("│                              PRÉSTAMOS FLEXIBLES ACTIVOS                                                  │")
    print("├────────────┬────────────┬──────────────┬──────────────────┬──────────────┬────────┬───────────────────────┤")
    print("│ Préstamo   │ Colateral  │ Deuda (USDT) │ Colateral (Cant) │ Valor Col.$  │  LTV%  │ Estado                │")
    print("├────────────┼────────────┼──────────────┼──────────────────┼──────────────┼────────┼───────────────────────┤")

    total_debt = 0.0
    total_collateral_value = 0.0

    for loan in ongoing:
        loan_coin = loan.get("loanCoin", "?")
        col_coin = loan.get("collateralCoin", "?")
        debt = float(loan.get("totalDebt", 0))
        col_amount = float(loan.get("collateralAmount", 0))
        ltv = float(loan.get("currentLTV", 0)) * 100

        # Calcular valor del colateral en USDT
        col_symbol = col_coin + "USDT"
        col_price = prices.get(col_symbol, 0)
        col_value = col_amount * col_price

        total_debt += debt
        total_collateral_value += col_value

        # Riesgo de liquidación
        if ltv >= 85:
            status = "🔴 PELIGRO LIQUIDACIÓN"
        elif ltv >= 75:
            status = "🟠 RIESGO ALTO"
        elif ltv >= 65:
            status = "🟡 MODERADO"
        else:
            status = "🟢 SEGURO"

        debt_str = f"${debt:.2f}"
        col_qty_str = f"{col_amount:.4f}" if col_amount < 1000 else f"{col_amount:.1f}"
        col_val_str = f"${col_value:.2f}"
        ltv_str = f"{ltv:.1f}%"

        print(f"│ {loan_coin:<10} │ {col_coin:<10} │ {debt_str:>12} │ {col_qty_str:>16} │ {col_val_str:>12} │ {ltv_str:>6} │ {status:<21} │")

    print("├────────────┴────────────┼──────────────┼──────────────────┼──────────────┼────────┼───────────────────────┤")

    net_exposure = total_collateral_value - total_debt
    avg_ltv = (total_debt / total_collateral_value * 100) if total_collateral_value > 0 else 0

    print(f"│ {'TOTALES':<23} │ {f'${total_debt:.2f}':>12} │ {'':>16} │ {f'${total_collateral_value:.2f}':>12} │ {f'{avg_ltv:.1f}%':>6} │ {'':>21} │")
    print("└─────────────────────────┴──────────────┴──────────────────┴──────────────┴────────┴───────────────────────┘")

    print(f"\n  📊 Deuda Total:              ${total_debt:.2f} USDT")
    print(f"  🏦 Valor Total Colateral:    ${total_collateral_value:.2f} USDT")
    print(f"  💰 Exposición Neta:          ${net_exposure:+.2f} USDT {'(En riesgo)' if net_exposure < 0 else '(Cubierto)'}")
    print(f"  📐 LTV Promedio:             {avg_ltv:.1f}%")

    if avg_ltv >= 75:
        print("  ⚠️  ALERTA: Tu LTV promedio está MUY ALTO. Riesgo de liquidación parcial inminente.")
    elif avg_ltv >= 65:
        print("  ⚡ PRECAUCIÓN: LTV elevado. Considera repagar parte o agregar colateral.")

    # ------- SECCIÓN 2: HISTORIAL DE PRÉSTAMOS TOMADOS -------
    print("\n┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐")
    print("│                              HISTORIAL DE PRÉSTAMOS TOMADOS                                               │")
    print("├────────────┬────────────┬───────────────┬──────────────────┬─────────────────────┬─────────────────────────┤")
    print("│ Préstamo   │ Colateral  │ Monto Préstam │ Colateral Dado   │ Fecha               │ Estado                  │")
    print("├────────────┼────────────┼───────────────┼──────────────────┼─────────────────────┼─────────────────────────┤")

    total_borrowed = 0.0
    borrows_sorted = sorted(borrows, key=lambda x: int(x.get("borrowTime", 0)), reverse=True)

    for b in borrows_sorted:
        loan_coin = b.get("loanCoin", "?")
        col_coin = b.get("collateralCoin", "?")
        loan_amount = float(b.get("initialLoanAmount", 0))
        col_amount = float(b.get("initialCollateralAmount", 0))
        borrow_time = int(b.get("borrowTime", 0))
        status = b.get("status", "?")
        date_str = datetime.fromtimestamp(borrow_time / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

        total_borrowed += loan_amount

        loan_str = f"${loan_amount:.2f}" if loan_coin == "USDT" else f"{loan_amount:.4f} {loan_coin}"
        col_str = f"{col_amount:.6f}" if col_amount < 1 else f"{col_amount:.4f}"

        status_icon = "✅" if status == "SUCCESS" else "❌"

        print(f"│ {loan_coin:<10} │ {col_coin:<10} │ {loan_str:>13} │ {col_str:>16} │ {date_str:>19} │ {status_icon} {status:<22} │")

    print("├────────────┴────────────┼───────────────┼──────────────────┼─────────────────────┼─────────────────────────┤")
    print(f"│ {'TOTAL PRESTADO':<23} │ {f'${total_borrowed:.2f}':>13} │ {'':>16} │ {'':>19} │ {'':>23} │")
    print("└─────────────────────────┴───────────────┴──────────────────┴─────────────────────┴─────────────────────────┘")

    # ------- SECCIÓN 3: HISTORIAL DE PAGOS -------
    print("\n┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────┐")
    print("│                              HISTORIAL DE PAGOS / REPAGOS                                                 │")
    print("├────────────┬────────────┬───────────────┬──────────────────┬─────────────────────┬─────────────────────────┤")
    print("│ Préstamo   │ Colateral  │ Monto Pagado  │ Col. Devuelto    │ Fecha               │ Estado                  │")
    print("├────────────┼────────────┼───────────────┼──────────────────┼─────────────────────┼─────────────────────────┤")

    total_repaid = 0.0
    total_col_returned = {}
    repays_sorted = sorted(repays, key=lambda x: int(x.get("repayTime", 0)), reverse=True)

    for r in repays_sorted:
        loan_coin = r.get("loanCoin", "?")
        col_coin = r.get("collateralCoin", "?")
        repay_amount = float(r.get("repayAmount", 0))
        col_return = float(r.get("collateralReturn", 0))
        repay_time = int(r.get("repayTime", 0))
        status = r.get("repayStatus", "?")
        date_str = datetime.fromtimestamp(repay_time / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")

        total_repaid += repay_amount
        if col_coin not in total_col_returned:
            total_col_returned[col_coin] = 0.0
        total_col_returned[col_coin] += col_return

        repay_str = f"${repay_amount:.4f}" if loan_coin == "USDT" else f"{repay_amount:.4f} {loan_coin}"
        col_str = f"{col_return:.6f}" if col_return < 1 else f"{col_return:.4f}"
        if col_return == 0:
            col_str = "0 (sin devol.)"

        status_icon = "✅" if status == "REPAID" else "⏳"

        print(f"│ {loan_coin:<10} │ {col_coin:<10} │ {repay_str:>13} │ {col_str:>16} │ {date_str:>19} │ {status_icon} {status:<22} │")

    print("├────────────┴────────────┼───────────────┼──────────────────┼─────────────────────┼─────────────────────────┤")
    print(f"│ {'TOTAL PAGADO':<23} │ {f'${total_repaid:.2f}':>13} │ {'':>16} │ {'':>19} │ {'':>23} │")
    print("└─────────────────────────┴───────────────┴──────────────────┴─────────────────────┴─────────────────────────┘")

    # ------- SECCIÓN 4: ANÁLISIS DE PÉRDIDAS POR INTERESES -------
    interest_paid = total_debt + total_repaid - total_borrowed
    if interest_paid < 0:
        interest_paid = total_debt - (total_borrowed - total_repaid)

    print("\n" + "=" * 110)
    print("  ANÁLISIS FINANCIERO")
    print("=" * 110)
    print(f"  💸 Total Prestado (histórico):    ${total_borrowed:.2f} USDT")
    print(f"  💵 Total Pagado:                  ${total_repaid:.2f} USDT")
    print(f"  🏦 Deuda Pendiente:               ${total_debt:.2f} USDT")
    print(f"  📈 Intereses Acumulados (aprox):  ${interest_paid:.2f} USDT")
    print(f"  📉 Costo Neto de Préstamos:       ${total_repaid + total_debt - total_borrowed:+.2f} USDT")

    # Riesgo por colateral
    print(f"\n  {'─'*50}")
    print(f"  RIESGO DE LIQUIDACIÓN POR COLATERAL:")
    for loan in ongoing:
        col_coin = loan.get("collateralCoin", "?")
        debt = float(loan.get("totalDebt", 0))
        col_amount = float(loan.get("collateralAmount", 0))
        ltv = float(loan.get("currentLTV", 0))

        col_price = prices.get(col_coin + "USDT", 0)
        col_value = col_amount * col_price

        # Calcular a qué precio se liquidaría (LTV = 0.90 típicamente)
        liquidation_ltv = 0.90
        if col_amount > 0:
            liquidation_price = (debt * liquidation_ltv) / (col_amount * ltv) * col_price * ltv / liquidation_ltv
            # More precise: liquidation happens when debt / (col_amount * price) >= 0.90
            # So price_liq = debt / (col_amount * 0.90)
            liquidation_price = debt / (col_amount * liquidation_ltv)
            drop_needed = ((col_price - liquidation_price) / col_price) * 100 if col_price > 0 else 0

            danger = "🔴" if drop_needed < 5 else "🟠" if drop_needed < 15 else "🟡" if drop_needed < 30 else "🟢"

            print(f"  {danger} {col_coin:<8} | Precio actual: ${col_price:.4f} | Liquidación: ${liquidation_price:.4f} | Caída necesaria: {drop_needed:.1f}%")

    print(f"\n{'=' * 110}")

if __name__ == "__main__":
    main()

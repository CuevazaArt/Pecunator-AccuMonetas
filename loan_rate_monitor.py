#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   PECUNATOR — Monitor Horario de Tasas de Préstamo (Loans)      ║
║   Registra cada hora el interés anual (APR) de los préstamos    ║
║   flexibles disponibles para stablecoins en Binance Crypto Loan ║
╚══════════════════════════════════════════════════════════════════╝

Uso:
    python loan_rate_monitor.py           # Loop continuo (cada hora)
    python loan_rate_monitor.py --once    # Ejecutar una sola vez
    python loan_rate_monitor.py --report  # Ver historial del CSV

Genera:
    loan_rates_log.csv   — Historial acumulado hora a hora
    loan_rates_last.txt  — Último snapshot en formato tabla legible
"""

import sys
import time
import csv
import os
import argparse
from datetime import datetime, timezone
import config
from binance.client import Client

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────
STABLECOINS = {
    "USDT", "USDC", "BUSD", "FDUSD", "USDS",
    "DAI",  "TUSD", "USDP", "PYUSD", "USDE",
    "FRAX", "GUSD", "LUSD", "SUSD",  "CRVUSD",
}

LOG_FILE   = os.path.join(os.path.dirname(__file__), "loan_rates_log.csv")
SNAP_FILE  = os.path.join(os.path.dirname(__file__), "loan_rates_last.txt")
INTERVAL_S = 3600  # 1 hora

CSV_HEADERS = [
    "timestamp", "datetime_utc",
    "loan_coin",
    "interest_rate_hourly_pct",   # % por hora
    "interest_rate_daily_pct",    # % por día
    "interest_rate_annual_pct",   # APR anual estimado
    "min_loan_amount",
    "max_loan_amount",
]

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def now_ts():
    return int(time.time() * 1000)

def ts_to_str(ts_ms=None):
    if ts_ms is None:
        ts_ms = now_ts()
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def ensure_csv_header():
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()

def interest_to_apr(hourly_rate_str):
    """
    La API devuelve flexibleInterestRate como tasa ANUAL en decimales.
    Ej: 0.48694107 = 48.69% APR anual
    También calculamos daily y hourly para completar el cuadro.
    """
    try:
        annual = float(hourly_rate_str)       # ya es anual en decimales
        daily  = annual / 365
        hourly = annual / 8760
        return round(annual * 100, 6), round(daily * 100, 6), round(hourly * 100, 8)
    except (TypeError, ValueError):
        return 0.0, 0.0, 0.0

# ─── FETCH ────────────────────────────────────────────────────────────────────
def fetch_loan_rates(client):
    """Obtiene todos los productos de préstamo flexible y filtra stablecoins."""
    try:
        res  = client.margin_v2_get_loan_flexible_loanable_data()
        rows = res.get("rows", [])
        return [r for r in rows if r.get("loanCoin", "") in STABLECOINS]
    except Exception as e:
        sys.stderr.write(f"  [ERROR] fetch_loan_rates: {e}\n")
        return []

# ─── PARSE ────────────────────────────────────────────────────────────────────
def parse_record(row, ts_ms):
    coin   = row.get("loanCoin", "")
    rate   = row.get("flexibleInterestRate", "0")
    min_l  = row.get("flexibleMinLimit", "")
    max_l  = row.get("flexibleMaxLimit", "")
    annual_pct, daily_pct, hourly_pct = interest_to_apr(rate)

    return {
        "timestamp":                ts_ms,
        "datetime_utc":             ts_to_str(ts_ms),
        "loan_coin":                coin,
        "interest_rate_hourly_pct": hourly_pct,
        "interest_rate_daily_pct":  daily_pct,
        "interest_rate_annual_pct": annual_pct,
        "min_loan_amount":          min_l,
        "max_loan_amount":          max_l,
    }

# ─── SNAPSHOT LEGIBLE ─────────────────────────────────────────────────────────
def save_snapshot(records, ts_ms):
    records_sorted = sorted(records, key=lambda x: x["interest_rate_annual_pct"])

    lines = []
    lines.append("=" * 100)
    lines.append("  PECUNATOR — Tasas de Préstamo Flexible (Stablecoins)  │  Crypto Loan")
    lines.append(f"  Snapshot: {ts_to_str(ts_ms)} UTC")
    lines.append("=" * 100)
    lines.append("")
    lines.append(
        f"  {'Stablecoin':<12} {'APR Anual':>12} {'APR Diario':>12} {'APR Horario':>14} "
        f"{'Mín Préstamo':>14} {'Máx Préstamo':>16}  Nivel de costo"
    )
    lines.append(
        f"  {'─'*12} {'─'*12} {'─'*12} {'─'*14} {'─'*14} {'─'*16}  {'─'*20}"
    )

    for r in records_sorted:
        apr    = r["interest_rate_annual_pct"]
        daily  = r["interest_rate_daily_pct"]
        hourly = r["interest_rate_hourly_pct"]
        mn     = r["min_loan_amount"]
        mx     = r["max_loan_amount"]

        # Nivel de costo visual
        if apr < 5:
            level = "🟢 Muy barato"
        elif apr < 15:
            level = "🟡 Moderado"
        elif apr < 35:
            level = "🟠 Caro"
        else:
            level = "🔴 Muy caro"

        # Formatear máximo con separador de miles
        try:
            mx_fmt = f"{int(mx):,}"
        except (ValueError, TypeError):
            mx_fmt = str(mx)

        lines.append(
            f"  {r['loan_coin']:<12} {apr:>11.4f}% {daily:>11.6f}% {hourly:>13.8f}% "
            f"{mn:>14} {mx_fmt:>16}  {level}"
        )

    lines.append("")
    aprs = [r["interest_rate_annual_pct"] for r in records]
    if aprs:
        best  = min(records, key=lambda x: x["interest_rate_annual_pct"])
        worst = max(records, key=lambda x: x["interest_rate_annual_pct"])
        avg   = sum(aprs) / len(aprs)

        lines.append("─" * 100)
        lines.append(f"  Productos rastreados:       {len(records)}")
        lines.append(f"  💰 Más barato de pedir prestado:   {best['loan_coin']:<8} → {best['interest_rate_annual_pct']:.4f}% APR anual")
        lines.append(f"  💸 Más caro de pedir prestado:     {worst['loan_coin']:<8} → {worst['interest_rate_annual_pct']:.4f}% APR anual")
        lines.append(f"  📊 Promedio APR:                   {avg:.4f}%")

        # Comparación earn vs loan para USDT y USDC
        lines.append("")
        lines.append("  📌 REFERENCIA: Diferencial Earn vs Loan")
        lines.append("  ─────────────────────────────────────────────────────────")
        earn_rates = {"USDT": 3.0, "USDC": 5.0, "FDUSD": 0.6, "FRAX": 2.92}
        for coin, earn_apr in earn_rates.items():
            match = next((r for r in records if r["loan_coin"] == coin), None)
            if match:
                loan_apr = match["interest_rate_annual_pct"]
                spread = loan_apr - earn_apr
                arrow  = "↑" if spread > 0 else "↓"
                lines.append(
                    f"  {coin:<8}  Earn: {earn_apr:.2f}%  │  Loan: {loan_apr:.4f}%  │  "
                    f"Spread: {spread:+.4f}% {arrow}"
                )

    lines.append("=" * 100)

    with open(SNAP_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ─── REPORTE HISTÓRICO ────────────────────────────────────────────────────────
def print_history_report():
    if not os.path.exists(LOG_FILE):
        print("No hay historial aún. Ejecuta el monitor primero.")
        return

    history = {}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            coin = row["loan_coin"]
            if coin not in history:
                history[coin] = []
            history[coin].append({
                "dt":  row["datetime_utc"],
                "apr": float(row["interest_rate_annual_pct"] or 0),
            })

    print("=" * 90)
    print("  HISTORIAL TASAS LOAN — STABLECOINS")
    print("=" * 90)
    print(f"  {'Coin':<10} {'Registros':>10} {'APR Mín':>12} {'APR Máx':>12} {'APR Ult':>12}  Tendencia")
    print(f"  {'─'*10} {'─'*10} {'─'*12} {'─'*12} {'─'*12}  {'─'*10}")

    for coin, entries in sorted(history.items(), key=lambda x: x[1][-1]["apr"]):
        aprs  = [e["apr"] for e in entries]
        last  = aprs[-1]
        trend = "→ Estable"
        if len(aprs) >= 2:
            diff = aprs[-1] - aprs[-2]
            if diff > 0.5:    trend = "📈 Subiendo"
            elif diff < -0.5: trend = "📉 Bajando"

        print(
            f"  {coin:<10} {len(entries):>10} {min(aprs):>11.4f}% {max(aprs):>11.4f}% "
            f"{last:>11.4f}%  {trend}"
        )

    total_snapshots = len(set(e["dt"][:16] for entries in history.values() for e in entries))
    print(f"\n  Total snapshots registrados: {total_snapshots}")
    print("=" * 90)

# ─── CICLO PRINCIPAL ──────────────────────────────────────────────────────────
def run_cycle(client):
    ts  = now_ts()
    sys.stderr.write(f"\n[{ts_to_str(ts)}] Descargando tasas de préstamo (stablecoins)...\n")

    raw     = fetch_loan_rates(client)
    records = [parse_record(r, ts) for r in raw]

    if not records:
        sys.stderr.write("  [WARN] Sin datos de préstamo en este ciclo.\n")
        return 0

    # CSV
    ensure_csv_header()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerows(records)

    # Snapshot
    save_snapshot(records, ts)

    # Mostrar en pantalla
    with open(SNAP_FILE, "r", encoding="utf-8") as f:
        print(f.read())

    sys.stderr.write(f"  ✅ {len(records)} stablecoins registradas en {LOG_FILE}\n")
    return len(records)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="Monitor horario de tasas de préstamo para stablecoins")
    parser.add_argument("--once",   action="store_true", help="Ejecutar una vez y salir")
    parser.add_argument("--report", action="store_true", help="Ver historial del CSV")
    args = parser.parse_args()

    if args.report:
        print_history_report()
        return

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

    if args.once:
        run_cycle(client)
        return

    print("🔄 Monitor de tasas de préstamo iniciado. Intervalo: 1 hora. Ctrl+C para detener.\n")
    cycle = 0
    while True:
        cycle += 1
        sys.stderr.write(f"[Ciclo #{cycle}] ")
        try:
            run_cycle(client)
        except KeyboardInterrupt:
            print("\n⏹  Monitor detenido.")
            break
        except Exception as e:
            sys.stderr.write(f"  [ERROR] {e}\n")

        sys.stderr.write(f"  Próximo ciclo en {INTERVAL_S // 60} minutos...\n")
        try:
            time.sleep(INTERVAL_S)
        except KeyboardInterrupt:
            print("\n⏹  Monitor detenido.")
            break

if __name__ == "__main__":
    main()

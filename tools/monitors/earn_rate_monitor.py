#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   PECUNATOR — Monitor Horario de Tasas Earn (Stablecoins)       ║
║   Registra cada hora el APR/APY de todos los productos Earn      ║
║   disponibles para stablecoins, con sus límites de volumen.      ║
╚══════════════════════════════════════════════════════════════════╝

Uso:
    python earn_rate_monitor.py           # Corre indefinidamente (cada hora)
    python earn_rate_monitor.py --once    # Ejecutar solo una vez y salir
    python earn_rate_monitor.py --report  # Mostrar reporte del historial guardado

Genera:
    earn_rates_log.csv   — Registro histórico de tasas
    earn_rates_last.txt  — Último snapshot legible en pantalla
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
    "DAI",  "TUSD", "USDP", "GUSD",  "FRAX",
    "PYUSD","USDE", "CRVUSD","SUSD",  "LUSD",
}

LOG_FILE    = os.path.join(os.path.dirname(__file__), "earn_rates_log.csv")
SNAP_FILE   = os.path.join(os.path.dirname(__file__), "earn_rates_last.txt")
INTERVAL_S  = 3600  # 1 hora

CSV_HEADERS = [
    "timestamp", "datetime_utc", "type",
    "asset", "product_id", "duration_days",
    "apr_pct", "boost_apr_pct", "total_apr_pct",
    "min_amount", "max_personal_quota",
    "is_sold_out", "can_purchase", "status",
    "reward_asset",
]

# ─── HELPERS ──────────────────────────────────────────────────────────────────
def now_ts():
    return int(time.time() * 1000)

def ts_to_str(ts_ms=None):
    if ts_ms is None:
        ts_ms = now_ts()
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def pct(value_str, decimals=4):
    try:
        return round(float(value_str) * 100, decimals)
    except (TypeError, ValueError):
        return 0.0

def ensure_csv_header():
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()

# ─── FETCH ────────────────────────────────────────────────────────────────────
def fetch_flexible(client):
    """Devuelve lista de productos Flexible Earn para stablecoins."""
    products = []
    page = 1
    while True:
        try:
            res = client.get_simple_earn_flexible_product_list(current=page, size=100)
            rows = res.get("rows", [])
            if not rows:
                break
            for r in rows:
                if r.get("asset", "") in STABLECOINS:
                    products.append(r)
            if len(rows) < 100:
                break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            sys.stderr.write(f"  [WARN] Flexible page {page}: {e}\n")
            break
    return products

def fetch_locked(client):
    """Devuelve lista de productos Locked Earn para stablecoins."""
    products = []
    page = 1
    while True:
        try:
            res = client.get_simple_earn_locked_product_list(current=page, size=100)
            rows = res.get("rows", [])
            if not rows:
                break
            for r in rows:
                asset = r.get("detail", {}).get("asset", "")
                if asset in STABLECOINS:
                    products.append(r)
            if len(rows) < 100:
                break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            sys.stderr.write(f"  [WARN] Locked page {page}: {e}\n")
            break
    return products

# ─── PARSE ────────────────────────────────────────────────────────────────────
def parse_flexible(row, ts_ms):
    apr      = pct(row.get("latestAnnualPercentageRate", 0))
    tiers    = row.get("tierAnnualPercentageRate", {})
    # Si hay tiers, tomamos la tasa del primer tramo (la más alta)
    if tiers:
        best_tier = max(float(v) for v in tiers.values())
        apr = round(best_tier * 100, 4)

    return {
        "timestamp":         ts_ms,
        "datetime_utc":      ts_to_str(ts_ms),
        "type":              "FLEXIBLE",
        "asset":             row.get("asset", ""),
        "product_id":        row.get("productId", ""),
        "duration_days":     "",
        "apr_pct":           apr,
        "boost_apr_pct":     "",
        "total_apr_pct":     apr,
        "min_amount":        row.get("minPurchaseAmount", ""),
        "max_personal_quota":"",
        "is_sold_out":       row.get("isSoldOut", False),
        "can_purchase":      row.get("canPurchase", False),
        "status":            row.get("status", ""),
        "reward_asset":      row.get("asset", ""),
    }

def parse_locked(row, ts_ms):
    detail   = row.get("detail", {})
    quota    = row.get("quota", {})
    apr      = pct(detail.get("apr", 0))
    boost    = pct(detail.get("boostRewardApr", 0))
    total    = round(apr + boost, 4)

    return {
        "timestamp":         ts_ms,
        "datetime_utc":      ts_to_str(ts_ms),
        "type":              "LOCKED",
        "asset":             detail.get("asset", ""),
        "product_id":        row.get("projectId", ""),
        "duration_days":     detail.get("duration", ""),
        "apr_pct":           apr,
        "boost_apr_pct":     boost if boost > 0 else "",
        "total_apr_pct":     total,
        "min_amount":        quota.get("minimum", ""),
        "max_personal_quota":quota.get("totalPersonalQuota", ""),
        "is_sold_out":       detail.get("isSoldOut", False),
        "can_purchase":      detail.get("status", "") == "PURCHASING",
        "status":            detail.get("status", ""),
        "reward_asset":      detail.get("rewardAsset", ""),
    }

# ─── SNAPSHOT ─────────────────────────────────────────────────────────────────
def save_snapshot(records, ts_ms):
    """Guarda earn_rates_last.txt con la tabla legible del último ciclo."""
    flex    = [r for r in records if r["type"] == "FLEXIBLE"]
    locked  = [r for r in records if r["type"] == "LOCKED"]

    # Ordenar por APR descendente
    flex.sort(key=lambda x: x["total_apr_pct"], reverse=True)
    locked.sort(key=lambda x: x["total_apr_pct"], reverse=True)

    lines = []
    lines.append("=" * 105)
    lines.append(f"  PECUNATOR — Tasas Earn Stablecoins")
    lines.append(f"  Snapshot: {ts_to_str(ts_ms)} UTC")
    lines.append("=" * 105)

    # ── FLEXIBLE ──
    lines.append(f"\n  FLEXIBLE  ({len(flex)} productos)")
    lines.append(f"  {'Asset':<10} {'Producto':<16} {'APR%':>8} {'Min Suscr':>12} {'Disponible':>12} {'Estado':<14}")
    lines.append(f"  {'─'*10} {'─'*16} {'─'*8} {'─'*12} {'─'*12} {'─'*14}")
    for r in flex:
        avail   = "✅ Disponible" if r["can_purchase"] and not r["is_sold_out"] else "🔴 Agotado"
        apr_str = f"{r['total_apr_pct']:.4f}%"
        lines.append(
            f"  {r['asset']:<10} {str(r['product_id']):<16} {apr_str:>8} "
            f"{str(r['min_amount']):>12} {avail:>12} {r['status']:<14}"
        )

    # ── LOCKED ──
    lines.append(f"\n  BLOQUEADO  ({len(locked)} productos)")
    lines.append(
        f"  {'Asset':<10} {'Producto':<14} {'Días':>5} {'APR%':>8} {'Boost%':>8} "
        f"{'Total%':>8} {'Min':>10} {'Cuota Max':>14} {'Disponible':>12}"
    )
    lines.append(f"  {'─'*10} {'─'*14} {'─'*5} {'─'*8} {'─'*8} {'─'*8} {'─'*10} {'─'*14} {'─'*12}")
    for r in locked:
        boost_str = f"{r['boost_apr_pct']:.2f}%" if r["boost_apr_pct"] != "" else "  ---  "
        total_str = f"{r['total_apr_pct']:.2f}%"
        avail     = "✅" if r["can_purchase"] and not r["is_sold_out"] else "🔴"
        lines.append(
            f"  {r['asset']:<10} {str(r['product_id']):<14} {str(r['duration_days']):>5} "
            f"{r['apr_pct']:>7.2f}% {boost_str:>8} {total_str:>8} "
            f"{str(r['min_amount']):>10} {str(r['max_personal_quota']):>14} {avail:>12}"
        )

    # ── RESUMEN ──
    all_apr = [r["total_apr_pct"] for r in records if r["total_apr_pct"] > 0]
    lines.append(f"\n{'='*105}")
    lines.append(f"  Productos rastreados:  {len(records)}")
    if all_apr:
        lines.append(f"  APR más alto:          {max(all_apr):.4f}%")
        lines.append(f"  APR promedio:          {sum(all_apr)/len(all_apr):.4f}%")
        lines.append(f"  APR más bajo:          {min(all_apr):.4f}%")
    lines.append(f"{'='*105}")

    with open(SNAP_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ─── REPORTE HISTÓRICO ────────────────────────────────────────────────────────
def print_history_report():
    if not os.path.exists(LOG_FILE):
        print("No hay historial registrado aún. Ejecuta el monitor primero.")
        return

    snapshots = {}
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts  = row["timestamp"]
            key = f"{row['type']}|{row['asset']}|{row['product_id']}"
            if key not in snapshots:
                snapshots[key] = []
            snapshots[key].append({
                "ts":        ts,
                "dt":        row["datetime_utc"],
                "apr":       float(row["total_apr_pct"] or 0),
                "available": row["can_purchase"],
            })

    print("=" * 90)
    print("  HISTORIAL DE TASAS EARN — STABLECOINS")
    print("=" * 90)
    print(f"  {'Tipo':<10} {'Asset':<10} {'Producto':<18} {'Registros':>10} {'APR Mín':>10} {'APR Máx':>10} {'APR Ult':>10}")
    print(f"  {'─'*10} {'─'*10} {'─'*18} {'─'*10} {'─'*10} {'─'*10} {'─'*10}")

    for key, entries in sorted(snapshots.items(), key=lambda x: -max(e["apr"] for e in x[1])):
        parts   = key.split("|")
        tipo    = parts[0]
        asset   = parts[1]
        prod    = parts[2]
        aprs    = [e["apr"] for e in entries]
        last_dt = entries[-1]["dt"]
        print(
            f"  {tipo:<10} {asset:<10} {prod:<18} {len(entries):>10} "
            f"{min(aprs):>9.4f}% {max(aprs):>9.4f}% {aprs[-1]:>9.4f}%"
        )

    print(f"\n  Último registro: {entries[-1]['dt']} UTC")
    print("=" * 90)

# ─── CICLO PRINCIPAL ──────────────────────────────────────────────────────────
def run_cycle(client):
    ts   = now_ts()
    now  = ts_to_str(ts)
    sys.stderr.write(f"\n[{now}] Recopilando tasas Earn para stablecoins...\n")

    flex_raw    = fetch_flexible(client)
    locked_raw  = fetch_locked(client)

    records = []
    for r in flex_raw:
        records.append(parse_flexible(r, ts))
    for r in locked_raw:
        records.append(parse_locked(r, ts))

    if not records:
        sys.stderr.write("  [WARN] Sin datos obtenidos en este ciclo.\n")
        return 0

    # Guardar en CSV
    ensure_csv_header()
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writerows(records)

    # Guardar snapshot legible
    save_snapshot(records, ts)

    # Mostrar en pantalla también
    with open(SNAP_FILE, "r", encoding="utf-8") as f:
        print(f.read())

    sys.stderr.write(f"  ✅ {len(records)} productos registrados en {LOG_FILE}\n")
    return len(records)

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="Monitor horario de tasas Earn para stablecoins")
    parser.add_argument("--once",   action="store_true", help="Ejecutar solo una vez y salir")
    parser.add_argument("--report", action="store_true", help="Mostrar reporte del historial CSV")
    args = parser.parse_args()

    if args.report:
        print_history_report()
        return

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

    if args.once:
        run_cycle(client)
        return

    # Modo continuo — loop cada hora
    print("🔄 Monitor iniciado. Intervalo: 1 hora. Ctrl+C para detener.\n")
    cycle = 0
    while True:
        cycle += 1
        sys.stderr.write(f"[Ciclo #{cycle}] ", )
        try:
            run_cycle(client)
        except KeyboardInterrupt:
            print("\n⏹  Monitor detenido por el usuario.")
            break
        except Exception as e:
            sys.stderr.write(f"  [ERROR] {e}\n")

        sys.stderr.write(f"  Próximo ciclo en {INTERVAL_S//60} minutos...\n")
        try:
            time.sleep(INTERVAL_S)
        except KeyboardInterrupt:
            print("\n⏹  Monitor detenido por el usuario.")
            break

if __name__ == "__main__":
    main()

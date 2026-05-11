#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   PECUNATOR — Hourly Loan Rate Monitor (Loans)                   ║
║   Records the annual interest (APR) of flexible loans            ║
║   available for stablecoins on Binance Crypto Loan each hour     ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
    python loan_rate_monitor.py           # Continuous loop (every hour)
    python loan_rate_monitor.py --once    # Run once and exit
    python loan_rate_monitor.py --report  # View CSV history

Generates:
    loan_rates_log.csv   — Accumulated hourly history
    loan_rates_last.txt  — Latest snapshot in readable table format
"""

import sys
import time
import csv
import os
import argparse
from datetime import datetime, timezone
import config
from binance.client import Client

# ─── CONFIGURATION ────────────────────────────────────────────────────────────
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
    "interest_rate_hourly_pct",   # % per hour
    "interest_rate_daily_pct",    # % per day
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
    The API returns flexibleInterestRate as ANNUAL rate in decimals.
    E.g.: 0.48694107 = 48.69% annual APR
    We also compute daily and hourly to complete the table.
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
    """Fetches all flexible loan products and filters stablecoins."""
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
    lines.append("  PECUNATOR — Flexible Loan Rates (Stablecoins)  │  Crypto Loan")
    lines.append(f"  Snapshot: {ts_to_str(ts_ms)} UTC")
    lines.append("=" * 100)
    lines.append("")
    lines.append(
        f"  {'Stablecoin':<12} {'Annual APR':>12} {'Daily APR':>12} {'Hourly APR':>14} "
        f"{'Min Loan':>14} {'Max Loan':>16}  Cost level"
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

        # Visual cost level
        if apr < 5:
            level = "🟢 Very cheap"
        elif apr < 15:
            level = "🟡 Moderate"
        elif apr < 35:
            level = "🟠 Expensive"
        else:
            level = "🔴 Very expensive"

        # Format maximum with thousands separator
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
        lines.append(f"  Products tracked:       {len(records)}")
        lines.append(f"  💰 Cheapest to borrow:   {best['loan_coin']:<8} → {best['interest_rate_annual_pct']:.4f}% annual APR")
        lines.append(f"  💸 Most expensive to borrow:     {worst['loan_coin']:<8} → {worst['interest_rate_annual_pct']:.4f}% annual APR")
        lines.append(f"  📊 Average APR:                   {avg:.4f}%")

        # Earn vs loan comparison for USDT and USDC
        lines.append("")
        lines.append("  📌 REFERENCE: Earn vs Loan Spread")
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

# ─── HISTORICAL REPORT ────────────────────────────────────────────────────────
def print_history_report():
    if not os.path.exists(LOG_FILE):
        print("No history yet. Run the monitor first.")
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
    print("  LOAN RATE HISTORY — STABLECOINS")
    print("=" * 90)
    print(f"  {'Coin':<10} {'Records':>10} {'Min APR':>12} {'Max APR':>12} {'Last APR':>12}  Trend")
    print(f"  {'─'*10} {'─'*10} {'─'*12} {'─'*12} {'─'*12}  {'─'*10}")

    for coin, entries in sorted(history.items(), key=lambda x: x[1][-1]["apr"]):
        aprs  = [e["apr"] for e in entries]
        last  = aprs[-1]
        trend = "→ Stable"
        if len(aprs) >= 2:
            diff = aprs[-1] - aprs[-2]
            if diff > 0.5:    trend = "📈 Rising"
            elif diff < -0.5: trend = "📉 Falling"

        print(
            f"  {coin:<10} {len(entries):>10} {min(aprs):>11.4f}% {max(aprs):>11.4f}% "
            f"{last:>11.4f}%  {trend}"
        )

    total_snapshots = len(set(e["dt"][:16] for entries in history.values() for e in entries))
    print(f"\n  Total snapshots recorded: {total_snapshots}")
    print("=" * 90)

# ─── MAIN CYCLE ──────────────────────────────────────────────────────────────
def run_cycle(client):
    ts  = now_ts()
    sys.stderr.write(f"\n[{ts_to_str(ts)}] Downloading loan rates (stablecoins)...\n")

    raw     = fetch_loan_rates(client)
    records = [parse_record(r, ts) for r in raw]

    if not records:
        sys.stderr.write("  [WARN] No loan data in this cycle.\n")
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

    sys.stderr.write(f"  ✅ {len(records)} stablecoins recorded in {LOG_FILE}\n")
    return len(records)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description="Hourly loan rate monitor for stablecoins")
    parser.add_argument("--once",   action="store_true", help="Run once and exit")
    parser.add_argument("--report", action="store_true", help="View CSV history")
    args = parser.parse_args()

    if args.report:
        print_history_report()
        return

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})

    if args.once:
        run_cycle(client)
        return

    print("🔄 Loan rate monitor started. Interval: 1 hour. Ctrl+C to stop.\n")
    cycle = 0
    while True:
        cycle += 1
        sys.stderr.write(f"[Cycle #{cycle}] ")
        try:
            run_cycle(client)
        except KeyboardInterrupt:
            print("\n⏹  Monitor stopped.")
            break
        except Exception as e:
            sys.stderr.write(f"  [ERROR] {e}\n")

        sys.stderr.write(f"  Next cycle in {INTERVAL_S // 60} minutes...\n")
        try:
            time.sleep(INTERVAL_S)
        except KeyboardInterrupt:
            print("\n⏹  Monitor stopped.")
            break

if __name__ == "__main__":
    main()

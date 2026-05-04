import sys
import time
from binance.client import Client
import config

# ─── CLASIFICACIÓN MANUAL POR CATEGORÍA ───────────────────────────────────────
# Basado en conocimiento del mercado cripto
MEME_TOKENS = {
    "DOGE","SHIB","PEPE","FLOKI","BONK","WIF","MEME","NEIRO","DOGS",
    "1000CAT","HMSTR","PENGU","BABY","LUNC","BOME","CHEEMS","MOG",
    "TURBO","BRETT","SUNDOG","MOODENG","PNUT","ACT","POPCAT"
}

DEFI_TOKENS = {
    "UNI","AAVE","COMP","MKR","SNX","YFI","CRV","SUSHI","1INCH",
    "LQTY","GNS","PENDLE","GMX","DYDX","BAL","CREAM","ALPHA","DEXE",
    "BANANA","MAV","COW","ORCA"
}

LAYER1_TOKENS = {
    "ETH","BNB","SOL","ADA","AVAX","DOT","ATOM","NEAR","FTM","ONE",
    "ALGO","HBAR","EGLD","ICP","SUI","APT","SEI","INJ","TRX","XLM",
    "XRP","LTC","BCH","ETC","ZEC","DASH","DCR","QTUM","NEO","GAS",
    "VET","IOTA","ROSE","KAVA","BERA","LAYER"
}

LAYER2_TOKENS = {
    "MATIC","ARB","OP","IMX","STRK","MANTA","METIS","BOBA","LRC",
    "LOOPRING","SCROLL","ZKSYNC","LINEA","ZK","TAIKO"
}

INFRA_TOKENS = {
    "LINK","GRT","FIL","AR","STORJ","OCEAN","API3","BAND","RLC",
    "RNDR","FET","AGIX","OCEAN","NMR","PYTH","JTO","W","SXT",
    "INIT","HOME","RESOLV","USUAL","SOLV"
}

GAMING_NFT_TOKENS = {
    "AXS","MANA","SAND","ENJ","GALA","ILV","GODS","ATLAS","POLIS",
    "GMT","GST","STEPN","CATI","PIXEL","PORTAL","YGG","MAGIC",
    "RONIN","ACE","BEAM","BEAMX","VIC","ANIME"
}

EXCHANGE_TOKENS = {
    "BNB","CRO","OKB","FTT","HT","KCS","GT","LEO","NEXO","KITE"
}

AI_TOKENS = {
    "FET","AGIX","OCEAN","RLC","NMR","ARKM","TAO","NEAR","OLAS",
    "ATH","ORAI","PHB","PROMPT"
}

RWA_TOKENS = {
    "ONDO","ZCOIN","PAXG","EURT","CACHE","RIO","MPL","TRU","CPOOL","POLYX"
}

def get_category(asset):
    if asset in MEME_TOKENS: return "MEME"
    if asset in AI_TOKENS: return "IA/AI"
    if asset in RWA_TOKENS: return "RWA"
    if asset in LAYER2_TOKENS: return "L2"
    if asset in LAYER1_TOKENS: return "L1/BlockChain"
    if asset in DEFI_TOKENS: return "DeFi"
    if asset in GAMING_NFT_TOKENS: return "Gaming/NFT"
    if asset in INFRA_TOKENS: return "Infraestructura"
    if asset in EXCHANGE_TOKENS: return "Exchange Token"
    return "Alpha/Otro"

def get_recovery_score(asset, price, volume_24h, price_change_24h, market_cap_rank=None):
    """Score de 0-10 basado en señales disponibles."""
    score = 5  # base

    # Volumen alto = más probabilidad de sobrevivir
    if volume_24h > 10_000_000: score += 2
    elif volume_24h > 1_000_000: score += 1
    elif volume_24h < 100_000: score -= 2
    elif volume_24h < 10_000: score -= 3

    # Si es L1 o L2 conocido, bonus
    if asset in LAYER1_TOKENS or asset in LAYER2_TOKENS: score += 1
    if asset in DEFI_TOKENS or asset in INFRA_TOKENS: score += 1

    # Memes: más volatiles, pueden explotar pero también morir
    if asset in MEME_TOKENS: score += 0  # neutral, son especulativos

    # Precio: si es muy bajo puede ser señal de muerte
    if price > 0 and price < 0.000001: score -= 3

    return max(0, min(10, score))

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
    sys.stderr.write("Cargando datos...\n")

    # Datos del exchange (para detectar delistados)
    exchange_info = client.get_exchange_info()
    symbol_status = {}
    for s in exchange_info["symbols"]:
        if s["symbol"].endswith("USDT"):
            asset = s["symbol"].replace("USDT", "")
            symbol_status[asset] = s["status"]  # TRADING, BREAK, END_OF_DAY, etc.

    # Todos los tickers con volumen y precio
    tickers_24h = client.get_ticker()
    ticker_map = {}
    for t in tickers_24h:
        sym = t["symbol"]
        if sym.endswith("USDT"):
            asset = sym.replace("USDT", "")
            ticker_map[asset] = {
                "price": float(t.get("lastPrice", 0)),
                "volume_usdt": float(t.get("quoteVolume", 0)),
                "change_24h": float(t.get("priceChangePercent", 0)),
                "high_24h": float(t.get("highPrice", 0)),
                "low_24h": float(t.get("lowPrice", 0)),
            }

    # Balances de Spot
    account = client.get_account()
    holdings = {}
    for b in account.get("balances", []):
        asset = b["asset"]
        qty = float(b.get("free", 0)) + float(b.get("locked", 0))
        if qty > 0:
            clean = asset[2:] if asset.startswith("LD") else asset
            holdings[clean] = holdings.get(clean, 0.0) + qty

    # Earn Flexible
    page = 1
    while True:
        try:
            res = client.get_simple_earn_flexible_product_position(current=page, size=100)
            rows = res.get("rows", [])
            if not rows: break
            for ep in rows:
                a = ep["asset"]
                q = float(ep.get("totalAmount", 0))
                if q > 0: holdings[a] = holdings.get(a, 0.0) + q
            if len(rows) < 100: break
            page += 1
        except: break

    # Earn Locked
    page = 1
    while True:
        try:
            res = client.get_simple_earn_locked_product_position(current=page, size=100)
            rows = res.get("rows", [])
            if not rows: break
            for ep in rows:
                a = ep.get("asset", "")
                q = float(ep.get("amount", 0))
                if q > 0: holdings[a] = holdings.get(a, 0.0) + q
            if len(rows) < 100: break
            page += 1
        except: break

    sys.stderr.write(f"  {len(holdings)} activos en portfolio\n")

    # ─── CLASIFICAR ───────────────────────────────────────────────────────────
    categories = {}
    delisted = []
    no_pair = []

    for asset, qty in holdings.items():
        if asset in ("USDT", "BUSD", "USDC", "FDUSD", "USDS"): continue

        t = ticker_map.get(asset, {})
        price = t.get("price", 0)
        volume = t.get("volume_usdt", 0)
        change = t.get("change_24h", 0)
        status = symbol_status.get(asset, None)

        value_usdt = qty * price

        # Detectar delistados o sin par
        if status is None and price == 0:
            no_pair.append({"asset": asset, "qty": qty, "reason": "Sin par USDT en Binance"})
            continue
        if status and status != "TRADING":
            delisted.append({"asset": asset, "qty": qty, "price": price, "value": value_usdt, "status": status})
            continue

        category = get_category(asset)
        score = get_recovery_score(asset, price, volume, change)

        entry = {
            "asset": asset,
            "qty": qty,
            "price": price,
            "value_usdt": value_usdt,
            "volume_24h": volume,
            "change_24h": change,
            "score": score,
            "category": category,
        }

        if category not in categories:
            categories[category] = []
        categories[category].append(entry)

    # ─── IMPRIMIR REPORTE ─────────────────────────────────────────────────────
    print("=" * 115)
    print("  PECUNATOR — CLASIFICACIÓN DE PORTAFOLIO POR CATEGORÍA Y PROBABILIDAD DE RECUPERACIÓN")
    print("=" * 115)
    print()

    # Ordenar categorías por valor total descendente
    cat_order = ["L1/BlockChain", "DeFi", "IA/AI", "RWA", "Infraestructura", "L2", "Gaming/NFT", "Exchange Token", "MEME", "Alpha/Otro"]

    total_portfolio = 0

    for cat in cat_order:
        tokens = categories.get(cat, [])
        if not tokens: continue

        # Ordenar por score desc, luego por valor desc
        tokens.sort(key=lambda x: (x["score"], x["value_usdt"]), reverse=True)
        cat_value = sum(t["value_usdt"] for t in tokens)
        total_portfolio += cat_value

        # Etiqueta de categoría
        cat_icons = {
            "L1/BlockChain": "⛓️  L1 / BLOCKCHAIN",
            "DeFi": "💱 DeFi",
            "IA/AI": "🤖 Inteligencia Artificial",
            "RWA": "🏦 Real World Assets",
            "Infraestructura": "🔧 Infraestructura Web3",
            "L2": "⚡ Layer 2",
            "Gaming/NFT": "🎮 Gaming / NFT",
            "Exchange Token": "🏛️  Exchange Tokens",
            "MEME": "🐸 MEME Coins",
            "Alpha/Otro": "🔮 Alpha / Proyectos Nuevos",
        }

        print(f"\n{'─'*115}")
        print(f"  {cat_icons.get(cat, cat)}   |   {len(tokens)} tokens   |   Valor total: ${cat_value:,.2f} USDT")
        print(f"{'─'*115}")
        print(f"  {'SCORE':>5}  {'Asset':<10} {'Cantidad':>14} {'Precio':>12} {'Val.USD':>10} {'Vol.24h':>14} {'Δ24h':>8}  Análisis")
        print(f"  {'─'*5}  {'─'*10} {'─'*14} {'─'*12} {'─'*10} {'─'*14} {'─'*8}  {'─'*30}")

        for t in tokens:
            score = t["score"]
            if score >= 8:
                score_icon = f"🟢 {score}/10"
                analysis = "Alta prob. de pump en bull run"
            elif score >= 6:
                score_icon = f"🟡 {score}/10"
                analysis = "Posibilidad moderada de subida"
            elif score >= 4:
                score_icon = f"🟠 {score}/10"
                analysis = "Incierto, bajo volumen"
            else:
                score_icon = f"🔴 {score}/10"
                analysis = "Riesgo alto / posible muerte"

            price = t["price"]
            if price < 0.0001:
                price_str = f"${price:.8f}"
            elif price < 1:
                price_str = f"${price:.6f}"
            else:
                price_str = f"${price:.4f}"

            vol = t["volume_24h"]
            if vol >= 1_000_000:
                vol_str = f"${vol/1_000_000:.1f}M"
            elif vol >= 1_000:
                vol_str = f"${vol/1_000:.1f}K"
            else:
                vol_str = f"${vol:.0f}"

            qty_str = f"{t['qty']:.4f}" if t["qty"] < 10000 else f"{t['qty']:.1f}"
            chg = t["change_24h"]
            chg_str = f"{chg:+.1f}%"

            print(f"  {score_icon}  {t['asset']:<10} {qty_str:>14} {price_str:>12} ${t['value_usdt']:>9.2f} {vol_str:>14} {chg_str:>8}  {analysis}")

    # ─── SIN PAR USDT (posibles delistados o tokens exóticos) ─────────────────
    if no_pair:
        print(f"\n{'─'*115}")
        print(f"  ❓ SIN PAR USDT EN BINANCE   |   {len(no_pair)} tokens   |   Posibles delistados o tokens solo en DEX")
        print(f"{'─'*115}")
        print(f"  {'Asset':<12} {'Cantidad':>16}  Acción recomendada")
        print(f"  {'─'*12} {'─'*16}  {'─'*50}")
        for t in no_pair:
            qty_str = f"{t['qty']:.4f}" if t["qty"] < 10000 else f"{t['qty']:.1f}"
            print(f"  {t['asset']:<12} {qty_str:>16}  ⚠️  Buscar en DEX (Uniswap/PancakeSwap) o retiro a wallet propia")

    # ─── DELISTADOS CON STATUS CONOCIDO ───────────────────────────────────────
    if delisted:
        print(f"\n{'─'*115}")
        print(f"  🚫 DELISTADOS / SUSPENDIDOS EN BINANCE   |   {len(delisted)} tokens")
        print(f"{'─'*115}")
        print(f"  {'Asset':<12} {'Cantidad':>16} {'Precio':>12} {'Valor':>10} {'Status':>15}  Acción")
        print(f"  {'─'*12} {'─'*16} {'─'*12} {'─'*10} {'─'*15}  {'─'*40}")
        for t in delisted:
            qty_str = f"{t['qty']:.4f}" if t["qty"] < 10000 else f"{t['qty']:.1f}"
            price_str = f"${t['price']:.6f}" if t["price"] > 0 else "N/D"
            action = "Retirar a wallet + vender en DEX" if t["price"] > 0 else "Verificar si aún existe el proyecto"
            print(f"  {t['asset']:<12} {qty_str:>16} {price_str:>12} ${t['value']:>9.4f} {t['status']:>15}  {action}")

    # ─── RESUMEN FINAL ─────────────────────────────────────────────────────────
    print(f"\n{'='*115}")
    print(f"  RESUMEN GLOBAL")
    print(f"{'='*115}")

    all_tokens = []
    for tokens in categories.values():
        all_tokens.extend(tokens)

    high_prob = [t for t in all_tokens if t["score"] >= 8]
    med_prob = [t for t in all_tokens if 6 <= t["score"] < 8]
    low_prob = [t for t in all_tokens if 4 <= t["score"] < 6]
    risky = [t for t in all_tokens if t["score"] < 4]

    print(f"  🟢 Alta probabilidad (score 8-10): {len(high_prob):>3} tokens | ${sum(t['value_usdt'] for t in high_prob):>8,.2f} USDT")
    print(f"  🟡 Probabilidad moderada (6-7):    {len(med_prob):>3} tokens | ${sum(t['value_usdt'] for t in med_prob):>8,.2f} USDT")
    print(f"  🟠 Incierto (4-5):                 {len(low_prob):>3} tokens | ${sum(t['value_usdt'] for t in low_prob):>8,.2f} USDT")
    print(f"  🔴 Alto riesgo / posible muerte:   {len(risky):>3} tokens | ${sum(t['value_usdt'] for t in risky):>8,.2f} USDT")
    print(f"  ❓ Sin par USDT (DEX/delistados):  {len(no_pair)+len(delisted):>3} tokens")
    print(f"  {'─'*60}")
    print(f"  💰 Valor total clasificado:                  ${total_portfolio:>8,.2f} USDT")
    print(f"{'='*115}")

if __name__ == "__main__":
    main()

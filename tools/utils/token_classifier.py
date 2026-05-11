import sys
import time
from binance.client import Client
import config

# ─── MANUAL CLASSIFICATION BY CATEGORY ───────────────────────────────────────
# Based on crypto market knowledge
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
    if asset in INFRA_TOKENS: return "Infrastructure"
    if asset in EXCHANGE_TOKENS: return "Exchange Token"
    return "Alpha/Other"

def get_recovery_score(asset, price, volume_24h, price_change_24h, market_cap_rank=None):
    """Score from 0-10 based on available signals."""
    score = 5  # base

    # High volume = higher probability of survival
    if volume_24h > 10_000_000: score += 2
    elif volume_24h > 1_000_000: score += 1
    elif volume_24h < 100_000: score -= 2
    elif volume_24h < 10_000: score -= 3

    # If it's a known L1 or L2, bonus
    if asset in LAYER1_TOKENS or asset in LAYER2_TOKENS: score += 1
    if asset in DEFI_TOKENS or asset in INFRA_TOKENS: score += 1

    # Memes: more volatile, can explode but also die
    if asset in MEME_TOKENS: score += 0  # neutral, speculative

    # Price: if very low it can be a death signal
    if price > 0 and price < 0.000001: score -= 3

    return max(0, min(10, score))

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
    sys.stderr.write("Loading data...\n")

    # Exchange data (to detect delisted tokens)
    exchange_info = client.get_exchange_info()
    symbol_status = {}
    for s in exchange_info["symbols"]:
        if s["symbol"].endswith("USDT"):
            asset = s["symbol"].replace("USDT", "")
            symbol_status[asset] = s["status"]  # TRADING, BREAK, END_OF_DAY, etc.

    # All tickers with volume and price
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

    sys.stderr.write(f"  {len(holdings)} assets in portfolio\n")

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

        # Detect delisted or missing pairs
        if status is None and price == 0:
            no_pair.append({"asset": asset, "qty": qty, "reason": "No USDT pair on Binance"})
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

    # ─── PRINT REPORT ─────────────────────────────────────────────────────────
    print("=" * 115)
    print("  PECUNATOR — PORTFOLIO CLASSIFICATION BY CATEGORY AND RECOVERY PROBABILITY")
    print("=" * 115)
    print()

    # Sort categories by total value descending
    cat_order = ["L1/BlockChain", "DeFi", "IA/AI", "RWA", "Infrastructure", "L2", "Gaming/NFT", "Exchange Token", "MEME", "Alpha/Other"]

    total_portfolio = 0

    for cat in cat_order:
        tokens = categories.get(cat, [])
        if not tokens: continue

        # Sort by score desc, then by value desc
        tokens.sort(key=lambda x: (x["score"], x["value_usdt"]), reverse=True)
        cat_value = sum(t["value_usdt"] for t in tokens)
        total_portfolio += cat_value

        # Category label
        cat_icons = {
            "L1/BlockChain": "⛓️  L1 / BLOCKCHAIN",
            "DeFi": "💱 DeFi",
            "IA/AI": "🤖 Artificial Intelligence",
            "RWA": "🏦 Real World Assets",
            "Infrastructure": "🔧 Web3 Infrastructure",
            "L2": "⚡ Layer 2",
            "Gaming/NFT": "🎮 Gaming / NFT",
            "Exchange Token": "🏛️  Exchange Tokens",
            "MEME": "🐸 MEME Coins",
            "Alpha/Other": "🔮 Alpha / New Projects",
        }

        print(f"\n{'─'*115}")
        print(f"  {cat_icons.get(cat, cat)}   |   {len(tokens)} tokens   |   Total value: ${cat_value:,.2f} USDT")
        print(f"{'─'*115}")
        print(f"  {'SCORE':>5}  {'Asset':<10} {'Quantity':>14} {'Price':>12} {'Val.USD':>10} {'Vol.24h':>14} {'Δ24h':>8}  Analysis")
        print(f"  {'─'*5}  {'─'*10} {'─'*14} {'─'*12} {'─'*10} {'─'*14} {'─'*8}  {'─'*30}")

        for t in tokens:
            score = t["score"]
            if score >= 8:
                score_icon = f"🟢 {score}/10"
                analysis = "High prob. of pump in bull run"
            elif score >= 6:
                score_icon = f"🟡 {score}/10"
                analysis = "Moderate chance of rise"
            elif score >= 4:
                score_icon = f"🟠 {score}/10"
                analysis = "Uncertain, low volume"
            else:
                score_icon = f"🔴 {score}/10"
                analysis = "High risk / possible death"

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

    # ─── NO USDT PAIR (possibly delisted or exotic tokens) ─────────────────────
    if no_pair:
        print(f"\n{'─'*115}")
        print(f"  ❓ NO USDT PAIR ON BINANCE   |   {len(no_pair)} tokens   |   Possibly delisted or DEX-only tokens")
        print(f"{'─'*115}")
        print(f"  {'Asset':<12} {'Quantity':>16}  Recommended action")
        print(f"  {'─'*12} {'─'*16}  {'─'*50}")
        for t in no_pair:
            qty_str = f"{t['qty']:.4f}" if t["qty"] < 10000 else f"{t['qty']:.1f}"
            print(f"  {t['asset']:<12} {qty_str:>16}  ⚠️  Search on DEX (Uniswap/PancakeSwap) or withdraw to own wallet")

    # ─── DELISTED WITH KNOWN STATUS ───────────────────────────────────────────
    if delisted:
        print(f"\n{'─'*115}")
        print(f"  🚫 DELISTED / SUSPENDED ON BINANCE   |   {len(delisted)} tokens")
        print(f"{'─'*115}")
        print(f"  {'Asset':<12} {'Quantity':>16} {'Price':>12} {'Value':>10} {'Status':>15}  Action")
        print(f"  {'─'*12} {'─'*16} {'─'*12} {'─'*10} {'─'*15}  {'─'*40}")
        for t in delisted:
            qty_str = f"{t['qty']:.4f}" if t["qty"] < 10000 else f"{t['qty']:.1f}"
            price_str = f"${t['price']:.6f}" if t["price"] > 0 else "N/D"
            action = "Withdraw to wallet + sell on DEX" if t["price"] > 0 else "Verify if the project still exists"
            print(f"  {t['asset']:<12} {qty_str:>16} {price_str:>12} ${t['value']:>9.4f} {t['status']:>15}  {action}")

    # ─── FINAL SUMMARY ─────────────────────────────────────────────────────────
    print(f"\n{'='*115}")
    print(f"  GLOBAL SUMMARY")
    print(f"{'='*115}")

    all_tokens = []
    for tokens in categories.values():
        all_tokens.extend(tokens)

    high_prob = [t for t in all_tokens if t["score"] >= 8]
    med_prob = [t for t in all_tokens if 6 <= t["score"] < 8]
    low_prob = [t for t in all_tokens if 4 <= t["score"] < 6]
    risky = [t for t in all_tokens if t["score"] < 4]

    print(f"  🟢 High probability (score 8-10): {len(high_prob):>3} tokens | ${sum(t['value_usdt'] for t in high_prob):>8,.2f} USDT")
    print(f"  🟡 Moderate probability (6-7):    {len(med_prob):>3} tokens | ${sum(t['value_usdt'] for t in med_prob):>8,.2f} USDT")
    print(f"  🟠 Uncertain (4-5):                 {len(low_prob):>3} tokens | ${sum(t['value_usdt'] for t in low_prob):>8,.2f} USDT")
    print(f"  🔴 High risk / possible death:   {len(risky):>3} tokens | ${sum(t['value_usdt'] for t in risky):>8,.2f} USDT")
    print(f"  ❓ No USDT pair (DEX/delisted):  {len(no_pair)+len(delisted):>3} tokens")
    print(f"  {'─'*60}")
    print(f"  💰 Total classified value:                  ${total_portfolio:>8,.2f} USDT")
    print(f"{'='*115}")

if __name__ == "__main__":
    main()

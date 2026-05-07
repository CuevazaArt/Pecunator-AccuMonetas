import sys
import time
import config
from binance.client import Client
from binance.exceptions import BinanceAPIException

def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')

    client = Client(config.api_key, config.api_secret, requests_params={'timeout': 30})
    print("Obteniendo balances de Spot...")

    try:
        account = client.get_account()
        balances = account.get("balances", [])
    except Exception as e:
        print(f"Error conectando a Binance: {e}")
        return

    # Filtrar activos con saldo disponible (free > 0), excluir USDT
    spot_balances = [
        b for b in balances
        if float(b.get("free", 0)) > 0 and b["asset"] != "USDT"
    ]

    print(f"Activos con saldo en Spot: {len(spot_balances)}")
    print("=" * 75)

    subscribed_count = 0
    skipped_count = 0

    for b in spot_balances:
        asset = b["asset"]
        free_qty = b["free"]

        # Saltar activos LD que aún estén atrapados en Earn
        if asset.startswith("LD"):
            print(f"Saltando {asset}: Ya es un token de Earn.")
            skipped_count += 1
            continue

        print(f"\n--- {asset} (Disponible: {free_qty}) ---")

        # =============================================
        # 1) Buscar productos Locked (mayor APR)
        # =============================================
        best_locked = None
        try:
            locked_res = client.get_simple_earn_locked_product_list(asset=asset, size=50)
            locked_rows = locked_res.get("rows", [])
            for prod in locked_rows:
                detail = prod.get("detail", {})
                if detail.get("status") != "PURCHASING" or detail.get("isSoldOut", True):
                    continue
                minimum = float(prod.get("quota", {}).get("minimum", 0))
                if float(free_qty) < minimum:
                    continue
                apr = float(detail.get("apr", 0))
                if best_locked is None or apr > best_locked["apr"]:
                    best_locked = {
                        "projectId": prod["projectId"],
                        "apr": apr,
                        "duration": detail.get("duration", "?"),
                        "minimum": minimum,
                        "type": "LOCKED"
                    }
        except Exception as e:
            print(f"  Advertencia al buscar Locked: {e}")

        # =============================================
        # 2) Buscar productos Flexible
        # =============================================
        best_flexible = None
        try:
            flex_res = client.get_simple_earn_flexible_product_list(asset=asset, size=10)
            flex_rows = flex_res.get("rows", [])
            for prod in flex_rows:
                if prod.get("status") != "PURCHASING" or prod.get("isSoldOut", True):
                    continue
                min_purchase = float(prod.get("minPurchaseAmount", 0))
                if float(free_qty) < min_purchase:
                    continue
                apr = float(prod.get("latestAnnualPercentageRate", 0))
                # Revisar si hay tiers con mejor tasa
                tiers = prod.get("tierAnnualPercentageRate", {})
                for tier_range, tier_apr in tiers.items():
                    tier_apr_f = float(tier_apr)
                    if tier_apr_f > apr:
                        apr = tier_apr_f
                if best_flexible is None or apr > best_flexible["apr"]:
                    best_flexible = {
                        "productId": prod["productId"],
                        "apr": apr,
                        "type": "FLEXIBLE"
                    }
        except Exception as e:
            print(f"  Advertencia al buscar Flexible: {e}")

        # =============================================
        # 3) Elegir el mejor producto (mayor APR gana)
        # =============================================
        chosen = None
        if best_locked and best_flexible:
            chosen = best_locked if best_locked["apr"] >= best_flexible["apr"] else best_flexible
        elif best_locked:
            chosen = best_locked
        elif best_flexible:
            chosen = best_flexible

        if not chosen:
            print(f"  Sin productos Earn disponibles para {asset}. Saltando.")
            skipped_count += 1
            time.sleep(0.5)
            continue

        apr_pct = chosen["apr"] * 100

        # =============================================
        # 4) Suscribir al producto elegido
        # =============================================
        if chosen["type"] == "LOCKED":
            print(f"  Mejor opción: LOCKED ({chosen['duration']} días) | APR: {apr_pct:.2f}% | ID: {chosen['projectId']}")
            try:
                res = client.subscribe_simple_earn_locked_product(
                    projectId=chosen["projectId"],
                    amount=free_qty,
                    autoSubscribe=True
                )
                print(f"  -> ¡Suscrito exitosamente a Locked Earn!")
                subscribed_count += 1
            except BinanceAPIException as e:
                print(f"  -> Error API: {e}")
                # Fallback: intentar con Flexible si Locked falla
                if best_flexible:
                    print(f"  Intentando fallback a Flexible (APR: {best_flexible['apr']*100:.2f}%)...")
                    try:
                        res = client.subscribe_simple_earn_flexible_product(
                            productId=best_flexible["productId"],
                            amount=free_qty,
                            autoSubscribe=True
                        )
                        print(f"  -> ¡Suscrito a Flexible Earn como fallback!")
                        subscribed_count += 1
                    except Exception as e2:
                        print(f"  -> Fallback también falló: {e2}")
            except Exception as e:
                print(f"  -> Error inesperado: {e}")
        else:
            print(f"  Mejor opción: FLEXIBLE | APR: {apr_pct:.2f}% | ID: {chosen['productId']}")
            try:
                res = client.subscribe_simple_earn_flexible_product(
                    productId=chosen["productId"],
                    amount=free_qty,
                    autoSubscribe=True
                )
                print(f"  -> ¡Suscrito exitosamente a Flexible Earn!")
                subscribed_count += 1
            except BinanceAPIException as e:
                print(f"  -> Error API: {e}")
            except Exception as e:
                print(f"  -> Error inesperado: {e}")

        # Esperar 1 segundo para respetar los límites de la API
        time.sleep(1.0)

    print("\n" + "=" * 75)
    print(f"Proceso finalizado.")
    print(f"  Activos suscritos a Earn: {subscribed_count}")
    print(f"  Activos saltados:         {skipped_count}")

if __name__ == "__main__":
    main()

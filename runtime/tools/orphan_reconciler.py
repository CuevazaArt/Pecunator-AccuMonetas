"""Orphan order detection and reconciliation — finds orders in Binance but not in Louise DB."""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from runtime.core.louise_db import LouiseDB
from runtime.connectors.binance_gateway import BinanceGateway

_LOG = logging.getLogger("pecunator.tools.orphan_reconciler")


class OrphanOrderMeta:
    """Metadata about an orphan order."""

    def __init__(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
        price: Decimal,
        status: str,
        time_ms: int,
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.status = status
        self.time_ms = time_ms

    def to_dict(self) -> Dict:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": str(self.quantity),
            "price": str(self.price),
            "status": self.status,
            "time_ms": self.time_ms,
        }


class OrphanReconciler:
    """Scans for orphaned orders and provides adoption/cancellation options."""

    def __init__(self, db: LouiseDB, gateway: BinanceGateway):
        self.db = db
        self.gateway = gateway

    async def scan_orphans(self, symbol: str = "BTCUSDT") -> List[OrphanOrderMeta]:
        """
        Scan Binance for all orders on symbol, compare against Louise DB.
        Returns list of orphaned orders (in Binance but not in DB).
        """
        if not self.gateway or not self.gateway._client:
            raise RuntimeError("Gateway not connected or no client available")

        try:
            # Fetch all orders from Binance for this symbol (open + closed)
            binance_orders = await self.gateway._client.get_all_orders(symbol=symbol)
            _LOG.info("Fetched %d orders from Binance for %s", len(binance_orders), symbol)
        except Exception as e:
            _LOG.error("Failed to fetch orders from Binance: %s", e)
            raise

        # Collect all purchase order IDs from Louise DB
        louise_order_ids = set()
        try:
            all_bots = self.db.get_all_bots()
            for bot in all_bots:
                bot_id = bot["bot_id"]
                all_epochs = self.db.get_all_epochs(bot_id)
                for epoch in all_epochs:
                    epoch_id = epoch["epoch_id"]
                    purchases = self.db.get_epoch_purchases(epoch_id)
                    for purchase in purchases:
                        if purchase.get("order_id"):
                            louise_order_ids.add(str(purchase["order_id"]))
        except Exception as e:
            _LOG.error("Failed to scan Louise DB: %s", e)
            raise

        # Find orphans: in Binance but not in Louise
        orphans = []
        for order in binance_orders:
            order_id = str(order["orderId"])
            if order_id not in louise_order_ids:
                # Only flag non-empty fills
                if order["status"] == "FILLED" and float(order["executedQty"]) > 0:
                    orphan = OrphanOrderMeta(
                        order_id=order_id,
                        symbol=order["symbol"],
                        side=order["side"],
                        quantity=Decimal(str(order["executedQty"])),
                        price=Decimal(str(order["price"])),
                        status=order["status"],
                        time_ms=order["time"],
                    )
                    orphans.append(orphan)
                    _LOG.warning("Found orphan order: %s", orphan.to_dict())

        return orphans

    async def adopt_orphan(
        self,
        orphan: OrphanOrderMeta,
        bot_id: str,
        epoch_id: str,
    ) -> bool:
        """
        Adopt an orphaned order by inserting it into Louise DB.
        Returns True on success, False otherwise.
        """
        try:
            # Verify bot and epoch exist
            bot = self.db.get_bot(bot_id)
            if not bot:
                _LOG.error("Bot %s not found", bot_id)
                return False

            epoch = self.db.get_epoch(epoch_id)
            if not epoch:
                _LOG.error("Epoch %s not found", epoch_id)
                return False

            # Calculate cost USDT based on execution price
            cost_usdt = float(orphan.quantity) * float(orphan.price)

            # Insert purchase record
            purchase_id = f"adopted_{orphan.order_id}"
            self.db.add_purchase(
                purchase_id=purchase_id,
                bot_id=bot_id,
                epoch_id=epoch_id,
                price_at_buy=float(orphan.price),
                volume=float(orphan.quantity),
                cost_usdt=cost_usdt,
                order_id=orphan.order_id,
                status="FILLED",
            )

            # Update epoch stats (increment num_purchases, total_cost, recalc avg_buy_price)
            purchases = self.db.get_epoch_purchases(epoch_id)
            total_cost = sum(p["cost_usdt"] for p in purchases)
            total_qty = sum(p["volume"] for p in purchases)
            avg_price = total_cost / total_qty if total_qty > 0 else 0

            self.db.update_epoch_stats(
                epoch_id=epoch_id,
                num_purchases=len(purchases),
                total_cost=total_cost,
                avg_buy_price=avg_price,
            )

            _LOG.info(
                "Adopted orphan order %s into bot %s epoch %s",
                orphan.order_id,
                bot_id,
                epoch_id,
            )
            return True
        except Exception as e:
            _LOG.error("Failed to adopt orphan %s: %s", orphan.order_id, e)
            return False

    async def cancel_orphan(self, orphan: OrphanOrderMeta) -> bool:
        """
        Cancel an orphaned order on Binance (if still open).
        Returns True on success, False otherwise.
        """
        if orphan.status != "NEW":
            _LOG.info("Order %s already %s, skipping cancel", orphan.order_id, orphan.status)
            return True

        try:
            await self.gateway._client.cancel_order(
                symbol=orphan.symbol,
                origClientOrderId=orphan.order_id,
            )
            _LOG.info("Cancelled orphan order %s", orphan.order_id)
            return True
        except Exception as e:
            _LOG.error("Failed to cancel orphan order %s: %s", orphan.order_id, e)
            return False

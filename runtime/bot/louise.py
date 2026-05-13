import logging
import asyncio
import time
from decimal import Decimal
import os
from typing import Optional, Dict, Any

from runtime.core.louise_db import LouiseDB
from runtime.core.event_bus import EventBus
from runtime.core.api_governor import get_api_governor, P_TRADING
from runtime.core.api_fuse import get_api_fuse
from runtime.core.exchange_filters import get_exchange_filters
from runtime.core.alert_dispatcher import get_alert_dispatcher
from runtime.core.budget_guard import get_budget_guard
from runtime.core.settings import (
    louise_price_staleness_sec,
    louise_min_usdt_balance,
    louise_cooldown_buy_fail_sec,
    louise_cooldown_gateway_fail_sec,
    louise_default_max_position_size_usdt,
    louise_default_max_purchases_per_epoch,
    louise_default_max_drawdown_pct,
)

logger = logging.getLogger("louise_bot")

class LouiseBotRunner:
    """
    Main runner for a Louise bot instance.
    Implements pure DCA downside-only strategy.
    Immortality & Crash-recovery built-in via SQLite DB.
    """

    def __init__(self, bot_id: str, db: LouiseDB, bus: EventBus, gateway: Any):
        self.bot_id = bot_id
        self.db = db
        self.bus = bus
        self.gateway = gateway
        self.config: Optional[Dict[str, Any]] = None
        self.active_epoch: Optional[Dict[str, Any]] = None

        self.current_price: Decimal = Decimal("0")
        self.last_price_timestamp: int = 0
        self.usdt_free_balance: Decimal = Decimal("0")
        self.pending_orders: Dict[str, Dict[str, Any]] = {}
        self.cooldown_until: int = 0

        self._running = False
        self._task: Optional[asyncio.Task] = None

    def initialize(self) -> bool:
        """Loads bot configuration and active epoch from database."""
        self.config = self.db.get_bot(self.bot_id)
        if not self.config:
            logger.error(f"Bot {self.bot_id} not found in database.")
            return False

        self.active_epoch = self.db.get_active_epoch(self.bot_id)

        # Subscribe to websocket data for price & balances (zero REST weight)
        symbol = self.config['symbol']
        self.bus.subscribe(f"market.ticker.{symbol}", self._on_ticker)
        self.bus.subscribe("account.balances", self._on_balances)
        self.bus.subscribe("account.execution_report", self._on_execution_report)

        logger.info(f"Initialized LouiseBot {self.bot_id} on {symbol} (subaccount: {self.config.get('subaccount', 'bluechip')}). Active epoch: {self.active_epoch['epoch_id'] if self.active_epoch else 'None'}")
        return True

    def _on_ticker(self, data: Dict[str, Any]):
        """Callback for websocket live price stream."""
        if 'c' in data:
            self.current_price = Decimal(str(data['c']))
            self.last_price_timestamp = int(time.time())

    def _on_balances(self, balances: list):
        """Callback for websocket balances stream."""
        for b in balances:
            if b.get("asset") == "USDT":
                self.usdt_free_balance = Decimal(str(b.get("free", "0")))
                break

    def _on_execution_report(self, event: Dict[str, Any]):
        client_oid = str(event.get('c', ''))
        status = event.get('X')
        order_id = str(event.get('i', ''))

        if client_oid in self.pending_orders and status == 'FILLED':
            meta = self.pending_orders.pop(client_oid)

            if meta['type'] == 'BUY':
                volume = Decimal(str(event.get('z', '0'))) # Cumulative filled quantity
                cost_usdt = Decimal(str(event.get('Z', '0'))) # Cumulative quote asset transacted qty
                price_at_buy = cost_usdt / volume if volume > Decimal("0") else Decimal(str(event.get('p', '0')))

                # order_id makes this unique even if two fills arrive in the same second
                purchase_id = f"pur_{self.bot_id}_{int(time.time())}_{order_id or client_oid}"
                self.db.add_purchase(
                    purchase_id, self.bot_id, meta['epoch_id'],
                    float(price_at_buy), float(volume), float(cost_usdt), order_id, "FILLED"
                )

                # Record to global budget guard
                from runtime.core.budget_guard import get_budget_guard
                get_budget_guard().record_spend(self.bot_id, self.config["symbol"], "BUY", cost_usdt)

                # Update epoch stats
                epoch = meta['epoch']
                new_purchases = epoch['num_purchases'] + 1

                old_cost = Decimal(str(epoch['total_cost']))
                old_avg_price = Decimal(str(epoch['avg_buy_price']))

                new_cost = old_cost + cost_usdt
                current_total_vol = (old_cost / old_avg_price) if old_avg_price > Decimal("0") else Decimal("0")
                new_total_vol = current_total_vol + volume
                new_avg_price = new_cost / new_total_vol if new_total_vol > Decimal("0") else price_at_buy

                self.db.update_epoch_stats(meta['epoch_id'], new_purchases, float(new_cost), float(new_avg_price))
                self.active_epoch = self.db.get_active_epoch(self.bot_id)
                logger.info(f"{self.bot_id}: Buy WS confirmed. New avg price: {new_avg_price:.4f}")

            elif meta['type'] == 'SELL':
                status = meta.get('status', 'CLOSED_SUCCESSFUL')
                self.db.close_epoch(meta['epoch_id'], float(meta['current_price']), float(meta['final_value']), float(meta['profit_usdt']), float(meta['profit_pct']), status=status)
                self.active_epoch = None
                logger.info(f"{self.bot_id}: Sell WS confirmed. Epoch closed with status {status} ({meta['profit_pct']:.2f}%)!")

    async def start(self):
        if not self.config:
            raise RuntimeError("Bot not initialized. Call initialize() first.")

        self._running = True
        self.db.update_bot_status(self.bot_id, "RUNNING")
        self.config['status'] = "RUNNING"
        self._task = asyncio.create_task(self._main_loop())
        logger.info(f"Bot {self.bot_id} started loop.")

    async def _main_loop(self):
        """Main loop that runs every poll_interval_seconds. Respects shutdown flag."""
        while self._running:
            # Check if graceful shutdown was requested
            try:
                from runtime.api.lifespan import is_shutdown_requested
                if is_shutdown_requested():
                    logger.info(f"Shutdown flag detected, stopping {self.bot_id}")
                    break
            except Exception:
                pass

            try:
                await self.poll_market()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in {self.bot_id} main loop: {e}")

            # Sleep for the configured interval
            interval = self.config.get('poll_interval_seconds', 300)
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info(f"{self.bot_id} sleep interrupted by cancellation")
                break

    async def poll_market(self):
        """
        Main logic for the pure DCA bot.
        """
        now = int(time.time())
        if self.config["status"] not in ["ACCUMULATING", "RUNNING"]:
            return

        if now < self.cooldown_until:
            return

        symbol = self.config["symbol"]

        # Ensure filters are loaded
        filters = get_exchange_filters().get(symbol)
        if not filters and getattr(self.gateway, "_client", None):
            try:
                filters = await get_exchange_filters().ensure_loaded(symbol, self.gateway._client)
            except Exception as e:
                logger.warning(f"{self.bot_id}: Failed to load exchange filters: {e}")

        # Check for stale price data (env-tunable, default 15s)
        staleness_sec = louise_price_staleness_sec()
        if self.current_price <= Decimal("0") or (now - self.last_price_timestamp > staleness_sec):
            logger.debug(f"{self.bot_id}: Waiting for fresh price feed (>{staleness_sec}s stale)...")
            return

        min_balance = Decimal(str(louise_min_usdt_balance()))
        if self.usdt_free_balance < min_balance:
            logger.warning(
                f"{self.bot_id}: Insufficient USDT in spot wallet (< {min_balance}). "
                f"Currently have {self.usdt_free_balance}."
            )
            return

        fuse = get_api_fuse()
        if fuse.is_tripped():
            logger.warning(f"{self.bot_id}: API Fuse is tripped. Skipping cycle.")
            return

        gov = get_api_governor()
        if not gov.can_execute("binance", P_TRADING, 1):
            logger.warning(f"{self.bot_id}: WeightGovernor blocked execution (limits reached).")
            return

        # Check if we need to create an epoch
        if not self.active_epoch:
            epoch_id = f"epoch_{self.bot_id}_{int(time.time())}"
            self.db.create_epoch(epoch_id, self.bot_id, "RUNNING")
            self.active_epoch = self.db.get_active_epoch(self.bot_id)
            logger.info(f"{self.bot_id}: Created new epoch {epoch_id}")

        epoch = self.active_epoch
        buy_volume = Decimal(str(self.config["buy_volume"]))

        # Check exit conditions first
        if epoch['num_purchases'] > 0:
            avg_price = Decimal(str(epoch['avg_buy_price']))
            total_cost = Decimal(str(epoch['total_cost']))

            # Current value of accumulated assets
            current_value = (total_cost / avg_price) * self.current_price
            profit_usdt = current_value - total_cost
            profit_pct = (profit_usdt / total_cost) * Decimal("100")

            target_profit = Decimal(str(self.config["target_profit_pct"]))

            logger.info(f"{self.bot_id}: Current PnL: {profit_pct:.2f}% (Target: {target_profit:.2f}%)")

            # 1. Take Profit Check
            if profit_pct >= target_profit:
                # Execute Market Sell to close epoch
                await self._execute_sell(epoch, current_value, profit_usdt, profit_pct)
                return

            # 2. Hard Stop Loss / Drawdown limit
            max_drawdown = Decimal(str(self.config.get("max_drawdown_pct", louise_default_max_drawdown_pct())))
            if max_drawdown < 0 and profit_pct <= max_drawdown:
                logger.error(
                    f"{self.bot_id}: CRITICAL: Stop loss reached "
                    f"({profit_pct:.2f}% <= {max_drawdown:.2f}%). Liquidating position."
                )
                await self._execute_sell(epoch, current_value, profit_usdt, profit_pct, status="CLOSED_STOP_LOSS")
                return

            # 3. Max purchases per epoch limit (preventive position control)
            max_purchases = self.config.get("max_purchases_per_epoch") or louise_default_max_purchases_per_epoch()
            if epoch['num_purchases'] >= max_purchases:
                logger.info(f"{self.bot_id}: Max purchases per epoch ({max_purchases}) reached. Force-selling.")
                await self._execute_sell(epoch, current_value, profit_usdt, profit_pct, status="CLOSED_MAX_PURCHASES")
                return

        # If not exiting, check if we can buy
        if epoch['num_purchases'] > 0:
            avg_price = Decimal(str(epoch['avg_buy_price']))
            if self.current_price >= avg_price:
                logger.debug(f"{self.bot_id}: Price {self.current_price:.4f} is above average {avg_price:.4f}. Skipping buy to strictly average down.")
                return

        # Check max position size (preventive position limit)
        current_exposure = Decimal(str(epoch.get('total_cost', 0.0)))
        max_exposure_raw = self.config.get("max_position_size_usdt") or louise_default_max_position_size_usdt()
        max_exposure = Decimal(str(max_exposure_raw))
        if current_exposure >= max_exposure:
            logger.info(
                f"{self.bot_id}: Max position size reached ({max_exposure} USDT). "
                f"Waiting for target or stop-loss."
            )
            return

        # BudgetGuard is the source of truth for global spend limits (checked first)
        bg = get_budget_guard()
        if not bg.can_spend(buy_volume, self.bot_id):
            logger.warning(f"{self.bot_id}: Global BudgetGuard rejected buy of {buy_volume} USDT. Throttling.")
            return

        # Local sanity check: daily_budget is per-bot limit, BudgetGuard is global truth
        daily_budget = Decimal(str(self.config.get("daily_budget_usdt", 500.0)))
        total_cost_so_far = Decimal(str(epoch.get('total_cost', 0.0)))

        if total_cost_so_far + buy_volume > daily_budget:
            logger.warning(f"{self.bot_id}: Daily budget reached ({daily_budget} USDT). Pausing DCA until target reached.")
            return

        # Check spot balance
        if self.usdt_free_balance < buy_volume:
            logger.warning(f"{self.bot_id}: Insufficient USDT in spot wallet. Need {buy_volume}, have {self.usdt_free_balance}.")
            return

        # Check MIN_NOTIONAL before buy
        filters = get_exchange_filters().get(symbol)
        if filters:
            if buy_volume < filters.min_notional:
                logger.warning(f"{self.bot_id}: buy_volume {buy_volume} is below MIN_NOTIONAL {filters.min_notional}")
                self.cooldown_until = now + louise_cooldown_buy_fail_sec()
                return

        await self._execute_buy(epoch, buy_volume)

    async def _execute_buy(self, epoch: Dict[str, Any], cost_usdt: Decimal):
        symbol = self.config["symbol"]
        alerts = get_alert_dispatcher()

        logger.info(f"{self.bot_id}: Executing MARKET BUY of {cost_usdt} USDT on {symbol}")
        client_oid = f"l_{self.bot_id}_{int(time.time())}"

        try:
            is_simulation = os.environ.get("LOUISE_PAPER_TRADE", "true").lower() == "true"

            if self.gateway and getattr(self.gateway, "_client", None):
                client = self.gateway._client

                # Register intent for WS confirmation
                self.pending_orders[client_oid] = {
                    'type': 'BUY',
                    'epoch_id': epoch['epoch_id'],
                    'epoch': epoch,
                }

                if is_simulation:
                    logger.info(f"{self.bot_id}: [SIMULATION] Paper-trading MARKET BUY of {cost_usdt} USDT")
                    qty = cost_usdt / self.current_price
                    sim_payload = {
                        'e': 'executionReport',
                        'x': 'TRADE',
                        'X': 'FILLED',
                        'c': client_oid,
                        's': symbol,
                        'S': 'BUY',
                        'q': str(qty),
                        'p': str(self.current_price),
                        'Z': str(cost_usdt)
                    }
                    # Delay slightly to mimic network
                    asyncio.create_task(self._delay_sim(sim_payload))
                else:
                    await client.create_order(
                        symbol=symbol,
                        side="BUY",
                        type="MARKET",
                        newClientOrderId=client_oid,
                        quoteOrderQty=str(cost_usdt)
                    )
                self.usdt_free_balance -= cost_usdt
            else:
                logger.error(f"{self.bot_id}: No gateway available to execute BUY")
                alerts.warning(
                    "NO_GATEWAY",
                    f"Bot {self.bot_id}: Gateway not available, cannot execute buy",
                    payload={"bot_id": self.bot_id, "symbol": symbol, "amount_usdt": float(cost_usdt)},
                    silent=True  # Don't spam if gateway is temporarily disconnecting
                )
                self.cooldown_until = int(time.time()) + louise_cooldown_gateway_fail_sec()

        except Exception as e:
            logger.error(f"{self.bot_id}: Failed to execute buy: {e}")
            alerts.warning(
                "BUY_FAILED",
                f"Bot {self.bot_id} failed to execute BUY on {symbol}: {str(e)[:100]}",
                payload={"bot_id": self.bot_id, "symbol": symbol, "amount_usdt": float(cost_usdt), "error": str(e)[:100]},
                silent=False
            )
            self.cooldown_until = int(time.time()) + louise_cooldown_buy_fail_sec()

    async def _execute_sell(self, epoch: Dict[str, Any], final_value: Decimal, profit_usdt: Decimal, profit_pct: Decimal, status: str = "CLOSED_SUCCESSFUL"):
        symbol = self.config["symbol"]
        total_vol = Decimal(str(epoch['total_cost'] / epoch['avg_buy_price']))
        alerts = get_alert_dispatcher()

        filters = get_exchange_filters().get(symbol)
        if filters:
            quantized_vol = filters.quantize_qty(total_vol)
        else:
            quantized_vol = round(total_vol, 5)

        logger.info(f"{self.bot_id}: Target reached! Executing MARKET SELL of {quantized_vol} {symbol}")
        client_oid = f"ls_{self.bot_id}_{int(time.time())}"

        try:
            is_simulation = os.environ.get("LOUISE_PAPER_TRADE", "true").lower() == "true"

            if self.gateway and getattr(self.gateway, "_client", None):
                client = self.gateway._client

                self.pending_orders[client_oid] = {
                    'type': 'SELL',
                    'epoch_id': epoch['epoch_id'],
                    'current_price': self.current_price,
                    'final_value': final_value,
                    'profit_usdt': profit_usdt,
                    'profit_pct': profit_pct,
                    'status': status
                }

                if is_simulation:
                    logger.info(f"{self.bot_id}: [SIMULATION] Paper-trading MARKET SELL of {quantized_vol} {symbol}")
                    sim_payload = {
                        'e': 'executionReport',
                        'x': 'TRADE',
                        'X': 'FILLED',
                        'c': client_oid,
                        's': symbol,
                        'S': 'SELL',
                        'q': str(quantized_vol),
                        'p': str(self.current_price),
                        'Z': str(quantized_vol * self.current_price)
                    }
                    asyncio.create_task(self._delay_sim(sim_payload))
                else:
                    await client.create_order(
                        symbol=symbol,
                        side="SELL",
                        type="MARKET",
                        newClientOrderId=client_oid,
                        quantity=str(quantized_vol)
                    )
            else:
                logger.error(f"{self.bot_id}: No gateway available to execute SELL")
                alerts.critical(
                    "SELL_BLOCKED_NO_GATEWAY",
                    f"CRITICAL: Bot {self.bot_id} reached take-profit but gateway unavailable. Position STUCK with {quantized_vol} {symbol} at {self.current_price}",
                    payload={
                        "bot_id": self.bot_id,
                        "symbol": symbol,
                        "quantity": float(quantized_vol),
                        "current_price": float(self.current_price),
                        "target_pnl_pct": float(profit_pct),
                        "epoch_id": epoch['epoch_id']
                    },
                    silent=False
                )
                self.cooldown_until = int(time.time()) + louise_cooldown_gateway_fail_sec()

        except Exception as e:
            logger.error(f"{self.bot_id}: Failed to execute sell: {e}")
            alerts.critical(
                "SELL_EXECUTION_FAILED",
                f"CRITICAL: Bot {self.bot_id} reached take-profit on {symbol} but SELL execution failed. Position STUCK: {str(e)[:80]}",
                payload={
                    "bot_id": self.bot_id,
                    "symbol": symbol,
                    "quantity": float(quantized_vol),
                    "error": str(e)[:100],
                    "epoch_id": epoch['epoch_id']
                },
                silent=False
            )
            self.cooldown_until = int(time.time()) + louise_cooldown_buy_fail_sec()

    async def _delay_sim(self, payload):
        await asyncio.sleep(1.5)
        await self.handle_order_update(payload)

    async def stop(self, shutdown_db=True):
        """Clean shutdown of the bot."""
        logger.info(f"Shutting down LouiseBot {self.bot_id}")
        self._running = False
        if self._task:
            self._task.cancel()
        if shutdown_db:
            self.db.update_bot_status(self.bot_id, "SHUTDOWN")
            self.config['status'] = "SHUTDOWN"

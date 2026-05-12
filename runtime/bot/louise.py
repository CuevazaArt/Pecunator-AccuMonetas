import logging
import asyncio
import time
from decimal import Decimal
from typing import Optional, Dict, Any

from runtime.core.louise_db import LouiseDB
from runtime.core.event_bus import EventBus
from runtime.core.api_governor import get_api_governor, P_TRADING
from runtime.core.api_fuse import get_api_fuse
from runtime.core.exchange_filters import get_exchange_filters

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
                
                purchase_id = f"pur_{self.bot_id}_{int(time.time())}"
                self.db.add_purchase(
                    purchase_id, self.bot_id, meta['epoch_id'],
                    float(price_at_buy), float(volume), float(cost_usdt), order_id, "FILLED"
                )
                
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
                self.db.close_epoch(meta['epoch_id'], float(meta['current_price']), float(meta['final_value']), float(meta['profit_usdt']), float(meta['profit_pct']))
                self.active_epoch = None
                logger.info(f"{self.bot_id}: Sell WS confirmed. Epoch closed with {meta['profit_pct']:.2f}% profit!")

    async def start(self):
        if not self.config:
            raise RuntimeError("Bot not initialized. Call initialize() first.")
        
        self._running = True
        self.db.update_bot_status(self.bot_id, "RUNNING")
        self.config['status'] = "RUNNING"
        self._task = asyncio.create_task(self._main_loop())
        logger.info(f"Bot {self.bot_id} started loop.")

    async def _main_loop(self):
        """Main loop that runs every poll_interval_seconds."""
        while self._running:
            try:
                await self.poll_market()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in {self.bot_id} main loop: {e}")
            
            # Sleep for the configured interval
            interval = self.config.get('poll_interval_seconds', 300)
            await asyncio.sleep(interval)

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
                
        # Check for stale data (price older than 15s)
        if self.current_price <= Decimal("0") or (now - self.last_price_timestamp > 15):
            logger.debug(f"{self.bot_id}: Waiting for fresh price feed from WebSocket...")
            return
            
        if self.usdt_free_balance < Decimal("8"):
            logger.warning(f"{self.bot_id}: Insufficient global USDT in spot wallet (< 8 USDT). Currently have {self.usdt_free_balance}.")
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
            
            if profit_pct >= target_profit:
                # Execute Market Sell to close epoch
                await self._execute_sell(epoch, current_value, profit_usdt, profit_pct)
                return

        # If not exiting, check if we can buy
        # DCA purely on time interval (every loop) for now, as it's a pure DCA.
        # Check spot balance instead of budget guard
        if self.usdt_free_balance < buy_volume:
            logger.warning(f"{self.bot_id}: Insufficient USDT in spot wallet. Need {buy_volume}, have {self.usdt_free_balance}.")
            return
            
        # Check MIN_NOTIONAL before buy
        filters = get_exchange_filters().get(symbol)
        if filters:
            if buy_volume < filters.min_notional:
                logger.warning(f"{self.bot_id}: buy_volume {buy_volume} is below MIN_NOTIONAL {filters.min_notional}")
                self.cooldown_until = now + 300
                return
                
        await self._execute_buy(epoch, buy_volume)

    async def _execute_buy(self, epoch: Dict[str, Any], cost_usdt: Decimal):
        symbol = self.config["symbol"]
        
        logger.info(f"{self.bot_id}: Executing MARKET BUY of {cost_usdt} USDT on {symbol}")
        client_oid = f"l_{self.bot_id}_{int(time.time())}"
        
        try:
            if self.gateway and getattr(self.gateway, "_client", None):
                client = self.gateway._client
                
                # Register intent for WS confirmation
                self.pending_orders[client_oid] = {
                    'type': 'BUY',
                    'epoch_id': epoch['epoch_id'],
                    'epoch': epoch,
                }
                
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
                self.cooldown_until = int(time.time()) + 60
                
        except Exception as e:
            logger.error(f"{self.bot_id}: Failed to execute buy: {e}")
            self.cooldown_until = int(time.time()) + 300

    async def _execute_sell(self, epoch: Dict[str, Any], final_value: Decimal, profit_usdt: Decimal, profit_pct: Decimal):
        symbol = self.config["symbol"]
        total_vol = Decimal(str(epoch['total_cost'] / epoch['avg_buy_price']))
        
        filters = get_exchange_filters().get(symbol)
        if filters:
            quantized_vol = filters.quantize_qty(total_vol)
        else:
            quantized_vol = round(total_vol, 5)
            
        logger.info(f"{self.bot_id}: Target reached! Executing MARKET SELL of {quantized_vol} {symbol}")
        client_oid = f"ls_{self.bot_id}_{int(time.time())}"
        
        try:
            if self.gateway and getattr(self.gateway, "_client", None):
                client = self.gateway._client
                
                self.pending_orders[client_oid] = {
                    'type': 'SELL',
                    'epoch_id': epoch['epoch_id'],
                    'current_price': self.current_price,
                    'final_value': final_value,
                    'profit_usdt': profit_usdt,
                    'profit_pct': profit_pct
                }
                
                await client.create_order(
                    symbol=symbol,
                    side="SELL",
                    type="MARKET",
                    newClientOrderId=client_oid,
                    quantity=str(quantized_vol)
                )
            else:
                logger.error(f"{self.bot_id}: No gateway available to execute SELL")
                self.cooldown_until = int(time.time()) + 60
            
        except Exception as e:
            logger.error(f"{self.bot_id}: Failed to execute sell: {e}")
            self.cooldown_until = int(time.time()) + 300

    async def stop(self):
        """Clean shutdown of the bot."""
        logger.info(f"Shutting down LouiseBot {self.bot_id}")
        self._running = False
        if self._task:
            self._task.cancel()
        self.db.update_bot_status(self.bot_id, "SHUTDOWN")
        self.config['status'] = "SHUTDOWN"

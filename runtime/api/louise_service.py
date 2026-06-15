"""Louise service for managing bot immortality and lifecycle."""

import asyncio
import logging
from typing import Dict
from runtime.core.louise_db import LouiseDB
from runtime.bot.louise import LouiseBotRunner

from runtime.api import deps
from runtime.api._helpers import resolve_pair_for_bot
from runtime.connectors.binance_gateway import BinanceGateway
from runtime.core.alert_dispatcher import get_alert_dispatcher

logger = logging.getLogger("pecunator.louise_service")

class LouiseService:
    def __init__(self):
        self.db = LouiseDB()
        self.runners: Dict[str, LouiseBotRunner] = {}
        self._immortality_task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._gateways: Dict[str, BinanceGateway] = {}

    async def start_immortality(self, interval_sec: float = 10.0):
        self._stop.clear()
        self._immortality_task = asyncio.create_task(self._immortality_loop(interval_sec))
        logger.info("Louise immortality loop started.")

    async def stop_immortality(self):
        self._stop.set()
        if self._immortality_task:
            self._immortality_task.cancel()
            try:
                await self._immortality_task
            except asyncio.CancelledError:
                pass
            self._immortality_task = None

        for bot_id, runner in list(self.runners.items()):
            try:
                await runner.stop(shutdown_db=False)
            except Exception as e:
                logger.error(f"Failed to stop {bot_id}: {e}")

        for gw in self._gateways.values():
            try:
                await gw.stop()
            except Exception as e:
                logger.error(f"Failed to stop gateway: {e}")

    async def _immortality_loop(self, interval_sec: float):
        while not self._stop.is_set():
            try:
                await self._check_bots()
            except Exception as e:
                logger.error(f"Error in Louise immortality loop: {e}")
            await asyncio.sleep(interval_sec)

    async def _check_bots(self):
        ctx = deps.get_ctx()
        bots = self.db.get_all_bots()
        alerts = get_alert_dispatcher()

        for bot_data in bots:
            bot_id = bot_data["bot_id"]
            status = bot_data["status"]

            if status in ["RUNNING", "ACCUMULATING"]:
                if bot_id not in self.runners:
                    subaccount = bot_data.get("subaccount", "bluechip")
                    pair = resolve_pair_for_bot(ctx, subaccount)
                    if not pair:
                        logger.warning(f"No credentials found for subaccount {subaccount}. Cannot start {bot_id}.")
                        alerts.warning(
                            "NO_CREDENTIALS",
                            f"Bot {bot_id}: No credentials found for subaccount {subaccount}",
                            payload={"bot_id": bot_id, "subaccount": subaccount},
                            silent=False
                        )
                        continue

                    # Gateway per subaccount
                    if subaccount not in self._gateways:
                        try:
                            gw = BinanceGateway(pair[0], pair[1], ctx.bus, ctx.state, ctx.log_line, ctx.config.data_dir)
                            await gw.start()
                            self._gateways[subaccount] = gw
                        except Exception as e:
                            logger.error(f"Failed to start gateway for {subaccount}: {e}")
                            alerts.critical(
                                "GATEWAY_START_FAILED",
                                f"Failed to start Binance gateway for subaccount {subaccount}: {e}",
                                payload={"subaccount": subaccount},
                                silent=False
                            )
                            continue

                    # Hemisphere gate: skip if Louise is disabled
                    louise_on = bool(bot_data.get("louise_enabled", 1))
                    if not louise_on:
                        logger.info(
                            f"Bot {bot_id}: Louise hemisphere disabled — skipping start"
                        )
                        continue

                    runner = LouiseBotRunner(bot_id, self.db, ctx.bus, gw)
                    if runner.initialize():
                        try:
                            await runner.start()
                            self.runners[bot_id] = runner
                        except Exception as e:
                            logger.error(f"Failed to start bot {bot_id}: {e}")
                            alerts.critical(
                                "BOT_START_FAILED",
                                f"Louise bot {bot_id} failed to start: {e}",
                                payload={"bot_id": bot_id},
                                silent=False
                            )
                    else:
                        logger.error(f"Failed to initialize bot {bot_id}")
                        alerts.critical(
                            "BOT_INIT_FAILED",
                            f"Louise bot {bot_id} failed to initialize (check logs)",
                            payload={"bot_id": bot_id},
                            silent=False
                        )

            elif status not in ["RUNNING", "ACCUMULATING"]:
                if bot_id in self.runners:
                    try:
                        await self.runners[bot_id].stop()
                        del self.runners[bot_id]
                    except Exception as e:
                        logger.error(f"Failed to stop bot {bot_id}: {e}")

_service = None
def get_louise_service() -> LouiseService:
    global _service
    if _service is None:
        _service = LouiseService()
    return _service

"""Shared FastAPI dependencies and process-wide `AppContext`."""

from __future__ import annotations

from typing import Optional

from runtime.api.bot_service import BotService
from runtime.api.earn_service import EarnService
from runtime.api.masha_service import MashaService
from runtime.api.thusnelda_service import ThusneldaService
from runtime.app import AppContext, build_context

_ctx: Optional[AppContext] = None
_bot: BotService = BotService()
_masha: MashaService = MashaService()
_thusnelda: ThusneldaService = ThusneldaService()
_earn: EarnService = EarnService()


def init_context() -> AppContext:
    global _ctx
    if _ctx is None:
        _ctx = build_context()
        _bot.attach_data_dir(_ctx.config.data_dir)
        _masha.attach_data_dir(_ctx.config.data_dir)
        _thusnelda.attach_data_dir(_ctx.config.data_dir)
        _earn.attach_data_dir(_ctx.config.data_dir)
    return _ctx


def get_ctx() -> AppContext:
    if _ctx is None:
        raise RuntimeError("AppContext not initialized (lifespan did not run)")
    return _ctx


def peek_ctx() -> Optional[AppContext]:
    return _ctx


def get_bot() -> BotService:
    return _bot


def get_masha() -> MashaService:
    return _masha


def get_thusnelda() -> ThusneldaService:
    return _thusnelda

def get_earn() -> EarnService:
    return _earn

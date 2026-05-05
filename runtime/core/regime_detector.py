"""Regime Detector — Translates VMO classifications into actionable signals.

This module consumes the regime snapshots from the SQLite cache and applies
multi-timeframe consensus rules to produce a final BotRecommendation.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from runtime.modules.vision.config import get_vmo_config
from runtime.modules.vision.regime_cache import RegimeCache

_LOG = logging.getLogger("pecunator.regime_detector")


@dataclass
class BotRecommendation:
    """Actionable recommendation from the Regime Detector."""
    symbol: str
    bot: str                 # "dorothy" | "masha" | "thusnelda" | "none"
    confidence: float        # Consensus confidence
    regime: str              # Consensus regime
    reason: str              # Explanation of the decision


class RegimeDetector:
    """Consumes VMO cache and produces bot activation signals."""

    def __init__(self, cache: Optional[RegimeCache] = None):
        if cache is None:
            cfg = get_vmo_config()
            self._cache = RegimeCache(cfg.db_path)
        else:
            self._cache = cache

    def get_recommendation(self, symbol: str) -> BotRecommendation:
        """Calculate multi-timeframe consensus for a symbol."""
        # Get the latest snapshot for ALL timeframes for this symbol
        # The cache stores them newest first. We need the latest 1 per timeframe.
        # But get_latest() returns all history.
        # We can fetch the latest 5 and group them by timeframe.
        recent = self._cache.get_latest(symbol=symbol, limit=10)
        
        # Keep only the newest snapshot per timeframe
        tf_snapshots = {}
        for r in recent:
            if r.timeframe not in tf_snapshots:
                tf_snapshots[r.timeframe] = r

        if not tf_snapshots:
            return BotRecommendation(
                symbol=symbol, bot="none", confidence=0.0,
                regime="UNKNOWN", reason="No VMO data available for symbol"
            )

        # Filter out low-confidence votes
        valid_votes = [
            r for r in tf_snapshots.values() 
            if r.confidence >= 0.6 and r.recommended_bot != "none"
        ]

        if not valid_votes:
            return BotRecommendation(
                symbol=symbol, bot="none", confidence=0.0,
                regime="CHOPPY", reason="Confidence too low across timeframes"
            )

        # Consensus rule: if 2/3 (or majority) timeframes agree on the bot, use it.
        # If we only have 1 or 2 timeframes, we just need the most common.
        bot_votes = [r.recommended_bot for r in valid_votes]
        winner_bot, count = Counter(bot_votes).most_common(1)[0]

        # Get the regime associated with the winning bot
        winning_regimes = [r.regime for r in valid_votes if r.recommended_bot == winner_bot]
        consensus_regime = Counter(winning_regimes).most_common(1)[0][0]

        # Average confidence of the winning votes
        winning_conf = sum(r.confidence for r in valid_votes if r.recommended_bot == winner_bot) / count

        # If we have multiple timeframes configured, require at least 1 valid vote
        # Actually, let's just trust the majority of valid votes.
        return BotRecommendation(
            symbol=symbol,
            bot=winner_bot,
            confidence=round(winning_conf, 2),
            regime=consensus_regime,
            reason=f"Consensus ({count}/{len(tf_snapshots)} TFs agree)"
        )

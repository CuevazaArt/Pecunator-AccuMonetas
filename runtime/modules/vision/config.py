"""VMO configuration — symbols, timeframes, intervals, and provider settings.

All values can be overridden via environment variables prefixed with ``VMO_``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key, "")
    if not val:
        return default
    return val.lower() in ("1", "true", "yes")


def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key, "")
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _env_float(key: str, default: float) -> float:
    val = os.environ.get(key, "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


@dataclass
class VMOConfig:
    """Central configuration for the Visual Market Observer."""

    # ── Master switch ───────────────────────────────────────────────
    enabled: bool = field(default_factory=lambda: _env_bool("VMO_ENABLED", False))

    # ── Symbols to monitor ─────────────────────────────────────────
    # Must include ALL symbols operated by any bot:
    #   Dorothy:   BTCUSDT, ETHUSDT, SOLUSDT
    #   Masha:     BTCUSDT, ETHUSDT, BNBUSDT
    #   Thusnelda: PEPEUSDT, SUIUSDT, NEARUSDT, INJUSDT, FETUSDT
    symbols: List[str] = field(default_factory=lambda: [
        s.strip() for s in _env(
            "VMO_SYMBOLS",
            "BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT,"
            "PEPEUSDT,SUIUSDT,NEARUSDT,INJUSDT,FETUSDT"
        ).split(",") if s.strip()
    ])

    # ── Timeframes per symbol ───────────────────────────────────────
    timeframes: List[str] = field(default_factory=lambda: [
        t.strip() for t in _env("VMO_TIMEFRAMES", "4h,1d").split(",")
        if t.strip()
    ])

    # ── Schedule ────────────────────────────────────────────────────
    interval_minutes: int = field(
        default_factory=lambda: _env_int("VMO_INTERVAL_MIN", 240)
    )

    # ── Capture source ──────────────────────────────────────────────
    capture_source: str = field(
        default_factory=lambda: _env("VMO_CAPTURE_SOURCE", "auto")
    )  # "chart-img" | "playwright" | "auto"

    chart_img_api_key: str = field(
        default_factory=lambda: _env("CHART_IMG_API_KEY", "")
    )
    chart_img_base_url: str = "https://api.chart-img.com/v1/tradingview/advanced-chart"

    # ── Image Fine-Tuning ──────────────────────────────────────────
    image_width: int = field(default_factory=lambda: _env_int("VMO_IMAGE_WIDTH", 800))
    image_height: int = field(default_factory=lambda: _env_int("VMO_IMAGE_HEIGHT", 600))
    image_theme: str = field(default_factory=lambda: _env("VMO_IMAGE_THEME", "dark")) # "dark" | "light"

    # chart-img rate limiting
    capture_delay_sec: float = field(
        default_factory=lambda: _env_float("VMO_CAPTURE_DELAY", 1.2)
    )
    capture_concurrency: int = field(
        default_factory=lambda: _env_int("VMO_CAPTURE_CONCURRENCY", 1)
    )

    # ── LLM provider ───────────────────────────────────────────────
    llm_provider: str = field(
        default_factory=lambda: _env("VMO_LLM_PROVIDER", "gemini")
    )  # "gemini" | "openai" | "anthropic"

    llm_model: str = field(
        default_factory=lambda: _env("VMO_LLM_MODEL", "gemini-2.5-flash")
    )

    gemini_api_key: str = field(
        default_factory=lambda: _env("GEMINI_API_KEY", "")
    )
    openai_api_key: str = field(
        default_factory=lambda: _env("OPENAI_API_KEY", "")
    )

    # ── Confidence threshold ────────────────────────────────────────
    min_confidence: float = field(
        default_factory=lambda: _env_float("VMO_MIN_CONFIDENCE", 0.6)
    )

    # ── Storage ─────────────────────────────────────────────────────
    png_retention_hours: int = field(
        default_factory=lambda: _env_int("VMO_PNG_RETENTION_HOURS", 48)
    )

    # ── Data directory ──────────────────────────────────────────────
    data_dir: Path = field(
        default_factory=lambda: Path(
            _env("VMO_DATA_DIR", str(
                Path(__file__).resolve().parent.parent.parent / "data"
            ))
        )
    )

    @property
    def captures_dir(self) -> Path:
        return self.data_dir / "vmo_captures"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "vmo_regimes.sqlite"

    @property
    def total_captures_per_cycle(self) -> int:
        return len(self.symbols) * len(self.timeframes)

    @property
    def cycles_per_day(self) -> float:
        if self.interval_minutes <= 0:
            return 0
        return 1440.0 / self.interval_minutes

    @property
    def daily_captures(self) -> float:
        return self.total_captures_per_cycle * self.cycles_per_day

    def summary(self) -> dict:
        return {
            "enabled": self.enabled,
            "symbols": self.symbols,
            "timeframes": self.timeframes,
            "interval_minutes": self.interval_minutes,
            "capture_source": self.capture_source,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "min_confidence": self.min_confidence,
            "image_size": f"{self.image_width}x{self.image_height}",
            "image_theme": self.image_theme,
            "captures_per_cycle": self.total_captures_per_cycle,
            "cycles_per_day": round(self.cycles_per_day, 1),
            "daily_captures": round(self.daily_captures, 0),
            "has_chart_img_key": bool(self.chart_img_api_key),
            "has_gemini_key": bool(self.gemini_api_key),
            "has_openai_key": bool(self.openai_api_key),
            "data_dir": str(self.data_dir),
        }


# Singleton — lazily constructed on first access
_config: VMOConfig | None = None


def get_vmo_config() -> VMOConfig:
    global _config
    if _config is None:
        _config = VMOConfig()
    return _config


def reset_vmo_config() -> None:
    """Reset singleton (useful for tests)."""
    global _config
    _config = None

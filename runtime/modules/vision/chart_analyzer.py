"""Chart analyzer — LLM Vision classification of market regimes.

Takes a PNG screenshot of a TradingView chart and returns a structured
MarketRegime classification using an LLM with vision capabilities.

Supports: Gemini (primary), OpenAI (fallback).
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

_LOG = logging.getLogger("pecunator.vmo.analyzer")

# ── MarketRegime dataclass ──────────────────────────────────────────

@dataclass
class MarketRegime:
    """Structured output from LLM vision analysis of a chart."""
    symbol: str
    timeframe: str               # "1h", "4h", "1d"
    trend: str                   # "UP", "DOWN", "LATERAL"
    trend_strength: str          # "STRONG", "MODERATE", "WEAK"
    volatility: str              # "HIGH", "NORMAL", "LOW", "COMPRESSED"
    regime: str                  # "TRENDING", "RANGING", "CHOPPY", "BREAKOUT"
    confidence: float            # 0.0 - 1.0
    recommended_bot: str         # "dorothy", "masha", "thusnelda", "none"
    risk_level: str              # "LOW", "MODERATE", "HIGH", "EXTREME"
    notes: str                   # Free-form LLM commentary
    captured_at: str = ""        # ISO timestamp of capture
    analyzed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    capture_source: str = ""     # "chart-img" | "playwright"
    llm_provider: str = ""       # "gemini" | "openai"
    llm_model: str = ""
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MarketRegime:
        # Filter to only known fields
        known = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in d.items() if k in known}
        return cls(**filtered)


# Valid values for validation
_VALID_TRENDS = {"UP", "DOWN", "LATERAL"}
_VALID_STRENGTHS = {"STRONG", "MODERATE", "WEAK"}
_VALID_VOLATILITY = {"HIGH", "NORMAL", "LOW", "COMPRESSED"}
_VALID_REGIMES = {"TRENDING", "RANGING", "CHOPPY", "BREAKOUT"}
_VALID_BOTS = {"dorothy", "masha", "thusnelda", "none"}
_VALID_RISKS = {"LOW", "MODERATE", "HIGH", "EXTREME"}


def _validate_regime(regime: MarketRegime) -> MarketRegime:
    """Clamp values to valid sets, enforce confidence bounds."""
    if regime.trend not in _VALID_TRENDS:
        regime.trend = "LATERAL"
    if regime.trend_strength not in _VALID_STRENGTHS:
        regime.trend_strength = "WEAK"
    if regime.volatility not in _VALID_VOLATILITY:
        regime.volatility = "NORMAL"
    if regime.regime not in _VALID_REGIMES:
        regime.regime = "RANGING"
    if regime.recommended_bot not in _VALID_BOTS:
        regime.recommended_bot = "none"
    if regime.risk_level not in _VALID_RISKS:
        regime.risk_level = "MODERATE"
    regime.confidence = max(0.0, min(1.0, regime.confidence))
    # If confidence is low, always recommend "none"
    if regime.confidence < 0.5:
        regime.recommended_bot = "none"
    return regime


# ── LLM Prompt ──────────────────────────────────────────────────────

_SCHEMA_EXAMPLE = """{
    "trend": "UP | DOWN | LATERAL",
    "trend_strength": "STRONG | MODERATE | WEAK",
    "volatility": "HIGH | NORMAL | LOW | COMPRESSED",
    "regime": "TRENDING | RANGING | CHOPPY | BREAKOUT",
    "confidence": 0.75,
    "recommended_bot": "dorothy | masha | thusnelda | none",
    "risk_level": "LOW | MODERATE | HIGH | EXTREME",
    "notes": "Brief 1-2 sentence explanation of what you see"
}"""

_SYSTEM_PROMPT = """You are a market regime classifier for a crypto trading system.
Analyze this TradingView chart image and return a JSON classification.

CRITICAL INSTRUCTIONS:
1. Technical Indicators: The chart contains RSI, MACD, and Bollinger Bands. You MUST use them:
   - RSI (Relative Strength Index): Check for extreme overbought (>70) or oversold (<30) conditions.
   - MACD: Check for momentum crossovers or divergence against price.
   - Bollinger Bands (BB): Check for squeeze/compression (low volatility) or expansion (high volatility).
2. Context: You will be provided with the last known regimes. Use this to determine if the market is shifting.
3. Bot Selection (Strict Mapping):
   - "TRENDING" → "dorothy" (trend-following scalper, rides momentum in BTC/ETH/SOL)
   - "RANGING" → "masha" (DCA range accumulator, buys dips in sideways BTC/ETH/BNB)
   - "BREAKOUT" → "thusnelda" (volatile basket, buys 5 mid-cap altcoins on dip, harvests on sector rally)
   - "CHOPPY" → "none" (erratic, sit out — no bot should operate)
4. If indicators contradict price action or you are unsure, lower confidence (<0.5) and recommend "none".
5. risk_level should reflect technical danger (e.g., trading trending near massive resistance = HIGH).
6. For mid-cap volatile assets (PEPE, SUI, NEAR, INJ, FET), expect wider natural oscillation ranges.

Respond ONLY with valid JSON matching the schema (no markdown, no explanations outside the JSON)."""


def _build_prompt(symbol: str, timeframe: str, history_context: str = "") -> str:
    prompt = (
        f"{_SYSTEM_PROMPT}\n{_SCHEMA_EXAMPLE}\n\n"
        f"Chart: {symbol} on {timeframe} timeframe."
    )
    if history_context:
        prompt += f"\n\nHistorical Context (Previous Regimes):\n{history_context}"
    return prompt


# ── Gemini client ───────────────────────────────────────────────────

async def _classify_gemini(
    png_bytes: bytes,
    symbol: str,
    timeframe: str,
    api_key: str,
    model: str = "gemini-2.0-flash",
    history_context: str = "",
) -> dict[str, Any]:
    """Classify chart using Google Gemini Vision API."""
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError("httpx required: pip install httpx") from e

    b64_image = base64.b64encode(png_bytes).decode("utf-8")
    prompt = _build_prompt(symbol, timeframe, history_context)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": b64_image,
                    }
                },
            ]
        }],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
        },
    }
    headers = {"Content-Type": "application/json"}
    params = {"key": api_key}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers, params=params)
        resp.raise_for_status()
        data = resp.json()

    # Extract text from Gemini response
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini response structure: {e}") from e

    return _parse_json_response(text)


# ── OpenAI client ───────────────────────────────────────────────────

async def _classify_openai(
    png_bytes: bytes,
    symbol: str,
    timeframe: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    history_context: str = "",
) -> dict[str, Any]:
    """Classify chart using OpenAI Vision API."""
    try:
        import httpx
    except ImportError as e:
        raise RuntimeError("httpx required: pip install httpx") from e

    b64_image = base64.b64encode(png_bytes).decode("utf-8")
    prompt = _build_prompt(symbol, timeframe, history_context)

    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64_image}",
                        "detail": "low",
                    },
                },
            ],
        }],
        "max_tokens": 1024,
        "temperature": 0.2,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected OpenAI response structure: {e}") from e

    return _parse_json_response(text)


# ── Response parsing ────────────────────────────────────────────────

def _parse_json_response(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response text (handles markdown fences)."""
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (the fences)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from LLM response: {text[:200]}")


# ── Unified classifier ─────────────────────────────────────────────

async def classify_chart(
    png_bytes: bytes,
    symbol: str,
    timeframe: str,
    *,
    provider: str = "",
    model: str = "",
    gemini_api_key: str = "",
    openai_api_key: str = "",
    captured_at: str = "",
    capture_source: str = "",
    history_context: str = "",
) -> MarketRegime:
    """Classify a chart image into a MarketRegime.

    Tries the configured provider first, falls back to alternatives.
    """
    if not provider or not gemini_api_key or not openai_api_key:
        from runtime.modules.vision.config import get_vmo_config
        cfg = get_vmo_config()
        provider = provider or cfg.llm_provider
        model = model or cfg.llm_model
        gemini_api_key = gemini_api_key or cfg.gemini_api_key
        openai_api_key = openai_api_key or cfg.openai_api_key

    t0 = time.monotonic()
    result_dict: dict[str, Any] = {}
    used_provider = ""
    used_model = ""

    # Try primary provider
    if provider == "gemini" and gemini_api_key:
        try:
            result_dict = await _classify_gemini(
                png_bytes, symbol, timeframe, gemini_api_key,
                model=model or "gemini-2.0-flash",
                history_context=history_context,
            )
            used_provider = "gemini"
            used_model = model or "gemini-2.0-flash"
        except Exception as e:
            _LOG.warning("Gemini classification failed: %s", e)
    elif provider == "openai" and openai_api_key:
        try:
            result_dict = await _classify_openai(
                png_bytes, symbol, timeframe, openai_api_key,
                model=model or "gpt-4o-mini",
                history_context=history_context,
            )
            used_provider = "openai"
            used_model = model or "gpt-4o-mini"
        except Exception as e:
            _LOG.warning("OpenAI classification failed: %s", e)

    # Fallback to the other provider
    if not result_dict and gemini_api_key and used_provider != "gemini":
        try:
            result_dict = await _classify_gemini(
                png_bytes, symbol, timeframe, gemini_api_key,
                history_context=history_context,
            )
            used_provider = "gemini"
            used_model = "gemini-2.0-flash"
        except Exception as e:
            _LOG.warning("Gemini fallback failed: %s", e)

    if not result_dict and openai_api_key and used_provider != "openai":
        try:
            result_dict = await _classify_openai(
                png_bytes, symbol, timeframe, openai_api_key,
                history_context=history_context,
            )
            used_provider = "openai"
            used_model = "gpt-4o-mini"
        except Exception as e:
            _LOG.warning("OpenAI fallback failed: %s", e)

    elapsed = int((time.monotonic() - t0) * 1000)

    if not result_dict:
        _LOG.error("All LLM providers failed for %s/%s", symbol, timeframe)
        return MarketRegime(
            symbol=symbol, timeframe=timeframe,
            trend="LATERAL", trend_strength="WEAK",
            volatility="NORMAL", regime="RANGING",
            confidence=0.0, recommended_bot="none",
            risk_level="HIGH",
            notes="All LLM providers failed — no classification available",
            captured_at=captured_at, capture_source=capture_source,
            llm_provider="none", llm_model="none",
            elapsed_ms=elapsed,
        )

    # Build MarketRegime from LLM response
    regime = MarketRegime(
        symbol=symbol,
        timeframe=timeframe,
        trend=result_dict.get("trend", "LATERAL"),
        trend_strength=result_dict.get("trend_strength", "WEAK"),
        volatility=result_dict.get("volatility", "NORMAL"),
        regime=result_dict.get("regime", "RANGING"),
        confidence=float(result_dict.get("confidence", 0.5)),
        recommended_bot=result_dict.get("recommended_bot", "none"),
        risk_level=result_dict.get("risk_level", "MODERATE"),
        notes=result_dict.get("notes", ""),
        captured_at=captured_at,
        capture_source=capture_source,
        llm_provider=used_provider,
        llm_model=used_model,
        elapsed_ms=elapsed,
    )
    regime = _validate_regime(regime)

    _LOG.info(
        "Classified %s/%s → %s (confidence=%.2f, bot=%s) via %s in %dms",
        symbol, timeframe, regime.regime, regime.confidence,
        regime.recommended_bot, used_provider, elapsed,
    )
    return regime


# ── Batch Classification (multiple images, 1 API call) ──────────────

_BATCH_SYSTEM_PROMPT = """You are a market regime classifier for a crypto trading system.
You will receive MULTIPLE TradingView chart images. Analyze EACH one independently.

For EACH chart, return a JSON object with these fields:
{
    "symbol": "the symbol shown",
    "timeframe": "the timeframe shown",
    "trend": "UP | DOWN | LATERAL",
    "trend_strength": "STRONG | MODERATE | WEAK",
    "volatility": "HIGH | NORMAL | LOW | COMPRESSED",
    "regime": "TRENDING | RANGING | CHOPPY | BREAKOUT",
    "confidence": 0.75,
    "recommended_bot": "dorothy | masha | thusnelda | none",
    "risk_level": "LOW | MODERATE | HIGH | EXTREME",
    "notes": "Brief explanation"
}

Bot Selection Rules:
- "TRENDING" → "dorothy" (trend-following scalper for BTC/ETH/SOL)
- "RANGING" → "masha" (DCA range accumulator for BTC/ETH/BNB)
- "BREAKOUT" → "thusnelda" (volatile basket: PEPE/SUI/NEAR/INJ/FET)
- "CHOPPY" → "none" (sit out, no bot operates)

Technical Indicators: Charts contain RSI, MACD, and Bollinger Bands. USE THEM.
For mid-cap volatile assets (PEPE, SUI, NEAR, INJ, FET), expect wider natural oscillation.

CRITICAL: Return a JSON ARRAY of objects, one per image, in the SAME ORDER as provided.
Example: [{"symbol": "BTCUSDT", ...}, {"symbol": "ETHUSDT", ...}]
Respond ONLY with the JSON array (no markdown, no explanations outside the array)."""


async def classify_charts_batch(
    charts: list[dict[str, Any]],
    *,
    gemini_api_key: str,
    model: str = "gemini-2.0-flash",
    history_context: str = "",
) -> list[MarketRegime]:
    """Classify multiple charts in a single Gemini API call.

    Args:
        charts: List of dicts with keys: "png" (bytes), "symbol", "timeframe"
        gemini_api_key: Gemini API key
        model: Gemini model to use
        history_context: Optional historical regime context

    Returns:
        List of MarketRegime objects, one per input chart.

    This reduces N API calls to 1, saving RPM quota.
    Gemini Flash supports up to ~16 images per request.
    """
    if not charts:
        return []

    try:
        import httpx
    except ImportError as e:
        raise RuntimeError("httpx required: pip install httpx") from e

    t0 = time.monotonic()

    # Build multi-image prompt
    chart_descriptions = []
    parts: list[dict[str, Any]] = []

    prompt_text = _BATCH_SYSTEM_PROMPT
    if history_context:
        prompt_text += f"\n\nHistorical Context:\n{history_context}"

    prompt_text += f"\n\nYou are receiving {len(charts)} chart images:"
    for i, chart in enumerate(charts):
        prompt_text += f"\n  Image {i+1}: {chart['symbol']} on {chart['timeframe']}"
        chart_descriptions.append(f"{chart['symbol']}/{chart['timeframe']}")

    parts.append({"text": prompt_text})

    # Add each image as inline_data
    for chart in charts:
        b64 = base64.b64encode(chart["png"]).decode("utf-8")
        parts.append({
            "inline_data": {
                "mime_type": "image/png",
                "data": b64,
            }
        })

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 4096,
        },
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url, json=payload,
            headers={"Content-Type": "application/json"},
            params={"key": gemini_api_key},
        )
        resp.raise_for_status()
        data = resp.json()

    # Extract text
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"Unexpected Gemini batch response: {e}") from e

    # Parse JSON array
    parsed = _parse_json_response(text)
    elapsed = int((time.monotonic() - t0) * 1000)

    # Handle single object (Gemini might return one object instead of array)
    if isinstance(parsed, dict):
        parsed = [parsed]

    if not isinstance(parsed, list):
        _LOG.error("Batch response is not a list: %s", type(parsed))
        parsed = []

    # Build MarketRegime objects
    results: list[MarketRegime] = []
    now = datetime.now(timezone.utc).isoformat()

    for i, chart in enumerate(charts):
        if i < len(parsed) and isinstance(parsed[i], dict):
            r = parsed[i]
        else:
            r = {}

        regime = MarketRegime(
            symbol=chart["symbol"],
            timeframe=chart["timeframe"],
            trend=r.get("trend", "LATERAL"),
            trend_strength=r.get("trend_strength", "WEAK"),
            volatility=r.get("volatility", "NORMAL"),
            regime=r.get("regime", "RANGING"),
            confidence=float(r.get("confidence", 0.3)),
            recommended_bot=r.get("recommended_bot", "none"),
            risk_level=r.get("risk_level", "MODERATE"),
            notes=r.get("notes", "batch classification"),
            captured_at=now,
            capture_source="batch",
            llm_provider="gemini",
            llm_model=model,
            elapsed_ms=elapsed,
        )
        regime = _validate_regime(regime)
        results.append(regime)

    _LOG.info(
        "Batch classified %d charts in %dms (1 API call): %s",
        len(results), elapsed,
        ", ".join(chart_descriptions),
    )
    return results


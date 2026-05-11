# VMO Evolution & Maximization Plan

> **Status:** Architectural design document
> **Date:** 2026-05-06
> **Objective:** Maximize the use of the "Free Tier" of APIs (chart-img, Gemini) and enhance the intelligence of the Visual Market Observer (VMO).

The current VMO is robust in resilience but suffers from analytical and network inefficiencies. Four critical architectural improvements are proposed:

## 1. Historical Blindness (Lack of State Memory)
**Problem:** Gemini evaluates each image as an isolated event (amnesic). It ignores whether the market is coming from a bullish trend or a prolonged range.
**Improvement to implement:** Modify the `_SYSTEM_PROMPT` to inject the regime from the last 3 cycles (retrieved from `regime_cache.py`), giving it temporal context.

## 2. Request Waste (Lack of Batch Processing)
**Problem:** The orchestrator analyzes 20 charts (10 symbols × 2 timeframes) in isolation, spending 20 LLM API calls, which causes `429 Too Many Requests` errors.
**Improvement to implement:** Send images of the same timeframe (e.g. the 10 4h charts) in a single mega-prompt. This reduces API calls to 1 and allows the LLM to detect **market correlation** (e.g. "Everything is falling because BTC is dragging the market").

## 3. Frequency Inefficiency (Static Timeframes)
**Problem:** Capturing a 1-day chart (`1d`) every 12 hours is redundant (the candle has not closed) and wastes `chart-img` quota.
**Improvement to implement:** Refactor the orchestrator (`observer.py`) to have a dynamic CRON per timeframe:
- `4h` charts are captured every 4 hours.
- `1d` charts are captured every 24 hours (00:00 UTC).

## 4. Prompt Focus (Prompt Engineering)
**Problem:** We have added indicators (RSI, MACD, BB) to the charts, but the LLM has no explicit instructions to read them.
**Improvement to implement:** Update the `_SYSTEM_PROMPT` to instruct the AI to look for overbought/oversold conditions (RSI), momentum crossovers (MACD) and compression (Bollinger Bands) before issuing a verdict.

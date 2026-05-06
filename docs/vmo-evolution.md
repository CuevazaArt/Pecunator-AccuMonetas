# VMO Evolution & Maximization Plan

> **Estado:** Documento de diseño arquitectónico
> **Fecha:** 2026-05-06
> **Objetivo:** Maximizar el uso del "Free Tier" de APIs (chart-img, Gemini) y potenciar la inteligencia del Visual Market Observer (VMO).

El VMO actual es robusto en resiliencia pero adolece de ineficiencias analíticas y de red. Se proponen 4 mejoras arquitectónicas críticas:

## 1. Ceguera Histórica (Falta de Memoria de Estado)
**Problema:** Gemini evalúa cada imagen como un evento aislado (amnésico). Ignora si el mercado viene de una tendencia alcista o de un rango prolongado.
**Mejora a implementar:** Modificar el `_SYSTEM_PROMPT` para inyectar el régimen de los últimos 3 ciclos (recuperados de `regime_cache.py`), otorgándole contexto temporal.

## 2. Desperdicio de Peticiones (Falta de Batch Processing)
**Problema:** El orquestador analiza 20 gráficos (10 símbolos × 2 timeframes) de forma aislada, gastando 20 llamadas a la API del LLM, lo que provoca errores `429 Too Many Requests`.
**Mejora a implementar:** Enviar las imágenes del mismo timeframe (ej. los 10 gráficos de 4h) en un solo mega-prompt. Esto reduce las llamadas a la API a 1 y permite al LLM detectar **correlación de mercado** (ej. "Todo cae porque BTC arrastra el mercado").

## 3. Ineficiencia de Frecuencia (Static Timeframes)
**Problema:** Capturar un gráfico de 1 día (`1d`) cada 12 horas es redundante (la vela no ha cerrado) y desperdicia cuota de `chart-img`.
**Mejora a implementar:** Refactorizar el orquestador (`observer.py`) para tener un CRON dinámico por timeframe:
- Gráficos `4h` se capturan cada 4 horas.
- Gráficos `1d` se capturan cada 24 horas (00:00 UTC).

## 4. Foco del Prompt (Ingeniería de Prompting)
**Problema:** Hemos añadido indicadores (RSI, MACD, BB) a los gráficos, pero el LLM no tiene instrucciones explícitas para leerlos.
**Mejora a implementar:** Actualizar el `_SYSTEM_PROMPT` para instruir a la IA a buscar sobrecompra/sobreventa (RSI), cruces de momentum (MACD) y compresión (Bollinger Bands) antes de emitir un veredicto.

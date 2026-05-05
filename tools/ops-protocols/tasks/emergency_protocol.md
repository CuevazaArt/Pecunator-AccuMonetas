# Task: Protocolo de Emergencia — Modo Defensivo

## ⛔ REGLA ABSOLUTA
Este task NUNCA ejecuta operaciones de trading, retiros, o transferencias
por sí solo. Solo diagnostica, analiza y presenta opciones al operador.
Cualquier acción sobre fondos requiere confirmación explícita del usuario.

## Trigger — Cuándo Ejecutar
- Crash de mercado > 15% en menos de 24h
- Bot reportando errores críticos o comportamiento anómalo
- Health factor de préstamo acercándose a zona de liquidación
- Pérdida de conectividad prolongada con Binance API
- Sospecha de compromiso de seguridad en API keys

## Contexto del Proyecto
- **Ops protocols existentes:**
  - `/api/v1/ops/red_button` — Botón rojo de emergencia (detiene bots)
  - `/api/v1/ops/protocol/close` — Protocolo de cierre ordenado
  - `/api/v1/ops/orders/cleanup/all` — Limpieza de órdenes abiertas
- **Reportes rápidos:** `portfolio_table.py`, `loans_report.py`, `audit_full.py`
- **Infraestructura:** `BotCoordinator`, `WeightGovernor`, `ApiFuse`

## Pasos de Ejecución (en orden estricto)

### Paso 1 — 🛑 FREEZE: Estado de Bots
Verificar estado del BotCoordinator:
- ¿Hay bots activos ejecutando trades?
- ¿Hay órdenes abiertas pendientes?
- Estado del circuit breaker (ApiFuse)

**SI hay bots activos con trades en curso:**
→ Reportar inmediatamente al usuario antes de continuar
→ Presentar opción de activar red_button

### Paso 2 — 📊 ASSESS: Exposición Actual
```bash
python portfolio_table.py
```
Extraer y reportar:
- Valor total del portfolio
- Top 5 posiciones por peso
- Cambio porcentual vs última auditoría (si disponible)
- Exposición total en posiciones apalancadas

### Paso 3 — 💰 ASSESS: Estado de Préstamos
```bash
python loans_report.py
```
Para cada préstamo activo, reportar:
| Préstamo | Colateral | Health Factor | Precio Liq. | Distancia % |
|----------|-----------|---------------|-------------|-------------|
| ...      | ...       | ...           | ...         | ...         |

Clasificar:
- 🔴 **PELIGRO**: HF < 1.3 — liquidación inminente
- ⚠️ **ALERTA**: HF 1.3-1.5 — requiere monitoreo activo
- ✅ **SEGURO**: HF > 1.5 — sin riesgo inmediato

### Paso 4 — 🔍 DIAGNÓSTICO: Causa Raíz
Dependiendo del trigger:

**Si crash de mercado:**
- ¿Qué tokens cayeron más?
- ¿Tenemos exposición directa a esos tokens?
- ¿Nuestro colateral está en riesgo?

**Si error de bot:**
- Revisar logs recientes del bot afectado
- ¿Es error de conectividad, lógica, o rate limit?
- ¿Afecta a otros bots?

**Si sospecha de seguridad:**
- ⛔ NO hacer requests a la API de Binance
- Reportar al usuario para que revoque keys manualmente desde la web

### Paso 5 — 📋 OPCIONES: Presentar al Operador

Generar un menú de acciones posibles, sin ejecutar ninguna:

```
## 🚨 Reporte de Emergencia — [FECHA/HORA]

### Situación
[Resumen de 2-3 líneas del estado actual]

### Riesgo Inmediato
[Nivel: CRITICAL / HIGH / MEDIUM / LOW]
[Justificación]

### Opciones de Acción

#### Opción A — Modo Defensivo (Conservador)
- Activar red_button → Detener todos los bots
- Cancelar todas las órdenes abiertas
- No tocar préstamos (mantener posición)
- Riesgo: Si el mercado sigue cayendo, el colateral puede no ser suficiente

#### Opción B — Reducción de Exposición (Moderado)
- Activar red_button → Detener todos los bots
- Cancelar órdenes abiertas
- Añadir colateral a préstamos en zona ⚠️
- Riesgo: Se usa capital libre para reforzar posiciones

#### Opción C — Liquidación Ordenada (Agresivo)
- Activar red_button → Detener todos los bots
- Cancelar órdenes abiertas
- Cerrar préstamos comenzando por HF más bajo
- Redimir earn positions para cubrir
- Riesgo: Se cristalizan pérdidas pero se elimina riesgo de liquidación

#### Opción D — Mantener y Monitorear
- No hacer nada
- Monitorear HF cada 15 minutos
- Riesgo: Si el mercado empeora, se pierde ventana de acción

### ⏰ Ventana de Tiempo Estimada
[Cuánto tiempo antes de que la situación escale al siguiente nivel]
```

### Paso 6 — ⏳ ESPERAR: Decisión del Operador
Presentar las opciones y ESPERAR instrucción explícita.
No ejecutar ninguna acción sobre fondos sin confirmación.

## Post-Emergencia
Una vez resuelta la situación:
1. Documentar qué pasó, qué se hizo, y el resultado
2. Ejecutar `@task portfolio_audit` para verificar estado final
3. Evaluar si los parámetros de riesgo de los bots necesitan ajuste

## Criterios de Éxito
- [ ] Estado de bots verificado en < 1 minuto
- [ ] Exposición actual documentada con cifras concretas
- [ ] Health factors de todos los préstamos calculados
- [ ] Causa raíz identificada o hipótesis formulada
- [ ] Opciones presentadas al usuario SIN ejecutar ninguna
- [ ] Tiempo total de diagnóstico < 5 minutos

# Marco de Pérdidas y Promoción de Bots

> Filosofía operativa: cuándo una pérdida es justa, cuándo es injusta,
> y cómo un bot pasa de idea a producción con capital real.
> Fecha: 2026-05-05

---

## 1. Definición de Pérdida Justa

> Una pérdida es **justa** cuando es el resultado de seguir un sistema
> con esperanza matemática positiva, dentro de los parámetros definidos,
> en un entorno compatible con la estrategia.
>
> Todo lo demás es ruido, error, o mala arquitectura.

### Pérdidas JUSTAS (aceptables)

- Dentro del drawdown máximo permitido del bot.
- Stop-loss ejecutado correctamente.
- Ocurre en un entorno donde la estrategia estadísticamente pierde
  (Dorothy en tendencia fuerte, Masha en lateral).
- No rompe la esperanza matemática del sistema.
- Es el costo de participar en un sistema incierto.

### Pérdidas INJUSTAS (errores del sistema)

- Sin stop-loss definido.
- Bot operando fuera de su entorno ideal.
- Capital insuficiente para la estrategia.
- Parámetros incorrectos o no validados.
- Operando con loans o apalancamiento no autorizado.
- Operando en sector muerto sin señales macro.
- Operando sin segmentación de subcuentas.
- Error de código o configuración.

### Principio operativo

**El objetivo no es evitar pérdidas. Es evitar pérdidas injustas.**

---

## 2. Límites por Subcuenta

| Subcuenta | Max Drawdown | Stop Loss por Trade | Capital Máximo |
|-----------|-------------|---------------------|----------------|
| SUB-01 (CORE_L1_DCA) | 15% | N/A (DCA, no aplica) | 40% del total |
| SUB-02 (SCALP_RANGE) | 20% | Definido por Dorothy | 25% del total |
| SUB-03 (MULTI_ASSET) | 20% | Por activo individual | 25% del total |
| SUB-04 (SECTOR_BETA) | 25% | Por sector | 15% del total |
| SUB-05 (SANDBOX) | 50% (aceptado) | Libre | 5% del total |

> **Nota:** Estos son **topes máximos**, no asignaciones fijas. La suma
> intencionalmente excede 100% porque MASTER actúa como reserva flotante
> que absorbe la diferencia. En cualquier momento:
> `capital_subcuentas + capital_MASTER = 100%`.

---

## 3. Pipeline de Promoción de Bots

Ningún bot toca capital real sin pasar por las tres etapas:

### Etapa A — Backtest Histórico

| Requisito | Criterio mínimo |
|-----------|----------------|
| Período | ≥ 6 meses de datos |
| Trades | ≥ 100 trades simulados |
| Win rate | > 40% |
| Sharpe | > 0.5 |
| Max drawdown | < umbral de su subcuenta |
| Resultado | Documentado en `docs/bots/{bot}/backtest_report.md` |

### Etapa B — Paper Trading en Vivo

| Requisito | Criterio mínimo |
|-----------|----------------|
| Período | ≥ 2 semanas |
| Ejecución | Bot real contra datos reales, sin capital |
| Validación | Comparar resultados paper vs backtest |
| Desviación aceptable | ≤ 20% de discrepancia |
| Resultado | Log en `runtime/data/{bot}_paper_log.sqlite` |

### Etapa C — Producción con Capital Real

| Requisito | Criterio mínimo |
|-----------|----------------|
| Capital inicial | Mínimo viable (ej. $50-100 USDT) |
| Subcuenta | Asignada y aislada |
| Drawdown guard | Configurado y activo |
| Monitoreo | Primer mes con revisión semanal |
| Escalado | Solo después de 1 mes con PnL positivo |

### Flujo visual

```
IDEA → Backtest (≥6 meses) → Paper Trading (≥2 sem) → Producción (capital mínimo)
                                                              ↓
                                                     1 mes PnL+ → Escalar capital
                                                     3 meses PnL- → Revisión/Apagado
```

---

## 4. Protocolo de Apagado por Pérdida Injusta

Si se detecta una pérdida injusta:

1. **Detener** el bot inmediatamente (vía BotCoordinator o PANIC.lock).
2. **Registrar** el evento en `runtime/data/incident_log.csv`.
3. **Diagnosticar** la causa raíz.
4. **Corregir** el parámetro, código, o configuración.
5. **Regresar** al bot a Etapa B (paper trading) antes de reactivar.

Nunca reactivar un bot después de una pérdida injusta sin corrección.

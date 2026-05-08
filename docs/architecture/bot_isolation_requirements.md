# Bot Isolation & Sub-Account Requirements

> **Status:** Production (Fase 1 — Cuenta Única con Tag Isolation)  
> **Last Updated:** 2026-05-07

---

## 1. Resumen de Convivencia

| Bot | ¿Requiere Subcuenta? | ¿Convive con otros? | Mecanismo de Aislamiento |
|-----|----------------------|---------------------|--------------------------|
| **Dorothy** | ❌ No (Fase 1) | ✅ Sí, con Masha | `clientOrderId` tag: `dorothy-{bot_id}-*` |
| **Masha** | ❌ No (Fase 1) | ✅ Sí, con Dorothy | `clientOrderId` tag: `masha-{bot_id}-*` |
| **Thusnelda** | 🔴 **SÍ OBLIGATORIO** | ❌ **NO** convive con nadie | Lee equity total → contamina si hay otros bots. Harvest vende TODO. |

---

## 2. Dorothy + Masha: Convivencia Segura

Dorothy y Masha pueden operar en la misma cuenta Binance porque:

1. **Etiquetas únicas**: Cada orden lleva un `newClientOrderId` con el formato `{bot_name}-{bot_id}-{action}-{timestamp}`.
2. **Filtro por tag**: Cada bot solo procesa órdenes cuyo `clientOrderId` empiece con su propio tag.
3. **Protección contra órdenes ajenas**: Si Dorothy detecta sell limits ajenas (sin su tag), **no compra** y **no las toca**.
4. **Sin colisión de símbolos**: Dorothy opera símbolos fijos; Masha escanea dinámicamente con shuffle aleatorio.

### ⚠️ Regla Crítica (Incidente 2026-05-07)
> **NUNCA** reiniciar el motor **después** de colocar órdenes manuales.  
> Si el motor tiene código viejo en memoria, puede interpretar las órdenes manuales como propias y liquidarlas.  
> **Secuencia correcta**: Stop engine → Apply code → Restart → THEN place manual orders.

---

## 3. Thusnelda: Aislamiento Estricto

**Thusnelda NO puede convivir con otros bots en la misma cuenta.**

### Razones:
1. **Equity poisoning**: Thusnelda calcula profit basándose en el `equity total` de la cuenta. Si hay otros fondos (Earn, otros bots), el profit target se vuelve inalcanzable.
2. **Harvest nuclear**: Cuando Thusnelda hace `harvest`, vende TODOS los tokens en la cuenta. Esto destruiría posiciones de Dorothy/Masha.
3. **Mutual destruction**: Múltiples Thusneldas en la misma cuenta se destruyen mutuamente en el harvest.

### Regla de Oro:
```
UNA SUBCUENTA = UN BOT THUSNELDA
```

### Implementación:
- Crear subcuenta en Binance: `POST /sapi/v1/sub-account/virtualSubAccount`
- Crear API Key dedicada con permisos: Spot only, NO withdraw, IP restricted
- Transferir capital: `POST /sapi/v1/sub-account/universalTransfer`
- Configurar Thusnelda con esas credenciales exclusivas

---

## 4. Fase 2 — Migración a Subcuentas Completas

| Subcuenta | Bot(s) | Capital Máx | Estado |
|-----------|--------|-------------|--------|
| SUB-DOROTHY | 10x Dorothy | $200 USDT | ⏳ Pendiente |
| SUB-MASHA | 15x Masha | $150 USDT | ⏳ Pendiente |
| SUB-THUSN-01 | 1x Thusnelda | $100 USDT | ⏳ Pendiente |
| MASTER | Earn, Hold, Reserve | Resto | ✅ Activa |

> **Pre-requisito**: Crear subcuentas con API keys independientes en Binance.
> **Ref**: [`thusnelda_subaccount_isolation.md`](thusnelda_subaccount_isolation.md), [`subaccount_ops.md`](../../tools/ops-protocols/tasks/subaccount_ops.md)

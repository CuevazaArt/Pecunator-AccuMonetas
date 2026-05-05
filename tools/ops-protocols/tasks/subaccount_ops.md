# Task: Operaciones de Sub-Cuentas

## Objetivo
Gestionar programáticamente subcuentas de Binance desde la cuenta Master,
incluyendo creación, configuración de permisos, transferencia de fondos,
y reportes consolidados.

## ⛔ Precaución
Todas las operaciones que involucren movimiento de fondos o creación de
cuentas requieren confirmación explícita del usuario antes de ejecutarse.

## Contexto
- **Gateway:** `runtime/connectors/binance_gateway.py`
- **Base URL:** `https://api.binance.com`
- **Autenticación:** HMAC SHA256 signing (implementado en gateway)

## Variante A — Crear Nueva Subcuenta para Bot

### Pasos
1. Llamar `POST /sapi/v1/sub-account/virtualSubAccount`
   - Genera email virtual automáticamente
   - Requiere permiso "Enable Spot & Margin Trading" en API key Master

2. Habilitar capacidades según bot:
   - Dorothy (Spot): Solo Spot habilitado por defecto
   - Masha (Futures): `POST /sapi/v1/sub-account/futures/enable`
   - Thusnelda (Mixed): Futures + Margin enable

3. Crear API Key para la subcuenta:
   - Permisos mínimos necesarios (principio de menor privilegio)
   - **NUNCA** habilitar withdraw en subcuenta de bot

4. Aplicar restricción de IP:
   - `POST /sapi/v1/sub-account/subAccountApi/ipRestriction`
   - Whitelist solo la IP del servidor donde corre el bot

5. Registrar credenciales en `runtime/core/config_manager.py`:
   - Guardar email de subcuenta
   - Guardar API key (encrypted)
   - Asociar con el bot correspondiente

6. Verificar conectividad:
   - `GET /sapi/v1/sub-account/list` → confirmar subcuenta existe
   - Query de balance → confirmar API key funciona

### Output
- Email de subcuenta creada
- API key generada (mostrar solo últimos 4 chars)
- Permisos configurados
- IP restriction aplicada
- Test de conectividad: ✅/🔴

---

## Variante B — Redistribución de Capital

### Pasos
1. Consultar balance de todas las subcuentas:
   - `GET /sapi/v1/sub-account/spot/summary` → Totales spot
   - Por cada subcuenta: `GET /sapi/v1/sub-account/assets` (V4)

2. Consultar rendimiento reciente de cada bot:
   - PnL últimas 24h / 7d si disponible
   - Ratio de utilización de capital (cuánto del balance asignado usa)

3. Calcular distribución óptima:
   ```
   Para cada bot:
     score = (PnL_7d / capital_asignado) * utilizacion
     capital_nuevo = total_disponible * (score / sum_scores)
   ```
   Con floor mínimo por bot y cap máximo de concentración.

4. Generar plan de transferencias:
   | Desde | Hacia | Monto | Token | Motivo |
   |-------|-------|-------|-------|--------|
   | Master | Sub-Masha | 500 USDT | USDT | Rendimiento alto |
   | Sub-Dorothy | Master | 200 USDT | USDT | Rendimiento bajo |

5. **ESPERAR confirmación del usuario**

6. Ejecutar Universal Transfers:
   - `POST /sapi/v1/sub-account/universalTransfer`
   - Tipo: `MAIN_TO_SUB` / `SUB_TO_MAIN` / `SUB_TO_SUB`

7. Verificar balances post-transferencia

### Output
- Tabla de balances pre/post transferencia
- Transfers ejecutados con txnIds
- Verificación de balances correcta

---

## Variante C — Reporte Consolidado

### Pasos
1. Listar todas las subcuentas:
   - `GET /sapi/v1/sub-account/list`

2. Por cada subcuenta, agregar:
   - Balance total en USD equivalent
   - PnL (si hay datos históricos)
   - Posiciones abiertas (Futures)
   - Préstamos activos (Margin)

3. Calcular métricas consolidadas:
   | Métrica | Valor |
   |---------|-------|
   | AUM Total (Master + Subs) | $XXX |
   | Mejor bot (7d) | [nombre] +X% |
   | Peor bot (7d) | [nombre] -X% |
   | Capital idle total | $XXX (X%) |
   | Exposición apalancada total | $XXX |

4. Generar reporte comparativo entre bots

### Output
Artefacto `subaccount_report_YYYY-MM-DD.md` con tablas consolidadas

## Criterios de Éxito
- [ ] Operación completada sin errores de API
- [ ] Confirmación del usuario obtenida antes de mover fondos
- [ ] Balances verificados post-operación
- [ ] Registro en audit log

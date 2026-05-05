# Hardening Arquitectónico — Análisis de Críticas y Resoluciones

> Documento de consulta: evalúa 5 fricciones estructurales identificadas
> en el Manifiesto desde perspectiva de sistemas distribuidos, seguridad
> algorítmica y resiliencia. Cada crítica recibe veredicto: ACEPTADA,
> DIFERIDA, o RECHAZADA, con justificación.
>
> Fecha: 2026-05-05

---

## Índice de Críticas

| # | Tema | Veredicto | Impacto |
|---|------|-----------|---------|
| 1 | Ubicación de DB (Flutter vs Python) | **ACEPTADA** | Alto — inversión cliente-servidor |
| 2 | Estado en memoria (crash-only) | **ACEPTADA** | Crítico — pérdida de estado al reiniciar |
| 3 | Air gap del LLM (Propuesta-Ejecución) | **ACEPTADA** | Alto — superficie de ataque |
| 4 | Kill Switch bloqueable | **ACEPTADA** | Crítico — fallo en emergencia |
| 5 | Aislamiento del Exchange (Gateway) | **DIFERIDA** | Medio — deuda técnica funcional |

---

## 1. Ubicación de la Base de Datos

### Crítica

El Manifiesto asigna a Flutter (Pilar III) la responsabilidad de DB de
respaldo (SQLite) y laboratorio de análisis. Esto invierte la relación
cliente-servidor: si los bots en Python necesitan historial para ajustar
estrategias, tendrían que pedírselo a la interfaz gráfica. Si Flutter se
cierra, el sistema pierde capacidad de persistir snapshots.

### Veredicto: ACEPTADA

**Resolución:**
- Mover la propiedad de SQLite al **Python Runtime** (`runtime/data/`).
- Python es dueño absoluto de persistencia, ingesta y almacenamiento.
- Flutter queda como **capa de presentación pura (View)** que consume
  datos del backend vía REST/WebSocket.
- Si Flutter se cae, el backend sigue registrando, analizando y operando.

**Cambio en Manifiesto:**
- Pilar III redefinido: "Dashboard Stateless + Laboratorio Visual".
- La DB SQLite operativa vive en `runtime/data/`, no en `desktop_shell/`.
- Flutter puede tener cache local para UX, pero NO es fuente de persistencia.

### Impacto en código existente

Los `MODULE.md` de cada bot ya referencian `runtime/data/*.sqlite`.
La migración es conceptual (doctrina), no de código: el runtime ya
almacena ahí. Lo que cambia es que Flutter deja de ser respaldo — solo lee.

---

## 2. Estado en Memoria (Crash-Only Philosophy)

### Crítica

`StateStore` vive en memoria. Si Python crashea, el estado del bot
(progreso de órdenes, métricas temporales, niveles de grid) se pierde.
Reconstruir desde Binance es propenso a errores catastróficos.

### Veredicto: ACEPTADA

**Resolución:**
- Implementar **State Hydration** con SQLite en modo WAL (Write-Ahead Logging).
- Cada transición de estado importante de un bot se escribe inmediatamente
  a disco (`runtime/data/bot_state_wal.sqlite`).
- Al arrancar, `BotCoordinator` lee estado persistido y rehidrata bots
  antes de consultar Binance.

**Diseño técnico:**

```
StateStore (memoria)
    │
    ├── on_transition(bot_id, old_state, new_state)
    │   └── WAL writer → bot_state_wal.sqlite
    │
    └── on_boot()
        └── WAL reader → rehidrata estado → valida contra Binance
```

**Regla de persistencia:**
- SIEMPRE persistir: cambio de estado de bot, órdenes creadas/cerradas,
  transiciones de capital.
- NUNCA persistir: ticks de mercado, datos efímeros, métricas de UI.

**Prioridad:** Alta — implementar antes de poner bots en producción
con capital real.

---

## 3. Air Gap del LLM (Propuesta-Ejecución)

### Crítica

"El LLM solo invoca scripts" es intención, no garantía. Si el LLM puede
generar código Python y ejecutarlo, un prompt injection o alucinación
podría producir un script que extraiga fondos y luego lo ejecute.

### Veredicto: ACEPTADA

**Resolución: Principio de Separación de Propuesta y Ejecución**

1. El LLM puede **escribir y proponer** código.
2. El entorno del LLM (IDE) **NO tiene permisos** para ejecutar código
   que toque vault o API en producción sin confirmación del operador.
3. Las acciones autónomas del LLM se restringen a **Tools tipadas,
   determinísticas y de solo lectura**.
4. Toda ejecución con efecto financiero requiere un **Task determinístico
   validado previamente en Git**.

**Matriz de permisos del LLM:**

| Acción | Permiso | Confirmación |
|--------|---------|-------------|
| Leer código/docs | ✅ Libre | No |
| Generar código | ✅ Libre | No |
| Ejecutar tests | ✅ Libre | No |
| Leer datos de API (solo lectura) | ✅ Via Tool | No |
| Ejecutar script con efecto en Binance | ⚠️ Via Task | **Sí — operador** |
| Acceder a vault/secrets | ❌ Prohibido | N/A |
| Ejecutar código arbitrario en producción | ❌ Prohibido | N/A |

**Cambio en Manifiesto:** Sección 4.2 expandida con esta regla.

---

## 4. Kill Switch Bloqueable

### Crítica

`/api/v1/ops/red_button` asume que FastAPI está vivo y el event loop no
está bloqueado. Si un bot entra en bucle infinito o hay deadlock, la
petición REST de pánico nunca se procesa.

### Veredicto: ACEPTADA

**Resolución: Kill Switch Out-of-Band (OOB)**

Además de la ruta API, el sistema debe reaccionar a señales externas:

1. **Archivo centinela:** Si `runtime/data/PANIC.lock` existe al inicio
   de cualquier ciclo de bot, el bot se detiene inmediatamente.
2. **Señal de OS:** En Linux/macOS, `SIGUSR1` invoca rutina de pánico.
   En Windows, un named pipe o archivo centinela.
3. **Watchdog de proceso:** Si el event loop no responde en 60s,
   un proceso supervisor mata los bots a nivel de OS (`taskkill`/`kill`).

**Flujo de emergencia:**

```
Operador detecta problema
    │
    ├── Opción A: API → POST /api/v1/ops/red_button
    │   (funciona si FastAPI está vivo)
    │
    ├── Opción B: Crear archivo PANIC.lock
    │   (funciona si el proceso lee filesystem)
    │
    └── Opción C: taskkill /F /PID del proceso Python
        (funciona SIEMPRE — nivel de OS)
```

**Cambio en Manifiesto:** Sección 6.2 expandida con OOB kill switch.

---

## 5. Aislamiento del Exchange (Gateway Abstracto)

### Crítica

Los bots llaman directamente a la API de Binance. Si Binance cambia un
endpoint, el código del bot se rompe. Además, sin abstracción no se
puede hacer backtesting con MockExchange.

### Veredicto: DIFERIDA (con preparación)

**Justificación:**
- El `BinanceGateway` ya existe como conector centralizado.
- Los bots no llaman a Binance directamente — pasan por el gateway.
- Crear un `IExchange` abstracto ahora añade complejidad sin usuario
  inmediato (no hay segundo exchange ni backtester aún).
- **Pero** se reconoce el valor: cuando llegue `ccxt` o backtesting,
  la interfaz será necesaria.

**Preparación ahora:**
- Documentar el contrato actual del gateway (métodos públicos, firmas).
- Cuando se implemente un segundo exchange o MockExchange, extraer
  la interfaz `IExchange` del gateway existente.
- No construir la abstracción vacía — construirla cuando haya un
  segundo implementador.

**En el roadmap:** Se mantiene en "Fase Siguiente — Diversificación CEX".

---

## Resumen de acciones

| Crítica | Acción | Cuándo |
|---------|--------|--------|
| DB en Flutter | Redefinir Pilar III como View pura | **Ahora** (doctrina) |
| Estado en memoria | Implementar WAL State Hydration | **Pre-producción** |
| LLM air gap | Definir matriz Propuesta-Ejecución | **Ahora** (doctrina) |
| Kill Switch OOB | Implementar PANIC.lock + watchdog | **Pre-producción** |
| Gateway abstracto | Documentar contrato, diferir interfaz | **Con segundo exchange** |

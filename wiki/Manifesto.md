# Manifiesto Arquitectónico — Pecunator

> Documento vivo que define la filosofía, arquitectura y directrices operativas del proyecto.  
> Toda decisión técnica es trazable a los principios aquí establecidos.  
> Última actualización: 2026-05-04

---

## 1. Visión del Proyecto

Pecunator es un **hub de operaciones financieras algorítmicas** diseñado para un operador individual. Su objetivo es componer beneficio a través de ciclos repetidos de trading, yield farming y gestión de portfolio, con control total sobre la lógica de decisión y la trazabilidad de cada operación.

No es un exchange. No es un fondo. Es una **estación de trabajo financiera personal** que combina automatización, análisis y supervisión humana.

### Principios Fundacionales

| # | Principio | Descripción |
|---|-----------|-------------|
| 1 | **Componer beneficio** | El objetivo es crecimiento compuesto, no apuestas únicas |
| 2 | **Contener pérdidas** | Las pérdidas no se prohíben; se contienen, auditan y aprenden con controles estrictos |
| 3 | **Soberanía operativa** | El operador mantiene control total sobre fondos, estrategias y datos |
| 4 | **Trazabilidad total** | Cada operación, decisión y cambio queda registrado y es auditable |

---

## 2. El Modelo de 4 Pilares

### Pilar I — Binance CEX (Ejecución y Custodia)

**Rol:** Proveedor central de ejecución de órdenes, custodia de activos, datos de mercado en tiempo real e historiales de trading.

**Binance es infraestructura, no producto.** Pecunator consume la API de Binance como servicio.

**Qué le delegamos:**
- Ejecución de órdenes (Spot, Futures, Margin)
- Custodia de fondos (wallets)
- Datos de mercado (tickers, orderbook, trades vía WebSocket)
- Productos financieros (Earn, Loans, Staking)
- Gestión de subcuentas
- Historiales de trades y transacciones

**Qué NO le delegamos:**
- Decisiones de trading
- Análisis de portfolio
- Persistencia de largo plazo
- Políticas operativas

### Pilar II — GitHub Repository (Conocimiento y Doctrina)

**Rol:** Sistema de gestión de conocimiento versionado, código fuente, políticas operativas y memoria institucional.

**El repo no es solo código; es la mente del proyecto.**

Contiene:
- Código fuente (runtime, bots, tools, scripts, desktop shell)
- Documentación arquitectónica (`docs/`)
- Políticas de seguridad (`docs/policies/`)
- Directrices de contexto para el LLM (`docs/context/`)
- Tasks operativos (`tools/ops-protocols/tasks/`)
- Changelog y decisiones históricas

**Convención de ramas:**
- `main` — rama estable, siempre deployable
- Ramas de feature/fix por PR

### Pilar III — Flutter Desktop Shell (Visualización, DB, Simulaciones)

**Rol:** Dashboard visual consolidado, base de datos local de respaldo y plataforma para simulaciones y análisis estadístico.

**Triple función:**

| Función | Descripción |
|---------|-------------|
| **Hub de bots** | Visualización simultánea de N bots con estado, P&L y métricas |
| **DB de respaldo** | SQLite local con snapshots de balances, trades, equity y estados |
| **Laboratorio de análisis** | Backtests e hipótesis sin consumir rate limits de Binance |

**Boundaries críticos:**
- Credenciales **NUNCA** en Dart — siempre en el vault Python
- Flutter habla **solo** con el runtime vía HTTP localhost
- La UI **no es** fuente de verdad para balances ni posiciones

### Pilar IV — IDE + LLM (Cerebro Operativo)

**Rol:** Capa cognitiva para análisis, orquestación de tareas complejas, generación de reportes y ejecución de protocolos operativos.

**El LLM propone, el código dispone.**

**Qué hace el LLM:**
- Analizar reportes y cruzar datos de múltiples fuentes
- Ejecutar Tasks operativos (briefings, auditorías, health checks)
- Generar código y scripts según directrices del repo
- Detectar patrones y proponer acciones
- Formalizar conocimiento en documentos `.md`

**Qué NO hace el LLM:**
- Ejecutar trades sin aprobación explícita
- Acceder directamente a private keys o secrets
- Tomar decisiones finales sobre fondos
- Reemplazar lógica determinística de bots

**Limitaciones conocidas:** no-determinístico, amnesia entre sesiones, latencia 5–30 s. Mitigación: Tasks codifican protocolos reproducibles; directrices en `docs/context/` proveen contexto persistente.

---

## 3. Jerarquía de Decisión

| Nivel | Agente | Responsabilidad | Horizonte |
|-------|--------|----------------|-----------|
| 1 | **Operador humano** | Estrategia, qué hacer, cuándo escalar | Días/Semanas |
| 2 | **LLM (IDE)** | Análisis, briefings, propuestas de acción | Minutos/Horas |
| 3 | **Scripts Python** | Ejecución determinística aprobada | Segundos |
| 4 | **Bots autónomos** | Operación continua con parámetros fijos | Ciclo continuo |
| 5 | **Binance API** | Ejecución de órdenes, custodia | Milisegundos |
| 6 | **Flutter Shell** | Visualización, persistencia local | Tiempo real |

Cada nivel solo interactúa con los adyacentes.

---

## 4. Política de Seguridad y Credenciales

### Almacenamiento de Secretos

- **API keys de Binance:** Vault cifrado en `runtime/data/` (AES via `cryptography`). Nunca en texto plano, nunca en variables de entorno sin cifrar en producción.
- **Private keys Web3** (futuro): `.env` local con `chmod 600` + vault cifrado. Nunca en el repo.
- **Tokens de GitHub:** Credential manager del sistema operativo.

### Principio de Menor Privilegio

- API keys de bots: solo permisos de trading, **NUNCA withdraw**
- Subcuentas: cada bot opera con su propia key restringida por IP
- El LLM solo invoca scripts; los scripts leen secrets del vault

### Rotación y Revocación

- API keys se rotan **cada 90 días** como mínimo
- Si hay sospecha de compromiso: **revocar INMEDIATAMENTE** desde Binance antes de cualquier diagnóstico técnico

### Sanitización de Logs

- Toda salida de log pasa por `security_util.sanitize_log_message()`
- Patrones de signature, API keys y secrets se redactan automáticamente

---

## 5. Política de Datos y Persistencia

### Fuentes de Verdad

| Dato | Fuente de verdad | Respaldo |
|------|------------------|----------|
| Balances actuales | Binance API (User Data Stream) | Flutter SQLite |
| Órdenes abiertas | Binance API (User Data Stream) | Flutter SQLite |
| Historial de trades | Binance API (`/myTrades`) | CSV logs locales |
| Tasas de earn/loan | Binance API + monitors | CSV logs en repo |
| Estado de bots | Runtime StateStore (memoria) | Flutter SQLite |
| Métricas de equity | Runtime EquityRollingWindow | Flutter SQLite |
| Políticas y doctrina | GitHub repo (`docs/`) | — (el repo ES la verdad) |
| Configuración de bots | `runtime/core/config_manager.py` | Vault cifrado |

### Formatos

| Tipo | Formato |
|------|---------|
| Reportes humanos | `.txt` o `.md` |
| Datos tabulares | `.csv` (parseables con pandas) |
| Datos estructurados | `.json` o SQLite |
| Políticas y documentación | `.md` (versionado en git) |

---

## 6. Filosofía de Trading

### Horizonte Temporal

Pecunator **NO** es un sistema de HFT ni scalping. Enfoque:

- **Gestión de portfolio** — horizonte de horas a días
- **Yield optimization** — horizonte de días a semanas
- **Arbitraje** — solo si la ventana es cómoda (segundos a minutos)
- **Auditoría y rebalanceo** — bajo demanda o periódico

### Gestión de Riesgo

| Control | Detalle |
|---------|---------|
| **Concentración máxima** | Ningún token individual debe superar el 25% del portfolio sin justificación documentada |
| **Health factor mínimo** | Préstamos con HF < 1.5 activan alerta; HF < 1.3 activa protocolo de emergencia |
| **Kill switch** | Botón rojo (`/api/v1/ops/red_button`) detiene todos los bots inmediatamente |
| **Circuit breaker** | `ApiFuse` corta el acceso REST automáticamente si el peso de API supera umbrales |

### Tratamiento de Pérdidas

Las pérdidas son eventos inevitables, no fallos del sistema:

1. **Contención** — Limitar la pérdida vía stop-loss o cierre manual
2. **Registro** — Documentar qué pasó, cuándo y por qué
3. **Análisis** — ¿Error de estrategia, ejecución o mercado?
4. **Adaptación** — Ajustar parámetros o estrategia si corresponde
5. **Continuación** — Seguir operando con controles actualizados

---

## 7. Roadmap de Expansión

### Fase Actual — Estabilización CEX

- [x] Runtime modular con BotCoordinator y WeightGovernor
- [x] Flutter desktop shell con dashboard de bots
- [x] Vault cifrado para credenciales
- [x] Monitors de earn/loan rates
- [x] Audit system y reportes
- [x] Tasks operativos en IDE
- [ ] DB SQLite en Flutter para persistencia local
- [ ] Subcuentas de Binance para aislamiento de bots

### Fase Siguiente — Diversificación CEX

- [ ] Segundo CEX vía `ccxt` (candidatos: Bybit, OKX)
- [ ] Abstracción de Gateway para multi-exchange
- [ ] Comparador de tasas cross-exchange

### Fase Futura — Web3 Multichain

- [ ] `web3_gateway.py` — conector on-chain para EVM
- [ ] DEX quotes vía agregadores (1inch, 0x)
- [ ] Spread detector CEX vs DEX
- [ ] Lending on-chain (Aave V3)

---

## 8. Glosario

| Término | Definición en contexto de Pecunator |
|---------|-------------------------------------|
| **Hub** | El runtime central que orquesta bots, APIs y estado |
| **Gateway** | Conector a un exchange o blockchain específico |
| **Task** | Protocolo operativo ejecutable por el LLM |
| **Fuse** | Circuit breaker que corta acceso ante exceso de uso |
| **Governor** | Regulador de peso/rate limit de API |
| **Coordinator** | Orquestador del ciclo de vida de bots |
| **Shell** | El frontend Flutter desktop |
| **Vault** | Almacenamiento cifrado de credenciales |
| **Doctrina** | Políticas y principios que rigen la operación |

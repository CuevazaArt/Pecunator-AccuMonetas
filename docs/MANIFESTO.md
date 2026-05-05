# Pecunator — Manifiesto Arquitectónico

> Documento vivo que define la filosofía, arquitectura, y directrices operativas del proyecto.
> Toda decisión técnica debe ser trazable a los principios aquí establecidos.
> Última actualización: 2026-05-04

---

## 1. Visión del Proyecto

Pecunator es un **hub de operaciones financieras algorítmicas** diseñado para
un operador individual. Su objetivo es componer beneficio a través de ciclos
repetidos de trading, yield farming, y gestión de portfolio, con control total
sobre la lógica de decisión y la trazabilidad de cada operación.

No es un exchange. No es un fondo. Es una **estación de trabajo financiera
personal** que combina automatización, análisis, y supervisión humana.

### Principios Fundacionales

1. **Componer beneficio** — El objetivo es crecimiento compuesto, no apuestas únicas.
2. **Contener pérdidas** — Las pérdidas no se prohíben; se contienen, se auditan,
   y se aprende de ellas con controles estrictos.
3. **Soberanía operativa** — El operador mantiene control total sobre sus fondos,
   sus estrategias, y sus datos. Ningún tercero puede bloquear la operación sin
   consecuencias conocidas y mitigadas.
4. **Trazabilidad total** — Cada operación, cada decisión, cada cambio de política
   queda registrado y es auditable.

---

## 2. El Modelo de 4 Pilares

La arquitectura de Pecunator se sostiene sobre cuatro pilares independientes,
cada uno con una responsabilidad clara y sin solapamiento.

### Pilar I — Binance CEX (Ejecución y Custodia)

**Rol:** Proveedor central de ejecución de órdenes, custodia de activos,
datos de mercado en tiempo real, y repositorio de historiales de trading.

**Principio:** Binance es infraestructura, no producto. Pecunator consume
la API de Binance como un servicio; no depende de su interfaz web ni de
sus herramientas analíticas.

**Qué le delegamos:**
- Ejecución de órdenes (Spot, Futures, Margin)
- Custodia de fondos (wallets de la cuenta)
- Datos de mercado (tickers, orderbook, trades vía WebSocket)
- Productos financieros (Earn, Loans, Staking)
- Gestión de subcuentas (creación, permisos, transferencias)
- Historiales de trades y transacciones

**Qué NO le delegamos:**
- Decisiones de trading (eso es nuestro)
- Análisis de portfolio (eso lo hacemos nosotros)
- Persistencia de largo plazo (eso es GitHub + Flutter DB)
- Políticas operativas (eso vive en el repo)

**Riesgo de contraparte:** Aceptado conscientemente. Binance es el exchange
más líquido y mejor documentado. Diversificar a otros CEXes y a Web3
es parte del roadmap, pero no se ejecuta hasta que el ecosistema y el capital
lo justifiquen. Mientras tanto, los snapshots locales (audit reports, CSV logs,
SQLite) actúan como seguro ante pérdida de acceso.

### Pilar II — GitHub Repository (Conocimiento y Doctrina)

**Rol:** Sistema de gestión de conocimiento versionado, código fuente,
políticas operativas, y memoria institucional del proyecto.

**Principio:** Todo lo que define "cómo opera Pecunator" vive en el repo.
El repo no es solo código; es la mente del proyecto.

**Qué guarda:**
- Código fuente (runtime, bots, tools, scripts, desktop shell)
- Documentación arquitectónica (`docs/`)
- Políticas de seguridad y credenciales (`docs/policies/`)
- Directrices de contexto para el LLM (`docs/context/`)
- Tasks operativos (`tools/ops-protocols/tasks/`)
- Filosofía y principios de diseño (este documento)
- Changelog y decisiones históricas (`docs/CHANGELOG.md`)

**Ventaja clave:** Git provee auditoría gratuita. Cada cambio de política
tiene un diff, un autor, una fecha, y un mensaje de commit. Ninguna base
de datos ofrece esta trazabilidad con esta simplicidad.

**Convención de ramas:**
- `main` — rama estable, siempre deployable
- Ramas de feature/fix según necesidad, merge vía PR o fast-forward

### Pilar III — Flutter Desktop Shell (Visualización, DB, Simulaciones)

**Rol:** Dashboard visual consolidado, base de datos local de respaldo,
y plataforma para simulaciones y análisis estadístico.

**Principio:** Flutter es el concentrador visual y el repositorio de datos
operativos. No toma decisiones; presenta información y persiste datos
para análisis offline.

**Triple función:**

**A) Hub de bots:** Visualización del estado de N bots simultáneamente,
cada uno con su subcuenta, estrategia, P&L, y métricas. Control de misión
estilo Bloomberg terminal para el operador.

**B) DB de respaldo:** SQLite local donde se persisten snapshots de balances,
trades, métricas de equity, y estados de bots. Esta DB NO es la fuente de
verdad (eso es Binance); es una réplica de trabajo y un seguro.

**C) Laboratorio de análisis:** Con datos históricos locales se pueden
ejecutar backtests, análisis estadísticos, estudiar correlaciones, y probar
hipótesis sin consumir rate limits de la API de Binance.

**Boundaries:**
- Credenciales NUNCA en Dart. Siempre en el vault de Python.
- El Flutter shell habla SOLO con el runtime vía HTTP localhost.
- El UI no es fuente de verdad para balances ni posiciones.

### Pilar IV — IDE + LLM (Cerebro Operativo)

**Rol:** Capa cognitiva para análisis, orquestación de tareas complejas,
generación de reportes, y ejecución de protocolos operativos.

**Principio:** El LLM propone, el código dispone. El LLM analiza y sugiere;
la ejecución final pasa por scripts determinísticos aprobados por el operador.

**Qué hace el LLM:**
- Analizar reportes y cruzar datos de múltiples fuentes
- Ejecutar Tasks operativos (briefings, auditorías, health checks)
- Generar código y scripts según directrices del repo
- Detectar patrones y proponer acciones
- Formalizar conocimiento en documentos `.md`

**Qué NO hace el LLM:**
- Ejecutar trades sin aprobación explícita del operador
- Acceder directamente a private keys o secrets
- Tomar decisiones finales sobre fondos
- Reemplazar lógica determinística de bots

**Limitaciones conocidas:**
- **No-determinístico:** Dos consultas iguales pueden dar respuestas diferentes
- **Amnesia:** Cada conversación nueva pierde contexto previo
- **Latencia:** 5-30 segundos por respuesta (inadecuado para HFT)
- **Mitigaciones:** Tasks codifican protocolos reproducibles;
  directrices en `docs/context/` proveen contexto persistente

---

## 3. Jerarquía de Decisión

Los niveles de decisión van de lo más humano a lo más automatizado:

| Nivel | Agente | Responsabilidad | Horizonte |
|-------|--------|----------------|-----------|
| 1 | **Operador humano** | Estrategia, qué hacer, cuándo escalar | Días/Semanas |
| 2 | **LLM (IDE)** | Análisis, briefings, propuestas de acción | Minutos/Horas |
| 3 | **Scripts Python** | Ejecución determinística aprobada | Segundos |
| 4 | **Bots autónomos** | Operación continua con parámetros fijos | Ciclo continuo |
| 5 | **Binance API** | Ejecución de órdenes, custodia | Milisegundos |
| 6 | **Flutter Shell** | Visualización, persistencia local | Tiempo real |

Cada nivel solo interactúa con los adyacentes. El LLM nunca toca Binance
directamente — siempre pasa por scripts. Los bots nunca toman decisiones
estratégicas — solo ejecutan reglas parametrizadas.

---

## 4. Política de Seguridad y Credenciales

### 4.1 Almacenamiento de Secretos

- **API keys de Binance:** Vault cifrado en `runtime/data/` (AES via `cryptography`).
  Nunca en texto plano, nunca en variables de entorno sin cifrar en producción.
- **Private keys Web3** (futuro): `.env` local con `chmod 600` + vault cifrado.
  Nunca en el repo. Nunca en contexto del LLM.
- **Tokens de GitHub:** Credenciales de sistema operativo (credential manager).
  Nunca hardcodeados.

### 4.2 Principio de Menor Privilegio

- API keys de bots: solo permisos de trading, NUNCA withdraw.
- Subcuentas: cada bot opera con su propia key restringida por IP.
- El LLM solo invoca scripts; los scripts leen secrets del vault.

### 4.3 Rotación y Revocación

- API keys se rotan cada 90 días como mínimo.
- Si hay sospecha de compromiso: revocar INMEDIATAMENTE desde la web de
  Binance, ANTES de cualquier diagnóstico técnico.
- Mantener documentadas las keys activas y su fecha de creación
  (sin incluir los valores, solo identificadores).

### 4.4 Sanitización de Logs

- Toda salida de log pasa por `security_util.sanitize_log_message()`.
- Patrones de signature, API keys, y secrets se redactan automáticamente.
- Los logs nunca se publican sin revisión.

---

## 5. Política de Datos y Persistencia

### 5.1 Fuentes de Verdad

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

### 5.2 Retención

- **CSV logs** (earn_rates, loan_rates): retención indefinida en repo.
  Son ligeros y la historia es valiosa.
- **Audit reports** (.txt): retención indefinida. Snapshots de estado.
- **SQLite Flutter**: retención local, no versionado en git.
  Incluir en backups periódicos del sistema.
- **Binance historiales**: depende de las políticas de retención de Binance.
  Se mitiga con snapshots locales periódicos.

### 5.3 Formatos

- Reportes humanos: `.txt` o `.md`
- Datos tabulares: `.csv` (parseables con pandas)
- Datos estructurados: `.json` o SQLite
- Políticas y documentación: `.md` (versionado en git)

---

## 6. Filosofía de Trading

### 6.1 Horizonte Temporal

Pecunator NO es un sistema de HFT ni de scalping. El enfoque es:

- **Gestión de portfolio** — horizonte de horas a días
- **Yield optimization** — horizonte de días a semanas
- **Arbitraje** — solo si la ventana es cómoda (segundos a minutos)
- **Auditoría y rebalanceo** — bajo demanda o periódico

Si en el futuro se exploran HFT o scalping, será con fines experimentales
y pedagógicos, en subcuentas aisladas con capital limitado.

### 6.2 Gestión de Riesgo

- **Concentración máxima:** Ningún token individual debe superar el 25%
  del portfolio sin justificación documentada.
- **Health factor mínimo:** Préstamos con HF < 1.5 activan alerta;
  HF < 1.3 activa protocolo de emergencia.
- **Kill switch:** El botón rojo (`/api/v1/ops/red_button`) detiene
  todos los bots inmediatamente. Disponible en Flutter y vía API.
- **Circuit breaker:** `ApiFuse` corta el acceso REST automáticamente
  si el peso de API supera umbrales de seguridad.

### 6.3 Tratamiento de Pérdidas

Las pérdidas son eventos inevitables, no fallos del sistema. Se tratan así:
1. **Contención** — Limitar la pérdida vía stop-loss o cierre manual
2. **Registro** — Documentar qué pasó, cuándo, y por qué
3. **Análisis** — ¿Fue error de estrategia, de ejecución, o de mercado?
4. **Adaptación** — Ajustar parámetros o estrategia si corresponde
5. **Continuación** — Seguir operando con los controles actualizados

---

## 7. Directrices de Contexto para el LLM

### 7.1 Idioma

- Coordinación humana y documentación: **Español**
- Código, identificadores, commits, y nombres de archivos: **Inglés**
- Logs del sistema: **Inglés** (para parseo y búsqueda consistente)

### 7.2 Convenciones de Código

- Python: type hints en funciones públicas, docstrings en clases
- Anti-NaN guards en toda operación con `Decimal`
- `sanitize_log_message()` en toda salida de log
- No bare `except:` — siempre especificar tipo de excepción
- Imports agrupados: stdlib → third party → local

### 7.3 Cómo el LLM Debe Operar

Al inicio de cada conversación, el LLM debería:
1. Revisar este manifiesto para alinear contexto
2. Consultar `docs/architecture-next.md` para estado técnico actual
3. Consultar `tools/ops-protocols/tasks/` para protocolos disponibles
4. Consultar `docs/repo-modules-map.md` para ubicación de componentes

El LLM NO debe:
- Implementar sin discutir primero (salvo tareas triviales)
- Asumir acceso a secrets o private keys
- Ejecutar trades sin confirmación explícita
- Cambiar políticas sin documentar el cambio

---

## 8. Roadmap de Expansión

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
- [ ] Cross-chain bridges
- [ ] MEV protection (Flashbots)

**Regla:** Web3 entra como conector secundario que alimenta al mismo hub,
no como sistema paralelo. Binance sigue siendo el centro de gravedad
hasta que el capital y la estabilidad justifiquen distribución.

---

## 9. Estructura de Documentación

```
docs/
├── MANIFESTO.md                    ← Este documento (filosofía + arquitectura)
├── architecture-next.md            ← Estado técnico actual del runtime
├── repo-modules-map.md             ← Mapa de módulos y ubicaciones
├── binance-api-and-compliance.md   ← Límites y compliance de Binance
├── CHANGELOG.md                    ← Historial de cambios del proyecto
├── GITHUB_WORKFLOW.md              ← Flujo de trabajo con GitHub
├── rest-weight-audit.md            ← Auditoría de peso REST
├── bots/                           ← Documentación por bot
└── binance-limits-snapshots/       ← Snapshots de rate limits
```

---

## 10. Glosario

| Término | Definición en contexto de Pecunator |
|---------|-------------------------------------|
| **Hub** | El runtime central que orquesta bots, APIs, y estado |
| **Gateway** | Conector a un exchange o blockchain específico |
| **Task** | Protocolo operativo ejecutable por el LLM |
| **Fuse** | Circuit breaker que corta acceso ante exceso de uso |
| **Governor** | Regulador de peso/rate limit de API |
| **Coordinator** | Orquestador del ciclo de vida de bots |
| **Shell** | El frontend Flutter desktop |
| **Vault** | Almacenamiento cifrado de credenciales |
| **Doctrina** | Políticas y principios que rigen la operación |

# Pecunator — Manifiesto Arquitectónico

> Documento vivo que define la filosofía, arquitectura, y directrices operativas del proyecto.
> Toda decisión técnica debe ser trazable a los principios aquí establecidos.
> Última actualización: 2026-05-05

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
- Persistencia de largo plazo (eso es GitHub + Runtime SQLite)
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

### Pilar III — Flutter Desktop Shell (Visualización Stateless)

**Rol:** Dashboard visual consolidado y capa de presentación pura.

**Principio:** Flutter es una **View stateless** que consume datos del
backend Python vía REST/WebSocket. Si Flutter se cae, el sistema de
registro, análisis y operación en background NO se inmuta.

**Doble función:**

**A) Hub de bots:** Visualización del estado de N bots simultáneamente,
cada uno con su subcuenta, estrategia, P&L, y métricas. Control de misión
estilo Bloomberg terminal para el operador.

**B) Laboratorio visual:** Con datos servidos por el backend se pueden
visualizar backtests, análisis estadísticos, correlaciones e hipótesis.

**La DB operativa (SQLite/WAL) vive en el Python Runtime** (`runtime/data/`).
Flutter puede mantener cache local para UX, pero NO es fuente de
persistencia ni respaldo. El backend es el dueño absoluto de la
persistencia, ingesta y almacenamiento.

**Boundaries:**
- Credenciales NUNCA en Dart. Siempre en el vault de Python.
- El Flutter shell habla SOLO con el runtime vía HTTP localhost.
- El UI no es fuente de verdad para balances, posiciones ni estado.
- Si Flutter se cierra, el backend sigue operando sin pérdida de datos.

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
| 6 | **Flutter Shell** | Visualización (stateless) | Tiempo real |

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
- El LLM opera bajo el principio de **Propuesta-Ejecución**:
  - El LLM puede escribir y proponer código.
  - El LLM NO tiene permisos de ejecución sobre el runtime de producción
    sin la invocación de un Task determinístico validado en Git.
  - Las acciones autónomas del LLM se restringen a Tools tipadas,
    determinísticas y de solo lectura.
  - Toda ejecución con efecto financiero requiere confirmación del operador.

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
| Balances actuales | Binance API (User Data Stream) | Runtime SQLite WAL |
| Órdenes abiertas | Binance API (User Data Stream) | Runtime SQLite WAL |
| Historial de trades | Binance API (`/myTrades`) | CSV logs locales |
| Tasas de earn/loan | Binance API + monitors | CSV logs en repo |
| Estado de bots | Runtime StateStore (SQLite WAL) | — (crash-safe) |
| Métricas de equity | Runtime EquityRollingWindow | Runtime SQLite WAL |
| Políticas y doctrina | GitHub repo (`docs/`) | — (el repo ES la verdad) |
| Configuración de bots | `runtime/core/config_manager.py` | Vault cifrado |

### 5.2 Retención

- **CSV logs** (earn_rates, loan_rates): retención indefinida en repo.
  Son ligeros y la historia es valiosa.
- **Audit reports** (.txt): retención indefinida. Snapshots de estado.
- **SQLite Runtime** (`runtime/data/`): retención local, no versionado en git.
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
- **Kill switch (in-band):** El botón rojo (`/api/v1/ops/red_button`)
  detiene todos los bots. Disponible en Flutter y vía API.
- **Kill switch (out-of-band):** Si `runtime/data/PANIC.lock` existe,
  los bots se detienen al inicio del siguiente ciclo sin depender de
  FastAPI. Funciona ante event loop bloqueado o deadlock.
- **Kill switch (OS-level):** `taskkill /F` del proceso Python como
  último recurso. Funciona siempre.
- **Circuit breaker:** `ApiFuse` corta el acceso REST automáticamente
  si el peso de API supera umbrales de seguridad.

### 6.3 Tratamiento de Pérdidas

Las pérdidas son eventos inevitables, no fallos del sistema.

**Pérdida justa:** resultado de seguir un sistema con esperanza matemática
positiva, dentro de parámetros definidos, en entorno compatible con la
estrategia. Aceptable. Se registra y se continúa.

**Pérdida injusta:** resultado de operar sin stop-loss, fuera del entorno
ideal, con parámetros incorrectos, o por error de código. Inaceptable.
Requiere corrección antes de reactivar el bot.

Protocolo ante cualquier pérdida:
1. **Contención** — Limitar la pérdida vía stop-loss o cierre manual
2. **Clasificación** — ¿Justa o injusta?
3. **Registro** — Documentar qué pasó, cuándo, y por qué
4. **Análisis** — ¿Error de estrategia, ejecución, o mercado?
5. **Adaptación** — Ajustar parámetros o estrategia si corresponde
6. **Continuación** — Seguir operando (si justa) o regresar a paper
   trading (si injusta) con los controles actualizados

Referencia completa: [`docs/loss-framework.md`](loss-framework.md)

### 6.4 Promoción de Bots a Producción

Ningún bot toca capital real sin pasar por tres etapas:

1. **Backtest histórico** — ≥6 meses de datos, ≥100 trades, documentado
2. **Paper trading en vivo** — ≥2 semanas, comparado contra backtest
3. **Producción con capital mínimo** — Subcuenta aislada, drawdown guard
   activo, revisión semanal el primer mes

Escalado de capital solo después de ≥1 mes con PnL positivo.
Referencia completa: [`docs/loss-framework.md`](loss-framework.md)

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

> Resumen de fases. Detalle completo con prerrequisitos y criterios de
> promoción en [`docs/evolution-plan.md`](evolution-plan.md).

### Fase 0 (Actual) — Hardening Doctrinal

- [x] Runtime modular con BotCoordinator y WeightGovernor
- [x] Flutter desktop shell como View stateless
- [x] Vault cifrado para credenciales
- [x] Monitors de earn/loan rates
- [x] Audit system y reportes
- [x] Tasks operativos en IDE
- [x] Pilar III redefinido: DB en Python, Flutter stateless
- [x] Principio Propuesta-Ejecución del LLM
- [x] Marco de pérdidas justas/injustas
- [x] Kill Switch OOB documentado

### Fase 1 — Bots en Producción

- [ ] WAL State Hydration en `runtime/core/state_store.py`
- [ ] PANIC.lock watchdog implementado
- [ ] Lógica de estrategia ejecutable para Dorothy, Masha, Thusnelda
- [ ] Pipeline de promoción: backtest → paper → producción
- [ ] Primer mes de P&L registrado

### Fase 2 — Subcuentas y Aislamiento

- [ ] Subcuentas de Binance (SUB-01 a SUB-05) con API keys aisladas
- [ ] Métricas por subcuenta activas
- [ ] Primera rotación de capital mensual ejecutada
- [ ] Ref: [`docs/subcuentas-architecture.md`](subcuentas-architecture.md)

### Fase 3 — Sensores y Heurísticas (VMO + Rotación Sectorial)

> **Prerrequisito:** Bots operando con parámetros fijos y P&L medible.

- [ ] `runtime/modules/vision/` — Captura, análisis, cache, observer
- [ ] Integración con `BotCoordinator` para activación/desactivación
      heurística de bots por régimen de mercado
- [ ] Sector Strength Scanner y rotación sectorial automatizada
- [ ] Validación: ¿VMO mejora P&L vs parámetros fijos?

**Concepto:** Sensor heurístico cualitativo que clasifica régimen de
mercado vía imágenes de gráficos + LLM Vision, sin consumir API weight.
Complementa datos OHLC numéricos; nunca los sustituye.

### Fase 4 — Multi-CEX (Diversificación)

- [ ] Interfaz `IExchange` extraída del `BinanceGateway` actual
- [ ] Segundo CEX vía `ccxt` (candidatos: Bybit, OKX)
- [ ] MockExchange para backtesting inyectable
- [ ] Comparador de tasas cross-exchange

### Fase 5 — Web3 Multichain (Reservado)

- [ ] Wallet Engine, DEX Execution, On-chain Metrics
- [ ] Multichain Router, DeFi Strategies
- [ ] Seguridad extrema: llaves privadas, wallets frías/calientes

**Regla:** Web3 entra como conector secundario que alimenta al mismo hub,
no como sistema paralelo. Binance sigue siendo el centro de gravedad
hasta que el capital y la estabilidad justifiquen distribución.

---

## 9. Estructura de Documentación

```
docs/
├── MANIFESTO.md                    ← Este documento (filosofía + arquitectura)
├── evolution-plan.md               ← Plan evolutivo por fases con prerrequisitos
├── architecture-next.md            ← Estado técnico actual del runtime
├── hardening-critique.md           ← Análisis de fricciones y resoluciones
├── subcuentas-architecture.md      ← Subcuentas, permisos, rotación de capital
├── loss-framework.md               ← Marco de pérdidas y promoción de bots
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
| **VMO** | Visual Market Observer — sensor heurístico que clasifica régimen de mercado vía imágenes + LLM Vision, sin consumir API weight |
| **WAL** | Write-Ahead Logging — modo de SQLite que persiste estado de bots de forma crash-safe |
| **Pérdida justa** | Pérdida dentro de parámetros definidos, en entorno compatible con la estrategia |
| **Pérdida injusta** | Pérdida por error de sistema, configuración, o violación de reglas operativas |
| **OOB Kill Switch** | Mecanismo de parada de emergencia fuera del canal HTTP (archivo centinela, señal de OS) |
| **Propuesta-Ejecución** | Principio de seguridad: el LLM propone, el operador confirma, el código determinístico ejecuta |

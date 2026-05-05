# Task: Health Check de Infraestructura Bot

## Objetivo
Verificar la integridad estructural y funcional del runtime de Pecunator,
incluyendo los 3 bots (Dorothy, Masha, Thusnelda), los sistemas de
coordinación (BotCoordinator, WeightGovernor), y la capa de API.

## Contexto del Proyecto
```
runtime/
├── core/
│   ├── bot_coordinator.py    # Orquestador central de bots
│   ├── weight_governor.py    # Control de peso de API requests
│   ├── api_fuse.py           # Circuit breaker para API calls
│   ├── market_cache.py       # Cache de datos de mercado
│   ├── rest_usage_log.py     # Logging de uso de API REST
│   ├── config_manager.py     # Gestión de configuración
│   ├── settings.py           # Settings centrales
│   ├── event_bus.py          # Bus de eventos inter-módulo
│   └── state_store.py        # Persistencia de estado
├── api/
│   ├── app.py                # FastAPI principal (~100KB, monolito)
│   ├── routers/              # Routers desacoplados
│   │   ├── system.py
│   │   ├── masha.py
│   │   └── thusnelda.py
│   ├── schemas.py            # Pydantic schemas
│   └── deps.py               # Dependency injection
├── connectors/
│   └── binance_gateway.py    # Gateway a Binance API
├── modules/
│   ├── bots/                 # Lógica de cada bot
│   │   ├── dorothy.py
│   │   ├── masha.py
│   │   └── thusnelda.py
│   └── tools/                # Herramientas auxiliares
│       ├── ops/
│       ├── rest_weight/
│       └── sandbox/
└── tests/                    # Test suite
```

## Pasos de Ejecución

### Paso 1 — Validación Sintáctica
Verificar que todos los archivos Python del runtime parsean sin errores:
```bash
python -m py_compile runtime/core/bot_coordinator.py
python -m py_compile runtime/core/weight_governor.py
python -m py_compile runtime/core/api_fuse.py
python -m py_compile runtime/connectors/binance_gateway.py
python -m py_compile runtime/api/app.py
```
Reportar cualquier SyntaxError inmediatamente.

### Paso 2 — Validación de Imports
Verificar que los imports cruzados entre módulos resuelven correctamente:
```bash
python -c "from runtime.core.bot_coordinator import BotCoordinator"
python -c "from runtime.core.weight_governor import WeightGovernor"
python -c "from runtime.connectors.binance_gateway import BinanceGateway"
```

### Paso 3 — Test Suite
Ejecutar los tests existentes:
```bash
python -m pytest runtime/tests/ -v --tb=short
```
Capturar: total tests, passed, failed, errors, warnings.

### Paso 4 — Inspección de Circuit Breakers
Revisar `runtime/core/api_fuse.py`:
- ¿Hay circuit breakers en estado OPEN (activados por fallo)?
- ¿Cuántos fallos consecutivos registra?
- ¿Cuándo fue el último reset?

### Paso 5 — Inspección de Rate Limits
Revisar `runtime/core/rest_usage_log.py` y `weight_governor.py`:
- ¿Peso acumulado actual vs límite permitido?
- ¿Porcentaje de uso del rate limit?
- ¿Alguna ventana temporal cercana al límite?

### Paso 6 — Integridad de Routers
Verificar que los routers FastAPI están correctamente registrados:
- `routers/system.py` → rutas de sistema
- `routers/masha.py` → rutas de bot Masha
- `routers/thusnelda.py` → rutas de bot Thusnelda

### Paso 7 — Generar Tabla de Estado

```
| Componente            | Estado | Detalle                        |
|-----------------------|--------|--------------------------------|
| bot_coordinator.py    | ✅/⚠️/🔴 | [descripción]               |
| weight_governor.py    | ✅/⚠️/🔴 | [descripción]               |
| api_fuse.py           | ✅/⚠️/🔴 | [circuit breaker status]    |
| binance_gateway.py    | ✅/⚠️/🔴 | [descripción]               |
| FastAPI app + routers | ✅/⚠️/🔴 | [rutas cargadas]            |
| Test suite            | ✅/⚠️/🔴 | [X/Y passed]                |
| Rate limits           | ✅/⚠️/🔴 | [X% usado]                  |
```

## Criterios de Estado
- ✅ **OK**: Componente funcional, sin warnings
- ⚠️ **WARN**: Funcional pero con warnings o degradación detectada
- 🔴 **FAIL**: Error de compilación, test fallido, o circuit breaker abierto

## Criterios de Éxito
- [ ] Todos los archivos core compilan sin SyntaxError
- [ ] Imports cruzados resuelven correctamente
- [ ] Test suite ejecutada (reportar pass rate)
- [ ] Estado de circuit breakers documentado
- [ ] Tabla de estado completa generada

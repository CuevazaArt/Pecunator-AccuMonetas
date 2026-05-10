# Arquitectura V4: Transición de Polling REST a Push Reactivo (WebSockets / SSE)

## 1. Declaración del Problema

La implementación actual en la versión 3.3.x de la interfaz gráfica en Flutter depende de un antipatrón arquitectónico: **Polling Agresivo basado en Temporizadores (`Timer.periodic`)**. 

Se identificaron al menos 10 temporizadores asíncronos en el frontend disparando peticiones `GET` repetitivas a la API REST local (`/api/v1/gateway/snapshot`, `/api/v1/hub/bots`, `/api-fuse/status`, etc.) a frecuencias que van desde los 3 hasta los 60 segundos.

### Debilidades Críticas
*   **Contención de I/O y CPU**: FastAPI se satura respondiendo solicitudes donde el estado no ha cambiado, consumiendo recursos locales y arriesgando topes de descriptores de archivo (sockets) en Windows.
*   **Desincronización de UI (Tearing)**: Debido a que cada widget tiene su propio temporizador, un panel puede mostrar 15 USDT de balance, mientras que la gráfica muestra 14.8 USDT hasta que su timer interno se cumpla.
*   **Latencia Perceptible**: Eventos de negocio críticos (trip de fusibles, detecciones de orphans, ejecuciones de órdenes) pueden tardar hasta 15 segundos en reflejarse en la UI.
*   **Ineficiencia Térmica**: Obliga al UI thread de Flutter a redibujar el árbol entero constantemente sin importar si los datos reales variaron o no.

## 2. Nueva Arquitectura Propuesta (Modelo Push Reactivo)

Para resolver esto de forma radical y preparar Pecunator para escalar hacia la Malla Ethos y monitoreos de mayor frecuencia, proponemos migrar la propagación del payload a una topología **Push a través de WebSockets (o Server-Sent Events)**, orquestada por el Gestor de Estado (`Riverpod` en Flutter).

### 2.1 Backend (Python / FastAPI)
*   **Event Bus Interno**: Reemplazar los logs directos de eventos (`jsonl`) con un `EventBus` en memoria (basado en `asyncio.Queue` o similares).
*   **WebSocket Broadcaster**: Crear un endpoint persistente `ws://127.0.0.1:8000/ws/telemetry`.
*   **Payload Unificado (JSON-RPC style)**: Todo evento emitido debe seguir una firma estandarizada:
    ```json
    {
      "type": "TELEMETRY_TICK",  // o "FUSE_TRIPPED", "ORPHAN_DETECTED"
      "ts_utc": "2026-05-10T16:40:00Z",
      "payload": { ... }
    }
    ```
*   **El `TelemetryCollector`**: Dejará de ser algo que solo escribe en DB. Cada vez que genere el snapshot (ahora puede ser cada 2 segundos sin costo de I/O), lo transmitirá por el EventBus al WebSocket Broadcaster.

### 2.2 Frontend (Flutter)
*   **Central Socket Service**: Un único `TelemetrySocketProvider` que mantiene y auto-reconecta el socket con el backend.
*   **State Notifier Global**: Recibe el payload del socket y actualiza el árbol inmutable de Riverpod (`HubState`, `MetricsState`).
*   **Eliminación Total de Timers**: 
    - En lugar de `Timer.periodic`, los Widgets usarán `ref.watch(telemetryProvider)`.
    - La UI se redibujará **solo cuando el servidor envíe nueva data real**, reduciendo a cero el polling inútil.

## 3. Plan de Migración (Payload Upgrade Path)

**Fase 1: Backend Broadcaster**
- Implementar el router de websockets en FastAPI (`runtime/api/routers/stream.py`).
- Extender `AlertDispatcher` para que también publique mensajes en el stream de WebSockets para notificar instantáneamente el disparo de un Fusible API/Orden.
- Integrar `TelemetryCollector` para que publique el snapshot consolidado al WS tras cada iteración.

**Fase 2: Cliente Flutter & Riverpod**
- Integrar `web_socket_channel` en `pubspec.yaml`.
- Crear el `TelemetryStreamProvider`.
- Depurar todos los `.dart` eliminando explícitamente cualquier uso de `Timer.periodic` vinculado a APIs.

**Fase 3: Optimización Final**
- Implementar payloads delta (solo enviar lo que cambió) si el tamaño excede el límite razonable de transmisión local.
- Configurar reconexión exponencial pasiva en el socket service de Dart.

## 4. Conclusión y Registro
Este cambio estructural reducirá el peso de la red local en un >95%, garantizará la inmediatez de la observabilidad, y sentará las bases definitivas para una interfaz de usuario verdaderamente profesional y lista para operación multi-bot en tiempo real.

# Manual de Operaciones: Cluster de Bots Louise en Binance

Este manual proporciona instrucciones detalladas y recomendaciones operacionales para diseñar, desplegar y mantener un **Cluster de Bots Louise** utilizando Pecunator-AccuMonetas.

---

## 1. Arquitectura de Louise: Mono-símbolo vs Multi-símbolo

A nivel de ejecución, cada bot individual de Louise (`LouiseBotRunner`) es estrictamente **mono-símbolo**. Esto significa que una instancia de bot gestiona las órdenes de compra (DCA), las alertas y la toma de ganancias para un único par de trading (por ejemplo, `BTCUSDT`).

Para operar múltiples monedas, Pecunator orquesta un **cluster de bots**. 
* **Mono-símbolo (Un solo bot):** Se crea un único bot en el sistema enfocado en acumular un activo.
* **Multi-símbolo (Cluster de bots):** Se inician múltiples instancias de bots individuales en paralelo. Esto se puede realizar de forma masiva a través de la CLI pasando una lista de símbolos separados por comas.

---

## 2. Recomendaciones de Aislamiento y Subcuentas

### Aislamiento de Inventario (Regla de Oro)
> [!IMPORTANT]
> **Nunca** debes ejecutar dos bots de Louise para el **mismo símbolo** compartiendo la misma subcuenta de Binance.
> Si lo haces, las compras se mezclarán en la billetera Spot. Cuando un bot decida vender para tomar ganancias, venderá todo el balance acumulado en la cuenta Spot, liquidando prematuramente las compras del otro bot e interfiriendo con su lógica.

### Convivencia en la misma Subcuenta
Varios bots de Louise pueden compartir una misma subcuenta (como la subcuenta predeterminada `bluechip`) **únicamente si operan símbolos diferentes** (ej. Bot 1 en `BTCUSDT`, Bot 2 en `ETHUSDT`, Bot 3 en `SOLUSDT`).
* **Ventaja:** Menos configuración de API Keys.
* **Desventaja:** Compiten por el saldo libre de USDT. Si el saldo de USDT se agota por caídas en un par, los otros bots no tendrán USDT libre para ejecutar sus recompras de DCA.

### Estructura de Subcuentas Recomendada
Para clusters profesionales, se recomienda dividir tus bots en grupos lógicos utilizando las subcuentas de Binance (habilitadas a través del menú de subcuentas en tu cuenta VIP/Corporativa de Binance, o simuladas a través del `SubAccountRegistry` de Pecunator):
1. **Subcuenta `bluechip`:** Dedicada a activos de alta capitalización y acumulación estable (`BTC`, `ETH`).
2. **Subcuenta `altcoins`:** Dedicada a monedas con mayor volatilidad y menor presupuesto de recompra (`SOL`, `ADA`, `XRP`).
3. **Subcuenta `experimental`:** Para pruebas con configuraciones agresivas de take-profit.

---

## 3. Configuración de Variables de Entorno (.env)

El archivo `.env` en la raíz de tu proyecto Pecunator debe contener la configuración de API keys y canales de Telegram:

```env
# Configuración del Motor
PECUNATOR_LOG_LEVEL=INFO
LOUISE_PAPER_TRADE=false # Pon en 'false' para operar en producción real en Binance

# Notificaciones y Alertas por Telegram
PECUNATOR_ALERT_TELEGRAM_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ  # Token de tu bot de Telegram
PECUNATOR_ALERT_TELEGRAM_CHAT_ID=987654321                         # ID de tu chat o grupo
LOUISE_TELEGRAM_NOTIFY_INTERVAL_HOURS=12                           # Reporte periódico cada 12 horas (0 para desactivar)

# Variables de Ajuste Generales
LOUISE_MIN_USDT_BALANCE=10.0                                       # Balance mínimo en USDT para permitir compras
LOUISE_PRICE_STALENESS_SEC=15                                      # Segundos máximos de precio antiguo aceptable
```

---

## 4. Gestión del Presupuesto Diario y USDT Libre

El cluster de Louise cuenta con protección contra caídas y sobre-exposición mediante el **BudgetGuard**:
- **Límite Global de Hub:** Louise tiene reservado el 40% del límite de gasto diario general de Pecunator.
- **Límite del Bot:** Configura adecuadamente el parámetro `--budget` al crear un bot. Este representa el máximo que un bot individual puede gastar en compras en un intervalo de 24 horas.
- **USDT Libre en Spot:** Asegúrate de mantener suficiente USDT libre en la subcuenta correspondiente. Si tienes 4 bots activos con compras configuradas de 10 USDT por orden, en un movimiento brusco del mercado a la baja podrías necesitar al menos 40 USDT de forma simultánea.

### Reserva Atómica (v4.2+)
> [!NOTE]
> A partir de v4.2, el BudgetGuard utiliza una reserva atómica (`try_reserve()`) con `BEGIN IMMEDIATE` en SQLite. Esto elimina la condición de carrera (TOCTOU) donde dos bots podían aprobar la misma cuota simultáneamente y exceder el presupuesto diario. Cada bot ahora bloquea exclusivamente la DB durante la verificación + registro del gasto.

---

## 5. Filosofía de Acumulación: Sin Stop-Loss por Diseño

> [!IMPORTANT]
> Louise **no tiene stop-loss ni límites artificiales de compra por epoch**. Esto es intencional y central a la estrategia.

### ¿Por qué no hay stop-loss?
- Louise opera **sin apalancamiento** en activos **bluechip** (BTC, ETH, BNB, SOL).
- El riesgo de que un activo bluechip caiga a cero de forma permanente es extremadamente bajo.
- Vender en pérdida (ej. -90%) **consolida una pérdida real** que, históricamente, se habría recuperado al mantener la posición.
- La estrategia DCA está diseñada para promediar el precio de entrada hacia abajo durante caídas — cuanto más baja el precio, mejor es el precio promedio de acumulación.

### ¿Por qué no hay límites de compras o posición?
- Los límites artificiales (`max_purchases_per_epoch`, `max_position_size_usdt`) **entorpecen la lógica de acumulación**.
- Louise debe ser libre de seguir comprando mientras haya presupuesto diario y USDT disponible.
- El único control de gasto es el **BudgetGuard** (presupuesto diario) y el **saldo libre de USDT en la subcuenta**.

### Control de riesgo real
El operador controla su exposición mediante:
1. **Presupuesto diario (`--budget`):** Limita cuánto gasta cada bot por día.
2. **Volumen de compra (`--buy-volume`):** Define el tamaño de cada orden individual.
3. **USDT asignado a la subcuenta:** Transferir solo el capital que estás dispuesto a comprometer.
4. **Selección de activos:** Solo operar activos con fundamentos sólidos y alta capitalización.

---

## 6. Operación en la CLI: Comandos Prácticos

### A. Crear bots en masa (Multi-símbolo)
Para lanzar rápidamente un cluster de acumulación para `BTC`, `ETH`, `SOL` y `BNB` bajo la subcuenta `bluechip`:
```bash
python -m cli bot create --symbol BTCUSDT,ETHUSDT,SOLUSDT,BNBUSDT --budget 300 --target-profit 4.5 --buy-volume 15 --poll-interval 60 --subaccount bluechip
```

### B. Monitorear el Estado del Cluster
Para ver el rendimiento general, el precio promedio de tus posiciones y el PnL no realizado de todo el hub:
```bash
python -m cli hub state
```

### C. Ajustar Parámetros de un Bot
Si el mercado está muy volátil y quieres reducir el número máximo de recompras o el tamaño máximo de posición del bot de Bitcoin:
```bash
python -m cli bot update louise_btc_a1b2 --max-position 2500 --max-purchases 12 --poll-interval 120
```

### D. Forzar Reporte en Telegram
Si quieres recibir inmediatamente un balance general y de estado del cluster en tu teléfono:
```bash
python -m cli notify
```

---

## 7. Mantenimiento de la Base de Datos

### Purga Automática de Snapshots (v4.2+)
El sistema genera un snapshot de P&L por cada ciclo de poll por bot. Con 10 bots a 5min de intervalo, esto son ~1M filas/año.

El `TelegramNotifier` ejecuta automáticamente `purge_old_snapshots(days=90)` cada vez que envía un reporte periódico. Esto elimina snapshots con más de 90 días de antigüedad.

**Purga manual** (si necesitas liberar espacio inmediatamente):
```bash
# Desde Python/CLI:
from runtime.core.louise_db import LouiseDB
db = LouiseDB()
deleted = db.purge_old_snapshots(days=30)  # Purgar snapshots de más de 30 días
print(f"Eliminados: {deleted} registros")
```

---

## 8. Detección de Posiciones Huérfanas

### Qué es una Posición Huérfana
Una posición huérfana ocurre cuando un epoch queda en estado `RUNNING` pero el bot no está activamente operando (crasheó, perdió conexión, o la venta de take-profit falló).

### Detección Automática (v4.2+)
El `OrphanGuard` ahora incluye `scan_louise_orphans()` que detecta:
- **Epochs sin compras** creados hace más de 24 horas (bot creó epoch pero nunca compró).
- **Epochs estancados** donde la última compra fue hace más de 24 horas sin que el epoch se cierre.

### Resolución Manual
Si detectas un epoch huérfano:
1. Verifica el estado del bot: `python -m cli bot status <bot_id>`
2. Si el bot está funcionando pero el precio no ha alcanzado el take-profit, espera.
3. Si el bot está caído o el gateway desconectado, reinicia el motor.
4. En último caso, cierra el epoch manualmente vía la API REST.

---

## 9. Seguridad

### Protección de Archivos Sensibles
- **Linux/macOS:** Los archivos del vault se protegen automáticamente con `chmod 600` (solo el propietario puede leer/escribir).
- **Windows (v4.2+):** Se usa `icacls` para remover permisos heredados y otorgar acceso solo al usuario actual.

### Buenas Prácticas
> [!CAUTION]
> - **Nunca** compartas tu archivo `.env` o los archivos del vault en repositorios públicos.
> - Usa siempre el vault encriptado de Pecunator para almacenar API keys (no variables de entorno crudas en producción).
> - Configura tu bot de Telegram como **privado** y nunca compartas el chat ID en público.
> - Revisa periódicamente los permisos de tus API keys en Binance: habilita solo "Spot Trading" y "Read", desactiva "Withdrawals".

---

## 10. Troubleshooting

### Bot no compra a pesar de tener USDT disponible
1. **Precio no ha bajado:** Louise solo compra cuando el precio es **estrictamente inferior** al de la última compra.
2. **BudgetGuard bloqueado:** Verifica el estado: `python -m cli hub state`. Si el gasto de 24h del hub "louise" llegó a su techo, espera a que se reinicie la ventana.
3. **API Fuse activo:** Si el peso de la API de Binance superó el 80%, todas las llamadas REST están bloqueadas. Espera al auto-reset.
4. **USDT insuficiente:** Verifica que la subcuenta tiene saldo libre suficiente para cubrir el `buy_volume` configurado.

### Notificaciones de Telegram no llegan
1. Verifica que `PECUNATOR_ALERT_TELEGRAM_TOKEN` y `PECUNATOR_ALERT_TELEGRAM_CHAT_ID` estén configurados en `.env`.
2. Asegúrate de que el bot de Telegram tiene permisos para enviar mensajes al chat/grupo.
3. Prueba manualmente: `python -m cli notify`.

### Reinicios automáticos frecuentes
Si recibes alertas `BOT_AUTO_RESTART` frecuentes, revisa:
1. Los logs del motor para errores del gateway o del WebSocket.
2. La estabilidad de tu conexión a internet.
3. Si la API key tiene los permisos correctos en Binance.

---

## 11. Checklist de Puesta en Marcha

1. [ ] Crear un Bot de Telegram con `@BotFather` y obtener su Token.
2. [ ] Obtener tu Chat ID (utilizando bots de Telegram como `@userinfobot`).
3. [ ] Añadir las variables `PECUNATOR_ALERT_TELEGRAM_TOKEN`, `PECUNATOR_ALERT_TELEGRAM_CHAT_ID` y `LOUISE_TELEGRAM_NOTIFY_INTERVAL_HOURS` al archivo `.env`.
4. [ ] Crear y encriptar las credenciales API de Binance en el Vault de Pecunator (`python -m cli vault add`).
5. [ ] Crear tu cluster de bots usando el comando masivo `python -m cli bot create`.
6. [ ] Iniciar el gateway de Binance (`python -m cli gateway start`).
7. [ ] Iniciar el motor en segundo plano (`python -m cli engine start`).
8. [ ] Comprobar el correcto funcionamiento enviando un reporte manual (`python -m cli notify`).

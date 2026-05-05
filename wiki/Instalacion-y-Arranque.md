# Instalación y Arranque — Pecunator

> Guía completa para instalar, configurar y arrancar el motor Python y la UI Flutter Desktop.

---

## Requisitos

| Componente | Versión mínima |
|------------|---------------|
| Python | 3.11+ |
| Flutter SDK | Latest stable |
| Windows | Para producción desktop |
| Git | Cualquier versión reciente |

---

## 1. Clonar el Repositorio

```bash
git clone https://github.com/CuevazaArt/Pecunator.git
cd Pecunator
```

---

## 2. Motor Python

### 2.1 Instalar dependencias

```bash
# Dependencias de producción
pip install -r requirements.txt

# Dependencias de desarrollo (tests, linters)
pip install -r requirements-dev.txt
```

### 2.2 Configurar credenciales

**Opción A — Variables de entorno (arranque rápido):**

```bash
# Windows PowerShell
$env:PECUNATOR_BINANCE_API_KEY = "tu_api_key"
$env:PECUNATOR_BINANCE_API_SECRET = "tu_api_secret"
```

**Opción B — Vault cifrado (recomendado para producción):**  
Gestionar desde la UI Flutter (ver sección Vault en la UI).

> ⚠️ Usar **una sola fuente activa** por sesión para evitar mezclar cuentas.

### 2.3 Arrancar el motor

```bash
# Arranque directo
python main.py

# Con PowerShell (venv + arranque)
powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1

# Motor inmortal (supervisor que reinicia si el proceso cae)
powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine_immortal.ps1
```

**Motor disponible en:** `http://127.0.0.1:8765`  
**OpenAPI interactivo:** `http://127.0.0.1:8765/docs`

### 2.4 Variables de entorno opcionales

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PECUNATOR_API_HOST` | `127.0.0.1` | Host de la API |
| `PECUNATOR_API_PORT` | `8765` | Puerto de la API |
| `PECUNATOR_API_WEIGHT_LIMIT_1M` | `6000` | Límite de referencia de peso REST para la barra UI |
| `PECUNATOR_EQUITY_BASE_ASSET` | `USDT` | Activo base para métricas de equity |
| `PECUNATOR_EQUITY_AVG_WINDOW` | `6` | Ventana de promedio rolling de equity |
| `PECUNATOR_EQUITY_POLL_STRIDE` | `5` | Cada cuántos ciclos refrescar equity |
| `PECUNATOR_ENGINE_STUB` | — | Si `=1`, modo stub sin servidor (solo log) |

### 2.5 Solución de problemas del motor

**Puerto 8765 ocupado por proceso anterior:**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/engine/stop_engine_port.ps1
```

**Autoarranque tras reinicio de Windows:**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/engine/InstallImmortalStartup.ps1
```

---

## 3. UI Flutter Desktop

### 3.1 Instalar Flutter SDK

Instalar [Flutter SDK para Windows](https://docs.flutter.dev/get-started/install/windows).

### 3.2 Inicializar Flutter Desktop

```powershell
# Desde la raíz del repo
powershell -ExecutionPolicy Bypass -File scripts/ui/init_flutter_desktop.ps1
```

Esto instala dependencias y configura `desktop_shell/`.

### 3.3 Ejecutar la UI

```bash
# Opción 1: Flutter directo
cd desktop_shell
flutter run -d windows

# Opción 2: Script PowerShell (PATH recargado + flutter run)
powershell -ExecutionPolicy Bypass -File scripts/ui/run_dashboard.ps1

# Opción 3: Doble clic en
scripts/ui/run_dashboard.cmd
```

### 3.4 Crear acceso directo en escritorio

```powershell
# Crea PecunatorCore.lnk en el escritorio (motor + app)
powershell -ExecutionPolicy Bypass -File scripts/ui/InstallDesktopShortcut.ps1
```

El lanzador se encuentra en `scripts/ui/PecunatorDesktopLauncher.ps1`.

### 3.5 Build para producción

```bash
cd desktop_shell
flutter build windows
# Ejecutable: desktop_shell/build/windows/x64/runner/Release/pecunator_desktop.exe
```

### 3.6 Limpiar caché y recompilar

> ⚠️ Cerrar `pecunator_desktop.exe` primero para liberar DLLs.

```bash
cd desktop_shell
flutter clean
flutter pub get
flutter build windows     # o flutter run -d windows
```

**Datos del hub en SQLite:** `runtime/data/dorothy_hub.sqlite`  
Eliminar este archivo solo si se quiere resetear logs/config del hub (hacer copia antes).

---

## 4. Flujo de Inicio Recomendado

```
1. Arrancar motor Python:
   powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1

2. Verificar que la API responde:
   curl http://127.0.0.1:8765/api/v1/vault/status

3. Arrancar UI Flutter:
   scripts/ui/run_dashboard.cmd

4. Configurar credenciales desde la UI (pestaña Vault)

5. Arrancar instancias de bots desde los Hubs
```

---

## 5. Verificación rápida

```bash
# ¿Motor corriendo?
curl http://127.0.0.1:8765/api/v1/vault/status

# ¿Credenciales activas?
curl http://127.0.0.1:8765/api/v1/credentials/active

# ¿Gateway conectado?
curl http://127.0.0.1:8765/api/v1/gateway/snapshot
```

---

## 6. Tests

```bash
# Python
pytest runtime/tests/ -v

# Python (test específico)
pytest runtime/tests/test_dorothy.py -v

# Flutter
cd desktop_shell
flutter test test/ -v

# Análisis Flutter
flutter analyze lib/
```

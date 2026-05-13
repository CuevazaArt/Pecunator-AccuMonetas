# Instrucciones para Levantar la UI Flutter

## Status Actual
- ✅ Motor Python: **ACTIVO en http://127.0.0.1:8000**
- ✅ Tests Python: **240/240 PASSING**
- ✅ Documentación: **COMPLETA**
- ⏳ UI Flutter: **LISTA PARA LEVANTAR**

---

## Opción 1: Levantar UI (Windows)

### Requisitos
- Flutter SDK instalado (https://docs.flutter.dev/get-started/install/windows)
- PATH actualizado con Flutter binaries

### Pasos

#### 1. Verificar Flutter instalado
```powershell
flutter --version
flutter doctor
```

#### 2. Navegar al directorio UI
```powershell
cd desktop_shell
```

#### 3. Instalar dependencias
```powershell
flutter pub get
```

#### 4. Levantar la app
```powershell
flutter run -d windows
```

**Resultado esperado:**
- App Flutter se abre
- Login con token (auto-generado en `runtime/data/api.token`)
- Dashboard muestra: 0 bots activos, portfolio vacío
- WebSocket conectado a motor

---

## Opción 2: Usar Script Rápido (Windows)

Si existe el script de arranque:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/ui/run_dashboard.ps1
```

O:
```powershell
& "scripts/ui/run_dashboard.cmd"
```

---

## Opción 3: Build Release (Windows)

Si quieres compilar un .exe ejecutable:

```powershell
cd desktop_shell

# Limpiar caché
flutter clean
flutter pub get

# Compilar para Windows
flutter build windows --release

# Ejecutar binary
.\build\windows\x64\runner\Release\pecunator_desktop.exe
```

**Artifact generado:**
- `desktop_shell/build/windows/x64/runner/Release/pecunator_desktop.exe`

---

## Flujo de Evaluación en la UI

### 1. Login
- Token se lee automáticamente desde `runtime/data/api.token`
- Ingresa Bearer token (file auto-filled)
- Click "Connect"

### 2. Dashboard Principal
- **Bots Activos:** 0 (estado limpio)
- **Portfolio Total:** $0 (sin dinero real)
- **PnL Realtime:** N/A (sin bots)
- **Subacuenta:** Default (Louise DCA)

### 3. Crear Bot
- Click "+ New Bot"
- Nombre: "Test Louise 1"
- Símbolo: "BTCUSDT"
- Cantidad: 100 USDT
- Click "Create"
- **Esperado:** Bot aparece en lista con estado PAUSED

### 4. Controlar Bot
- Click bot en lista
- Botones disponibles:
  - ▶️ **Resume** — Inicia ciclos de compra
  - ⏸️ **Pause** — Pausa compras
  - 🗑️ **Delete** — Elimina bot
- Observar metricas en tiempo real (WebSocket)

### 5. WebSocket Real-Time
- Mientras bot está RUNNING:
  - Nuevas compras = evento websocket inmediato
  - Métricas actualizadas cada 2-5s
  - Precio BTC actualizado
  - PnL recalculado

### 6. Manejo de Errores
- Desconectar motor: `pkill -f "python main.py"`
- UI debe mostrar "Disconnected" sin crash
- Reconectar motor
- UI debe reconectar automáticamente

---

## Troubleshooting

### Flutter no encontrado
```powershell
# Instalar Flutter SDK
# https://docs.flutter.dev/get-started/install/windows

# Agregar al PATH manualmente
$env:PATH += ";C:\flutter\bin"
flutter --version
```

### Puerto 8000 ocupado
```powershell
# Ver qué proceso usa el puerto
netstat -ano | findstr :8000

# Matar proceso (ejemplo: PID 1234)
taskkill /PID 1234 /F

# Reiniciar motor
python main.py
```

### Cache de Flutter corrupto
```powershell
cd desktop_shell
flutter clean
flutter pub get
flutter run -d windows
```

### Certificado de desarrollo inválido
```powershell
cd desktop_shell

# En primera ejecución, Windows puede bloquear el .exe
# Permitir en Windows Defender/SmartScreen
# O compilar sin verificación:
flutter run -d windows --verbose
```

---

## Métricas a Validar en UI

✅ **Login & Auth**
- [ ] Token se carga desde archivo
- [ ] Bearer header se envía correctamente
- [ ] API responde 200 (no 401)

✅ **Dashboard**
- [ ] Bots listados correctamente
- [ ] Portfolio total calculado
- [ ] PnL% mostrado en tiempo real

✅ **Creación de Bot**
- [ ] Validación de formulario
- [ ] Status cambia a RUNNING después de crear
- [ ] WebSocket conecta automáticamente

✅ **Control en Vivo**
- [ ] Pause detiene ciclos
- [ ] Resume reinicia ciclos
- [ ] Métricas actualizan en tiempo real

✅ **Recuperación de Errores**
- [ ] Motor offline = "Disconnected" en UI
- [ ] Reconecta cuando motor vuelve
- [ ] No hay crashes de UI

---

## Datos Esperados

### Health Check (Motor)
```json
{
  "status": "healthy",
  "fuse_tripped": false,
  "weight_zone": "GREEN",
  "active_bots": 0,
  "hubs": {
    "louise": {
      "active_bots": 0,
      "total_portfolio": 0.0,
      "completed_epochs": 0
    }
  }
}
```

### Bot Creado
```json
{
  "id": "louise_1",
  "strategy": "louise",
  "state": "PAUSED",
  "symbol": "BTCUSDT",
  "buy_amount_usdt": 100,
  "epochs": [],
  "created_at": "2026-05-13T..."
}
```

---

## Próximos Pasos Después de Evaluación

1. ✅ Merge PR a main (GitHub Actions)
2. ⏳ **Peer Security Review** (~2h)
3. ⏳ **Load Testing** (~2h)
4. ⏳ **Production Deployment**

---

**¿Preguntas?** Revisar `JORNADA_COMPLEMENTACION.md` o `README.md` para más contexto.

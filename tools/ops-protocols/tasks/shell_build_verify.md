# Task: Verificación de Desktop Shell (Flutter)

## Objetivo
Asegurar que el frontend Flutter del desktop shell compila correctamente,
no tiene regresiones de análisis estático, y mantiene sincronía con los
schemas del backend FastAPI.

## Contexto del Proyecto
- **Ubicación:** `desktop_shell/`
- **Framework:** Flutter (Windows desktop)
- **Backend schemas:** `runtime/api/schemas.py` (Pydantic models)
- **Análisis previo:** `desktop_shell/analyze_out.txt`
- **Config:** `desktop_shell/pubspec.yaml`

## Pasos de Ejecución

### Paso 1 — Análisis Estático
```bash
cd desktop_shell && flutter analyze
```
Capturar output completo. Clasificar issues en:
- 🔴 **Errors** — Impiden compilación
- ⚠️ **Warnings** — Posibles problemas
- 💡 **Info/Hints** — Sugerencias de mejora

### Paso 2 — Comparar con Análisis Anterior
Leer `desktop_shell/analyze_out.txt` (análisis previo).
Detectar:
- Issues **nuevos** que no existían antes → Regresiones
- Issues **resueltos** que ya no aparecen → Progreso
- Issues **persistentes** → Deuda técnica pendiente

### Paso 3 — Verificar Compilación
```bash
cd desktop_shell && flutter build windows --debug
```
Si falla:
- Capturar error exacto
- Identificar si es error de dependencia, código, o configuración
- Proponer fix

### Paso 4 — Sincronía de Schemas
Comparar los modelos de datos del frontend (archivos Dart en `lib/`)
con los schemas del backend en `runtime/api/schemas.py`:

- ¿Los campos coinciden en nombre y tipo?
- ¿Hay campos nuevos en el backend que el frontend no conoce?
- ¿Hay campos deprecados en el backend que el frontend sigue usando?

Generar tabla de discrepancias:
| Schema Backend | Modelo Frontend | Estado | Discrepancia |
|---------------|----------------|--------|-------------|
| BotStatus     | BotStatusModel | ✅/⚠️  | [detalle]    |
| ...           | ...            | ...    | ...         |

### Paso 5 — Dependencias
Revisar `pubspec.yaml` y `pubspec.lock`:
- ¿Hay paquetes con versiones muy antiguas?
- ¿Hay deprecation warnings en dependencias?

### Paso 6 — Actualizar Registro
Guardar el nuevo output de `flutter analyze` en `desktop_shell/analyze_out.txt`
para la próxima comparación.

## Output Esperado
Reporte con:
1. Estado de compilación: ✅ BUILD OK / 🔴 BUILD FAILED
2. Análisis estático: X errors, Y warnings, Z hints
3. Delta vs análisis anterior: +N nuevos, -M resueltos
4. Tabla de sincronía de schemas
5. Lista de dependencias a actualizar (si aplica)

## Criterios de Éxito
- [ ] `flutter analyze` ejecutado
- [ ] Comparación con análisis anterior realizada
- [ ] Build debug intentado
- [ ] Sincronía de schemas verificada
- [ ] `analyze_out.txt` actualizado

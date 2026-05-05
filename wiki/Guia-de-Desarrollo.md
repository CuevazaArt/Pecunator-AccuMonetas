# Guía de Desarrollo — Pecunator

> Flujo de trabajo, convenciones, tests y CI/CD para contribuir al proyecto.  
> Rama de desarrollo activa: `refactor/stable-ui-and-tests`

---

## Quick Start (5 minutos)

```bash
# 1. Clonar
git clone https://github.com/CuevazaArt/Pecunator.git
cd Pecunator

# 2. Instalar dependencias Python
pip install -r requirements-dev.txt

# 3. Instalar dependencias Flutter
cd desktop_shell && flutter pub get && cd ..

# 4. Verificar tests
pytest runtime/tests/ -v
cd desktop_shell && flutter test test/ -v
```

---

## Estructura de Branches

| Branch | Propósito |
|--------|-----------|
| `main` | Rama estable — siempre deployable. **Push directo bloqueado.** |
| `refactor/stable-ui-and-tests` | Desarrollo activo — todo el trabajo va aquí |
| `feature/*` | Ramas de feature derivadas desde `refactor/stable-ui-and-tests` |

### Reglas

**✅ HACER:**
- Desarrollar en `refactor/stable-ui-and-tests` o ramas de feature derivadas
- Crear PRs hacia `refactor/stable-ui-and-tests`
- Correr tests localmente antes de hacer push
- Documentar cambios en `docs/CHANGELOG.md`

**❌ NO HACER:**
- Push directo a `main` (está protegido)
- PRs hacia `main` sin autorización explícita
- Mergear código sin tests
- Ignorar fallos de GitHub Actions

---

## Flujo de Trabajo

### 1. Crear rama de feature

```bash
git checkout refactor/stable-ui-and-tests
git pull
git checkout -b feature/nombre-de-la-feature
```

### 2. Desarrollar y testear

```bash
# Hacer cambios...

# Python tests
pytest runtime/tests/ -v

# Flutter tests
cd desktop_shell
flutter test test/ -v
flutter analyze lib/

# Commit con formato convencional
git add .
git commit -m "feat(scope): descripción del cambio"
```

**Formato de commits:**

| Prefijo | Cuándo usar |
|---------|-------------|
| `feat(scope):` | Nueva funcionalidad |
| `fix(scope):` | Corrección de bug |
| `docs:` | Solo documentación |
| `refactor(scope):` | Refactorización sin cambio funcional |
| `test:` | Tests |
| `chore:` | Tareas de mantenimiento |

### 3. Push y PR

```bash
git push -u origin feature/nombre-de-la-feature

# Crear PR hacia refactor/stable-ui-and-tests
gh pr create --base refactor/stable-ui-and-tests \
             --head feature/nombre-de-la-feature \
             --title "feat: descripción" \
             --body "Descripción de los cambios"
```

### 4. Esperar GitHub Actions

GitHub Actions ejecuta automáticamente:
- ✅ Python tests (pytest en Python 3.11 y 3.12)
- ✅ Flutter tests (flutter test)
- ✅ Análisis de código (ruff, dart analyzer)

### 5. Merge a refactor branch

Una vez que pasan los tests y hay revisión:

```bash
gh pr merge <PR_NUMBER> --merge
```

---

## Tests

### Python

```bash
# Todos los tests
pytest runtime/tests/ -v

# Test específico
pytest runtime/tests/test_dorothy.py -v

# Test específico por nombre
pytest runtime/tests/test_dorothy.py::test_defaults -v

# Con reporte de duración
pytest runtime/tests/ -v --durations=10

# Con cobertura
pytest runtime/tests/ --cov=runtime --cov-report=term-missing
```

**Estructura de tests:**

```
runtime/
└── tests/
    ├── __init__.py
    └── test_dorothy.py    # 25+ tests para Dorothy
```

### Flutter

```bash
cd desktop_shell

# Todos los tests
flutter test test/ -v

# Análisis estático
flutter analyze lib/

# Formato de código
dart format lib/
```

---

## Organización del Código

### Python (Backend)

```
runtime/
├── tests/              # Suite de tests
├── api/                # FastAPI endpoints
├── bot/                # Compatibilidad legacy (deprecado)
├── connectors/         # Clientes API
├── core/               # Config, seguridad, state
└── modules/
    ├── bots/           # Lógica de bots (imports canónicos aquí)
    └── tools/          # Herramientas operativas
```

**Convenciones Python:**
- Type hints en funciones públicas
- Docstrings en clases
- Anti-NaN guards en operaciones con `Decimal`
- `sanitize_log_message()` en toda salida de log
- No bare `except:` — siempre especificar tipo
- Imports: stdlib → third party → local

### Flutter (Frontend)

```
desktop_shell/lib/
├── config/app_config.dart      # Configuración centralizada
├── providers/app_providers.dart # Estado con Riverpod
├── services/
│   ├── http_client.dart
│   ├── exceptions.dart
│   └── preferences.dart
├── screens/                    # Pantallas completas
│   ├── home_screen.dart
│   ├── bots_screen.dart
│   └── spot_account_screen.dart
├── widgets/                    # Widgets reutilizables
│   ├── error_display.dart
│   ├── logs_viewer.dart
│   └── gateway_status.dart
├── utils/number_formatter.dart # Helpers
├── api_client.dart             # Cliente HTTP del motor
└── main.dart                   # Entry point
```

---

## Ejemplos de Tareas Comunes

### Añadir un test Python

```python
# runtime/tests/test_dorothy.py

def test_nueva_feature():
    """Test de la nueva feature."""
    # Arrange
    config = DorothyConfig(symbol="BTCUSDT")
    
    # Act
    config.normalize()
    
    # Assert
    assert config.symbol == "BTCUSDT"
```

### Añadir un widget Flutter

```dart
// desktop_shell/lib/widgets/nuevo_widget.dart

import 'package:flutter/material.dart';

class NuevoWidget extends StatelessWidget {
  const NuevoWidget({super.key});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Text('Nuevo Widget'),
      ),
    );
  }
}
```

### Añadir un Riverpod provider

```dart
// desktop_shell/lib/providers/app_providers.dart

final miDatoProvider = FutureProvider<MiDato>((ref) async {
  final api = ref.watch(engineApiProvider);
  return api.fetchMiDato();
});
```

---

## GitHub Actions

### Workflows disponibles

| Workflow | Trigger | Qué ejecuta |
|----------|---------|-------------|
| `test-python.yml` | Push a `refactor/**`, `main`, PR a `main` | pytest (Python 3.11, 3.12) |
| `test-flutter.yml` | Push a `refactor/**`, `main`, PR a `main` | flutter test + dart analyzer |
| `protect-main.yml` | PR hacia `main` | Bloquea PRs desde `refactor/*` sin autorización |
| `sync-main.yml` | Push a `main` con cambios en `docs/` | Sincroniza docs a `refactor/stable-ui-and-tests` |
| `secret-scan.yml` | Push y PR a ramas principales | Gitleaks — detección de secretos |

### Ver logs de CI

```bash
# Listar últimas ejecuciones
gh run list --branch refactor/stable-ui-and-tests -L 10

# Ver logs de una ejecución
gh run view <RUN_ID> --log
```

---

## Sincronización con Main

```bash
# Obtener últimas docs de main
git fetch origin
git merge origin/main -- docs/
git push origin refactor/stable-ui-and-tests

# Obtener mejoras de código de main
git fetch origin
git merge origin/main -- runtime/core/
git push origin refactor/stable-ui-and-tests

# Mantener rama de feature actualizada
git fetch origin
git rebase origin/refactor/stable-ui-and-tests
git push --force-with-lease origin feature/tu-rama
```

---

## Checklist antes de crear un PR

- [ ] El código corre localmente sin errores
- [ ] Tests Python pasan: `pytest runtime/tests/ -v`
- [ ] Tests Flutter pasan: `flutter test test/ -v`
- [ ] Código formateado: `dart format lib/`
- [ ] Sin warnings de lint: `flutter analyze lib/`
- [ ] Commits descriptivos con formato convencional
- [ ] Descripción del PR explica los cambios

---

## Proceso para Mergear a Main

1. Obtener **autorización explícita**: "merge to main approved"
2. Crear PR formal: `gh pr create --base main --head refactor/stable-ui-and-tests`
3. Esperar que GitHub Actions pase + aprobación del owner
4. Mergear cuando todos los checks estén en verde

# Task: Boy Scout Hardening Pass

## Objetivo
Aplicar mejoras incrementales de calidad al codebase del runtime sin alterar
la lógica de negocio. Cada ejecución selecciona archivos no tocados recientemente
y les aplica el estándar de producción.

## Reglas Inquebrantables
1. **NO cambiar lógica de negocio** — Solo calidad de código
2. **NO agregar dependencias** — Trabajar con lo que ya existe
3. **NO borrar comentarios existentes** — Preservar documentación
4. **Cada cambio debe pasar los tests** — Ejecutar suite después de editar

## Alcance por Ejecución
Seleccionar **3 archivos** del `runtime/` que no hayan sido modificados
en el commit más reciente. Priorizar por este orden:
1. Archivos en `runtime/core/` (infraestructura crítica)
2. Archivos en `runtime/connectors/` (interfaz con exchange)
3. Archivos en `runtime/api/` (capa de presentación)
4. Archivos en `runtime/modules/` (lógica de bots)

## Checklist por Archivo

### A) Type Hints
- [ ] Todas las funciones públicas tienen type hints en parámetros
- [ ] Todas las funciones públicas tienen type hint de retorno
- [ ] Los tipos complejos usan `Optional`, `Union`, `dict[str, ...]` correctamente
- [ ] Imports de `typing` o `__future__.annotations` presentes si necesario

### B) Error Handling
- [ ] No hay `except:` bare (sin tipo de excepción)
- [ ] No hay `except Exception:` que silencie errores con `pass`
- [ ] Operaciones de red tienen timeout y retry
- [ ] Operaciones con Decimal tienen guard contra NaN/Infinity:
  ```python
  # Anti-NaN guard pattern
  if value.is_nan() or value.is_infinite():
      value = Decimal("0")
  ```

### C) Docstrings
- [ ] Todas las clases tienen docstring describiendo propósito
- [ ] Funciones públicas tienen docstring con Args/Returns
- [ ] Módulo tiene docstring de nivel superior

### D) Code Hygiene
- [ ] No hay `print()` sueltos (usar logger)
- [ ] No hay TODO sin ticket/referencia
- [ ] No hay imports sin usar
- [ ] Constantes mágicas extraídas a variables con nombre descriptivo

## Pasos de Ejecución

### Paso 1 — Seleccionar Archivos
```bash
git log --oneline -5 -- runtime/
```
Identificar los 3 archivos con menos actividad reciente.

### Paso 2 — Aplicar Checklist
Por cada archivo seleccionado, aplicar los 4 bloques del checklist.
Documentar cada cambio realizado.

### Paso 3 — Verificar Tests
```bash
python -m pytest runtime/tests/ -v --tb=short
```
Si algún test falla por los cambios, revertir el cambio específico.

### Paso 4 — Reportar
Generar tabla resumen:
| Archivo | Type Hints | Error Handling | Docstrings | Hygiene | Cambios |
|---------|-----------|----------------|------------|---------|---------|
| ...     | ✅/⚠️     | ✅/⚠️          | ✅/⚠️      | ✅/⚠️   | N       |

## Criterios de Éxito
- [ ] 3 archivos procesados
- [ ] Todos los tests siguen pasando
- [ ] Al menos 1 mejora aplicada por archivo
- [ ] Tabla resumen generada

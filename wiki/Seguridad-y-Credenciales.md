# Seguridad y Credenciales — Pecunator

> Política de seguridad, gestión del vault cifrado y buenas prácticas de credenciales.

---

## Vault de Credenciales

### Almacenamiento

| Archivo | Descripción |
|---------|-------------|
| `runtime/data/credentials.enc` | Credenciales cifradas con Fernet (AES 128-CBC + HMAC-SHA256) |
| `runtime/data/vault_local.key` | Clave del vault (machine-local, nunca en git) |

El vault usa **Fernet** de la librería `cryptography`. Solo hacen falta **API key** y **secret**.

### Gestión desde la UI Flutter

1. Abrir la sección **Vault** en la UI
2. Añadir nueva credencial (API key + secret) → se activa automáticamente
3. Para eliminar: seleccionar y borrar (la última credencial añadida se activa)

### Gestión vía variables de entorno

```bash
# Windows PowerShell
$env:PECUNATOR_BINANCE_API_KEY = "tu_api_key"
$env:PECUNATOR_BINANCE_API_SECRET = "tu_api_secret"
```

> ⚠️ **Usar una sola fuente activa por sesión** — vault O variables de entorno, no ambas al mismo tiempo.

---

## Principios de Seguridad

### Principio de Menor Privilegio

| Componente | Permisos |
|------------|----------|
| **API keys de bots** | Solo trading (spot) — **NUNCA withdraw** |
| **Subcuentas** | Cada bot opera con su propia key restringida por IP |
| **Flutter** | Nunca tiene API keys; habla solo con el motor Python |
| **LLM/IDE** | Solo invoca scripts; los scripts leen secrets del vault |

### Reglas absolutas

- API keys **NUNCA** en texto plano en el repositorio
- API keys **NUNCA** en código fuente ni en Flutter
- Private keys **NUNCA** en contexto del LLM
- Los logs **NUNCA** se publican sin revisión de sanitización

---

## Rotación y Revocación

### Rotación periódica

- Rotar API keys **cada 90 días** como mínimo
- Mantener documentados los identificadores de keys activas (sin sus valores) con fecha de creación

### Revocación de emergencia

> ⛔ Si hay **sospecha de compromiso**, revocar **INMEDIATAMENTE** desde la web de Binance **ANTES** de cualquier diagnóstico técnico.

```
1. Ir a: https://www.binance.com/en/my/settings/api-management
2. Revocar la key comprometida
3. SOLO ENTONCES diagnosticar qué pasó
4. Crear nueva key con permisos mínimos
5. Actualizar el vault
```

---

## Sanitización de Logs

Toda salida de log del motor pasa por `security_util.sanitize_log_message()` que redacta automáticamente:

- Patrones de firma Binance (`signature=...`)
- Valores de API keys
- Otros patrones de secrets configurados

```python
# Ejemplo de uso en código
from runtime.core.security_util import sanitize_log_message

log.info(sanitize_log_message(f"Calling API with params: {params}"))
```

---

## Escaneo Automático de Secretos (CI)

El repositorio incluye escaneo automático de secretos en CI:

- **Workflow:** `.github/workflows/secret-scan.yml`
- **Herramienta:** Gitleaks
- **Triggers:** Push y PR a ramas principales
- **Objetivo:** Detectar y bloquear exposición accidental de API keys, tokens u otros secrets

---

## Backup del Vault

> ⚠️ Si se pierde `vault_local.key`, las credenciales en `credentials.enc` **no pueden recuperarse**.

**Recomendación:** Guardar backup de `runtime/data/vault_local.key` en un lugar seguro fuera del repositorio (gestor de contraseñas, almacenamiento cifrado offline).

---

## Resumen de Archivos Sensibles

| Archivo | ¿En git? | Descripción |
|---------|----------|-------------|
| `runtime/data/credentials.enc` | ❌ No | Credenciales cifradas |
| `runtime/data/vault_local.key` | ❌ No | Clave del vault |
| `runtime/data/*.sqlite` | ❌ No | Bases de datos locales |
| `.env` (si existe) | ❌ No | Variables de entorno locales |
| `docs/` | ✅ Sí | Documentación (sin secrets) |
| `runtime/**/*.py` | ✅ Sí | Código fuente (sin hardcoded secrets) |

---

## API Keys de Binance — Configuración Recomendada

Al crear una API key en Binance para Pecunator:

1. **Habilitar:** Lectura de cuenta, Trading Spot
2. **Deshabilitar:** Retiro, Futures (si no se usa), Margin (si no se usa)
3. **Restricción por IP:** Configurar la IP del servidor/máquina que corre el motor
4. **Sin restricción de subdomain:** Solo para la máquina local de ejecución

Esta configuración minimiza el daño en caso de compromiso.

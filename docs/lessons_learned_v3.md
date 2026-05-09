# Pecunator Hardening: Lecciones Aprendidas (v3.1.0 - v3.1.1)

Durante la fase de endurecimiento y auditoría del motor Pecunator, se identificaron y mitigaron varios puntos críticos de falla. Este documento resume los hallazgos y las soluciones implementadas.

## 1. Validación de Esquemas (API 500)
**Problema**: El bot Elphaba (Margin Short) no iniciaba porque el esquema Pydantic `HubBotOut` requería `stop_loss_pct`. Como Elphaba no usa stop loss convencional, la validación fallaba con un error 500 interno.
**Lección**: Los esquemas compartidos entre diferentes tipos de bots deben ser lo suficientemente flexibles para manejar campos opcionales o específicos de cada lógica.
**Solución**: Se hizo `stop_loss_pct` opcional con valor por defecto `"0"`.

## 2. Visibilidad de Guards
**Problema**: Los mecanismos de seguridad (`ApiFuse`, `Governor`, `SymmetryGuard`) estaban envueltos en bloques `except Exception: pass`. Si fallaban, el bot seguía operando "a ciegas" sin que el operador supiera que las protecciones estaban inactivas.
**Lección**: Nunca silenciar errores en capas de seguridad crítica. Es mejor un log de advertencia ruidoso que un silencio peligroso.
**Solución**: Se reemplazaron por logs explícitos (`fuse_check_failed`, etc.) y se integraron al sistema de alertas.

## 3. Ruido en Logs y Rotación
**Problema**:
1. El archivo `backend.log` crecía sin límite, arriesgando el espacio en disco.
2. El polling constante de la UI Flutter (cada 1s para snapshot y fuse) enterraba los logs de ejecución real.
**Lección**: El logging productivo requiere gestión de cuotas y filtrado de ruido de transporte.
**Solución**:
- Implementado `RotatingFileHandler` (15MB total).
- Silenciado `uvicorn.access` por defecto (activable vía `PECUNATOR_ACCESS_LOGS=1`).

## 4. Asimetría de Despliegue
**Problema**: Crear Dorothy y luego Elphaba manualmente dejaba una ventana de tiempo (o riesgo de error humano/red) donde solo un lado del hedge estaba activo.
**Lección**: Las operaciones de cobertura deben ser atómicas.
**Solución**: Endpoint `/api/v1/hub/deploy-symmetric` que garantiza el éxito de ambos o realiza rollback total.

## 5. Supervivencia del Proceso
**Problema**: Si el motor Python crasheaba por una excepción no controlada, no había nada que lo levantara automáticamente.
**Lección**: Un sistema autónomo requiere supervisión externa (Watchdog).
**Solución**: Script `watchdog.py` que monitorea el endpoint `/health` y reinicia el proceso ante fallos.

## 6. Visibilidad del Prospector
**Problema**: El prospector realizaba escaneos pesados pero solo logueaba el inicio y el final, lo que hacía parecer que el sistema estaba "congelado" o no hacía nada.
**Lección**: Tareas de larga duración deben reportar progreso granular en el log para dar confianza al operador.
**Solución**: Añadido logging por batches (ej. "procesando batch 3/10") y logs detallados de decisiones de auto-staging.

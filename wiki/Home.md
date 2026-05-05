# Pecunator — Wiki

> **Hub de operaciones financieras algorítmicas** para un operador individual.  
> Motor Python + UI Flutter Desktop. Sin dashboard web.

---

## Índice de páginas

| Página | Descripción |
|--------|-------------|
| [Manifiesto](Manifesto) | Filosofía, principios y doctrina del proyecto |
| [Arquitectura](Arquitectura) | Diseño Flutter desktop + motor Python |
| [Mapa de Módulos](Mapa-de-Modulos) | Estructura de carpetas y ownership |
| [Instalación y Arranque](Instalacion-y-Arranque) | Setup completo, scripts de inicio |
| [API Surface](API-Surface) | Referencia completa de endpoints REST |
| [Bot Dorothy](Bot-Dorothy) | Escalera spot — manual operativo |
| [Bot Masha](Bot-Masha) | DCA multi-timeframe — manual operativo |
| [Bot Thusnelda](Bot-Thusnelda) | Cesta de símbolos — manual operativo |
| [Protocolos Operativos](Protocolos-Operativos) | Runbooks: cierre, botón rojo, auditorías |
| [Seguridad y Credenciales](Seguridad-y-Credenciales) | Vault, política de secretos, rotación |
| [Binance — Límites y Cumplimiento](Binance-Limites-y-Cumplimiento) | REST/WS rate limits y checklist |
| [Guía de Desarrollo](Guia-de-Desarrollo) | Flujo Git, tests, CI/CD |
| [Changelog](Changelog) | Historial de cambios arquitectónico |

---

## Resumen rápido

```
PecunatorCore/
├── runtime/          # Motor Python (FastAPI + lógica de dominio)
├── bots/             # Índices de bots (Dorothy, Masha, Thusnelda)
├── tools/            # Herramientas operativas (protocols, sandbox, weight-monitor)
├── desktop_shell/    # UI Flutter Desktop
├── docs/             # Documentación técnica
├── scripts/          # Scripts de arranque y operación
└── examples/         # Referencias históricas (no funcionales)
```

**Motor Python** → `python main.py` → API en `http://127.0.0.1:8765`  
**UI Flutter** → `flutter run -d windows` en `desktop_shell/`  
**OpenAPI** → `http://127.0.0.1:8765/docs`

---

## Convención de idioma

- **Coordinación y documentación:** Español
- **Código fuente, commits, identificadores:** Inglés

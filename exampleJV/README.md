# Dorothy7.0 (exampleJV)

Iteración de ejemplo del bot Dorothy; uso modular y cliente Binance vía `python-binance`.

## Credenciales (alineado con PecunatorCore)

1. Copia `config.example.py` → **`config.py`** (no se versiona).
2. Rellena `api_key` y `api_secret` de tu cuenta Binance (clave con permisos mínimos e IP restringida si aplica).

Alternativa sin archivo: exporta las mismas variables que usa el motor:

- `PECUNATOR_BINANCE_API_KEY`
- `PECUNATOR_BINANCE_API_SECRET`

`accesoAPI.py` resuelve credenciales en este orden: **`config.py` → variables de entorno**.

## Motor PecunatorCore + mismas claves

Si quieres que el motor HTTP (`python main.py`) arranque **sin** pasar claves a mano cuando ya tienes `exampleJV/config.py`:

```powershell
.\.venv\Scripts\python.exe scripts\run_engine_with_examplejv.py
```

La UI Flutter sigue usando el cofre o env según `runtime/core/settings.py`; este script solo facilita el arranque local cuando las claves viven en `exampleJV/config.py`.

## Referencias de API Binance

Ver [`docs/binance-api-and-compliance.md`](../docs/binance-api-and-compliance.md).

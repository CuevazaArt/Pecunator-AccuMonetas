# ⚠️ DEPRECATED — Flutter Desktop Shell

**Deprecated:** 2026-06-15
**Replaced by:** CLI (`cli/`) — Python Click-based command-line interface

## Reason

The Flutter desktop UI has been deprecated in favor of a lightweight Python CLI
that consumes the same REST API. This decision was made to:

1. **Focus development effort** on hardening the Louise DCA engine
2. **Eliminate the Flutter dependency** from the CI/CD pipeline
3. **Reduce attack surface** — fewer moving parts in production
4. **Enable headless server operation** — CLI is ideal for remote/VPS deployment

## Migration

All operations previously done via the Flutter UI are now available through the CLI:

```bash
python -m cli bot list          # List all bots
python -m cli bot create ...    # Create a new bot
python -m cli bot pause <id>    # Pause a bot
python -m cli health            # Health check
python -m cli gateway status    # Gateway status
```

See the project `README.md` for full CLI documentation.

## Status

- This directory is **NOT maintained** and will not receive updates.
- CI pipelines no longer test or build Flutter code.
- The code remains in the repo for reference only.

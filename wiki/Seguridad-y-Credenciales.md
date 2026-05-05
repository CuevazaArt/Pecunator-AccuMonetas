# Security and Credentials — Pecunator

> Security policy, encrypted vault management and good credential practices.

---

## Credential Vault

### Storage

| Archive | Description |
|---------|-------------|
| `runtime/data/credentials.enc` | Credentials encrypted with Fernet (AES 128-CBC + HMAC-SHA256) |
| `runtime/data/vault_local.key` | Vault key (machine-local, never in git) |

The vault uses **Fernet** from the `cryptography` library. You only need **API key** and **secret**.

### Management from the Flutter UI

1. Open the **Vault** section in the UI
2. Add new credential (API key + secret) → activates automatically
3. To delete: select and delete (the last added credential becomes active)

### Management via environment variables

```bash
# Windows PowerShell
$env:PECUNATOR_BINANCE_API_KEY = "tu_api_key"
$env:PECUNATOR_BINANCE_API_SECRET = "tu_api_secret"
```

> ⚠️ **Use a single active source per session** — vault OR environment variables, not both at the same time.

---

## Security Principles

### Least Privilege Principle

| Component | Permissions |
|------------|----------|
| **bot API keys** | Only trading (spot) — **NEVER withdraw** |
| **Subaccounts** | Each bot operates with its own IP-restricted key |
| **Flutter** | It never has API keys; talks only to the Python engine |
| **LLM/IDE** | It only invokes scripts; scripts read secrets from vault |

### Absolute rules

- API keys **NEVER** in plain text in the repository
- API keys **NEVER** in source code or in Flutter
- Private keys **NEVER** in the context of the LLM
- Logs are **NEVER** published without a sanitization review

---

## Rotation and Revocation

### Periodic rotation

- Rotate API keys **every 90 days** at least
- Keep active key identifiers documented (without their values) with creation date

### Emergency revocation

> ⛔ If there is **suspicion of compromise**, revoke **IMMEDIATELY** from the Binance website **BEFORE** any technical diagnosis.

```
1. Ir a: https://www.binance.com/en/my/settings/api-management
2. Revocar la key comprometida
3. SOLO ENTONCES diagnosticar qué pasó
4. Crear nueva key con permisos mínimos
5. Actualizar el vault
```

---

## Log Sanitization

All log output from the engine goes through `security_util.sanitize_log_message()` which automatically writes:

- Binance signature patterns (`signature=...`)
- API key values
- Other configured secret patterns

```python
# Example of use in code
from runtime.core.security_util import sanitize_log_message

log.info(sanitize_log_message(f"Calling API with params: {params}"))
```

---

## Automatic Secret Scanning (CI)

The repository includes automatic scanning of secrets in CI:

- **Workflow:** `.github/workflows/secret-scan.yml`
- **Tool:** Gitleaks
- **Triggers:** Push and PR to main branches
- **Goal:** Detect and block accidental exposure of API keys, tokens or other secrets

---

## Vault Backup

> ⚠️ If `vault_local.key` is lost, the credentials in `credentials.enc` **cannot be recovered**.

**Recommendation:** Save backup of `runtime/data/vault_local.key` in a safe place outside the repository (password manager, offline encrypted storage).

---

## Summary of Sensitive Files

| Archive | In git? | Description |
|---------|----------|-------------|
| `runtime/data/credentials.enc` | ❌ No | Encrypted credentials |
| `runtime/data/vault_local.key` | ❌ No | Vault Key |
| `runtime/data/*.sqlite` | ❌ No | Local databases |
| `.env` (if exists) | ❌ No | Local environment variables |
| `docs/` | ✅ Yes | Documentation (without secrets) |
| `runtime/**/*.py` | ✅ Yes | Source code (without hardcoded secrets) |

---

## Binance API Keys — Recommended Configuration

When creating an API key on Binance for Pecunator:

1. **Enable:** Account Reading, Spot Trading
2. **Disable:** Withdrawal, Futures (if not used), Margin (if not used)
3. **IP restriction:** Configure the IP of the server/machine that runs the engine
4. **No subdomain restriction:** Only for the local execution machine

This configuration minimizes damage in the event of a compromise.
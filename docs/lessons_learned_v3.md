# Pecunator Hardening: Lessons Learned (v3.1.0 - v3.1.1)

During the hardening and audit phase of the Pecunator engine, several critical failure points were identified and mitigated. This document summarizes the findings and implemented solutions.

## 1. Schema Validation (API 500)
**Problem**: The Elphaba bot (Margin Short) would not start because the Pydantic schema `HubBotOut` required `stop_loss_pct`. Since Elphaba does not use a conventional stop loss, validation failed with an internal 500 error.
**Lesson**: Shared schemas across different bot types must be flexible enough to handle optional or logic-specific fields.
**Solution**: Made `stop_loss_pct` optional with a default value of `"0"`.

## 2. Guard Visibility
**Problem**: Safety mechanisms (`ApiFuse`, `Governor`, `SymmetryGuard`) were wrapped in `except Exception: pass` blocks. If they failed, the bot continued operating "blind" without the operator knowing the protections were inactive.
**Lesson**: Never silence errors in critical security layers. A noisy warning log is better than dangerous silence.
**Solution**: Replaced with explicit logs (`fuse_check_failed`, etc.) and integrated into the alerting system.

## 3. Log Noise and Rotation
**Problem**:
1. The `backend.log` file grew without limit, risking disk space exhaustion.
2. Constant polling from the Flutter UI (every 1s for snapshot and fuse) buried the real execution logs.
**Lesson**: Production logging requires quota management and transport noise filtering.
**Solution**:
- Implemented `RotatingFileHandler` (15MB total).
- Silenced `uvicorn.access` by default (activatable via `PECUNATOR_ACCESS_LOGS=1`).

## 4. Deployment Asymmetry
**Problem**: Creating Dorothy and then Elphaba manually left a time window (or human/network error risk) where only one side of the hedge was active.
**Lesson**: Hedging operations must be atomic.
**Solution**: Endpoint `/api/v1/hub/deploy-symmetric` that guarantees both sides succeed or performs a full rollback.

## 5. Process Survival
**Problem**: If the Python engine crashed due to an unhandled exception, nothing would restart it automatically.
**Lesson**: An autonomous system requires external supervision (Watchdog).
**Solution**: `watchdog.py` script that monitors the `/health` endpoint and restarts the process on failure.

## 6. Prospector Visibility
**Problem**: The prospector performed heavy scans but only logged the start and end, making the system appear "frozen" or idle.
**Lesson**: Long-running tasks must report granular progress in the log to give the operator confidence.
**Solution**: Added per-batch logging (e.g. "processing batch 3/10") and detailed auto-staging decision logs.

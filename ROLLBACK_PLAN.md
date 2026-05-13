# Rollback Plan: Emergency Recovery Procedures

## Decision Tree

| Symptom | Severity | Rollback Type | Time |
|---------|----------|---------------|------|
| Single bot error | LOW | Pause bot, restart service | 5 min |
| Weight zone RED | MEDIUM | Pause all bots | 2 min |
| Database corruption | HIGH | Restore from backup | 30 min |
| API token compromised | HIGH | Rotate token + restart | 15 min |
| Gateway down >15 min | CRITICAL | Service restart or rollback | 10 min |
| Data loss detected | CRITICAL | Restore full backup | 60+ min |

---

## Rollback Levels

### Level 1: Soft Reset (No Code Change)

**When:** Single bot stuck, WebSocket flaky, but system fundamentally OK

**Steps:**
```bash
# 1. Pause all bots (freeze trading)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/bots/pause-all

# 2. Restart service (cleanly)
systemctl restart louise
sleep 10

# 3. Resume bots
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/bots/resume-all

# 4. Verify
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/health
```

**Recovery time:** 5-10 minutes

**Data impact:** ZERO (no changes)

---

### Level 2: Revert to Previous Commit

**When:** Bug introduced in latest deployment, tests failing, API errors

**Steps:**
```bash
# 1. Stop service
systemctl stop louise

# 2. Check recent commits
cd /opt/louise
git log --oneline -10

# 3. Revert to stable commit
git revert HEAD  # Creates new commit undoing changes
# OR
git reset --hard <commit_hash>  # Direct revert (more aggressive)

# 4. Restart
systemctl start louise

# 5. Verify health
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/health

# 6. If still broken, rollback further
git reset --hard <older_commit>
systemctl restart louise
```

**Recovery time:** 10-15 minutes

**Data impact:** Code only, DB intact

**Example:**
```bash
# If v1.2.3 is broken, revert to v1.2.2
git reset --hard v1.2.2
```

---

### Level 3: Restore Database from Backup

**When:** Database corruption detected, data loss, schema break

**Steps:**
```bash
# 1. Stop service
systemctl stop louise

# 2. Verify backup exists
ls -lh /backups/louise_hub.sqlite*
# Expected: Recent backup, e.g., louise_hub.sqlite.2026-05-13T18:00Z

# 3. Restore from backup
cp /backups/louise_hub.sqlite.2026-05-13T18:00Z \
   /opt/louise/runtime/data/louise_hub.sqlite

# 4. Verify backup integrity
sqlite3 /opt/louise/runtime/data/louise_hub.sqlite "PRAGMA integrity_check;"
# Expected: "ok"

# 5. Restart service
systemctl start louise

# 6. Verify data
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/bots | jq 'length'
# Should match expected bot count
```

**Recovery time:** 20-30 minutes

**Data impact:** Loss of trades/epochs after backup time (e.g., last 24h)

**Backup Strategy:**
```bash
# Daily at 00:00 UTC, keep 7 days of backups
# Symlink: /backups/louise_hub.sqlite → latest backup

# Manual backup (anytime)
cp runtime/data/louise_hub.sqlite \
   /backups/louise_hub.sqlite.$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

---

### Level 4: Full Service Replacement

**When:** Service completely broken, multiple cascading failures, data unrecoverable

**Steps:**
```bash
# 1. Notify stakeholders
# Email ops team: "Initiating Level 4 rollback, service will be down 1 hour"

# 2. Stop current service
systemctl stop louise

# 3. Completely clean up
rm -rf /opt/louise
rm -rf runtime/data/louise_hub.sqlite
rm -rf logs/

# 4. Re-clone from known good state
cd /opt
git clone https://github.com/CuevazaArt/Pecunator-AccuMonetas.git louise
cd louise
git checkout v1.2.2  # Last known good tag

# 5. Reinstall
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. Restore env vars and token
# (should be in version control or secure vault)
export BINANCE_API_KEY=...
export BINANCE_API_SECRET=...
export PECUNATOR_VAULT_PASSPHRASE=...
echo "$API_TOKEN" > runtime/data/api.token

# 7. Start fresh
systemctl start louise
sleep 10

# 8. Verify
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/health
```

**Recovery time:** 45-60 minutes

**Data impact:** Complete data loss (start fresh). All bots paused.

**Required:** Access to git repo, env var backup, API token

---

## Backup & Recovery Automation

### Automated Daily Backup

```bash
#!/bin/bash
# /etc/cron.daily/louise-backup

BACKUP_DIR="/backups"
DB_PATH="/opt/louise/runtime/data/louise_hub.sqlite"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Create backup
cp "$DB_PATH" "$BACKUP_DIR/louise_hub.sqlite.$TIMESTAMP"

# Keep only 7 days
find "$BACKUP_DIR" -name "louise_hub.sqlite.*" -mtime +7 -delete

# Update symlink to latest
ln -sf "louise_hub.sqlite.$TIMESTAMP" "$BACKUP_DIR/louise_hub.sqlite"

# Log backup
echo "Backup: $TIMESTAMP" >> /var/log/louise-backups.log
```

---

## Point-in-Time Recovery

**If you need to recover to a specific time (not just latest backup):**

```bash
# List all backups
ls -lh /backups/louise_hub.sqlite.*

# Example:
# louise_hub.sqlite.2026-05-13T00:00:00Z
# louise_hub.sqlite.2026-05-12T00:00:00Z
# louise_hub.sqlite.2026-05-11T00:00:00Z

# Restore to 2026-05-11 00:00
systemctl stop louise
cp /backups/louise_hub.sqlite.2026-05-11T00:00:00Z \
   /opt/louise/runtime/data/louise_hub.sqlite
systemctl start louise
```

---

## Testing Rollback Procedures

**Monthly Rollback Drill:**

```bash
# 1. Practice Level 1 soft reset (first Thursday of month)
systemctl restart louise
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/health

# 2. Practice Level 2 git revert (second Thursday)
git log --oneline | head -5
git revert HEAD --no-edit
git reset --hard HEAD~1  # Undo the revert

# 3. Test backup/restore (third Thursday)
cp runtime/data/louise_hub.sqlite \
   runtime/data/louise_hub.sqlite.test-backup
# ... simulate corruption ...
cp runtime/data/louise_hub.sqlite.test-backup \
   runtime/data/louise_hub.sqlite
```

---

## Escalation & Communication

### Notify Stakeholders

**Template Message:**
```
Subject: [LOUISE] Level X Rollback Initiated

We are executing a Level [1/2/3/4] rollback due to [brief reason].

Expected downtime: [5/10/30/60] minutes
Expected data loss: [none/last 24h/complete]
Action required: [none/approve Level 3+]

Status updates every 10 minutes.
```

**Recipients:**
- Ops oncall: pagerduty
- Trading team lead
- Risk officer (if Level 3+)

---

## Verification After Rollback

**Post-Rollback Checklist:**
- [ ] Service status: `systemctl status louise` → active
- [ ] Health endpoint: returns `"status": "healthy"`
- [ ] Bot count: matches expected (e.g., 5 bots)
- [ ] Recent log: no CRITICAL errors
- [ ] Weight governor: zone != "RED"
- [ ] Database: `PRAGMA integrity_check;` → "ok"
- [ ] Binance connectivity: can get price
- [ ] WebSocket: receives price updates

---

## Never Do

❌ Force-push to main (`git push --force`)
❌ Delete database without backup
❌ Ignore alerts for >30 minutes
❌ Restart without pausing bots first
❌ Restore without verifying backup integrity
❌ Keep trading during Level 3+ rollback

---

**See:** OPERATIONAL_RUNBOOK.md for ongoing monitoring.
**See:** DEPLOYMENT.md for initial setup.

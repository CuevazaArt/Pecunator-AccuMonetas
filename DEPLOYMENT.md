# Deployment Guide: Pecunator-AccuMonetas Louise Bot Hub

## Pre-Deployment Checklist

- [ ] Production server OS: Windows or Linux with Python 3.11+
- [ ] Binance API keys provisioned (subaccount: bluechip)
- [ ] SSL certificates if using HTTPS proxy
- [ ] Monitoring tools installed (optional: Prometheus, Grafana)
- [ ] Backup strategy in place (SQLite DB backups)
- [ ] Runbook reviewed by ops team
- [ ] Rollback plan tested

---

## Prerequisites

### System Requirements
- **OS:** Windows 10+, Linux (Ubuntu 20.04+), or macOS 12+
- **Python:** 3.11+
- **Flutter:** 3.41.9 (for desktop UI)
- **Disk:** 2GB minimum (SQLite + logs)
- **RAM:** 512MB minimum (typically uses <100MB)

### Environment Variables

Create a `.env` file or set these:

```bash
# Binance API
BINANCE_API_KEY=<bluechip_subaccount_key>
BINANCE_API_SECRET=<bluechip_subaccount_secret>

# API Server
PECUNATOR_API_HOST=0.0.0.0
PECUNATOR_API_PORT=8000
PECUNATOR_API_AUTH_DISABLED=0  # KEEP ENABLED (=0) IN PRODUCTION

# Louise Bot Tuning (optional — defaults provided)
LOUISE_PRICE_STALENESS_THRESHOLD=15        # seconds
LOUISE_MIN_USDT_BALANCE=8                   # minimum USDT to trade
LOUISE_COOLDOWN_BUY_FAIL=300                # seconds between buy retries
LOUISE_COOLDOWN_GATEWAY_FAIL=60             # seconds before retry
LOUISE_DEFAULT_MAX_POSITION_SIZE=5000       # USDT max exposure per bot
LOUISE_DEFAULT_MAX_PURCHASES_PER_EPOCH=20   # max DCA buys per cycle
LOUISE_DEFAULT_MAX_DRAWDOWN_PCT=-10         # max loss % before stop-loss
LOUISE_PAPER_TRADE=false                    # true for paper trading

# Vault Security
PECUNATOR_VAULT_PASSPHRASE=<strong_passphrase>  # Must be ≥32 chars

# Alerts (optional)
PECUNATOR_ALERT_TELEGRAM_TOKEN=<bot_token>
PECUNATOR_ALERT_TELEGRAM_CHAT_ID=<chat_id>
PECUNATOR_ALERT_EMAIL_ENABLED=0
```

---

## Step-by-Step Deployment

### 1. Clone and Set Up (5 min)

```bash
# Clone repo
git clone https://github.com/CuevazaArt/Pecunator-AccuMonetas.git
cd Pecunator-AccuMonetas

# Create venv
python3.11 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install Python deps
pip install -r requirements.txt
pip install -r requirements-dev.txt  # for tests/monitoring

# Flutter (if deploying UI)
flutter pub get -C desktop_shell/
flutter pub upgrade -C desktop_shell/
```

### 2. Verify Installation (5 min)

```bash
# Check Python environment
python --version  # Should be 3.11+
pip list | grep fastapi asyncpython-binance  # Verify key packages

# Check Flutter (if applicable)
flutter --version
dart --version
```

### 3. Set Environment Variables (5 min)

```bash
# Linux/macOS
export BINANCE_API_KEY=<key>
export BINANCE_API_SECRET=<secret>
export PECUNATOR_VAULT_PASSPHRASE=<passphrase>

# Windows (PowerShell)
$env:BINANCE_API_KEY = "<key>"
$env:BINANCE_API_SECRET = "<secret>"
$env:PECUNATOR_VAULT_PASSPHRASE = "<passphrase>"
```

### 4. Create API Token (5 min)

```bash
# Generate a secure token (32+ random chars)
python -c "import secrets; print(secrets.token_hex(32))"

# Save to runtime/data/api.token (create directory if needed)
mkdir -p runtime/data
echo "<generated_token>" > runtime/data/api.token
chmod 600 runtime/data/api.token  # Linux: restrict permissions
```

### 5. Verify Binance Connectivity (10 min)

```bash
# Start engine in test mode
python main.py &

# In another terminal, test gateway
python -c "
from runtime.connectors.binance_gateway import BinanceGateway
import asyncio

async def test():
    gw = BinanceGateway()
    await gw.start()
    ticker = await gw.get_ticker_price('BTCUSDT')
    print(f'BTC/USDT: {ticker}')
    await gw.stop()

asyncio.run(test())
"

# If successful: shows current BTC price
# If error: check API keys, Binance status, network
```

### 6. Initialize Database (2 min)

```bash
# The DB auto-initializes on first bot creation, but verify:
python -c "
from runtime.core.louise_db import LouiseDB
db = LouiseDB('runtime/data/louise_hub.sqlite')
bots = db.get_all_bots()
print(f'DB initialized. Existing bots: {len(bots)}')
"
```

### 7. Start Services (5 min)

**Option A: Direct Start**
```bash
python main.py
# Logs: Uvicorn running on http://0.0.0.0:8000
```

**Option B: Systemd Service (Linux)**
```bash
# Create /etc/systemd/system/louise.service
[Unit]
Description=Louise DCA Bot Hub
After=network.target

[Service]
Type=simple
User=trading
WorkingDirectory=/home/trading/Pecunator-AccuMonetas
EnvironmentFile=/home/trading/louise.env
ExecStart=/home/trading/venv/bin/python main.py
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target

# Enable and start
sudo systemctl enable louise
sudo systemctl start louise
sudo systemctl status louise
```

**Option C: Docker (Optional)**
```bash
docker build -t louise-bot .
docker run -d \
  -e BINANCE_API_KEY=$BINANCE_API_KEY \
  -e BINANCE_API_SECRET=$BINANCE_API_SECRET \
  -e PECUNATOR_VAULT_PASSPHRASE=$PECUNATOR_VAULT_PASSPHRASE \
  -p 8000:8000 \
  -v /data/louise:/app/runtime/data \
  louise-bot
```

---

## Post-Deployment Verification

### 1. API Health Check (2 min)

```bash
curl -H "Authorization: Bearer <api_token>" \
  http://localhost:8000/api/louise/health

# Expected response:
# {
#   "status": "healthy",  # or "degraded" if issues
#   "uptime_seconds": 45,
#   "active_bots": 0,
#   "weight_zone": "GREEN"
# }
```

### 2. WebSocket Connectivity (2 min)

```bash
# Open Flutter UI or use wscat
wscat -c "ws://localhost:8000/ws?token=<api_token>"

# Should receive: {"event": "connected", "timestamp": ...}
```

### 3. Run Full Test Suite (5 min)

```bash
pytest runtime/tests/ tests/ -v --tb=short -x

# Expected: 241 passed, 0 failed
```

### 4. Create Test Bot (5 min)

```bash
curl -X POST http://localhost:8000/api/louise/bots \
  -H "Authorization: Bearer <api_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "buy_volume": 10,
    "poll_interval_seconds": 300,
    "target_profit_pct": 2,
    "daily_budget_usdt": 500
  }'

# Expected: 201 Created with bot_id
# Then verify: curl http://localhost:8000/api/louise/bots
```

### 5. Monitor First 30 Minutes

Check logs for:
- ✅ No "CRITICAL" alerts
- ✅ Price feed active (WebSocket messages)
- ✅ Budget guard operational
- ✅ Bot polls executing (see poll_market logs)

---

## Rollback (Emergency)

If deployment fails:

```bash
# Stop service
systemctl stop louise  # or Ctrl+C if running directly

# Review logs
tail -f logs/louise.log

# See ROLLBACK_PLAN.md for detailed recovery steps
```

---

## Next Steps

- Read: `OPERATIONAL_RUNBOOK.md` — 24/7 monitoring procedures
- Read: `MONITORING_CHECKLIST.md` — what metrics to watch
- Read: `ROLLBACK_PLAN.md` — emergency procedures

**Deployment complete. Monitor for 48 hours before enabling real trading.**

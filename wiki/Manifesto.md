# Architectural Manifesto — Pecunator

> Living document that defines the philosophy, architecture and operational guidelines of the project.  
> Every technical decision is traceable to the principles established here.  
> Last update: 2026-05-04

---

## 1. Project Vision

Pecunator is an algorithmic financial trading hub designed for an individual trader. Its objective is to compound profit through repeated cycles of trading, yield farming and portfolio management, with full control over the decision logic and traceability of each operation.

It is not an exchange. It is not a background. It is a **personal financial workstation** that combines automation, analysis and human oversight.

### Founding Principles

| # | Principle | Description |
|---|--------|-------------|
| 1 | **Compose profit** | The goal is compound growth, not one-time bets |
| 2 | **Contain losses** | Losses are not prohibited; are contained, audited and learned with strict controls |
| 3 | **Operational sovereignty** | The trader maintains full control over funds, strategies and data |
| 4 | **Full traceability** | Every operation, decision and change is recorded and auditable |

---

## 2. The 4 Pillar Model

### Pillar I — Binance CEX (Execution and Custody)

**Role:** Central provider of order execution, asset custody, real-time market data and trading histories.

**Binance is infrastructure, not product.** Pecunator consumes the Binance API as a service.

**What we delegate to you:**
- Order execution (Spot, Futures, Margin)
- Custody of funds (wallets)
- Market data (tickers, orderbook, trades via WebSocket)
- Financial products (Earn, Loans, Staking)
- Subaccount management
- Trade and transaction histories

**What we DO NOT delegate to you:**
- Trading decisions
- Portfolio analysis
- Long term persistence
- Operational policies

### Pillar II — GitHub Repository (Knowledge and Doctrine)

**Role:** Versioned knowledge management system, source code, operational policies and institutional memory.

**The repo is not just code; is the mind of the project.**

Contains:
- Source code (runtime, bots, tools, scripts, desktop shell)
- Architectural documentation (`docs/`)
- Security policies (`docs/policies/`)
- Context guidelines for the LLM (`docs/context/`)
- Operational tasks (`tools/ops-protocols/tasks/`)
- Changelog and historical decisions

**Branch convention:**
- `main` — stable branch, always deployable
- Feature/fix branches by PR

### Pillar III — Flutter Desktop Shell (Visualization, DB, Simulations)

**Role:** Consolidated visual dashboard, local backup database and platform for simulations and statistical analysis.

**Triple function:**

| Function | Description |
|---------|-------------|
| **Bot Hub** | Simultaneous visualization of N bots with status, P&L and metrics |
| **Backup DB** | Local SQLite with snapshots of balances, trades, equity and states |
| **Analysis laboratory** | Backtests and hypotheses without consuming Binance rate limits |

**Critical boundaries:**
- Credentials **NEVER** in Dart — always in the Python vault
- Flutter talks **only** to the runtime via HTTP localhost
- The UI is **not** a source of truth for balance sheets or positions

### Pillar IV — IDE + LLM (Operational Brain)

**Role:** Cognitive layer for analysis, orchestration of complex tasks, generation of reports and execution of operational protocols.

**The LLM proposes, the code disposes.**

**What the LLM does:**
- Analyze reports and cross-reference data from multiple sources
- Execute operational tasks (briefings, audits, health checks)
- Generate code and scripts according to repo guidelines
- Detect patterns and propose actions
- Formalize knowledge in `.md` documents

**What the LLM DOES NOT do:**
- Execute trades without explicit approval
- Directly access private keys or secrets
- Make final funding decisions
- Replace deterministic bot logic

**Known limitations:** non-deterministic, amnesia between sessions, latency 5–30 s. Mitigation: Tasks encode reproducible protocols; Guidelines in `docs/context/` provide persistent context.

---

## 3. Decision Hierarchy

| Level | Agent | Responsibility | Horizon |
|-------|--------|----------------|-----------|
| 1 | **Human operator** | Strategy, what to do, when to scale | Days/Weeks |
| 2 | **LLM (IDE)** | Analysis, briefings, action proposals | Minutes/Hours |
| 3 | **Python Scripts** | Deterministic execution approved | Seconds |
| 4 | **Autonomous bots** | Continuous operation with fixed parameters | Continuous cycle |
| 5 | **Binance API** | Execution of orders, custody | Milliseconds |
| 6 | **Flutter Shell** | Visualization, local persistence | Real time |

Each level only interacts with adjacent ones.

---

## 4. Security and Credentials Policy

### Secret Storage

- **Binance API keys:** Vault encrypted in `runtime/data/` (AES via `cryptography`). Never in plain text, never in unencrypted environment variables in production.
- **Private keys Web3** (future): local `.env` with `chmod 600` + encrypted vault. Never in repo.
- **GitHub tokens:** Credential manager of the operating system.

### Least Privilege Principle

- Bot API keys: trading permissions only, **NEVER withdraw**
- Subaccounts: each bot operates with its own IP-restricted key
- The LLM only invokes scripts; scripts read secrets from vault

### Rotation and Revocation

- API keys are rotated **every 90 days** at least
- If compromise is suspected: **IMMEDIATELY revoke** from Binance prior to any technical diagnosis

### Log Sanitization

- All log output goes through `security_util.sanitize_log_message()`
- Signature patterns, API keys and secrets are written automatically

---

## 5. Data and Persistence Policy

### Sources of Truth

| Data | Source of truth | Backup |
|------|-------|----------|
| Current balances | Binance API (User Data Stream) | Flutter SQLite |
| Open orders | Binance API (User Data Stream) | Flutter SQLite |
| Trade history | Binance API (`/myTrades`) | CSV local logs |
| Earn/loan rates | Binance API + monitors | CSV logs in repo |
| Bot Status | Runtime StateStore (memory) | Flutter SQLite |
| Equity metrics | Runtime EquityRollingWindow | Flutter SQLite |
| Policies and doctrine | GitHub repo (`docs/`) | — (the repo IS the truth) |
| Bot Configuration | `runtime/core/config_manager.py` | Encrypted Vault |

### Formats

| Type | Format |
|------|---------|
| Human reports | `.txt` or `.md` |
| Tabular data | `.csv` (parseable with pandas) |
| Structured data | `.json` or SQLite |
| Policies and documentation | `.md` (versioned in git) |

---

## 6. Trading Philosophy

### Time Horizon

Pecunator is **NOT** an HFT or scalping system. Approach:

- **Portfolio management** — horizon from hours to days
- **Yield optimization** — horizon from days to weeks
- **Arbitration** — only if the window is comfortable (seconds to minutes)
- **Audit and rebalancing** — on demand or periodic

### Risk Management

| Control | Detail |
|---------|---------|
| **Maximum concentration** | No individual token should exceed 25% of the portfolio without documented justification |
| **Minimum health factor** | Loans with HF < 1.5 activate alert; HF < 1.3 activates emergency protocol |
| **Kill switch** | Red button (`/api/v1/ops/red_button`) stops all bots immediately |
| **Circuit breaker** | `ApiFuse` automatically cuts REST access if API weight exceeds thresholds |

### Loss Treatment

Losses are unavoidable events, not system failures:

1. **Containment** — Limit loss via stop-loss or manual closing
2. **Recording** — Document what happened, when and why
3. **Analysis** — Strategy, execution or market error?
4. **Adaptation** — Adjust parameters or strategy if applicable
5. **Continued** — Continue operating with updated controls

---

## 7. Expansion Roadmap

### Current Phase — CEX Stabilization

- [x] Modular runtime with BotCoordinator and WeightGovernor
- [x] Flutter desktop shell with bot dashboard
- [x] Encrypted Vault for credentials
- [x] Earn/loan rates monitors
- [x] Audit system and reports
- [x] Operational tasks in IDE
- [ ] SQLite DB in Flutter for local persistence
- [ ] Binance subaccounts for bot isolation

### Next Phase — CEX Diversification

- [ ] Second CEX via `ccxt` (candidates: Bybit, OKX)
- [ ] Gateway abstraction for multi-exchange
- [ ] Cross-exchange rate comparator

### Future Phase — Web3 Multichain

- [ ] `web3_gateway.py` — on-chain connector for EVM
- [ ] DEX quotes via aggregators (1inch, 0x)
- [ ] Spread detector CEX vs DEX
- [ ] Lending on-chain (Aave V3)

---

## 8. Glossary

| Term | Definition in context of Pecunator |
|---------|-------------------------------------|
| **Hub** | The central runtime that orchestrates bots, APIs and state |
| **Gateway** | Connector to a specific exchange or blockchain |
| **Task** | Operational protocol executable by the LLM |
| **Fuse** | Circuit breaker that cuts off access due to excessive use |
| **Governor** | API weight/rate limit regulator |
| **Coordinator** | Bot Lifecycle Orchestrator |
| **Shell** | The Flutter desktop frontend |
| **Vault** | Encrypted credential storage |
| **Doctrine** | Policies and principles that govern the operation |
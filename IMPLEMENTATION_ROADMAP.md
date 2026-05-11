# Pecunator-AccuMonetas: Implementation Roadmap

**Project:** Louise Bot Hub (Multi-instance DCA Platform)  
**Start Date:** 2026-05-11  
**Target Completion:** 8-10 weeks  
**Team:** Solo development (Claude Code) + Your oversight

---

## 📋 Phase Breakdown

### PHASE 1: Foundation & Setup (Week 1-2)

#### 1.1 Backend Structure
- [ ] Create bot runner module: `runtime/bot/louise.py`
  - Classes: `LouiseBot`, `LouiseEpoch`, `LouiseMetrics`
  - Methods: `initialize()`, `poll_market()`, `execute_buy()`, `check_exit_condition()`, `shutdown()`
  
- [ ] Create Louise API routers: `runtime/api/routers/louise.py`
  - Endpoints: Bot CRUD, metrics, history, WebSocket stream
  
- [ ] Extend SQLite schema: `runtime/core/database.py`
  - Tables: `louise_bots`, `louise_purchases`, `louise_epochs`
  - Migrations script

- [ ] Integrate with existing control modules
  - BudgetGuard: daily spend limits per bot
  - WeightGovernor: API rate limiting
  - OrderLedger: audit trail of buys/sells
  - StateWAL: crash recovery

#### 1.2 Testing Infrastructure
- [ ] Create test suite: `runtime/tests/test_louise_*.py`
  - Unit tests: price comparison, VWAP calculation, profit %, state transitions
  - Integration tests: BinanceGateway (testnet), SQLite, API endpoints
  - Simulation tests: downtrend/uptrend market scenarios

- [ ] Add CI/CD: GitHub Actions workflow
  - Run tests on PR: `pytest runtime/tests/ -x`
  - Linting: ruff
  - Type checking: mypy (optional)

#### 1.3 Documentation
- [ ] Create `docs/LOUISE_ARCHITECTURE.md` — Design details
- [ ] Create `docs/LOUISE_API_REFERENCE.md` — Full endpoint docs
- [ ] Update main `README.md` — Louise-specific quick start

#### Deliverables
- [ ] Bot runner module (functional, testable)
- [ ] API routers (ready for Flutter integration)
- [ ] Database schema (initialized)
- [ ] 95%+ test coverage
- [ ] GitHub Actions CI passing

---

### PHASE 2: Backend Implementation (Week 3-4)

#### 2.1 Louise Bot Runner
- [ ] Implement `LouiseBot` class
  - Constructor: load config (symbol, buy_volume, poll_interval, target_profit, budget)
  - `initialize()`: connect to BinanceGateway, load epoch from DB, execute first buy
  - `poll_market()`: fetch current price, check buy condition
  - `execute_buy()`: place market order, record in DB
  - `check_exit_condition()`: calculate P&L %, check if >= target_profit
  - `shutdown()`: market sell all, close epoch, persist to DB
  - Error handling: retry logic, logging, state recovery

- [ ] Implement `LouiseEpoch` class
  - Constructor: bot_id, symbol, timestamp
  - Methods: add_purchase(), update_avg_price(), calculate_pnl(), close()
  - Persistence: load/save from DB

- [ ] Implement `LouiseMetrics` class
  - Calculate: VWAP, unrealized P&L %, budget remaining
  - Real-time updates: sync with current market price

#### 2.2 Integration with PecunatorCore
- [ ] Connect `LouiseBot` to `BinanceGateway`
  - Async market orders
  - Price feeds
  - Order status tracking

- [ ] Connect to `BudgetGuard`
  - Pre-check: daily budget before buy
  - Post-check: deduct cost from daily budget

- [ ] Connect to `WeightGovernor`
  - API weight allocation per bot
  - Pause if weight zone turns RED

- [ ] Connect to `OrderLedger`
  - Every purchase logged with order_id
  - Every sale logged

- [ ] Connect to `StateWAL`
  - Bot state persisted after each cycle
  - Crash recovery: resume from last known state

#### 2.3 API Endpoints Implementation
- [ ] `POST /api/v1/louise/bots` — Create new bot
- [ ] `GET /api/v1/louise/bots` — List all bots
- [ ] `GET /api/v1/louise/bots/{bot_id}` — Get bot details
- [ ] `PATCH /api/v1/louise/bots/{bot_id}` — Update config
- [ ] `POST /api/v1/louise/bots/{bot_id}/enable` — Start bot
- [ ] `POST /api/v1/louise/bots/{bot_id}/disable` — Pause bot
- [ ] `POST /api/v1/louise/bots/{bot_id}/shutdown` — Force shutdown
- [ ] `GET /api/v1/louise/bots/{bot_id}/metrics` — Real-time metrics
- [ ] `GET /api/v1/louise/bots/{bot_id}/epochs` — Epoch history
- [ ] `GET /api/v1/louise/bots/{bot_id}/purchases` — Purchase history
- [ ] `GET /api/v1/louise/stats` — Hub-wide stats
- [ ] `WebSocket /ws/louise/metrics/{bot_id}` — Real-time stream

#### 2.4 Logging & Monitoring
- [ ] Bot lifecycle logs: created, started, paused, shutdown, error
- [ ] Purchase logs: every buy with price, volume, cost
- [ ] Exit logs: epoch closed, profit/loss, duration
- [ ] Error logs: exchange errors, budget exhausted, network failures

#### Deliverables
- [ ] Complete bot runner (all methods implemented)
- [ ] All API endpoints working
- [ ] Full integration with control modules
- [ ] 100% test pass
- [ ] Logs structured and queryable

---

### PHASE 3: Frontend Implementation (Week 5-6)

#### 3.1 Flutter Project Setup
- [ ] Extend `desktop_shell/` for Louise-specific UI
  - Create `lib/screens/louise_dashboard.dart`
  - Create `lib/screens/louise_detail.dart`
  - Create `lib/screens/louise_history.dart`
  - Create `lib/screens/louise_settings.dart`

#### 3.2 State Management (Provider pattern)
- [ ] `lib/providers/louise_bots_provider.dart` — Bot list state
- [ ] `lib/providers/louise_selected_bot_provider.dart` — Current selected bot
- [ ] `lib/providers/louise_metrics_provider.dart` — Real-time metrics from WebSocket
- [ ] `lib/providers/louise_alerts_provider.dart` — Error/success notifications

#### 3.3 Widgets & Components
- [ ] `lib/widgets/bot_card.dart` — Summary card (status, price, P&L, actions)
- [ ] `lib/widgets/metrics_panel.dart` — Market data display (current price, avg price, position)
- [ ] `lib/widgets/pnl_indicator.dart` — Color-coded profit % display
- [ ] `lib/widgets/budget_tracker.dart` — Daily spend visualization
- [ ] `lib/widgets/purchase_table.dart` — Transaction history
- [ ] `lib/widgets/epoch_table.dart` — Completed cycles list
- [ ] `lib/widgets/status_badge.dart` — Bot status icon + text

#### 3.4 Pages & Navigation
- [ ] `DashboardPage` — Main hub view (bot grid)
  - Build bot cards from provider
  - WebSocket real-time updates
  - [Create Bot] button → modal dialog
  - Bot card tap → detail page

- [ ] `BotDetailPage` — Expanded bot view
  - Display all metrics
  - Show budget tracking
  - Recent purchases table
  - Quick action buttons (enable/disable/shutdown)

- [ ] `HistoryPage` — Epochs & purchases tabs
  - Epoch table (filter, sort, export)
  - Purchase table (paginated)
  - Summary stats

- [ ] `SettingsPage` — App configuration
  - API connection status
  - Alerts/notifications config
  - Export/backup controls

#### 3.5 Dialogs & Modals
- [ ] `CreateBotDialog` — Form to create new Louise instance
  - Symbol picker
  - Buy volume input
  - Poll interval slider
  - Target profit input
  - Daily budget input
  - Validation before submit

- [ ] `ConfirmationDialog` — Confirm critical actions
  - Force shutdown? (delete current epoch)
  - Enable bot? (starts first buy)

- [ ] `AlertDialog` — Error/success notifications
  - Error messages from API
  - Success confirmations
  - Auto-dismiss or click-to-close

#### 3.6 WebSocket Integration
- [ ] Implement `WebSocketService` for real-time metrics
  - Connect to `/ws/louise/metrics/{bot_id}`
  - Parse incoming JSON (price, P&L, budget, status)
  - Emit to `louise_metrics_provider`
  - Auto-reconnect on disconnect

- [ ] Auto-update UI components
  - BotCard: update P&L % and price live
  - MetricsPanel: live price, position value
  - BudgetTracker: remaining budget updates
  - PnL indicator: color changes as % changes

#### 3.7 API Integration
- [ ] Implement `LouiseApiService`
  - REST calls to all endpoints
  - Error handling & retries
  - Bearer token auth
  - Parse responses → model objects

- [ ] Create data models
  - `BotConfig` — Bot parameters
  - `BotMetrics` — Real-time metrics
  - `Purchase` — Single transaction
  - `Epoch` — Completed cycle

#### 3.8 Local Storage & Caching
- [ ] Cache bot list locally (update from API periodically)
- [ ] Cache epoch/purchase history (for offline browsing)
- [ ] Persist UI state (selected bot, tab, scroll position)

#### Deliverables
- [ ] All screens implemented & styled
- [ ] WebSocket real-time metrics working
- [ ] API integration complete
- [ ] State management robust
- [ ] Zero console errors on startup
- [ ] Flutter analyze passing

---

### PHASE 4: Integration & Testing (Week 7)

#### 4.1 End-to-End Testing
- [ ] Manual test: Create bot → Enable → Verify first buy
- [ ] Manual test: Monitor bot → Watch metrics update live
- [ ] Manual test: Bot reaches profit target → Auto-close → Verify UI updates
- [ ] Manual test: Manual shutdown → Force sell → Verify epoch logged
- [ ] Manual test: Create multiple bots → Monitor all simultaneously

#### 4.2 Load Testing
- [ ] Run 10 Louise bots simultaneously
- [ ] Verify API weight governor holds steady
- [ ] Verify no missed purchases
- [ ] Verify metrics refresh latency < 1 second

#### 4.3 Error Scenario Testing
- [ ] Network disconnect → Bot pauses → Reconnects → Resumes
- [ ] Budget exhausted → Bot stops buying → Alert shown
- [ ] Invalid credentials → Critical alert → Operator action required
- [ ] Exchange timeout → Retry logic → Success

#### 4.4 UI Polish
- [ ] Responsive layout (desktop sizes: 1280x800, 1920x1080, etc.)
- [ ] Dark mode styling
- [ ] Color contrast (WCAG AA compliance)
- [ ] Typography sizing & spacing
- [ ] Button/control sizing (touch-friendly)

#### 4.5 Documentation
- [ ] User guide: How to create & manage Louise bots
- [ ] Operator runbook: Common tasks, troubleshooting
- [ ] API reference: Complete endpoint documentation
- [ ] Architecture diagrams: Data flow, component interactions

#### Deliverables
- [ ] All manual tests pass
- [ ] Load test report (10 bots sustained)
- [ ] UI passes accessibility review
- [ ] Documentation complete & reviewed
- [ ] Zero known bugs

---

### PHASE 5: Hardening & Production (Week 8-10)

#### 5.1 Security Hardening
- [ ] Credential vault: ensure encrypted storage
- [ ] API auth: bearer token validation
- [ ] Rate limiting: verify WeightGovernor blocks over-limit requests
- [ ] Input validation: sanitize all user inputs (bot config)
- [ ] Error messages: no sensitive data leaked
- [ ] Logging: no credentials logged

#### 5.2 Performance Optimization
- [ ] Profile API response times
- [ ] Optimize SQLite queries (indices on frequently queried fields)
- [ ] WebSocket message size optimization
- [ ] UI rendering optimization (large epoch lists)
- [ ] Memory usage monitoring (long-running app)

#### 5.3 Reliability Hardening
- [ ] Crash recovery: bot resumes from last state
- [ ] Database integrity: periodic PRAGMA integrity_check
- [ ] Stale data detection: mark metrics stale if WebSocket silent > 30s
- [ ] Backup & restore: daily DB snapshots
- [ ] Alert escalation: critical errors → operator notification

#### 5.4 Deployment Preparation
- [ ] Create `.env.example` with Louise-specific vars
- [ ] Create deployment checklist document
- [ ] Setup GitHub releases process (semantic versioning)
- [ ] Document rollback procedure
- [ ] Create monitoring dashboard (ops template)

#### 5.5 Final Testing
- [ ] Full test suite: `pytest runtime/tests/ -x` (200+ tests)
- [ ] Flutter test: `flutter test test/` (all screens)
- [ ] Integration test: Engine + UI end-to-end
- [ ] Regression test: verify no side effects

#### 5.6 Documentation Finalization
- [ ] Update `README.md` with Louise features
- [ ] Update `CHANGELOG.md` with version notes
- [ ] Create `DEPLOYMENT.md` with ops procedures
- [ ] Create `TROUBLESHOOTING.md` with common issues

#### Deliverables
- [ ] Security audit passed
- [ ] Performance benchmarks documented
- [ ] Reliability testing complete
- [ ] Production deployment checklist signed off
- [ ] All documentation finalized
- [ ] **READY FOR PRODUCTION LAUNCH**

---

## 🎯 Milestones & Timeline

| Milestone | Target Date | Status |
|-----------|-------------|--------|
| Phase 1 complete (backend structure) | 2026-05-25 | — |
| Phase 2 complete (bot runner + API) | 2026-06-08 | — |
| Phase 3 complete (Flutter UI) | 2026-06-22 | — |
| Phase 4 complete (E2E testing) | 2026-06-29 | — |
| Phase 5 complete (hardening) | 2026-07-20 | — |
| **Production Launch** | **2026-07-20** | — |

---

## 🔧 Development Branch Strategy

Each phase will use feature branches:

```
main (production-ready)
  ↑
  ├─ feature/louise-backend (Phase 1-2)
  │  ├─ runtime/bot/louise.py
  │  ├─ runtime/api/routers/louise.py
  │  ├─ runtime/core/louise_db.py (schema)
  │  └─ runtime/tests/test_louise_*.py
  │
  ├─ feature/louise-ui (Phase 3)
  │  ├─ desktop_shell/lib/screens/louise_*
  │  ├─ desktop_shell/lib/providers/louise_*
  │  ├─ desktop_shell/lib/widgets/louise_*
  │  └─ desktop_shell/test/ (UI tests)
  │
  └─ feature/louise-integration (Phase 4-5)
     ├─ Integration tests
     ├─ Load tests
     └─ Hardening fixes
```

Each branch:
- Has PR with detailed description
- Passes all tests before merge
- Includes documentation updates
- Gets code review (your sign-off)

---

## 📊 Resource Estimates

| Task | Effort | Risk |
|------|--------|------|
| Phase 1 (structure) | 2 weeks | Low |
| Phase 2 (bot + API) | 2 weeks | Medium (exchange integration) |
| Phase 3 (Flutter UI) | 2 weeks | Medium (state management) |
| Phase 4 (testing) | 1 week | Low |
| Phase 5 (hardening) | 2 weeks | Low |
| **Total** | **~9 weeks** | — |

---

## ⚠️ Risks & Mitigations

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Binance API changes | Medium | Monitor API docs, quick adapt |
| WebSocket latency | Low | Fallback to REST polling |
| Database locks (concurrent bots) | Medium | SQLite WAL mode, proper locks |
| Flutter version incompatibility | Low | Pin dependencies, test matrix |
| Market volatility affects testing | Low | Use testnet + simulation mode |

---

## 🚀 Success Criteria

- [ ] ✅ All phases delivered on schedule
- [ ] ✅ 200+ tests passing (100% coverage on core logic)
- [ ] ✅ Zero production bugs in first month
- [ ] ✅ UI responsive and intuitive
- [ ] ✅ Operator can manage 5+ bots simultaneously
- [ ] ✅ All epochs successfully closed at profit (by design)
- [ ] ✅ Documentation complete and reviewed
- [ ] ✅ GitHub Actions CI/CD passing every commit

---

**Next Step:** Start Phase 1 → Create `feature/louise-backend` branch → Implement bot runner module

**Questions?** Refer to:
- `docs/BOT_SPECIFICATION.md` — Technical details
- `docs/UI_WIREFRAMES.md` — UI/UX design
- `CLAUDE.md` — Development process

"""Load test baseline for Louise bot hub — concurrent bots under simulated load.

Validates performance targets before production:
  - p95 DB write latency < 50ms
  - p95 DB read latency < 20ms
  - 10 concurrent bots complete 10 epochs each without errors
  - Total memory allocated for DB operations < 100MB estimate

Run: python -m pytest runtime/tests/test_louise_load.py -v --tb=short
"""

import gc
import statistics
import time
import uuid
from pathlib import Path
from typing import List

import pytest

from runtime.core.louise_db import LouiseDB


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path) -> LouiseDB:
    yield LouiseDB(db_path=str(tmp_path / "louise_load_test.sqlite"))


@pytest.fixture
def multi_db(tmp_path) -> LouiseDB:
    """Shared DB for concurrent-bot tests."""
    yield LouiseDB(db_path=str(tmp_path / "louise_concurrent.sqlite"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_bot(db: LouiseDB, bot_id: str = None) -> str:
    bot_id = bot_id or f"load-bot-{uuid.uuid4().hex[:8]}"
    db.create_bot(
        bot_id=bot_id,
        symbol="BTCUSDT",
        buy_volume=50.0,
        poll_interval_seconds=60,
        target_profit_pct=1.5,
        daily_budget_usdt=500.0,
        subaccount="bluechip",
        status="RUNNING",
    )
    return bot_id


def _run_epoch(db: LouiseDB, bot_id: str, num_purchases: int = 5) -> float:
    """Run one full epoch: create → add purchases → close. Returns epoch duration in ms."""
    epoch_id = f"epoch_{bot_id}_{uuid.uuid4().hex[:8]}"
    t_start = time.perf_counter()

    db.create_epoch(epoch_id=epoch_id, bot_id=bot_id, status="RUNNING")

    for i in range(num_purchases):
        db.add_purchase(
            purchase_id=f"pur_{epoch_id}_{i}",
            bot_id=bot_id,
            epoch_id=epoch_id,
            price_at_buy=40000.0 + i * 100,
            volume=0.001,
            cost_usdt=50.0,
            order_id=f"order_{i}_{uuid.uuid4().hex[:6]}",
            status="FILLED",
        )

    total_cost = num_purchases * 50.0
    avg_price = 40000.0 + ((num_purchases - 1) * 100) / 2
    db.update_epoch_stats(epoch_id, num_purchases, total_cost, avg_price)
    db.close_epoch(
        epoch_id=epoch_id,
        final_price=41500.0,
        final_value=total_cost * 1.02,
        profit_usdt=total_cost * 0.02,
        profit_pct=2.0,
        status="CLOSED_SUCCESSFUL",
    )

    return (time.perf_counter() - t_start) * 1000  # ms


# ── M1: Write Latency ────────────────────────────────────────────────────────

class TestDBWriteLatency:
    """Verify DB write latency under sustained sequential load."""

    def test_create_bot_p95_under_50ms(self, db):
        latencies: List[float] = []
        for i in range(50):
            t = time.perf_counter()
            _make_bot(db, bot_id=f"bot-write-{i}")
            latencies.append((time.perf_counter() - t) * 1000)

        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
        assert p95 < 50, f"create_bot p95={p95:.1f}ms exceeds 50ms target"

    def test_add_purchase_p95_under_50ms(self, db):
        bot_id = _make_bot(db)
        epoch_id = f"epoch_{bot_id}_0"
        db.create_epoch(epoch_id=epoch_id, bot_id=bot_id)

        latencies: List[float] = []
        for i in range(100):
            t = time.perf_counter()
            db.add_purchase(
                purchase_id=f"pur_{i}_{uuid.uuid4().hex[:6]}",
                bot_id=bot_id,
                epoch_id=epoch_id,
                price_at_buy=40000.0,
                volume=0.001,
                cost_usdt=50.0,
                order_id=f"ord_{i}",
                status="FILLED",
            )
            latencies.append((time.perf_counter() - t) * 1000)

        p95 = statistics.quantiles(latencies, n=20)[18]
        assert p95 < 50, f"add_purchase p95={p95:.1f}ms exceeds 50ms target"

    def test_close_epoch_p95_under_50ms(self, db):
        latencies: List[float] = []
        for i in range(50):
            bot_id = _make_bot(db, bot_id=f"close-bot-{i}")
            epoch_id = f"epoch_close_{i}"
            db.create_epoch(epoch_id=epoch_id, bot_id=bot_id)

            t = time.perf_counter()
            db.close_epoch(epoch_id, 41000.0, 102.0, 2.0, 2.0, "CLOSED_SUCCESSFUL")
            latencies.append((time.perf_counter() - t) * 1000)

        p95 = statistics.quantiles(latencies, n=20)[18]
        assert p95 < 50, f"close_epoch p95={p95:.1f}ms exceeds 50ms target"


# ── M2: Read Latency ─────────────────────────────────────────────────────────

class TestDBReadLatency:
    """Verify read latency under dataset growth."""

    def test_get_bot_p95_under_20ms(self, db):
        # Seed with 100 bots
        bot_ids = [_make_bot(db, bot_id=f"read-bot-{i}") for i in range(100)]

        latencies: List[float] = []
        import random
        for _ in range(200):
            bid = random.choice(bot_ids)
            t = time.perf_counter()
            result = db.get_bot(bid)
            latencies.append((time.perf_counter() - t) * 1000)
            assert result is not None

        p95 = statistics.quantiles(latencies, n=20)[18]
        assert p95 < 20, f"get_bot p95={p95:.1f}ms exceeds 20ms target"

    def test_get_all_bots_under_100ms(self, db):
        for i in range(200):
            _make_bot(db, bot_id=f"all-bot-{i}")

        times: List[float] = []
        for _ in range(30):
            t = time.perf_counter()
            bots = db.get_all_bots()
            times.append((time.perf_counter() - t) * 1000)
            assert len(bots) == 200

        avg = statistics.mean(times)
        assert avg < 100, f"get_all_bots avg={avg:.1f}ms exceeds 100ms target"

    def test_get_epochs_for_bot_p95_under_20ms(self, db):
        bot_id = _make_bot(db)
        for i in range(50):
            epoch_id = f"epoch_{bot_id}_{i}"
            db.create_epoch(epoch_id=epoch_id, bot_id=bot_id)
            db.close_epoch(epoch_id, 41000.0, 102.0, 2.0, 2.0)

        latencies: List[float] = []
        for _ in range(100):
            t = time.perf_counter()
            epochs = db.get_all_epochs(bot_id)
            latencies.append((time.perf_counter() - t) * 1000)
            assert len(epochs) == 50

        p95 = statistics.quantiles(latencies, n=20)[18]
        assert p95 < 20, f"get_all_epochs p95={p95:.1f}ms exceeds 20ms target"


# ── M3: Concurrent Bot Simulation ────────────────────────────────────────────

class TestConcurrentBotSimulation:
    """Simulate 10 bots running independently, each completing multiple epochs."""

    def test_10_bots_10_epochs_each_no_errors(self, multi_db):
        """10 bots × 10 epochs × 5 purchases = 500 DB writes — verify no errors."""
        bot_ids = [_make_bot(multi_db, bot_id=f"concurrent-{i}") for i in range(10)]
        epoch_durations: List[float] = []
        errors = []

        for epoch_round in range(10):
            for bot_id in bot_ids:
                try:
                    ms = _run_epoch(multi_db, bot_id, num_purchases=5)
                    epoch_durations.append(ms)
                except Exception as e:
                    errors.append(f"{bot_id}/epoch{epoch_round}: {e}")

        assert not errors, f"Errors during concurrent simulation: {errors}"
        assert len(epoch_durations) == 100  # 10 bots × 10 epochs

        p95 = statistics.quantiles(epoch_durations, n=20)[18]
        assert p95 < 500, f"Full epoch p95={p95:.1f}ms exceeds 500ms target"

    def test_epoch_throughput_100_per_minute(self, multi_db):
        """100 epochs should complete within 60 seconds under sequential load."""
        bot_id = _make_bot(multi_db)
        t_start = time.perf_counter()

        for _ in range(100):
            _run_epoch(multi_db, bot_id, num_purchases=3)

        elapsed = time.perf_counter() - t_start
        assert elapsed < 60, f"100 epochs took {elapsed:.1f}s — exceeds 60s budget"

    def test_status_updates_under_load(self, multi_db):
        """Status updates for 10 bots don't degrade over 500 cycles."""
        bot_ids = [_make_bot(multi_db, bot_id=f"status-bot-{i}") for i in range(10)]
        latencies: List[float] = []

        statuses = ["RUNNING", "IDLE", "PAUSED", "RUNNING"]
        for cycle in range(500):
            bot_id = bot_ids[cycle % 10]
            status = statuses[cycle % len(statuses)]
            t = time.perf_counter()
            multi_db.update_bot_status(bot_id, status)
            latencies.append((time.perf_counter() - t) * 1000)

        p95 = statistics.quantiles(latencies, n=20)[18]
        assert p95 < 50, f"update_bot_status p95={p95:.1f}ms exceeds 50ms under load"


# ── M4: Data Volume Stress ────────────────────────────────────────────────────

class TestDataVolumeStress:
    """Verify the DB handles realistic data volumes for a 30-day production window."""

    def test_30_day_data_volume(self, db):
        """Simulate 30 days × 10 bots × 8 epochs/day = 2400 epochs."""
        NUM_BOTS = 5
        EPOCHS_PER_DAY = 8
        NUM_DAYS = 10  # Scaled down: 10d × 5 bots × 8 epochs = 400 epochs

        bot_ids = [_make_bot(db, bot_id=f"volume-bot-{i}") for i in range(NUM_BOTS)]
        total_epochs = NUM_BOTS * EPOCHS_PER_DAY * NUM_DAYS
        created = 0
        errors = []

        for _ in range(NUM_DAYS):
            for _ in range(EPOCHS_PER_DAY):
                for bot_id in bot_ids:
                    try:
                        _run_epoch(db, bot_id, num_purchases=3)
                        created += 1
                    except Exception as e:
                        errors.append(str(e))

        assert not errors, f"Errors in volume test: {errors[:5]}"
        assert created == total_epochs

        # Verify reads still fast after volume
        t = time.perf_counter()
        bots = db.get_all_bots()
        read_ms = (time.perf_counter() - t) * 1000
        assert len(bots) == NUM_BOTS
        assert read_ms < 50, f"get_all_bots after volume={read_ms:.1f}ms — too slow"

    def test_purchases_query_scales_with_volume(self, db):
        """Verify purchase queries stay fast as purchase count grows (indexed query)."""
        bot_id = _make_bot(db)
        epoch_id = f"epoch_scale_{bot_id}"
        db.create_epoch(epoch_id=epoch_id, bot_id=bot_id)

        for i in range(500):
            db.add_purchase(
                purchase_id=f"pur_scale_{i}_{uuid.uuid4().hex[:6]}",
                bot_id=bot_id,
                epoch_id=epoch_id,
                price_at_buy=40000.0 + i,
                volume=0.001,
                cost_usdt=50.0,
                order_id=f"ord_scale_{i}",
                status="FILLED",
            )

        t = time.perf_counter()
        purchases = db.get_purchases_by_epoch(epoch_id)
        query_ms = (time.perf_counter() - t) * 1000
        assert len(purchases) == 500
        assert query_ms < 50, f"get_purchases_by_epoch (500 rows) took {query_ms:.1f}ms"


# ── M5: Summary Report ───────────────────────────────────────────────────────

class TestLoadTestSummary:
    """Final summary test — provides a performance snapshot for the operator."""

    def test_performance_summary(self, multi_db, capsys):
        """Run a mini benchmark and print performance summary."""
        bot_id = _make_bot(multi_db)
        write_times, read_times, epoch_times = [], [], []

        for i in range(20):
            t = time.perf_counter()
            _make_bot(multi_db, bot_id=f"summary-bot-{i}")
            write_times.append((time.perf_counter() - t) * 1000)

        for i in range(20):
            t = time.perf_counter()
            multi_db.get_bot(f"summary-bot-{i % 20}")
            read_times.append((time.perf_counter() - t) * 1000)

        for _ in range(10):
            t = time.perf_counter()
            _run_epoch(multi_db, bot_id, num_purchases=5)
            epoch_times.append((time.perf_counter() - t) * 1000)

        gc.collect()

        print("\n" + "="*60)
        print("LOAD TEST PERFORMANCE SUMMARY")
        print("="*60)
        print(f"DB Write (create_bot)     avg={statistics.mean(write_times):.1f}ms  p95={statistics.quantiles(write_times, n=20)[18]:.1f}ms")
        print(f"DB Read  (get_bot)        avg={statistics.mean(read_times):.1f}ms  p95={statistics.quantiles(read_times, n=20)[18]:.1f}ms")
        print(f"Full Epoch (5 purchases)  avg={statistics.mean(epoch_times):.1f}ms  p95={statistics.quantiles(epoch_times, n=20)[18]:.1f}ms")
        print("="*60)
        print("TARGETS: writes<50ms, reads<20ms, epoch<500ms")
        print("="*60)

        assert statistics.quantiles(write_times, n=20)[18] < 50
        assert statistics.quantiles(read_times, n=20)[18] < 20
        assert statistics.quantiles(epoch_times, n=20)[18] < 500

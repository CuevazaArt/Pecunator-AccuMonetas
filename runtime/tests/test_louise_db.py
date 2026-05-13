import os
import pytest
from runtime.core.louise_db import LouiseDB

import uuid

@pytest.fixture
def test_db():
    # Use a unique temporary database for testing
    db_path = f"runtime/data/test_louise_hub_{uuid.uuid4().hex}.sqlite"
    db = LouiseDB(db_path=db_path)
    yield db

    # Cleanup after test
    import glob
    for f in glob.glob(f"{db_path}*"):
        try:
            os.remove(f)
        except OSError:
            pass


def test_create_and_get_bot(test_db):
    bot_id = "bot_001"
    test_db.create_bot(
        bot_id=bot_id,
        symbol="BTC/USDT",
        buy_volume=10.0,
        poll_interval_seconds=60,
        target_profit_pct=5.0,
        daily_budget_usdt=100.0
    )

    bot = test_db.get_bot(bot_id)
    assert bot is not None
    assert bot["bot_id"] == bot_id
    assert bot["symbol"] == "BTC/USDT"
    assert bot["status"] == "IDLE"

    all_bots = test_db.get_all_bots()
    assert len(all_bots) == 1
    assert all_bots[0]["bot_id"] == bot_id

def test_epoch_lifecycle(test_db):
    bot_id = "bot_002"
    epoch_id = "ep_001"

    test_db.create_bot(
        bot_id=bot_id,
        symbol="ETH/USDT",
        buy_volume=10.0,
        poll_interval_seconds=60,
        target_profit_pct=5.0,
        daily_budget_usdt=100.0
    )

    test_db.create_epoch(epoch_id, bot_id)

    active = test_db.get_active_epoch(bot_id)
    assert active is not None
    assert active["epoch_id"] == epoch_id
    assert active["status"] == "RUNNING"

    test_db.update_epoch_stats(epoch_id, num_purchases=2, total_cost=20.0, avg_buy_price=3000.0)

    test_db.close_epoch(
        epoch_id=epoch_id,
        final_price=3150.0,
        final_value=21.0,
        profit_usdt=1.0,
        profit_pct=5.0
    )

    active_after = test_db.get_active_epoch(bot_id)
    assert active_after is None

def test_add_purchase(test_db):
    bot_id = "bot_003"
    epoch_id = "ep_002"
    purchase_id = "pur_001"

    test_db.create_bot(bot_id, "SOL/USDT", 10.0, 60, 5.0, 100.0)
    test_db.create_epoch(epoch_id, bot_id)

    test_db.add_purchase(
        purchase_id=purchase_id,
        bot_id=bot_id,
        epoch_id=epoch_id,
        price_at_buy=100.0,
        volume=0.1,
        cost_usdt=10.0,
        order_id="123456",
        status="FILLED"
    )

    purchases = test_db.get_purchases_by_epoch(epoch_id)
    assert len(purchases) == 1
    assert purchases[0]["purchase_id"] == purchase_id
    assert purchases[0]["price_at_buy"] == 100.0

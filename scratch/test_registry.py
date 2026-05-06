"""Smoke test: registry + transfer service."""
import sys; sys.path.insert(0, ".")

from runtime.core.subaccount_registry import get_subaccount_registry
reg = get_subaccount_registry()
s = reg.summary()
print(f"Total accounts: {s['total_accounts']}")
print(f"Active bots: {s['active_bots']}")
for a in s["accounts"]:
    line = f"  {a['id']:12s} | {a['role']:10s} | bot={a['bot']:12s} | enabled={a['enabled']}"
    print(line)

print()
print("Bot accounts:")
for b in reg.list_bots():
    print(f"  {b.account_id} -> {b.email}")
    print(f"    {b.description}")
    print(f"    symbols={b.symbols}, max_equity={b.max_equity_usdt}")

print()
from runtime.core.transfer_service import TransferService
ts = TransferService("test", "test")
result = ts.fund_bot("dorothy", "USDT", "10", dry_run=True)
print(f"Dry-run fund dorothy: {result}")
result2 = ts.fund_bot("dorothy", "USDT", "9999", dry_run=True)
print(f"Dry-run over-limit:   {result2}")
result3 = ts.fund_bot("nonexistent", "USDT", "10", dry_run=True)
print(f"Dry-run bad bot:      {result3}")

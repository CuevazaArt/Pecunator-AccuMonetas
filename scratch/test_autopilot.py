"""Smoke test for AutoPilot system."""
import sys; sys.path.insert(0, ".")

from runtime.core.autopilot import AutoPilot, AutoTuner, AutoStager

# Test AutoTuner
tuner = AutoTuner()
result = tuner.compute_params(
    bot_type="dorothy",
    regime="TRENDING",
    volatility="HIGH",
    confidence=0.90,
    current_params={
        "profit_factor": 0.05,
        "stop_loss": 0.10,
        "margin_drop": 0.004,
        "interval_sec": 450,
        "quote_order_qty": 8.0,
    },
)
print("AutoTuner result:")
print(f"  Adjusted: {result['adjusted']}")
print(f"  Reason: {result['reason']}")
for adj in result.get("adjustments", []):
    print(f"    {adj}")
print()

# Test low confidence (should NOT adjust)
result2 = tuner.compute_params(
    bot_type="masha", regime="RANGING", volatility="NORMAL",
    confidence=0.40, current_params={},
)
print(f"Low confidence: adjusted={result2['adjusted']}")
print(f"  Reason: {result2['reason']}")
print()

# Test BREAKOUT with compressed volatility
result3 = tuner.compute_params(
    bot_type="thusnelda", regime="BREAKOUT", volatility="COMPRESSED",
    confidence=0.85, current_params={},
)
print("Breakout + Compressed:")
print(f"  Adjusted: {result3['adjusted']}")
for adj in result3.get("adjustments", []):
    print(f"    {adj}")
print()

# Test AutoPilot
pilot = AutoPilot(flutter_enabled=False, vmo_enabled=False)
print(f"AutoPilot status: {pilot.status()}")
print()
print("ALL OK")

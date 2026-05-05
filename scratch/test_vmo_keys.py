import asyncio
import os
from runtime.modules.vision.chart_capture import capture_chart
from runtime.modules.vision.chart_analyzer import classify_chart
from runtime.modules.vision.config import get_vmo_config

async def test_keys():
    print("--- VMO Key Verification ---")
    cfg = get_vmo_config()
    print(f"Chart-img key present: {bool(cfg.chart_img_api_key)}")
    print(f"Gemini key present: {bool(cfg.gemini_api_key)}")
    
    print("\n1. Testing chart-img capture...")
    res = await capture_chart("BTCUSDT", "4h", source="chart-img")
    if res.ok:
        print(f"SUCCESS: Captured {len(res.png)} bytes via {res.source}")
        
        print("\n2. Testing Gemini Vision analysis...")
        try:
            regime = await classify_chart(
                res.png, "BTCUSDT", "4h", 
                provider="gemini", 
                captured_at=res.captured_at,
                capture_source=res.source
            )
            print("SUCCESS: Gemini analysis complete")
            print(f"Regime: {regime.regime}")
            print(f"Confidence: {regime.confidence:.2f}")
            print(f"Bot: {regime.recommended_bot}")
            print(f"Notes: {regime.notes}")
        except Exception as e:
            print(f"FAILED: Gemini analysis error: {e}")
    else:
        print(f"FAILED: Capture error: {res.error}")

if __name__ == "__main__":
    asyncio.run(test_keys())

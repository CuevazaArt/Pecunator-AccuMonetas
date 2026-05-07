import sys
import traceback
import os

print("Starting debug run...")

# Set an environment variable so main.py doesn't start uvicorn blocking loop if we just want to see if it imports
os.environ["PECUNATOR_ENGINE_STUB"] = "0"  # Force run

try:
    from runtime.main import main
    main()
except Exception as e:
    print("\n" + "="*50)
    print("❌ ENGINE CRASHED! Here is the error:")
    print("="*50)
    traceback.print_exc()
    print("="*50)

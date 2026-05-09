import sys
import os
sys.path.append(os.getcwd())
from runtime.api.schemas import HubBotOut
from runtime.api.elphaba_service import ElphabaService

try:
    svc = ElphabaService()
    bots = svc.list_instances()
    if bots:
        row = bots[0]
        HubBotOut(**row)
        print("Success")
    else:
        print("No bots")
except Exception as e:
    import traceback
    traceback.print_exc()

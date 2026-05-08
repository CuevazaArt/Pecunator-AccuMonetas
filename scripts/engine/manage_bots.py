import httpx

print("--- STOPPING THUSNELDA BOTS ---")
try:
    bots = httpx.get('http://127.0.0.1:8000/api/v1/thusnelda/bots').json().get('bots', [])
    for b in bots:
        if b.get('running') or b.get('desired_running'):
            bot_id = b.get('bot_id')
            httpx.post(f'http://127.0.0.1:8000/api/v1/thusnelda/bots/{bot_id}/stop')
            print(f"Stopped Thusnelda: {bot_id} ({b.get('tag')})")
except Exception as e:
    print(f"Error stopping Thusnelda: {e}")

print("\n--- MASHA STATUS ---")
try:
    m_bots = httpx.get('http://127.0.0.1:8000/api/v1/masha/bots').json().get('bots', [])
    for b in m_bots:
        print(f"\nMasha: {b.get('tag')} (ID: {b.get('bot_id')}) - Running: {b.get('running')}")
        last_rep = b.get('last_report', {})
        print(f"  Decision: {last_rep.get('decision')}")
        print(f"  Execution: {last_rep.get('execution')}")
        print(f"  Hunting List: {b.get('symbols_csv', '')[:30]}...")
        print(f"  Active Slot (Symbol): {last_rep.get('symbol', 'None (Hunting)')}")
        print(f"  Active DCA Rungs: {last_rep.get('active_rungs', 0)}/{last_rep.get('max_rungs', 3)}")
        print(f"  Current Price: {last_rep.get('close_h', '0')}")
except Exception as e:
    print(f"Error getting Masha status: {e}")

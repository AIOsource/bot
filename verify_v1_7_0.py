"""Verification script for v1.7.0 features."""
import asyncio
import os
from datetime import datetime
from db_pkg import init_database, get_session
from llm_monitor import LLMMonitor, CircuitBreaker, BudgetExceededError, init_monitor_db
from db_pkg import LLMUsageRepository, IncidentRepository
from incident import IncidentManager
from ops_http import OpsServer
import aiohttp

async def verify():
    print("=== Verification v1.7.0 ===")
    
    # 1. Init DB
    await init_database("sqlite+aiosqlite:///test_v170.db")
    await init_monitor_db()
    
    # 2. Test Guardrails (Budget)
    print("\n[Test] Guardrails: Budget")
    try:
        await LLMMonitor.track_request("test", "model", cost=0.5, context="test")
        print("  - Tracked $0.50 cost")
        
        await LLMMonitor.check_budget()
        print("  ❌ Budget check failed (expected error)")
    except BudgetExceededError:
        print("  ✅ Budget check passed (caught BudgetExceededError)")
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")

    # 3. Test Circuit Breaker
    print("\n[Test] Guardrails: Circuit Breaker")
    print(f"  - Initial State: {'Open' if CircuitBreaker.is_open() else 'Closed'}")
    
    # Trigger errors
    for i in range(6):
        CircuitBreaker.record_error()
    
    if CircuitBreaker.is_open():
        print("  ✅ Circuit Breaker OPEN after errors")
    else:
        print("  ❌ Circuit Breaker CLOSED (expected OPEN)")
        
    # Recovery
    CircuitBreaker._is_open = False # Manual reset for test
    CircuitBreaker._errors = []
    
    # 4. Test Incident Clustering
    print("\n[Test] Signal Quality: Clustering")
    inc_id1 = await IncidentManager.process_signal(1, "Moscow", "accident", "Pipe burst")
    print(f"  - Created Incident #{inc_id1}")
    
    inc_id2 = await IncidentManager.process_signal(2, "Moscow", "accident", "Pipe burst 2")
    print(f"  - Processed Signal 2 -> Incident #{inc_id2}")
    
    if inc_id1 == inc_id2:
        print("  ✅ Clustering works (merged to same incident)")
    else:
        print(f"  ❌ Clustering failed (ids differ: {inc_id1} vs {inc_id2})")
        
    # 5. Test Ops Server
    print("\n[Test] Ops: Health API")
    server = OpsServer(port=8090)
    await server.start()
    
    async with aiohttp.ClientSession() as session:
        async with session.get("http://localhost:8090/health") as resp:
            data = await resp.json()
            print(f"  - GET /health: {resp.status} {data}")
            if data["status"] == "OK" or data["status"] == "DEGRADED":
                 print("  ✅ Health API works")
            else:
                 print("  ❌ Health API failed")
                 
    await server.stop()
    
    print("\n=== Verification Complete ===")

if __name__ == "__main__":
    try:
        asyncio.run(verify())
    except Exception as e:
        print(f"Fatal: {e}")

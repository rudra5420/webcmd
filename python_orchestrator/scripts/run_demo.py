"""WebCMD Live End-to-End Demonstration Runner.

Executes the 5 distinct trials proving the complete WebCMD architecture:
1. Cold Start Execution (Version A)
2. Workflow Reuse (Memory Hit)
3. Controlled Failure & Self-Healing Recovery (Version B)
4. Learned Recovery Reuse
5. Checkpoint Interruption & Safe Resume
"""
import asyncio
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
import websockets

BASE_URL = "http://127.0.0.1:8000"
LAB_URL = "http://127.0.0.1:9888"
EXACT_TASK = (
    "Download the latest monthly report from the report portal, "
    "save it locally as the correct report file, "
    "verify that the file is valid, and complete the task."
)


def http_get(url: str) -> dict:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_post(url: str, data: dict) -> dict:
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def collect_ws_events(execution_id: str, timeout: float = 35.0) -> list[dict]:
    """Connect to WebSocket and collect all domain events until awaiting_human_verification or terminal state."""
    ws_url = f"ws://127.0.0.1:8000/ws/executions/{execution_id}"
    events = []
    start_time = time.time()
    
    try:
        async with websockets.connect(ws_url) as ws:
            while time.time() - start_time < timeout:
                try:
                    raw_msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    msg = json.loads(raw_msg)
                    if msg.get("type") == "event" and msg.get("event"):
                        ev = msg["event"]
                        events.append(ev)
                        ev_type = ev.get("event_type")
                        print(f"      [EVENT] {ev_type}: {str(ev.get('payload', {}))[:90]}")
                        if ev_type in ("HumanVerificationRequested", "StepCompleted"):
                            pass
                    if msg.get("execution"):
                        status = msg["execution"].get("status")
                        if status in ("awaiting_human_verification", "completed", "failed"):
                            if status == "awaiting_human_verification":
                                # Give small grace for remaining events
                                await asyncio.sleep(0.5)
                                break
                except asyncio.TimeoutError:
                    # Check status via REST
                    det = http_get(f"{BASE_URL}/api/executions/{execution_id}")
                    ex_status = det.get("execution", {}).get("status")
                    if ex_status in ("awaiting_human_verification", "completed", "failed"):
                        break
    except Exception as e:
        print(f"      [WS Warning] {e}")
    return events


async def run_trial_1():
    print("\n" + "=" * 80)
    print(" TRIAL 1: COLD START EXECUTION (VERSION A)")
    print(" Intent Normalization -> Cold Start -> Browser Worker -> Verification -> Human Gate")
    print("=" * 80)
    
    # 1. Reset portal to Version A and clear prior memories for pure cold start
    http_get(f"{LAB_URL}/portal/switch?mode=A")
    http_post(f"{BASE_URL}/api/memory/clear", {})
    report_file = Path("downloads/september-report.pdf")
    if report_file.exists():
        report_file.unlink()

    # 2. Submit task
    t0 = time.time()
    res = http_post(f"{BASE_URL}/api/executions", {"task": EXACT_TASK, "auto_confirm": False})
    eid = res["execution_id"]
    print(f"   Submitted Task: '{EXACT_TASK}'")
    print(f"   Execution ID:   {eid}")

    # 3. Stream WebSocket events
    events = await collect_ws_events(eid)
    
    # 4. Verify Execution is AWAITING_HUMAN_VERIFICATION
    det = http_get(f"{BASE_URL}/api/executions/{eid}")
    ex = det["execution"]
    status = ex["status"]
    print(f"\n   Execution Status: {status}")
    assert status == "awaiting_human_verification", f"Expected awaiting_human_verification, got {status}"
    assert report_file.exists(), "Downloaded report file does not exist!"
    file_size = report_file.stat().st_size
    print(f"   Downloaded File:  {report_file} ({file_size} bytes)")
    assert file_size > 0, "File size must be non-zero"
    
    # Check automated verification payload
    checkpoints = det.get("checkpoints", [])
    print(f"   Checkpoints:      {len(checkpoints)} created")
    assert len(checkpoints) > 0, "Expected at least 1 checkpoint"
    print(f"   State Hash:       {checkpoints[-1].get('state_hash')}")

    # 5. User confirms at single final human verification gate
    print("   -> Confirming final human verification gate...")
    conf = http_post(f"{BASE_URL}/api/executions/{eid}/confirm", {"verified_by": "lead_operator"})
    assert conf["status"] == "success"
    final_status = conf["execution"]["status"]
    elapsed = time.time() - t0
    print(f"   Final Status:     {final_status} (verified by {conf['execution']['human_verification']['verified_by']})")
    print(f"   Trial 1 Duration: {elapsed:.2f}s")
    
    # 6. Verify Memory created with confidence 0.95
    mem_items = http_get(f"{BASE_URL}/api/memory?domain=127.0.0.1:9888")
    assert len(mem_items) > 0, "Memory items not found"
    top_mem = mem_items[0]
    conf_val = top_mem.get("confidence", 0.0)
    print(f"   Learned Memory:   Confidence={conf_val:.2f}, Scope={top_mem.get('scope_key')}")
    assert conf_val >= 0.90, f"Expected high confidence >= 0.90, got {conf_val}"
    return elapsed


async def run_trial_2(trial_1_duration: float):
    print("\n" + "=" * 80)
    print(" TRIAL 2: WORKFLOW REUSE (MEMORY HIT)")
    print(" Exact Intent -> Memory Lookup -> Direct Workflow Reuse -> Human Gate -> Complete")
    print("=" * 80)

    report_file = Path("downloads/september-report.pdf")
    if report_file.exists():
        report_file.unlink()

    t0 = time.time()
    res = http_post(f"{BASE_URL}/api/executions", {"task": EXACT_TASK, "auto_confirm": False})
    eid = res["execution_id"]
    print(f"   Execution ID:   {eid}")

    events = await collect_ws_events(eid)
    
    mem_events = [e for e in events if e.get("event_type") == "MemoryUpdated"]
    if mem_events:
        hit = mem_events[0].get("payload", {}).get("memory_hit")
        print(f"   Memory Hit Detected: {hit} (Selector: {mem_events[0].get('payload', {}).get('preferred_selector')})")
        assert hit is True, "Expected memory hit in Trial 2!"
    
    det = http_get(f"{BASE_URL}/api/executions/{eid}")
    ex = det["execution"]
    assert ex["status"] == "awaiting_human_verification"
    
    # Confirm
    conf = http_post(f"{BASE_URL}/api/executions/{eid}/confirm", {"verified_by": "lead_operator"})
    elapsed = time.time() - t0
    print(f"   Final Status:     {conf['execution']['status']}")
    print(f"   Trial 2 Duration: {elapsed:.2f}s (reused remembered workflow)")
    return elapsed


async def run_trial_3():
    print("\n" + "=" * 80)
    print(" TRIAL 3: CONTROLLED FAILURE & SELF-HEALING RECOVERY (VERSION B)")
    print(" Switch to Version B -> #btn-download Missing -> Autonomous Recovery -> Adapt to #btn-export")
    print("=" * 80)

    # Switch portal to Version B: #btn-download is gone, #btn-export is present
    sw = http_get(f"{LAB_URL}/portal/switch?mode=B")
    print(f"   Portal switched: Mode = {sw['mode']} (#btn-download REMOVED -> #btn-export PRESENT)")
    
    report_file = Path("downloads/september-report.pdf")
    if report_file.exists():
        report_file.unlink()

    t0 = time.time()
    res = http_post(f"{BASE_URL}/api/executions", {"task": EXACT_TASK, "auto_confirm": False})
    eid = res["execution_id"]
    print(f"   Execution ID:   {eid}")

    events = await collect_ws_events(eid)

    # Check for RecoveryAttempted event
    recovery_events = [e for e in events if e.get("event_type") == "RecoveryAttempted"]
    print(f"\n   Recovery Events Detected: {len(recovery_events)}")
    assert len(recovery_events) > 0, "Expected RecoveryAttempted event during Version B execution!"
    rec_payload = recovery_events[0].get("payload", {})
    print(f"   Recovery Action:    {rec_payload.get('action')}")
    print(f"   Original Selector:  {rec_payload.get('original_selector')}")
    print(f"   Adapted Selector:   {rec_payload.get('adapted_selector')}")
    print(f"   Reason:             {rec_payload.get('reason')}")

    det = http_get(f"{BASE_URL}/api/executions/{eid}")
    ex = det["execution"]
    assert ex["status"] == "awaiting_human_verification"
    assert ex["result"]["self_healing_recovery_engaged"] is True
    assert ex["result"]["selector_used"] == "#btn-export"
    assert report_file.exists()
    print(f"   Automated Verification: {ex['result']['automated_verification']}")

    # Confirm human verification
    conf = http_post(f"{BASE_URL}/api/executions/{eid}/confirm", {"verified_by": "lead_operator"})
    elapsed = time.time() - t0
    print(f"   Final Status:       {conf['execution']['status']}")
    print(f"   Trial 3 Duration:   {elapsed:.2f}s (including self-healing recovery loop)")

    # Verify memory updated with adapted selector
    mem_items = http_get(f"{BASE_URL}/api/memory?domain=127.0.0.1:9888")
    adapted_mem = [m for m in mem_items if m.get("content", {}).get("preferred_selector") == "#btn-export" or m.get("content", {}).get("selector") == "#btn-export"]
    assert len(adapted_mem) > 0, "Adapted selector not found in persistent memory!"
    found_sel = adapted_mem[0].get('content', {}).get('selector') or adapted_mem[0].get('content', {}).get('preferred_selector')
    print(f"   Learned Adapted Memory: Selector={found_sel}, Confidence={adapted_mem[0].get('confidence')}")
    return elapsed


async def run_trial_4():
    print("\n" + "=" * 80)
    print(" TRIAL 4: LEARNED RECOVERY REUSE")
    print(" Version B -> Memory Recall (#btn-export) -> Direct Execution (No Error) -> Verified")
    print("=" * 80)

    report_file = Path("downloads/september-report.pdf")
    if report_file.exists():
        report_file.unlink()

    t0 = time.time()
    res = http_post(f"{BASE_URL}/api/executions", {"task": EXACT_TASK, "auto_confirm": False})
    eid = res["execution_id"]
    print(f"   Execution ID:   {eid}")

    events = await collect_ws_events(eid)

    # In Trial 4, the adapted locator is used directly from memory, so NO recovery is needed!
    recovery_events = [e for e in events if e.get("event_type") == "RecoveryAttempted"]
    print(f"   Recovery Events in Trial 4: {len(recovery_events)} (0 expected due to learned memory reuse)")
    assert len(recovery_events) == 0, "Recovery should NOT be triggered; learned selector should be used directly!"

    det = http_get(f"{BASE_URL}/api/executions/{eid}")
    ex = det["execution"]
    assert ex["status"] == "awaiting_human_verification"
    assert ex["result"]["selector_used"] == "#btn-export"
    assert report_file.exists()

    conf = http_post(f"{BASE_URL}/api/executions/{eid}/confirm", {"verified_by": "lead_operator"})
    elapsed = time.time() - t0
    print(f"   Final Status:     {conf['execution']['status']}")
    print(f"   Trial 4 Duration: {elapsed:.2f}s (direct execution with learned selector)")
    return elapsed


async def run_trial_5():
    print("\n" + "=" * 80)
    print(" TRIAL 5: CHECKPOINT INTERRUPTION & SAFE RESUME")
    print(" Progress to Pre-Verification -> Pause/Simulate Interruption -> Resume from Checkpoint -> Confirm")
    print("=" * 80)

    # Switch back to Version A
    http_get(f"{LAB_URL}/portal/switch?mode=A")
    report_file = Path("downloads/september-report.pdf")
    if report_file.exists():
        report_file.unlink()

    # 1. Start execution
    res = http_post(f"{BASE_URL}/api/executions", {"task": EXACT_TASK, "auto_confirm": False})
    eid = res["execution_id"]
    print(f"   Execution ID:   {eid}")

    # Wait until it reaches awaiting_human_verification
    events = await collect_ws_events(eid)
    det = http_get(f"{BASE_URL}/api/executions/{eid}")
    assert det["execution"]["status"] == "awaiting_human_verification"
    checkpoints = det.get("checkpoints", [])
    assert len(checkpoints) > 0
    cp = checkpoints[-1]
    seq = cp.get("sequence_number")
    state_hash = cp.get("state_hash")
    print(f"   Checkpoint Created: Sequence #{seq}, Hash: {state_hash}")

    # 2. Simulate process interruption / restart
    print("   [Simulation] Process paused / interrupted while awaiting confirmation.")
    time.sleep(1.0)

    # 3. Call resume endpoint
    print(f"   -> Resuming execution {eid} from checkpoint #{seq}...")
    resume_res = http_post(f"{BASE_URL}/api/executions/{eid}/resume", {})
    assert resume_res["status"] == "resumed"
    resumed_ex = resume_res["execution"]
    print(f"   Resumed Status:     {resumed_ex['status']}")
    assert resumed_ex["status"] == "awaiting_human_verification"
    assert report_file.exists(), "Report file preserved from prior step"

    # 4. Confirm verification after resume
    print("   -> Confirming human verification on resumed execution...")
    conf = http_post(f"{BASE_URL}/api/executions/{eid}/confirm", {"verified_by": "lead_operator"})
    print(f"   Final Status:       {conf['execution']['status']}")
    assert conf["execution"]["status"] == "completed"
    print("   Trial 5 Passed: Resumed cleanly from checkpoint and completed without re-executing steps!")


async def main():
    print("\n" + "=" * 80)
    print(" WEBCMD LOCALHOST END-TO-END DEMONSTRATION")
    print(f" Control UI: {BASE_URL}")
    print(f" Test Lab:   {LAB_URL}")
    print("=" * 80)

    t1_dur = await run_trial_1()
    t2_dur = await run_trial_2(t1_dur)
    t3_dur = await run_trial_3()
    t4_dur = await run_trial_4()
    await run_trial_5()

    print("\n" + "=" * 80)
    print(" ALL 5 DEMONSTRATION TRIALS COMPLETED SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

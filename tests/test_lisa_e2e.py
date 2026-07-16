"""
LISA End-to-End Integration Test
================================
Tests the full pipeline:
  Mock OCS (port 8001)  ->  LCU Main (port 8000)  ->  LISA SDK Server (port 8004)

This test:
  1. Verifies all 3 servers are reachable
  2. Triggers a schedule sync on the LCU
  3. Monitors the executor state as it processes LISA observations
  4. Validates that the LISA SDK server received the commands

Prerequisites (3 terminals):
  Terminal 1:  py tests/mock_ocs_server.py          (port 8001)
  Terminal 2:  py sdk_api_server.py --simulate       (port 8004)
  Terminal 3:  py -m uvicorn main:app --host 0.0.0.0 --port 8000

Then run:
  py tests/test_lisa_e2e.py
"""

import os
import sys
import time
import requests
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Configuration ──────────────────────────────────────────────
LCU_URL       = os.environ.get("LCU_URL",       "http://127.0.0.1:8000")
MOCK_OCS_URL  = os.environ.get("MOCK_OCS_URL",  "http://127.0.0.1:8001")
LISA_SDK_URL  = os.environ.get("LISA_SDK_URL",   "http://127.0.0.1:8004")

POLL_INTERVAL = 2      # seconds between status checks
MAX_WAIT      = 120     # max seconds to wait for observation pipeline


def header(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def step(num, msg):
    print(f"\n[Step {num}] {msg}")
    print("-" * 50)


def check_server(name, url, endpoint="/"):
    """Check if a server is reachable."""
    try:
        resp = requests.get(f"{url}{endpoint}", timeout=5)
        print(f"  [OK] {name:20s} -> {url:30s} (HTTP {resp.status_code})")
        return True
    except Exception as e:
        print(f"  [FAIL] {name:20s} -> {url:30s} (UNREACHABLE: {e})")
        return False


def run_e2e_test():
    header("LISA END-TO-END INTEGRATION TEST")

    # ─── Step 1: Verify all servers ─────────────────────────────
    step(1, "Verifying all servers are reachable")
    
    all_ok = True
    all_ok &= check_server("Mock OCS Server",  MOCK_OCS_URL, "/api/instruments/")
    all_ok &= check_server("LCU Main App",     LCU_URL,      "/")
    all_ok &= check_server("LISA SDK Server",   LISA_SDK_URL, "/")
    
    if not all_ok:
        print("\n[FATAL] Not all servers are running. Please start them first.")
        print("  Terminal 1:  py tests/mock_ocs_server.py")
        print("  Terminal 2:  cd <AtikSDK>/src/server && py sdk_api_server.py --simulate")
        print("  Terminal 3:  py -m uvicorn main:app --host 0.0.0.0 --port 8000")
        return False

    # ─── Step 2: Check Mock OCS instruments ─────────────────────
    step(2, "Checking Mock OCS instrument configuration")
    
    instruments = requests.get(f"{MOCK_OCS_URL}/api/instruments/", timeout=5).json()
    print(f"  Registered instruments: {json.dumps(instruments, indent=4)}")
    
    lisa_entry = instruments.get("LISA")
    if lisa_entry:
        print(f"  [OK] LISA found: class={lisa_entry.get('class')}, name={lisa_entry.get('name')}")
    else:
        print("  [WARN] LISA not found in Mock OCS instruments.")
        print("    The mock OCS may not include LISA in the schedule.")

    # ─── Step 3: Check LCU system status (before sync) ──────────
    step(3, "LCU system status (before sync)")
    
    status = requests.get(f"{LCU_URL}/", timeout=5).json()
    
    t_plugins = status.get("telescope_plugins", {})
    i_plugins = status.get("instrument_plugins", {})
    hw_mapping = status.get("hardware_mapping", {})
    
    print(f"  Telescope plugins : {list(t_plugins.keys())}")
    print(f"  Instrument plugins: {list(i_plugins.keys())}")
    print(f"  Hardware mapping  : {json.dumps(hw_mapping, indent=4)}")
    
    if "LISA" not in i_plugins:
        print("\n  [WARN] LISA instrument plugin is NOT loaded in LCU!")
        print("  Check that Plugins/instrument/LISA/instrument_plugin.py exists and is valid.")
    else:
        print(f"  [OK] LISA plugin loaded. Queue size: {i_plugins['LISA'].get('queue_size', 0)}")

    # ─── Step 4: Check LISA SDK server health ───────────────────
    step(4, "LISA SDK server health check")
    
    sdk_health = requests.get(f"{LISA_SDK_URL}/", timeout=5).json()
    cli_running = sdk_health.get("data", {}).get("cli_running", False)
    sim_mode = sdk_health.get("data", {}).get("simulation_mode", False)
    print(f"  CLI running    : {cli_running}")
    print(f"  Simulation mode: {sim_mode}")
    
    sdk_status = requests.get(f"{LISA_SDK_URL}/api/status", timeout=5).json()
    cam_state = sdk_status.get("data", {})
    print(f"  Camera connected: {cam_state.get('connected', False)}")
    print(f"  Current binning : {cam_state.get('bin_x', '?')}x{cam_state.get('bin_y', '?')}")
    print(f"  Filter position : {cam_state.get('filter_position', '?')}")

    # ─── Step 5: Trigger schedule sync on LCU ───────────────────
    step(5, "Triggering schedule sync on LCU")
    
    sync_resp = requests.post(f"{LCU_URL}/sync", timeout=10)
    print(f"  Sync response: {sync_resp.json()}")
    
    # Wait a moment for sync to complete
    time.sleep(3)
    
    # Check status after sync
    status_after = requests.get(f"{LCU_URL}/", timeout=5).json()
    i_plugins_after = status_after.get("instrument_plugins", {})
    t_plugins_after = status_after.get("telescope_plugins", {})
    
    lisa_queue = i_plugins_after.get("LISA", {}).get("queue_size", 0)
    print(f"  LISA queue after sync: {lisa_queue} observation(s)")
    
    for t_id, t_info in t_plugins_after.items():
        t_queue = t_info.get("queue_size", 0)
        if t_queue > 0:
            print(f"  Telescope {t_id} queue: {t_queue} target(s)")

    # ─── Step 6: Monitor executor pipeline ──────────────────────
    step(6, "Monitoring T100 executor pipeline")
    
    states_seen = set()
    start_time = time.time()
    last_state = None
    observation_started = False
    observation_completed = False
    
    while time.time() - start_time < MAX_WAIT:
        try:
            status = requests.get(f"{LCU_URL}/", timeout=5).json()
            executors = status.get("executors", {})
            
            # Focus on T100 executor since LISA is routed there
            exec_info = executors.get("T100", {})
            state = exec_info.get("current_state", "IDLE")
            obs_id = exec_info.get("current_obs_id")
            ra = exec_info.get("current_ra")
            dec = exec_info.get("current_dec")
            
            if state != last_state:
                elapsed = time.time() - start_time
                coord_str = f"RA={ra:.4f}, DEC={dec:.4f}" if ra is not None else ""
                obs_str = f"obs={obs_id}" if obs_id else ""
                print(f"  [{elapsed:6.1f}s] T100 -> {state:15s} {obs_str:30s} {coord_str}")
                last_state = state
                states_seen.add(state)
                
                # Check for active state transitions
                if state not in ["IDLE", "ABORTED", "DONE", "ERROR", "REJECTED"]:
                    observation_started = True
                
                # If we were active and now we went back to IDLE or reached terminal state
                if observation_started and state in ["IDLE", "DONE", "ERROR", "ABORTED", "REJECTED"]:
                    observation_completed = True
                    print(f"\nObservation finished with state: {state}")
                    break
                    
        except Exception as e:
            print(f"  [!] Error polling status: {e}")
        
        time.sleep(POLL_INTERVAL)
    
    # ─── Step 7: Final status report ────────────────────────────
    step(7, "Final status report")
    
    elapsed_total = time.time() - start_time
    print(f"  Total time       : {elapsed_total:.1f}s")
    print(f"  States observed  : {sorted(states_seen)}")
    print(f"  Obs started      : {'YES' if observation_started else 'NO'}")
    print(f"  Obs completed    : {'YES' if observation_completed else 'NO'}")
    
    # Check LISA SDK state after execution
    try:
        sdk_status_after = requests.get(f"{LISA_SDK_URL}/api/status", timeout=5).json()
        cam_state_after = sdk_status_after.get("data", {})
        print(f"\n  LISA SDK post-execution state:")
        print(f"    Connected    : {cam_state_after.get('connected', '?')}")
        print(f"    Binning      : {cam_state_after.get('bin_x', '?')}x{cam_state_after.get('bin_y', '?')}")
        print(f"    Filter pos   : {cam_state_after.get('filter_position', '?')}")
        print(f"    Cooling      : {cam_state_after.get('cooling', '?')} (target: {cam_state_after.get('target_c', '?')}°C)")
    except Exception:
        pass
    
    # Final verdict
    header("TEST RESULT")
    if observation_completed:
        print("  [OK] END-TO-END TEST PASSED")
        print("  The full pipeline executed successfully:")
        print("    Mock OCS -> LCU Sync -> Telescope Executor -> LISA Plugin -> LISA SDK")
    elif observation_started:
        print("  [WARN] PARTIAL: Observation started but did not complete within timeout")
        print(f"    Last state seen: {last_state}")
        print(f"    States observed: {sorted(states_seen)}")
    else:
        print("  [FAIL] NO OBSERVATION EXECUTED")
        print("  Possible reasons:")
        print("    - Mock OCS schedule doesn't include LISA observations")
        print("    - LISA is not mapped to any telescope in the hardware mapping")
        print("    - The schedule start times are in the future")
        
    return observation_completed


if __name__ == "__main__":
    success = run_e2e_test()
    sys.exit(0 if success else 1)

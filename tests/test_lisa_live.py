import os
import sys
import asyncio

# Ensure LCU root is in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.instrument.LISA.instrument_plugin import LISACameraPlugin
from core.communications.schemas import ScheduleSchema

MOCK_API_DATA = {
    "id": 1,
    "request": {
        "id": 101,
        "observation_note": "LISA Camera Live Test",
        "state": "PENDING",
        "acceptability_threshold": 90.0,
        "modified": "2026-06-03T12:00:00Z",
        "duration": 600,
        "configurations": [{
            "id": 501,
            "instrument_type": "LISA",
            "type": "EXPOSE",
            "priority": 1,
            "instrument_configs": [{
                "optical_elements": {"filter": "luminance"},
                "mode": "full",
                "exposure_time": 2.0,
                "exposure_count": 2,
                "rotator_mode": "SKY",
                "extra_params": {
                    "binning": "2x2", 
                    "cooling": -5.0,
                    "delay": 1.0,
                    "subframe_x": 0, "subframe_y": 0, "subframe_w": 1000, "subframe_h": 1000
                },
                "rois": []
            }],
            "target": {
                "type": "ICRS",
                "name": "Live Target",
                "ra": 10.684,
                "dec": 41.269,
                "epoch": 2000.0
            },
            "configuration_status": 1,
            "state": "PENDING",
            "instrument_name": "LISA",
            "guide_camera_name": "guider"
        }]
    },
    "site": "tst",
    "enclosure": "doma",
    "telescope": "1m0a",
    "start": "2026-06-03T20:00:00Z",
    "end": "2026-06-03T20:10:00Z",
    "priority": 100,
    "state": "PENDING",
    "proposal": "P1",
    "submitter": "T1",
    "name": "Live Target",
    "ipp_value": 1.0,
    "observation_type": "S",
    "request_group_id": 1001,
    "created": "2026-06-03T10:00:00Z",
    "modified": "2026-06-03T10:00:00Z"
}

async def run_live_test():
    print("=========================================")
    print("  LISA PLUGIN LIVE INTEGRATION TEST")
    print("=========================================\n")
    
    print("[1] Initialising plugin (will trigger startup connect)...\n")
    api_url = os.environ.get("LISA_API_URL", "http://127.0.0.1:8000")
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
        if not api_url.startswith("http"):
            api_url = f"http://{api_url}"
            if ":" not in api_url.replace("http://", ""):
                api_url = f"{api_url}:8000"
    print(f"Using API URL: {api_url}")

    # Early exit check: Verify the server is actually reachable before proceeding
    try:
        import requests
        print("Checking server connectivity...")
        requests.get(f"{api_url}/", timeout=3)
    except Exception as e:
        print(f"\n[!] FATAL: API server is NOT reachable at {api_url}.")
        print("Please check if the server is running, bound to 0.0.0.0, and the firewall is open.")
        print(f"Error details: {e}")
        return

    # This will automatically POST to /api/command with {"command": "connect"}
    plugin = LISACameraPlugin(instrument_name="LISA", api_url=api_url)
    
    # Wait briefly for startup logs to flush
    await asyncio.sleep(1)
    
    print("\n[2] Fetching camera status and info...")
    info = await plugin.get_camera_info()
    temp = await plugin.get_temperature()
    print(f"Info: {info}")
    print(f"Temp: {temp}")

    if info is None:
        print("\n[!] Failed to connect or retrieve info from server. Stopping test.")
        await plugin.disconnect()
        return

    obs = ScheduleSchema.model_validate(MOCK_API_DATA)
    config = obs.request.configurations[0]
    
    print("\n[3] Triggering CONFIGURE (Setting filters, binning, etc.)...")
    await plugin.configure(config)
    
    print("\n[4] Triggering EXPOSE (2x 2.0s sequence)...")
    await plugin.expose(config)
    
    print("\n[5] Test sequence complete. Cleaning up...")
    await plugin.disconnect()
    print("Done!")

if __name__ == '__main__':
    asyncio.run(run_live_test())

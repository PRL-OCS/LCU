import asyncio
import os
import sys
from typing import Any, Dict

# Ensure local packages can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set Skychart port to 3292 for the real running application
os.environ["SKYCHART_PORT"] = "3292"

from Plugins.telescope.T1P2.telescope_plugin import T1P2TelescopePlugin
from core.communications.schemas import Target

# 1. Create 3 example requests: 2 sidereal targets and 1 non-sidereal target
mock_requests = [
    # Request 1 (Sidereal): Vega
    {
        "id": 101,
        "observation_note": "Observing Vega (Sidereal)",
        "configurations": [
            {
                "id": 501,
                "target": {
                    "type": "ICRS",
                    "name": "Vega",
                    "ra": 279.234735,
                    "dec": 38.783689,
                    "epoch": 2000.0
                }
            }
        ]
    },
    # Request 2 (Sidereal): Sirius
    {
        "id": 102,
        "observation_note": "Observing Sirius (Sidereal)",
        "configurations": [
            {
                "id": 502,
                "target": {
                    "type": "ICRS",
                    "name": "Sirius",
                    "ra": 101.28715,
                    "dec": -16.716116,
                    "epoch": 2000.0
                }
            }
        ]
    },
    # Request 3 (Non-sidereal): Mars (Requires Skychart name resolution)
    {
        "id": 103,
        "observation_note": "Observing Mars (Non-sidereal)",
        "configurations": [
            {
                "id": 503,
                "target": {
                    "type": "NON-SIDEREAL",
                    "name": "Mars",
                    "ra": 0.0,
                    "dec": 0.0,
                    "epoch": 2000.0
                }
            }
        ]
    }
]

def parse_request_target(request_data: Dict[str, Any]) -> Target:
    """
    Parses the incoming request data, extracting only the 'target' field
    and instantiating a Target Pydantic model for the telescope plugin.
    """
    try:
        config = request_data["configurations"][0]
        target_dict = config["target"]
        target = Target(**target_dict)
        return target
    except (KeyError, IndexError) as e:
        raise ValueError(f"Failed to parse target field from request: {e}")

async def run_simulation():
    print("\n" + "="*65)
    print("STARTING T1P2 SKYCHART MULTI-REQUEST SIMULATION (PORT 3292)")
    print("="*65)

    # Initialize the T1P2 plugin
    plugin = T1P2TelescopePlugin(telescope_id="1m0a")
    print(f"[INIT] Plugin initialized. Telescope ID: {plugin.telescope_id}")
    print(f"[INIT] Skychart online: {plugin.driver.is_skychart_online}")

    if not plugin.driver.is_skychart_online:
        print("[ERROR] Skychart is not detected/responding on port 3292. Please make sure the Skychart application is running with its TCP server active.")
        return

    # Execute each request one by one
    for idx, request in enumerate(mock_requests, 1):
        print("\n" + "-"*50)
        print(f"PROCESSING REQUEST {idx}/3 (ID: {request['id']})")
        print(f"Note: {request['observation_note']}")
        print("-"*50)

        # 2. Parse the request, extracting only the 'target' field
        try:
            target = parse_request_target(request)
            print(f"[PARSE] Target parsed successfully: Name='{target.name}', Type='{target.type}'")
        except Exception as err:
            print(f"[PARSE ERROR] Failed to parse target: {err}")
            continue

        # 3. Slew to target
        print(f"[EXECUTE] Triggering slew to '{target.name}'...")
        try:
            await plugin.slew_to_target(target)
            print(f"[EXECUTE] Slew complete.")
        except Exception as e:
            print(f"[EXECUTE ERROR] Slew failed for '{target.name}': {e}")
            continue

        # 4. Start tracking
        print(f"[EXECUTE] Triggering tracking for '{target.name}'...")
        try:
            await plugin.start_tracking(target)
            print(f"[EXECUTE] Tracking enabled successfully.")
        except Exception as e:
            print(f"[EXECUTE ERROR] Starting tracking failed: {e}")

        # Show current telemetry
        telemetry = plugin.get_current_telemetry()
        print(f"[TELEMETRY] Coordinates: RA={telemetry['ra']:.4f}°, Dec={telemetry['dec']:.4f}°")
        print(f"[TELEMETRY] Status: Connected={telemetry['is_connected']}, Slewing={telemetry['is_slewing']}, Tracking={telemetry['is_tracking']}")

        # 5. Delay of 10 seconds before the next request
        if idx < len(mock_requests):
            print(f"\n[DELAY] Waiting 10 seconds before next request...")
            await asyncio.sleep(10.0)

    print("\n" + "="*65)
    print("ALL REQUESTS PROCESSED SUCCESSFULLY!")
    print("="*65)

if __name__ == "__main__":
    asyncio.run(run_simulation())

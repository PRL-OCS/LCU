from fastapi import FastAPI
import uvicorn
import copy
import argparse
from datetime import datetime, timedelta, timezone

app = FastAPI(title="Mock Observation Portal - Multi-Telescope Test")

CURRENT_MODE = "default"
global_counter = 1000
global_obs_counter = 1

@app.get("/api/instruments/")
def get_instruments():
    return {
        "LISA": {
            "class": "1m2",
            "name": "LISA"
        },
        "T2P5_CAM": {
            "class": "T2P5",
            "name": "T2P5_CAM"
        }
    }

# Base configuration template to duplicate
base_config = {
    "id": 1000,
    "instrument_type": "MOCK_CAM",
    "type": "TEST",
    "priority": 1,
    "instrument_configs": [
        {
            "mode": "IMG",
            "exposure_time": 5.0
        }
    ],
    "target": {
        "type": "ICRS",
        "name": "Target-Alpha",
        "ra": 88.792,
        "dec": 7.407,
        "epoch": 2000.0
    },
    "configuration_status": 1,
    "state": "PENDING",
    "instrument_name": "MOCK_CAM"
}

@app.get("/api/schedule/")
def get_schedule():
    global global_counter
    global global_obs_counter
    
    now = datetime.now(timezone.utc)
    
    # ----------------------------------------
    # 1m2 Observation 1: M43 (Sidereal)
    # ----------------------------------------
    obs1_start = now + timedelta(seconds=2)
    obs1_end = obs1_start + timedelta(seconds=25)
    
    obs1 = {
        "id": global_obs_counter,
        "request": {
            "id": global_obs_counter * 100,
            "observation_note": "1m2 Observation 1 - M43",
            "state": "PENDING",
            "acceptability_threshold": 90.0,
            "modified": now.isoformat(),
            "duration": 3600,
            "configurations": []
        },
        "site": "PRL",
        "enclosure": "DomeC",
        "telescope": "1m2",
        "start": obs1_start.isoformat(),
        "end": obs1_end.isoformat(),
        "priority": 1,
        "state": "PENDING",
        "proposal": "PROP-03",
        "submitter": "astronomer",
        "name": "M43 Obs",
        "ipp_value": 1.0,
        "observation_type": "NORMAL",
        "request_group_id": 3,
        "created": now.isoformat(),
        "modified": now.isoformat()
    }

    # Add configuration for M43
    cfg1 = copy.deepcopy(base_config)
    cfg1["id"] = global_counter
    cfg1["configuration_status"] = global_counter
    global_counter += 1
    cfg1["instrument_type"] = "LISA"
    cfg1["instrument_name"] = "LISA"
    cfg1["target"]["name"] = "M43"
    cfg1["target"]["type"] = "MPC_COMET"
    cfg1["target"]["ra"] = 83.858
    cfg1["target"]["dec"] = -5.269
    cfg1["instrument_configs"][0]["exposure_time"] = 5.0
    obs1["request"]["configurations"].append(cfg1)

    # ----------------------------------------
    # 1m2 Observation 2: Jupiter (Non-Sidereal)
    # ----------------------------------------
    obs2_start = now + timedelta(seconds=30)
    obs2_end = obs2_start + timedelta(seconds=25)
    
    obs2 = {
        "id": global_obs_counter + 1,
        "request": {
            "id": (global_obs_counter + 1) * 100,
            "observation_note": "1m2 Observation 2 - Jupiter",
            "state": "PENDING",
            "acceptability_threshold": 90.0,
            "modified": now.isoformat(),
            "duration": 3600,
            "configurations": []
        },
        "site": "PRL",
        "enclosure": "DomeC",
        "telescope": "1m2",
        "start": obs2_start.isoformat(),
        "end": obs2_end.isoformat(),
        "priority": 2,
        "state": "PENDING",
        "proposal": "PROP-03",
        "submitter": "astronomer",
        "name": "Jupiter Obs",
        "ipp_value": 1.0,
        "observation_type": "NORMAL",
        "request_group_id": 4,
        "created": now.isoformat(),
        "modified": now.isoformat()
    }

    # Add configuration for Jupiter
    cfg2 = copy.deepcopy(base_config)
    cfg2["id"] = global_counter
    cfg2["configuration_status"] = global_counter
    global_counter += 1
    cfg2["instrument_type"] = "LISA"
    cfg2["instrument_name"] = "LISA"
    cfg2["target"]["name"] = "Jupiter"
    cfg2["target"]["type"] = "MPC_PLANET"
    cfg2["target"]["ra"] = 0.0
    cfg2["target"]["dec"] = 0.0
    cfg2["instrument_configs"][0]["exposure_time"] = 5.0
    obs2["request"]["configurations"].append(cfg2)

    # ----------------------------------------
    # 1m2 Observation 3: Polaris (Sidereal)
    # ----------------------------------------
    obs3_start = now + timedelta(seconds=60)
    obs3_end = obs3_start + timedelta(seconds=25)
    
    obs3 = {
        "id": global_obs_counter + 2,
        "request": {
            "id": (global_obs_counter + 2) * 100,
            "observation_note": "1m2 Observation 3 - Polaris",
            "state": "PENDING",
            "acceptability_threshold": 90.0,
            "modified": now.isoformat(),
            "duration": 3600,
            "configurations": []
        },
        "site": "PRL",
        "enclosure": "DomeC",
        "telescope": "1m2",
        "start": obs3_start.isoformat(),
        "end": obs3_end.isoformat(),
        "priority": 3,
        "state": "PENDING",
        "proposal": "PROP-03",
        "submitter": "astronomer",
        "name": "Polaris Obs",
        "ipp_value": 1.0,
        "observation_type": "NORMAL",
        "request_group_id": 5,
        "created": now.isoformat(),
        "modified": now.isoformat()
    }

    # Add configuration for Polaris
    cfg3 = copy.deepcopy(base_config)
    cfg3["id"] = global_counter
    cfg3["configuration_status"] = global_counter
    global_counter += 1
    cfg3["instrument_type"] = "LISA"
    cfg3["instrument_name"] = "LISA"
    cfg3["target"]["name"] = "Polaris"
    cfg3["target"]["type"] = "MPC_COMET"
    cfg3["target"]["ra"] = 37.95
    cfg3["target"]["dec"] = 89.26
    cfg3["instrument_configs"][0]["exposure_time"] = 5.0
    obs3["request"]["configurations"].append(cfg3)

    global_obs_counter += 3

    return {
        "results": [obs1, obs2, obs3]
    }

@app.patch("/api/observations/{obs_id}/")
def patch_observation(obs_id: int, payload: dict):
    print(f"[MOCK PRAMANA] Observation {obs_id} state updated to: {payload.get('state')}")
    return {"status": "success", "id": obs_id, "state": payload.get('state')}

@app.patch("/api/configurationstatus/{config_id}/")
def patch_configuration_status(config_id: int, payload: dict):
    # Print the payload formatted for easy debugging
    main_state = payload.get("state", "NO_CHANGE")
    summary = payload.get("summary", {})
    summary_state = summary.get("state", "NO_CHANGE")
    events = summary.get("events", [])
    
    start_time = summary.get("start", "N/A")
    end_time = summary.get("end", "N/A")
    time_completed = summary.get("time_completed", 0.0)
    
    print(f"\n[MOCK PRAMANA] ConfigStatus {config_id} PATCH Received:")
    print(f"  --> Main State: {main_state}")
    print(f"  --> Summary State: {summary_state}")
    print(f"  --> Start Time: {start_time}")
    print(f"  --> End Time: {end_time}")
    print(f"  --> Exposure Time Completed: {time_completed}s")
    print(f"  --> Timeline Events: {len(events)}")
    for e in events:
        print(f"      - {e.get('state')} @ {e.get('timestamp')}")
    print()
    return {"status": "success"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock OCS Server")
    parser.add_argument("--mode", type=str, default="default", help="Test mode: 'default' or 'slewing'")
    args = parser.parse_args()
    
    CURRENT_MODE = args.mode
    print(f"Starting Mock OCS Server in MODE: {CURRENT_MODE}")
    
    uvicorn.run(app, host="127.0.0.1", port=8001)

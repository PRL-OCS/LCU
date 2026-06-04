from fastapi import FastAPI
import uvicorn
import copy
import argparse
from datetime import datetime, timedelta, timezone

app = FastAPI(title="Mock Observation Portal - Multi-Telescope Test")

CURRENT_MODE = "default"

@app.get("/api/instruments/")
def get_instruments():
    return {
        "MOCK_CAM": {
            "class": "T100",
            "name": "MOCK_CAM"
        },
        "T200_CAM": {
            "class": "T200",
            "name": "T200_CAM"
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
    
    now = datetime.now(timezone.utc)
    
    # ----------------------------------------
    # T100 Observation (Multiple Exposures)
    # ----------------------------------------
    t100_start = now
    t100_end = now + timedelta(seconds=60)
    
    t100_obs = {
        "id": 1,
        "request": {
            "id": 101,
            "observation_note": "T100 Multi-Exposure",
            "state": "PENDING",
            "acceptability_threshold": 90.0,
            "modified": now.isoformat(),
            "duration": 3600,
            "configurations": []
        },
        "site": "PRL",
        "enclosure": "DomeA",
        "telescope": "T100",
        "start": t100_start.isoformat(),
        "end": t100_end.isoformat(),
        "priority": 1,
        "state": "PENDING",
        "proposal": "PROP-01",
        "submitter": "astronomer",
        "name": "T100 Test Obs",
        "ipp_value": 1.0,
        "observation_type": "NORMAL",
        "request_group_id": 1,
        "created": now.isoformat(),
        "modified": now.isoformat()
    }
    
    if CURRENT_MODE == "slewing":
        # Add 3 configurations with completely different targets to force slewing
        for i in range(3):
            cfg = copy.deepcopy(base_config)
            cfg["id"] = 1000 + i
            cfg["instrument_configs"][0]["exposure_time"] = 4.0
            cfg["target"]["name"] = f"SlewTarget-{i}"
            cfg["target"]["ra"] = 88.792 + (i * 25.0)
            cfg["target"]["dec"] = 7.407 - (i * 15.0)
            t100_obs["request"]["configurations"].append(cfg)
    else:
        # Add 3 configurations (exposures) for T100 on the SAME target
        for i in range(3):
            cfg = copy.deepcopy(base_config)
            cfg["id"] = 1000 + i
            cfg["instrument_configs"][0]["exposure_time"] = 10.0 + (i * 5) # 10s, 15s, 20s
            t100_obs["request"]["configurations"].append(cfg)

    # ----------------------------------------
    # T200 Observation (Multiple Exposures)
    # ----------------------------------------
    t200_start = now + timedelta(seconds=30)
    t200_end = t200_start + timedelta(seconds=60)
    
    t200_obs = {
        "id": 2,
        "request": {
            "id": 201,
            "observation_note": "T200 Multi-Exposure",
            "state": "PENDING",
            "acceptability_threshold": 90.0,
            "modified": now.isoformat(),
            "duration": 3600,
            "configurations": []
        },
        "site": "PRL",
        "enclosure": "DomeB",
        "telescope": "T200",
        "start": t200_start.isoformat(),
        "end": t200_end.isoformat(),
        "priority": 1,
        "state": "PENDING",
        "proposal": "PROP-02",
        "submitter": "astronomer",
        "name": "T200 Test Obs",
        "ipp_value": 1.0,
        "observation_type": "NORMAL",
        "request_group_id": 2,
        "created": now.isoformat(),
        "modified": now.isoformat()
    }

    # Add 2 configurations (exposures) for T200
    for i in range(2):
        cfg = copy.deepcopy(base_config)
        cfg["id"] = 2000 + i
        cfg["instrument_type"] = "T200_CAM"
        cfg["instrument_name"] = "T200_CAM"
        cfg["target"]["name"] = "Target-Beta"
        cfg["instrument_configs"][0]["exposure_time"] = 12.0 # 12s each
        t200_obs["request"]["configurations"].append(cfg)

    return {
        "results": [t100_obs, t200_obs]
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock OCS Server")
    parser.add_argument("--mode", type=str, default="default", help="Test mode: 'default' or 'slewing'")
    args = parser.parse_args()
    
    CURRENT_MODE = args.mode
    print(f"Starting Mock OCS Server in MODE: {CURRENT_MODE}")
    
    uvicorn.run(app, host="127.0.0.1", port=8001)

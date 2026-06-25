from fastapi import FastAPI, UploadFile, File, Form
import uvicorn
import copy
import json
import argparse
import io
from astropy.io import fits
from datetime import datetime, timedelta, timezone

app = FastAPI(title="Mock Observation Portal - Multi-Telescope Test")

CURRENT_MODE = "default"
USE_T200 = False
global_counter = 1000
global_obs_counter = 1

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

# Advanced configuration template based on user schema
advanced_obs_template = {
    "site": "tst",
    "enclosure": "doma",
    "telescope": "1m0a",
    "start": "2019-08-24T14:15:22Z",
    "end": "2019-08-24T14:15:22Z",
    "state": "PENDING",
    "configuration_statuses": [
        {
            "id": 0,
            "summary": {
                "start": "2019-08-24T14:15:22Z",
                "end": "2019-08-24T14:15:22Z",
                "state": "PENDING",
                "reason": "string",
                "time_completed": 0,
                "events": {}
            },
            "instrument_name": "MOCK_CAM",
            "guide_camera_name": "string",
            "end": "2019-08-24T14:15:22Z",
            "exposures_start_at": "2019-08-24T14:15:22Z",
            "state": "PENDING",
            "configuration": 0
        }
    ],
    "request": {
        "id": 0,
        "configurations": [
            {
                "id": 0,
                "constraints": {
                    "max_airmass": 1.6,
                    "min_lunar_distance": 30,
                    "max_lunar_phase": 1,
                    "max_seeing": 0,
                    "min_transparency": 0,
                    "extra_params": {}
                },
                "instrument_configs": [
                    {
                        "rois": [
                            {
                                "x1": 2147483647,
                                "x2": 2147483647,
                                "y1": 2147483647,
                                "y2": 2147483647
                            }
                        ],
                        "optical_elements": {},
                        "mode": "IMG",
                        "exposure_time": 5.0,
                        "exposure_count": 1,
                        "rotator_mode": "string",
                        "extra_params": {}
                    }
                ],
                "acquisition_config": {
                    "mode": "string",
                    "exposure_time": 60,
                    "extra_params": {}
                },
                "guiding_config": {
                    "optional": True,
                    "mode": "string",
                    "optical_elements": {},
                    "exposure_time": 120,
                    "extra_params": {}
                },
                "target": {
                    "name": "Target",
                    "type": "ICRS",
                    "hour_angle": 0,
                    "ra": 360,
                    "dec": -90,
                    "altitude": 90,
                    "azimuth": 360,
                    "proper_motion_ra": 20000,
                    "proper_motion_dec": 20000,
                    "epoch": 2100,
                    "parallax": 2000,
                    "diff_altitude_rate": 0,
                    "diff_azimuth_rate": 0,
                    "diff_epoch": 0,
                    "diff_altitude_acceleration": 0,
                    "diff_azimuth_acceleration": 0,
                    "scheme": "ASA_MAJOR_PLANET",
                    "epochofel": 10000,
                    "orbinc": 180,
                    "longascnode": 360,
                    "longofperih": 360,
                    "argofperih": 360,
                    "meandist": 0,
                    "perihdist": 0,
                    "eccentricity": 0,
                    "meanlong": 0,
                    "meananom": 360,
                    "dailymot": 0,
                    "epochofperih": 361,
                    "extra_params": {}
                },
                "instrument_type": "MOCK_CAM",
                "instrument_name": "MOCK_CAM",
                "state": "PENDING",
                "type": "EXPOSE",
                "repeat_duration": 0,
                "extra_params": {},
                "priority": 0,
                "configuration_status": 0
            }
        ],
        "duration": "3600",
        "observation_note": "string",
        "optimization_type": "TIME",
        "state": "PENDING",
        "modified": "2019-08-24T14:15:22Z",
        "created": "2019-08-24T14:15:22Z",
        "acceptability_threshold": 100,
        "configuration_repeats": 1,
        "extra_params": {}
    },
    "proposal": "PROP-03",
    "submitter": "astronomer",
    "ipp_value": 1.0,
    "observation_type": "NORMAL",
    "request_group_id": 3,
    "created": "2019-08-24T14:15:22Z",
    "priority": 1,
    "id": 0,
    "modified": "2019-08-24T14:15:22Z",
    "name": "Obs"
}

@app.get("/api/schedule/")
def get_schedule():
    global global_counter
    global global_obs_counter
    
    now = datetime.now(timezone.utc)
    results = []
    
    targets = [
        {"name": "M43", "ra": 83.858, "dec": -5.269, "type": "MPC_COMET"},
        {"name": "Jupiter", "ra": 0.0, "dec": 0.0, "type": "MPC_PLANET"},
        {"name": "Polaris", "ra": 37.95, "dec": 89.26, "type": "ICRS"}
    ]
    
    for i, t in enumerate(targets):
        obs_start = now + timedelta(seconds=2 + i*30)
        obs_end = obs_start + timedelta(seconds=25)
        
        obs = copy.deepcopy(advanced_obs_template)
        
        # Base metadata
        obs["id"] = global_obs_counter + i
        obs["telescope"] = "T200" if USE_T200 else "T100"
        obs["site"] = "PRL"
        obs["name"] = f"{t['name']} Obs"
        obs["start"] = obs_start.isoformat()
        obs["end"] = obs_end.isoformat()
        
        # Request
        obs["request"]["id"] = obs["id"] * 100
        obs["request"]["observation_note"] = f"{obs['telescope']} Observation {i+1} - {t['name']}"
        obs["request"]["modified"] = now.isoformat()
        obs["request"]["created"] = now.isoformat()
        
        # Configurations
        cfg = obs["request"]["configurations"][0]
        cfg["id"] = global_counter
        cfg["configuration_status"] = global_counter
        global_counter += 1
        
        cfg["target"]["name"] = t["name"]
        cfg["target"]["ra"] = t["ra"]
        cfg["target"]["dec"] = t["dec"]
        cfg["target"]["type"] = t["type"]
        
        # Configuration Status
        obs["configuration_statuses"][0]["id"] = cfg["configuration_status"]
        obs["configuration_statuses"][0]["configuration"] = cfg["id"]
        
        results.append(obs)

    global_obs_counter += len(targets)

    return {
        "results": results
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

@app.post("/pramana_ingest/")
async def mock_pramana_ingest(file: UploadFile = File(...), headers: str = Form(...)):
    print(f"\n[MOCK ARCHIVE] Ingestion Received!")
    print(f"  --> File Name: {file.filename}")
    try:
        header_dict = json.loads(headers)
        
        # Read the file contents into memory
        file_bytes = await file.read()
        
        # Open the FITS file with astropy
        with fits.open(io.BytesIO(file_bytes)) as hdul:
            primary_hdu = hdul[0]
            
            # Merge our JSON headers into the FITS header
            for key, value in header_dict.items():
                fit_key = key.upper()
                if fit_key not in ['SIMPLE', 'BITPIX', 'NAXIS', 'EXTEND', 'END'] and not fit_key.startswith('NAXIS'):
                    primary_hdu.header[fit_key] = value
                    
            print(f"  --> Final Merged FITS Headers:")
            print(f"      - PROPID: {primary_hdu.header.get('PROPID')}")
            print(f"      - OBJECT: {primary_hdu.header.get('OBJECT')}")
            print(f"      - RA:     {primary_hdu.header.get('RA')}")
            print(f"      - DEC:    {primary_hdu.header.get('DEC')}")
            print(f"      - EXPOSURE: {primary_hdu.header.get('EXPOSURE')}")
            print(f"      - DATE-OBS: {primary_hdu.header.get('DATE-OBS')}")
            print(f"      - INSTRUME: {primary_hdu.header.get('INSTRUME')}")
            
    except Exception as e:
        print(f"  --> Failed to process FITS/Headers: {e}")
    return {"status": "success", "message": "File ingested successfully."}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock OCS Server")
    parser.add_argument("--mode", type=str, default="default", help="Test mode: 'default' or 'slewing'")
    parser.add_argument("--T200", dest="use_T200", action="store_true", help="All schedules are for T200 telescope")
    args = parser.parse_args()
    
    CURRENT_MODE = args.mode
    USE_T200 = args.use_T200
    print(f"Starting Mock OCS Server in MODE: {CURRENT_MODE} (USE_T200: {USE_T200})")
    
    uvicorn.run(app, host="127.0.0.1", port=8001)

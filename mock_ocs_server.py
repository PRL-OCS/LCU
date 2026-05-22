from fastapi import FastAPI
import uvicorn

app = FastAPI(title="Mock Observation Portal")

@app.get("/api/instruments/")
def get_instruments():
    return {
        "MOCK_CAM": {
            "class": "T100",
            "name": "MOCK_CAM"
        }
    }

@app.get("/api/schedule/")
def get_schedule():
    return {
        "results": [
            {
                "id": 1,
                "request": {
                    "id": 101,
                    "observation_note": "Mock observation",
                    "state": "PENDING",
                    "acceptability_threshold": 90.0,
                    "modified": "2026-05-22T00:00:00Z",
                    "duration": 3600,
                    "configurations": [
                        {
                            "id": 999,
                            "instrument_type": "MOCK_CAM",
                            "type": "TEST",
                            "priority": 1,
                            "instrument_configs": [
                                {
                                    "mode": "IMG",
                                    "exposure_time": 4.0
                                }
                            ],
                            "target": {
                                "type": "ICRS",
                                "name": "Betelgeuse",
                                "ra": 88.792,
                                "dec": 7.407,
                                "epoch": 2000.0
                            },
                            "configuration_status": 1,
                            "state": "PENDING",
                            "instrument_name": "MOCK_CAM"
                        }
                    ]
                },
                "site": "PRL",
                "enclosure": "DomeA",
                "telescope": "T100",
                "start": "2026-05-22T00:00:00Z",
                "end": "2026-05-22T01:00:00Z",
                "priority": 1,
                "state": "PENDING",
                "proposal": "PROP-01",
                "submitter": "astronomer",
                "name": "Betelgeuse Obs",
                "ipp_value": 1.0,
                "observation_type": "NORMAL",
                "request_group_id": 1,
                "created": "2026-05-22T00:00:00Z",
                "modified": "2026-05-22T00:00:00Z"
            }
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)

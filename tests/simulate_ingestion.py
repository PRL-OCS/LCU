import asyncio
import os
from dotenv import load_dotenv

# Load .env variables so ARCHIVE_API_URL and PRAMANA_API_TOKEN are set
load_dotenv()

from Plugins.instrument.mock_instrument import MockInstrumentPlugin
from core.communications.schemas import Configuration
from core.ingestion.manager import ingestion_manager

async def run_end_to_end_ingestion():
    print("1. Initializing Mock Instrument...")
    plugin = MockInstrumentPlugin("MOCK_CAM")
    
    # Create a dummy configuration envelope
    config = Configuration.model_validate({
        "id": 888,
        "instrument_type": "MOCK_CAM",
        "type": "SCIENCE",
        "priority": 1,
        "instrument_configs": [
            {
                "mode": "Imaging",
                "exposure_time": 2.0,
                "exposure_count": 1
            }
        ],
        "target": {
            "type": "ICRS",
            "name": "Crab Nebula",
            "ra": 83.633,
            "dec": 22.014,
            "epoch": 2000.0,
            "configuration_id": 888
        },
        "configuration_status": 888,
        "state": "PENDING",
        "instrument_name": "MOCK_CAM"
    })
    
    # We need a dummy observation dictionary context to pass to the ingestion queue
    dummy_obs = {
        "id": 999,
        "request": {
            "id": 777,
            "observation_note": "",
            "state": "PENDING",
            "acceptability_threshold": 90.0,
            "extra_params": {},
            "modified": "2026-01-01T00:00:00",
            "duration": 10,
            "configurations": [config.model_dump()]
        },
        "site": "PRL",
        "enclosure": "Dome",
        "telescope": "T100",
        "start": "2026-01-01T00:00:00",
        "end": "2026-01-01T01:00:00",
        "priority": 1,
        "state": "PENDING",
        "proposal": "TEST-PROP-001",
        "submitter": "Test Astronomer",
        "name": "Crab Nebula Obs",
        "ipp_value": 1.0,
        "observation_type": "NORMAL",
        "request_group_id": 10,
        "created": "2026-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00"
    }
    
    print("2. Exposing (this will take ~2 seconds and copy a real FITS file)...")
    file_path = await plugin.expose(config)
    print(f"--> File generated at: {file_path}")
    
    print("\n3. Starting Ingestion Manager Worker Loop...")
    ingestion_manager.start()
    
    print("4. Enqueuing file to Ingestion Manager...")
    await ingestion_manager.enqueue(
        file_path=file_path,
        obs_dict=dummy_obs,
        config_id=config.id,
        telemetry={"current_ra": 83.63, "current_dec": 22.01}
    )
    
    print("\n5. Waiting for ingestion to upload to your Mock Server on port 8001...")
    # Give the background worker 5 seconds to wake up, process the queue, and upload
    for i in range(5):
        await asyncio.sleep(1)
        if len(ingestion_manager.queue) == 0:
            print("--> Queue is empty! Upload must have finished.")
            break
            
    if not os.path.exists(file_path):
        print("--> Success! The local FITS file was successfully purged.")
    else:
        print("--> Upload might have failed. File still exists.")
        
    ingestion_manager.stop()

if __name__ == "__main__":
    asyncio.run(run_end_to_end_ingestion())

import pytest
import os
import asyncio
import json
from datetime import datetime
from pathlib import Path
from core.ingestion.manager import IngestionManager
from core.communications.schemas import ScheduleSchema

@pytest.fixture(autouse=True)
def reset_singleton():
    IngestionManager._instance = None

@pytest.fixture
def mock_storage(tmp_path):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()
    return storage_dir

@pytest.fixture
def dummy_fits(mock_storage):
    file_path = mock_storage / "test_image.fits"
    with open(file_path, "w") as f:
        f.write("MOCK FITS")
    return str(file_path)

@pytest.fixture
def dummy_obs_dict():
    return {
        "id": 100,
        "request": {
            "id": 200,
            "observation_note": "",
            "state": "PENDING",
            "acceptability_threshold": 90.0,
            "extra_params": {},
            "modified": "2026-01-01T00:00:00",
            "duration": 10,
            "configurations": [
                {
                    "id": 1,
                    "instrument_type": "MOCK_CAM",
                    "type": "SCIENCE",
                    "priority": 1,
                    "instrument_configs": [
                        {
                            "mode": "Imaging",
                            "exposure_time": 5.0,
                            "exposure_count": 1,
                            "optical_elements": {"filter": "V"}
                        }
                    ],
                    "target": {
                        "type": "ICRS",
                        "name": "M31",
                        "ra": 10.684,
                        "dec": 41.269,
                        "epoch": 2000.0,
                        "configuration_id": 1
                    },
                    "configuration_status": 1,
                    "state": "PENDING",
                    "instrument_name": "MOCK_CAM"
                }
            ]
        },
        "site": "PRL",
        "enclosure": "Dome",
        "telescope": "1m",
        "start": "2026-01-01T00:00:00",
        "end": "2026-01-01T01:00:00",
        "priority": 1,
        "state": "PENDING",
        "proposal": "PROP-01",
        "submitter": "Test User",
        "name": "Test Obs",
        "ipp_value": 1.0,
        "observation_type": "NORMAL",
        "request_group_id": 10,
        "created": "2026-01-01T00:00:00",
        "modified": "2026-01-01T00:00:00"
    }

@pytest.mark.asyncio
async def test_queue_persistence(mock_storage, dummy_fits, dummy_obs_dict):
    manager1 = IngestionManager(storage_dir=str(mock_storage))
    
    await manager1.enqueue(
        file_path=dummy_fits,
        obs_dict=dummy_obs_dict,
        config_id=1,
        telemetry={"current_ra": 10.68, "current_dec": 41.27}
    )
    
    assert len(manager1.queue) == 1
    assert manager1.queue[0]["status"] == "pending"
    
    # Simulate a crash/restart by creating a new manager instance pointing to the same dir
    IngestionManager._instance = None
    manager2 = IngestionManager(storage_dir=str(mock_storage))
    
    assert len(manager2.queue) == 1
    assert manager2.queue[0]["file_path"] == dummy_fits
    assert manager2.queue[0]["telemetry"]["current_ra"] == 10.68

@pytest.mark.asyncio
async def test_header_generation(mock_storage, dummy_obs_dict):
    manager = IngestionManager(storage_dir=str(mock_storage))
    obs = ScheduleSchema.model_validate(dummy_obs_dict)
    
    headers = manager._generate_headers(obs, 1, {"current_ra": 12.34})
    
    assert headers["PROPID"] == "PROP-01"
    assert headers["OBJECT"] == "M31"
    assert headers["EXPOSURE"] == 5.0
    assert headers["FILTER"] == "V"
    assert headers["RA"] == 12.34  # from telemetry
    assert headers["TRGALPH"] == 10.684  # from target

@pytest.mark.asyncio
async def test_successful_upload_removes_file(mock_storage, dummy_fits, dummy_obs_dict, monkeypatch):
    manager = IngestionManager(storage_dir=str(mock_storage))
    
    await manager.enqueue(dummy_fits, dummy_obs_dict, 1, {})
    
    # Mock the _upload_to_archive method to simulate a success (200 OK)
    async def mock_upload(*args, **kwargs):
        return True
    
    monkeypatch.setattr(manager, "_upload_to_archive", mock_upload)
    
    assert os.path.exists(dummy_fits)
    
    # Start worker and give it a moment to process the queue
    manager.start()
    await asyncio.sleep(0.2)
    manager.stop()
    
    # File should be deleted and queue should be empty
    assert not os.path.exists(dummy_fits)
    assert len(manager.queue) == 0

@pytest.mark.asyncio
async def test_failed_upload_increments_retry(mock_storage, dummy_fits, dummy_obs_dict, monkeypatch):
    manager = IngestionManager(storage_dir=str(mock_storage))
    
    await manager.enqueue(dummy_fits, dummy_obs_dict, 1, {})
    
    # Mock upload to fail
    async def mock_upload(*args, **kwargs):
        return False
    
    monkeypatch.setattr(manager, "_upload_to_archive", mock_upload)
    
    manager.start()
    await asyncio.sleep(0.2)
    manager.stop()
    
    # File should STILL exist, queue should still have item, retry count incremented
    assert os.path.exists(dummy_fits)
    assert len(manager.queue) == 1
    assert manager.queue[0]["retries"] == 1

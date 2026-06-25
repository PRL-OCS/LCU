import pytest
import os
import asyncio
from pathlib import Path
from Plugins.instrument.mock_instrument import MockInstrumentPlugin
from core.communications.schemas import Configuration

@pytest.mark.asyncio
async def test_mock_instrument_real_fits():
    plugin = MockInstrumentPlugin("MOCK_CAM")
    config = Configuration.model_validate({
        "id": 1,
        "instrument_type": "MOCK_CAM",
        "type": "SCIENCE",
        "priority": 1,
        "instrument_configs": [
            {
                "mode": "Imaging",
                "exposure_time": 0.1,
                "exposure_count": 1
            }
        ],
        "target": {
            "type": "ICRS",
            "name": "M31",
            "ra": 10.0,
            "dec": 10.0,
            "epoch": 2000.0,
            "configuration_id": 1
        },
        "configuration_status": 1,
        "state": "PENDING",
        "instrument_name": "MOCK_CAM"
    })
    
    file_path = await plugin.expose(config)
    
    assert os.path.exists(file_path)
    assert file_path.endswith(".fits")
    
    # Check if the file is a valid FITS file (or our fallback text)
    with open(file_path, "r", errors="ignore") as f:
        content = f.read(80)
    assert content.startswith("SIMPLE  =")
    
    # Clean up
    os.remove(file_path)

@pytest.mark.asyncio
async def test_mock_instrument_acquisition():
    plugin = MockInstrumentPlugin("MOCK_CAM")
    
    file_path = await plugin.take_acquisition_image()
    
    assert os.path.exists(file_path)
    assert file_path.endswith(".fits")
    
    with open(file_path, "r", errors="ignore") as f:
        content = f.read(80)
    assert content.startswith("SIMPLE  =")
    
    # Clean up
    os.remove(file_path)

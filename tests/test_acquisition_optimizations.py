import pytest
import asyncio
import datetime
from unittest.mock import AsyncMock, patch

from core.acquisition.manager import AcquisitionManager

class MockTarget:
    def __init__(self, ra, dec, name="Test Target"):
        self.ra = ra
        self.dec = dec
        self.name = name

class MockImage:
    pass

class MockInstrumentPlugin:
    def __init__(self, fov_type='wide'):
        self.fov_type = fov_type
        self.take_acquisition_image = AsyncMock(return_value=MockImage())

class MockTelescopePlugin:
    def __init__(self):
        self.correct_pointing = AsyncMock()
        self.hop_success = True

@pytest.mark.asyncio
async def test_seeded_solve_receives_hints():
    manager = AcquisitionManager()
    target = MockTarget(10.0, 20.0)
    
    # We patch the internal _try_plate_solve to ensure it uses target as a hint
    with patch.object(manager, '_try_plate_solve', new_callable=AsyncMock) as mock_solve:
        mock_solve.return_value = (10.0, 20.0) # Perfect hit
        
        telescope = MockTelescopePlugin()
        instrument = MockInstrumentPlugin()
        
        await manager.acquire_target(target, telescope, instrument)
        
        # Verify it passed the target to the solver for hinting
        mock_solve.assert_called_once()
        args, kwargs = mock_solve.call_args
        assert args[1] == target

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock

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
        self.active_pointing_model = False

    def has_active_pointing_model(self):
        return self.active_pointing_model

    async def get_pointing_model_coordinates(self, target_ra, target_dec):
        return target_ra, target_dec

@pytest.mark.asyncio
async def test_wide_fov_success():
    manager = AcquisitionManager()
    manager.tolerance_arcsec = 5.0
    
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    instrument = MockInstrumentPlugin(fov_type='wide')
    
    # Mock the image to return a successful plate solve within tolerance
    # Let's say it's off by 2 arcseconds, which is <= 5.0 tolerance
    img = MockImage()
    img.plate_solve_result = (10.0 + 2.0, 20.0)
    instrument.take_acquisition_image.return_value = img
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    # Correct pointing should NOT be called because error is 2.0 <= 5.0
    telescope.correct_pointing.assert_not_called()

@pytest.mark.asyncio
async def test_wide_fov_plate_solve_correction():
    manager = AcquisitionManager()
    manager.tolerance_arcsec = 5.0
    
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    instrument = MockInstrumentPlugin(fov_type='wide')
    
    # First image returns 10 arcsec error (requires correction)
    img1 = MockImage()
    img1.plate_solve_result = (10.0 + 10.0, 20.0)
    
    # Second image returns 2 arcsec error (success)
    img2 = MockImage()
    img2.plate_solve_result = (10.0 + 2.0, 20.0)
    
    instrument.take_acquisition_image.side_effect = [img1, img2]
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    assert instrument.take_acquisition_image.call_count == 2
    telescope.correct_pointing.assert_called_once_with(
        target_ra=10.0, target_dec=20.0, actual_ra=20.0, actual_dec=20.0
    )

@pytest.mark.asyncio
async def test_narrow_fov_skips_plate_solve():
    manager = AcquisitionManager()
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    instrument = MockInstrumentPlugin(fov_type='narrow')
    
    img = MockImage()
    img.plate_solve_result = (10.0 + 10.0, 20.0) # Should be ignored
    img.pattern_match_result = (10.0 + 1.0, 20.0) # Success
    instrument.take_acquisition_image.return_value = img
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    telescope.correct_pointing.assert_not_called()

@pytest.mark.asyncio
async def test_all_fallback_to_star_hop():
    manager = AcquisitionManager()
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    instrument = MockInstrumentPlugin(fov_type='wide')
    
    # Image 1: Fails Plate Solve AND Pattern Match
    img1 = MockImage()
    img1.plate_solve_result = (None, None)
    img1.pattern_match_result = (None, None)
    
    # Image 2: After star hop, it finds the target via pattern match
    img2 = MockImage()
    img2.plate_solve_result = (None, None)
    img2.pattern_match_result = (10.0 + 1.0, 20.0)
    
    instrument.take_acquisition_image.side_effect = [img1, img2]
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    assert instrument.take_acquisition_image.call_count == 2

@pytest.mark.asyncio
async def test_pattern_match_kdtree_logic():
    manager = AcquisitionManager()
    target = MockTarget(10.0, 20.0) # Requested Target
    
    # Simulate calling _try_pattern_match with a mock image that DOESN'T have a mocked return
    # so it falls through to the real KDTree math
    img = MockImage()
    
    # We expect the median shift to be X=-50, Y=20 based on the mock functions in manager.py:
    # observed: [150, 180], catalog: [100, 200]
    # shift = catalog - observed = [-50, +20]
    # pixel scale = 0.5 arcsec/pixel
    # offset_ra_arcsec = -25.0 arcsec
    # offset_dec_arcsec = +10.0 arcsec
    # actual_ra = 10.0 - (-25.0 / 3600.0) = 10.00694
    # actual_dec = 20.0 - (10.0 / 3600.0) = 19.99722
    
    actual_ra, actual_dec = await manager._try_pattern_match(img, target)
    
    assert actual_ra is not None
    assert round(actual_ra, 5) == 10.00694
    assert round(actual_dec, 5) == 19.99722

import pytest
import asyncio
import numpy as np
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
        self.pixel_scale = 0.5
        self.image_width = 2048
        self.image_height = 2048
        self.take_acquisition_image = AsyncMock(return_value=MockImage())

class MockTelescopePlugin:
    def __init__(self):
        self.correct_pointing = AsyncMock()
        self.slew_to_target = AsyncMock()
        self.start_tracking = AsyncMock()
        self.hop_success = True
        self.active_pointing_model = False

    def has_active_pointing_model(self):
        return self.active_pointing_model

    async def get_pointing_model_coordinates(self, target_ra, target_dec):
        return target_ra, target_dec


# Helper: convert arcsec offset in RA to degrees at a given declination
def ra_offset_arcsec_to_deg(arcsec, dec_deg):
    """Convert an RA offset in arcseconds to a degree offset, accounting for cos(dec)."""
    cos_dec = np.cos(np.radians(dec_deg))
    return arcsec / (3600.0 * cos_dec)


@pytest.mark.asyncio
async def test_wide_fov_success():
    """Plate solve returns coordinates within tolerance → acquisition succeeds."""
    manager = AcquisitionManager()
    manager.tolerance_arcsec = 5.0
    
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    instrument = MockInstrumentPlugin(fov_type='wide')
    
    # 2 arcsec offset in RA (within 5.0 arcsec tolerance)
    offset_deg = ra_offset_arcsec_to_deg(2.0, 20.0)
    img = MockImage()
    img.plate_solve_result = (10.0 + offset_deg, 20.0)
    instrument.take_acquisition_image.return_value = img
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    # Correct pointing should NOT be called because error is within tolerance
    telescope.correct_pointing.assert_not_called()


@pytest.mark.asyncio
async def test_wide_fov_plate_solve_correction():
    """First solve exceeds tolerance, correction is applied, second solve is within tolerance."""
    manager = AcquisitionManager()
    manager.tolerance_arcsec = 5.0
    
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    instrument = MockInstrumentPlugin(fov_type='wide')
    
    # First image: 10 arcsec offset in Dec (exceeds tolerance)
    img1 = MockImage()
    img1.plate_solve_result = (10.0, 20.0 + 10.0 / 3600.0)
    
    # Second image: 2 arcsec offset in Dec (within tolerance)
    img2 = MockImage()
    img2.plate_solve_result = (10.0, 20.0 + 2.0 / 3600.0)
    
    instrument.take_acquisition_image.side_effect = [img1, img2]
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    assert instrument.take_acquisition_image.call_count == 2
    telescope.correct_pointing.assert_called_once_with(
        target_ra=10.0, target_dec=20.0,
        actual_ra=10.0, actual_dec=pytest.approx(20.0 + 10.0 / 3600.0)
    )


@pytest.mark.asyncio
async def test_narrow_fov_skips_plate_solve():
    """Narrow FOV instruments skip plate solve and go directly to pattern match."""
    manager = AcquisitionManager()
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    instrument = MockInstrumentPlugin(fov_type='narrow')
    
    # 1 arcsec offset in Dec (within default 5.0 tolerance)
    img = MockImage()
    img.plate_solve_result = (10.0 + 10.0, 20.0)  # Should be IGNORED for narrow FOV
    img.pattern_match_result = (10.0, 20.0 + 1.0 / 3600.0)  # Success via pattern match
    instrument.take_acquisition_image.return_value = img
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    telescope.correct_pointing.assert_not_called()


@pytest.mark.asyncio
async def test_all_fallback_to_star_hop():
    """When plate solve and pattern match both fail, bright star hop is triggered."""
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
    img2.pattern_match_result = (10.0, 20.0 + 1.0 / 3600.0)  # 1 arcsec offset
    
    # Image 3: A third image is needed if the hop consumes one in verification.
    # But with the mock fast-path (hop_success attribute), the hop doesn't take images.
    # So we just need img1 (fail) + img2 (success after hop).
    instrument.take_acquisition_image.side_effect = [img1, img2]
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    assert instrument.take_acquisition_image.call_count == 2


@pytest.mark.asyncio
async def test_pattern_match_kdtree_logic():
    """
    Tests the KDTree math directly using the mock fallback data in manager.py.
    
    The mock functions return:
      observed: [150, 180], [350, 480], [550, 880]
      catalog:  [100, 200], [300, 500], [500, 900]
      
    Median shift = catalog - observed = [-50, +20]
    pixel_scale = 0.5 arcsec/pixel
    offset_ra_arcsec = -25.0 arcsec
    offset_dec_arcsec = +10.0 arcsec
    
    With cos(dec) correction at dec=20.0:
      cos(20°) ≈ 0.93969
      actual_ra  = 10.0 - (-25.0 / (3600.0 * cos(20°)))
      actual_dec = 20.0 - (10.0 / 3600.0) 
    """
    manager = AcquisitionManager()
    target = MockTarget(10.0, 20.0)
    
    # Use a MockImage WITHOUT pattern_match_result so it falls through to real KDTree
    img = MockImage()
    
    actual_ra, actual_dec = await manager._try_pattern_match(img, target)
    
    assert actual_ra is not None
    
    # Compute expected values with cos(dec) correction
    cos_dec = np.cos(np.radians(20.0))
    expected_ra = 10.0 - (-25.0 / (3600.0 * cos_dec))
    expected_dec = 20.0 - (10.0 / 3600.0)
    
    assert actual_ra == pytest.approx(expected_ra, abs=1e-7)
    assert actual_dec == pytest.approx(expected_dec, abs=1e-7)


@pytest.mark.asyncio
async def test_angular_separation_utility():
    """Test the Vincenty angular separation calculation."""
    # Same point → 0 arcsec
    sep = AcquisitionManager._angular_separation_arcsec(10.0, 20.0, 10.0, 20.0)
    assert sep == pytest.approx(0.0, abs=0.001)
    
    # 1 degree separation in Dec → 3600 arcsec
    sep = AcquisitionManager._angular_separation_arcsec(10.0, 20.0, 10.0, 21.0)
    assert sep == pytest.approx(3600.0, abs=0.1)
    
    # Small separation: 1 arcsec in Dec
    sep = AcquisitionManager._angular_separation_arcsec(10.0, 20.0, 10.0, 20.0 + 1.0/3600.0)
    assert sep == pytest.approx(1.0, abs=0.01)


@pytest.mark.asyncio
async def test_pointing_model_success():
    """Test that pointing model short-circuits acquisition when error is within tolerance."""
    manager = AcquisitionManager()
    manager.tolerance_arcsec = 5.0
    
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    telescope.active_pointing_model = True  # Enable pointing model
    instrument = MockInstrumentPlugin()
    
    # The mock returns exact coordinates (0 error), so it should succeed immediately
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is True
    # No acquisition image should have been taken
    instrument.take_acquisition_image.assert_not_called()


@pytest.mark.asyncio
async def test_acquisition_failure_after_max_iterations():
    """Acquisition fails after max_iterations if offset never converges."""
    manager = AcquisitionManager()
    manager.tolerance_arcsec = 1.0
    manager.max_iterations = 2
    
    target = MockTarget(10.0, 20.0)
    telescope = MockTelescopePlugin()
    instrument = MockInstrumentPlugin(fov_type='wide')
    
    # Always return 100 arcsec offset (way above 1.0 tolerance)
    img = MockImage()
    img.plate_solve_result = (10.0, 20.0 + 100.0 / 3600.0)
    instrument.take_acquisition_image.return_value = img
    
    success = await manager.acquire_target(target, telescope, instrument)
    
    assert success is False
    assert instrument.take_acquisition_image.call_count == 2
    assert telescope.correct_pointing.call_count == 2

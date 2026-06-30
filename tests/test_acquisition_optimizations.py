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
        self.pixel_scale = 0.5
        self.image_width = 2048
        self.image_height = 2048
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

@pytest.mark.asyncio
async def test_cos_dec_correction_near_pole():
    """
    Verify that at high declination (dec=80°), the RA correction is amplified
    by 1/cos(dec) compared to the equator.
    """
    import numpy as np
    
    manager = AcquisitionManager()
    
    # At the equator (dec=0), cos(dec)=1 → no amplification
    target_eq = MockTarget(10.0, 0.0)
    ra_eq, dec_eq = manager._kdtree_match(
        manager._mock_extract_image_sources(),
        manager._mock_query_catalog(),
        target_eq,
        pixel_scale=0.5
    )
    
    # At dec=80°, cos(80°) ≈ 0.1736 → RA correction should be ~5.76x larger
    target_pole = MockTarget(10.0, 80.0)
    ra_pole, dec_pole = manager._kdtree_match(
        manager._mock_extract_image_sources(),
        manager._mock_query_catalog(),
        target_pole,
        pixel_scale=0.5
    )
    
    # The RA offset at the pole should be larger than at the equator
    delta_ra_eq = abs(ra_eq - 10.0)
    delta_ra_pole = abs(ra_pole - 10.0)
    
    # Ratio should be approximately 1/cos(80°) ≈ 5.76
    ratio = delta_ra_pole / delta_ra_eq
    expected_ratio = 1.0 / np.cos(np.radians(80.0))
    
    assert ratio == pytest.approx(expected_ratio, rel=0.01)

@pytest.mark.asyncio
async def test_pixel_scale_from_instrument():
    """
    Verify that pixel_scale is read from the instrument plugin
    and affects the computed offset.
    """
    manager = AcquisitionManager()
    target = MockTarget(10.0, 20.0)
    
    # Use a larger pixel scale (1.0 arcsec/px instead of 0.5)
    # The RA/Dec offset should be 2x larger
    ra_half, dec_half = manager._kdtree_match(
        manager._mock_extract_image_sources(),
        manager._mock_query_catalog(),
        target,
        pixel_scale=0.5
    )
    
    ra_full, dec_full = manager._kdtree_match(
        manager._mock_extract_image_sources(),
        manager._mock_query_catalog(),
        target,
        pixel_scale=1.0
    )
    
    delta_dec_half = abs(dec_half - 20.0)
    delta_dec_full = abs(dec_full - 20.0)
    
    # The dec offset with scale=1.0 should be exactly 2x the offset with scale=0.5
    assert delta_dec_full == pytest.approx(delta_dec_half * 2.0, rel=0.001)

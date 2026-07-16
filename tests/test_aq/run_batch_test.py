import os
import sys
import asyncio
import numpy as np
from astropy.io import fits
import types

# Ensure LCU root is in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from core.acquisition.manager import AcquisitionManager
from core.communications.schemas import Target

class CustomInstrumentPlugin:
    def __init__(self, pixel_scale, width, height):
        self.pixel_scale = pixel_scale
        self.image_width = width
        self.image_height = height
        self.fov_type = 'narrow'

def patched_query_catalog(self, target, fov_size=10.43, pixel_scale=0.5, image_width=658, image_height=492, force_mock=False, **kwargs):
    if force_mock:
        return self._mock_query_catalog()
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    coord = SkyCoord(ra=target.ra * u.deg, dec=target.dec * u.deg)
    radius = fov_size * u.arcmin
    vizier = Vizier(columns=['RA_ICRS', 'DE_ICRS', 'Gmag'], row_limit=1000)
    result = vizier.query_region(coord, radius=radius, catalog='I/355/gaiadr3')
    if not result or len(result) == 0:
        return np.array([])
    table = result[0]
    cat_ra = np.array(table['RA_ICRS'], dtype=np.float64)
    cat_dec = np.array(table['DE_ICRS'], dtype=np.float64)
    cx, cy = image_width / 2.0, image_height / 2.0
    cos_dec = np.cos(np.radians(target.dec))
    delta_ra_deg = (cat_ra - target.ra) * cos_dec
    delta_dec_deg = cat_dec - target.dec
    x_pix = cx - (delta_ra_deg * 3600.0) / pixel_scale
    y_pix = cy + (delta_dec_deg * 3600.0) / pixel_scale
    return np.column_stack((x_pix, y_pix))

async def test_file(filename, target_ra, target_dec, pixel_scale):
    fits_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    if not os.path.exists(fits_file):
        print(f"[ERROR] File not found: {fits_file}")
        return

    print(f"\n==================== Testing File: {filename} ====================")
    with fits.open(fits_file) as hdul:
        hdr = hdul[0].header
        width = hdr.get("NAXIS1", 658)
        height = hdr.get("NAXIS2", 492)
        print(f"Image Resolution: {width} x {height} | Exposure: {hdr.get('EXPTIME', 'N/A')}s")

    manager = AcquisitionManager()
    manager._query_catalog = types.MethodType(patched_query_catalog, manager)
    instrument = CustomInstrumentPlugin(pixel_scale, width, height)
    target = Target(name="M31", ra=target_ra, dec=target_dec, type="ICRS", epoch=2000.0)

    # 1. Centroid Extraction
    observed_points = manager._extract_image_sources(fits_file)
    print(f"SEP successfully extracted {len(observed_points)} star centroids.")

    # 2. KD-Tree Matcher
    solved_model_ra, solved_model_dec = await manager._try_pattern_match(fits_file, target, instrument)

    if solved_model_ra is not None and solved_model_dec is not None:
        print("[SUCCESS] KD-Tree Pattern Match solver converged!")
        print(f"  Solved Coordinates: RA = {solved_model_ra:.6f} deg, DEC = {solved_model_dec:.6f} deg")
        error_arcsec = manager._angular_separation_arcsec(target.ra, target.dec, solved_model_ra, solved_model_dec)
        print(f"  Pointing Error Offset: {error_arcsec:.2f} arcseconds")
    else:
        print("[FAILURE] KD-Tree solver did not converge.")

async def main():
    target_ra = 10.684
    target_dec = 41.269
    pixel_scale = 0.5
    
    await test_file("test_1_aq.fit", target_ra, target_dec, pixel_scale)
    await test_file("test_2_aq.fit", target_ra, target_dec, pixel_scale)
    await test_file("test_3_aq.fit", target_ra, target_dec, pixel_scale)

if __name__ == '__main__':
    asyncio.run(main())

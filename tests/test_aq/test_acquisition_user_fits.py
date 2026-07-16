import os
import sys
import asyncio
import numpy as np
from astropy.io import fits
from astroquery.vizier import Vizier
from astropy.coordinates import SkyCoord
import astropy.units as u

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

def get_astrometry_key():
    """Retrieve API key from env variable or cmd arguments."""
    key = os.environ.get("ASTROMETRY_API_KEY")
    for arg in sys.argv:
        if arg.startswith("--key="):
            key = arg.split("=")[1]
    return key

async def main():
    print("=========================================================")
    print("  VERIFYING LCU TARGET ACQUISITION ON USER FITS FILES")
    print("=========================================================\n")

    fits_file = r"d:\PRL\LCU-main\LCU-main\tests\test_aq\test_1_aq.fit"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        fits_file = sys.argv[1]

    if not os.path.exists(fits_file):
        print(f"[ERROR] Specified FITS file not found: {fits_file}")
        print("Usage: py tests/test_aq/test_acquisition_user_fits.py [path_to_fits] [--key=your_astrometry_net_api_key]")
        return

    print(f"Loading FITS file: {fits_file}")
    with fits.open(fits_file) as hdul:
        hdr = hdul[0].header
        width = hdr.get("NAXIS1", 658)
        height = hdr.get("NAXIS2", 492)
        print(f"Image Resolution: {width} x {height}")
        print(f"Exposure Time:    {hdr.get('EXPTIME', 'N/A')}s")
        print(f"Date Observed:    {hdr.get('DATE-OBS', 'N/A')}")
        print(f"Pixel Size:       {hdr.get('XPIXSZ', 7.4)} x {hdr.get('YPIXSZ', 7.4)} um")

    # 1. Plate Solve to obtain target coordinates
    api_key = get_astrometry_key()
    solved_ra = None
    solved_dec = None
    pixel_scale = None

    if api_key:
        print("\n--- Step 1: Solving Coordinates Online (Astrometry.net) ---")
        try:
            from astroquery.astrometry_net import AstrometryNet
            astrometry = AstrometryNet()
            astrometry.api_key = api_key
            
            print("Uploading image to Astrometry.net (this might take 30-60 seconds)...")
            wcs_header = astrometry.solve_from_image(fits_file)
            
            if wcs_header:
                print("[SUCCESS] Image solved successfully!")
                wcs = wcs_header
                solved_ra = wcs.get("CRVAL1")
                solved_dec = wcs.get("CRVAL2")
                # Calculate pixel scale from CD matrix
                if "CD1_1" in wcs:
                    pixel_scale = np.sqrt(wcs["CD1_1"]**2 + wcs["CD1_2"]**2) * 3600.0
                elif "CDELT1" in wcs:
                    pixel_scale = abs(wcs["CDELT1"]) * 3600.0
                else:
                    pixel_scale = 0.5  # fallback default
                
                print(f"  Solved Center RA:   {solved_ra:.6f} deg")
                print(f"  Solved Center Dec:  {solved_dec:.6f} deg")
                print(f"  Solved Pixel Scale: {pixel_scale:.4f} arcsec/pixel")
            else:
                print("[WARNING] Astrometry.net returned empty result. Please check image quality.")
        except Exception as e:
            print(f"[ERROR] Failed to solve image online: {e}")
    else:
        print("\n--- Step 1: Coordinates (No Astrometry.net API Key Provided) ---")
        print("To automatically resolve coordinates online, please provide an API key using:")
        print("  py tests/test_aq/test_acquisition_user_fits.py [fits_file] --key=YOUR_API_KEY")
        print("\nOr, enter target coordinates manually to test KD-Tree matching:")
        try:
            ra_input = input("Enter Target RA (deg) [e.g., 10.684]: ").strip()
            dec_input = input("Enter Target Dec (deg) [e.g., 41.269]: ").strip()
            scale_input = input("Enter Pixel Scale (arcsec/px) [default 0.5]: ").strip()
            
            solved_ra = float(ra_input) if ra_input else 10.684
            solved_dec = float(dec_input) if dec_input else 41.269
            pixel_scale = float(scale_input) if scale_input else 0.5
        except ValueError:
            print("[ERROR] Invalid numeric input. Using defaults (M31 coordinates).")
            solved_ra = 10.684
            solved_dec = 41.269
            pixel_scale = 0.5

    # 2. Extract sources locally
    print("\n--- Step 2: Star Centroid Extraction (Local SEP) ---")
    manager = AcquisitionManager()
    instrument = CustomInstrumentPlugin(pixel_scale, width, height)
    target = Target(name="Acq Test Target", ra=solved_ra, dec=solved_dec, type="ICRS", epoch=2000.0)

    # Monkeypatch manager._query_catalog to query 1000 rows to avoid Vizier truncation issues
    import types
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

    manager._query_catalog = types.MethodType(patched_query_catalog, manager)

    observed_points = manager._extract_image_sources(fits_file)
    print(f"SEP successfully extracted {len(observed_points)} star centroids.")
    for idx, pt in enumerate(observed_points[:5]):
        print(f"  [{idx+1}] X={pt[0]:.2f}, Y={pt[1]:.2f}")

    if len(observed_points) < 3:
        print("[ERROR] Less than 3 stars detected in the image. Target acquisition requires at least 3 stars.")
        return

    # 3. Query catalog and run KD-Tree matcher
    print("\n--- Step 3: Running LCU KD-Tree Matcher ---")
    solved_model_ra, solved_model_dec = await manager._try_pattern_match(fits_file, target, instrument)

    if solved_model_ra is not None and solved_model_dec is not None:
        print("\n=========================================================")
        print("[SUCCESS] KD-Tree Pattern Match solver converged!")
        print("=========================================================")
        print(f"Solved Coordinates: RA = {solved_model_ra:.6f} deg, DEC = {solved_model_dec:.6f} deg")
        
        error_arcsec = manager._angular_separation_arcsec(target.ra, target.dec, solved_model_ra, solved_model_dec)
        print(f"Calculated pointing error offset: {error_arcsec:.2f} arcseconds")
        print(f"  dRA  = {(solved_model_ra - target.ra) * 3600.0 * np.cos(np.radians(target.dec)):.2f} arcsec")
        print(f"  dDec = {(solved_model_dec - target.dec) * 3600.0:.2f} arcsec")
    else:
        print("\n=========================================================")
        print("[FAILURE] KD-Tree solver did not converge.")
        print("=========================================================")
        print("Hints for resolving failure:")
        print("1. Ensure your manually-entered Target RA/Dec is close to the actual field center (within ~15-30 arcseconds).")
        print("2. Ensure the pixel scale is set correctly (e.g. calculated using focal length and pixel size).")

if __name__ == '__main__':
    asyncio.run(main())

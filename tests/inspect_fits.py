import os
from astropy.io import fits
import numpy as np

downloads_dir = r"d:\aaaaaaaaaaa\AtikCamerasSDK_2025_11_11_Master_2111\src\server\downloads"
for f in os.listdir(downloads_dir):
    if f.endswith('.fit'):
        fits_path = os.path.join(downloads_dir, f)
        print(f"\n=== File: {f} ===")
        try:
            with fits.open(fits_path) as hdul:
                hdr = hdul[0].header
                print(f"INSTRUME = {hdr.get('INSTRUME')}")
                print(f"DATAMIN  = {hdr.get('DATAMIN')}")
                print(f"DATAMAX  = {hdr.get('DATAMAX')}")
                print(f"NAXIS1   = {hdr.get('NAXIS1')}")
                print(f"NAXIS2   = {hdr.get('NAXIS2')}")
                
                data = hdul[0].data
                print(f"Shape: {data.shape}, Type: {data.dtype}")
                print(f"Real Min: {np.min(data)}, Real Max: {np.max(data)}")
                # Check if data contains simulated star pattern or uniform values
                unique_vals = len(np.unique(data))
                print(f"Unique values: {unique_vals}")
        except Exception as e:
            print(f"Error: {e}")


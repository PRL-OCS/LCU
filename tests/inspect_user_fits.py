import os
from astropy.io import fits
import numpy as np

fits_path = r"D:\PRL\lisa_testtt.fit"
if os.path.exists(fits_path):
    print("=== Standard File Analysis ===")
    try:
        with fits.open(fits_path) as hdul:
            hdr = hdul[0].header
            for key, val in hdr.items():
                print(f"{key:8} = {val}")
            
            data = hdul[0].data
            print("\n=== DATA STATS ===")
            print(f"Data type: {data.dtype}")
            print(f"Shape: {data.shape}")
            print(f"Min: {np.min(data)}")
            print(f"Max: {np.max(data)}")
            print(f"Mean: {np.mean(data)}")
            print(f"Std: {np.std(data)}")
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"File not found: {fits_path}")

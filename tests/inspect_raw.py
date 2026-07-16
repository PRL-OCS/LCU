import os
import numpy as np

downloads_dir = r"d:\aaaaaaaaaaa\AtikCamerasSDK_2025_11_11_Master_2111\src\server\downloads"
for f in os.listdir(downloads_dir):
    if f.endswith('.raw'):
        raw_path = os.path.join(downloads_dir, f)
        print(f"\n=== Raw File: {f} ===")
        try:
            data = np.fromfile(raw_path, dtype=np.uint16)
            print(f"Size: {data.size} pixels")
            print(f"Min: {np.min(data)}")
            print(f"Max: {np.max(data)}")
            print(f"Mean: {np.mean(data)}")
            print(f"Unique values: {len(np.unique(data))}")
        except Exception as e:
            print(f"Error: {e}")

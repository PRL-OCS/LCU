import os
import sys
import asyncio
import requests

# Ensure LCU root is in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.instrument.LISA.instrument_plugin import LISACameraPlugin

class TestLISACameraPlugin(LISACameraPlugin):
    """
    Subclass LISACameraPlugin to supply a dummy implementation
    of the abstract take_acquisition_image method. This allows
    us to safely test connection without modifying core files.
    """
    async def take_acquisition_image(self, exposure_time: float = 5.0, binning: int = 2) -> str:
        print(f"[TEST] take_acquisition_image called (exp={exposure_time}s, binning={binning}x{binning})")
        return "dummy_path"

async def test_connection():
    print("=========================================")
    print("  LISA CONNECTION QUICK TEST")
    print("=========================================\n")
    
    api_url = os.environ.get("LISA_API_URL", "http://127.0.0.1:8000")
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
        if not api_url.startswith("http"):
            api_url = f"http://{api_url}"
            if ":" not in api_url.replace("http://", ""):
                api_url = f"{api_url}:8000"
                
    print(f"Checking connectivity to: {api_url}")
    
    # 1. Simple HTTP Health Check
    try:
        resp = requests.get(f"{api_url}/", timeout=3)
        print(f"[SUCCESS] Server is reachable! HTTP status code: {resp.status_code}")
        try:
            data = resp.json()
            print(f"Server response data: {data}")
        except Exception:
            print("Response is not JSON, but server is alive.")
    except Exception as e:
        print(f"[FAILURE] Cannot connect to API server at {api_url}.")
        print(f"Error details: {e}")
        return

    # 2. Instantiate TestLISACameraPlugin (triggers startup connect)
    print("\nInitializing TestLISACameraPlugin...")
    try:
        plugin = TestLISACameraPlugin(instrument_name="LISA", api_url=api_url)
        
        # Give a small delay
        await asyncio.sleep(1)
        
        # Try to query camera info
        print("\nQuerying camera info...")
        info = await plugin.get_camera_info()
        print(f"Camera Info: {info}")
        
        print("\nQuerying camera temperature...")
        temp = await plugin.get_temperature()
        print(f"Camera Temperature: {temp}")
        
        if info is not None:
            print("\n[SUCCESS] Connection and camera query succeeded!")
        else:
            print("\n[FAILURE] Plugin initialized, but failed to retrieve camera info.")
            
        print("\nDisconnecting...")
        await plugin.disconnect()
        print("Disconnected successfully.")
        
    except Exception as e:
        print(f"\n[FAILURE] Exception during plugin connection test: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())

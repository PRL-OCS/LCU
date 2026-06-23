import os
import sys
import time
import asyncio

# Ensure LCU root is in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.telescope.T1P2.telescope_plugin import T1P2TelescopePlugin

def format_ra(deg):
    hours = deg / 15.0
    h = int(hours)
    m = int((hours - h) * 60)
    s = (hours - h - m/60.0) * 3600
    return f"{h:02d}h {m:02d}m {s:04.1f}s"

def format_dec(deg):
    sign = '+' if deg >= 0 else '-'
    deg = abs(deg)
    d = int(deg)
    m = int((deg - d) * 60)
    s = (deg - d - m/60.0) * 3600
    return f"{sign}{d:02d}° {m:02d}' {s:04.1f}\""

async def main():
    print("=" * 60)
    print("  LCU LIVE TELEMETRY MONITOR (1.2m Telescope / Skychart)")
    print("=" * 60)
    print("Initializing plugin...")
    
    # Initialize the 1.2m T1P2 plugin
    # Setting cache time to 0.0 inside script to bypass caching for pure live monitoring
    plugin = T1P2TelescopePlugin(telescope_id="1m2")
    plugin._last_telemetry_time = -9999.0
    
    print("\nStarting live telemetry loop. Press Ctrl+C to stop.\n")
    print(f"{'TIMESTAMP':<20} | {'CONN':<5} | {'ONLINE':<6} | {'SLEW':<5} | {'TRACK':<5} | {'RA (deg)':<10} | {'DEC (deg)':<10} | {'COORDINATES'}")
    print("-" * 115)
    
    try:
        while True:
            # Bypass cache for live console query
            plugin._last_telemetry_time = 0.0
            
            telemetry = plugin.get_current_telemetry()
            
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            ra_deg = telemetry["ra"]
            dec_deg = telemetry["dec"]
            
            coord_str = f"RA: {format_ra(ra_deg)} | DEC: {format_dec(dec_deg)}"
            
            print(f"{ts:<20} | "
                  f"{str(telemetry['is_connected']):<5} | "
                  f"{str(telemetry['skychart_online']):<6} | "
                  f"{str(telemetry['is_slewing']):<5} | "
                  f"{str(telemetry['is_tracking']):<5} | "
                  f"{ra_deg:<10.4f} | "
                  f"{dec_deg:<10.4f} | "
                  f"{coord_str}")
                  
            await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    finally:
        # Stop background thread drivers if any
        plugin.driver.disconnect()

if __name__ == "__main__":
    asyncio.run(main())

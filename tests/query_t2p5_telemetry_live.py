import os
import sys
import time
import asyncio
import argparse
import socket
from unittest.mock import patch

# Ensure LCU root is in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.telescope.T2P5.telescope_plugin import DefaultTelescope
from tests.test_telnet_mock_service import MockTelnetServer

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
    parser = argparse.ArgumentParser(description="Query T2P5 Telemetry Continuously")
    parser.add_argument("--live", action="store_true", help="Connect directly to the live telescope hardware")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds")
    args = parser.parse_args()

    server = None
    connect_patcher = None

    if not args.live:
        print("\n*** RUNNING IN MOCK SERVER MODE ***")
        print("Starting mock Telnet server...")
        server = MockTelnetServer()
        server.start()
        # Seed mock coordinates
        server.current_ra = 10.0  # 150 deg
        server.current_dec = 30.0
        server.target_ra = 10.0
        server.target_dec = 30.0
        time.sleep(0.2)

        # Redirect socket connections
        original_connect = socket.socket.connect

        def mock_connect(self_sock, address):
            host, port = address
            if host == "172.16.20.221" and int(port) == 7280:
                return original_connect(self_sock, ("127.0.0.1", server.port))
            return original_connect(self_sock, address)

        connect_patcher = patch.object(socket.socket, "connect", mock_connect)
        connect_patcher.start()
    else:
        print("\n*** RUNNING IN LIVE HARDWARE MODE ***")
        print("Connecting to live hardware at 172.16.20.221:7280...")

    print("=" * 115)
    print("  LCU T2P5 TELEMETRY MONITOR")
    print("=" * 115)
    print("Initializing plugin...")

    try:
        plugin = DefaultTelescope(telescope_id="T2P5")
    except Exception as e:
        print(f"Failed to initialize T2P5 plugin: {e}")
        if server:
            server.stop()
        if connect_patcher:
            connect_patcher.stop()
        return

    print("\nStarting live telemetry loop. Press Ctrl+C to stop.\n")
    print(f"{'TIMESTAMP':<20} | {'CONN':<5} | {'SLEW':<5} | {'TRACK':<5} | {'RA (deg)':<10} | {'DEC (deg)':<10} | {'COORDINATES'}")
    print("-" * 115)

    try:
        # Sleep for a bit to let first telemetry cycle run
        await asyncio.sleep(0.5)
        while True:
            telemetry = plugin.get_current_telemetry()
            
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            ra_deg = telemetry.get("ra", 0.0)
            dec_deg = telemetry.get("dec", 0.0)
            
            coord_str = f"RA: {format_ra(ra_deg)} | DEC: {format_dec(dec_deg)}"
            
            print(f"{ts:<20} | "
                  f"{str(telemetry.get('connected', False)):<5} | "
                  f"{str(telemetry.get('slewing', False)):<5} | "
                  f"{str(telemetry.get('tracking', False)):<5} | "
                  f"{ra_deg:<10.4f} | "
                  f"{dec_deg:<10.4f} | "
                  f"{coord_str}")
                  
            # If in mock mode, simulate a small random drift or coordinate changes periodically to see it update
            if not args.live and server:
                with server.lock:
                    # Let's add a tiny drift to current_ra (hours) and current_dec (degrees)
                    server.current_ra = (server.current_ra + 0.001) % 24.0
                    server.current_dec = min(max(server.current_dec + 0.0015, -90.0), 90.0)

            await asyncio.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    finally:
        # Clean up
        plugin.driver.disconnect()
        if connect_patcher:
            connect_patcher.stop()
        if server:
            server.stop()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

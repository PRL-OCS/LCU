import os
import sys
import time
import socket
import argparse
import unittest
import asyncio
import threading
from unittest.mock import patch

# Ensure LCU root is in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Plugins.telescope.T2P5.telescope_plugin import DefaultTelescope
from core.communications.schemas import Target

# Parse custom argument before unittest parses command line arguments
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--live", action="store_true", help="Connect directly to the live telescope hardware")
args, unknown = parser.parse_known_args()

# Clean up sys.argv so unittest doesn't fail on the custom argument
sys.argv = [sys.argv[0]] + unknown

LIVE_TEST = args.live

class SimpleMockServer:
    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, port))
        self.port = self.server_sock.getsockname()[1]
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        try:
            self.server_sock.close()
        except:
            pass
        if self.thread:
            self.thread.join(timeout=1.0)

    def _run(self):
        self.server_sock.listen(5)
        while self.running:
            try:
                conn, addr = self.server_sock.accept()
                t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                t.start()
            except Exception:
                break

    def _handle_client(self, conn):
        try:
            conn.sendall(b"Connect: OK\r\n")
            buffer = bytearray()
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break
                buffer.extend(data)
                while b"\r\n" in buffer:
                    idx = buffer.index(b"\r\n")
                    line = buffer[:idx].decode("utf-8").strip()
                    del buffer[:idx+2]
                    if not line:
                        continue
                    
                    if line == "get nispdatads":
                        conn.sendall(b"got nispdatads 61220.405246499 9.0726953 09:04:21.7 09:43:33.17 89.999588 0.000268 6.45807316 24.67505189 FK5 9.05170817 24.75541476 1.223 off stationary off stationary off true Running 23.900000 68.100000 17.6 827.000000 2.800000 325.000000 \r\n")
                    elif line.startswith("do track"):
                        conn.sendall(b"ack track 0 OK\r\ndone track 0 OK\r\n")
                    elif line.startswith("do target"):
                        conn.sendall(b"ack target 0 OK\r\ndone target 0 OK\r\n")
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except:
                pass

class TestT2P5PluginFlow(unittest.IsolatedAsyncioTestCase):
    async def test_t2p5_plugin_flow(self):
        server = None
        connect_patcher = None

        if not LIVE_TEST:
            print("\n*** RUNNING IN MOCK SERVER MODE ***")
            server = SimpleMockServer()
            server.start()
            time.sleep(0.1)

            # Redirect all socket connections to local mock server
            original_connect = socket.socket.connect
            def mock_connect(self_sock, address):
                return original_connect(self_sock, ("127.0.0.1", server.port))

            connect_patcher = patch('socket.socket.connect', mock_connect)
            connect_patcher.start()
        else:
            print("\n*** RUNNING IN LIVE HARDWARE MODE ***")

        try:
            # 1. Initialize plugin (will connect and check b'Connect: OK')
            print("Initializing DefaultTelescope plugin...")
            plugin = DefaultTelescope(telescope_id="T2P5")
            self.assertTrue(plugin.driver.is_connected)

            # Let telemetry thread pull at least once
            await asyncio.sleep(30.0)

            # 2. Get current telemetry and print it
            print("\nQuerying current telemetry from plugin...")
            telemetry = plugin.get_current_telemetry()
            print(f"Telemetry received: {telemetry}")

            # Verify coordinate parsing works
            # self.assertAlmostEqual(telemetry["ra"], 9.05170817 * 15.0)
            # self.assertAlmostEqual(telemetry["dec"], 24.75541476)

            # Create target with hardcoded coordinates
            target = Target(
                configuration_id=101,
                type="ICRS",
                name="HardcodedTarget",
                ra=161.25,
                dec=10.5,
                epoch=2000.0
            )

            # 3. Turn on tracking using the plugin function


            # 4. Slew to target using the plugin function
            print("\nTriggering slew to target via plugin...")
            await plugin.slew_to_target(target)
            self.assertTrue(plugin.is_slewing)
            print("Slew command executed successfully via plugin interface.")

            # tracking should be on after slew, so we can call start_tracking to ensure it's set
            print("\nSetting tracking to ON via plugin...")
            await plugin.start_tracking(target)
            self.assertTrue(plugin.is_tracking)

        finally:
            # Clean up connection
            if 'plugin' in locals():
                print("\nDisconnecting plugin...")
                plugin.driver.disconnect()
            if connect_patcher:
                connect_patcher.stop()
            if server:
                server.stop()

if __name__ == "__main__":
    unittest.main()

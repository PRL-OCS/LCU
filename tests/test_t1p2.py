import os
import sys
import time
import asyncio
import socket
import datetime
import unittest
import argparse
import threading
from unittest.mock import patch, MagicMock

# Parse custom argument before unittest parses command line arguments
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--live", action="store_true", help="Connect directly to the live Skychart service")
args, unknown = parser.parse_known_args()

# Clean up sys.argv so unittest doesn't fail on the custom argument
sys.argv = [sys.argv[0]] + unknown

LIVE_TEST = args.live

# Add LCU root to path so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.telescope.T1P2.telescope_plugin import T1P2TelescopePlugin
from core.communications.schemas import Target, Configuration, InstrumentConfig, ScheduleSchema, RequestSchema

class MockSkychartServer:
    """
    Simulates a running Skychart TCP application server on localhost.
    """
    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.port = port
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.port = self.server_sock.getsockname()[1]
        self.running = False
        self.thread = None
        self.lock = threading.Lock()
        
        # Simulated telescope state
        self.target_ra = 10.0      # in hours
        self.target_dec = 30.0     # in degrees
        self.current_ra = 10.0     # in hours
        self.current_dec = 30.0    # in degrees
        self.is_tracking = False
        self.is_slewing = False

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
            except:
                break

    def _handle_client(self, conn):
        try:
            # Send Skychart greeting
            conn.sendall(b"OK! Skychart Ready\r\n")
            
            buffer = bytearray()
            while self.running:
                # Slew simulation step: instant convergence for faster unit testing
                with self.lock:
                    if self.is_slewing:
                        self.current_ra = self.target_ra
                        self.current_dec = self.target_dec
                        self.is_slewing = False

                data = conn.recv(1024)
                if not data:
                    break
                buffer.extend(data)
                
                while b"\r\n" in buffer:
                    line_idx = buffer.index(b"\r\n")
                    line = buffer[:line_idx].decode("utf-8").strip()
                    del buffer[:line_idx+2]
                    
                    if not line:
                        continue
                    
                    parts = line.split()
                    cmd = parts[0].upper()
                    
                    response = b"OK\r\n"
                    if cmd == "GETSCOPERADEC":
                        with self.lock:
                            response = f"OK! {self.current_ra} {self.current_dec}\r\n".encode()
                    elif cmd == "SEARCH":
                        response = b"OK\r\n"
                    elif cmd == "REDRAW":
                        response = b"OK\r\n"
                    elif cmd == "GETSELECTEDOBJECT":
                        # Returns mock coordinates format
                        with self.lock:
                            response = b"OK!\t18h36m54s\t+38d46m48s\r\n"
                    elif cmd == "CONNECTTELESCOPE":
                        response = b"OK\r\n"
                    elif cmd == "SLEW":
                        if len(parts) > 2:
                            with self.lock:
                                self.target_ra = float(parts[1])
                                self.target_dec = float(parts[2])
                                self.is_slewing = True
                        response = b"OK\r\n"
                    elif cmd == "ABORTSLEW":
                        with self.lock:
                            self.is_slewing = False
                        response = b"OK\r\n"
                    elif cmd == "TRACKTELESCOPE":
                        if len(parts) > 1:
                            with self.lock:
                                self.is_tracking = parts[1] == "ON"
                        response = b"OK\r\n"
                        
                    conn.sendall(response)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except:
                pass


class TestT1P2Flow(unittest.IsolatedAsyncioTestCase):
    """
    Unified sequential test flow for the T1P2 (Skychart) Telescope Plugin.
    Runs connection, telemetry polling, and slewing sequentially on the same object.
    Supports running on mock server or live Skychart via the --live argument.
    """

    @classmethod
    def setUpClass(cls):
        if LIVE_TEST:
            print("\n*** RUNNING IN LIVE HARDWARE MODE (SKYCHART FLATPAK) ***")
            cls.server = None
            cls.connect_patcher = None
        else:
            print("\n*** RUNNING IN MOCK SERVER MODE ***")
            # Start local mock Skychart server
            cls.server = MockSkychartServer()
            cls.server.start()
            # Wait for server to bind
            time.sleep(0.2)

            # Redirect socket connections to our mock server
            cls.original_connect = socket.socket.connect

            def mock_connect(self_sock, address):
                host, port = address
                # Redirect default Skychart IP/port to local mock server
                if host == "127.0.0.1" and int(port) == 3292:
                    return cls.original_connect(self_sock, ("127.0.0.1", cls.server.port))
                return cls.original_connect(self_sock, address)

            cls.connect_patcher = patch.object(socket.socket, "connect", mock_connect)
            cls.connect_patcher.start()

    @classmethod
    def tearDownClass(cls):
        if cls.connect_patcher:
            cls.connect_patcher.stop()
        if cls.server:
            cls.server.stop()

    async def test_t1p2_sequential_flow(self):
        print("\n--- Step 1: Initializing T1P2 Telescope Plugin ---")
        # 1. Initialize the object (connects to live Skychart, or mock server via redirect)
        plugin = T1P2TelescopePlugin(telescope_id="T1P2")
        
        # Test basic attributes after initialization
        self.assertEqual(plugin.get_id(), "T1P2")
        
        print("\n--- Step 2: Testing Hardware Connection ---")
        # Verify the hardware connection is active and health check thread started
        self.assertTrue(plugin.driver.is_connected)
        self.assertTrue(plugin.driver._thread is not None and plugin.driver._thread.is_alive())

        print("\n--- Step 3: Testing Polling Telemetry ---")
        if LIVE_TEST:
            # Command Skychart to connect to the telescope mount first
            print("Live Mode: Sending CONNECTTELESCOPE to Skychart mount...")
            try:
                plugin.driver._execute("CONNECTTELESCOPE")
            except Exception as e:
                print(f"Warning: CONNECTTELESCOPE failed: {e}")
        else:
            # Seed coordinates on the mock server
            # RA = 10.0 hours -> 150.0 degrees, Dec = 30.0 degrees
            with self.server.lock:
                self.server.current_ra = 10.0
                self.server.current_dec = 30.0

        # Wait for background telemetry thread to poll at least once (interval is 2s)
        # and allow connection state to propagate
        print("Waiting for background telemetry thread to poll...")
        await asyncio.sleep(2.5)

        # Fetch telemetry through the plugin
        telemetry = plugin.get_current_telemetry()
        print(f"Fetched Telemetry: {telemetry}")
        
        # Verify basic telemetry status fields
        self.assertTrue(telemetry["is_connected"])
        self.assertIn("ra", telemetry)
        self.assertIn("dec", telemetry)

        if not LIVE_TEST:
            # Verify telemetry coordinates match scaled values
            self.assertAlmostEqual(telemetry["ra"], 150.0) # 10.0 hours * 15
            self.assertAlmostEqual(telemetry["dec"], 30.0)
            self.assertEqual(plugin.current_ra, 150.0)
            self.assertEqual(plugin.current_dec, 30.0)

        print("\n--- Step 4: Testing target scheduling and slewing ---")
        # Create a mock target and schedule
        target = Target(
            configuration_id=600,
            type="MPC_COMET", #for test purposes so that resolving works
            name="Polaris",
            ra=279.23,  # 18.615 hours
            dec=38.78,
            epoch=2000.0
        )
        
        config = Configuration(
            id=600,
            instrument_type="MOCK_CAM",
            type="TEST",
            priority=1,
            instrument_configs=[InstrumentConfig(mode="IMG", exposure_time=2.0)],
            target=target,
            configuration_status=600,
            state="PENDING",
            instrument_name="MOCK_CAM"
        )
        
        now = datetime.datetime.now(datetime.timezone.utc)
        request = RequestSchema(
            id=999,
            observation_note="T1P2 test schedule",
            state="PENDING",
            acceptability_threshold=1.0,
            modified=now,
            duration=15,
            configurations=[config]
        )
        
        obs_schedule = ScheduleSchema(
            id=999,
            request=request,
            site="PRL",
            enclosure="DomeA",
            telescope="T1P2",
            start=now - datetime.timedelta(seconds=5),
            end=now + datetime.timedelta(seconds=60),
            priority=1,
            state="PENDING",
            proposal="PROP-T1P2",
            submitter="observer",
            name="T1P2TestSchedule",
            ipp_value=1.0,
            observation_type="SCIENCE",
            request_group_id=1,
            created=now,
            modified=now
        )

        # Receive schedule and test local queue state
        plugin.receive_schedule([obs_schedule])
        self.assertEqual(len(plugin.observations), 1)
        self.assertEqual(len(plugin.targets), 1)
        
        # Trigger slew to the target coordinates
        print(f"Triggering slew to {target.name} (RA: {target.ra}, Dec: {target.dec})")
        await plugin.slew_to_target(target)
        
        # Start tracking
        await plugin.start_tracking(target)
        self.assertTrue(plugin.is_tracking)

        # Allow some time for hardware/mock server to process slew coordinates
        await asyncio.sleep(2.5)

        # Check telemetry again
        telemetry_after = plugin.get_current_telemetry()
        print(f"Telemetry after slew: {telemetry_after}")
        self.assertTrue(telemetry_after["is_connected"])
        
        if not LIVE_TEST:
            # Slew targets in server should match target RA (in hours) and Dec
            with self.server.lock:
                self.assertAlmostEqual(self.server.target_ra, 18.615)
                self.assertAlmostEqual(self.server.target_dec, 38.78)

        # Stop telemetry thread and disconnect safely
        plugin.driver.disconnect()
        print("T1P2 sequential test flow finished successfully.")

if __name__ == "__main__":
    unittest.main()

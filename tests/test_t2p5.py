import os
import sys
import time
import asyncio
import socket
import datetime
import unittest
import argparse
from unittest.mock import patch, MagicMock

# Parse custom argument before unittest parses command line arguments
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--live", action="store_true", help="Connect directly to the live telescope hardware")
args, unknown = parser.parse_known_args()

# Clean up sys.argv so unittest doesn't fail on the custom argument
sys.argv = [sys.argv[0]] + unknown

LIVE_TEST = args.live

# Add LCU root to path so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.telescope.T2P5.telescope_plugin import DefaultTelescope
from tests.test_telnet_mock_service import MockTelnetServer
from core.communications.schemas import Target, Configuration, InstrumentConfig, ScheduleSchema, RequestSchema

class TestT2P5Flow(unittest.IsolatedAsyncioTestCase):
    """
    Unified sequential test flow for the T2P5 Telescope Plugin.
    Runs connection, telemetry polling, and slewing sequentially on the same object.
    Supports running on mock server or live hardware via the --live argument.
    """

    @classmethod
    def setUpClass(cls):
        if LIVE_TEST:
            print("\n*** RUNNING IN LIVE HARDWARE MODE ***")
            cls.server = None
            cls.connect_patcher = None
        else:
            print("\n*** RUNNING IN MOCK SERVER MODE ***")
            # Start local mock Telnet server
            cls.server = MockTelnetServer()
            cls.server.start()
            # Wait for server to bind
            time.sleep(0.2)

            # Redirect socket connections to our mock server
            cls.original_connect = socket.socket.connect

            def mock_connect(self_sock, address):
                host, port = address
                # Redirect default telescope IP/port to local mock server
                if host == "172.16.20.221" and int(port) == 7281:
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

    async def test_t2p5_sequential_flow(self):
        print("\n--- Step 1: Initializing T2P5 Telescope Plugin ---")
        # 1. Initialize the object (connects to live hardware, or mock server via redirect)
        plugin = DefaultTelescope(telescope_id="T2P5")
        
        # Test basic attributes after initialization
        self.assertEqual(plugin.get_id(), "T2P5")
        
        print("\n--- Step 2: Testing Hardware Connection ---")
        # Verify the hardware connection is active and telemetry thread started
        self.assertTrue(plugin.driver.is_connected)
        self.assertTrue(plugin.driver.telemetry.running)
        
        # Ensure the welcome banner negotiation happened
        self.assertIsNotNone(plugin.driver.tn)

        print("\n--- Step 3: Testing Polling Telemetry ---")
        if LIVE_TEST:
            print("Live Mode: Fetching current telemetry directly from hardware...")
            telemetry = plugin.get_current_telemetry()
            print(f"Live Telemetry: {telemetry}")
            self.assertIn("ra", telemetry)
            self.assertIn("dec", telemetry)
            self.assertTrue(telemetry["connected"])
        else:
            # Seed coordinates on the mock server
            # RA = 10.0 hours -> 150.0 degrees, Dec = 30.0 degrees
            with self.server.lock:
                self.server.current_ra = 10.0
                self.server.current_dec = 30.0

            # Wait for background telemetry thread to poll at least once (interval is 2s)
            print("Waiting for background telemetry thread to poll...")
            await asyncio.sleep(2.5)

            # Fetch telemetry through the plugin
            telemetry = plugin.get_current_telemetry()
            print(f"Fetched Telemetry: {telemetry}")
            
            # Verify telemetry coordinates match scaled values
            self.assertAlmostEqual(telemetry["ra"], 150.0) # 10.0 hours * 15
            self.assertAlmostEqual(telemetry["dec"], 30.0)
            self.assertFalse(telemetry["tracking"]) # Starts False until set via driver
            self.assertTrue(plugin.is_connected)
            self.assertEqual(plugin.current_ra, 150.0)
            self.assertEqual(plugin.current_dec, 30.0)

        print("\n--- Step 4: Testing target scheduling and slewing ---")
        # Create a mock target and schedule
        target = Target(
            configuration_id=500,
            type="ICRS",
            name="Polaris",
            ra=37.95454167,  # 18.615 hours
            dec=89.26410833,
            epoch=2000.0
        )
        
        config = Configuration(
            id=500,
            instrument_type="T2P5_CAM",
            type="TEST",
            priority=1,
            instrument_configs=[InstrumentConfig(mode="IMG", exposure_time=2.0)],
            target=target,
            configuration_status=500,
            state="PENDING",
            instrument_name="T2P5_CAM"
        )
        
        now = datetime.datetime.now(datetime.timezone.utc)
        request = RequestSchema(
            id=999,
            observation_note="T2P5 test schedule",
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
            enclosure="DomeB",
            telescope="T2P5",
            start=now - datetime.timedelta(seconds=5),
            end=now + datetime.timedelta(seconds=60),
            priority=1,
            state="PENDING",
            proposal="PROP-T2P5",
            submitter="observer",
            name="T2P5TestSchedule",
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
        self.assertTrue(plugin.is_slewing)

        # Start tracking
        await plugin.start_tracking(target)
        self.assertTrue(plugin.is_tracking)

        # Allow some time for hardware/mock server to process slew coordinates
        await asyncio.sleep(2.5)

        # Check telemetry again
        telemetry_after = plugin.get_current_telemetry()
        print(f"Telemetry after slew: {telemetry_after}")
        self.assertTrue(telemetry_after["tracking"])
        
        if not LIVE_TEST:
            # Slew targets in server should match target RA (in hours) and Dec
            with self.server.lock:
                self.assertAlmostEqual(self.server.target_ra, target.ra / 15.0)
                self.assertAlmostEqual(self.server.target_dec, target.dec)

        # Stop telemetry thread and disconnect safely
        plugin.driver.disconnect()
        print("T2P5 sequential test flow finished successfully.")

if __name__ == "__main__":
    unittest.main()

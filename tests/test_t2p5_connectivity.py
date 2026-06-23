import os
import sys
import unittest
from unittest.mock import patch

# Add LCU root to path so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.telescope.T2P5.telescope_driver import TelescopeDriver
from Plugins.telescope.T2P5.telnet_client import Telnet

class TestT2P5Connectivity(unittest.TestCase):
    def test_real_connection_failure(self):
        """
        Attempts to connect to the T2P5 telescope at its configured IP/port.
        Since there is no hardware connected, this is expected to raise a TelescopeConnectionError.
        """
        from Plugins.telescope.T2P5.errors import TelescopeConnectionError
        # Create driver pointing to the T2P5 address
        driver = TelescopeDriver(host="172.16.20.221", port=7281)
        
        # Connect is expected to fail by raising TelescopeConnectionError
        with self.assertRaises(TelescopeConnectionError):
            driver.connect()
        self.assertFalse(driver.is_connected)

    @patch("socket.socket")
    @patch("Plugins.telescope.T2P5.telescope_telemetry.TelescopeTelemetry.start")
    def test_mocked_connection_success(self, mock_telemetry_start, mock_socket_class):
        """
        Mocks the socket connection to simulate a successful connection handshake 
        to verify that the driver behaves correctly when the connection succeeds.
        """
        mock_socket_instance = mock_socket_class.return_value
        # Mock receiving the greeting line: welcome banner
        mock_socket_instance.recv.side_effect = [b"Welcome to SiTech/PWI Server\r\n", b"\r\n", b"\r\n"]
        
        driver = TelescopeDriver(host="172.16.20.221", port=7281)
        connected = driver.connect()
        
        self.assertTrue(connected)
        self.assertTrue(driver.is_connected)
        mock_telemetry_start.assert_called_once()
        
        # Clean up
        driver.disconnect()
        self.assertFalse(driver.is_connected)

if __name__ == "__main__":
    unittest.main()

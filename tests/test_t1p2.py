import os
import sys
import unittest
import asyncio
from unittest.mock import patch, MagicMock

# Ensure LCU root is in Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.telescope.T1P2.telescope_plugin import T1P2TelescopePlugin
from core.communications.schemas import ScheduleSchema, Target
from Plugins.telescope.T1P2.telescope_driver import TelescopeDriver

MOCK_TELESCOPE_API_DATA = {
    "id": 1,
    "request": {
        "id": 101,
        "observation_note": "T1P2 Observation",
        "state": "PENDING",
        "acceptability_threshold": 90.0,
        "modified": "2026-06-03T12:00:00Z",
        "duration": 600,
        "configurations": [{
            "id": 501,
            "instrument_type": "camera",
            "type": "EXPOSE",
            "priority": 1,
            "instrument_configs": [{
                "optical_elements": {"filter": "V"},
                "mode": "full",
                "exposure_time": 10.0,
                "exposure_count": 1,
                "rotator_mode": "SKY",
                "extra_params": {"bin_x": 1, "bin_y": 1, "defocus": 0.0},
                "rois": []
            }],
            "target": {
                "type": "ICRS",
                "name": "M31",
                "ra": 10.684,
                "dec": 41.269,
                "epoch": 2000.0
            },
            "configuration_status": 1,
            "state": "PENDING",
            "instrument_name": "T1P2_IMAGER",
            "guide_camera_name": "guider"
        }]
    },
    "site": "tst",
    "enclosure": "doma",
    "telescope": "1m0a",
    "start": "2026-06-03T20:00:00Z",
    "end": "2026-06-03T20:10:00Z",
    "priority": 100,
    "state": "PENDING",
    "proposal": "P1",
    "submitter": "T1",
    "name": "M31",
    "ipp_value": 1.0,
    "observation_type": "S",
    "request_group_id": 1001,
    "created": "2026-06-03T10:00:00Z",
    "modified": "2026-06-03T10:00:00Z"
}

MOCK_NON_SIDEREAL_API_DATA = {
    "id": 2,
    "request": {
        "id": 102,
        "observation_note": "T1P2 Non-Sidereal Observation",
        "state": "PENDING",
        "acceptability_threshold": 90.0,
        "modified": "2026-06-03T12:00:00Z",
        "duration": 600,
        "configurations": [{
            "id": 502,
            "instrument_type": "camera",
            "type": "EXPOSE",
            "priority": 1,
            "instrument_configs": [{
                "optical_elements": {"filter": "V"},
                "mode": "full",
                "exposure_time": 10.0,
                "exposure_count": 1,
                "rotator_mode": "SKY",
                "extra_params": {"bin_x": 1, "bin_y": 1, "defocus": 0.0},
                "rois": []
            }],
            "target": {
                "type": "NON-SIDEREAL",
                "name": "Jupiter",
                "ra": 0.0,  # Needs resolution
                "dec": 0.0, # Needs resolution
                "epoch": 2000.0
            },
            "configuration_status": 1,
            "state": "PENDING",
            "instrument_name": "T1P2_IMAGER",
            "guide_camera_name": "guider"
        }]
    },
    "site": "tst",
    "enclosure": "doma",
    "telescope": "1m0a",
    "start": "2026-06-03T20:00:00Z",
    "end": "2026-06-03T20:10:00Z",
    "priority": 100,
    "state": "PENDING",
    "proposal": "P1",
    "submitter": "T1",
    "name": "Jupiter",
    "ipp_value": 1.0,
    "observation_type": "S",
    "request_group_id": 1001,
    "created": "2026-06-03T10:00:00Z",
    "modified": "2026-06-03T10:00:00Z"
}

class TestT1P2Plugin(unittest.IsolatedAsyncioTestCase):
    
    @patch('socket.socket')
    def setUp(self, mock_socket):
        # Mock socket behaviors to avoid connecting to a real server during tests
        self.mock_socket_inst = MagicMock()
        mock_socket.return_value.__enter__.return_value = self.mock_socket_inst
        
        # Instantiate plugin
        self.plugin = T1P2TelescopePlugin(telescope_id="1m0a")

    def tearDown(self):
        # Clean up driver background thread
        self.plugin.driver.disconnect()

    def test_initialization(self):
        """Verify that the plugin is correctly initialized."""
        self.assertEqual(self.plugin.telescope_id, "1m0a")
        self.assertTrue(hasattr(self.plugin, 'driver'))

    def test_receive_schedule(self):
        """Verify schedule loading and target extraction."""
        obs = ScheduleSchema.model_validate(MOCK_TELESCOPE_API_DATA)
        self.plugin.receive_schedule([obs])
        
        self.assertEqual(len(self.plugin.targets), 1)
        target = self.plugin.targets[0]
        self.assertEqual(target.name, "M31")
        self.assertEqual(target.ra, 10.684)
        self.assertEqual(target.dec, 41.269)
        self.assertEqual(target.configuration_id, 501)

    @patch.object(TelescopeDriver, 'slew_to')
    @patch.object(TelescopeDriver, 'get_status')
    async def test_slew_to_sidereal_target(self, mock_get_status, mock_slew_to):
        """Test slewing to a sidereal target using database coordinates directly."""
        obs = ScheduleSchema.model_validate(MOCK_TELESCOPE_API_DATA)
        self.plugin.receive_schedule([obs])
        target = self.plugin.get_next_target()
        
        # Mock status updates so slew completes quickly
        mock_get_status.return_value = {
            "ra": 10.684,
            "dec": 41.269,
            "connected": True,
            "skychart_online": True
        }
        
        await self.plugin.slew_to_target(target)
        
        # Verify slew was invoked with direct coordinates
        mock_slew_to.assert_called_once_with(10.684, 41.269)

    @patch.object(TelescopeDriver, 'resolve_target')
    @patch.object(TelescopeDriver, 'slew_to')
    @patch.object(TelescopeDriver, 'get_status')
    async def test_slew_to_non_sidereal_target(self, mock_get_status, mock_slew_to, mock_resolve_target):
        """Test resolving non-sidereal target name to coordinates and slewing."""
        obs = ScheduleSchema.model_validate(MOCK_NON_SIDEREAL_API_DATA)
        self.plugin.receive_schedule([obs])
        target = self.plugin.get_next_target()
        
        # Mock target resolution values (Jupiter: RA=100.0, Dec=10.0)
        mock_resolve_target.return_value = (100.0, 10.0)
        
        # Mock status updates so slew completes quickly
        mock_get_status.return_value = {
            "ra": 100.0,
            "dec": 10.0,
            "connected": True,
            "skychart_online": True
        }
        
        await self.plugin.slew_to_target(target)
        
        # Verify resolution was attempted and resolved coordinates were used to slew
        mock_resolve_target.assert_called_once_with("Jupiter")
        mock_slew_to.assert_called_once_with(100.0, 10.0)

    @patch.object(TelescopeDriver, 'get_status')
    def test_telemetry(self, mock_get_status):
        """Verify telemetry collection."""
        mock_get_status.return_value = {
            "ra": 10.684,
            "dec": 41.269,
            "connected": True,
            "skychart_online": True
        }
        
        telemetry = self.plugin.get_current_telemetry()
        self.assertEqual(telemetry["ra"], 10.684)
        self.assertEqual(telemetry["dec"], 41.269)
        self.assertTrue(telemetry["is_connected"])
        self.assertTrue(telemetry["skychart_online"])

if __name__ == '__main__':
    unittest.main()

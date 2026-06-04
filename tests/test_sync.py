import sys
import os
os.environ["PRAMANA_API_TOKEN"] = "mock_token"
from unittest.mock import MagicMock, patch

# Ensure the script can import local packages
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock the API Response Data
MOCK_API_DATA = {
    "results": [
        {
            "id": 1,
            "request": {
                "id": 101,
                "observation_note": "Test observation 1",
                "state": "PENDING",
                "acceptability_threshold": 90.0,
                "modified": "2026-04-04T12:00:00Z",
                "duration": 600,
                "configurations": [{
                    "id": 501,
                    "instrument_type": "1m0-SciCam-Sinistro",
                    "type": "EXPOSE",
                    "priority": 1,
                    "instrument_configs": [{
                        "optical_elements": {"filter": "V"},
                        "mode": "full_frame",
                        "exposure_time": 120.0,
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
                    "instrument_name": "xx04",
                    "guide_camera_name": "guider"
                }]
            },
            "site": "tst",
            "enclosure": "doma",
            "telescope": "1m0a",
            "start": "2026-04-04T20:00:00Z",
            "end": "2026-04-04T20:10:00Z",
            "priority": 100,
            "state": "PENDING",
            "proposal": "TEST_PROP",
            "submitter": "tester",
            "name": "M31 Observation",
            "ipp_value": 1.0,
            "observation_type": "SCIENCE",
            "request_group_id": 1001,
            "created": "2026-04-04T10:00:00Z",
            "modified": "2026-04-04T10:00:00Z"
        },
        {
            "id": 2,
            "request": {
                "id": 102,
                "observation_note": "Test observation 2",
                "state": "PENDING",
                "acceptability_threshold": 90.0,
                "modified": "2026-04-04T12:00:00Z",
                "duration": 300,
                "configurations": [{
                    "id": 502,
                    "instrument_type": "2m0-SciCam-Spectral",
                    "type": "EXPOSE",
                    "priority": 2,
                    "instrument_configs": [{
                        "optical_elements": {"filter": "R"},
                        "mode": "default",
                        "exposure_time": 60.0,
                        "exposure_count": 1,
                        "rotator_mode": "SKY",
                        "extra_params": {"bin_x": 2, "bin_y": 2, "defocus": 0.0},
                        "rois": []
                    }],
                    "target": {
                        "type": "ICRS",
                        "name": "M42",
                        "ra": 83.822,
                        "dec": -5.391,
                        "epoch": 2000.0
                    },
                    "configuration_status": 1,
                    "state": "PENDING",
                    "instrument_name": "xx06",
                    "guide_camera_name": "guider"
                }]
            },
            "site": "tst",
            "enclosure": "clma",
            "telescope": "2m0a",
            "start": "2026-04-04T21:00:00Z",
            "end": "2026-04-04T21:05:00Z",
            "priority": 200,
            "state": "PENDING",
            "proposal": "TEST_PROP",
            "submitter": "tester",
            "name": "M42 Observation",
            "ipp_value": 1.5,
            "observation_type": "SCIENCE",
            "request_group_id": 1002,
            "created": "2026-04-04T10:00:00Z",
            "modified": "2026-04-04T10:00:00Z"
        }
    ]
}

def run_test():
    with patch("requests.get") as mock_get:
        # Mock the response object
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = MOCK_API_DATA
        mock_get.return_value = mock_response
        
        # 1. Initialize Plugin Manager
        from core.plugins.manager import PluginManager
        from core.schedule_coordinator import ScheduleCoordinator
        
        # We need to make sure the plugin manager can find our demo plugin
        manager = PluginManager()
        manager.discover_plugins()
        
        # 2. Initialize Coordinator
        coordinator = ScheduleCoordinator(manager)
        
        # 3. Synchronize
        coordinator.sync_all()
        
        # 4. Verify results in plugins
        print("\n[VERIFICATION]")
        for telescope_id, plugin in manager.get_all_telescope_plugins().items():
            print(f"Plugin '{telescope_id}' task count: {len(plugin.targets)}")
            if len(plugin.targets) > 0:
                print(f"  First task target: {plugin.targets[0].name}")

if __name__ == "__main__":
    run_test()

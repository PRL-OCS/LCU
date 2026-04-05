import sys
import os
from unittest.mock import MagicMock, patch

# Ensure the script can import local packages
sys.path.append(os.getcwd())

# Mock the API Response Data
MOCK_API_DATA = {
    "results": [
        {
            "id": 1,
            "request": {
                "id": 101,
                "observation_note": "Dual target task",
                "state": "PENDING",
                "acceptability_threshold": 90.0,
                "modified": "2026-04-05T12:00:00Z",
                "duration": 600,
                "configurations": [{
                    "id": 501,
                    "instrument_type": "camera",
                    "type": "EXPOSE",
                    "priority": 1,
                    "instrument_configs": [{"optical_elements": {"filter": "V"}, "mode": "full", "exposure_time": 10.0, "exposure_count": 1, "rotator_mode": "SKY", "extra_params": {"bin_x": 1, "bin_y": 1, "defocus": 0.0}, "rois": []}],
                    "target": {"type": "I", "name": "M31", "ra": 10.0, "dec": 41.0, "epoch": 2000.0},
                    "configuration_status": 1,
                    "state": "PENDING",
                    "instrument_name": "T1P2_IMAGER",
                    "guide_camera_name": "guider"
                }]
            },
            "site": "tst",
            "enclosure": "doma",
            "telescope": "1m0a",
            "start": "2026-04-05T20:00:00Z",
            "end": "2026-04-05T20:10:00Z",
            "priority": 100,
            "state": "PENDING",
            "proposal": "P1",
            "submitter": "T1",
            "name": "M31",
            "ipp_value": 1.0,
            "observation_type": "S",
            "request_group_id": 1001,
            "created": "2026-04-05T10:00:00Z",
            "modified": "2026-04-05T10:00:00Z"
        },
        {
            "id": 2,
            "request": {
                "id": 102,
                "observation_note": "Instrument only task",
                "state": "PENDING",
                "acceptability_threshold": 90.0,
                "modified": "2026-04-05T12:00:00Z",
                "duration": 300,
                "configurations": [{
                    "id": 502,
                    "instrument_type": "camera",
                    "type": "EXPOSE",
                    "priority": 2,
                    "instrument_configs": [{"optical_elements": {"filter": "R"}, "mode": "full", "exposure_time": 5.0, "exposure_count": 1, "rotator_mode": "SKY", "extra_params": {"bin_x": 1, "bin_y": 1, "defocus": 0.0}, "rois": []}],
                    "target": {"type": "I", "name": "M42", "ra": 83.0, "dec": -5.0, "epoch": 2000.0},
                    "configuration_status": 1,
                    "state": "PENDING",
                    "instrument_name": "T1P2_IMAGER",
                    "guide_camera_name": "guider"
                }]
            },
            "site": "tst",
            "enclosure": "clma",
            "telescope": "UNKNOWN_SCOPE",
            "start": "2026-04-05T21:00:00Z",
            "end": "2026-04-05T21:05:00Z",
            "priority": 200,
            "state": "PENDING",
            "proposal": "P2",
            "submitter": "T2",
            "name": "M42",
            "ipp_value": 1.5,
            "observation_type": "S",
            "request_group_id": 1002,
            "created": "2026-04-05T10:00:00Z",
            "modified": "2026-04-05T10:00:00Z"
        },
        {
            "id": 3,
            "request": {
                "id": 103,
                "observation_note": "Telescope only task",
                "state": "PENDING",
                "acceptability_threshold": 90.0,
                "modified": "2026-04-05T12:00:00Z",
                "duration": 400,
                "configurations": [{
                    "id": 503,
                    "instrument_type": "spectral",
                    "type": "EXPOSE",
                    "priority": 3,
                    "instrument_configs": [{"optical_elements": {"filter": "B"}, "mode": "full", "exposure_time": 20.0, "exposure_count": 1, "rotator_mode": "SKY", "extra_params": {"bin_x": 1, "bin_y": 1, "defocus": 0.0}, "rois": []}],
                    "target": {"type": "I", "name": "M51", "ra": 202.0, "dec": 47.0, "epoch": 2000.0},
                    "configuration_status": 1,
                    "state": "PENDING",
                    "instrument_name": "UNKNOWN_INST",
                    "guide_camera_name": "guider"
                }]
            },
            "site": "tst",
            "enclosure": "doma",
            "telescope": "1m0a",
            "start": "2026-04-05T22:00:00Z",
            "end": "2026-04-05T22:10:00Z",
            "priority": 300,
            "state": "PENDING",
            "proposal": "P3",
            "submitter": "T3",
            "name": "M51",
            "ipp_value": 2.0,
            "observation_type": "S",
            "request_group_id": 1003,
            "created": "2026-04-05T10:00:00Z",
            "modified": "2026-04-05T10:00:00Z"
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
        
        # 1. Initialize Unified Plugin Manager
        from core.plugins.manager import PluginManager
        from core.coordinator import ScheduleCoordinator
        
        # Discover plugins (will find our 1m0a telescope and T1P2_IMAGER instrument)
        manager = PluginManager()
        manager.discover_plugins()
        
        # 2. Initialize Coordinator
        coordinator = ScheduleCoordinator(manager)
        
        # 3. Synchronize
        print("\n" + "="*60)
        print("RUNNING SYNC ALL")
        print("="*60)
        coordinator.sync_all()
        
        # 4. Verify results
        print("\n" + "="*60)
        print("VERIFICATION")
        print("="*60)
        
        print("\nTelescope Plugins Status:")
        for tid, plugin in manager.get_all_telescope_plugins().items():
            print(f"- Telescope '{tid}' holds {len(plugin.targets)} targets.")
            for i, target in enumerate(plugin.targets):
                print(f"    {i+1}. [TEL-TARGET] Name: {target.name} | RA: {target.ra} | DEC: {target.dec}")

        print("\nInstrument Plugins Status:")
        for iid, plugin in manager.get_all_instrument_plugins().items():
            print(f"- Instrument '{iid}' holds {len(plugin.configs)} configs.")
            for i, config in enumerate(plugin.configs):
                print(f"    {i+1}. [INST-CONFIG] Filter: {config.optical_elements.filter} | Exp: {config.exposure_time}s")

if __name__ == "__main__":
    run_test()

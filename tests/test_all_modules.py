# Set mock environment variable before loading core imports
import os
os.environ["PRAMANA_API_TOKEN"] = "mock_token"

import unittest
import asyncio
from unittest.mock import patch, MagicMock

# Add LCU root to path so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.orchestrator import orchestrator
from core.states.manager import state_manager
from core.communications.schemas import ScheduleAPIResponse, InstrumentMappingResponse
from core.logging_config import logger

class TestAllModules(unittest.IsolatedAsyncioTestCase):
    
    _initialized = False

    async def asyncSetUp(self):
        """Initialize the orchestrator and clear state before each test."""
        if not self.__class__._initialized:
            logger.info("Initializing Orchestrator for Full Module Tests")
            orchestrator.initialize()
            
            self.__class__.mock_t = orchestrator.plugin_manager.get_telescope_plugin("T100")
            self.__class__.mock_i = orchestrator.plugin_manager.get_instrument_plugin("MOCK_CAM")
            
            if not self.mock_t or not self.mock_i:
                raise RuntimeError("Mock plugins not found. Tests cannot proceed.")
            self.__class__._initialized = True
            
        state_manager.observations.clear()
        self.mock_t.targets.clear()
        self.mock_i.configs.clear()

    def _get_mock_mapping_response(self):
        """Returns a valid hardware mapping response."""
        return {
            "MOCK_CAM": {
                "class": "T100",
                "name": "MOCK_CAM"
            }
        }

    def _get_mock_schedule_response(self, obs_id: int = 100, instrument: str = "MOCK_CAM"):
        """Returns a valid schedule response."""
        return {
            "results": [
                {
                    "id": 1,
                    "request": {
                        "id": 999,
                        "observation_note": "Mock observation",
                        "state": "PENDING",
                        "acceptability_threshold": 90.0,
                        "modified": "2026-05-22T00:00:00Z",
                        "duration": 3600,
                        "configurations": [
                            {
                                "id": obs_id,
                                "instrument_type": instrument,
                                "type": "TEST",
                                "priority": 1,
                                "instrument_configs": [
                                    {
                                        "mode": "IMG",
                                        "exposure_time": 1.0
                                    }
                                ],
                                "target": {
                                    "type": "ICRS",
                                    "name": f"Test Target {obs_id}",
                                    "ra": 100.0,
                                    "dec": 10.0,
                                    "epoch": 2000.0
                                },
                                "configuration_status": 1,
                                "state": "PENDING",
                                "instrument_name": instrument
                            }
                        ]
                    },
                    "site": "PRL",
                    "enclosure": "DomeA",
                    "telescope": "T100",
                    "start": "2026-05-22T00:00:00Z",
                    "end": "2026-05-22T01:00:00Z",
                    "priority": 1,
                    "state": "PENDING",
                    "proposal": "PROP-01",
                    "submitter": "astronomer",
                    "name": "Test Obs",
                    "ipp_value": 1.0,
                    "observation_type": "NORMAL",
                    "request_group_id": 1,
                    "created": "2026-05-22T00:00:00Z",
                    "modified": "2026-05-22T00:00:00Z"
                }
            ]
        }

    @patch('core.communications.api.requests.get')
    async def test_full_pipeline_normal(self, mock_get):
        """
        Tests the entire pipeline:
        API -> ScheduleCoordinator -> PluginManager -> TelescopeExecutor -> StateManager
        """
        logger.info("--- RUNNING TEST: FULL PIPELINE NORMAL ---")
        
        # Configure the mock API responses
        # First call is for mapping, second is for schedule
        mock_response_mapping = MagicMock()
        mock_response_mapping.json.return_value = self._get_mock_mapping_response()
        
        mock_response_schedule = MagicMock()
        mock_response_schedule.json.return_value = self._get_mock_schedule_response(obs_id=200)
        
        mock_get.side_effect = [mock_response_mapping, mock_response_schedule]
        
        # This will trigger api.py -> PluginManager mapping & ScheduleCoordinator dispatch
        orchestrator.plugin_manager.fetch_hardware_mapping()
        orchestrator.coordinator.sync_all()
        
        # Assert the data hit the plugins
        self.assertEqual(len(self.mock_t.targets), 1)
        self.assertEqual(len(self.mock_i.configs), 1)
        
        # Wait for the background executor to process it
        processed = False
        for _ in range(15):
            await asyncio.sleep(1)
            if "obs_cfg_200" in state_manager.observations:
                state = state_manager.observations["obs_cfg_200"].current_state.value
                if state in ["COMPLETED", "FAILED", "ABORTED", "READING_OUT"]:
                    processed = True
                    self.assertEqual(state, "READING_OUT")
                    break
        
        self.assertTrue(processed, "Executor failed to process the observation in time.")

    @patch('core.communications.api.requests.get')
    async def test_full_pipeline_missing_plugin(self, mock_get):
        """
        Tests safety logic in ScheduleCoordinator: 
        If an observation requires a missing plugin, it should be ignored safely.
        """
        logger.info("--- RUNNING TEST: FULL PIPELINE MISSING PLUGIN ---")
        
        mock_response_mapping = MagicMock()
        mock_response_mapping.json.return_value = self._get_mock_mapping_response()
        
        mock_response_schedule = MagicMock()
        # Create an observation pointing to a non-existent instrument
        mock_response_schedule.json.return_value = self._get_mock_schedule_response(obs_id=201, instrument="GHOST_CAM")
        
        mock_get.side_effect = [mock_response_mapping, mock_response_schedule]
        
        orchestrator.plugin_manager.fetch_hardware_mapping()
        orchestrator.coordinator.sync_all()
        
        # Because the instrument plugin doesn't exist, the orchestrator should skip it
        # Therefore, the telescope should NOT receive the target
        self.assertEqual(len(self.mock_t.targets), 0)
        self.assertEqual(len(self.mock_i.configs), 0)
        
if __name__ == '__main__':
    unittest.main()

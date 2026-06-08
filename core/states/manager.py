from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
from .schemas import LCUState, ObservationState, ObservationStatus
from core.logging_config import logger
from .uplink import uplink_manager

class StateManager:
    """
    Manages the lifecycle of System and Observation states.
    Enforces basic transition validation and audit logging.
    """
    def __init__(self):
        self.system_state: LCUState = LCUState.INITIALIZING
        self.observations: Dict[str, ObservationStatus] = {}
        self.last_update: datetime = datetime.now()
        logger.info(f"StateManager initialized at {self.last_update}")

    def update_system_state(self, new_state: LCUState):
        """Sets the overall system performance state."""
        if new_state == self.system_state:
            return
            
        logger.info(f"System Transition: {self.system_state.value} -> {new_state.value}")
        self.system_state = new_state
        self.last_update = datetime.now()

    def update_observation(self, obs_id: str, new_state: ObservationState, reason: Optional[str] = None,
                           pramana_obs_id: Optional[int] = None, pramana_config_id: Optional[int] = None,
                           exposure_time: float = 0.0):
        """
        Transitions an observation to a new state.
        Allocates new status tracking if not already present.
        """
        if obs_id not in self.observations:
            logger.info(f"New lifecycle started: {obs_id}")
            self.observations[obs_id] = ObservationStatus(id=obs_id)

        status = self.observations[obs_id]
        
        # Validation: check for illegal jumps or re-entry into terminal states
        if status.current_state in [ObservationState.DONE, ObservationState.ERROR, ObservationState.ABORTED, ObservationState.REJECTED]:
            if new_state != status.current_state:
                logger.warning(f"Blocked attempt to transition {obs_id} out of terminal state {status.current_state.value}")
                return

        if status.current_state == new_state:
            return

        logger.info(f"Observation {obs_id}: {status.current_state.value} -> {new_state.value}")
        status.add_transition(new_state, reason=reason)
        self.last_update = datetime.now()

        # Enqueue state uplink to PRAMANA if IDs are provided
        try:
            loop = asyncio.get_running_loop()
            if pramana_config_id is not None:
                loop.create_task(uplink_manager.enqueue_configuration_status(
                    pramana_config_id, new_state.name, reason or "", exposure_time=exposure_time
                ))
        except RuntimeError:
            pass # No running loop, cannot enqueue

    def get_observation_status(self, obs_id: str) -> Optional[ObservationStatus]:
        """Retrieves raw status for a specific observation."""
        return self.observations.get(obs_id)

    def get_summary(self) -> Dict[str, Any]:
        """Summary of current observations and system status."""
        return {
            "system_state": self.system_state.value,
            "observation_count": len(self.observations),
            "last_update": self.last_update.isoformat(),
            "active_observations": {
                id: obs.current_state.value 
                for id, obs in self.observations.items() 
                if obs.current_state not in [ObservationState.DONE, ObservationState.ERROR, ObservationState.ABORTED, ObservationState.REJECTED]
            }
        }

# Global singleton for core module shared access
state_manager = StateManager()

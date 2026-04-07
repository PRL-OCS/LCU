from typing import Dict, Any, List, Optional
from datetime import datetime
from .schemas import LCUState, ObservationState, ObservationStatus

class StateManager:
    """
    Manages the lifecycle of System and Observation states.
    Enforces basic transition validation and audit logging.
    """
    def __init__(self):
        self.system_state: LCUState = LCUState.INITIALIZING
        self.observations: Dict[str, ObservationStatus] = {}
        self.last_update: datetime = datetime.now()
        print(f"[SYSTEM] StateManager initialized at {self.last_update}")

    def update_system_state(self, new_state: LCUState):
        """Sets the overall system performance state."""
        if new_state == self.system_state:
            return
            
        print(f"[STATE] System Transition: {self.system_state.value} -> {new_state.value}")
        self.system_state = new_state
        self.last_update = datetime.now()

    def update_observation(self, obs_id: str, new_state: ObservationState, reason: Optional[str] = None):
        """
        Transitions an observation to a new state.
        Allocates new status tracking if not already present.
        """
        if obs_id not in self.observations:
            print(f"[STATE] New lifecycle started: {obs_id}")
            self.observations[obs_id] = ObservationStatus(id=obs_id)

        status = self.observations[obs_id]
        
        # Validation: check for illegal jumps or re-entry into terminal states
        if status.current_state in [ObservationState.COMPLETED, ObservationState.FAILED, ObservationState.ABORTED]:
            if new_state != status.current_state:
                print(f"[WARNING] Blocked attempt to transition {obs_id} out of terminal state {status.current_state.value}")
                return

        if status.current_state == new_state:
            return

        print(f"[STATE] {obs_id}: {status.current_state.value} -> {new_state.value}")
        status.add_transition(new_state, reason=reason)
        self.last_update = datetime.now()

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
                if obs.current_state not in [ObservationState.COMPLETED, ObservationState.FAILED, ObservationState.ABORTED]
            }
        }

# Global singleton for core module shared access
state_manager = StateManager()

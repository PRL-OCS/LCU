from enum import Enum
from typing import Dict, Optional, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

class LCUState(str, Enum):
    """Global states for the LCU Node system."""
    INITIALIZING = "INITIALIZING"
    IDLE = "IDLE"
    SYNCING = "SYNCING"
    BUSY = "BUSY"
    ERROR = "ERROR"
    MANUAL = "MANUAL"
    SHUTTING_DOWN = "SHUTTING_DOWN"

class ObservationState(str, Enum):
    """Detailed lifecycle states for an individual observation."""
    IDLE = "IDLE"
    PREPARING = "PREPARING"
    SLEWING = "SLEWING"        # Telescope moving
    ACQUIRING = "ACQUIRING"    # Closed-loop target verification
    CONFIGURING = "CONFIGURING" # Instrument setting up
    CALIBRATING = "CALIBRATING" # Dark/Flat/Bias frames
    EXPOSING = "EXPOSING"       # Shutter open
    READING_OUT = "READING_OUT" # Transferring from sensor
    FILE_DETECTED = "FILE_DETECTED" # Local file watcher found output
    STAGING_DATA = "STAGING_DATA"   # Validation/Checksum/Metadata prep
    INGESTING = "INGESTING"     # Pushing to Science Archive
    INGESTED = "INGESTED"       # Archive confirmed storage
    DONE = "DONE"               # Cleanup done
    
    # Terminal/Safety States
    PARKING = "PARKING"
    PARKED = "PARKED"
    ERROR = "ERROR"
    ABORTED = "ABORTED"
    REJECTED = "REJECTED"

class StateTransition(BaseModel):
    """Record of a state change for audit trails."""
    from_state: ObservationState
    to_state: ObservationState
    timestamp: datetime = Field(default_factory=datetime.now)
    reason: Optional[str] = None

class ObservationStatus(BaseModel):
    """The current status and history of an observation."""
    id: str
    current_state: ObservationState = ObservationState.IDLE
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    transitions: List[StateTransition] = []
    metadata: Dict[str, Any] = {}

    def add_transition(self, to_state: ObservationState, reason: Optional[str] = None):
        """Records a new state transition."""
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            reason=reason
        )
        self.transitions.append(transition)
        self.current_state = to_state
        if to_state in [ObservationState.DONE, ObservationState.ERROR, ObservationState.ABORTED, ObservationState.REJECTED]:
            self.end_time = datetime.now()

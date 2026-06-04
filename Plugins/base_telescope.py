import os
import json
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
from core.communications.schemas import ScheduleSchema
from core.logging_config import logger

class TelescopePlugin(ABC):
    """
    Abstract base class for all telescope plugins in LCU_Node.
    Now receives the full ScheduleSchema containing timing data.
    Persists to storage/telescope.
    """
    
    # Class-level registry for discovered telescope blueprint classes
    registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Register the class using its own name
        TelescopePlugin.registry[cls.__name__] = cls
        logger.debug(f"Discovered telescope plugin class: {cls.__name__}")

    def __init__(self, telescope_id: str, storage_dir: str = "storage/telescope"):
        self.telescope_id = telescope_id
        self.storage_dir = Path(storage_dir)
        self.observations: List[ScheduleSchema] = []
        
        # --- Hardware State (Default: Parked at Zenith) ---
        self.current_ra: float = 0.0          # Zenith RA
        self.current_dec: float = 90.0        # Zenith DEC
        self.dome_status: str = "unknown"      # e.g., "open", "closed", "moving"
        self.is_connected: bool = False
        self.is_tracking: bool = False
        self.is_slewing: bool = False
        self.is_guiding: bool = False
        
        # Determine unique storage file
        self.cache_file = self.storage_dir / f"{self.telescope_id}_targets.json"

    def receive_schedule(self, observations: List[ScheduleSchema]):
        """
        Callback method called by the ScheduleCoordinator when new observations 
        are available for this specific telescope.
        """
        self.observations = observations
        logger.info(f"[{self.telescope_id}] received {len(observations)} new observations.")
        self.save_to_disk()

    def get_next_observation(self) -> ScheduleSchema | None:
        """
        Pops and returns the next observation in the queue.
        """
        if self.observations:
            obs = self.observations.pop(0)
            self.save_to_disk()
            return obs
        return None

    @abstractmethod
    async def slew_to_target(self, target: Target):
        """
        Slews the telescope to the specified target coordinates.
        """
        pass

    @abstractmethod
    async def start_tracking(self, target: Target):
        """
        Sets the target, starts tracking, and initiates guiding if configured.
        """
        pass

    @abstractmethod
    async def force_stop(self):
        """
        Immediately stops all telescope and dome movement.
        """
        pass

    @abstractmethod
    async def pause(self):
        """
        Pauses current operations gracefully if supported.
        """
        pass

    @abstractmethod
    def get_current_telemetry(self) -> dict:
        """
        Returns a snapshot of the current hardware state/telemetry.
        """
        pass

    def save_to_disk(self):
        """
        Serializes current observations and saves them to a local JSON file.
        """
        try:
            # Ensure directory exists
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Serialize: Convert Pydantic models to dicts
            obs_data = [obs.model_dump() for obs in self.observations]
            
            with open(self.cache_file, "w") as f:
                json.dump(obs_data, f, indent=4, default=str)
                
            logger.debug(f"Persisted {len(self.observations)} observations to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save observations for {self.telescope_id}: {e}", exc_info=True)

    def load_from_disk(self):
        """
        Restores observations from the local JSON file if it exists.
        """
        if not self.cache_file.exists():
            logger.debug(f"No cache file found for {self.telescope_id}.")
            return

        try:
            with open(self.cache_file, "r") as f:
                raw_data = json.load(f)
                
            # Re-validate data back into Pydantic models
            self.observations = [ScheduleSchema.model_validate(o) for o in raw_data]
            logger.info(f"Restored {len(self.observations)} observations from {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to load observations for {self.telescope_id}: {e}", exc_info=True)

    def get_id(self) -> str:
        return self.telescope_id

    
import os
import json
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
from core.communications.schemas import ScheduleSchema, Configuration
from core.logging_config import logger

class InstrumentPlugin(ABC):
    """
    Abstract base class for all instrument plugins in LCU_Node.
    Now receives the full Configuration data model.
    Persists to storage/instrument.
    """
    
    # Class-level registry for discovered instrument blueprint classes
    registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Register the class using its own name
        InstrumentPlugin.registry[cls.__name__] = cls
        logger.debug(f"Discovered instrument plugin class: {cls.__name__}")

    def __init__(self, instrument_name: str, storage_dir: str = "storage/instrument"):
        self.instrument_name = instrument_name
        self.storage_dir = Path(storage_dir)
        self.observations: List[ScheduleSchema] = []
        
        # Determine unique storage file
        self.cache_file = self.storage_dir / f"{self.instrument_name}_configs.json"

    def receive_schedule(self, observations: List[ScheduleSchema]):
        """
        Callback method called by the ScheduleCoordinator when new observations 
        are available for this specific instrument.
        Can be overridden by subclasses if special processing is needed.
        """
        self.observations = observations
        logger.info(f"[{self.instrument_name}] received {len(observations)} new observations.")
        self.save_to_disk()

    def get_observation(self, obs_id: int) -> ScheduleSchema | None:
        """
        Returns the observation envelope matching the given configuration id (which is used as obs_id in our system)
        without removing it from the cache.
        Returns None if not found.
        """
        # The LCU uses configuration_id from the Target to look up the matching instrument Configuration.
        # But now we hold the whole ScheduleSchema, so we can match against obs.request.configurations[0].id
        for obs in self.observations:
            if obs.request.configurations and obs.request.configurations[0].id == obs_id:
                return obs
        return None

    def get_configuration(self, config_status_id: int) -> Configuration | None:
        """
        Returns the matching configuration and REMOVES it from the observation queue.
        This allows the executor to process the config while keeping the UI queue in sync.
        """
        for i, obs in enumerate(self.observations):
            for j, config in enumerate(obs.request.configurations):
                if getattr(config, 'configuration_status', None) == config_status_id:
                    matched_config = obs.request.configurations.pop(j)
                    # If this was the last config in the observation, pop the observation
                    if len(obs.request.configurations) == 0:
                        self.observations.pop(i)
                    self.save_to_disk()
                    return matched_config
        return None

    @abstractmethod
    async def configure(self, config: Configuration):
        """
        Applies the configuration to the instrument (e.g., filters, readout mode).
        """
        pass

    @abstractmethod
    async def expose(self, config: Configuration):
        """
        Triggers the exposure and waits for it to complete.
        """
        pass

    @abstractmethod
    async def take_acquisition_image(self, exposure_time: float = 5.0, binning: int = 2) -> str:
        """
        Takes a short exposure for closed-loop acquisition and returns the file path or image object.
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
            logger.error(f"Failed to save observations for {self.instrument_name}: {e}", exc_info=True)

    def load_from_disk(self):
        """
        Restores observations from the local JSON file if it exists.
        """
        if not self.cache_file.exists():
            logger.debug(f"No cache file found for {self.instrument_name}.")
            return

        try:
            with open(self.cache_file, "r") as f:
                raw_data = json.load(f)
                
            # Re-validate data back into Pydantic models
            self.observations = [ScheduleSchema.model_validate(c) for c in raw_data]
            logger.info(f"Restored {len(self.observations)} observations from {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to load observations for {self.instrument_name}: {e}", exc_info=True)

    def get_id(self) -> str:
        return self.instrument_name

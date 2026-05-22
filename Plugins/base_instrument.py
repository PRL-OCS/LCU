import os
import json
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
from core.communications.schemas import Configuration
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
        self.configs: List[Configuration] = []
        
        # Determine unique storage file
        self.cache_file = self.storage_dir / f"{self.instrument_name}_configs.json"

    def receive_schedule(self, configs: List[Configuration]):
        """
        Default callback: stores the schedule in memory and persists to disk.
        Can be overridden by subclasses if special processing is needed.
        """
        self.configs = configs
        logger.info(f"[{self.instrument_name}] received {len(configs)} new configs.")
        self.save_to_disk()

    def get_configuration(self, config_id: str) -> Configuration | None:
        """
        Retrieves a specific configuration by ID.
        """
        for config in self.configs:
            if config.id == config_id:
                return config
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


    def save_to_disk(self):
        """
        Serializes current configs and saves them to a local JSON file.
        """
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            config_data = [config.model_dump() for config in self.configs]
            
            with open(self.cache_file, "w") as f:
                json.dump(config_data, f, indent=4, default=str)
                
            logger.debug(f"Persisted {len(self.configs)} configs to {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to save configs for {self.instrument_name}: {e}", exc_info=True)

    def load_from_disk(self):
        """
        Restores configs from the local JSON file if it exists.
        """
        if not self.cache_file.exists():
            logger.debug(f"No cache file found for {self.instrument_name}.")
            return

        try:
            with open(self.cache_file, "r") as f:
                raw_data = json.load(f)
                
            # Re-validate data back into Pydantic models
            self.configs = [Configuration.model_validate(c) for c in raw_data]
            logger.info(f"Restored {len(self.configs)} configs from {self.cache_file}")
        except Exception as e:
            logger.error(f"Failed to load configs for {self.instrument_name}: {e}", exc_info=True)

    def get_id(self) -> str:
        return self.instrument_name

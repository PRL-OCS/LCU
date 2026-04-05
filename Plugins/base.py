import os
import json
from abc import ABC, abstractmethod
from typing import List
from pathlib import Path
from core.communications.schemas import Target

class TelescopePlugin(ABC):
    """
    Abstract base class for all telescope plugins in LCU_Node.
    Now receives only Target data subsets.
    Persists to storage/telescope.
    """
    
    # Class-level registry for discovered telescope blueprint classes
    registry = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Register the class using its own name
        TelescopePlugin.registry[cls.__name__] = cls
        print(f"[REGISTRY-TEL] Discovered telescope plugin class: {cls.__name__}")

    def __init__(self, telescope_id: str, storage_dir: str = "storage/telescope"):
        self.telescope_id = telescope_id
        self.storage_dir = Path(storage_dir)
        self.targets: List[Target] = []
        
        # Determine unique storage file
        self.cache_file = self.storage_dir / f"{self.telescope_id}_targets.json"

    @abstractmethod
    def receive_schedule(self, targets: List[Target]):
        """
        Callback method called by the ScheduleCoordinator when new targets 
        are available for this specific telescope.
        """
        pass

    def save_to_disk(self):
        """
        Serializes current targets and saves them to a local JSON file.
        """
        try:
            # Ensure directory exists
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Serialize: Convert Pydantic models to dicts
            target_data = [target.model_dump() for target in self.targets]
            
            with open(self.cache_file, "w") as f:
                json.dump(target_data, f, indent=4, default=str)
                
            print(f"[DISK-TEL] Persisted {len(self.targets)} targets to {self.cache_file}")
        except Exception as e:
            print(f"[DISK ERROR] Failed to save targets for {self.telescope_id}: {e}")

    def load_from_disk(self):
        """
        Restores targets from the local JSON file if it exists.
        """
        if not self.cache_file.exists():
            print(f"[DISK-TEL] No cache file found for {self.telescope_id}.")
            return

        try:
            with open(self.cache_file, "r") as f:
                raw_data = json.load(f)
                
            # Re-validate data back into Pydantic models
            self.targets = [Target.model_validate(t) for t in raw_data]
            print(f"[DISK-TEL] Restored {len(self.targets)} targets from {self.cache_file}")
        except Exception as e:
            print(f"[DISK ERROR] Failed to load targets for {self.telescope_id}: {e}")

    def get_id(self) -> str:
        return self.telescope_id

    
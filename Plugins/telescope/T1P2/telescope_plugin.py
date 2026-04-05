from Plugins.base import TelescopePlugin
from core.communications.schemas import Target
from typing import List

class DefaultTelescope(TelescopePlugin):
    """
    A concrete implementation of a telescope plugin.
    This one is identified as '1m0a' by default.
    Now works with Target data subsets.
    """
    
    def __init__(self, telescope_id: str = "T2P5"):
        super().__init__(telescope_id)
        print(f"[PLUGIN-TEL] {self.telescope_id} initialized.")
        
        # Load from disk on startup if a cache exists
        self.load_from_disk()

    def receive_schedule(self, targets: List[Target]):
        # Custom logic before or after the base behavior
        super().receive_schedule(targets)
        
        # Keep our custom debug print
        for i, target in enumerate(self.targets):
            print(f"  {i+1}. [TEL-TARGET] ID: {target.configuration_id} | Name: {target.name} | RA: {target.ra}")



from Plugins.base_telescope import TelescopePlugin
from core.communications.schemas import Target
from typing import List

class HotReloadTelescope(TelescopePlugin):
    """
    A temporary plugin to verify hot rescan functionality.
    """
    def __init__(self, telescope_id: str = "hot_reload_test"):
        super().__init__(telescope_id)
        
    def receive_schedule(self, tasks: List[Target]):
        self.targets = tasks
        self.save_to_disk()

    def start_schedule(self, target: Target):
        pass

    def force_stop(self):
        pass

    def pause(self):
        pass

    def get_current_telemetry(self) -> dict:
        return {}

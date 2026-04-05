from Plugins.base import TelescopePlugin
from core.communications.schemas import ScheduleSchema
from typing import List

class HotReloadTelescope(TelescopePlugin):
    """
    A temporary plugin to verify hot rescan functionality.
    """
    def __init__(self, telescope_id: str = "hot_reload_test"):
        super().__init__(telescope_id)
        
    def receive_schedule(self, tasks: List[ScheduleSchema]):
        self.tasks = tasks
        self.save_to_disk()

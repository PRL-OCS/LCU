import asyncio
from pathlib import Path
from core.plugins.manager import PluginManager
from core.schedule_coordinator import ScheduleCoordinator

class LCUOrchestrator:
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize internal components
        self.plugin_manager = PluginManager()
        self.coordinator = ScheduleCoordinator(self.plugin_manager)
        
        self._sync_task = None

    def initialize(self):
        """
        Initial plugin discovery and hardware mapping fetch.
        """
        print("[ORCHESTRATOR] Initializing LCU Node subsystems...")
        self.plugin_manager.discover_plugins()
        self.plugin_manager.fetch_hardware_mapping()
        
        t_count = len(self.plugin_manager.get_all_telescope_plugins())
        i_count = len(self.plugin_manager.get_all_instrument_plugins())
        m_count = len(self.plugin_manager.hardware_mapping)
        
        print(f"[ORCHESTRATOR] LCU Node ready with {t_count} telescopes, {i_count} instruments, and {m_count} mappings.")

    def start_background_tasks(self):
        """
        Starts the automated background loops.
        """
        if self._sync_task is None:
            print("[ORCHESTRATOR] Starting background scheduler...")
            self._sync_task = asyncio.create_task(self._periodic_sync_loop())

    async def _periodic_sync_loop(self):
        """
        Automated background loop that triggers a sync every 5 minutes.
        """
        print("[ORCHESTRATOR] Background sync loop started (Interval: 5 minutes).")
        while True:
            try:
                self.coordinator.sync_all()
            except Exception as e:
                print(f"[ORCHESTRATOR ERROR] Periodic sync failed: {e}")
            
            await asyncio.sleep(300)

    def sync_now(self):
        """
        Manually trigger a schedule sync.
        """
        self.coordinator.sync_all()

    def rescan_plugins(self):
        """
        Manually trigger discovery scan.
        """
        self.plugin_manager.discover_plugins()
        self.plugin_manager.fetch_hardware_mapping()
        return {
            "telescope_plugins": list(self.plugin_manager.get_all_telescope_plugins().keys()),
            "instrument_plugins": list(self.plugin_manager.get_all_instrument_plugins().keys()),
            "mapping_count": len(self.plugin_manager.hardware_mapping)
        }

    def get_system_status(self):
        """
        Aggregates status information for all managed hardware.
        """
        telescope_info = {}
        for tid, plugin in self.plugin_manager.get_all_telescope_plugins().items():
            telescope_info[tid] = {
                "target_count": len(plugin.targets),
                "cached_file": str(plugin.cache_file) if hasattr(plugin, 'cache_file') else None
            }
        
        instrument_info = {}
        for iid, plugin in self.plugin_manager.get_all_instrument_plugins().items():
            instrument_info[iid] = {
                "config_count": len(plugin.configs),
                "cached_file": str(plugin.cache_file) if hasattr(plugin, 'cache_file') else None
            }
            
        return {
            "status": "online",
            "storage_dir": str(self.storage_dir),
            "telescope_plugins": telescope_info,
            "instrument_plugins": instrument_info
        }

# Singleton instance for high-level control
orchestrator = LCUOrchestrator()

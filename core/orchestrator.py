import asyncio
from pathlib import Path
from core.plugins.manager import PluginManager
from core.schedule_coordinator import ScheduleCoordinator

from core.states.manager import state_manager, LCUState
from core.executors.manager import executor_manager
from core.logging_config import logger

from ingestion.file_watchdog import FileWatchdog


class LCUOrchestrator:
    def __init__(self, storage_dir: str = "storage"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize internal components
        self.plugin_manager = PluginManager()
        self.coordinator = ScheduleCoordinator(self.plugin_manager)
        self.watchdog = FileWatchdog(watch_dir=self.storage_dir / "cache")
        
        self._sync_task = None

    def initialize(self):
        """
        Initial plugin discovery and hardware mapping fetch.
        """
        state_manager.update_system_state(LCUState.INITIALIZING)
        logger.info("Initializing LCU Node subsystems...")
        self.plugin_manager.discover_plugins()
        self.plugin_manager.fetch_hardware_mapping()
        self.watchdog.initialize()
        
        executor_manager.start_all(self.plugin_manager)
        
        state_manager.update_system_state(LCUState.IDLE)
        
        t_count = len(self.plugin_manager.get_all_telescope_plugins())
        i_count = len(self.plugin_manager.get_all_instrument_plugins())
        m_count = len(self.plugin_manager.hardware_mapping)
        
        logger.info(f"LCU Node ready with {t_count} telescopes, {i_count} instruments, and {m_count} mappings.")

    def start_background_tasks(self):
        """
        Starts the automated background loops.
        """
        from core.states.uplink import uplink_manager
        
        if self._sync_task is None:
            logger.info("Starting background scheduler...")
            self._sync_task = asyncio.create_task(self._periodic_sync_loop())
            asyncio.create_task(self.watchdog.run_forever())
            asyncio.create_task(uplink_manager.start())

    async def _periodic_sync_loop(self):
        """
        Automated background loop that triggers a sync every 5 minutes.
        """
        logger.info("Background sync loop started (Interval: 5 minutes).")
        while True:
            try:
                self.coordinator.sync_all()
            except Exception as e:
                logger.error(f"Periodic sync failed: {e}")
            
            await asyncio.sleep(300)

    def sync_now(self):
        """
        Manually trigger a schedule sync.
        """
        self.coordinator.sync_all()

    def set_operating_mode(self, manual: bool):
        """
        Switches the system into or out of MANUAL operator mode.
        """
        from core.states.schemas import LCUState
        if manual:
            state_manager.update_system_state(LCUState.MANUAL)
        else:
            state_manager.update_system_state(LCUState.IDLE)

    def abort_telescope(self, telescope_id: str, reason: str = "Operator Abort"):
        """
        Aborts the specified telescope executor, putting it into manual mode.
        """
        executor_manager.abort_executor(telescope_id, reason)

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
            queued_reqs = []
            for obs in getattr(plugin, 'observations', []):
                queued_reqs.append(f"req_{obs.request.id}")
                
            telescope_info[tid] = {
                "queue_size": len(queued_reqs),
                "queued_items": queued_reqs,
                "cached_file": str(plugin.cache_file) if hasattr(plugin, 'cache_file') else None
            }
        
        instrument_info = {}
        for iid, plugin in self.plugin_manager.get_all_instrument_plugins().items():
            queued_cfgs = []
            for obs in getattr(plugin, 'observations', []):
                for cfg in obs.request.configurations:
                    queued_cfgs.append(f"cfg_{cfg.id}")
                    
            instrument_info[iid] = {
                "queue_size": len(queued_cfgs),
                "queued_items": queued_cfgs,
                "cached_file": str(plugin.cache_file) if hasattr(plugin, 'cache_file') else None
            }
            
        from core.logging_config import recent_logs
        return {
            "status": "online",
            "state_summary": state_manager.get_summary(),
            "storage_dir": str(self.storage_dir),
            "telescope_plugins": telescope_info,
            "instrument_plugins": instrument_info,
            "executors": executor_manager.get_status(),
            "hardware_mapping": self.plugin_manager.hardware_mapping,
            "recent_logs": list(recent_logs)
        }

# Singleton instance for high-level control
orchestrator = LCUOrchestrator()

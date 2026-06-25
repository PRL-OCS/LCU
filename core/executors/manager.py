from typing import Dict
from core.plugins.manager import PluginManager
from .telescope_executor import TelescopeExecutor
from core.logging_config import logger

class ExecutorManager:
    """
    Manages the lifecycle of all TelescopeExecutor threads.
    """
    def __init__(self):
        self.executors: Dict[str, TelescopeExecutor] = {}

    def start_all(self, plugin_manager: PluginManager):
        """
        Discovers active telescope plugins and spawns an executor for each.
        """
        telescopes = plugin_manager.get_all_telescope_plugins()
        if not telescopes:
            logger.warning("No telescope plugins loaded. Executors cannot be started.")
            return

        logger.info(f"Starting executors for {len(telescopes)} telescopes...")
        
        for t_id, plugin in telescopes.items():
            if t_id not in self.executors:
                executor = TelescopeExecutor(plugin, plugin_manager)
                self.executors[t_id] = executor
                executor.start()
            elif not self.executors[t_id]._running:
                self.executors[t_id].start()

    def stop_all(self):
        print(f"[EXECUTOR-MANAGER] Stopping all executors...")
        for executor in self.executors.values():
            executor.stop()

    def abort_executor(self, telescope_id: str, reason: str = "Operator Abort"):
        if telescope_id in self.executors:
            self.executors[telescope_id].abort(reason)
            logger.warning(f"Executor for {telescope_id} has been aborted and set to manual mode.")

    def get_status(self) -> dict:
        return {
            t_id: executor.get_status()
            for t_id, executor in self.executors.items()
        }

# Global singleton
executor_manager = ExecutorManager()

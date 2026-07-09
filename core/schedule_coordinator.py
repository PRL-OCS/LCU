from core.communications.api import fetch_schedule
from core.plugins.manager import PluginManager
from typing import List, Dict
from core.communications.schemas import ScheduleSchema
from core.logging_config import logger

class ScheduleCoordinator:
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        logger.info("ScheduleCoordinator initialized with unified plugin manager.")

    def sync_all(self):
        """
        
        1. Fetches the entire schedule.
        2. Groups tasks by telescope and instrument.
        3. Distributes the intact ScheduleSchema payload to respective plugins.
        """
        logger.info("Starting schedule sync...")
        
        try:
            # 1. Fetch entire schedule
            master_schedule = fetch_schedule()
            all_tasks = master_schedule.results
            logger.info(f"Fetched {len(all_tasks)} tasks from API.")
            
            # 2. Group tasks
            grouped_by_telescope: Dict[str, List[ScheduleSchema]] = {}
            grouped_by_instrument: Dict[str, List[ScheduleSchema]] = {}

            for task in all_tasks:
                if not task.request.configurations:
                    continue

                if getattr(task.request, 'state', '').upper() != "PENDING":
                    logger.warning(f"Task {task.id} skipped: state is {task.request.state}, not PENDING.")
                    continue

                # Filter configurations that are already in a terminal state
                from core.states.manager import state_manager
                from core.states.schemas import ObservationState
                
                active_configs = []
                for config in task.request.configurations:
                    pramana_config_id = getattr(config, 'configuration_status', None)
                    obs_id = f"config_status_{pramana_config_id}"
                    
                    if obs_id in state_manager.observations:
                        status = state_manager.observations[obs_id]
                        if status.current_state in [ObservationState.DONE, ObservationState.ERROR, ObservationState.ABORTED, ObservationState.REJECTED]:
                            continue # Skip this configuration as it's already finished
                    
                    active_configs.append(config)
                
                task.request.configurations = active_configs
                if not task.request.configurations:
                    continue # Skip the entire task if all configurations are completed

                t_id = task.telescope
                # We use the 'instrument_type' from the first configuration to identify the required instrument
                i_name = task.request.configurations[0].instrument_type

                # --- PLUGIN-BASED VALIDATION ---
                # 1. Access the loaded plugins
                t_plugins = self.plugin_manager.get_all_telescope_plugins()
                i_plugins = self.plugin_manager.get_all_instrument_plugins()

                # 2. Logic: If we dont have either telescope or instrument plugin, skip (safety)
                if t_id not in t_plugins or i_name not in i_plugins:
                    logger.warning(f"Task {task.id} skipped: Telescope '{t_id}' is ready but instrument '{i_name}' plugin is missing.")
                    continue
                
                # 3. Logic: If we don't have the telescope or it is offline, skip the task so it remains PENDING on PRAMANA
                t_plugin = t_plugins.get(t_id)
                if not t_plugin or not getattr(t_plugin, "is_connected", False):
                    logger.warning(f"Task {task.id} skipped: Telescope '{t_id}' is offline/disconnected.")
                    continue
                # ------------------------------


                # Group for Telescope
                if t_id not in grouped_by_telescope:
                    grouped_by_telescope[t_id] = []
                
                # Append the entire observation envelope
                grouped_by_telescope[t_id].append(task)


                # Group for Instrument
                if i_name not in grouped_by_instrument:
                    grouped_by_instrument[i_name] = []
                
                grouped_by_instrument[i_name].append(task)
            
            # 3. Distribute to Telescope Plugins
            t_plugins = self.plugin_manager.get_all_telescope_plugins()
            for t_id, plugin in t_plugins.items():
                targets = grouped_by_telescope.get(t_id, [])
                logger.info(f"Dispatching {len(targets)} targets to telescope plugin: {t_id}")
                plugin.receive_schedule(targets)
            
            # 4. Distribute to Instrument Plugins
            i_plugins = self.plugin_manager.get_all_instrument_plugins()
            for i_name, plugin in i_plugins.items():
                configs = grouped_by_instrument.get(i_name, [])
                logger.info(f"Dispatching {len(configs)} configs to instrument plugin: {i_name}")
                plugin.receive_schedule(configs)
                
            # 5. Logging Orphans
            for t_id in grouped_by_telescope:
                if t_id not in t_plugins:
                    logger.warning(f"No telescope plugin for '{t_id}'. {len(grouped_by_telescope[t_id])} targets ignored.")
            
            for i_name in grouped_by_instrument:
                if i_name not in i_plugins:
                    logger.info(f"No instrument plugin for '{i_name}'. {len(grouped_by_instrument[i_name])} configs ignored.")

            logger.info("Sync completed successfully.")
            
        except Exception as e:
            logger.error(f"Schedule sync failed: {e}", exc_info=True)

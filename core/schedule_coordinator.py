from core.communications.api import fetch_schedule
from core.plugins.manager import PluginManager
from typing import List, Dict
from core.communications.schemas import ScheduleSchema, Target, Configuration

class ScheduleCoordinator:
    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        print("[SYSTEM] ScheduleCoordinator initialized with unified plugin manager.")

    def sync_all(self):
        """
        
        1. Fetches the entire schedule.
        2. Groups tasks by telescope and instrument.
        3. Extracts subsets (Target and InstrumentConfig).
        4. Distributes to respective plugins.
        """
        print("\n" + "="*50)
        print("[SYSTEM] Starting schedule sync...")
        print("="*50)
        
        try:
            # 1. Fetch entire schedule
            master_schedule = fetch_schedule()
            all_tasks = master_schedule.results
            print(f"[SYSTEM] Fetched {len(all_tasks)} tasks from API.")
            
            # 2. Group tasks
            grouped_by_telescope: Dict[str, List[Target]] = {}
            grouped_by_instrument: Dict[str, List[Configuration]] = {}

            for task in all_tasks:
                if not task.request.configurations:
                    continue

                t_id = task.telescope
                # We use the 'instrument_type' from the first configuration to identify the required instrument
                i_name = task.request.configurations[0].instrument_type

                # --- PLUGIN-BASED VALIDATION ---
                # 1. Access the loaded plugins
                t_plugins = self.plugin_manager.get_all_telescope_plugins()
                i_plugins = self.plugin_manager.get_all_instrument_plugins()

                # 2. Logic: If we dont have either telescope or instrument plugin, skip (safety)
                if t_id not in t_plugins or i_name not in i_plugins:
                    print(f"[SYSTEM] Task {task.id} skipped: Telescope '{t_id}' is ready but instrument '{i_name}' plugin is missing.")
                    continue
                
                # 3. Logic: If we don't have the telescope, we can't do anything anyway
                if t_id not in t_plugins:
                    continue
                # ------------------------------


                # Extract Target for Telescope
                if t_id not in grouped_by_telescope:
                    grouped_by_telescope[t_id] = []
                
                # Use the target from the first configuration and "stamp" it with the configuration ID
                first_config = task.request.configurations[0]
                target = first_config.target.model_copy(update={"configuration_id": first_config.id})
                grouped_by_telescope[t_id].append(target)


                # Extract InstrumentConfigs for Instrument
                if i_name not in grouped_by_instrument:
                    grouped_by_instrument[i_name] = []
                
                # Flatten all configurations in this task
                for config in task.request.configurations:
                    grouped_by_instrument[i_name].append(config)
            
            # 3. Distribute to Telescope Plugins
            t_plugins = self.plugin_manager.get_all_telescope_plugins()
            for t_id, plugin in t_plugins.items():
                targets = grouped_by_telescope.get(t_id, [])
                print(f"[SYSTEM] Dispatching {len(targets)} targets to telescope plugin: {t_id}")
                plugin.receive_schedule(targets)
            
            # 4. Distribute to Instrument Plugins
            i_plugins = self.plugin_manager.get_all_instrument_plugins()
            for i_name, plugin in i_plugins.items():
                configs = grouped_by_instrument.get(i_name, [])
                print(f"[SYSTEM] Dispatching {len(configs)} configs to instrument plugin: {i_name}")
                plugin.receive_schedule(configs)
                
            # 5. Logging Orphans
            for t_id in grouped_by_telescope:
                if t_id not in t_plugins:
                    print(f"[WARNING] No telescope plugin for '{t_id}'. {len(grouped_by_telescope[t_id])} targets ignored.")
            
            for i_name in grouped_by_instrument:
                if i_name not in i_plugins:
                    print(f"[INFO] No instrument plugin for '{i_name}'. {len(grouped_by_instrument[i_name])} configs ignored.")

            print("="*50)
            print("[SYSTEM] Sync completed successfully.")
            print("="*50 + "\n")
            
        except Exception as e:
            print(f"[CRITICAL ERROR] Schedule sync failed: {e}")
            import traceback
            traceback.print_exc()

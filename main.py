import os
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from core.plugins.manager import PluginManager
from core.coordinator import ScheduleCoordinator

app = FastAPI(title="LCU_Node")

# 0. Configuration
STORAGE_DIR = "storage"
Path(STORAGE_DIR).mkdir(parents=True, exist_ok=True)

# 1. Initialize Unified Plugin Manager and Coordinator
plugin_manager = PluginManager()
coordinator = ScheduleCoordinator(plugin_manager)

import asyncio

@app.on_event("startup")
async def startup_event():
    """
    On startup, discover both telescope and instrument plugins,
    and start the automated 5-minute background sync.
    """
    plugin_manager.discover_plugins()
    plugin_manager.fetch_hardware_mapping()
    t_count = len(plugin_manager.get_all_telescope_plugins())
    i_count = len(plugin_manager.get_all_instrument_plugins())
    m_count = len(plugin_manager.hardware_mapping)
    print(f"[SYSTEM] LCU Node started with {t_count} telescopes, {i_count} instruments, and {m_count} mappings.")
    
    # START THE BACKGROUND SCHEDULER
    asyncio.create_task(periodic_sync_task())

async def periodic_sync_task():
    """
    Automated background loop that triggers a sync every 5 minutes.
    """
    print("[SYSTEM] Background scheduler started (Interval: 5 minutes).")
    while True:
        try:
            coordinator.sync_all()
        except Exception as e:
            print(f"[SCHEDULER ERROR] Periodic sync failed: {e}")
        
        # Wait for 300 seconds (5 minutes)
        await asyncio.sleep(300)


@app.get("/")
def read_root():
    telescope_info = {}
    for tid, plugin in plugin_manager.get_all_telescope_plugins().items():
        telescope_info[tid] = {
            "target_count": len(plugin.targets),
            "cached_file": str(plugin.cache_file) if hasattr(plugin, 'cache_file') else None
        }
    
    instrument_info = {}
    for iid, plugin in plugin_manager.get_all_instrument_plugins().items():
        instrument_info[iid] = {
            "config_count": len(plugin.configs),
            "cached_file": str(plugin.cache_file) if hasattr(plugin, 'cache_file') else None
        }
        
    return {
        "status": "online",
        "storage_dir": STORAGE_DIR,
        "telescope_plugins": telescope_info,
        "instrument_plugins": instrument_info
    }

@app.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Manually trigger a schedule sync.
    We run it as a background task so the API remains responsive.
    """
    background_tasks.add_task(coordinator.sync_all)
    return {"message": "Sync triggered in background."}

@app.post("/plugins/rescan")
async def rescan_plugins():
    """
    Manually trigger discovery scan for both telescope and instrument plugins.
    """
    plugin_manager.discover_plugins()
    plugin_manager.fetch_hardware_mapping()
    t_plugins = list(plugin_manager.get_all_telescope_plugins().keys())
    i_plugins = list(plugin_manager.get_all_instrument_plugins().keys())
    return {
        "message": "Plugin scan completed.",
        "telescope_count": len(t_plugins),
        "instrument_count": len(i_plugins),
        "mapping_count": len(plugin_manager.hardware_mapping),
        "telescope_plugins": t_plugins,
        "instrument_plugins": i_plugins
    }

@app.get("/telescope/{telescope_id}/tasks")
def get_telescope_tasks(telescope_id: str):
    """
    Helper endpoint to see what targets a specific telescope is holding.
    """
    plugin = plugin_manager.get_telescope_plugin(telescope_id)
    if not plugin:
        return {"error": "Telescope plugin not found."}, 404
    
    return {
        "telescope_id": telescope_id,
        "target_count": len(plugin.targets),
        "targets": [target.model_dump() for target in plugin.targets]
    }

@app.get("/instrument/{instrument_id}/tasks")
def get_instrument_tasks(instrument_id: str):
    """
    Helper endpoint to see what configs a specific instrument is holding.
    """
    plugin = plugin_manager.get_instrument_plugin(instrument_id)
    if not plugin:
        return {"error": "Instrument plugin not found."}, 404
    
    return {
        "instrument_id": instrument_id,
        "config_count": len(plugin.configs),
        "configs": [config.model_dump() for config in plugin.configs]
    }

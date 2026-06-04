import os
import asyncio
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks
from core.orchestrator import orchestrator
from nicegui import ui
import ui as lcu_ui

app = FastAPI(title="LCU_Node")

# 0. Configuration
STORAGE_DIR = "storage"
Path(STORAGE_DIR).mkdir(parents=True, exist_ok=True)

@app.on_event("startup")
async def startup_event():
    """
    On startup, delegating discovery and background tasks to the Orchestrator.
    """
    orchestrator.initialize()
    orchestrator.start_background_tasks()


@app.get("/")
def read_root():
    return orchestrator.get_system_status()

@app.post("/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """
    Manually trigger a schedule sync via the Orchestrator.
    """
    background_tasks.add_task(orchestrator.sync_now)
    return {"message": "Sync triggered in background via Orchestrator."}

@app.post("/plugins/rescan")
async def rescan_plugins():
    """
    Manually trigger discovery scan via the Orchestrator.
    """
    stats = orchestrator.rescan_plugins()
    return {
        "message": "Plugin scan completed by Orchestrator.",
        **stats
    }

@app.get("/telescope/{telescope_id}/tasks")
def get_telescope_tasks(telescope_id: str):
    """
    Helper endpoint to see what targets a specific telescope is holding.
    """
    plugin = orchestrator.plugin_manager.get_telescope_plugin(telescope_id)
    if not plugin:
        return {"error": "Telescope plugin not found."}, 404
    
    return {
        "telescope_id": telescope_id,
        "target_count": len(plugin.observations),
        "targets": [obs.model_dump() for obs in plugin.observations]
    }

@app.get("/instrument/{instrument_id}/tasks")
def get_instrument_tasks(instrument_id: str):
    """
    Helper endpoint to see what configs a specific instrument is holding.
    """
    plugin = orchestrator.plugin_manager.get_instrument_plugin(instrument_id)
    if not plugin:
        return {"error": "Instrument plugin not found."}, 404
    
    return {
        "instrument_id": instrument_id,
        "config_count": len(plugin.observations),
        "configs": [obs.model_dump() for obs in plugin.observations]
    }

# Build and mount the NiceGUI interface
ui.run_with(app, title="LCU Dashboard", mount_path="/dashboard", storage_secret="lcu_secret")


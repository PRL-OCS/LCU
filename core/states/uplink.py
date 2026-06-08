import asyncio
import time
from typing import Dict, Any, Optional
from core.logging_config import logger
from core.communications.api import push_configuration_status

class StateUplinkManager:
    """
    Asynchronously processes state and telemetry updates and pushes them to PRAMANA.
    This prevents network latency from blocking the LCU's hardware loops.
    """
    def __init__(self):
        self.queue = asyncio.Queue()
        self.running = False
        self._task: Optional[asyncio.Task] = None
        
        # Keep track of events per configuration status ID
        self._events_cache: Dict[int, list] = {}

    async def start(self):
        if not self.running:
            self.running = True
            self._task = asyncio.create_task(self._process_queue())
            logger.info("StateUplinkManager started.")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("StateUplinkManager stopped.")

    async def enqueue_configuration_status(self, config_status_id: int, lcu_state: str, error_message: str = "", exposure_time: float = 0.0):
        """
        Enqueue a configuration-level telemetry update.
        Maps the LCU internal state to the PRAMANA configuration status payload.
        """
        await self.queue.put({
            "type": "configuration",
            "config_status_id": config_status_id,
            "lcu_state": lcu_state,
            "error_message": error_message,
            "exposure_time": exposure_time,
            "timestamp": time.time()
        })

    async def _process_queue(self):
        while self.running:
            try:
                update = await self.queue.get()
                
                if update["type"] == "configuration":
                    # Process configuration status telemetry
                    config_id = update["config_status_id"]
                    lcu_state = update["lcu_state"]
                    timestamp = update["timestamp"]
                    error_message = update.get("error_message", "")
                    
                    # Ensure events list exists for this config
                    if config_id not in self._events_cache:
                        self._events_cache[config_id] = []
                        
                    # Append new event
                    event = {"state": lcu_state, "timestamp": timestamp}
                    self._events_cache[config_id].append(event)
                    
                    # Map to PRAMANA state
                    exposure_time = update.get("exposure_time", 0.0)
                    payload = self._build_config_payload(config_id, lcu_state, error_message, exposure_time)
                    
                    success = await asyncio.to_thread(push_configuration_status, config_id, payload)
                    if not success:
                        logger.warning(f"Uplink failed for config status {config_id}")
                        
                self.queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in StateUplinkManager loop: {e}", exc_info=True)
                
    def _build_config_payload(self, config_id: int, lcu_state: str, error_message: str, exposure_time: float) -> dict:
        """
        Maps LCU state to PRAMANA ConfigurationStatus PATCH payload.
        """
        from datetime import datetime, timezone
        
        # Get accumulated events
        events = self._events_cache.get(config_id, [])
        
        # Calculate start and end times based on events
        start_ts = events[0]["timestamp"] if events else time.time()
        end_ts = events[-1]["timestamp"] if events else time.time()
        
        start_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()
        end_iso = datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat()
        
        # Default payload structure
        payload = {
            "summary": {
                "events": events,
                "start": start_iso,
                "end": end_iso,
                "time_completed": exposure_time
            }
        }
        
        # Main mapping logic based on user rules
        if lcu_state == "PREPARING":
            payload["state"] = "ATTEMPTED"
            payload["summary"]["state"] = "ATTEMPTED"
            
        elif lcu_state in ["SLEWING", "CONFIGURING", "EXPOSING", "READING_OUT"]:
            # Keep state as ATTEMPTED implicitly (already set during PREPARING)
            payload["state"] = "ATTEMPTED"
            # Only update the summary internal state
            payload["summary"]["state"] = lcu_state
            
        elif lcu_state == "DONE":
            payload["state"] = "COMPLETED"
            payload["summary"]["state"] = "COMPLETED"
            
        elif lcu_state == "ERROR":
            payload["state"] = "FAILED"
            payload["summary"]["state"] = "FAILED"
            if error_message:
                payload["summary"]["reason"] = error_message
                
        elif lcu_state == "REJECTED":
            payload["state"] = "NOT_ATTEMPTED"
            payload["summary"]["state"] = "NOT_ATTEMPTED"
            if error_message:
                payload["summary"]["reason"] = error_message
                
        return payload

# Global instance
uplink_manager = StateUplinkManager()

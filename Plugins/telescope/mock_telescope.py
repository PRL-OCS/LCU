import asyncio
from typing import Dict, Any
from Plugins.base_telescope import TelescopePlugin
from core.communications.schemas import Target
from core.logging_config import logger

class MockTelescopePlugin(TelescopePlugin):
    """
    A mock telescope plugin for testing the executor pipeline.
    Simulates delays for slewing and tracking.
    """
    def __init__(self, telescope_id: str = "T100"):
        super().__init__(telescope_id=telescope_id)

    async def slew_to_target(self, target: Target):
        logger.info(f"[{self.telescope_id} - MOCK] Slewing to RA: {target.ra}, DEC: {target.dec}...")
        self.is_slewing = True
        
        start_ra = self.current_ra
        start_dec = self.current_dec
        
        import math
        dist_ra = target.ra - start_ra
        dist_dec = target.dec - start_dec
        total_dist = math.sqrt(dist_ra**2 + dist_dec**2)
        
        # Slew speed: 5 degrees per second
        slew_speed = 5.0
        total_time = total_dist / slew_speed if total_dist > 0 else 0
        if total_time < 2.0:
            total_time = 2.0
            
        step_duration = 0.5
        steps = max(int(total_time / step_duration), 1)
        
        for i in range(1, steps + 1):
            if not self.is_slewing:
                break # Interrupted/Cancelled
            await asyncio.sleep(step_duration)
            self.current_ra = round(start_ra + (dist_ra * (i / steps)), 4)
            self.current_dec = round(start_dec + (dist_dec * (i / steps)), 4)

        self.current_ra = target.ra
        self.current_dec = target.dec
        self.is_slewing = False
        logger.info(f"[{self.telescope_id} - MOCK] Slew complete.")

    async def start_tracking(self, target: Target):
        logger.info(f"[{self.telescope_id} - MOCK] Starting tracking for target {target.name}...")
        self.is_tracking = True
        await asyncio.sleep(1) # Small delay to engage tracking
        logger.info(f"[{self.telescope_id} - MOCK] Tracking engaged.")

    async def force_stop(self):
        logger.warning(f"[{self.telescope_id} - MOCK] EMERGENCY STOP triggered. Halting motors.")
        self.is_slewing = False
        self.is_tracking = False

    async def pause(self):
        logger.info(f"[{self.telescope_id} - MOCK] Pausing tracking.")
        self.is_tracking = False

    def get_current_telemetry(self) -> Dict[str, Any]:
        return {
            "telescope_id": self.telescope_id,
            "ra": self.current_ra,
            "dec": self.current_dec,
            "is_slewing": self.is_slewing,
            "is_tracking": self.is_tracking,
            "dome_status": self.dome_status
        }

import asyncio
from typing import Dict, Any
from Plugins.base_telescope import TelescopePlugin
from core.communications.schemas import Target
from core.logging_config import logger

class T200MockTelescopePlugin(TelescopePlugin):
    """
    A mock telescope plugin for T200 testing.
    """
    def __init__(self, telescope_id: str = "T200"):
        super().__init__(telescope_id=telescope_id)

    async def slew_to_target(self, target: Target):
        logger.info(f"[{self.telescope_id} - MOCK] Slewing to RA: {target.ra}, DEC: {target.dec}...")
        self.is_slewing = True
        # Simulate a variable slew time based on some arbitrary math or just a fixed delay
        await asyncio.sleep(2)
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

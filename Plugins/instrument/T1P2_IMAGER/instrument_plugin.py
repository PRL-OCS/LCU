import asyncio
from Plugins.base_instrument import InstrumentPlugin
from core.communications.schemas import Configuration, ScheduleSchema
from typing import List
from core.logging_config import logger

class T1P2ImagerPlugin(InstrumentPlugin):
    """
    A concrete implementation of an instrument plugin.
    This one is identified as 'T1P2_IMAGER' by default.
    Now works with full Configuration data models.
    """
    
    def __init__(self, instrument_name: str = "LISA"):
        super().__init__(instrument_name)
        print(f"[PLUGIN-INST] {self.instrument_name} initialized.")
        
        # Load from disk on startup if a cache exists
        self.load_from_disk()

    def receive_schedule(self, configs: List[ScheduleSchema]):
        """
        Hold the configs in memory AND persist to disk.
        """
        super().receive_schedule(configs)
        
        # Simple debug print
        for i, obs in enumerate(self.observations):
            for config in obs.request.configurations:
                for j, ic in enumerate(config.instrument_configs):
                    filter_val = ic.optical_elements.get('filter') or ic.optical_elements.get('Slit') or "Unknown"
                    print(f"  {i+1}.{j+1} [CONFIG] Opt: {filter_val} | Exp: {ic.exposure_time}s | Mode: {config.type}")

    async def configure(self, config: Configuration):
        logger.info(f"[{self.instrument_name}] Configuring instrument for config ID: {config.id}...")
        await asyncio.sleep(1)
        logger.info(f"[{self.instrument_name}] Configuration applied.")

    async def expose(self, config: Configuration):
        exposure_time = 3.0
        if config.instrument_configs and config.instrument_configs[0].exposure_time:
            exposure_time = float(config.instrument_configs[0].exposure_time)

        logger.info(f"[{self.instrument_name}] Opening shutter for {exposure_time} seconds...")
        await asyncio.sleep(exposure_time)
        logger.info(f"[{self.instrument_name}] Shutter closed.")



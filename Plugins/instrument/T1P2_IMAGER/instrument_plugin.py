from Plugins.base_instrument import InstrumentPlugin
from core.communications.schemas import Configuration
from typing import List

class T1P2ImagerPlugin(InstrumentPlugin):
    """
    A concrete implementation of an instrument plugin.
    This one is identified as 'T1P2_IMAGER' by default.
    Now works with full Configuration data models.
    """
    
    def __init__(self, instrument_name: str = "PARAS2"):
        super().__init__(instrument_name)
        print(f"[PLUGIN-INST] {self.instrument_name} initialized.")
        
        # Load from disk on startup if a cache exists
        self.load_from_disk()

    def receive_schedule(self, configs: List[Configuration]):
        """
        Hold the configs in memory AND persist to disk.
        """
        self.configs = configs
        print(f"[PLUGIN-INST] {self.instrument_name} received {len(configs)} configs.")
        
        # PERSIST: Save to storage/instrument/xxx_configs.json
        self.save_to_disk()
        
        # Simple debug print
        for i, config in enumerate(self.configs):
            # A configuration can have multiple instrument configs (exposures)
            for j, ic in enumerate(config.instrument_configs):
                filter_val = ic.optical_elements.get('filter') or ic.optical_elements.get('Slit') or "Unknown"
                print(f"  {i+1}.{j+1} [CONFIG] Opt: {filter_val} | Exp: {ic.exposure_time}s | Mode: {config.type}")


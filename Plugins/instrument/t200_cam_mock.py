import asyncio
import json
from pathlib import Path
from Plugins.base_instrument import InstrumentPlugin
from core.communications.schemas import Configuration
from core.logging_config import logger

class T200MockInstrumentPlugin(InstrumentPlugin):
    """
    A mock instrument plugin for T200 testing.
    """
    def __init__(self, instrument_name: str = "T200_CAM"):
        super().__init__(instrument_name=instrument_name)
        self.output_dir = Path("storage/cache")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def configure(self, config: Configuration):
        logger.info(f"[{self.instrument_name} - MOCK] Configuring instrument for config ID: {config.id}...")
        # Simulate filter wheel and readout setup
        await asyncio.sleep(1)
        logger.info(f"[{self.instrument_name} - MOCK] Configuration applied.")

    async def expose(self, config: Configuration):
        # We assume the config specifies an exposure time, if not default to 3s.
        exposure_time = 3.0
        if config.instrument_configs and config.instrument_configs[0].exposure_time:
            exposure_time = float(config.instrument_configs[0].exposure_time)

        logger.info(f"[{self.instrument_name} - MOCK] Opening shutter for {exposure_time} seconds...")
        await asyncio.sleep(exposure_time)
        logger.info(f"[{self.instrument_name} - MOCK] Shutter closed.")
        
        # Simulate readout and file generation
        await asyncio.sleep(1)
        self._generate_mock_fits(config.id)
        
    def _generate_mock_fits(self, config_id: int):
        """
        Since we are testing without a real CCD, we just drop a text file 
        or an empty .fits file into the cache directory for the FileWatchdog to find.
        """
        mock_file = self.output_dir / f"mock_image_{config_id}.fits"
        with open(mock_file, "w") as f:
            f.write("SIMPLE  =                    T / file does conform to FITS standard\n")
            f.write("BITPIX  =                   16 / number of bits per data pixel\n")
            f.write("NAXIS   =                    2 / number of data axes\n")
            f.write("END\n")
        logger.info(f"[{self.instrument_name} - MOCK] Generated mock FITS output: {mock_file}")

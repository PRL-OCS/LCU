import asyncio
import json
import shutil
import random
from pathlib import Path
from Plugins.base_instrument import InstrumentPlugin
from core.communications.schemas import Configuration
from core.logging_config import logger

class MockInstrumentPlugin(InstrumentPlugin):
    """
    A mock instrument plugin for testing the executor pipeline.
    Simulates configuring the camera and exposing a FITS file.
    """
    def __init__(self, instrument_name: str = "MOCK_CAM"):
        super().__init__(instrument_name=instrument_name)
        self.output_dir = Path("storage/cache")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def configure(self, config: Configuration):
        logger.info(f"[{self.instrument_name} - MOCK] Configuring instrument for config ID: {config.id}...")
        # Simulate filter wheel and readout setup
        await asyncio.sleep(1)
        logger.info(f"[{self.instrument_name} - MOCK] Configuration applied.")

    async def expose(self, config: Configuration) -> str:
        # We assume the config specifies an exposure time, if not default to 3s.
        exposure_time = 3.0
        if config.instrument_configs and config.instrument_configs[0].exposure_time:
            exposure_time = float(config.instrument_configs[0].exposure_time)

        logger.info(f"[{self.instrument_name} - MOCK] Opening shutter for {exposure_time} seconds...")
        await asyncio.sleep(exposure_time)
        logger.info(f"[{self.instrument_name} - MOCK] Shutter closed.")
        
        # Simulate readout and file generation
        file_path = self._generate_mock_fits(config.id)
        return file_path
        
    def _generate_mock_fits(self, config_id: int) -> str:
        """
        Copies a real FITS file from the ingester test files to simulate a real exposure.
        """
        mock_file = self.output_dir / f"mock_image_{config_id}.fits"
        real_fits_dir = Path("c:/prl/PRL_OCS/ingester_code/tests/test_files/fits")
        
        if real_fits_dir.exists():
            fits_files = list(real_fits_dir.glob("*.fits"))
            if fits_files:
                chosen_fits = random.choice(fits_files)
                shutil.copy(chosen_fits, mock_file)
                logger.info(f"[{self.instrument_name} - MOCK] Copied real FITS {chosen_fits.name} to {mock_file}")
                return str(mock_file.absolute())
                
        # Fallback if no real FITS files found
        with open(mock_file, "w") as f:
            f.write("SIMPLE  =                    T / file does conform to FITS standard\n")
            f.write("BITPIX  =                   16 / number of bits per data pixel\n")
            f.write("NAXIS   =                    2 / number of data axes\n")
            f.write("END\n")
        logger.info(f"[{self.instrument_name} - MOCK] Generated fallback text FITS: {mock_file}")
        return str(mock_file.absolute())

    async def take_acquisition_image(self) -> str:
        logger.info(f"[{self.instrument_name} - MOCK] Taking acquisition image...")
        await asyncio.sleep(1)
        
        mock_file = self.output_dir / f"mock_acq_image.fits"
        real_fits_dir = Path("c:/prl/PRL_OCS/ingester_code/tests/test_files/fits")
        
        if real_fits_dir.exists():
            fits_files = list(real_fits_dir.glob("*.fits"))
            if fits_files:
                chosen_fits = random.choice(fits_files)
                shutil.copy(chosen_fits, mock_file)
                return str(mock_file.absolute())
                
        # Fallback
        with open(mock_file, "w") as f:
            f.write("SIMPLE  =                    T / ACQ IMAGE\n")
            f.write("END\n")
        return str(mock_file.absolute())

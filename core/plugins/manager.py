import os
import importlib.util
import inspect
from typing import Dict
from Plugins.base_telescope import TelescopePlugin
from Plugins.base_instrument import InstrumentPlugin
from core.communications.api import fetch_instruments
from core.logging_config import logger

class PluginManager:
    def __init__(self, telescope_dir: str = "Plugins/telescope", instrument_dir: str = "Plugins/instrument"):
        self.telescope_dir = telescope_dir
        self.instrument_dir = instrument_dir
        self.telescope_registry: Dict[str, TelescopePlugin] = {}
        self.instrument_registry: Dict[str, InstrumentPlugin] = {}
        self.hardware_mapping: Dict[str, str] = {} # instrument_code -> telescope_id

    def discover_plugins(self):
        """
        Discovers both telescope and instrument plugins, and fetches hardware mapping.
        """
        self._discover_telescope_plugins()
        self._discover_instrument_plugins()

    def fetch_hardware_mapping(self):
        """
        Fetches the global instrument-to-telescope mapping from the API.
        """
        logger.info("Fetching hardware mapping from API...")
        try:
            mapping_response = fetch_instruments()
            self.hardware_mapping = {data.name: data.telescope_class for code, data in mapping_response.root.items()}
            logger.info(f"Hardware mapping updated with {len(self.hardware_mapping)} relationships.")

        except Exception as e:
            logger.error(f"Failed to fetch hardware mapping: {e}")

    def validate_belonging(self, telescope_id: str, instrument_name: str) -> bool:
        """
        Validates whether a specific instrument belongs to a specific telescope 
        according to the global mapping.
        """
        if not self.hardware_mapping:
            logger.warning("Hardware mapping is empty. Validation bypassed.")
            return True # Or False if we want to be strict
            
        assigned_telescope = self.hardware_mapping.get(instrument_name)
        if assigned_telescope is None:
            logger.warning(f"Unknown instrument '{instrument_name}'.")
            return False
            
        if assigned_telescope != telescope_id:
            logger.warning(f"Mismatch! {instrument_name} belongs to {assigned_telescope}, not {telescope_id}.")
            return False
            
        return True

    def _discover_telescope_plugins(self):
        logger.info(f"Discovering telescope plugins in {self.telescope_dir}...")
        if not os.path.exists(self.telescope_dir):
            logger.warning(f"Telescope plugin directory {self.telescope_dir} does not exist.")
            return

        TelescopePlugin.registry = {}
        self._load_modules_from_dir(self.telescope_dir, TelescopePlugin, TelescopePlugin.registry)
        
        self.telescope_registry = {}
        for class_name, plugin_class in TelescopePlugin.registry.items():
            try:
                instance = plugin_class() 
                self.telescope_registry[instance.get_id()] = instance
                logger.info(f"Loaded telescope plugin: {instance.get_id()}")
            except Exception as e:
                logger.error(f"Failed to instantiate telescope plugin {class_name}: {e}")

    def _discover_instrument_plugins(self):
        logger.info(f"Discovering instrument plugins in {self.instrument_dir}...")
        if not os.path.exists(self.instrument_dir):
            logger.warning(f"Instrument plugin directory {self.instrument_dir} does not exist.")
            return

        InstrumentPlugin.registry = {}
        self._load_modules_from_dir(self.instrument_dir, InstrumentPlugin, InstrumentPlugin.registry)
        
        self.instrument_registry = {}
        for class_name, plugin_class in InstrumentPlugin.registry.items():
            try:
                instance = plugin_class() 
                self.instrument_registry[instance.get_id()] = instance
                logger.info(f"Loaded instrument plugin: {instance.get_id()}")
            except Exception as e:
                logger.error(f"Failed to instantiate instrument plugin {class_name}: {e}")

    def _load_modules_from_dir(self, directory: str, base_class, registry: dict):
        for root, dirs, files in os.walk(directory):
            for filename in files:
                if filename.endswith(".py") and not filename.startswith("__"):
                    module_name = filename[:-3]
                    file_path = os.path.join(root, filename)
                    spec = importlib.util.spec_from_file_location(module_name, file_path)
                    if spec and spec.loader:
                        try:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            for name, obj in inspect.getmembers(module, inspect.isclass):
                                if issubclass(obj, base_class) and obj is not base_class:
                                    logger.debug(f"Discovered plugin class: {obj.__name__}")
                                    registry[obj.__name__] = obj
                        except Exception as e:
                            logger.error(f"Failed to import module {file_path}: {e}")

    def get_telescope_plugin(self, telescope_id: str) -> TelescopePlugin:
        return self.telescope_registry.get(telescope_id)

    def get_instrument_plugin(self, instrument_name: str) -> InstrumentPlugin:
        return self.instrument_registry.get(instrument_name)

    def get_all_telescope_plugins(self) -> Dict[str, TelescopePlugin]:
        return self.telescope_registry

    def get_all_instrument_plugins(self) -> Dict[str, InstrumentPlugin]:
        return self.instrument_registry

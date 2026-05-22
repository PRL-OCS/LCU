import asyncio
from core.states.manager import state_manager
from core.states.schemas import ObservationState
from Plugins.base_telescope import TelescopePlugin
from core.logging_config import logger

class TelescopeExecutor:
    """
    Executes observation workflows for a single telescope autonomously.
    """
    def __init__(self, telescope_plugin: TelescopePlugin, plugin_manager):
        self.telescope_plugin = telescope_plugin
        self.plugin_manager = plugin_manager
        self.telescope_id = self.telescope_plugin.get_id()
        self._running = False
        self._task = None

    async def run(self):
        self._running = True
        logger.info(f"Started loop for telescope: {self.telescope_id}")

        while self._running:
            try:
                target = self.telescope_plugin.get_next_target()
                if not target:
                    await asyncio.sleep(2)
                    continue

                obs_id = f"obs_cfg_{target.configuration_id}"
                
                logger.info(f"[{self.telescope_id}] Processing target for configuration {target.configuration_id}")
                state_manager.update_observation(obs_id, ObservationState.PREPARING)

                # Find matching instrument configuration
                matched_instrument = None
                matched_config = None
                
                for inst_id, inst_plugin in self.plugin_manager.get_all_instrument_plugins().items():
                    config = inst_plugin.get_configuration(target.configuration_id)
                    if config:
                        matched_instrument = inst_plugin
                        matched_config = config
                        logger.debug(f"[{self.telescope_id}] Found configuration for {target.configuration_id} on {inst_id}")
                        break
                
                if not matched_instrument:
                    logger.error(f"[{self.telescope_id}] No matching instrument config found for {target.configuration_id}. Aborting.")
                    state_manager.update_observation(obs_id, ObservationState.ABORTED, reason="Missing instrument configuration")
                    continue

                # SLEWING
                state_manager.update_observation(obs_id, ObservationState.SLEWING)
                logger.info(f"[{self.telescope_id}] Slewing to target...")
                await self.telescope_plugin.slew_to_target(target)
                await self.telescope_plugin.start_tracking(target)

                # CONFIGURING
                state_manager.update_observation(obs_id, ObservationState.CONFIGURING)
                logger.info(f"[{self.telescope_id}] Configuring instrument {matched_instrument.get_id()}...")
                await matched_instrument.configure(matched_config)

                # EXPOSING
                state_manager.update_observation(obs_id, ObservationState.EXPOSING)
                logger.info(f"[{self.telescope_id}] Exposing...")
                await matched_instrument.expose(matched_config)

                # READING_OUT
                state_manager.update_observation(obs_id, ObservationState.READING_OUT)
                logger.info(f"[{self.telescope_id}] Reading out...")
                await asyncio.sleep(1) 

                logger.info(f"[{self.telescope_id}] Execution complete for {obs_id}. Awaiting file detection.")
                
            except asyncio.CancelledError:
                logger.info(f"[{self.telescope_id}] Task cancelled.")
                break
            except Exception as e:
                logger.error(f"[{self.telescope_id}] Error during execution: {e}", exc_info=True)
                if 'obs_id' in locals():
                    state_manager.update_observation(obs_id, ObservationState.FAILED, reason=str(e))
                await asyncio.sleep(2)

    def start(self):
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.run())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    def get_status(self):
        return {
            "telescope_id": self.telescope_plugin.get_id(),
            "running": self._running,
            "queue_size": len(self.telescope_plugin.targets)
        }

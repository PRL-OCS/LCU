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
        self.current_obs_id = None
        self.current_ra = None
        self.current_dec = None
        self.exposure_start_time = None
        self.exposure_duration = None
        self.active_instrument = None
        self.abort_reason = None

    async def run(self):
        self._running = True
        logger.info(f"Started loop for telescope: {self.telescope_id}")

        while self._running:
            try:
                from core.states.schemas import LCUState
                if state_manager.system_state == LCUState.MANUAL:
                    await asyncio.sleep(2)
                    continue

                obs = getattr(self.telescope_plugin, 'get_next_observation', lambda: None)()
                if not obs:
                    await asyncio.sleep(2)
                    continue

                # --- Gap 10: Time-Aware Execution ---
                # Check if the observation is scheduled for the future
                import datetime
                now = datetime.datetime.now(datetime.timezone.utc)
                
                # --- Gap 9: Dynamic Constraint Validation (Time Expiration) ---
                if getattr(obs, 'end', None) and obs.end < now:
                    logger.warning(f"[{self.telescope_id}] Observation {obs.id} time window expired ({obs.end}). Rejecting.")
                    for config_item in obs.request.configurations:
                        state_manager.update_observation(f"obs_cfg_{config_item.target.configuration_id}", ObservationState.FAILED, reason="Time window expired")
                    continue

                if obs.start > now:
                    delay = (obs.start - now).total_seconds()
                    logger.info(f"[{self.telescope_id}] Observation {obs.id} scheduled in the future. Waiting {delay:.1f}s...")
                    await asyncio.sleep(delay)

                # Loop through a shallow copy of configurations to prevent iterator skipping 
                # when the instrument plugin pops them out of the shared schema list.
                for config_item in list(obs.request.configurations):
                    target = config_item.target
                    target.configuration_id = config_item.id

                    obs_id = f"obs_cfg_{target.configuration_id}"
                    self.current_obs_id = obs_id
                    
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
                            self.active_instrument = inst_plugin
                            logger.debug(f"[{self.telescope_id}] Found configuration for {target.configuration_id} on {inst_id}")
                            break
                    
                    if not matched_instrument:
                        logger.error(f"[{self.telescope_id}] No matching instrument config found for {target.configuration_id}. Aborting.")
                        state_manager.update_observation(obs_id, ObservationState.ABORTED, reason="Missing instrument configuration")
                        continue

                    # --- Gap 9: Dynamic Constraint Validation (Altitude/Safety) ---
                    min_altitude = matched_config.constraints.get('min_altitude')
                    if min_altitude is not None:
                        # In a real system, calculate actual altitude from RA/DEC + LST. 
                        # Using a mock value for demonstration.
                        current_alt = 45.0 
                        if current_alt < float(min_altitude):
                            logger.error(f"[{self.telescope_id}] Altitude constraint violated ({current_alt} < {min_altitude}). Aborting target.")
                            state_manager.update_observation(obs_id, ObservationState.FAILED, reason="Constraint violation: min_altitude")
                            continue

                    # SLEWING
                    if self.current_ra != target.ra or self.current_dec != target.dec:
                        state_manager.update_observation(obs_id, ObservationState.SLEWING)
                        logger.info(f"[{self.telescope_id}] Slewing to target {target.ra}, {target.dec}...")
                        await self.telescope_plugin.slew_to_target(target)
                        self.current_ra = target.ra
                        self.current_dec = target.dec
                    else:
                        logger.info(f"[{self.telescope_id}] Already pointing at {target.ra}, {target.dec}. Skipping slew.")
                        state_manager.update_observation(obs_id, ObservationState.SLEWING) # Flash state for continuity
                        
                    await self.telescope_plugin.start_tracking(target)

                    # CONFIGURING
                    state_manager.update_observation(obs_id, ObservationState.CONFIGURING)
                    logger.info(f"[{self.telescope_id}] Configuring instrument {matched_instrument.get_id()}...")
                    await matched_instrument.configure(matched_config)

                    # EXPOSING
                    state_manager.update_observation(obs_id, ObservationState.EXPOSING)
                    
                    # Extract exposure time for telemetry
                    exposure_time = 0.0
                    if matched_config.instrument_configs and matched_config.instrument_configs[0].exposure_time:
                        exposure_time = float(matched_config.instrument_configs[0].exposure_time)
                        
                    import time
                    self.exposure_start_time = time.time()
                    self.exposure_duration = exposure_time
                    
                    logger.info(f"[{self.telescope_id}] Exposing for {exposure_time}s...")
                    await matched_instrument.expose(matched_config)
                    
                    self.exposure_start_time = None
                    self.exposure_duration = None

                    # READING_OUT
                    state_manager.update_observation(obs_id, ObservationState.READING_OUT)
                    logger.info(f"[{self.telescope_id}] Reading out...")
                    await asyncio.sleep(1) 

                    logger.info(f"[{self.telescope_id}] Execution complete for {obs_id}. Awaiting file detection.")
                    self.current_obs_id = None
                
            except asyncio.CancelledError:
                logger.info(f"[{self.telescope_id}] Task cancelled.")
                if self.abort_reason:
                    logger.warning(f"[{self.telescope_id}] EMERGENCY ABORT TRIGGERED: {self.abort_reason}")
                    if getattr(self, 'current_obs_id', None):
                        state_manager.update_observation(self.current_obs_id, ObservationState.ABORTED, reason=self.abort_reason)
                    
                    # Fire-and-forget hardware stops to avoid cancellation propagation
                    asyncio.create_task(self.telescope_plugin.force_stop())
                    if self.active_instrument:
                        asyncio.create_task(self.active_instrument.force_stop())
                break
            except Exception as e:
                logger.error(f"[{self.telescope_id}] Error during execution: {e}", exc_info=True)
                if 'obs_id' in locals():
                    state_manager.update_observation(obs_id, ObservationState.FAILED, reason=str(e))
                self.current_obs_id = None
                await asyncio.sleep(2)

    def start(self):
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.run())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    def abort(self, reason: str):
        """
        Emergency stop mechanism.
        """
        logger.error(f"[{self.telescope_id}] Abort requested: {reason}")
        self.abort_reason = reason
        self._running = False
        if self._task:
            self._task.cancel()

    def get_status(self):
        # Find the state of the current observation from the state manager
        current_state = "IDLE"
        if self.current_obs_id:
            status_obj = state_manager.get_observation_status(self.current_obs_id)
            if status_obj:
                current_state = status_obj.current_state.value
                
        return {
            "telescope_id": self.telescope_plugin.get_id(),
            "running": self._running,
            "queue_size": len(getattr(self.telescope_plugin, 'observations', [])),
            "current_obs_id": self.current_obs_id,
            "current_state": current_state,
            "current_ra": getattr(self.telescope_plugin, 'current_ra', self.current_ra),
            "current_dec": getattr(self.telescope_plugin, 'current_dec', self.current_dec),
            "exposure_start_time": self.exposure_start_time,
            "exposure_duration": self.exposure_duration
        }

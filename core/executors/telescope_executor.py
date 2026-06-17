import asyncio
from core.states.manager import state_manager
from core.states.schemas import ObservationState
from Plugins.base_telescope import TelescopePlugin
from core.logging_config import logger
from core.acquisition.manager import AcquisitionManager

class TelescopeExecutor:
    """
    Executes observation workflows for a single telescope autonomously.
    """
    def __init__(self, telescope_plugin: TelescopePlugin, plugin_manager):
        self.telescope_plugin = telescope_plugin
        self.plugin_manager = plugin_manager
        self.acquisition_manager = AcquisitionManager()
        self.telescope_id = self.telescope_plugin.get_id()
        self._running = False
        self._task = None
        self._telemetry_task = None
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
                if getattr(obs, 'end', None):
                    # Estimate required time for this observation
                    total_exposure_time = 0
                    for cfg in obs.request.configurations:
                        if getattr(cfg, 'instrument_configs', None) and getattr(cfg.instrument_configs[0], 'exposure_time', None):
                            total_exposure_time += float(cfg.instrument_configs[0].exposure_time)
                    
                    # Arbitrary overheads are already handled by the Observation Portal.
                    # We just ensure the raw exposure time still fits within the remaining window.
                    expected_end = now + datetime.timedelta(seconds=total_exposure_time)
                    
                    if expected_end > obs.end:
                        logger.warning(f"[{self.telescope_id}] Observation {obs.id} requires {total_exposure_time}s exposure but window ends at {obs.end}. Rejecting.")
                        for config_item in obs.request.configurations:
                            state_manager.update_observation(
                                f"config_status_{config_item.configuration_status}", 
                                ObservationState.REJECTED, 
                                reason="Insufficient time remaining in window",
                                pramana_obs_id=obs.id,
                                pramana_config_id=config_item.configuration_status
                            )
                        # Clear from local cache since we are dropping it
                        getattr(self.telescope_plugin, 'complete_current_observation', lambda: None)()
                        continue

                if obs.start > now:
                    delay = (obs.start - now).total_seconds()
                    logger.info(f"[{self.telescope_id}] Observation {obs.id} scheduled in the future. Waiting {delay:.1f}s...")
                    await asyncio.sleep(delay)

                # Loop through a shallow copy of configurations to prevent iterator skipping 
                # when the instrument plugin pops them out of the shared schema list.
                for config_item in list(obs.request.configurations):
                    target = config_item.target
                    pramana_config_id = getattr(config_item, 'configuration_status', None)
                    target.configuration_id = pramana_config_id  # Ensure the instrument gets the right ID

                    obs_id = f"config_status_{pramana_config_id}"
                    self.current_obs_id = obs_id
                    
                    logger.info(f"[{self.telescope_id}] Processing target for configuration status {pramana_config_id}")
                    state_manager.update_observation(
                        obs_id, 
                        ObservationState.PREPARING,
                        pramana_obs_id=obs.id,
                        pramana_config_id=pramana_config_id
                    )

                    # Find matching instrument configuration
                    matched_instrument = None
                    matched_config = None
                    
                    for inst_id, inst_plugin in self.plugin_manager.get_all_instrument_plugins().items():
                        config = inst_plugin.get_configuration(pramana_config_id)
                        if config:
                            matched_instrument = inst_plugin
                            matched_config = config
                            self.active_instrument = inst_plugin
                            logger.debug(f"[{self.telescope_id}] Found configuration for {pramana_config_id} on {inst_id}")
                            break
                    
                    if not matched_instrument:
                        logger.error(f"[{self.telescope_id}] No matching instrument config found for {pramana_config_id}. Aborting.")
                        state_manager.update_observation(
                            obs_id, 
                            ObservationState.ABORTED, 
                            reason="Missing instrument configuration",
                            pramana_obs_id=obs.id,
                            pramana_config_id=pramana_config_id
                        )
                        continue

                    # --- Gap 9: Dynamic Constraint Validation (Altitude/Safety) ---
                    min_altitude = matched_config.constraints.get('min_altitude')
                    if min_altitude is not None:
                        # In a real system, calculate actual altitude from RA/DEC + LST. 
                        # Using a mock value for demonstration.
                        current_alt = 45.0 
                        if current_alt < float(min_altitude):
                            logger.error(f"[{self.telescope_id}] Altitude constraint violated ({current_alt} < {min_altitude}). Aborting target.")
                            state_manager.update_observation(
                                obs_id, 
                                ObservationState.REJECTED, 
                                reason="Constraint violation: min_altitude",
                                pramana_obs_id=obs.id,
                                pramana_config_id=pramana_config_id
                            )
                            continue

                    # Update executor coordinates from plugin telemetry
                    try:
                        self.telescope_plugin.get_current_telemetry()
                    except Exception:
                        pass
                    self.current_ra = getattr(self.telescope_plugin, 'current_ra', self.current_ra)
                    self.current_dec = getattr(self.telescope_plugin, 'current_dec', self.current_dec)

                    # SLEWING
                    if self.current_ra != target.ra or self.current_dec != target.dec:
                        state_manager.update_observation(obs_id, ObservationState.SLEWING, pramana_obs_id=obs.id, pramana_config_id=pramana_config_id)
                        logger.info(f"[{self.telescope_id}] Slewing to target {target.ra}, {target.dec}...")
                        await self.telescope_plugin.slew_to_target(target)
                        
                        # Sync coordinates post-slew
                        try:
                            self.telescope_plugin.get_current_telemetry()
                        except Exception:
                            pass
                        self.current_ra = getattr(self.telescope_plugin, 'current_ra', self.current_ra)
                        self.current_dec = getattr(self.telescope_plugin, 'current_dec', self.current_dec)
                    else:
                        logger.info(f"[{self.telescope_id}] Already pointing at {target.ra}, {target.dec}. Skipping slew.")
                        state_manager.update_observation(obs_id, ObservationState.SLEWING, pramana_obs_id=obs.id, pramana_config_id=pramana_config_id) # Flash state for continuity
                        
                    await self.telescope_plugin.start_tracking(target)

                    # --- ACQUISITION LOOP ---
                    # Only acquire if target requires it (could be based on target.type or config)
                    # For now, we attempt acquisition on all targets
                    state_manager.update_observation(obs_id, ObservationState.ACQUIRING, pramana_obs_id=obs.id, pramana_config_id=pramana_config_id)
                    logger.info(f"[{self.telescope_id}] Handing over to AcquisitionManager...")
                    
                    acquired = await self.acquisition_manager.acquire_target(target, self.telescope_plugin, matched_instrument)
                    if not acquired:
                        logger.error(f"[{self.telescope_id}] Failed to acquire target {target.name}. Aborting observation.")
                        state_manager.update_observation(
                            obs_id, 
                            ObservationState.ABORTED, 
                            reason="Target acquisition failed",
                            pramana_obs_id=obs.id,
                            pramana_config_id=pramana_config_id
                        )
                        continue

                    # CONFIGURING
                    state_manager.update_observation(obs_id, ObservationState.CONFIGURING, pramana_obs_id=obs.id, pramana_config_id=pramana_config_id)
                    logger.info(f"[{self.telescope_id}] Configuring instrument {matched_instrument.get_id()}...")
                    await matched_instrument.configure(matched_config)

                    # EXPOSING
                    state_manager.update_observation(obs_id, ObservationState.EXPOSING, pramana_obs_id=obs.id, pramana_config_id=pramana_config_id)
                    
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
                    state_manager.update_observation(obs_id, ObservationState.READING_OUT, pramana_obs_id=obs.id, pramana_config_id=pramana_config_id)
                    logger.info(f"[{self.telescope_id}] Reading out...")
                    await asyncio.sleep(1) 
                    
                    state_manager.update_observation(
                        obs_id, 
                        ObservationState.DONE, 
                        pramana_obs_id=obs.id, 
                        pramana_config_id=pramana_config_id,
                        exposure_time=exposure_time
                    )

                    logger.info(f"[{self.telescope_id}] Execution complete for {obs_id}. Awaiting file detection.")
                    self.current_obs_id = None
                
                # All configurations complete for this observation. Now clear from local cache.
                getattr(self.telescope_plugin, 'complete_current_observation', lambda: None)()
                
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
                    # We may not have pramana_obs_id locally if it crashed before config iteration, 
                    # but usually it crashes inside the config iteration.
                    p_obs_id = locals().get('obs', type('obj', (object,), {'id': None})).id
                    p_config_id = locals().get('pramana_config_id', None)
                    state_manager.update_observation(
                        obs_id, 
                        ObservationState.ERROR, 
                        reason=str(e),
                        pramana_obs_id=p_obs_id,
                        pramana_config_id=p_config_id
                    )
                self.current_obs_id = None
                # Clear from cache so we don't get stuck in a crash loop with a bad target
                getattr(self.telescope_plugin, 'complete_current_observation', lambda: None)()
                await asyncio.sleep(2)

    def start(self):
        self._running = True
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self.run())
        if not self._telemetry_task or self._telemetry_task.done():
            self._telemetry_task = asyncio.create_task(self._telemetry_loop())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
        if self._telemetry_task:
            self._telemetry_task.cancel()

    def abort(self, reason: str):
        """
        Emergency stop mechanism.
        """
        logger.error(f"[{self.telescope_id}] Abort requested: {reason}")
        self.abort_reason = reason
        self._running = False
        if self._task:
            self._task.cancel()
        if self._telemetry_task:
            self._telemetry_task.cancel()

    async def _telemetry_loop(self):
        logger.info(f"Started telemetry loop for telescope: {self.telescope_id}")
        while self._running:
            try:
                # Query get_current_telemetry in a separate thread to not block main loop
                await asyncio.get_event_loop().run_in_executor(
                    None, self.telescope_plugin.get_current_telemetry
                )
            except Exception as e:
                logger.error(f"[{self.telescope_id}] Telemetry loop error: {e}")
            await asyncio.sleep(1.0)

    def get_status(self):
        # Find the state of the current observation from the state manager
        current_state = "IDLE"
        if self.current_obs_id:
            status_obj = state_manager.get_observation_status(self.current_obs_id)
            if status_obj:
                current_state = status_obj.current_state.value
                
        # Read from cached telemetry
        telemetry = {}
        if hasattr(self.telescope_plugin, '_last_telemetry_cache') and self.telescope_plugin._last_telemetry_cache:
            telemetry = self.telescope_plugin._last_telemetry_cache
            
        status_dict = {
            "telescope_id": self.telescope_plugin.get_id(),
            "running": self._running,
            "queue_size": len(getattr(self.telescope_plugin, 'observations', [])),
            "current_obs_id": self.current_obs_id,
            "current_state": current_state,
            "current_ra": telemetry.get("ra", getattr(self.telescope_plugin, 'current_ra', self.current_ra)),
            "current_dec": telemetry.get("dec", getattr(self.telescope_plugin, 'current_dec', self.current_dec)),
            "exposure_start_time": self.exposure_start_time,
            "exposure_duration": self.exposure_duration
        }

        # Merge additional telemetry keys from the plugin
        if isinstance(telemetry, dict):
            for k, v in telemetry.items():
                if k not in status_dict:
                    status_dict[k] = v

        return status_dict

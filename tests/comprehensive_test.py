import asyncio
from core.orchestrator import orchestrator
from core.communications.schemas import Target, Configuration, InstrumentConfig
from core.states.manager import state_manager
from core.logging_config import logger

async def run_scenario_1_normal_flow(mock_t, mock_i):
    logger.info("=== SCENARIO 1: NORMAL FLOW ===")
    target = Target(configuration_id=101, type="ICRS", name="Test 1", ra=10.0, dec=20.0, epoch=2000.0)
    config = Configuration(id=101, instrument_type="MOCK_CAM", type="TEST", priority=1, 
                           instrument_configs=[InstrumentConfig(mode="IMG", exposure_time=1.0)], 
                           target=target, configuration_status=1, state="PENDING", instrument_name="MOCK_CAM")
    
    mock_i.receive_schedule([config])
    mock_t.receive_schedule([target])
    
    # Wait for completion
    for _ in range(10):
        await asyncio.sleep(1)
        if "obs_cfg_101" in state_manager.observations:
            state = state_manager.observations["obs_cfg_101"].current_state.value
            if state in ["COMPLETED", "FAILED", "ABORTED", "READING_OUT"]:
                logger.info(f"Scenario 1 ended in state: {state}")
                break

async def run_scenario_2_missing_config(mock_t, mock_i):
    logger.info("=== SCENARIO 2: MISSING INSTRUMENT CONFIG ===")
    target = Target(configuration_id=102, type="ICRS", name="Test 2", ra=15.0, dec=25.0, epoch=2000.0)
    # We do NOT send the configuration to the instrument plugin
    
    mock_t.receive_schedule([target])
    
    for _ in range(5):
        await asyncio.sleep(1)
        if "obs_cfg_102" in state_manager.observations:
            state = state_manager.observations["obs_cfg_102"].current_state.value
            if state in ["COMPLETED", "FAILED", "ABORTED"]:
                logger.info(f"Scenario 2 ended in state: {state}")
                break

async def run_scenario_3_multiple_queue(mock_t, mock_i):
    logger.info("=== SCENARIO 3: MULTIPLE QUEUE PROCESSING ===")
    targets = [
        Target(configuration_id=103, type="ICRS", name="Test 3A", ra=1.0, dec=1.0, epoch=2000.0),
        Target(configuration_id=104, type="ICRS", name="Test 3B", ra=2.0, dec=2.0, epoch=2000.0)
    ]
    configs = [
        Configuration(id=103, instrument_type="MOCK_CAM", type="TEST", priority=1, instrument_configs=[InstrumentConfig(mode="IMG", exposure_time=1.0)], target=targets[0], configuration_status=1, state="PENDING", instrument_name="MOCK_CAM"),
        Configuration(id=104, instrument_type="MOCK_CAM", type="TEST", priority=1, instrument_configs=[InstrumentConfig(mode="IMG", exposure_time=1.0)], target=targets[1], configuration_status=1, state="PENDING", instrument_name="MOCK_CAM")
    ]
    
    mock_i.receive_schedule(configs)
    mock_t.receive_schedule(targets)
    
    for _ in range(15):
        await asyncio.sleep(1)
        if "obs_cfg_104" in state_manager.observations:
            state = state_manager.observations["obs_cfg_104"].current_state.value
            if state in ["COMPLETED", "FAILED", "ABORTED", "READING_OUT"]:
                logger.info("Scenario 3 ended (processed queue).")
                break

async def main():
    logger.info("Starting Comprehensive Test Suite...")
    orchestrator.initialize()
    
    t_plugins = orchestrator.plugin_manager.get_all_telescope_plugins()
    i_plugins = orchestrator.plugin_manager.get_all_instrument_plugins()
    
    mock_t = t_plugins.get("T100")
    mock_i = i_plugins.get("MOCK_CAM")
    
    if not mock_t or not mock_i:
        logger.error("Mock plugins not found!")
        return

    # Clear existing state
    mock_t.targets.clear()
    mock_i.configs.clear()
    
    await run_scenario_1_normal_flow(mock_t, mock_i)
    await run_scenario_2_missing_config(mock_t, mock_i)
    await run_scenario_3_multiple_queue(mock_t, mock_i)
    
    # Let final background tasks settle
    await asyncio.sleep(2)
    
    logger.info("Test Suite Completed.")
    
if __name__ == "__main__":
    asyncio.run(main())

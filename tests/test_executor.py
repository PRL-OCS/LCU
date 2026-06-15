import asyncio
from core.orchestrator import orchestrator
from core.communications.schemas import Target, Configuration, InstrumentConfig

async def test_flow():
    print("--- Starting LCU Initialization ---")
    orchestrator.initialize()
    
    # Check plugins
    t_plugins = orchestrator.plugin_manager.get_all_telescope_plugins()
    i_plugins = orchestrator.plugin_manager.get_all_instrument_plugins()
    
    print(f"Telescopes discovered: {list(t_plugins.keys())}")
    print(f"Instruments discovered: {list(i_plugins.keys())}")
    
    mock_t = t_plugins.get("T100")
    mock_i = i_plugins.get("MOCK_CAM")
    
    if not mock_t or not mock_i:
        print("Mock plugins not found! Did you delete them?")
        return

    print("\n--- Injecting Mock Schedule Data ---")
    # Create a mock target
    target = Target(
        configuration_id=999,
        type="ICRS",
        name="Sirius",
        ra=101.287,
        dec=-16.716,
        epoch=2000.0
    )
    
    # Create a matching instrument configuration
    config = Configuration(
        id=999,
        instrument_type="MOCK_CAM",
        type="TEST",
        priority=1,
        instrument_configs=[InstrumentConfig(mode="IMG", exposure_time=2.5)],
        target=target,
        configuration_status=1,
        state="PENDING",
        instrument_name="MOCK_CAM"
    )
    
    # Inject directly into the plugins to bypass the API
    mock_i.receive_schedule([config])
    mock_t.receive_schedule([target])
    
    print("\n--- Monitoring Executor Flow ---")
    # Wait to let the executor process it
    for i in range(12):
        await asyncio.sleep(1)
        summary = orchestrator.get_system_status()['state_summary']
        if 'obs_cfg_999' in summary['active_observations']:
            current_state = summary['active_observations']['obs_cfg_999']
            print(f"[TEST MON] Second {i+1}: Observation obs_cfg_999 is in state: {current_state}")
        else:
            print(f"[TEST MON] Second {i+1}: Observation obs_cfg_999 not active or completed.")
        
    print("\n--- Test Complete ---")

if __name__ == "__main__":
    asyncio.run(test_flow())

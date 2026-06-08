import pytest
import asyncio
import datetime
from unittest.mock import patch, MagicMock

from core.communications.schemas import (
    ScheduleAPIResponse, ScheduleSchema, RequestSchema, Configuration, Target, InstrumentConfig
)
from core.schedule_coordinator import ScheduleCoordinator
from core.plugins.manager import PluginManager
from core.executors.telescope_executor import TelescopeExecutor
from Plugins.telescope.mock_telescope import MockTelescopePlugin
from Plugins.instrument.t200_cam_mock import T200MockInstrumentPlugin
from core.states.manager import state_manager

@pytest.fixture
def dummy_schedule():
    now = datetime.datetime.now(datetime.timezone.utc)
    
    cfg1 = Configuration(
        id=1, instrument_type="T200_CAM", type="exposure", priority=1,
        instrument_configs=[InstrumentConfig(mode="img", exposure_time=10.0)],
        target=Target(type="SIDEREAL", name="Target1", ra=10.0, dec=20.0, epoch=2000.0),
        configuration_status=1001, state="PENDING", instrument_name="T200_CAM"
    )
    req1 = RequestSchema(id=101, state="PENDING", observation_note="1", acceptability_threshold=90.0, modified=now, duration=0, configurations=[cfg1])
    task1 = ScheduleSchema(id=10, request=req1, site="site", enclosure="enc", priority=1, state="PENDING", proposal="1", submitter="sub", name="name", ipp_value=0.0, observation_type="type", request_group_id=1, created=now, modified=now, telescope="T200", start=now, end=now + datetime.timedelta(minutes=5))
    
    cfg2 = Configuration(
        id=2, instrument_type="T200_CAM", type="exposure", priority=1,
        instrument_configs=[InstrumentConfig(mode="img", exposure_time=10.0)],
        target=Target(type="SIDEREAL", name="Target2", ra=10.0, dec=20.0, epoch=2000.0),
        configuration_status=1002, state="PENDING", instrument_name="T200_CAM"
    )
    req2 = RequestSchema(id=102, state="CANCELLED", observation_note="1", acceptability_threshold=90.0, modified=now, duration=0, configurations=[cfg2])
    task2 = ScheduleSchema(id=11, request=req2, site="site", enclosure="enc", priority=1, state="CANCELLED", proposal="1", submitter="sub", name="name", ipp_value=0.0, observation_type="type", request_group_id=1, created=now, modified=now, telescope="T200", start=now, end=now + datetime.timedelta(minutes=5))

    cfg3 = Configuration(
        id=3, instrument_type="T200_CAM", type="exposure", priority=1,
        instrument_configs=[InstrumentConfig(mode="img", exposure_time=500.0)],
        target=Target(type="SIDEREAL", name="Target3", ra=10.0, dec=20.0, epoch=2000.0),
        configuration_status=1003, state="PENDING", instrument_name="T200_CAM"
    )
    req3 = RequestSchema(id=103, state="PENDING", observation_note="1", acceptability_threshold=90.0, modified=now, duration=0, configurations=[cfg3])
    task3 = ScheduleSchema(id=12, request=req3, site="site", enclosure="enc", priority=1, state="PENDING", proposal="1", submitter="sub", name="name", ipp_value=0.0, observation_type="type", request_group_id=1, created=now, modified=now, telescope="T200", start=now, end=now + datetime.timedelta(seconds=10))

    return ScheduleAPIResponse(results=[task1, task2, task3])

@patch("core.schedule_coordinator.fetch_schedule")
def test_sync_filters_states(mock_fetch, dummy_schedule):
    mock_fetch.return_value = dummy_schedule
    pm = PluginManager()
    t200 = MockTelescopePlugin(telescope_id="T200")
    t200_cam = T200MockInstrumentPlugin(instrument_name="T200_CAM")
    
    pm.get_all_telescope_plugins = MagicMock(return_value={"T200": t200})
    pm.get_all_instrument_plugins = MagicMock(return_value={"T200_CAM": t200_cam})
    
    coordinator = ScheduleCoordinator(pm)
    coordinator.sync_all()
    
    assert len(t200.observations) == 2
    assert t200.observations[0].id == 10
    assert t200.observations[1].id == 12

@pytest.mark.asyncio
async def test_time_expiration_and_cache_peeking(dummy_schedule):
    pm = PluginManager()
    t200 = MockTelescopePlugin(telescope_id="T200")
    t200_cam = T200MockInstrumentPlugin(instrument_name="T200_CAM")
    
    pm.get_all_telescope_plugins = MagicMock(return_value={"T200": t200})
    pm.get_all_instrument_plugins = MagicMock(return_value={"T200_CAM": t200_cam})
    
    t200.observations = [dummy_schedule.results[2]]
    executor = TelescopeExecutor(t200, pm)
    
    obs = t200.get_next_observation()
    assert len(t200.observations) == 1
    
    executor.start()
    await asyncio.sleep(1)
    executor.stop()
    
    assert len(t200.observations) == 0
    status = state_manager.get_observation_status("config_status_1003")
    assert status.current_state.value == "REJECTED"

@pytest.mark.asyncio
async def test_executor_abort(dummy_schedule):
    pm = PluginManager()
    t200 = MockTelescopePlugin(telescope_id="T200")
    t200_cam = T200MockInstrumentPlugin(instrument_name="T200_CAM")
    
    pm.get_all_telescope_plugins = MagicMock(return_value={"T200": t200})
    pm.get_all_instrument_plugins = MagicMock(return_value={"T200_CAM": t200_cam})
    
    t200.observations = [dummy_schedule.results[0]]
    executor = TelescopeExecutor(t200, pm)
    
    executor.start()
    await asyncio.sleep(0.5)
    
    executor.abort("WEATHER_EMERGENCY")
    await asyncio.sleep(0.5)
    
    status = state_manager.get_observation_status("config_status_1001")
    assert status is not None
    assert status.current_state.value in ["ABORTED", "ERROR"]
    assert executor._running is False


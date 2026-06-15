from pydantic import BaseModel, Field, RootModel
from typing import List, Dict, Any, Optional
from datetime import datetime

# ==========================================
# 1. INSTRUMENT SCHEMAS
# ==========================================
# ==========================================
# 1. INSTRUMENT SCHEMAS
# ==========================================
class InstrumentConfig(BaseModel):
    optical_elements: Dict[str, Any] = {}
    mode: str
    exposure_time: Optional[float] = 0.0
    exposure_count: int = 1
    rotator_mode: Optional[str] = ""
    extra_params: Dict[str, Any] = {}
    rois: List[Any] = []  # Regions of Interest

class Target(BaseModel):
    configuration_id: Optional[int] = None
    type: str
    name: str
    ra: float
    dec: float
    proper_motion_ra: Optional[float] = 0.0
    proper_motion_dec: Optional[float] = 0.0
    parallax: Optional[float] = 0.0
    epoch: float
    hour_angle: Optional[float] = None
    extra_params: Dict[str, Any] = {}


class Configuration(BaseModel):
    id: int
    instrument_type: str
    type: str
    repeat_duration: Optional[float] = None
    extra_params: Dict[str, Any] = {}
    priority: int
    instrument_configs: List[InstrumentConfig]
    constraints: Dict[str, Any] = {}
    acquisition_config: Dict[str, Any] = {}
    guiding_config: Dict[str, Any] = {}
    target: Target
    configuration_status: int
    state: str
    instrument_name: str
    guide_camera_name: Optional[str] = ""
    summary: Dict[str, Any] = {}



# ==========================================
# 2. REQUEST SCHEMA
# ==========================================
class RequestSchema(BaseModel):
    id: int
    observation_note: str
    state: str
    acceptability_threshold: float
    extra_params: Dict[str, Any] = {}
    modified: datetime
    duration: int
    configurations: List[Configuration]

# ==========================================
# 3. SCHEDULE SCHEMA (The Top-Level Wrapper)
# ==========================================
class ScheduleSchema(BaseModel):
    id: int
    request: RequestSchema
    site: str
    enclosure: str
    telescope: str
    start: datetime
    end: datetime
    priority: int
    state: str
    proposal: str
    submitter: str
    name: str
    ipp_value: float
    observation_type: str
    request_group_id: int
    created: datetime
    modified: datetime

# ==========================================
# 4. THE API RESPONSE SCHEMA
# ==========================================
class ScheduleAPIResponse(BaseModel):
    results: List[ScheduleSchema]

# ==========================================
# 5. INSTRUMENT MAPPING SCHEMAS
# ==========================================
class InstrumentMapping(BaseModel):
    telescope_class: str = Field(..., alias="class")
    name: str

class InstrumentMappingResponse(RootModel):
    root: Dict[str, InstrumentMapping]

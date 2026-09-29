from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class RiverNodeBase(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    elevation: float
    slope: float
    bankfull_capacity: float

class RiverNodeOut(RiverNodeBase):
    class Config:
        from_attributes = True

class RainfallInput(BaseModel):
    source: str
    timestamp: datetime
    latitude: float
    longitude: float
    rainfall_mm: float
    quality: float

class FieldObservationCreate(BaseModel):
    latitude: float
    longitude: float
    water_level_m: Optional[float] = None
    rainfall_mm: Optional[float] = None
    notes: Optional[str] = None
    
class FieldObservationOut(FieldObservationCreate):
    id: int
    timestamp: datetime
    synced: bool
    class Config:
        from_attributes = True

class HazardStatusOut(BaseModel):
    node_id: str
    timestamp: datetime
    current_discharge: float
    predicted_discharge: float
    capacity_utilization: float
    trend: str
    status: str
    class Config:
        from_attributes = True

class AlertOut(BaseModel):
    id: str
    timestamp: datetime
    severity: str
    urgency: str
    certainty: str
    headline: str
    description: str
    affected_nodes: list
    class Config:
        from_attributes = True

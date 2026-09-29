# models for emergency stations and response units

from typing import Literal, Optional, List
from pydantic import BaseModel, Field
import uuid

class EmergencyStation(BaseModel):
    """Static registry of police, fire, and hospital facilities"""
    id: str = Field(default_factory=lambda: f"STN-{uuid.uuid4().hex[:6].upper()}")
    name: str
    type: Literal['POLICE', 'FIRE', 'HOSPITAL']
    coordinates: dict = Field(..., description='{"lat": float, "lng": float}')
    address: Optional[str] = None

class ResponseUnit(BaseModel):
    """Tactical response unit attached to a station"""
    id: str = Field(default_factory=lambda: f"UNIT-{uuid.uuid4().hex[:6].upper()}")
    callSign: str
    unitType: Literal['FIRE', 'POLICE', 'AMBULANCE', 'RESCUE_TASKFORCE']
    stationId: str
    stationName: str
    coordinates: dict = Field(..., description='{"lat": float, "lng": float}')
    status: Literal['AVAILABLE', 'DEPLOYED', 'MAINTENANCE'] = 'AVAILABLE'
    assignedIncidentId: Optional[str] = None
    personnelCount: int = 4
    equipment: List[str] = []

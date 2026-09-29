from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import uuid

DisasterType = Literal[
    "INDUSTRIAL",
    "FIRE",
    "FLOOD",
    "EARTHQUAKE",
    "CYCLONE",
    "STRUCTURAL_COLLAPSE",
    "OTHER"
]

SeverityLevel = Literal["CRITICAL", "HIGH", "MODERATE", "LOW"]

IncidentStatus = Literal[
    "PENDING",
    "TRIAGED",
    "DISPATCHED",
    "ACCEPTED",
    "EN_ROUTE",
    "ON_SCENE",
    "ASSISTANCE_REQUIRED",
    "SITUATION_UNDER_CONTROL",
    "RESOLVED"
]

class VictimProfile(BaseModel):
    id: str = Field(default_factory=lambda: f"VIC-{uuid.uuid4().hex[:6].upper()}")
    name: str = "Unknown Individual"
    category: Literal["RED", "YELLOW", "GREEN", "BLACK"] = "RED"
    notes: Optional[str] = ""
    rescued: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class VictimSubmitRequest(BaseModel):
    name: str = "Unknown Individual"
    category: Literal["RED", "YELLOW", "GREEN", "BLACK"] = "RED"
    notes: Optional[str] = ""
    rescued: bool = False

UnitType = Literal[
    "NDRF_RESCUE",
    "FIRE_ENGINE",
    "AMBULANCE_ALS",
    "POLICE_PATROL",
    "BOAT_RESCUE",
    "DRONE_RECON",
    "SDRF_QUICK_RESPONSE"
]

UnitStatus = Literal["AVAILABLE", "DISPATCHED", "ON_SCENE", "MAINTENANCE"]

class AffectedPeople(BaseModel):
    injured: int = Field(default=0, ge=0)
    trapped: int = Field(default=0, ge=0)
    evacuated: int = Field(default=0, ge=0)
    totalEstimated: int = Field(default=0, ge=0)

class CADIncidentData(BaseModel):
    title: str
    type: DisasterType
    severity: SeverityLevel
    urgencyScore: int = Field(..., ge=0, le=100)
    locationName: str
    affectedPeople: AffectedPeople
    casualtySummary: str
    actionableNotes: str

class TriageResult(BaseModel):
    is_relevant: bool
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    incident: Optional[CADIncidentData] = None
    rejection_reason: Optional[str] = None
    is_out_of_jurisdiction: bool = False
    jurisdiction_warning: Optional[str] = None

class IncidentRecord(BaseModel):
    id: str = Field(default_factory=lambda: f"INC-{uuid.uuid4().hex[:8].upper()}")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_text: str = ""
    channel: str = "WEB_CAD"
    metadata_info: Optional[str] = None
    is_relevant: bool = True
    confidence_score: float = 0.95
    rejection_reason: Optional[str] = None
    is_out_of_jurisdiction: bool = False
    jurisdiction_warning: Optional[str] = None
    source_url: Optional[str] = None
    author_handle: Optional[str] = None
    channel_icon: Optional[str] = None
    
    # Parsed CAD Fields matching exact schema
    title: str = "Unnamed Disaster Incident"
    type: DisasterType = "OTHER"
    severity: SeverityLevel = "MODERATE"
    currentStatus: str = "REPORTED"
    status: IncidentStatus = "PENDING"
    locationName: str = "Unknown Location"
    location_name: str = "Unknown Location"
    latitude: float = 13.0827
    longitude: float = 80.2707
    coordinates: dict = Field(default_factory=lambda: {"lat": 13.0827, "lng": 80.2707})
    urgencyScore: int = 50
    urgency_score: int = 50
    sosAlertsCount: int = 1
    sos_alerts_count: int = 1
    affectedPeople: AffectedPeople = Field(default_factory=AffectedPeople)
    affected_injured: int = 0
    affected_trapped: int = 0
    affected_evacuated: int = 0
    affected_total: int = 0
    casualty_summary: str = "None reported"
    actionable_notes: str = "Immediate reconnaissance recommended"
    accessRoutes: str = "Primary evacuation corridor cleared. Heavy vehicle access via Main Arterial Road."
    emergencyInstructions: str = "Establish cordon 150m. Deploy breathing apparatus and thermal imaging."
    victims: List[dict] = Field(default_factory=list)
    
    # CAD Operational State
    dispatched_units: List[str] = Field(default_factory=list)
    timeline: List[dict] = Field(default_factory=list)

    def model_post_init(self, __context):
        if not self.locationName or self.locationName == "Unknown Location":
            self.locationName = self.location_name
        if not self.location_name or self.location_name == "Unknown Location":
            self.location_name = self.locationName
            
        if self.urgencyScore != 50 and self.urgency_score == 50:
            self.urgency_score = self.urgencyScore
        elif self.urgency_score != 50 and self.urgencyScore == 50:
            self.urgencyScore = self.urgency_score

        if not self.coordinates or self.coordinates == {"lat": 13.0827, "lng": 80.2707}:
            self.coordinates = {"lat": self.latitude, "lng": self.longitude}
        else:
            self.latitude = self.coordinates.get("lat", self.latitude)
            self.longitude = self.coordinates.get("lng", self.longitude)
            
        if self.affectedPeople.totalEstimated == 0 and self.affected_total > 0:
            self.affectedPeople = AffectedPeople(
                injured=self.affected_injured,
                trapped=self.affected_trapped,
                evacuated=self.affected_evacuated,
                totalEstimated=self.affected_total
            )
        elif self.affectedPeople.totalEstimated > 0 and self.affected_total == 0:
            self.affected_injured = self.affectedPeople.injured
            self.affected_trapped = self.affectedPeople.trapped
            self.affected_evacuated = self.affectedPeople.evacuated
            self.affected_total = self.affectedPeople.totalEstimated

        if self.status != "PENDING" and self.currentStatus == "REPORTED":
            self.currentStatus = self.status
        elif self.currentStatus != "REPORTED" and self.status == "PENDING":
            self.status = "REPORTED" if self.currentStatus == "REPORTED" else self.currentStatus

class EmergencyUnit(BaseModel):
    id: str
    name: str
    type: UnitType
    status: UnitStatus = "AVAILABLE"
    station_name: str
    latitude: float
    longitude: float
    assigned_incident_id: Optional[str] = None
    contact_callsign: str
    personnel_count: int = 4

class IngestRequest(BaseModel):
    raw_message: str
    metadata_or_coordinates: Optional[str] = None
    channel: Optional[str] = "SOCIAL_FEED"

class DispatchRequest(BaseModel):
    unit_ids: List[str]
    notes: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: IncidentStatus
    notes: Optional[str] = None

class SystemStats(BaseModel):
    total_incidents: int
    active_critical: int
    active_high: int
    trapped_count: int
    injured_count: int
    available_units: int
    dispatched_units: int
    average_urgency: float
    triaged_today: int

class EmergencyStation(BaseModel):
    id: str
    name: str
    type: Literal["POLICE", "FIRE", "HOSPITAL", "DISASTER_MGMT", "OTHER"] = "POLICE"
    latitude: float
    longitude: float
    address: str = ""

class ResponseUnit(BaseModel):
    id: str
    call_sign: str
    unit_type: str
    station_id: Optional[str] = None
    latitude: float
    longitude: float
    status: Literal["AVAILABLE", "DISPATCHED", "ON_SCENE", "MAINTENANCE"] = "AVAILABLE"
    assigned_incident_id: Optional[str] = None
    personnel_count: int = 4
    equipment: Optional[str] = None

class NearestDispatchRequest(BaseModel):
    unit_type: Optional[str] = None
    notes: Optional[str] = None

class POIItem(BaseModel):
    place_id: Optional[str] = None
    name: str
    type: str
    latitude: float
    longitude: float
    vicinity: Optional[str] = None
    distance_km: Optional[float] = None

class ImageAnalysisResult(BaseModel):
    is_disaster_related: bool
    disaster_category: Literal['FLOOD', 'FIRE', 'STRUCTURAL_COLLAPSE', 'INDUSTRIAL', 'ROAD_ACCIDENT', 'NONE']
    damage_severity: Literal['CRITICAL', 'HIGH', 'MODERATE', 'LOW']
    visual_evidence: List[str] = Field(default_factory=list)
    estimated_casualty_risk: Literal['EXTREME', 'HIGH', 'MODERATE', 'LOW']
    confidence_score: float = 0.0
    suggested_urgency_adjustment: int = 0
    synopsis: Optional[str] = ""

class ImageIngestRequest(BaseModel):
    image_base64: Optional[str] = None
    image_url: Optional[str] = None
    caption: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    channel: Optional[str] = "IMAGE_INGEST"


class SocialStreamItem(BaseModel):
    id: str = Field(default_factory=lambda: f"POST-{uuid.uuid4().hex[:8]}")
    platform: Literal["TWITTER_X", "REDDIT", "TELEGRAM", "CITIZEN_PORTAL", "DISPATCH_112"] = "TWITTER_X"
    author: str = "@citizen_alert"
    author_avatar: Optional[str] = None
    text: str
    media_url: Optional[str] = None
    location_hint: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source_url: Optional[str] = None


class SocialStreamEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"EVT-{uuid.uuid4().hex[:8]}")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    item: SocialStreamItem
    action_taken: Literal["TICKET_GENERATED", "MERGED", "SPAM_DISCARDED", "OUT_OF_JURISDICTION"]
    incident_id: Optional[str] = None
    incident_title: Optional[str] = None
    distance_meters: Optional[float] = None
    triage_result: Optional[dict] = None
    summary: str = ""



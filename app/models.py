from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class EventMetadata(BaseModel):
    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: Optional[int] = None

class StoreEvent(BaseModel):
    event_id: str = Field(..., description="Globally unique UUID for the event")
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: datetime
    zone_id: Optional[str] = None
    dwell_ms: Optional[int] = None
    is_staff: bool = False
    confidence: float
    metadata: Optional[EventMetadata] = None

class PosTransaction(BaseModel):
    store_id: str
    transaction_id: str
    timestamp: datetime
    basket_value_inr: float

class MetricResponse(BaseModel):
    unique_visitors: int
    conversion_rate: float
    avg_dwell_per_zone: Dict[str, float]
    queue_depth: int
    abandonment_rate: float

class FunnelResponse(BaseModel):
    entry_count: int
    zone_visit_count: int
    billing_queue_count: int
    purchase_count: int
    drop_off_pct_entry_to_zone: float
    drop_off_pct_zone_to_billing: float
    drop_off_pct_billing_to_purchase: float

class HeatmapZone(BaseModel):
    zone_id: str
    visit_frequency_normalized: float
    avg_dwell_ms: float

class HeatmapResponse(BaseModel):
    zones: List[HeatmapZone]
    data_confidence: bool

class Anomaly(BaseModel):
    severity: str
    description: str
    suggested_action: str

class AnomaliesResponse(BaseModel):
    active_anomalies: List[Anomaly]

class HealthResponse(BaseModel):
    status: str
    last_event_timestamps: Dict[str, Optional[datetime]]
    warnings: List[str]

class StatsResponse(BaseModel):
    store_id: str
    total_events: int
    last_event_timestamp: Optional[datetime]

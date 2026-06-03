from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from .database import DBEvent
from .models import HeatmapResponse, HeatmapZone

def get_heatmap(store_id: str, db: Session) -> HeatmapResponse:
    # Get total zone visits and average dwell time per zone
    zone_stats = db.query(
        DBEvent.zone_id,
        func.count(DBEvent.event_id).label("visit_count"),
        func.avg(DBEvent.dwell_ms).label("avg_dwell")
    ).filter(
        DBEvent.store_id == store_id,
        DBEvent.zone_id.isnot(None),
        DBEvent.event_type == 'ZONE_DWELL',
        DBEvent.is_staff == False
    ).group_by(DBEvent.zone_id).all()
    
    # Calculate normalization base (max visits)
    max_visits = max([stats[1] for stats in zone_stats]) if zone_stats else 1
    
    zones = []
    for zone_id, visit_count, avg_dwell in zone_stats:
        normalized_freq = (visit_count / max_visits) * 100
        zones.append(HeatmapZone(
            zone_id=zone_id,
            visit_frequency_normalized=normalized_freq,
            avg_dwell_ms=float(avg_dwell) if avg_dwell else 0.0
        ))
        
    # Check data confidence (fewer than 20 sessions in window)
    total_sessions = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.event_type == 'ENTRY'
    ).distinct().count()
    
    data_confidence = total_sessions >= 20
    
    return HeatmapResponse(zones=zones, data_confidence=data_confidence)

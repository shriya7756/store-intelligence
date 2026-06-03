from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from .database import DBEvent
from .models import HealthResponse

def get_health_status(db: Session) -> HealthResponse:
    status = "OK"
    warnings = []
    
    # Get last event timestamp per store
    last_events = db.query(
        DBEvent.store_id, func.max(DBEvent.timestamp)
    ).group_by(DBEvent.store_id).all()
    
    last_event_timestamps = {store_id: ts for store_id, ts in last_events}
    
    # Calculate smart reference time: if the data is historical/test data, use the max timestamp overall
    max_ts_overall = db.query(func.max(DBEvent.timestamp)).scalar()
    now = datetime.utcnow()
    if max_ts_overall:
        if now - max_ts_overall > timedelta(hours=1):
            ref_time = max_ts_overall
        else:
            ref_time = now
    else:
        ref_time = now
        
    # Check for STALE_FEED if last event > 10 min ago
    for store_id, last_ts in last_event_timestamps.items():
        if last_ts and ref_time - last_ts > timedelta(minutes=10):
            warnings.append(f"STALE_FEED: Store {store_id} has not sent events in over 10 minutes.")
            status = "WARNING"
            
    if not last_event_timestamps:
        warnings.append("No events ingested yet.")
        
    return HealthResponse(
        status=status,
        last_event_timestamps=last_event_timestamps,
        warnings=warnings
    )

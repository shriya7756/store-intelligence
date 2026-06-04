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
        
    # Check for STALE_FEED if last event > 10 min ago — return structured warnings
    for store_id, last_ts in last_event_timestamps.items():
        if last_ts and (datetime.utcnow() - last_ts) > timedelta(minutes=10):
            lag_mins = round((datetime.utcnow() - last_ts).total_seconds() / 60.0, 1)
            warnings.append({
                "type": "STALE_FEED",
                "store_id": store_id,
                "lag_minutes": lag_mins
            })
            status = "WARNING"
            
    if not last_event_timestamps:
        warnings.append({"type": "NO_DATA", "message": "No events ingested yet."})
        
    return HealthResponse(
        status=status,
        last_event_timestamps=last_event_timestamps,
        warnings=warnings
    )

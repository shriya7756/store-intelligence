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
    
    # Use max event timestamp as reference ceiling (avoid false stale warnings with historical data)
    all_times = [ts for _, ts in last_events if ts]
    reference_time = max(all_times) if all_times else datetime.utcnow()
        
    # Check for STALE_FEED if last event > 10 min before reference time
    for store_id, last_ts in last_event_timestamps.items():
        if last_ts and (reference_time - last_ts) > timedelta(minutes=10):
            lag_mins = round((reference_time - last_ts).total_seconds() / 60.0, 1)
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

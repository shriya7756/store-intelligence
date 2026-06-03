from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from .database import DBEvent, DBPosTransaction
from .models import AnomaliesResponse, Anomaly

def get_conversion_rate_for_range(store_id: str, start_dt: datetime, end_dt: datetime, db: Session) -> float:
    unique_visitors_q = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.is_staff == False,
        DBEvent.event_type.in_(['ENTRY', 'REENTRY']),
        DBEvent.timestamp >= start_dt,
        DBEvent.timestamp < end_dt
    ).distinct().count()
    
    joins = db.query(DBEvent).filter(
        DBEvent.store_id == store_id,
        DBEvent.is_staff == False,
        DBEvent.event_type == 'BILLING_QUEUE_JOIN',
        DBEvent.timestamp >= start_dt,
        DBEvent.timestamp < end_dt
    ).all()
    
    transactions = db.query(DBPosTransaction).filter(
        DBPosTransaction.store_id == store_id,
        DBPosTransaction.timestamp >= start_dt,
        DBPosTransaction.timestamp < end_dt
    ).all()
    
    converted_visitors = set()
    for join in joins:
        for tx in transactions:
            time_diff = (tx.timestamp - join.timestamp).total_seconds()
            if 0 <= time_diff <= 300:
                converted_visitors.add(join.visitor_id)
                break
                
    return (len(converted_visitors) / unique_visitors_q) if unique_visitors_q > 0 else 0.0

def check_anomalies(store_id: str, db: Session) -> AnomaliesResponse:
    anomalies = []
    
    # Get reference time based on the latest event timestamp for this store
    latest_event = db.query(DBEvent.timestamp).filter(
        DBEvent.store_id == store_id
    ).order_by(DBEvent.timestamp.desc()).first()
    
    if latest_event:
        now = latest_event[0]
    else:
        now = datetime.utcnow()
        
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # 1. Billing Queue Spike
    latest_queue = db.query(DBEvent).filter(
        DBEvent.store_id == store_id,
        DBEvent.event_type == 'BILLING_QUEUE_JOIN',
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).order_by(DBEvent.timestamp.desc()).first()
    
    if latest_queue and latest_queue.metadata_json:
        queue_depth = latest_queue.metadata_json.get('queue_depth', 0)
        # Spike if queue depth is > 5
        if queue_depth > 5:
            anomalies.append(Anomaly(
                severity="WARN",
                description=f"High billing queue depth: {queue_depth}",
                suggested_action="Open an additional billing counter."
            ))

    # 2. Dead Zone (No visits in last 30 min relative to now)
    thirty_mins_ago = now - timedelta(minutes=30)
    
    # Get all zones for store
    zones = db.query(DBEvent.zone_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.zone_id.isnot(None)
    ).distinct().all()
    
    for (zone_id,) in zones:
        recent_visit = db.query(DBEvent).filter(
            DBEvent.store_id == store_id,
            DBEvent.zone_id == zone_id,
            DBEvent.timestamp >= thirty_mins_ago,
            DBEvent.timestamp <= now,
            DBEvent.event_type.in_(['ZONE_ENTER', 'ZONE_DWELL'])
        ).first()
        
        if not recent_visit:
            anomalies.append(Anomaly(
                severity="INFO",
                description=f"Dead zone detected: {zone_id} has had no visits in the last 30 minutes.",
                suggested_action="Verify camera feed for this zone or check physical access."
            ))
            
    # 3. Conversion Drop vs 7-day average
    # Calculate unique visitors today
    unique_visitors_today = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.is_staff == False,
        DBEvent.event_type.in_(['ENTRY', 'REENTRY']),
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).distinct().count()

    # Calculate 7-day average conversion rate (days 1 to 7 before today)
    avg_conversions = []
    for i in range(1, 8):
        d_start = today_start - timedelta(days=i)
        d_end = d_start + timedelta(days=1)
        rate = get_conversion_rate_for_range(store_id, d_start, d_end, db)
        avg_conversions.append(rate)
        
    seven_day_avg = sum(avg_conversions) / 7.0
    today_rate = get_conversion_rate_for_range(store_id, today_start, today_end, db)
    
    # Flag critical drop if today's conversion is < 50% of the 7-day average
    if unique_visitors_today >= 5 and seven_day_avg > 0.0 and today_rate < 0.5 * seven_day_avg:
        anomalies.append(Anomaly(
            severity="CRITICAL",
            description=f"Conversion drop: Today's conversion rate ({today_rate*100:.1f}%) is less than half of the 7-day average ({seven_day_avg*100:.1f}%).",
            suggested_action="Check POS system connectivity and verify staff presence at billing."
        ))

    return AnomaliesResponse(active_anomalies=anomalies)

import os
import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import logging

from .database import DBEvent, DBPosTransaction
from .models import MetricResponse

logger = logging.getLogger("store_intelligence_api.metrics")

def load_store_layout():
    paths = ["store_layout.json", "../store_layout.json", "store-intelligence/store_layout.json"]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return []

def get_metrics(store_id: str, db: Session) -> MetricResponse:
    # Get reference time based on the latest event timestamp for this store
    latest_event = db.query(DBEvent.timestamp).filter(
        DBEvent.store_id == store_id
    ).order_by(DBEvent.timestamp.desc()).first()
    
    if latest_event:
        ref_time = latest_event[0]
    else:
        ref_time = datetime.utcnow()
        
    today_start = ref_time.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    # 1. Unique Visitors (excluding staff) today
    unique_visitors_query = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.is_staff == False,
        DBEvent.event_type.in_(['ENTRY', 'REENTRY']),
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).distinct().all()
    
    unique_visitors = [v[0] for v in unique_visitors_query]
    unique_visitors_count = len(unique_visitors)
    
    # 2. Conversion Rate (visitors who purchased / unique visitors)
    # A visitor who was in the billing zone in the 5-minute window before a transaction timestamp
    # counts as a converted visitor for that session.
    joins = db.query(DBEvent).filter(
        DBEvent.store_id == store_id,
        DBEvent.is_staff == False,
        DBEvent.event_type == 'BILLING_QUEUE_JOIN',
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).all()
    
    transactions = db.query(DBPosTransaction).filter(
        DBPosTransaction.store_id == store_id,
        DBPosTransaction.timestamp >= today_start,
        DBPosTransaction.timestamp < today_end
    ).all()
    
    converted_visitors = set()
    for join in joins:
        for tx in transactions:
            # tx timestamp must be within 5 minutes after join timestamp
            time_diff = (tx.timestamp - join.timestamp).total_seconds()
            if 0 <= time_diff <= 300:
                converted_visitors.add(join.visitor_id)
                break
                
    conversion_rate = (len(converted_visitors) / unique_visitors_count) if unique_visitors_count > 0 else 0.0
    
    # 3. Avg Dwell Per Zone today
    zone_dwells = db.query(
        DBEvent.zone_id, func.avg(DBEvent.dwell_ms)
    ).filter(
        DBEvent.store_id == store_id,
        DBEvent.is_staff == False,
        DBEvent.event_type == 'ZONE_DWELL',
        DBEvent.zone_id.isnot(None),
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).group_by(DBEvent.zone_id).all()
    
    avg_dwell_per_zone = {zone: float(dwell) for zone, dwell in zone_dwells if zone is not None}
    
    # 4. Queue Depth (currently in queue)
    # Find billing zones for this store from store layout
    layouts = load_store_layout()
    billing_zones = []
    for s in layouts:
        if s["store_id"] == store_id:
            for z in s["zones"]:
                if z["type"] == "BILLING":
                    billing_zones.append(z["zone_id"])
                    
    # Visitors who joined the queue today
    joined_q = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.is_staff == False,
        DBEvent.event_type == 'BILLING_QUEUE_JOIN',
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).distinct().all()
    joined_set = {v[0] for v in joined_q}
    
    # Visitors who left the billing zone today
    left_q = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.is_staff == False,
        DBEvent.event_type.in_(['ZONE_EXIT', 'BILLING_QUEUE_ABANDON']),
        DBEvent.zone_id.in_(billing_zones),
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).distinct().all()
    left_set = {v[0] for v in left_q}
    
    queue_depth = len(joined_set - left_set)
        
    # 5. Abandonment Rate (Abandoned queues / Total joined queues) today
    joins_count = len(joins)
    abandons_count = db.query(DBEvent).filter(
        DBEvent.store_id == store_id,
        DBEvent.event_type == 'BILLING_QUEUE_ABANDON',
        DBEvent.is_staff == False,
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).count()
    
    abandonment_rate = (abandons_count / joins_count) if joins_count > 0 else 0.0
 
    return MetricResponse(
        unique_visitors=unique_visitors_count,
        conversion_rate=conversion_rate,
        avg_dwell_per_zone=avg_dwell_per_zone,
        queue_depth=queue_depth,
        abandonment_rate=abandonment_rate
    )

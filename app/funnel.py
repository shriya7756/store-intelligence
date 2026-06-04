from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from .database import DBEvent, DBPosTransaction
from .models import FunnelResponse

def get_funnel(store_id: str, db: Session) -> FunnelResponse:
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

    # 1. Entry Count (Unique visitor sessions starting today)
    entry_sessions = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.event_type.in_(['ENTRY', 'REENTRY']),
        DBEvent.is_staff == False,
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).distinct().all()
    entry_visitor_ids = {s[0] for s in entry_sessions}
    entry_count = len(entry_visitor_ids)
    
    # 2. Zone Visit Count (Visitors who entered at least one zone today)
    zone_sessions = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.visitor_id.in_(entry_visitor_ids) if entry_visitor_ids else False,
        DBEvent.event_type == 'ZONE_ENTER',
        DBEvent.is_staff == False,
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).distinct().all()
    zone_visitor_ids = {s[0] for s in zone_sessions}
    zone_visit_count = len(zone_visitor_ids)
    
    # 3. Billing Queue Count (Visitors who joined the billing queue today)
    billing_sessions = db.query(DBEvent.visitor_id).filter(
        DBEvent.store_id == store_id,
        DBEvent.visitor_id.in_(zone_visitor_ids) if zone_visitor_ids else False,
        DBEvent.event_type == 'BILLING_QUEUE_JOIN',
        DBEvent.is_staff == False,
        DBEvent.timestamp >= today_start,
        DBEvent.timestamp < today_end
    ).distinct().all()
    billing_visitor_ids = {s[0] for s in billing_sessions}
    billing_queue_count = len(billing_visitor_ids)
    
    # 4. Purchase Count (Visitors who joined billing queue AND there was a transaction shortly after)
    # A visitor who was in the billing zone in the 5-minute window before a transaction timestamp
    # counts as a converted visitor for that session.
    transactions = db.query(DBPosTransaction).filter(
        DBPosTransaction.store_id == store_id,
        DBPosTransaction.timestamp >= today_start,
        DBPosTransaction.timestamp < today_end
    ).all()

    converted_visitors = set()
    for tx in transactions:
        window_start = tx.timestamp - timedelta(minutes=5)
        joins_in_window = db.query(DBEvent.visitor_id).filter(
            DBEvent.store_id == store_id,
            DBEvent.is_staff == False,
            DBEvent.event_type == 'BILLING_QUEUE_JOIN',
            DBEvent.timestamp >= window_start,
            DBEvent.timestamp <= tx.timestamp,
            DBEvent.visitor_id.in_(billing_visitor_ids) if billing_visitor_ids else True
        ).distinct().all()
        for j in joins_in_window:
            converted_visitors.add(j[0])

    purchase_count = len(converted_visitors)
    
    # Calculate Drop-off Percentages
    drop_off_pct_entry_to_zone = 0.0
    if entry_count > 0:
        drop_off_pct_entry_to_zone = ((entry_count - zone_visit_count) / entry_count) * 100
        
    drop_off_pct_zone_to_billing = 0.0
    if zone_visit_count > 0:
        drop_off_pct_zone_to_billing = ((zone_visit_count - billing_queue_count) / zone_visit_count) * 100
        
    drop_off_pct_billing_to_purchase = 0.0
    if billing_queue_count > 0:
        drop_off_pct_billing_to_purchase = ((billing_queue_count - purchase_count) / billing_queue_count) * 100

    return FunnelResponse(
        entry_count=entry_count,
        zone_visit_count=zone_visit_count,
        billing_queue_count=billing_queue_count,
        purchase_count=purchase_count,
        drop_off_pct_entry_to_zone=drop_off_pct_entry_to_zone,
        drop_off_pct_zone_to_billing=drop_off_pct_zone_to_billing,
        drop_off_pct_billing_to_purchase=drop_off_pct_billing_to_purchase
    )

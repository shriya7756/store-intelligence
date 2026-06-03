import csv
import os
from datetime import datetime, timedelta
from database import engine, DBPosTransaction, DBEvent, SessionLocal, init_db

def load_pos_data():
    csv_path = "pos_transactions.csv"
    if not os.path.exists(csv_path):
        print(f"CSV {csv_path} not found.")
        return

    db = SessionLocal()
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            try:
                dt_str = f"{row['order_date']} {row['order_time']}"
                dt = datetime.strptime(dt_str, "%d-%m-%Y %H:%M:%S")
                
                txn = DBPosTransaction(
                    transaction_id=str(row['order_id']),
                    store_id=row['store_id'],
                    timestamp=dt,
                    basket_value_inr=float(row['total_amount'])
                )
                db.merge(txn)
                count += 1
            except Exception as e:
                print(f"Error loading row: {e}")
                
        db.commit()
        print(f"Loaded {count} POS transactions.")
    db.close()

def load_events_data():
    db = SessionLocal()
    # Check if events already exist to avoid duplicate seeding
    if db.query(DBEvent).first():
        db.close()
        return

    events = []
    
    # Store configuration mappings
    for store_id, floor_zone, billing_zone, entry_cam, floor_cam, billing_cam, sku in [
        ("ST1008", "MAKEUP", "BILLING_01", "CAM1", "CAM2", "CAM3", "LIPSTICK"),
        ("STORE_BLR_002", "SKINCARE", "BILLING_01", "CAM_ENTRY_01", "CAM_FLOOR_01", "CAM_BILLING_01", "MOISTURISER")
    ]:
        # Visitor 1 (Normal customer, completed purchase)
        t1 = datetime(2026, 4, 10, 12, 0, 0)
        events.extend([
            DBEvent(event_id=f"{store_id}-ev1", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_001", event_type="ENTRY", timestamp=t1, confidence=0.98, metadata_json={"session_seq": 1}),
            DBEvent(event_id=f"{store_id}-ev2", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_001", event_type="ZONE_ENTER", timestamp=t1 + timedelta(minutes=1), zone_id=floor_zone, confidence=0.95, metadata_json={"sku_zone": sku, "session_seq": 2}),
            DBEvent(event_id=f"{store_id}-ev3", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_001", event_type="ZONE_DWELL", timestamp=t1 + timedelta(minutes=1, seconds=40), zone_id=floor_zone, dwell_ms=40000, confidence=0.92, metadata_json={"sku_zone": sku, "session_seq": 3}),
            DBEvent(event_id=f"{store_id}-ev4", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_001", event_type="ZONE_EXIT", timestamp=t1 + timedelta(minutes=10), zone_id=floor_zone, confidence=0.94, metadata_json={"sku_zone": sku, "session_seq": 4}),
            DBEvent(event_id=f"{store_id}-ev5", store_id=store_id, camera_id=billing_cam, visitor_id="VIS_001", event_type="BILLING_QUEUE_JOIN", timestamp=t1 + timedelta(minutes=12), zone_id=billing_zone, confidence=0.93, metadata_json={"queue_depth": 1, "session_seq": 5}),
            DBEvent(event_id=f"{store_id}-ev6", store_id=store_id, camera_id=billing_cam, visitor_id="VIS_001", event_type="ZONE_DWELL", timestamp=t1 + timedelta(minutes=14), zone_id=billing_zone, dwell_ms=120000, confidence=0.90, metadata_json={"session_seq": 6}),
            DBEvent(event_id=f"{store_id}-ev7", store_id=store_id, camera_id=billing_cam, visitor_id="VIS_001", event_type="ZONE_EXIT", timestamp=t1 + timedelta(minutes=15), zone_id=billing_zone, confidence=0.91, metadata_json={"session_seq": 7}),
            DBEvent(event_id=f"{store_id}-ev8", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_001", event_type="EXIT", timestamp=t1 + timedelta(minutes=16), confidence=0.96, metadata_json={"session_seq": 8})
        ])
        
        # Visitor 2 (Abandoned queue customer)
        t2 = datetime(2026, 4, 10, 12, 50, 0)
        events.extend([
            DBEvent(event_id=f"{store_id}-ev9", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_002", event_type="ENTRY", timestamp=t2, confidence=0.97, metadata_json={"session_seq": 1}),
            DBEvent(event_id=f"{store_id}-ev10", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_002", event_type="ZONE_ENTER", timestamp=t2 + timedelta(minutes=2), zone_id=floor_zone, confidence=0.94, metadata_json={"sku_zone": sku, "session_seq": 2}),
            DBEvent(event_id=f"{store_id}-ev11", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_002", event_type="ZONE_EXIT", timestamp=t2 + timedelta(minutes=8), zone_id=floor_zone, confidence=0.91, metadata_json={"sku_zone": sku, "session_seq": 3}),
            DBEvent(event_id=f"{store_id}-ev12", store_id=store_id, camera_id=billing_cam, visitor_id="VIS_002", event_type="BILLING_QUEUE_JOIN", timestamp=t2 + timedelta(minutes=10), zone_id=billing_zone, confidence=0.92, metadata_json={"queue_depth": 2, "session_seq": 4}),
            DBEvent(event_id=f"{store_id}-ev13", store_id=store_id, camera_id=billing_cam, visitor_id="VIS_002", event_type="BILLING_QUEUE_ABANDON", timestamp=t2 + timedelta(minutes=20), zone_id=billing_zone, confidence=0.88, metadata_json={"session_seq": 5}),
            DBEvent(event_id=f"{store_id}-ev14", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_002", event_type="EXIT", timestamp=t2 + timedelta(minutes=25), confidence=0.95, metadata_json={"session_seq": 6})
        ])
        
        # Visitor 3 (Staff)
        t3 = datetime(2026, 4, 10, 9, 0, 0)
        events.extend([
            DBEvent(event_id=f"{store_id}-ev15", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_STAFF", event_type="ENTRY", timestamp=t3, is_staff=True, confidence=0.99, metadata_json={"session_seq": 1}),
            DBEvent(event_id=f"{store_id}-ev16", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_STAFF", event_type="ZONE_ENTER", timestamp=t3 + timedelta(minutes=30), zone_id=floor_zone, is_staff=True, confidence=0.98, metadata_json={"sku_zone": sku, "session_seq": 2}),
            DBEvent(event_id=f"{store_id}-ev17", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_STAFF", event_type="ZONE_DWELL", timestamp=t3 + timedelta(minutes=31), zone_id=floor_zone, dwell_ms=60000, is_staff=True, confidence=0.95, metadata_json={"sku_zone": sku, "session_seq": 3}),
            DBEvent(event_id=f"{store_id}-ev18", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_STAFF", event_type="EXIT", timestamp=t3 + timedelta(hours=8), is_staff=True, confidence=0.99, metadata_json={"session_seq": 4})
        ])
        
        # Visitor 4 (Reentry visitor)
        t4 = datetime(2026, 4, 10, 13, 30, 0)
        events.extend([
            DBEvent(event_id=f"{store_id}-ev19", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_004", event_type="ENTRY", timestamp=t4, confidence=0.96, metadata_json={"session_seq": 1}),
            DBEvent(event_id=f"{store_id}-ev20", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_004", event_type="EXIT", timestamp=t4 + timedelta(minutes=5), confidence=0.95, metadata_json={"session_seq": 2}),
            DBEvent(event_id=f"{store_id}-ev21", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_004", event_type="REENTRY", timestamp=t4 + timedelta(minutes=15), confidence=0.96, metadata_json={"session_seq": 3}),
            DBEvent(event_id=f"{store_id}-ev22", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_004", event_type="ZONE_ENTER", timestamp=t4 + timedelta(minutes=17), zone_id=floor_zone, confidence=0.92, metadata_json={"sku_zone": sku, "session_seq": 4}),
            DBEvent(event_id=f"{store_id}-ev23", store_id=store_id, camera_id=floor_cam, visitor_id="VIS_004", event_type="ZONE_DWELL", timestamp=t4 + timedelta(minutes=20), zone_id=floor_zone, dwell_ms=180000, confidence=0.90, metadata_json={"sku_zone": sku, "session_seq": 5}),
            DBEvent(event_id=f"{store_id}-ev24", store_id=store_id, camera_id=entry_cam, visitor_id="VIS_004", event_type="EXIT", timestamp=t4 + timedelta(minutes=30), confidence=0.94, metadata_json={"session_seq": 6})
        ])

    for e in events:
        db.merge(e)
    db.commit()
    print(f"Loaded {len(events)} mock events.")
    db.close()

if __name__ == "__main__":
    init_db()
    load_pos_data()
    load_events_data()

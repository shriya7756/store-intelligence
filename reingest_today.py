#!/usr/bin/env python3
"""Re-ingest synthetic events with today's timestamp to clear STALE_FEED warnings."""

import requests
from datetime import datetime
from uuid import uuid4

BASE_URL = "http://127.0.0.1:8000"
STORE_ID = "ST1008"

# Get today's date at different times
today = datetime(2026, 6, 5)
times = [
    today.replace(hour=10, minute=0),
    today.replace(hour=10, minute=15),
    today.replace(hour=10, minute=30),
    today.replace(hour=10, minute=45),
    today.replace(hour=11, minute=0),
    today.replace(hour=11, minute=15),
]

events = []
for i, ts in enumerate(times):
    # Alternate between ENTRY, ZONE_DWELL, BILLING_QUEUE_JOIN, PURCHASE
    event_types = ["ENTRY", "ZONE_DWELL", "BILLING_QUEUE_JOIN"]
    event_type = event_types[i % len(event_types)]
    
    zone_id = None
    if event_type in ["ZONE_DWELL"]:
        zone_id = "MAKEUP" if i % 2 == 0 else "BILLING_01"
    elif event_type == "BILLING_QUEUE_JOIN":
        zone_id = "BILLING_01"
    
    event = {
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM1",
        "visitor_id": f"VIS_{i}",
        "event_type": event_type,
        "timestamp": ts.isoformat() + "Z",
        "zone_id": zone_id,
        "dwell_ms": 1200 if event_type == "ZONE_DWELL" else None,
        "is_staff": False,
        "confidence": 0.95
    }
    events.append(event)

# Post to ingest endpoint
try:
    resp = requests.post(f"{BASE_URL}/events/ingest", json=events, timeout=10)
    print(f"✅ Ingested {len(events)} events")
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.text[:200]}")
except Exception as e:
    print(f"❌ Error: {e}")

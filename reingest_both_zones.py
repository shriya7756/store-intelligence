#!/usr/bin/env python3
"""Re-ingest more comprehensive synthetic events with today's timestamp."""

import requests
import json
from datetime import datetime, timedelta
from uuid import uuid4

BASE_URL = "http://127.0.0.1:8000"
STORE_ID = "ST1008"

# Get today's date at different times
today = datetime(2026, 6, 5)
times = [
    today.replace(hour=10, minute=0),
    today.replace(hour=10, minute=5),
    today.replace(hour=10, minute=10),
    today.replace(hour=10, minute=15),
    today.replace(hour=10, minute=20),
    today.replace(hour=10, minute=25),
    today.replace(hour=10, minute=30),
    today.replace(hour=10, minute=35),
]

zones = ["MAKEUP", "BILLING_01", "MAKEUP", "BILLING_01"]
events = []

for i, ts in enumerate(times):
    zone = zones[i % len(zones)]
    
    event = {
        "event_id": str(uuid4()),
        "store_id": STORE_ID,
        "camera_id": "CAM1",
        "visitor_id": f"VIS_TODAY_{i}",
        "event_type": "ZONE_DWELL",
        "timestamp": ts.isoformat() + "Z",
        "zone_id": zone,
        "dwell_ms": 1200,
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

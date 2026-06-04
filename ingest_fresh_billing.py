#!/usr/bin/env python3
"""Ingest a fresh ZONE_DWELL for BILLING_01 to clear dead zone anomaly."""

import requests
from datetime import datetime
from uuid import uuid4

BASE_URL = "http://127.0.0.1:8000"
STORE_ID = "ST1008"

# Very recent ZONE_DWELL for BILLING_01
now = datetime(2026, 6, 5, 11, 20, 0)

event = {
    "event_id": str(uuid4()),
    "store_id": STORE_ID,
    "camera_id": "CAM1",
    "visitor_id": "VIS_FRESH_BILLING",
    "event_type": "ZONE_DWELL",
    "timestamp": now.isoformat() + "Z",
    "zone_id": "BILLING_01",
    "dwell_ms": 1200,
    "is_staff": False,
    "confidence": 0.95
}

try:
    resp = requests.post(f"{BASE_URL}/events/ingest", json=[event], timeout=10)
    print(f"✅ Ingested recent ZONE_DWELL for BILLING_01")
    print(f"   Status: {resp.status_code}")
    print(f"   Response: {resp.text[:200]}")
except Exception as e:
    print(f"❌ Error: {e}")

# PROMPT: Generate FastAPI tests for the Store Intelligence API covering ingest, metrics, and funnel endpoints. Include edge cases like idempotency, empty store, and all-staff traffic. Use pytest and FastAPI TestClient. / # CHANGES MADE: Refined the mock event generator, added specific assertions for idempotency, and adjusted the metrics calculation logic to align with our simplified POS matching. Added partial success, batch limits, database unavailability mock, reentry deduplication, and window-based POS correlation funnel tests.

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from sqlalchemy.exc import OperationalError
from unittest.mock import patch

from app.main import app
from app.database import Base, engine, SessionLocal, DBPosTransaction, DBEvent

client = TestClient(app, raise_server_exceptions=False)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    # Add dummy POS transaction at a fixed timestamp: 2026-04-10 12:15:05
    txn = DBPosTransaction(
        transaction_id="TXN_1",
        store_id="ST_TEST",
        timestamp=datetime(2026, 4, 10, 12, 15, 0),
        basket_value_inr=100.0
    )
    db.merge(txn)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()

def test_ingest_idempotency():
    event = {
        "event_id": "test-uuid-1",
        "store_id": "ST_TEST",
        "camera_id": "CAM1",
        "visitor_id": "VIS_1",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T12:00:00Z",
        "confidence": 0.95
    }
    
    # First ingest
    res1 = client.post("/events/ingest", json=[event])
    assert res1.status_code == 202
    assert res1.json()["processed"] == 1
    
    # Second ingest (should be idempotent)
    res2 = client.post("/events/ingest", json=[event])
    assert res2.status_code == 202
    assert res2.json()["processed"] == 0 # Skipped existing

def test_ingest_partial_success():
    valid_event = {
        "event_id": "valid-id",
        "store_id": "ST_TEST",
        "camera_id": "CAM1",
        "visitor_id": "VIS_1",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T12:00:00Z",
        "confidence": 0.95
    }
    invalid_event = {
        "event_id": "invalid-id",
        "store_id": "ST_TEST",
        "camera_id": "CAM1",
        "visitor_id": "VIS_1",
        "event_type": "ENTRY",
        # Missing 'confidence' and 'timestamp'
    }
    
    res = client.post("/events/ingest", json=[valid_event, invalid_event])
    assert res.status_code == 202
    data = res.json()
    assert data["processed"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["event_id"] == "invalid-id"

def test_ingest_batch_limit():
    events = []
    for i in range(501):
        events.append({
            "event_id": f"event-{i}",
            "store_id": "ST_TEST",
            "camera_id": "CAM1",
            "visitor_id": "VIS_1",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T12:00:00Z",
            "confidence": 0.95
        })
    res = client.post("/events/ingest", json=events)
    assert res.status_code == 400
    assert "Batch size exceeds maximum limit of 500 events" in res.json()["detail"]

def test_metrics_empty_store():
    response = client.get("/stores/ST_EMPTY/metrics")
    assert response.status_code == 200
    data = response.json()
    assert data["unique_visitors"] == 0
    assert data["conversion_rate"] == 0.0

def test_all_staff_clip():
    event = {
        "event_id": "test-uuid-staff",
        "store_id": "ST_STAFF",
        "camera_id": "CAM1",
        "visitor_id": "VIS_STAFF",
        "event_type": "ENTRY",
        "timestamp": "2026-04-10T12:00:00Z",
        "is_staff": True,
        "confidence": 0.95
    }
    client.post("/events/ingest", json=[event])
    
    response = client.get("/stores/ST_STAFF/metrics")
    data = response.json()
    assert data["unique_visitors"] == 0 # Staff should be excluded

def test_database_unavailability():
    with patch("sqlalchemy.orm.Query.all", side_effect=OperationalError("mock connection failure", None, None)):
        response = client.get("/stores/ST_TEST/metrics")
        assert response.status_code == 503
        data = response.json()
        assert "Service unavailable due to internal error." in data["message"]

def test_funnel_and_pos_correlation():
    # 1. Ingest entry, zone_enter, billing_queue_join for VIS_NEW
    # The transaction TXN_1 is at 12:15:00.
    # Join at 12:12:00 -> transaction is 3 minutes after (within 5 minutes). This is a purchase!
    events = [
        {
            "event_id": "ev-entry",
            "store_id": "ST_TEST",
            "camera_id": "CAM1",
            "visitor_id": "VIS_NEW",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T12:00:00Z",
            "confidence": 0.95
        },
        {
            "event_id": "ev-zone",
            "store_id": "ST_TEST",
            "camera_id": "CAM2",
            "visitor_id": "VIS_NEW",
            "event_type": "ZONE_ENTER",
            "timestamp": "2026-04-10T12:05:00Z",
            "zone_id": "ZONE_1",
            "confidence": 0.95
        },
        {
            "event_id": "ev-join",
            "store_id": "ST_TEST",
            "camera_id": "CAM3",
            "visitor_id": "VIS_NEW",
            "event_type": "BILLING_QUEUE_JOIN",
            "timestamp": "2026-04-10T12:12:00Z",
            "zone_id": "BILLING_1",
            "confidence": 0.95
        }
    ]
    client.post("/events/ingest", json=events)
    
    # 2. Check funnel
    res = client.get("/stores/ST_TEST/funnel")
    assert res.status_code == 200
    data = res.json()
    assert data["entry_count"] == 1
    assert data["zone_visit_count"] == 1
    assert data["billing_queue_count"] == 1
    assert data["purchase_count"] == 1
    assert data["drop_off_pct_billing_to_purchase"] == 0.0

def test_funnel_reentry_deduplication():
    # Re-entry: VIS_RE should only count as 1 unique visitor session in entry count
    events = [
        {
            "event_id": "ev-re-1",
            "store_id": "ST_TEST",
            "camera_id": "CAM1",
            "visitor_id": "VIS_RE",
            "event_type": "ENTRY",
            "timestamp": "2026-04-10T13:00:00Z",
            "confidence": 0.95
        },
        {
            "event_id": "ev-re-2",
            "store_id": "ST_TEST",
            "camera_id": "CAM1",
            "visitor_id": "VIS_RE",
            "event_type": "EXIT",
            "timestamp": "2026-04-10T13:10:00Z",
            "confidence": 0.95
        },
        {
            "event_id": "ev-re-3",
            "store_id": "ST_TEST",
            "camera_id": "CAM1",
            "visitor_id": "VIS_RE",
            "event_type": "REENTRY",
            "timestamp": "2026-04-10T13:20:00Z",
            "confidence": 0.95
        }
    ]
    client.post("/events/ingest", json=events)
    
    res = client.get("/stores/ST_TEST/funnel")
    data = res.json()
    # Only VIS_RE is in the database, so unique entries is 1
    assert data["entry_count"] == 1

def test_heatmap_endpoint():
    # Ingest a zone dwell event to test heatmap
    event = {
        "event_id": "dwell-id-1",
        "store_id": "ST_TEST",
        "camera_id": "CAM2",
        "visitor_id": "VIS_DWELLER",
        "event_type": "ZONE_DWELL",
        "zone_id": "SKINCARE",
        "dwell_ms": 5000,
        "timestamp": "2026-04-10T12:30:00Z",
        "confidence": 0.90
    }
    client.post("/events/ingest", json=[event])
    res = client.get("/stores/ST_TEST/heatmap")
    assert res.status_code == 200
    data = res.json()
    assert "zones" in data
    assert len(data["zones"]) > 0
    assert data["zones"][0]["zone_id"] == "SKINCARE"
    assert data["zones"][0]["visit_frequency_normalized"] == 100.0
    assert data["data_confidence"] is False # less than 20 sessions

def test_anomalies_endpoint():
    res = client.get("/stores/ST_TEST/anomalies")
    assert res.status_code == 200
    data = res.json()
    assert "active_anomalies" in data

def test_ingest_json_lines():
    event1 = '{"event_id": "jl-1", "store_id": "ST_TEST", "camera_id": "CAM1", "visitor_id": "VIS_JL", "event_type": "ENTRY", "timestamp": "2026-04-10T12:00:00Z", "confidence": 0.95}'
    event2 = '{"event_id": "jl-2", "store_id": "ST_TEST", "camera_id": "CAM1", "visitor_id": "VIS_JL", "event_type": "EXIT", "timestamp": "2026-04-10T12:10:00Z", "confidence": 0.95}'
    payload = f"{event1}\n{event2}\n"
    
    res = client.post("/events/ingest", content=payload, headers={"Content-Type": "text/plain"})
    assert res.status_code == 202
    assert res.json()["processed"] == 2

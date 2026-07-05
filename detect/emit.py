import json
import uuid
from typing import Optional, Dict, Any

def create_event(
    store_id: str,
    camera_id: str,
    visitor_id: str,
    event_type: str,
    timestamp: str,
    zone_id: Optional[str] = None,
    dwell_ms: Optional[int] = None,
    is_staff: bool = False,
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None
) -> dict:
    if metadata is None:
        metadata = {}
        
    full_metadata = {
        "queue_depth": metadata.get("queue_depth", None),
        "sku_zone": metadata.get("sku_zone", None),
        "session_seq": metadata.get("session_seq", None)
    }
    for k, v in metadata.items():
        if k not in full_metadata:
            full_metadata[k] = v

    event = {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": camera_id,
        "visitor_id": visitor_id,
        "event_type": event_type,
        "timestamp": timestamp,
        "zone_id": zone_id,
        "dwell_ms": dwell_ms,
        "is_staff": is_staff,
        "confidence": confidence,
        "metadata": full_metadata
    }
    return event

def emit_event(event: dict, output_file: Optional[str] = None):
    event_json = json.dumps(event)
    print(event_json)
    if output_file:
        with open(output_file, 'a') as f:
            f.write(event_json + '\n')

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Tuple
from .models import StoreEvent
from .database import DBEvent
import json

def process_single_event(event: StoreEvent, db: Session) -> Tuple[bool, str]:
    try:
        # Check for existing event (Idempotency)
        existing = db.query(DBEvent).filter(DBEvent.event_id == event.event_id).first()
        if existing:
            return True, "duplicate"

        metadata_dict = event.metadata.dict() if event.metadata else {}
        
        db_event = DBEvent(
            event_id=event.event_id,
            store_id=event.store_id,
            camera_id=event.camera_id,
            visitor_id=event.visitor_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            zone_id=event.zone_id,
            dwell_ms=event.dwell_ms,
            is_staff=event.is_staff,
            confidence=event.confidence,
            metadata_json=metadata_dict
        )
        db.add(db_event)
        db.commit()
        return True, ""
    except IntegrityError:
        db.rollback()
        return False, "Integrity error"
    except Exception as e:
        db.rollback()
        return False, str(e)

def process_events(events: List[StoreEvent], db: Session) -> Tuple[int, List[dict]]:
    processed_count = 0
    errors = []
    
    for event in events:
        success, err = process_single_event(event, db)
        if success:
            if err != "duplicate":
                processed_count += 1
        else:
            errors.append({"event_id": event.event_id, "error": err})
            
    return processed_count, errors

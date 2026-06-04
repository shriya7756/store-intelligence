from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from .database import DBEvent
from .models import StatsResponse


def get_stats(store_id: str, db: Session) -> StatsResponse:
    total = db.query(func.count(DBEvent.event_id)).filter(DBEvent.store_id == store_id).scalar() or 0
    last_ts = db.query(func.max(DBEvent.timestamp)).filter(DBEvent.store_id == store_id).scalar()
    return StatsResponse(store_id=store_id, total_events=int(total), last_event_timestamp=last_ts)

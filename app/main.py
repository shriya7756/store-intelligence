import time
import uuid
import logging
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List

from .models import StoreEvent, MetricResponse, FunnelResponse, HeatmapResponse, AnomaliesResponse, HealthResponse
from .database import engine, Base, get_db, init_db
from .ingestion import process_events, process_single_event
from .seed import load_pos_data, load_events_data
from pydantic import ValidationError
from .metrics import get_metrics
from .funnel import get_funnel
from .heatmap import get_heatmap
from .anomalies import check_anomalies
from .health import get_health_status

# Configure structured logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("store_intelligence_api")

app = FastAPI(title="Store Intelligence API")
app.mount("/dashboard", StaticFiles(directory="app/static", html=True), name="static")

@app.on_event("startup")
def startup_event():
    init_db()
    load_pos_data()
    load_events_data()

@app.get("/")
def root():
    return RedirectResponse(url="/dashboard/")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    trace_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Initialize state for event count
    request.state.event_count = 0
    
    # Check if request has store_id in path
    store_id = None
    if "stores/" in request.url.path:
        parts = request.url.path.split("/")
        try:
            idx = parts.index("stores")
            if idx + 1 < len(parts):
                store_id = parts[idx + 1]
        except ValueError:
            pass

    response = await call_next(request)
    process_time = (time.time() - start_time) * 1000
    
    event_count = getattr(request.state, "event_count", 0)
    
    log_data = {
        "trace_id": trace_id,
        "store_id": store_id,
        "endpoint": request.url.path,
        "method": request.method,
        "latency_ms": round(process_time, 2),
        "event_count": event_count,
        "status_code": response.status_code,
    }
    logger.info(log_data)
    
    # Inject trace id to headers
    response.headers["X-Trace-Id"] = trace_id
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}")
    return JSONResponse(
        status_code=503,
        content={"message": "Service unavailable due to internal error.", "error_type": type(exc).__name__},
    )

import json
from pydantic import ValidationError
from .ingestion import process_single_event

@app.post("/events/ingest", status_code=202)
async def ingest_events(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    try:
        raw_events = json.loads(body)
    except json.JSONDecodeError:
        try:
            lines = body.decode("utf-8").strip().split("\n")
            raw_events = [json.loads(line) for line in lines if line.strip()]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON or JSON Lines payload")
            
    if not isinstance(raw_events, list):
        raise HTTPException(status_code=400, detail="Payload must be a list of events")
        
    if len(raw_events) > 500:
        raise HTTPException(status_code=400, detail="Batch size exceeds maximum limit of 500 events")

    request.state.event_count = len(raw_events)

    processed_count = 0
    errors = []
    
    for idx, item in enumerate(raw_events):
        try:
            if not isinstance(item, dict):
                errors.append({"index": idx, "error": "Event must be a JSON object", "event_id": None})
                continue
            # Validate using Pydantic model
            event = StoreEvent(**item)
            # Process single event (deduplicate and save)
            success, err_msg = process_single_event(event, db)
            if success:
                if err_msg != "duplicate":
                    processed_count += 1
            else:
                errors.append({"index": idx, "error": err_msg, "event_id": item.get("event_id")})
        except ValidationError as ve:
            err_details = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in ve.errors()]
            errors.append({"index": idx, "error": err_details, "event_id": item.get("event_id") if isinstance(item, dict) else None})
        except Exception as e:
            errors.append({"index": idx, "error": str(e), "event_id": item.get("event_id") if isinstance(item, dict) else None})
            
    return {"processed": processed_count, "errors": errors}

@app.get("/stores/{store_id}/metrics", response_model=MetricResponse)
def metrics(store_id: str, db: Session = Depends(get_db)):
    return get_metrics(store_id, db)

@app.get("/stores/{store_id}/funnel", response_model=FunnelResponse)
def funnel(store_id: str, db: Session = Depends(get_db)):
    return get_funnel(store_id, db)

@app.get("/stores/{store_id}/heatmap", response_model=HeatmapResponse)
def heatmap(store_id: str, db: Session = Depends(get_db)):
    return get_heatmap(store_id, db)

@app.get("/stores/{store_id}/anomalies", response_model=AnomaliesResponse)
def anomalies(store_id: str, db: Session = Depends(get_db)):
    return check_anomalies(store_id, db)

@app.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    return get_health_status(db)

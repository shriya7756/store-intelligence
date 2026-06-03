# Technical Choices

## 1. Detection Model
- **Options Considered**: YOLOv8, MediaPipe, RT-DETR.
- **What AI Suggested**: The LLM suggested YOLOv8 for its optimal balance of speed and accuracy, and strong out-of-the-box tracking (ByteTrack) integration via the `ultralytics` library.
- **What I Chose**: I chose `YOLOv8n` (nano) coupled with simple centroid tracking logic. This ensures that the pipeline can run locally even without a powerful GPU, fulfilling the requirement of a reproducible pipeline. For the sake of the API test, I also implemented a fallback mock generator within the script if the large CV libraries are not installed.

## 2. Event Schema Design
- **Options Considered**: Deeply nested JSON with full bounding box coordinates vs. Flat, semantic events.
- **What AI Suggested**: The LLM proposed sending every frame's raw bounding box data to the API for processing.
- **What I Chose**: I overrode the AI. Sending raw bounding boxes at 15fps creates massive network overhead. Instead, the detection layer is stateful. It computes `ZONE_ENTER` and `ZONE_DWELL` and emits only semantic events. The schema uses a flat structure with a generic `metadata` dictionary to allow for future extensibility (e.g., `queue_depth`).

## 3. API Architecture
- **Options Considered**: Express.js, Flask, FastAPI.
- **What AI Suggested**: The LLM recommended FastAPI due to its async nature, built-in Pydantic validation, and automatic OpenAPI documentation.
- **What I Chose**: I agreed with the AI and used FastAPI. FastAPI's Pydantic models automatically validate the incoming event schema, rejecting malformed events with clear error messages. This guarantees that the SQLite database only stores valid, strictly-typed data, making the downstream metric calculations robust.

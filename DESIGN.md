# Design Overview

## Architecture

The system is split into two primary components to allow independent scaling and development:
1. **Detection Layer (`detect.py`)**: A script designed to process video frames using YOLOv8, track individuals across frames, compute dwell times, and emit structured JSON events.
2. **Intelligence API (`FastAPI`)**: A high-performance REST API that ingests the JSON events, persists them to an SQLite database, and serves real-time computed metrics such as conversion rates and funnels.

## AI-Assisted Decisions

1. **Test Edge Case Generation**:
   - *Prompt*: "Generate FastAPI tests for the Store Intelligence API covering ingest, metrics, and funnel endpoints. Include edge cases like idempotency, empty store, and all-staff traffic."
   - *Decision*: I used an LLM to quickly scaffold the `test_pipeline.py` file with the Pytest framework. The LLM suggested using `TestClient` which is standard. However, I had to override the initial LLM output because it assumed an in-memory DB setup that conflicted with my SQLAlchemy initialization. I added the `setup_db` fixture to ensure the database was cleanly initialized and seeded with mock POS data for the tests to pass.

2. **Database Choice for Metrics**:
   - *Decision*: When designing the metrics computation, I queried an LLM on whether to compute metrics on-the-fly via SQL aggregates or pre-compute them asynchronously. The LLM suggested an event-driven architecture with Redis for real-time counters. I overrode this suggestion. For this challenge, a simpler read-optimized SQL query approach on SQLite is sufficient and reduces infrastructure complexity (no Redis required for `docker compose up`).

3. **POS Data Correlation**:
   - *Decision*: I used an LLM to conceptualize how to tie asynchronous POS transactions (which have no customer ID) to visitor tracks. It proposed a time-window correlation. I implemented a simplified version of this logic in the metrics calculations.

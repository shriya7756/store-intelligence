# Store Intelligence

## Setup & Run

1. `git clone <repo>`
2. `cd store-intelligence`
3. `docker compose up --build`
4. The API is now running at `http://localhost:8000`
5. The Live Dashboard is accessible at `http://localhost:8000/dashboard/`
6. The POS data is automatically seeded on startup via `app/seed.py`.

## Running the Detection Pipeline
1. Install Python requirements for detection: `pip install ultralytics opencv-python`
2. Run the detection script against the clips:
   `cd detect`
   `python detect.py --video "../Store 1-20260602T101818Z-3-001ec38db8/Store 1/CAM 3 - entry.mp4" --store "STORE_BLR_002" --camera "CAM_ENTRY_01" > events.jsonl`
   
Note: If `ultralytics` is not installed, `detect.py` will automatically generate a mock events list to allow you to test the API easily.

## Ingesting Events
You can pipe the generated events into the API:
```bash
curl -X POST -H "Content-Type: application/json" -d @detect/events.jsonl http://localhost:8000/events/ingest
```

## Deploying to Production

### Option 1: Render (Recommended)
1. Go to [render.com](https://render.com)
2. Sign in with GitHub
3. Create a new Web Service from the `store-intelligence` repository
4. Render will auto-detect `render.yaml` and configure the deployment
5. The API will be live at your Render domain (e.g., `https://store-intelligence.onrender.com`)
6. Access the dashboard at `/dashboard/`

### Option 2: Railway
1. Go to [railway.app](https://railway.app)
2. Sign in with GitHub
3. Create a new project and connect the repository
4. Railway will detect Python and use the `Procfile`
5. Set environment variables if needed
6. Deploy — the API will be live on your Railway domain

### Option 3: Local Docker Deployment
```bash
docker compose up --build
```

## Hackathon Submission
- **Submitter**: `shriyapachunuri`
- **Challenge**: Purplle Tech Challenge 2026 | Round 2
- **Team Name**: Shriya's Team 3
- **Role**: Team Leader
- **Team Size**: 1 member

### Submission Deliverables
- `README.md`
- `DESIGN.md`
- `CHOICES.md`
- `sample_events.jsonl`
- Source code in this repository

### Notes
- `sample_events.jsonl` provides a valid JSONL event log example for ingestion.
- `DESIGN.md` includes an AI-Assisted Decisions section.
- `CHOICES.md` covers model selection, schema design, and API architecture decisions.
- Deployment configs (`render.yaml`, `Procfile`) included for seamless production deployment.

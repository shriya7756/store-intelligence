#!/bin/bash

# This script runs the detection pipeline on sample clips and posts events to the API
# Usage: ./run.sh

set -euo pipefail

mkdir -p output

# Generate events for Store ST1008 (writes to stdout) and POST to local ingest endpoint
INGEST_URL=${INGEST_URL:-http://localhost:8000/events/ingest}

python detect.py --video "../Store 1-20260602T101818Z-3-001ec38db8/Store 1/CAM 3 - entry.mp4" --store "ST1008" --camera "CAM1" | python post_events.py -u "$INGEST_URL"

# Also generate for STORE_BLR_002 and POST
python detect.py --video "../Store 1-20260602T101818Z-3-001ec38db8/Store 1/CAM 3 - entry.mp4" --store "STORE_BLR_002" --camera "CAM_ENTRY_01" | python post_events.py -u "$INGEST_URL"

echo "Events generated and posted to ingest endpoint"

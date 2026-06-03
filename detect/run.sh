#!/bin/bash

# This script runs the detection pipeline on sample clips
# Usage: ./run.sh

mkdir -p output

# Process Store 1 Videos
python detect.py --video "../Store 1-20260602T101818Z-3-001ec38db8/Store 1/CAM 3 - entry.mp4" --store "ST1008" --camera "CAM1" > output/events.jsonl

# In a real environment we would pipe to the API or use a POST script
# e.g., cat output/events.jsonl | python post_events.py

echo "Events written to output/events.jsonl"

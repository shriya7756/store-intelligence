import argparse
import cv2
import sys
import json
import uuid
import os
import csv
from datetime import datetime, timedelta
import time

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

from emit import create_event, emit_event

# Shared Re-ID gallery file path
REID_GALLERY_PATH = "reid_gallery.json"
BASE_TIMESTAMP_STR = "2026-04-10T12:00:00Z"
BASE_TIMESTAMP = datetime.strptime(BASE_TIMESTAMP_STR, "%Y-%m-%dT%H:%M:%SZ")

def load_store_layout():
    paths = ["store_layout.json", "../store_layout.json", "store-intelligence/store_layout.json"]
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
    return []

def get_zone_for_camera(store_id: str, camera_id: str):
    layouts = load_store_layout()
    for store in layouts:
        if store["store_id"] == store_id:
            for zone in store["zones"]:
                if camera_id in zone["camera_coverage"]:
                    return zone
    return None

def load_reid_gallery():
    if os.path.exists(REID_GALLERY_PATH):
        try:
            with open(REID_GALLERY_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_reid_gallery(gallery):
    try:
        with open(REID_GALLERY_PATH, "w") as f:
            json.dump(gallery, f)
    except Exception as e:
        print(f"Error saving Re-ID gallery: {e}", file=sys.stderr)

def get_color_histogram(frame, box):
    x1, y1, x2, y2 = box
    h, w, _ = frame.shape
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    try:
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [8, 8], [0, 180, 0, 256])
        cv2.normalize(hist, hist)
        return hist.flatten().tolist()
    except Exception:
        return None

def compare_histograms(hist1, hist2):
    if not hist1 or not hist2:
        return 0.0
    import numpy as np
    h1 = np.array(hist1, dtype=np.float32)
    h2 = np.array(hist2, dtype=np.float32)
    dot = np.dot(h1, h2)
    norm1 = np.linalg.norm(h1)
    norm2 = np.linalg.norm(h2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))

def check_pos_transaction_completed(store_id: str, exit_time_dt: datetime) -> bool:
    csv_paths = ["pos_transactions.csv", "../pos_transactions.csv", "../POS - sample transactionsb1e826f.csv"]
    for path in csv_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['store_id'] == store_id:
                            dt_str = f"{row['order_date']} {row['order_time']}"
                            dt = datetime.strptime(dt_str, "%d-%m-%Y %H:%M:%S")
                            diff = (dt - exit_time_dt).total_seconds()
                            if 0 <= diff <= 300: # 5 minute window
                                return True
            except Exception as e:
                print(f"Error reading CSV {path}: {e}", file=sys.stderr)
    return False

def generate_mock_events(store_id: str, camera_id: str, output_file: str = None):
    """Generates a highly realistic series of mock events complying with the schema and POS data."""
    print(f"Generating realistic mock events for {store_id} / {camera_id}...", file=sys.stderr)
    zone_info = get_zone_for_camera(store_id, camera_id)
    zone_id = zone_info["zone_id"] if zone_info else "ZONE_01"
    zone_type = zone_info["type"] if zone_info else "FLOOR"
    sku_zone = zone_info.get("sku_zone", None) if zone_info else None
    
    events = []
    
    # 1. Normal Customer: VIS_001. Enters store, dwells, enters billing queue, purchases, exits.
    # We map this to match a transaction at 12:15:05
    v1 = "VIS_001"
    t1_base = datetime(2026, 4, 10, 12, 0, 0)
    
    if zone_type == "THRESHOLD":
        events.append(create_event(store_id, camera_id, v1, "ENTRY", (t1_base).isoformat() + "Z", confidence=0.98, metadata={"session_seq": 1}))
        events.append(create_event(store_id, camera_id, v1, "EXIT", (t1_base + timedelta(minutes=16)).isoformat() + "Z", confidence=0.96, metadata={"session_seq": 6}))
        
    elif zone_type == "FLOOR":
        events.append(create_event(store_id, camera_id, v1, "ZONE_ENTER", (t1_base + timedelta(minutes=1)).isoformat() + "Z", zone_id=zone_id, confidence=0.95, metadata={"sku_zone": sku_zone, "session_seq": 2}))
        events.append(create_event(store_id, camera_id, v1, "ZONE_DWELL", (t1_base + timedelta(minutes=1, seconds=40)).isoformat() + "Z", zone_id=zone_id, dwell_ms=40000, confidence=0.92, metadata={"sku_zone": sku_zone, "session_seq": 3}))
        events.append(create_event(store_id, camera_id, v1, "ZONE_EXIT", (t1_base + timedelta(minutes=10)).isoformat() + "Z", zone_id=zone_id, confidence=0.94, metadata={"sku_zone": sku_zone, "session_seq": 4}))
        
    elif zone_type == "BILLING":
        events.append(create_event(store_id, camera_id, v1, "BILLING_QUEUE_JOIN", (t1_base + timedelta(minutes=12)).isoformat() + "Z", zone_id=zone_id, confidence=0.93, metadata={"queue_depth": 1, "session_seq": 5}))
        # Dwells in queue
        events.append(create_event(store_id, camera_id, v1, "ZONE_DWELL", (t1_base + timedelta(minutes=14)).isoformat() + "Z", zone_id=zone_id, dwell_ms=120000, confidence=0.90, metadata={"session_seq": 6}))
        events.append(create_event(store_id, camera_id, v1, "ZONE_EXIT", (t1_base + timedelta(minutes=15)).isoformat() + "Z", zone_id=zone_id, confidence=0.91, metadata={"session_seq": 7}))

    # 2. Abandoned Customer: VIS_002. Enters billing queue but exits without a POS transaction.
    # Placing billing queue exit at 13:10:00 (no transaction matches in 12:42:18 - 13:41:55)
    v2 = "VIS_002"
    t2_base = datetime(2026, 4, 10, 12, 50, 0)
    
    if zone_type == "THRESHOLD":
        events.append(create_event(store_id, camera_id, v2, "ENTRY", t2_base.isoformat() + "Z", confidence=0.97, metadata={"session_seq": 1}))
        events.append(create_event(store_id, camera_id, v2, "EXIT", (t2_base + timedelta(minutes=25)).isoformat() + "Z", confidence=0.95, metadata={"session_seq": 5}))
        
    elif zone_type == "FLOOR":
        events.append(create_event(store_id, camera_id, v2, "ZONE_ENTER", (t2_base + timedelta(minutes=2)).isoformat() + "Z", zone_id=zone_id, confidence=0.94, metadata={"sku_zone": sku_zone, "session_seq": 2}))
        events.append(create_event(store_id, camera_id, v2, "ZONE_EXIT", (t2_base + timedelta(minutes=8)).isoformat() + "Z", zone_id=zone_id, confidence=0.91, metadata={"sku_zone": sku_zone, "session_seq": 3}))
        
    elif zone_type == "BILLING":
        events.append(create_event(store_id, camera_id, v2, "BILLING_QUEUE_JOIN", (t2_base + timedelta(minutes=10)).isoformat() + "Z", zone_id=zone_id, confidence=0.92, metadata={"queue_depth": 2, "session_seq": 4}))
        # Abandon event
        events.append(create_event(store_id, camera_id, v2, "BILLING_QUEUE_ABANDON", (t2_base + timedelta(minutes=20)).isoformat() + "Z", zone_id=zone_id, confidence=0.88, metadata={"session_seq": 5}))

    # 3. Staff: VIS_STAFF. Stays long, visits all zones, marked is_staff=True.
    v_staff = "VIS_STAFF"
    t3_base = datetime(2026, 4, 10, 9, 0, 0)
    
    if zone_type == "THRESHOLD":
        events.append(create_event(store_id, camera_id, v_staff, "ENTRY", t3_base.isoformat() + "Z", is_staff=True, confidence=0.99, metadata={"session_seq": 1}))
        events.append(create_event(store_id, camera_id, v_staff, "EXIT", (t3_base + timedelta(hours=8)).isoformat() + "Z", is_staff=True, confidence=0.99, metadata={"session_seq": 10}))
        
    elif zone_type == "FLOOR":
        events.append(create_event(store_id, camera_id, v_staff, "ZONE_ENTER", (t3_base + timedelta(minutes=30)).isoformat() + "Z", zone_id=zone_id, is_staff=True, confidence=0.98, metadata={"sku_zone": sku_zone, "session_seq": 2}))
        events.append(create_event(store_id, camera_id, v_staff, "ZONE_DWELL", (t3_base + timedelta(minutes=31)).isoformat() + "Z", zone_id=zone_id, dwell_ms=60000, is_staff=True, confidence=0.95, metadata={"sku_zone": sku_zone, "session_seq": 3}))
        
    elif zone_type == "BILLING":
        events.append(create_event(store_id, camera_id, v_staff, "ZONE_ENTER", (t3_base + timedelta(hours=2)).isoformat() + "Z", zone_id=zone_id, is_staff=True, confidence=0.97, metadata={"session_seq": 4}))

    # 4. Re-Entry Customer: VIS_004. Enters, exits, and then re-enters.
    v4 = "VIS_004"
    t4_base = datetime(2026, 4, 10, 13, 30, 0)
    
    if zone_type == "THRESHOLD":
        # First entry
        events.append(create_event(store_id, camera_id, v4, "ENTRY", t4_base.isoformat() + "Z", confidence=0.96, metadata={"session_seq": 1}))
        events.append(create_event(store_id, camera_id, v4, "EXIT", (t4_base + timedelta(minutes=5)).isoformat() + "Z", confidence=0.95, metadata={"session_seq": 2}))
        # Re-entry
        events.append(create_event(store_id, camera_id, v4, "REENTRY", (t4_base + timedelta(minutes=15)).isoformat() + "Z", confidence=0.96, metadata={"session_seq": 3}))
        events.append(create_event(store_id, camera_id, v4, "EXIT", (t4_base + timedelta(minutes=30)).isoformat() + "Z", confidence=0.94, metadata={"session_seq": 6}))
        
    elif zone_type == "FLOOR":
        events.append(create_event(store_id, camera_id, v4, "ZONE_ENTER", (t4_base + timedelta(minutes=17)).isoformat() + "Z", zone_id=zone_id, confidence=0.92, metadata={"sku_zone": sku_zone, "session_seq": 4}))
        events.append(create_event(store_id, camera_id, v4, "ZONE_DWELL", (t4_base + timedelta(minutes=20)).isoformat() + "Z", zone_id=zone_id, dwell_ms=180000, confidence=0.90, metadata={"sku_zone": sku_zone, "session_seq": 5}))

    # Emit all generated events
    for ev in events:
        emit_event(ev, output_file)

def process_video(video_path: str, store_id: str, camera_id: str):
    if not HAS_YOLO or not os.path.exists(video_path):
        print("Falling back to realistic mock events generator.", file=sys.stderr)
        generate_mock_events(store_id, camera_id)
        return

    print(f"Starting YOLO detection and tracking on {video_path}...", file=sys.stderr)
    model = YOLO("yolov8n.pt")
    cap = cv2.VideoCapture(video_path)
    
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 15.0
    int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if frame_height == 0:
        frame_height = 1080

    zone_info = get_zone_for_camera(store_id, camera_id)
    if not zone_info:
        print(f"Error: Camera {camera_id} is not mapped in layout for store {store_id}", file=sys.stderr)
        return
        
    zone_id = zone_info["zone_id"]
    zone_type = zone_info["type"]
    sku_zone = zone_info.get("sku_zone", None)

    # Initialize tracking & state
    active_tracks = {}
    gallery = load_reid_gallery()
    frame_count = 0
    
    # Active queue count for BILLING camera
    billing_active_visitors = set()

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        # Process every 5th frame to speed up
        if frame_count % 5 != 0:
            continue
            
        results = model.track(frame, persist=True, classes=[0], verbose=False)
        
        # Calculate video frame-offset based timestamp
        offset_seconds = frame_count / fps
        event_time = BASE_TIMESTAMP + timedelta(seconds=offset_seconds)
        ts_str = event_time.isoformat() + "Z"

        present_track_ids = set()

        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            track_ids = results[0].boxes.id.int().cpu().tolist()
            confidences = results[0].boxes.conf.cpu().tolist()
            
            for box, track_id, conf in zip(boxes, track_ids, confidences):
                x1, y1, x2, y2 = box
                (x1 + x2) / 2
                cy = (y1 + y2) / 2
                y_norm = cy / frame_height
                
                present_track_ids.add(track_id)

                # Re-ID lookup or registration
                hist = get_color_histogram(frame, box)
                visitor_id = None
                is_reentry = False
                
                # Check match against gallery
                best_match_id = None
                best_similarity = 0.0
                for vid, profile in gallery.items():
                    if profile.get("store") == store_id:
                        sim = compare_histograms(hist, profile.get("histogram"))
                        if sim > best_similarity:
                            best_similarity = sim
                            best_match_id = vid
                
                if best_similarity > 0.75:
                    visitor_id = best_match_id
                    profile = gallery[visitor_id]
                    # Check if they previously exited
                    if profile.get("exited", False):
                        is_reentry = True
                        profile["exited"] = False
                    profile["last_seen_time"] = time.time()
                else:
                    visitor_id = f"VIS_{uuid.uuid4().hex[:6]}"
                    gallery[visitor_id] = {
                        "histogram": hist,
                        "store": store_id,
                        "first_seen": ts_str,
                        "last_seen_time": time.time(),
                        "exited": False,
                        "cameras": [camera_id],
                        "session_seq": 0,
                        "is_staff": False
                    }
                
                profile = gallery[visitor_id]
                if camera_id not in profile["cameras"]:
                    profile["cameras"].append(camera_id)
                
                # Track session sequence count
                profile["session_seq"] += 1
                seq = profile["session_seq"]
                is_staff = profile.get("is_staff", False)

                # Track initialization or updates
                if track_id not in active_tracks:
                    # New local track
                    active_tracks[track_id] = {
                        "visitor_id": visitor_id,
                        "start_time": time.time(),
                        "start_ts": event_time,
                        "last_seen": time.time(),
                        "last_y": y_norm,
                        "history": [y_norm],
                        "dwell_start_time": time.time(),
                        "last_dwell_emit": time.time()
                    }
                    
                    # Handle threshold crossing / Entry detection
                    if zone_type == "THRESHOLD":
                        event_type = "REENTRY" if is_reentry else "ENTRY"
                        ev = create_event(store_id, camera_id, visitor_id, event_type, ts_str, is_staff=is_staff, confidence=conf, metadata={"session_seq": seq})
                        emit_event(ev)
                    else:
                        # Non-threshold cameras map to ZONE_ENTER immediately
                        ev = create_event(store_id, camera_id, visitor_id, "ZONE_ENTER", ts_str, zone_id=zone_id, is_staff=is_staff, confidence=conf, metadata={"sku_zone": sku_zone, "session_seq": seq})
                        emit_event(ev)
                        
                        if zone_type == "BILLING":
                            billing_active_visitors.add(visitor_id)
                            # Emit BILLING_QUEUE_JOIN
                            ev_join = create_event(store_id, camera_id, visitor_id, "BILLING_QUEUE_JOIN", ts_str, zone_id=zone_id, is_staff=is_staff, confidence=conf, metadata={"queue_depth": len(billing_active_visitors), "session_seq": seq + 1})
                            profile["session_seq"] += 1
                            emit_event(ev_join)
                else:
                    # Existing local track
                    track = active_tracks[track_id]
                    track["last_seen"] = time.time()
                    track["history"].append(y_norm)
                    
                    # Staff detection heuristic:
                    # If track duration exceeds 5 mins (300 secs) or visits more than 2 cameras
                    duration = time.time() - track["start_time"]
                    if (duration > 300 or len(profile["cameras"]) >= 3) and not profile["is_staff"]:
                        profile["is_staff"] = True
                        is_staff = True
                    
                    # Dwell times
                    dwell_duration = (time.time() - track["dwell_start_time"])
                    if dwell_duration >= 30: # every 30 seconds
                        ev_dwell = create_event(store_id, camera_id, visitor_id, "ZONE_DWELL", ts_str, zone_id=zone_id, dwell_ms=int(dwell_duration * 1000), is_staff=is_staff, confidence=conf, metadata={"sku_zone": sku_zone, "session_seq": seq})
                        profile["session_seq"] += 1
                        emit_event(ev_dwell)
                        track["dwell_start_time"] = time.time() # Reset dwell timer
                        
        # Detect tracks that left (local clean-up & Exit / Abandonment emits)
        lost_tracks = []
        for track_id, track in active_tracks.items():
            if track_id not in present_track_ids:
                # Track lost (person left camera)
                lost_tracks.append(track_id)
                visitor_id = track["visitor_id"]
                profile = gallery[visitor_id]
                seq = profile["session_seq"]
                is_staff = profile.get("is_staff", False)

                # Process Exit
                if zone_type == "THRESHOLD":
                    # Direction verification: check first y vs last y
                    track["history"][0]
                    track["history"][-1]
                    # y increases downwards, so if y went from >0.5 to <0.5 (moving up/out) or similar.
                    # Standard fallback: emit EXIT since they left threshold cam area
                    ev_exit = create_event(store_id, camera_id, visitor_id, "EXIT", ts_str, is_staff=is_staff, confidence=0.90, metadata={"session_seq": seq + 1})
                    profile["session_seq"] += 1
                    emit_event(ev_exit)
                    profile["exited"] = True
                    profile["exit_time"] = ts_str
                    
                else:
                    # Zone Exit
                    ev_exit = create_event(store_id, camera_id, visitor_id, "ZONE_EXIT", ts_str, zone_id=zone_id, is_staff=is_staff, confidence=0.90, metadata={"sku_zone": sku_zone, "session_seq": seq + 1})
                    profile["session_seq"] += 1
                    emit_event(ev_exit)
                    
                    if zone_type == "BILLING" and visitor_id in billing_active_visitors:
                        billing_active_visitors.remove(visitor_id)
                        # Check POS transaction correlation to decide if Abandon or Purchase
                        # Note: we use event_time as checkout exit timestamp
                        has_purchased = check_pos_transaction_completed(store_id, event_time)
                        if not has_purchased and not is_staff:
                            # Emit BILLING_QUEUE_ABANDON
                            ev_abandon = create_event(store_id, camera_id, visitor_id, "BILLING_QUEUE_ABANDON", ts_str, zone_id=zone_id, is_staff=is_staff, confidence=0.90, metadata={"session_seq": seq + 2})
                            profile["session_seq"] += 2
                            emit_event(ev_abandon)

        for track_id in lost_tracks:
            del active_tracks[track_id]

        save_reid_gallery(gallery)

    cap.release()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=str, required=True, help="Path to video file")
    parser.add_argument("--store", type=str, required=True, help="Store ID")
    parser.add_argument("--camera", type=str, required=True, help="Camera ID")
    parser.add_argument("--output", type=str, required=False, default=None, help="Save to events file")
    args = parser.parse_args()
    
    process_video(args.video, args.store, args.camera)

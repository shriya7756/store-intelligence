import sys
import json
import argparse
from typing import List
import httpx


def read_events_from_stream(stream) -> List[dict]:
    text = stream.read()
    if not text:
        return []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
    except Exception:
        # Try JSON Lines
        events = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                # Skip invalid lines
                continue
        return events
    return []


def post_events(events: List[dict], url: str, batch_size: int = 200):
    if not events:
        print("No events to post.")
        return 0

    client = httpx.Client(timeout=30.0)
    posted = 0
    for i in range(0, len(events), batch_size):
        batch = events[i:i+batch_size]
        try:
            resp = client.post(url, json=batch)
            if resp.status_code in (200, 202):
                print(f"Posted batch {i//batch_size + 1}: {len(batch)} events -> {resp.status_code}")
                posted += len(batch)
            else:
                print(f"Failed to post batch {i//batch_size + 1}: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Error posting batch {i//batch_size + 1}: {e}")
    client.close()
    return posted


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Post events JSON/JSONL to Store Intelligence ingest endpoint')
    parser.add_argument('-u', '--url', default='http://localhost:8000/events/ingest', help='Ingest endpoint URL')
    parser.add_argument('-b', '--batch', type=int, default=200, help='Batch size for posting')
    parser.add_argument('file', nargs='?', help='File path to read events from (defaults to stdin)')
    args = parser.parse_args()

    if args.file:
        with open(args.file, 'r', encoding='utf-8') as f:
            events = read_events_from_stream(f)
    else:
        events = read_events_from_stream(sys.stdin)

    total = post_events(events, args.url, batch_size=args.batch)
    print(f"Total events posted: {total}")

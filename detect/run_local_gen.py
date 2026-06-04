import sys
from detect import generate_mock_events

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python run_local_gen.py <STORE_ID> <CAMERA_ID>", file=sys.stderr)
        sys.exit(2)
    store = sys.argv[1]
    camera = sys.argv[2]
    # generate_mock_events prints JSONL to stdout
    generate_mock_events(store, camera)

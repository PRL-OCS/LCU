import urllib.request
import json

def test_guide():
    url = "http://localhost:8004/api/command"
    payload = {
        "command": "guide",
        "params": {
            "directions": "N",
            "duration_ms": 1000
        }
    }
    
    print(f"Sending guide command to {url}...")
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            print("\nResponse from server:")
            print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"\nFailed to connect or send request: {e}")

if __name__ == "__main__":
    test_guide()

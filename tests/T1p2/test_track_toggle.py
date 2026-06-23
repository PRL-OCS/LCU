import socket
import sys
import time
import argparse

class SkychartSDK:
    def __init__(self, host: str = "127.0.0.1", port: int = 3292):
        self.host = host
        self.port = port

    def _execute(self, command: str) -> str:
        """Handles low-level socket delivery, flushes greetings, and returns clean data."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(3.0)
                s.connect((self.host, self.port))
                
                # FLUSH GREETING: Skychart sends an "OK!" token immediately on connect.
                _greeting = s.recv(1024) 
                
                # Now dispatch the real automation instruction
                s.sendall(f"{command}\r\n".encode('utf-8'))
                
                # Capture the actual evaluation response token
                response = s.recv(4096).decode('utf-8')
                return response.strip()
        except socket.timeout:
            return "ERROR: Connection Timeout"
        except ConnectionRefusedError:
            return "ERROR: Skychart server not running"
        except Exception as e:
            return f"ERROR: {e}"

    def test_connection(self) -> tuple[bool, str]:
        """Verifies if the network socket is active and accepting instructions."""
        response = self._execute("REDRAW")
        if response.startswith("ERROR"):
            return False, response
        return True, "Skychart daemon is awake, listening, and ready."

    def set_tracking(self, enabled: bool) -> tuple[bool, str]:
        """Enables or disables tracking in Skychart."""
        val = "ON" if enabled else "OFF"
        response = self._execute(f"TRACKTELESCOPE {val}")
        if response.startswith("ERROR") or "ERR" in response:
            return False, response
        return True, f"TRACKTELESCOPE {val} command succeeded."


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Skychart TCP Tracking Toggle")
    parser.add_argument("--host", default="127.0.0.1", help="Skychart TCP server host")
    parser.add_argument("--port", type=int, default=3292, help="Skychart TCP server port")
    args = parser.parse_args()

    print(f"Testing connection to Skychart at {args.host}:{args.port}...")
    skychart = SkychartSDK(host=args.host, port=args.port)
    
    is_online, msg = skychart.test_connection()
    if not is_online:
        print(f"[FAIL] Connection failed: {msg}")
        sys.exit(1)
        
    print(f"[PASS] Connection succeeded: {msg}")
    
    print("\n--- Starting Tracking Test ---")
    print("Enabling tracking...")
    success, resp = skychart.set_tracking(True)
    if not success:
        print(f"[FAIL] Failed to enable tracking: {resp}")
        sys.exit(1)
    print(f"[PASS] Tracking enabled successfully: {resp}")
    
    print("Waiting 10 seconds...")
    time.sleep(10)
    
    print("Disabling tracking...")
    success, resp = skychart.set_tracking(False)
    if not success:
        print(f"[FAIL] Failed to disable tracking: {resp}")
        sys.exit(1)
    print(f"[PASS] Tracking disabled successfully: {resp}")
    
    print("\nAll tests completed successfully!")
    sys.exit(0)

import socket
import sys

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
                # We consume it here so it doesn't pollute our actual command response.
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

    def test_connection(self) -> tuple[bool, str]:
        """Verifies if the network socket is active and accepting instructions."""
        response = self._execute("REDRAW")
        if response.startswith("ERROR"):
            return False, response
        return True, "Skychart daemon is awake, listening, and ready."

    def connect_telescope(self) -> dict:
        """Instructs Skychart to connect to the configured telescope."""
        response = self._execute("CONNECTTELESCOPE")
        if "ERR" in response or response.startswith("ERROR"):
            return {"success": False, "response": response}
        return {"success": True, "response": response}

    def target_to_coordinates(self, target_name: str) -> dict:
        """Resolves an object name and extracts computed equatorial coordinates."""
        search_res = self._execute(f'SEARCH "{target_name}"')
        if "ERR" in search_res or search_res.startswith("ERROR"):
            return {"success": False, "error": f"Lookup failed ({search_res})"}
        
        self._execute("REDRAW")
        coord_string = self._execute("GETSELECTEDOBJECT")
        return {"success": True, "raw_data": coord_string}


if __name__ == "__main__":
    skychart = SkychartSDK()
    
    print("==================================================")
    print("        SKYCHART FLATPAK API CONNECTIVITY TEST    ")
    print("==================================================\n")

    # Phase 1: Test Server Connection
    is_online, msg = skychart.test_connection()
    if not is_online:
        print(f"[FAIL] Phase 1 (Skychart Connection): {msg}")
        sys.exit(1)
    print(f"[PASS] Phase 1 (Skychart Connection): {msg}\n")

    # Phase 1.5: Test Telescope Connection via Skychart
    print("[RUN] Phase 1.5: Attempting to connect telescope driver in Skychart...")
    tel_conn = skychart.connect_telescope()
    if tel_conn["success"]:
        print(f"[PASS] Phase 1.5: Telescope connected. Response: {tel_conn['response']}\n")
    else:
        print(f"[FAIL] Phase 1.5: Telescope failed to connect! Response: {tel_conn['response']}\n")

    # Phase 2: Resolve Target Coordinates
    target = "Jupiter"
    print(f"[RUN] Phase 2: Resolving target '{target}'...")
    api_result = skychart.target_to_coordinates(target)
    
    if api_result["success"]:
        print("[PASS] Phase 2: Coordinates successfully retrieved!")
        print(f"       Data: {api_result['raw_data']}")
    else:
        print(f"[FAIL] Phase 2: {api_result['error']}")
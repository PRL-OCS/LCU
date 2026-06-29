import os
import sys
import time
import socket
import argparse
import unittest
import threading

# Parse custom argument before unittest parses command line arguments
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--live", action="store_true", help="Connect directly to the live telescope hardware")
args, unknown = parser.parse_known_args()

# Clean up sys.argv so unittest doesn't fail on the custom argument
sys.argv = [sys.argv[0]] + unknown

LIVE_TEST = args.live

class SimpleMockServer:
    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, port))
        self.port = self.server_sock.getsockname()[1]
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        try:
            self.server_sock.close()
        except:
            pass
        if self.thread:
            self.thread.join(timeout=1.0)

    def _run(self):
        self.server_sock.listen(1)
        while self.running:
            try:
                conn, addr = self.server_sock.accept()
                conn.sendall(b"Connect: OK\r\n")
                buffer = bytearray()
                while self.running:
                    data = conn.recv(1024)
                    if not data:
                        break
                    buffer.extend(data)
                    while b"\r\n" in buffer:
                        idx = buffer.index(b"\r\n")
                        line = buffer[:idx].decode("utf-8").strip()
                        del buffer[:idx+2]
                        if not line:
                            continue
                        
                        if line == "get nispdatads":
                            conn.sendall(b"got nispdatads 61220.405246499 9.0726953 09:04:21.7 09:43:33.17 89.999588 0.000268 6.45807316 24.67505189 FK5 9.05170817 24.75541476 1.223 off stationary off stationary off true Running 23.900000 68.100000 17.6 827.000000 2.800000 325.000000 \r\n")
                        elif line.startswith("do track"):
                            conn.sendall(b"ack track 0 OK\r\ndone track 0 OK\r\n")
                        elif line.startswith("do target"):
                            conn.sendall(b"ack target 0 OK\r\ndone target 0 OK\r\n")
            except Exception:
                break

class TestT2P5Flow(unittest.TestCase):
    def test_t2p5_flow(self):
        server = None
        if not LIVE_TEST:
            print("\n*** RUNNING IN MOCK SERVER MODE ***")
            server = SimpleMockServer()
            server.start()
            connect_host = "127.0.0.1"
            connect_port = server.port
            time.sleep(0.1)
        else:
            print("\n*** RUNNING IN LIVE HARDWARE MODE ***")
            connect_host = "172.16.20.221"
            connect_port = 7280

        print(f"Connecting to telescope at {connect_host}:{connect_port}...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(15.0)

        try:
            s.connect((connect_host, connect_port))
            
            # 1. Read first welcome/connect message
            # Must first receive b'Connect: OK\r\n'
            buffer = b""
            while b"\r\n" not in buffer:
                chunk = s.recv(1024)
                if not chunk:
                    break
                buffer += chunk
                
            line, sep, rest = buffer.partition(b"\r\n")
            print(f"Received handshake: {line}")
            self.assertIn(b"Connect: OK", line)
                
            # 2. Call "get nispdatads" and print response without formatting
            # Poll only once and move on to next step once received, else wait for 15 seconds.
            print("Sending command: get nispdatads")
            s.sendall(b"get nispdatads\r\n")
            
            # Read response
            t_start = time.time()
            resp_buffer = rest
            nisp_line = None
            
            while time.time() - t_start < 15.0:
                if b"\r\n" in resp_buffer:
                    nisp_line, sep, rest = resp_buffer.partition(b"\r\n")
                    break
                chunk = s.recv(1024)
                if not chunk:
                    break
                resp_buffer += chunk
                
            self.assertIsNotNone(nisp_line, "Did not receive nispdatads response within 15 seconds.")
            print(f"Received response: {nisp_line}")
            
            # 3. Parse indices 10 and 11 respectively (current RA and Dec)
            parts = nisp_line.decode("utf-8").strip().split()
            self.assertTrue(len(parts) >= 13, f"Expected at least 13 parts, got {len(parts)}")
            
            # parts[11] is RA, parts[12] is Dec
            parsed_ra = parts[11]
            parsed_dec = parts[12]
            print(f"Parsed current coordinates: RA={parsed_ra}, Dec={parsed_dec}")
            
            # Target coordinates hardcoded to ra=10 and dec=11
            ra = "10"
            dec = "11"
            
            # 4. Turn on tracking: send "do track state=on\r\n"
            track_cmd = "do track state=on\r\n"
            print(f"Sending command: {track_cmd.strip()}")
            s.sendall(track_cmd.encode())
            
            # Read tracking responses (expecting ack and done track)
            t_start = time.time()
            track_resp_buffer = rest
            track_responses = []
            
            while len(track_responses) < 2 and time.time() - t_start < 15.0:
                while b"\r\n" in track_resp_buffer:
                    line_resp, sep, track_resp_buffer = track_resp_buffer.partition(b"\r\n")
                    track_responses.append(line_resp)
                    if len(track_responses) == 2:
                        break
                if len(track_responses) == 2:
                    break
                chunk = s.recv(1024)
                if not chunk:
                    break
                track_resp_buffer += chunk
                
            rest = track_resp_buffer
            for r in track_responses:
                print(f"Received response: {r}")
                
            self.assertTrue(any(b"ack track 0" in r.lower() for r in track_responses), "Missing ack track 0")
            self.assertTrue(any(b"done track 0" in r.lower() for r in track_responses), "Missing done track 0")

            # 5. Slew: send "do target ra={ra} dec={dec}\r\n"
            slew_cmd = f"do target ra={ra} dec={dec}\r\n"
            print(f"Sending command: {slew_cmd.strip()}")
            s.sendall(slew_cmd.encode())
            
            # Read response (expecting ack and done target)
            t_start = time.time()
            ack_buffer = rest
            responses = []
            
            while len(responses) < 2 and time.time() - t_start < 15.0:
                while b"\r\n" in ack_buffer:
                    line_resp, sep, ack_buffer = ack_buffer.partition(b"\r\n")
                    responses.append(line_resp)
                    if len(responses) == 2:
                        break
                if len(responses) == 2:
                    break
                chunk = s.recv(1024)
                if not chunk:
                    break
                ack_buffer += chunk
                
            for r in responses:
                print(f"Received response: {r}")
                
            # Check responses
            self.assertTrue(any(b"ack target 0 OK" in r for r in responses), "Missing ack target 0 OK")
            self.assertTrue(any(b"done target 0 OK" in r for r in responses), "Missing done target 0 OK")
            print("Slew command acknowledged and complete.")
            print("Slew initiated. Final step reached.")
            
        finally:
            s.close()
            if server:
                server.stop()

if __name__ == "__main__":
    unittest.main()

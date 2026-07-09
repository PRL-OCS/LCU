import os
import sys
import time
import socket
import unittest
import argparse
from unittest.mock import patch

# Parse custom argument before unittest parses command line arguments
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--live", action="store_true", help="Connect directly to the live Skychart service")
args, unknown = parser.parse_known_args()

# Clean up sys.argv so unittest doesn't fail on the custom argument
sys.argv = [sys.argv[0]] + unknown

LIVE_TEST = args.live

SKYCHART_HOST = "127.0.0.1"
SKYCHART_PORT = 3292
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 5001

class MockSkychartServer:
    def __init__(self, host="127.0.0.1", port=0):
        self.host = host
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, port))
        self.port = self.server_sock.getsockname()[1]
        self.running = False
        self.thread = None

    def start(self):
        import threading
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
        import threading
        self.server_sock.listen(5)
        while self.running:
            try:
                conn, addr = self.server_sock.accept()
                t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                t.start()
            except:
                break

    def _handle_client(self, conn):
        try:
            conn.sendall(b"OK! Skychart Ready\r\n")
            buffer = bytearray()
            while self.running:
                data = conn.recv(1024)
                if not data:
                    break
                buffer.extend(data)
                while b"\r\n" in buffer:
                    line_idx = buffer.index(b"\r\n")
                    line = buffer[:line_idx].decode("utf-8").strip()
                    del buffer[:line_idx+2]
                    if not line:
                        continue
                    parts = line.split()
                    cmd = parts[0].upper()
                    response = b"OK\r\n"
                    if cmd == "GETSCOPERADEC":
                        response = b"OK! 10.0 30.0\r\n"
                    elif cmd == "CONNECTTELESCOPE":
                        response = b"OK\r\n"
                    elif cmd == "SLEW":
                        response = b"OK\r\n"
                    conn.sendall(response)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except:
                pass

class TestT1P2WithoutPlugin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if LIVE_TEST:
            print("\n*** RUNNING IN LIVE HARDWARE MODE (SKYCHART FLATPAK) ***")
            cls.server = None
            cls.connect_patcher = None
        else:
            print("\n*** RUNNING IN MOCK SERVER MODE ***")
            cls.server = MockSkychartServer()
            cls.server.start()
            time.sleep(0.2)

            cls.original_connect = socket.socket.connect

            def mock_connect(self_sock, address):
                host, port = address
                # Redirect default Skychart IP/port to local mock server
                if host == "127.0.0.1" and int(port) == 3292:
                    return cls.original_connect(self_sock, ("127.0.0.1", cls.server.port))
                return cls.original_connect(self_sock, address)

            cls.connect_patcher = patch.object(socket.socket, "connect", mock_connect)
            cls.connect_patcher.start()

    @classmethod
    def tearDownClass(cls):
        if cls.connect_patcher:
            cls.connect_patcher.stop()
        if cls.server:
            cls.server.stop()

    def test_t1p2_raw_commands_flow(self):
        # 1. Perform connection to Skychart on port 3292
        print("\n=== STEP 1: Perform Connection ===")
        skychart_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        skychart_sock.settimeout(5.0)
        skychart_sock.connect((SKYCHART_HOST, SKYCHART_PORT))
        greeting = skychart_sock.recv(1024)
        print(f"Connected to Skychart greeting: {greeting.decode().strip()}")
        print("Waiting 5 seconds...")
        time.sleep(5.0)

        # Connect telescope in Skychart first
        print("\n=== STEP 1.5: Connect Telescope in Skychart ===")
        skychart_sock.sendall(b"CONNECTTELESCOPE\r\n")
        conn_resp = skychart_sock.recv(4096).decode('utf-8').strip()
        print(f"Skychart CONNECTTELESCOPE response: {conn_resp}")
        print("Waiting 5 seconds...")
        time.sleep(5.0)

        # 2. Fetch telemetry
        print("\n=== STEP 2: Fetch Telemetry ===")
        skychart_sock.sendall(b"GETSCOPERADEC F\r\n")
        response = skychart_sock.recv(4096).decode('utf-8').strip()
        print(f"Skychart telemetry response: {response}")
        print("Waiting 5 seconds...")
        time.sleep(5.0)

        # 3. Turn on tracking
        print("\n=== STEP 3: Turn On Tracking ===")
        proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_sock.settimeout(5.0)
        proxy_sock.connect((PROXY_HOST, PROXY_PORT))
        print("Connected to serial proxy.")
        proxy_sock.sendall(b":RG#")
        response_on = proxy_sock.recv(1024)
        print(f"Serial proxy response (ON): {response_on.decode(errors='replace')}")
        proxy_sock.close()
        print("Waiting 5 seconds...")
        time.sleep(5.0)

        # 4. Slew to target
        print("\n=== STEP 4: Slew to Target ===")
        ra_hours = 279.23 / 15.0
        dec_deg = 38.78
        

        
        # Send slew command
        slew_cmd = f"SLEW {ra_hours} {dec_deg}\r\n"
        print(f"Sending Skychart slew command: {slew_cmd.strip()}")
        skychart_sock.sendall(slew_cmd.encode('utf-8'))
        slew_resp = skychart_sock.recv(4096).decode('utf-8').strip()
        print(f"Skychart SLEW response: {slew_resp}")
        print("Waiting 5 seconds...")
        time.sleep(5.0)

        # 5. Wait for 5 seconds (Step 5 itself)
        print("\n=== STEP 5: Wait for 5 Seconds ===")
        time.sleep(5.0)

        # 6. Turn off tracking
        print("\n=== STEP 6: Turn Off Tracking ===")
        proxy_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_sock.settimeout(5.0)
        proxy_sock.connect((PROXY_HOST, PROXY_PORT))
        proxy_sock.sendall(b":RS#")
        response_off = proxy_sock.recv(1024)
        print(f"Serial proxy response (OFF): {response_off.decode(errors='replace')}")
        proxy_sock.close()
        print("Waiting 5 seconds...")
        time.sleep(5.0)

        # 7. Disconnect
        print("\n=== STEP 7: Disconnect ===")
        skychart_sock.close()
        print("Disconnected. T1P2 sequential flow without plugin finished successfully.")
        print("Waiting 5 seconds...")
        time.sleep(5.0)

if __name__ == "__main__":
    unittest.main()

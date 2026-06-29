import os
import sys
import time
import socket
import threading
import unittest

# Add LCU root to path so imports work correctly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Plugins.telescope.T2P5.telnet_client import Telnet

def parse_sexagesimal(val_str: str) -> float:
    """
    Parses a sexagesimal string (e.g. '12:34:56.78' or '+34:12:05.2') or a simple float string.
    Returns float value (hours or degrees).
    """
    val_str = val_str.strip()
    if not val_str:
        return 0.0
    
    try:
        return float(val_str)
    except ValueError:
        pass
    
    import re
    parts = re.split(r'[:\s]', val_str)
    parts = [p for p in parts if p]
    
    if not parts:
        return 0.0
    
    try:
        sign = 1.0
        first_part = parts[0]
        if first_part.startswith('-'):
            sign = -1.0
            first_part = first_part[1:]
        elif first_part.startswith('+'):
            first_part = first_part[1:]
            
        h = float(first_part)
        m = float(parts[1]) if len(parts) > 1 else 0.0
        s = float(parts[2]) if len(parts) > 2 else 0.0
        
        return sign * (h + m / 60.0 + s / 3600.0)
    except Exception:
        return 0.0


class MockTelnetServer:
    def __init__(self, host="127.0.0.1", port=8888):
        self.host = host
        self.port = port
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.port = self.server_sock.getsockname()[1]
        self.running = False
        self.thread = None
        self.received_data = []
        self.sent_negotiations = []
        self.received_negotiations = []
        
        # Simulated telescope state
        self.target_ra = 0.0      # in hours
        self.target_dec = 0.0     # in degrees
        self.current_ra = 0.0     # in hours
        self.current_dec = 0.0    # in degrees
        self.is_tracking = False
        self.is_slewing = False
        self.lock = threading.Lock()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        try:
            self.server_sock.close()
        except Exception:
            pass
        if self.thread:
            self.thread.join(timeout=1.0)

    def _run(self):
        self.server_sock.listen(5)
        while self.running:
            try:
                conn, addr = self.server_sock.accept()
                t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                t.start()
            except Exception:
                break

    def _handle_client(self, conn):
        try:
            # Send welcome banner
            conn.sendall(b"Welcome to Mock Telescope Telnet Server\r\n")
            
            buffer = bytearray()
            while self.running:
                # Update client simulation steps
                with self.lock:
                    if self.is_slewing:
                        ra_diff = self.target_ra - self.current_ra
                        dec_diff = self.target_dec - self.current_dec
                        dist = (ra_diff**2 + dec_diff**2)**0.5
                        if dist < 0.05:
                            self.current_ra = self.target_ra
                            self.current_dec = self.target_dec
                            self.is_slewing = False
                        else:
                            self.current_ra += ra_diff * 0.5
                            self.current_dec += dec_diff * 0.5

                data = conn.recv(1024)
                if not data:
                    break
                
                # Check if we got any Telnet negotiation responses from client
                i = 0
                while i < len(data):
                    if data[i] == 255 and i + 2 < len(data):
                        iac = data[i:i+3]
                        self.received_negotiations.append(iac)
                        i += 3
                    else:
                        buffer.append(data[i])
                        i += 1
                
                # Process line-by-line
                while b"\r\n" in buffer:
                    line_idx = buffer.index(b"\r\n")
                    line = buffer[:line_idx].decode("utf-8").strip()
                    del buffer[:line_idx+2]
                    
                    if not line:
                        continue
                    
                    self.received_data.append(line)
                    parts = line.split()
                    cmd = parts[0].lower()
                    
                    response = b"\r\n"
                    if cmd == "targetra":
                        if len(parts) > 1:
                            with self.lock:
                                self.target_ra = float(parts[1])
                            response = f"targetra set to {parts[1]}\r\n".encode()
                    elif cmd == "targetdec":
                        if len(parts) > 1:
                            with self.lock:
                                self.target_dec = float(parts[1])
                            response = f"targetdec set to {parts[1]}\r\n".encode()
                    elif cmd == "track":
                        if len(parts) > 1:
                            with self.lock:
                                self.is_tracking = parts[1] == "1"
                            response = f"track set to {parts[1]}\r\n".encode()
                    elif cmd == "slew":
                        with self.lock:
                            self.is_slewing = True
                        response = b"slew initiated\r\n"
                    elif cmd == "stop":
                        with self.lock:
                            self.is_slewing = False
                        response = b"stop complete\r\n"
                    elif cmd == "do":
                        if len(parts) > 1 and parts[1] == "target":
                            import re
                            ra_val = 0.0
                            dec_val = 0.0
                            ra_match = re.search(r'ra=([^=]+?)(?:\s+dec=|$)', line)
                            dec_match = re.search(r'dec=([^=]+?)(?:\s+ra=|$)', line)
                            if ra_match:
                                ra_val = parse_sexagesimal(ra_match.group(1).strip())
                            if dec_match:
                                dec_val = parse_sexagesimal(dec_match.group(1).strip())
                            with self.lock:
                                self.target_ra = ra_val
                                self.target_dec = dec_val
                                self.is_slewing = True
                            response = b"slew initiated\r\n"
                        elif len(parts) > 1 and parts[1] == "track":
                            state_val = False
                            for p in parts[2:]:
                                if p.startswith("state="):
                                    state_val = (p.split("=")[1].lower() == "on")
                            with self.lock:
                                self.is_tracking = state_val
                            response = f"track set to {state_val}\r\n".encode()
                    elif cmd == "unalias":
                        response = b"unalias success\r\n"
                    elif cmd == "alias":
                        response = b"alias success\r\n"
                    elif cmd == "get":
                        if len(parts) > 1 and parts[1] == "tn_data":
                            with self.lock:
                                response = f"tn_data {time.time()} {self.target_ra} {self.target_dec} J2000 {self.current_ra} {self.current_dec}\r\n".encode()
                        elif len(parts) > 1 and parts[1] == "nispdatads":
                            with self.lock:
                                response = f"nispdatads {time.time()} 0.0 00:00:00 2026-06-15T10:00:00 45.0 180.0 {self.target_ra} {self.target_dec} J2000 {self.current_ra} {self.current_dec} 1.0 0.0 0 0 0 0 1 1 20.0 50.0 10.0 1013.0 5.0 90.0\r\n".encode()
                    elif cmd == "send_iac":
                        # Send IAC DO SUPPRESS-GO-AHEAD (255, 253, 3)
                        conn.sendall(bytes([255, 253, 3]))
                        self.sent_negotiations.append(bytes([255, 253, 3]))
                        response = b"IAC sent\r\n"
                        
                    conn.sendall(response)
                    
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


class TestTelnetClientWithMockServer(unittest.TestCase):
    def setUp(self):
        self.server = MockTelnetServer()
        self.server.start()
        time.sleep(0.1)
        self.client = Telnet(self.server.host, self.server.port, timeout=3)

    def tearDown(self):
        self.client.close()
        self.server.stop()

    def test_connection_and_banner(self):
        welcome = self.client.read_until(b"\r\n")
        self.assertIn(b"Welcome to Mock Telescope Telnet Server", welcome)

    def test_commands_and_responses(self):
        # Flush banner
        self.client.read_until(b"\r\n")
        
        # Test setting target RA and Dec
        self.client.write(b"targetra 10.5\r\n")
        resp = self.client.read_until(b"\r\n")
        self.assertIn(b"targetra set to 10.5", resp)
        self.assertEqual(self.server.target_ra, 10.5)

        self.client.write(b"targetdec -23.4\r\n")
        resp = self.client.read_until(b"\r\n")
        self.assertIn(b"targetdec set to -23.4", resp)
        self.assertEqual(self.server.target_dec, -23.4)

        # Test tracking
        self.client.write(b"track 1\r\n")
        resp = self.client.read_until(b"\r\n")
        self.assertIn(b"track set to 1", resp)
        self.assertTrue(self.server.is_tracking)

        # Test alias and telemetry query
        self.client.write(b"unalias tn_data\r\n")
        resp = self.client.read_until(b"\r\n")
        self.assertIn(b"unalias success", resp)

        self.client.write(b"alias tn_data targetra targetdec targetframe currentra currentdec\r\n")
        resp = self.client.read_until(b"\r\n")
        self.assertIn(b"alias success", resp)

        # Get telemetry
        self.client.write(b"get tn_data\r\n")
        resp = self.client.read_until(b"\r\n")
        self.assertIn(b"tn_data", resp)
        parts = resp.decode("utf-8").strip().split()
        self.assertEqual(parts[2], "10.5")
        self.assertEqual(parts[3], "-23.4")

    def test_slew_simulation(self):
        # Flush banner
        self.client.read_until(b"\r\n")

        self.client.write(b"targetra 5.0\r\n")
        self.client.read_until(b"\r\n")
        self.client.write(b"targetdec 10.0\r\n")
        self.client.read_until(b"\r\n")

        self.client.write(b"slew\r\n")
        resp = self.client.read_until(b"\r\n")
        self.assertIn(b"slew initiated", resp)
        self.assertTrue(self.server.is_slewing)

        # Wait a moment for slewing simulation steps
        time.sleep(0.5)
        self.client.write(b"get tn_data\r\n")
        resp = self.client.read_until(b"\r\n")
        parts = resp.decode("utf-8").strip().split()
        current_ra = float(parts[5])
        current_dec = float(parts[6])
        # Coordinates should have moved towards 5.0 and 10.0
        self.assertTrue(current_ra > 0.0)
        self.assertTrue(current_dec > 0.0)

    def test_telnet_iac_negotiation(self):
        # Flush banner
        self.client.read_until(b"\r\n")

        # Command server to send an IAC sequence
        self.client.write(b"send_iac\r\n")
        resp = self.client.read_until(b"\r\n")
        self.assertIn(b"IAC sent", resp)

        # Wait a moment to ensure response has been processed
        time.sleep(0.2)
        
        self.assertTrue(len(self.server.received_negotiations) > 0)
        # Expected negotiation response: IAC WONT SUPPRESS-GO-AHEAD (255, 252, 3)
        self.assertEqual(self.server.received_negotiations[0], bytes([255, 252, 3]))

if __name__ == "__main__":
    unittest.main()

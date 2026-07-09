import serial
import threading
import socket
import time
import logging
import argparse
from typing import Tuple, Optional

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("SerialProxy")

# Configurations
PHYSICAL_PORT = "COM5"
VIRTUAL_PORT = "COM11"  # Connected to COM10 (which Skychart uses)
BAUDRATE = 115200
STOPBITS = serial.STOPBITS_ONE
BYTESIZE = serial.EIGHTBITS
PARITY = serial.PARITY_NONE

TCP_HOST = "127.0.0.1"
TCP_PORT = 5001

# Synchronisation Mutex for physical port transactions
serial_lock = threading.Lock()

class MockSerialPort:
    """Simulates a physical serial port connected to a Meade LX200 mount."""
    def __init__(self):
        self.is_open = True
        self._in_buffer = bytearray()
        self._out_buffer = bytearray()
        
    def write(self, data: bytes):
        self._out_buffer.extend(data)
        self._process_commands()
        return len(data)
        
    def read(self, size: int = 1) -> bytes:
        # Simulate small transmission delay
        time.sleep(0.01)
        res = self._in_buffer[:size]
        del self._in_buffer[:size]
        return bytes(res)
        
    def reset_input_buffer(self):
        self._in_buffer.clear()
        
    def reset_output_buffer(self):
        self._out_buffer.clear()
        
    def flush(self):
        pass
        
    def close(self):
        self.is_open = False
        
    @property
    def in_waiting(self) -> int:
        return len(self._in_buffer)
        
    def _process_commands(self):
        # Meade command processing
        while b"\x06" in self._out_buffer:
            idx = self._out_buffer.index(b"\x06")
            self._in_buffer.extend(b"G#")
            del self._out_buffer[:idx+1]
            
        while b":" in self._out_buffer and b"#" in self._out_buffer:
            start = self._out_buffer.index(b":")
            end = self._out_buffer.index(b"#")
            if end > start:
                cmd = self._out_buffer[start:end+1]
                cmd_str = cmd.decode('ascii', errors='ignore')
                del self._out_buffer[:end+1]
                
                # Mock responses
                if cmd_str == ":GD#":
                    self._in_buffer.extend(b"+38*46:00#")
                elif cmd_str == ":GR#":
                    self._in_buffer.extend(b"18:36:54#")
                elif cmd_str in [":RG#", ":RS#"]:
                    self._in_buffer.extend(b"1")
                else:
                    self._in_buffer.extend(b"1")
            else:
                del self._out_buffer[:start]

class SerialProxy:
    def __init__(self, phys_port: str, virt_port: str, baud: int, tcp_host: str, tcp_port: int, mock_mount: bool = False):
        self.phys_port = phys_port
        self.virt_port = virt_port
        self.baud = baud
        self.tcp_host = tcp_host
        self.tcp_port = tcp_port
        self.mock_mount = mock_mount
        
        self.phys_ser: Optional[serial.Serial] = None
        self.virt_ser: Optional[serial.Serial] = None
        self.running = False
        self.virt_thread = None
        self.tcp_thread = None

    def connect_physical(self) -> bool:
        """Attempts to connect to the physical telescope mount."""
        if self.mock_mount:
            logger.info("Using simulated (MOCK) telescope mount responder.")
            self.phys_ser = MockSerialPort()
            return True
        try:
            self.phys_ser = serial.Serial(
                port=self.phys_port,
                baudrate=self.baud,
                bytesize=BYTESIZE,
                parity=PARITY,
                stopbits=STOPBITS,
                timeout=0.5
            )
            logger.info(f"Connected to physical mount on {self.phys_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to physical port {self.phys_port}: {e}")
            return False

    def connect_virtual(self) -> bool:
        """Attempts to connect to the virtual COM port endpoint."""
        try:
            self.virt_ser = serial.Serial(
                port=self.virt_port,
                baudrate=self.baud,
                bytesize=BYTESIZE,
                parity=PARITY,
                stopbits=STOPBITS,
                timeout=0.1
            )
            logger.info(f"Connected to virtual port loopback {self.virt_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to virtual port {self.virt_port}: {e}")
            return False

    def send_and_receive(self, cmd_bytes: bytes) -> bytes:
        """
        Sends a command to the physical serial port and waits for the response.
        Must be called while holding the serial_lock.
        """
        if not self.phys_ser or not self.phys_ser.is_open:
            logger.warning("Physical serial port not open. Attempting to reconnect...")
            if not self.connect_physical():
                return b""

        # Flush raw buffers to prevent cross-talk
        self.phys_ser.reset_input_buffer()
        self.phys_ser.reset_output_buffer()

        logger.info(f"[PHYS TX] -> {cmd_bytes}")
        self.phys_ser.write(cmd_bytes)
        self.phys_ser.flush()

        # Parse command to determine response type
        cmd_str = cmd_bytes.decode('ascii', errors='ignore').strip()
        response = b""
        
        # 1. ACK command
        if cmd_bytes == b"\x06":
            # Expect response ending with '#' (e.g., G#)
            response = self._read_until_hash()
        # 2. Queries or Syncs (starts with :G or :C)
        elif cmd_str.startswith(":G") or cmd_str.startswith(":C"):
            response = self._read_until_hash()
        # 3. Action commands (starts with :R, :M, :Q, etc.)
        else:
            # Expect single character (0 or 1)
            response = self.phys_ser.read(1)
            # If nothing returned immediately, check again after brief sleep
            if not response:
                time.sleep(0.05)
                if self.phys_ser.in_waiting > 0:
                    response = self.phys_ser.read(1)

        logger.info(f"[PHYS RX] <- {response}")
        return response

    def _read_until_hash(self, timeout_sec: float = 1.0) -> bytes:
        """Helper to read serial stream until a '#' character is found."""
        buffer = bytearray()
        start_time = time.time()
        while time.time() - start_time < timeout_sec:
            char = self.phys_ser.read(1)
            if not char:
                # read timeout occurred
                break
            buffer.extend(char)
            if char == b'#':
                break
        return bytes(buffer)

    def run_virtual_listener(self):
        """Thread to listen to incoming commands from Skychart on the virtual port."""
        buffer = bytearray()
        while self.running:
            try:
                if not self.virt_ser or not self.virt_ser.is_open:
                    time.sleep(1.0)
                    self.connect_virtual()
                    continue

                # Read all available bytes from virtual serial port
                if self.virt_ser.in_waiting > 0:
                    char = self.virt_ser.read(1)
                    if not char:
                        continue
                    buffer.extend(char)

                    # Check for completed commands
                    # Case A: ACK command (0x06)
                    if b"\x06" in buffer:
                        idx = buffer.index(b"\x06")
                        cmd = bytes([0x06])
                        # Process command
                        with serial_lock:
                            resp = self.send_and_receive(cmd)
                            self.virt_ser.write(resp)
                            self.virt_ser.flush()
                        del buffer[:idx+1]
                    
                    # Case B: Standard LX200 command (:command#)
                    elif b":" in buffer and b"#" in buffer:
                        start_idx = buffer.index(b":")
                        end_idx = buffer.index(b"#")
                        if end_idx > start_idx:
                            cmd = bytes(buffer[start_idx : end_idx+1])
                            # Process command
                            with serial_lock:
                                resp = self.send_and_receive(cmd)
                                self.virt_ser.write(resp)
                                self.virt_ser.flush()
                            del buffer[:end_idx+1]
                        else:
                            # Malformed: '#' came before ':'. Discard prior to ':'
                            del buffer[:start_idx]
                else:
                    time.sleep(0.005)
            except Exception as e:
                logger.error(f"Error in virtual port listener: {e}")
                time.sleep(1.0)

    def run_tcp_server(self):
        """Thread that listens on TCP port 5001 for injection commands from LCU."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind((self.tcp_host, self.tcp_port))
            server.listen(5)
            logger.info(f"Command injection TCP server listening on {self.tcp_host}:{self.tcp_port}")
        except Exception as e:
            logger.critical(f"Failed to bind TCP server: {e}")
            return

        while self.running:
            try:
                server.settimeout(1.0)
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue

                t = threading.Thread(target=self._handle_tcp_client, args=(conn, addr), daemon=True)
                t.start()
            except Exception as e:
                logger.error(f"Error in TCP server loop: {e}")

    def _handle_tcp_client(self, conn: socket.socket, addr: Tuple[str, int]):
        logger.info(f"TCP client connected from LCU: {addr}")
        conn.settimeout(3.0)
        try:
            data = conn.recv(1024).decode('ascii', errors='ignore').strip()
            if not data:
                return

            # Normalize command format (add ':' and '#' if not present)
            if data == "ACK" or data == "\x06":
                cmd_bytes = b"\x06"
            else:
                cmd_str = data
                if not cmd_str.startswith(':'):
                    cmd_str = ':' + cmd_str
                if not cmd_str.endswith('#'):
                    cmd_str = cmd_str + '#'
                cmd_bytes = cmd_str.encode('ascii')

            logger.info(f"[INJECT COMMAND] -> {cmd_bytes.decode()}")
            
            # Execute with lock
            with serial_lock:
                response = self.send_and_receive(cmd_bytes)

            logger.info(f"[INJECT RESPONSE] <- {response}")
            conn.sendall(response)
        except Exception as e:
            logger.error(f"Error handling LCU client {addr}: {e}")
        finally:
            conn.close()

    def start(self):
        self.running = True
        
        # Connect to physical port first
        self.connect_physical()
        # Connect to virtual port next
        self.connect_virtual()

        # Start threads
        self.virt_thread = threading.Thread(target=self.run_virtual_listener, daemon=True)
        self.tcp_thread = threading.Thread(target=self.run_tcp_server, daemon=True)
        
        self.virt_thread.start()
        self.tcp_thread.start()

        logger.info("Serial Proxy fully started. Press Ctrl+C to stop.")
        try:
            while self.running:
                # Check health of ports and reconnect if dead
                with serial_lock:
                    if self.phys_ser and not self.phys_ser.is_open:
                        logger.warning("Physical serial disconnected. Reconnecting...")
                        self.connect_physical()
                time.sleep(2.0)
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.stop()

    def stop(self):
        self.running = False
        if self.phys_ser:
            try:
                self.phys_ser.close()
            except:
                pass
        if self.virt_ser:
            try:
                self.virt_ser.close()
            except:
                pass
        logger.info("Proxy stopped.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meade LX200 Protocol-Aware Serial Sharing Proxy")
    parser.add_argument("--phys-port", default=PHYSICAL_PORT, help=f"Physical COM port connected to mount (default: {PHYSICAL_PORT})")
    parser.add_argument("--virt-port", default=VIRTUAL_PORT, help=f"Virtual COM port connected to proxy side (default: {VIRTUAL_PORT})")
    parser.add_argument("--baud", type=int, default=BAUDRATE, help=f"Baud rate (default: {BAUDRATE})")
    parser.add_argument("--tcp-host", default=TCP_HOST, help=f"Host to bind the TCP server (default: {TCP_HOST})")
    parser.add_argument("--tcp-port", type=int, default=TCP_PORT, help=f"Port for the TCP server (default: {TCP_PORT})")
    parser.add_argument("--mock-mount", action="store_true", help="Run with a mock telescope mount responder (offline mode)")
    
    args = parser.parse_args()
    
    proxy = SerialProxy(
        phys_port=args.phys_port,
        virt_port=args.virt_port,
        baud=args.baud,
        tcp_host=args.tcp_host,
        tcp_port=args.tcp_port,
        mock_mount=args.mock_mount
    )
    proxy.start()

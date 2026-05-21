import threading
import time
from telnetlib import Telnet
from typing import Dict, Any, Optional
from Plugins.telescope.T1P2.telescope_telemetry import TelescopeTelemetry
from Plugins.telescope.T1P2.errors import TelescopeConnectionError, TelescopeSlewError, TelescopeTrackingError, TelescopeStopError

class TelescopeDriver:
    """
    Low-level driver for controlling a telescope via Telnet (PWI/SiTech protocol).
    Handles atomic control commands and delegates monitoring to TelescopeTelemetry.
    """
    
    def __init__(self, host: str = "172.16.20.221", port: int = 7281):
        self.host = host
        self.port = port
        self.tn: Optional[Telnet] = None
        self.lock = threading.Lock()
        
        # Telemetry Handler
        self.telemetry = TelescopeTelemetry()
        
        # Internal State (non-telemetry)
        self.is_connected = False

    def connect(self) -> bool:
        """Establishes connection and starts telemetry monitoring."""
        try:
            with self.lock:
                self.tn = Telnet(self.host, str(self.port), timeout=5)
                self.telemetry.tn = self.tn
                self.telemetry.start()
                
            self.is_connected = True
            print(f"[DRIVER] Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            self.is_connected = False
            raise TelescopeConnectionError(f"Connection failed: {e}") from e

    def disconnect(self):
        """Shut down monitoring and close connection."""
        self.telemetry.stop()
        if self.tn:
            try:
                self.tn.close()
            except:
                pass
        self.is_connected = False

    def slew_to(self, ra_deg: float, dec_deg: float):
        """Sets target coordinates and begins slew."""
        if not self.is_connected:
            raise TelescopeConnectionError("Cannot slew: Telescope is not connected.")
        
        ra_hours = ra_deg / 15.0
        try:
            with self.lock:
                self.tn.write(f"targetra {ra_hours}\r\n".encode())
                self.tn.write(f"targetdec {dec_deg}\r\n".encode())
                self.tn.write(b"slew\r\n")
            print(f"[DRIVER] Slewing to RA={ra_deg}, Dec={dec_deg}")
        except Exception as e:
            raise TelescopeSlewError(f"Slew failed: {e}") from e

    def stop(self):
        """Immediately stops all mount movement."""
        if not self.is_connected:
            raise TelescopeConnectionError("Cannot stop: Telescope is not connected.")
        try:
            with self.lock:
                self.tn.write(b"stop\r\n")
            print("[DRIVER] Emergency stop command sent.")
        except Exception as e:
            raise TelescopeStopError(f"Stop failed: {e}") from e

    def set_tracking(self, enabled: bool):
        """Enable or disable mount tracking."""
        if not self.is_connected:
            raise TelescopeConnectionError("Cannot set tracking: Telescope is not connected.")
        val = 1 if enabled else 0
        try:
            with self.lock:
                self.tn.write(f"track {val}\r\n".encode())
            self.telemetry.is_tracking = enabled
            print(f"[DRIVER] Tracking set to: {enabled}")
        except Exception as e:
            raise TelescopeTrackingError(f"Set tracking failed: {e}") from e

    def get_status(self) -> Dict[str, Any]:
        """Returns a snapshot of the current state, combining telemetry and local state."""
        telemetry_status = self.telemetry.get_telemetry()
        return {
            **telemetry_status,
            "connected": self.is_connected
        }

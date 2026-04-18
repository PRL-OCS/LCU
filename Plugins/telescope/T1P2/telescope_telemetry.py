import threading
import time
from telnetlib import Telnet
from typing import Optional, Dict, Any

class TelescopeTelemetry:
    """
    Handles background monitoring of telescope telemetry via Telnet.
    Separates the parsing and state tracking from the main driver.
    """
    def __init__(self, tn: Optional[Telnet] = None):
        self.tn = tn
        self.lock = threading.Lock()
        
        # Telemetry State
        self.current_ra = 0.0
        self.current_dec = 0.0
        self.target_ra = 0.0
        self.target_dec = 0.0
        self.is_slewing = False
        self.is_tracking = False
        
        self.monitor_thread = None
        self.running = False

    def setup_monitoring(self):
        """Sets up the 'monitor' command aliases on the mount."""
        if not self.tn:
            return
        
        try:
            # Setup: Clear old aliases and set up the 'monitor' command
            self.tn.write(b"unalias tndata_target\r\n")
            self.tn.read_until(b"\r\n", timeout=2)
            
            self.tn.write(b"alias tndata_target targetra targetdec targetframe currentra currentdec\r\n")
            self.tn.read_until(b"\r\n", timeout=2)
            
            self.tn.write(b"monitor tndata_target interval=1000\r\n")
        except Exception as e:
            print(f"[TELEMETRY ERROR] Failed to setup monitoring: {e}")

    def start(self):
        """Starts the background telemetry monitoring thread."""
        if self.running or not self.tn:
            return+
        
        self.setup_monitoring()
        self.running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop(self):
        """Stops the telemetry monitoring thread."""
        self.running = False
        # We don't join here to avoid blocking the main thread if the telnet read is stuck
        # But we could if needed.

    def _monitor_loop(self):
        """Background thread to parse monitoring data."""
        while self.running:
            try:
                if not self.tn:
                    time.sleep(1)
                    continue

                line = self.tn.read_until(b"\r\n", timeout=5)
                if not line:
                    continue
                
                parts = line.decode("utf-8").strip().split(" ")
                
                # Expected format based on alias:
                # [0] tndata_target [1] timestamp [2] targetra [3] targetdec [4] targetframe [5] currentra [6] currentdec
                if len(parts) >= 7:
                    # In test_telnet_telescope.py mapping:
                    # parts[3] -> targetra (hours)
                    # parts[4] -> targetdec
                    # parts[6] -> currentra (hours)
                    # parts[7] -> currentdec
                    
                    self.target_ra = float(parts[3]) * 15.0
                    self.target_dec = float(parts[4])
                    self.current_ra = float(parts[6]) * 15.0
                    self.current_dec = float(parts[7])
                    
                    # Heuristic for slewing
                    dist = ((self.current_ra - self.target_ra)**2 + (self.current_dec - self.target_dec)**2)**0.5
                    self.is_slewing = dist > 0.01  # 0.01 degree tolerance
                    
            except Exception as e:
                if self.running:
                    print(f"[TELEMETRY ERROR] Monitor loop error: {e}")
                    time.sleep(1)

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns a snapshot of the current coordinates and slewing status."""
        return {
            "ra": self.current_ra,
            "dec": self.current_dec,
            "target_ra": self.target_ra,
            "target_dec": self.target_dec,
            "slewing": self.is_slewing,
            "tracking": self.is_tracking
        }

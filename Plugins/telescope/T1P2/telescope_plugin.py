from typing import List
from Plugins.base_telescope import TelescopePlugin
from core.communications.schemas import Target
from Plugins.telescope.T1P2.telescope_driver import TelescopeDriver
from Plugins.telescope.T1P2.errors import TelescopeConnectionError, TelescopeSlewError, TelescopeTrackingError, TelescopeStopError

class DefaultTelescope(TelescopePlugin):
    """
    A concrete implementation of a telescope plugin.
    This one uses the TelnetTelescopeDriver for hardware communication.
    """
    
    def __init__(self, telescope_id: str = "T1P2"):
        super().__init__(telescope_id)
        print(f"[PLUGIN-TEL] {self.telescope_id} initialized.")
        
        # Initialize the hardware driver
        self.driver = TelescopeDriver()
        try:
            if self.driver.connect():
                print(f"[PLUGIN-TEL] {self.telescope_id} successfully connected to hardware.")
        except TelescopeConnectionError as e:
            print(f"[PLUGIN-TEL ERROR] {self.telescope_id} failed to connect to hardware: {e}")
            raise

        # Load from disk on startup if a cache exists
        self.load_from_disk()

    def receive_schedule(self, targets: List[Target]):
        # Custom logic before or after the base behavior
        super().receive_schedule(targets)
        
        for i, target in enumerate(self.targets):
            print(f"  {i+1}. [TEL-TARGET] ID: {target.configuration_id} | Name: {target.name} | RA: {target.ra}")

    def start_schedule(self, target: Target):
        """
        Sets the target and begins slewing using the driver.
        """
        print(f"[PLUGIN-TEL] {self.telescope_id} starting schedule for {target.name}")
        self.driver.slew_to(target.ra, target.dec)
        self.driver.set_tracking(True)

    def force_stop(self):
        """
        Emergency stop via driver.
        """
        print(f"[PLUGIN-TEL] {self.telescope_id} FORCE STOP called.")
        self.driver.stop()

    def pause(self):
        """
        Graceful pause (stops movement).
        """
        print(f"[PLUGIN-TEL] {self.telescope_id} PAUSE called.")
        self.driver.stop()

    def get_current_telemetry(self) -> dict:
        """
        Returns hardware status from the driver merged with plugin-level metadata.
        """
        driver_status = self.driver.get_status()
        
        # Update plugin base state variables from driver
        self.current_ra = driver_status["ra"]
        self.current_dec = driver_status["dec"]
        self.is_connected = driver_status["connected"]
        self.is_tracking = driver_status["tracking"]
        self.is_slewing = driver_status["slewing"]

        return {
            "telescope_id": self.telescope_id,
            **driver_status,
            "dome": self.dome_status,
            "guiding": self.is_guiding
        }



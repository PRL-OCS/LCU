class TelescopeError(Exception):
    """Base exception class for all telescope plugin errors."""
    pass

class TelescopeConnectionError(TelescopeError):
    """Raised when there is an issue establishing or maintaining connection with the hardware."""
    pass

class TelescopeSlewError(TelescopeError):
    """Raised when a slew command fails or cannot be executed."""
    pass

class TelescopeTrackingError(TelescopeError):
    """Raised when setting tracking state fails."""
    pass

class TelescopeStopError(TelescopeError):
    """Raised when emergency stop command fails."""
    pass

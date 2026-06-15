import logging
import sys
import collections
from pathlib import Path

recent_logs = collections.deque(maxlen=50)

class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            recent_logs.append(msg)
        except Exception:
            self.handleError(record)

# Create logs directory if it doesn't exist
LOG_DIR = Path("storage/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "lcu.log"

def setup_logger(name: str = "LCU") -> logging.Logger:
    """
    Configures and returns a centralized logger for the LCU.
    Outputs to both Console (stdout) and a rolling log file.
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers if setup_logger is called multiple times
    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG)

    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File Handler
    file_handler = logging.FileHandler(LOG_FILE)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    
    # Memory Handler for UI
    memory_handler = MemoryLogHandler()
    memory_handler.setLevel(logging.INFO)
    memory_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(memory_handler)

    return logger

# Global instance for easy import
logger = setup_logger()

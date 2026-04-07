import os
import time
import asyncio
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class NewFileHandler(FileSystemEventHandler):
    """
    Custom event handler that filters for specific science extensions
    and only triggers on file creation.
    """
    def __init__(self, callback: Callable[[str], None], extensions: tuple):
        super().__init__()
        self.callback = callback
        self.extensions = extensions

    def on_created(self, event):
        # We only care about file creation, not directories
        if event.is_directory:
            return
            
        filename = os.path.basename(event.src_path)
        if filename.lower().endswith(self.extensions):
            self.callback(event.src_path)

class FileWatchdog:
    def __init__(self, watch_dir: str = "storage/cache"):
        self.watch_dir = Path(watch_dir)
        self.extensions = (".fits", ".fit", ".fits.gz", ".fits.fz")
        
        # Ensure the directory exists
        self.watch_dir.mkdir(parents=True, exist_ok=True)
        
        self.observer: Optional[Observer] = None
        self.handler = NewFileHandler(self._handle_new_file_event, self.extensions)

    def initialize(self):
        """
        Record existing files to avoid double-processing, and prepare the observer.
        """
        print(f"[WATCHDOG] Initializing library-based watcher for {self.watch_dir}...")
        # (Optional: You could perform a catch-up scan here if needed)
        pass

    def start(self):
        """
        Starts the watchdog observer in a background thread.
        """
        if self.observer is None:
            self.observer = Observer()
            self.observer.schedule(self.handler, str(self.watch_dir), recursive=False)
            self.observer.start()
            print(f"[WATCHDOG] Event-driven monitoring started (Watchdog Library).")

    def stop(self):
        """
        Stops the observer.
        """
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def _handle_new_file_event(self, file_path: str):
        """
        Triggered when the watchdog library detects a 'created' event.
        """
        filename = os.path.basename(file_path)
        print("\n" + "*"*50)
        print(f"[DATA DETECTED] New science file found: {filename}")
        print(f"[WATCHDOG] Library Event: Created | Path: {file_path}")
        print("*"*50 + "\n")
        
        # TODO: Link to IngestionManager or Orchestrator callback here
        # self.orchestrator.on_data_received(file_path)

    async def run_forever(self):
        """
        Async wrapper to keep the task alive if the orchestrator manages it as a task.
        Since Watchdog runs in its own thread, we just need to keep this coroutine alive.
        """
        self.start()
        try:
            while True:
                # Keep the async task alive
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.stop()

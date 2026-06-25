import asyncio
import json
import os
import httpx
from pathlib import Path
from datetime import datetime, timezone
from core.logging_config import logger
from core.communications.schemas import ScheduleSchema

class IngestionManager:
    """
    Manages asynchronous uploading of FITS files to the Pramana Science Archive.
    Maintains a persistent queue to survive crashes and retries failed uploads.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, storage_dir: str = "storage"):
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        self.storage_dir = Path(storage_dir)
        self.queue_file = self.storage_dir / "ingestion_queue.json"
        self.queue = []
        self._running = False
        self._worker_task = None
        self._lock = asyncio.Lock()
        
        self.archive_url = os.environ.get("ARCHIVE_API_URL", "http://localhost:9500").rstrip('/')
        self.api_token = os.environ.get("PRAMANA_API_TOKEN", "")
        
        self.load_queue()
        self._initialized = True

    def load_queue(self):
        if self.queue_file.exists():
            try:
                with open(self.queue_file, "r") as f:
                    self.queue = json.load(f)
                logger.info(f"[IngestionManager] Loaded {len(self.queue)} items from persistent queue.")
            except Exception as e:
                logger.error(f"[IngestionManager] Failed to load queue: {e}")
                self.queue = []
        else:
            self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def save_queue(self):
        async with self._lock:
            try:
                with open(self.queue_file, "w") as f:
                    json.dump(self.queue, f, indent=4)
            except Exception as e:
                logger.error(f"[IngestionManager] Failed to save queue: {e}")

    async def enqueue(self, file_path: str, obs_dict: dict, config_id: int, telemetry: dict):
        """
        Adds a FITS file to the ingestion queue. Returns immediately.
        Note: We serialize obs_dict because we persist it to JSON.
        """
        job = {
            "id": f"job_{int(datetime.now(timezone.utc).timestamp())}_{os.path.basename(file_path)}",
            "file_path": file_path,
            "obs_dict": obs_dict,
            "config_id": config_id,
            "telemetry": telemetry,
            "retries": 0,
            "status": "pending",
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        
        async with self._lock:
            self.queue.append(job)
        
        await self.save_queue()
        logger.info(f"[IngestionManager] Enqueued {file_path} for ingestion.")

    def start(self):
        self._running = True
        if not self._worker_task or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    def stop(self):
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()

    def _generate_headers(self, obs: ScheduleSchema, config_id: int, telemetry: dict) -> dict:
        """
        Synthesizes the FITS headers from the LCU's available context.
        """
        headers = {}
        
        # 1. Base Observation Info
        headers["PROPID"] = obs.proposal
        headers["TITLE"] = obs.name
        headers["PI_NAME"] = obs.submitter
        headers["ORIGIN"] = obs.site
        headers["TELESCOP"] = obs.telescope
        headers["BLKUID"] = obs.id
        headers["REQNUM"] = obs.request.id
        headers["TRACKNUM"] = obs.request_group_id
        headers["TEL_OPRT"] = "LCU Automated System"
        
        # 2. Timing
        headers["DATE-OBS"] = obs.end.isoformat() if obs.end else datetime.now(timezone.utc).isoformat()
        headers["UTSTART"] = obs.start.isoformat() if obs.start else datetime.now(timezone.utc).isoformat()
        headers["UTSTOP"] = obs.end.isoformat() if obs.end else datetime.now(timezone.utc).isoformat()
        
        # 3. Active Configuration & Target
        active_config = None
        for config in obs.request.configurations:
            if getattr(config, 'configuration_status', None) == config_id or config.id == config_id:
                active_config = config
                break
                
        if active_config:
            headers["CONFTYPE"] = active_config.type
            headers["OBJECT"] = active_config.target.name
            headers["TRGALPH"] = active_config.target.ra
            headers["TRGDELT"] = active_config.target.dec
            headers["EPOCH"] = active_config.target.epoch
            headers["INSTRUME"] = active_config.instrument_type
            
            # Additional params mapped
            for key, val in active_config.extra_params.items():
                headers[key.upper()[:8]] = val
                
            if active_config.instrument_configs:
                inst_cfg = active_config.instrument_configs[0]
                headers["EXPOSURE"] = inst_cfg.exposure_time
                for key, val in inst_cfg.extra_params.items():
                    headers[key.upper()[:8]] = val
                for key, val in inst_cfg.optical_elements.items():
                    if val:
                        headers[key.upper()[:8]] = val
                        
        # 4. Telemetry Overlay
        headers["RA"] = telemetry.get("current_ra", headers.get("TRGALPH", 0.0))
        headers["DEC"] = telemetry.get("current_dec", headers.get("TRGDELT", 0.0))
        
        return headers

    async def _worker_loop(self):
        logger.info("[IngestionManager] Background worker started.")
        while self._running:
            try:
                # Find the next pending job that hasn't exceeded retries
                # We process them sequentially.
                job_to_process = None
                async with self._lock:
                    for job in self.queue:
                        if job["status"] == "pending" and job["retries"] < 5:
                            job_to_process = job
                            break
                            
                if not job_to_process:
                    await asyncio.sleep(5)
                    continue

                logger.info(f"[IngestionManager] Processing job {job_to_process['id']}")
                file_path = job_to_process["file_path"]
                
                if not os.path.exists(file_path):
                    logger.error(f"[IngestionManager] File missing: {file_path}. Dropping job.")
                    async with self._lock:
                        self.queue.remove(job_to_process)
                    await self.save_queue()
                    continue

                # Parse the dict back into Pydantic models to easily navigate
                try:
                    obs_model = ScheduleSchema.model_validate(job_to_process["obs_dict"])
                except Exception as e:
                    logger.error(f"[IngestionManager] Failed to validate schema for job {job_to_process['id']}: {e}")
                    async with self._lock:
                        self.queue.remove(job_to_process)
                    await self.save_queue()
                    continue

                headers = self._generate_headers(obs_model, job_to_process["config_id"], job_to_process["telemetry"])
                
                # Upload logic
                success = await self._upload_to_archive(file_path, headers)
                
                if success:
                    logger.info(f"[IngestionManager] Successfully ingested {file_path}. Removing local copy.")
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        logger.warning(f"[IngestionManager] Could not delete {file_path}: {e}")
                        
                    async with self._lock:
                        if job_to_process in self.queue:
                            self.queue.remove(job_to_process)
                    await self.save_queue()
                else:
                    async with self._lock:
                        job_to_process["retries"] += 1
                        if job_to_process["retries"] >= 5:
                            job_to_process["status"] = "failed"
                            logger.error(f"[IngestionManager] Job {job_to_process['id']} permanently failed.")
                    await self.save_queue()
                    # Backoff before trying the next
                    await asyncio.sleep(10 * job_to_process["retries"])

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[IngestionManager] Worker loop error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _upload_to_archive(self, file_path: str, headers: dict) -> bool:
        """
        Performs the multipart POST to Pramana.
        """
        url = f"{self.archive_url}/pramana_ingest/"
        
        auth_headers = {}
        if self.api_token:
            auth_headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            async with httpx.AsyncClient() as client:
                with open(file_path, "rb") as f:
                    files = {'file': (os.path.basename(file_path), f, 'image/fits')}
                    data = {'headers': json.dumps(headers)}
                    
                    response = await client.post(
                        url,
                        headers=auth_headers,
                        files=files,
                        data=data,
                        timeout=120.0  # Large files may take time
                    )
                    
                    if response.status_code in (200, 201):
                        return True
                    else:
                        logger.error(f"[IngestionManager] Upload failed. Code: {response.status_code}. Response: {response.text}")
                        return False
        except Exception as e:
            logger.error(f"[IngestionManager] Network/upload error: {e}")
            return False

# Global instance
ingestion_manager = IngestionManager()

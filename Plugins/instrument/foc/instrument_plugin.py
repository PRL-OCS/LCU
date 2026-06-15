"""
FOC Camera Instrument Plugin
Drives the Andor camera via the FOC SDK REST API server (sdk_api_server.py).

The PluginManager auto-discovers this class because it lives under
Plugins/instrument/ and extends InstrumentPlugin.

Schedule flow:
  ScheduleCoordinator -> receive_schedule(List[ScheduleSchema])
  TelescopeExecutor   -> get_configuration(config_status_id) -> configure() -> expose()
"""

import asyncio
import requests
from typing import List, Optional, Dict, Any
from pathlib import Path

from Plugins.base_instrument import InstrumentPlugin
from core.communications.schemas import Configuration, ScheduleSchema
from core.logging_config import logger


# ─── Filter-name → wheel-position mapping (customise for your wheel) ───
FILTER_MAP: Dict[str, int] = {
    "luminance": 1, "L": 1,
    "red": 2,       "R": 2,
    "green": 3,     "G": 3,
    "blue": 4,      "B": 4,
    "h-alpha": 5,   "Ha": 5,
}


class FOCCameraPlugin(InstrumentPlugin):
    """
    Concrete instrument plugin for the FOC / Andor CCD camera.

    Communicates with the REST API server (sdk_api_server.py) which in turn
    manages a persistent CLI subprocess that talks to the Andor SDK.

    Default instrument_name = "FOC" — this is the key that the
    ScheduleCoordinator uses to route observations to this plugin
    (matched against Configuration.instrument_type in the schedule).
    """

    def __init__(
        self,
        instrument_name: str = "FOC",
        api_url: str = "http://127.0.0.1:8000",
    ):
        super().__init__(instrument_name)
        self.api_url = api_url.rstrip("/")
        self.output_dir = Path("storage/cache")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Internal state mirror (updated from API responses)
        self._camera_state: Dict[str, Any] = {}

        logger.info(
            f"[{self.instrument_name}] Plugin initialised. "
            f"Target API: {self.api_url}"
        )

        # Load any persisted observation cache from disk
        self.load_from_disk()

        # Try to connect to the camera on startup
        self._startup_connect()

    # ─────────────────────────────────────────────────────────
    # Startup helpers
    # ─────────────────────────────────────────────────────────
    def _startup_connect(self):
        """Attempt to connect to the camera API server at boot time."""
        try:
            health = requests.get(f"{self.api_url}/", timeout=5).json()
            cli_ok = health.get("data", {}).get("cli_running", False)
            if not cli_ok:
                msg = f"[{self.instrument_name}] API server reachable but CLI subprocess is NOT running."
                logger.error(msg)
                raise ConnectionError(msg)
        except requests.exceptions.RequestException as e:
            msg = f"[{self.instrument_name}] API server not reachable at {self.api_url}. Is it running?"
            logger.error(msg)
            raise ConnectionError(msg) from e

        resp = self._post_command("connect")
        if resp and resp.get("success"):
            mode = resp.get("data", {}).get("mode", "unknown")
            logger.info(
                f"[{self.instrument_name}] Camera connected "
                f"(mode: {mode})."
            )
        else:
            err = resp.get('error') if resp else 'no response'
            msg = f"[{self.instrument_name}] Camera connect failed: {err}"
            logger.error(msg)
            raise ConnectionError(msg)

    # ─────────────────────────────────────────────────────────
    # Low-level API helpers
    # ─────────────────────────────────────────────────────────
    def _post_command(
        self, cmd: str, params: Optional[dict] = None, timeout: float = 30
    ) -> Optional[dict]:
        """Synchronous POST to /api/command. Returns parsed JSON or None."""
        payload = {"command": cmd, "params": params or {}}
        try:
            resp = requests.post(
                f"{self.api_url}/api/command",
                json=payload,
                timeout=timeout,
            )
            return resp.json()
        except Exception as e:
            logger.error(
                f"[{self.instrument_name}] HTTP error on '{cmd}': {e}"
            )
            return None

    async def send_command(
        self,
        cmd: str,
        params: Optional[dict] = None,
        timeout: float = 30,
    ) -> dict:
        """
        Async wrapper around _post_command.
        Runs the blocking request in a thread so we don't stall the event loop.
        """
        data = await asyncio.to_thread(
            self._post_command, cmd, params, timeout
        )
        if data is None:
            data = {"success": False, "error": "No response from API server"}

        if data.get("success"):
            logger.info(
                f"[{self.instrument_name}] {cmd} -> {data.get('message')}"
            )
        else:
            logger.error(
                f"[{self.instrument_name}] {cmd} FAILED -> "
                f"{data.get('error')}"
            )
        return data

    # ─────────────────────────────────────────────────────────
    # Schedule ingestion  (called by ScheduleCoordinator)
    # ─────────────────────────────────────────────────────────
    def receive_schedule(self, observations: List[ScheduleSchema]):
        """
        Called by the ScheduleCoordinator with the full ScheduleSchema
        envelopes that belong to this instrument.
        Stores them and persists to disk.
        """
        self.observations = observations
        logger.info(
            f"[{self.instrument_name}] Received {len(observations)} "
            f"observation(s)."
        )
        self.save_to_disk()

        # Debug print
        for i, obs in enumerate(observations):
            for j, cfg in enumerate(obs.request.configurations):
                for k, ic in enumerate(cfg.instrument_configs):
                    filt = (
                        ic.optical_elements.get("filter")
                        or ic.optical_elements.get("Filter")
                        or "—"
                    )
                    logger.debug(
                        f"  {i+1}.{j+1}.{k+1} [FOC] "
                        f"Filter={filt} | Exp={ic.exposure_time}s | "
                        f"Count={ic.exposure_count} | "
                        f"Mode={cfg.type}"
                    )

    # ─────────────────────────────────────────────────────────
    # configure()   (called by TelescopeExecutor)
    # ─────────────────────────────────────────────────────────
    async def configure(self, config: Configuration):
        """
        Apply all hardware settings before the exposure starts:
          - filter wheel position
          - binning
          - subframe / ROI
          - cooling target
          - preview / dark / 8-bit / amplifier modes
          - gain / offset
        """
        logger.info(
            f"[{self.instrument_name}] Configuring for "
            f"config id={config.id} …"
        )

        for ic in config.instrument_configs:

            # ── 1. Filter Wheel ──────────────────────────────
            filter_val = (
                ic.optical_elements.get("filter")
                or ic.optical_elements.get("Filter")
            )
            if filter_val is not None:
                pos = self._resolve_filter_position(filter_val)
                if pos is not None:
                    await self.send_command(
                        "set_filter", {"position": pos}
                    )

            # ── 2. Binning ───────────────────────────────────
            binning = ic.extra_params.get("binning")
            if binning is not None:
                bx, by = self._parse_binning(binning)
                if bx and by:
                    await self.send_command(
                        "set_bin", {"x": bx, "y": by}
                    )

            # ── 3. Subframe / ROI ────────────────────────────
            if "subframe_w" in ic.extra_params and "subframe_h" in ic.extra_params:
                await self.send_command("set_subframe", {
                    "x": int(ic.extra_params.get("subframe_x", 0)),
                    "y": int(ic.extra_params.get("subframe_y", 0)),
                    "w": int(ic.extra_params["subframe_w"]),
                    "h": int(ic.extra_params["subframe_h"]),
                })

            # ── 4. Cooling ───────────────────────────────────
            cooling = ic.extra_params.get("cooling")
            if cooling is not None:
                try:
                    await self.send_command(
                        "set_cooling",
                        {"temperature": float(cooling)},
                    )
                except (ValueError, TypeError):
                    logger.error(
                        f"[{self.instrument_name}] Invalid cooling "
                        f"value: {cooling}"
                    )

            # ── 5. Preview / Dark / 8-bit / Amplifier ────────
            for key, cmd in [
                ("preview",   "set_preview"),
                ("dark_mode", "set_dark_mode"),
                ("eight_bit", "set_eight_bit"),
                ("amplifier", "set_amplifier"),
            ]:
                if key in ic.extra_params:
                    await self.send_command(
                        cmd, {"enable": bool(ic.extra_params[key])}
                    )

            # ── 6. Gain / Offset ─────────────────────────────
            if "gain" in ic.extra_params:
                await self.send_command(
                    "set_gain", {"gain": int(ic.extra_params["gain"])}
                )
            if "offset" in ic.extra_params:
                await self.send_command(
                    "set_offset",
                    {"offset": int(ic.extra_params["offset"])},
                )

        logger.info(
            f"[{self.instrument_name}] Configuration complete for "
            f"config id={config.id}."
        )

    # ─────────────────────────────────────────────────────────
    # expose()   (called by TelescopeExecutor)
    # ─────────────────────────────────────────────────────────
    async def expose(self, config: Configuration):
        """
        Execute exposures as specified by the instrument_configs.
        Supports single exposures, multi-frame sequences, and
        quick-expose presets.
        """
        logger.info(
            f"[{self.instrument_name}] Starting exposure(s) for "
            f"config id={config.id} …"
        )

        for ic in config.instrument_configs:
            exp_time = float(ic.exposure_time or 1.0)
            count = int(ic.exposure_count or 1)
            delay = float(ic.extra_params.get("delay", 0.0))

            # Quick-expose preset shortcut
            quick_preset = ic.extra_params.get("quick_preset")
            if quick_preset is not None:
                res = await self.send_command(
                    "quick_expose",
                    {"preset": int(quick_preset)},
                    timeout=max(60, exp_time + 30),
                )
                if res and res.get("success"):
                    url = res.get("data", {}).get("download_url")
                    if url:
                        await self._download_file(url)
                continue

            if count > 1:
                # Use the server-side sequence command
                logger.info(
                    f"[{self.instrument_name}] Sequence: "
                    f"{count} × {exp_time}s  (delay={delay}s)"
                )
                total_wait = count * (exp_time + delay) + 10
                res = await self.send_command(
                    "sequence",
                    {
                        "count": count,
                        "exposure": exp_time,
                        "delay": delay,
                    },
                    timeout=max(total_wait, 30),
                )
                if res and res.get("success"):
                    urls = res.get("data", {}).get("download_urls", [])
                    for url in urls:
                        await self._download_file(url)
            else:
                logger.info(
                    f"[{self.instrument_name}] Single exposure: "
                    f"{exp_time}s"
                )
                res = await self.send_command(
                    "expose",
                    {"seconds": exp_time},
                    timeout=max(exp_time + 30, 30),
                )
                if res and res.get("success"):
                    url = res.get("data", {}).get("download_url")
                    if url:
                        await self._download_file(url)

        logger.info(
            f"[{self.instrument_name}] All exposures done for "
            f"config id={config.id}."
        )

    # ─────────────────────────────────────────────────────────
    # Additional camera helpers (can be called externally)
    # ─────────────────────────────────────────────────────────
    async def _download_file(self, url_path: str):
        full_url = f"{self.api_url}{url_path}"
        filename = url_path.split("/")[-1]
        save_path = self.output_dir / filename
        
        def download():
            try:
                resp = requests.get(full_url, stream=True, timeout=30)
                resp.raise_for_status()
                with open(save_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"[{self.instrument_name}] Downloaded {filename} to {save_path}")
            except Exception as e:
                logger.error(f"[{self.instrument_name}] Failed to download {filename}: {e}")
                
        await asyncio.to_thread(download)


    async def get_temperature(self) -> Optional[str]:
        """Read the current sensor temperature."""
        resp = await self.send_command("get_temperature")
        return resp.get("data", {}).get("output") if resp else None

    async def get_camera_info(self) -> Optional[str]:
        """Retrieve camera model / properties info."""
        resp = await self.send_command("info")
        return resp.get("data", {}).get("output") if resp else None

    async def warm_up(self):
        """Initiate cooler warm-up (call before disconnect)."""
        await self.send_command("warm_up")

    async def disconnect(self):
        """Safely disconnect from the camera."""
        await self.send_command("warm_up")      # safety: warm first
        await self.send_command("disconnect")

    async def force_stop(self):
        """
        Emergency stop — called by the executor on abort.
        Attempt to warm up the cooler and disconnect gracefully.
        """
        logger.warning(
            f"[{self.instrument_name}] EMERGENCY STOP requested."
        )
        try:
            await self.send_command("warm_up", timeout=5)
            await self.send_command("disconnect", timeout=10)
        except Exception as e:
            logger.error(
                f"[{self.instrument_name}] Error during force_stop: {e}"
            )

    # ─────────────────────────────────────────────────────────
    # Private utilities
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def _resolve_filter_position(value) -> Optional[int]:
        """
        Accept either an integer position directly or a filter name
        and resolve it via FILTER_MAP.
        """
        # Already an int
        try:
            return int(value)
        except (ValueError, TypeError):
            pass
        # Lookup by name
        return FILTER_MAP.get(str(value).strip())

    @staticmethod
    def _parse_binning(value):
        """
        Accept '2x2', '2', 2, etc. and return (x, y).
        Returns (None, None) on failure.
        """
        try:
            s = str(value).lower().strip()
            if "x" in s:
                parts = s.split("x")
                return int(parts[0]), int(parts[1])
            v = int(value)
            return v, v
        except Exception:
            return None, None

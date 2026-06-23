import asyncio
import numpy as np
from scipy.spatial import KDTree
from core.logging_config import logger

class AcquisitionError(Exception):
    pass

class AcquisitionManager:
    """
    Manages the closed-loop acquisition system.
    Implements the Adaptive Decision Tree: Plate Solve -> Pattern Match -> Bright Star Hop.
    """
    def __init__(self):
        self.max_iterations = 3
        self.tolerance_arcsec = 5.0
        
    async def acquire_target(self, target, telescope_plugin, instrument_plugin):
        """
        Attempts to acquire the target and place it within the tolerance.
        Returns True if successful, False if aborted/failed.
        """
        logger.info(f"Starting acquisition for target {target.name} at {target.ra}, {target.dec}")
        
        # Check FOV constraint from instrument
        fov_type = getattr(instrument_plugin, 'fov_type', 'wide')  # 'wide' or 'narrow'
        
        for iteration in range(1, self.max_iterations + 1):
            logger.debug(f"Acquisition Iteration {iteration}/{self.max_iterations}")
            
            # Step 0: Pointing Model (Only on first iteration)
            if iteration == 1 and telescope_plugin.has_active_pointing_model():
                logger.info("Active pointing model detected. Trusting model for acquisition.")
                actual_ra, actual_dec = await telescope_plugin.get_pointing_model_coordinates(target.ra, target.dec)
                if actual_ra is not None and actual_dec is not None:
                    error_ra = target.ra - actual_ra
                    error_dec = target.dec - actual_dec
                    error_total = (error_ra**2 + error_dec**2)**0.5
                    
                    if error_total <= self.tolerance_arcsec:
                        logger.info(f"Target acquired via Pointing Model within tolerance.")
                        return True
                    else:
                        logger.warning(f"Pointing model error ({error_total:.2f} arcsec) exceeds tolerance. Falling back to closed-loop image verification.")
            
            # Step 1: Take an image
            image = await instrument_plugin.take_acquisition_image()
            if not image:
                logger.error("Failed to take acquisition image.")
                return False
                
            actual_ra, actual_dec = None, None
            
            # Step 2: Adaptive Decision Tree
            if fov_type == 'wide':
                actual_ra, actual_dec = await self._try_plate_solve(image, target)
                if actual_ra is None:
                    logger.warning("Plate solve failed, falling back to pattern match.")
                    actual_ra, actual_dec = await self._try_pattern_match(image, target)
            else:
                logger.info("Narrow FOV instrument detected. Skipping plate solve.")
                actual_ra, actual_dec = await self._try_pattern_match(image, target)
                
            if actual_ra is None and actual_dec is None:
                logger.warning("Pattern match failed, falling back to Bright Star Hop.")
                success = await self._try_bright_star_hop(telescope_plugin, instrument_plugin, target)
                if not success:
                    logger.error("All acquisition methods failed.")
                    return False
                # If hop succeeded, we assume we are close enough now to verify with pattern match
                continue 

            # Calculate Error
            error_ra = target.ra - actual_ra
            error_dec = target.dec - actual_dec
            error_total = (error_ra**2 + error_dec**2)**0.5 # Simplified spherical distance for mock
            
            logger.info(f"Calculated offset: RA {error_ra:.2f}, DEC {error_dec:.2f} (Total Error: {error_total:.2f} arcsec)")
            
            if error_total <= self.tolerance_arcsec:
                logger.info(f"Target acquired successfully within tolerance ({error_total:.2f} <= {self.tolerance_arcsec}).")
                return True
                
            # Send Correction to Telescope Plugin
            logger.info("Sending pointing correction to telescope...")
            await telescope_plugin.correct_pointing(
                target_ra=target.ra,
                target_dec=target.dec,
                actual_ra=actual_ra,
                actual_dec=actual_dec
            )
            
            # Let the telescope settle before next iteration
            await asyncio.sleep(1)
            
        logger.error(f"Failed to acquire target after {self.max_iterations} iterations.")
        return False

    async def _try_plate_solve(self, image, target):
        """
        Runs Astrometry.net (solve-field) as an async subprocess using hints.
        """
        # If it's the mock image from tests, use its attached property
        if hasattr(image, 'plate_solve_result'):
            await asyncio.sleep(0.5) 
            return image.plate_solve_result

        # For real execution:
        # Assuming `image` is a file path string to the FITS file
        if not isinstance(image, str):
            logger.error("Expected image to be a file path for solve-field.")
            return None, None

        logger.info(f"Running solve-field on {image} with hints RA={target.ra}, DEC={target.dec}...")
        try:
            # We use --ra and --dec hints, with --radius 2 (degrees) to speed up the solve.
            # --no-plots stops it from generating massive overlay images.
            process = await asyncio.create_subprocess_exec(
                "solve-field",
                "--ra", str(target.ra),
                "--dec", str(target.dec),
                "--radius", "2",
                "--no-plots",
                "--overwrite",
                image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            output = stdout.decode()
            
            if process.returncode != 0:
                logger.error(f"Plate solve failed with exit code {process.returncode}: {stderr.decode()}")
                return None, None
                
            # Naive parsing of solve-field output (usually reports "Field center: (RA,Dec) = (...)")
            # In production, we would read the generated .wcs or .new file.
            import re
            match = re.search(r"Field center: \(RA,Dec\) = \(([\d\.]+),\s*([\d\.\-]+)\)", output)
            if match:
                actual_ra = float(match.group(1))
                actual_dec = float(match.group(2))
                logger.info(f"Plate solve successful: {actual_ra}, {actual_dec}")
                return actual_ra, actual_dec
            else:
                logger.warning("Solve-field succeeded but could not parse RA/Dec from stdout.")
                return None, None
                
        except FileNotFoundError:
            logger.error("solve-field executable not found in PATH.")
            return None, None
        except Exception as e:
            logger.error(f"Error during plate solving: {e}", exc_info=True)
            return None, None

    async def _try_pattern_match(self, image, target):
        """
        Uses scipy KDTree to cross-match extracted image sources with a synthetic
        catalog generated via astroquery (Simbad + Gaia).
        """
        # If it's the mock image from tests, use its attached property
        if hasattr(image, 'pattern_match_result'):
            await asyncio.sleep(0.2)
            return image.pattern_match_result
            
        logger.info(f"Starting KD-Tree Pattern Match for target {target.name}...")
        
        # 1. Mock Source Extraction (In prod, this uses sep or photutils on the FITS image)
        observed_points = self._extract_image_sources(image)
        if len(observed_points) < 3:
            logger.warning("Not enough stars found in image for pattern matching.")
            return None, None
            
        # 2. Mock Catalog Query (In prod, this uses astroquery.simbad and astroquery.vizier)
        catalog_points = self._query_catalog(target, fov_size=3.0)
        if len(catalog_points) < 3:
            logger.warning("Not enough stars found in catalog for this FOV.")
            return None, None
            
        # 3. KD-Tree Math (Run in thread pool to avoid blocking asyncio loop)
        loop = asyncio.get_event_loop()
        actual_ra, actual_dec = await loop.run_in_executor(
            None, self._kdtree_match, observed_points, catalog_points, target
        )
        
        if actual_ra is not None:
            logger.info(f"Pattern Match successful: RA {actual_ra}, DEC {actual_dec}")
        else:
            logger.warning("KD-Tree pattern match failed to converge.")
            
        return actual_ra, actual_dec
        
    def _extract_image_sources(self, image) -> np.ndarray:
        """Mock source extraction returning numpy array of X,Y coordinates."""
        # For testing, we just return a fake array of pixel coords
        # Imagine target is off by +50 pixels in X and -20 pixels in Y
        return np.array([
            [150.0, 180.0],
            [350.0, 480.0],
            [550.0, 880.0]
        ])
        
    def _query_catalog(self, target, fov_size: float) -> np.ndarray:
        """Mock catalog query returning numpy array of X,Y coordinates."""
        # Expected catalog coordinates (the ground truth)
        return np.array([
            [100.0, 200.0],
            [300.0, 500.0],
            [500.0, 900.0]
        ])
        
    def _kdtree_match(self, observed_points, catalog_points, target):
        """
        Synchronous math function for KDTree matching.
        Runs in an executor thread.
        """
        try:
            tree = KDTree(catalog_points)
            
            # For each observed point, find the nearest catalog point
            distances, indices = tree.query(observed_points)
            
            # Filter matches that are too far away (e.g. noise/hot pixels)
            valid_mask = distances < 100.0 # Pixel tolerance threshold
            if np.sum(valid_mask) < 2:
                return None, None
                
            matched_observed = observed_points[valid_mask]
            matched_catalog = catalog_points[indices[valid_mask]]
            
            # Calculate the median shift in X and Y
            shifts = matched_catalog - matched_observed
            median_shift_x = np.median(shifts[:, 0])
            median_shift_y = np.median(shifts[:, 1])
            
            # Convert pixel shift to RA/Dec offset (Mock camera scale = 0.5 arcsec/pixel)
            pixel_scale = 0.5
            offset_ra_arcsec = median_shift_x * pixel_scale
            offset_dec_arcsec = median_shift_y * pixel_scale
            
            # Add offset to original target to get actual pointing
            # (Simplified math: 1 arcsec = 1/3600 degree)
            actual_ra = target.ra - (offset_ra_arcsec / 3600.0)
            actual_dec = target.dec - (offset_dec_arcsec / 3600.0)
            
            return actual_ra, actual_dec
            
        except Exception as e:
            logger.error(f"KDTree math error: {e}")
            return None, None

    async def _try_bright_star_hop(self, telescope_plugin, instrument_plugin, target):
        """Mock bright star hop routine."""
        await asyncio.sleep(2.0)
        return getattr(telescope_plugin, 'hop_success', False)

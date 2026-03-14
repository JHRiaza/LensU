"""STMap generation helpers for LensU."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from calibration import (
    CalibrationPoint,
    reconstruct_camera_matrix,
    reconstruct_dist_coeffs,
)


def _scaled_camera_matrix(camera_matrix: np.ndarray, image_size: tuple[int, int], output_size: tuple[int, int]) -> np.ndarray:
    if image_size == output_size:
        return camera_matrix.astype(np.float32)

    in_width, in_height = image_size
    out_width, out_height = output_size
    scaled = camera_matrix.astype(np.float32).copy()
    scaled[0, 0] *= out_width / in_width
    scaled[1, 1] *= out_height / in_height
    scaled[0, 2] *= out_width / in_width
    scaled[1, 2] *= out_height / in_height
    return scaled


def generate_stmap(
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    image_size: tuple[int, int],
    output_size: Optional[tuple[int, int]] = None,
) -> np.ndarray:
    """Generate an undistorted-to-distorted STMap as a float32 RGB array."""

    output_size = output_size or image_size
    new_camera_matrix = _scaled_camera_matrix(camera_matrix, image_size, output_size)
    map_x, map_y = cv2.initUndistortRectifyMap(
        camera_matrix,
        dist_coeffs,
        None,
        new_camera_matrix,
        output_size,
        cv2.CV_32FC1,
    )

    width, height = image_size
    stmap = np.zeros((output_size[1], output_size[0], 3), dtype=np.float32)
    stmap[..., 0] = (map_x + 0.5) / float(width)
    stmap[..., 1] = (map_y + 0.5) / float(height)
    return stmap


def save_stmap_exr(stmap: np.ndarray, output_path: Path) -> Path:
    """Save an STMap as float EXR, or TIFF if EXR is unavailable."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if stmap.dtype != np.float32 or stmap.ndim != 3 or stmap.shape[2] != 3:
        raise ValueError("STMap must be a float32 HxWx3 array.")

    preferred = output_path if output_path.suffix.lower() == ".exr" else output_path.with_suffix(".exr")
    os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")
    try:
        if cv2.imwrite(str(preferred), stmap):
            return preferred
    except cv2.error:
        pass

    fallback = output_path.with_suffix(".tiff")
    if cv2.imwrite(str(fallback), stmap):
        return fallback
    raise RuntimeError("Failed to save STMap as EXR or TIFF.")


def generate_stmap_from_calibration(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    output_path: Path,
) -> Path:
    """Generate and save an STMap from a calibration point."""

    camera_matrix = reconstruct_camera_matrix(point, image_size)
    dist_coeffs = reconstruct_dist_coeffs(point)
    stmap = generate_stmap(camera_matrix, dist_coeffs, image_size)
    return save_stmap_exr(stmap, output_path)

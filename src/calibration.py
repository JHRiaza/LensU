"""LensU — Core calibration engine using OpenCV."""

import json
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class CalibrationPoint:
    """Single calibration data point at a specific focal length."""
    focal_length_mm: float
    # Distortion coefficients (Brown-Conrady model)
    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    k3: float = 0.0
    # Image center (principal point), normalized 0-1
    cx: float = 0.5
    cy: float = 0.5
    # Focal length in pixels
    fx: float = 0.0
    fy: float = 0.0
    # Reprojection error (quality metric)
    rms_error: float = 0.0
    # Number of images used
    num_images: int = 0


@dataclass
class NodalOffset:
    """Nodal point offset at a specific focal length."""
    focal_length_mm: float
    # Translation offset in mm
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_z: float = 0.0
    # Rotation offset in degrees
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0


@dataclass
class LensProfile:
    """Complete lens calibration profile."""
    lens_name: str = "Unknown Lens"
    sensor_width_mm: float = 36.0  # Full frame default
    sensor_height_mm: float = 24.0
    image_width: int = 1920
    image_height: int = 1080
    calibration_points: list[CalibrationPoint] = field(default_factory=list)
    nodal_offsets: list[NodalOffset] = field(default_factory=list)

    def add_calibration(self, point: CalibrationPoint):
        # Replace existing point at same focal length, or append
        self.calibration_points = [
            p for p in self.calibration_points
            if abs(p.focal_length_mm - point.focal_length_mm) > 0.1
        ]
        self.calibration_points.append(point)
        self.calibration_points.sort(key=lambda p: p.focal_length_mm)

    def add_nodal_offset(self, offset: NodalOffset):
        self.nodal_offsets = [
            n for n in self.nodal_offsets
            if abs(n.focal_length_mm - offset.focal_length_mm) > 0.1
        ]
        self.nodal_offsets.append(offset)
        self.nodal_offsets.sort(key=lambda n: n.focal_length_mm)

    def to_dict(self) -> dict:
        return asdict(self)

    def save_json(self, path: Path):
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load_json(cls, path: Path) -> "LensProfile":
        data = json.loads(path.read_text())
        profile = cls(
            lens_name=data.get("lens_name", "Unknown"),
            sensor_width_mm=data.get("sensor_width_mm", 36.0),
            sensor_height_mm=data.get("sensor_height_mm", 24.0),
            image_width=data.get("image_width", 1920),
            image_height=data.get("image_height", 1080),
        )
        for p in data.get("calibration_points", []):
            profile.calibration_points.append(CalibrationPoint(**p))
        for n in data.get("nodal_offsets", []):
            profile.nodal_offsets.append(NodalOffset(**n))
        return profile


def detect_checkerboard(
    image: np.ndarray,
    pattern_size: tuple[int, int] = (9, 6),
) -> tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
    """Detect checkerboard corners in an image.
    
    Returns: (found, corners, display_image)
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    
    flags = (
        cv2.CALIB_CB_ADAPTIVE_THRESH
        | cv2.CALIB_CB_NORMALIZE_IMAGE
        | cv2.CALIB_CB_FAST_CHECK
    )
    found, corners = cv2.findChessboardCorners(gray, pattern_size, flags)
    
    if found and corners is not None:
        # Refine to sub-pixel accuracy
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    
    # Draw corners on a copy for display
    display = image.copy()
    cv2.drawChessboardCorners(display, pattern_size, corners, found)
    
    return found, corners, display


def calibrate_from_images(
    image_paths: list[Path],
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    focal_length_mm: float = 50.0,
) -> tuple[Optional[CalibrationPoint], list[bool]]:
    """Run full calibration from a set of checkerboard images.
    
    Returns: (CalibrationPoint or None, list of which images were used)
    """
    # Prepare object points (3D points in real-world space)
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size_mm

    obj_points = []  # 3D points
    img_points = []  # 2D points
    used = []
    img_size = None

    for path in image_paths:
        img = cv2.imread(str(path))
        if img is None:
            used.append(False)
            continue

        if img_size is None:
            img_size = (img.shape[1], img.shape[0])

        found, corners, _ = detect_checkerboard(img, pattern_size)
        if found and corners is not None:
            obj_points.append(objp)
            img_points.append(corners)
            used.append(True)
        else:
            used.append(False)

    if len(obj_points) < 3:
        return None, used

    # Run calibration
    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, img_size, None, None
    )

    # Extract parameters
    fx = camera_matrix[0, 0]
    fy = camera_matrix[1, 1]
    cx = camera_matrix[0, 2] / img_size[0]  # Normalize to 0-1
    cy = camera_matrix[1, 2] / img_size[1]

    k1 = float(dist_coeffs[0, 0])
    k2 = float(dist_coeffs[0, 1])
    p1 = float(dist_coeffs[0, 2])
    p2 = float(dist_coeffs[0, 3])
    k3 = float(dist_coeffs[0, 4]) if dist_coeffs.shape[1] > 4 else 0.0

    point = CalibrationPoint(
        focal_length_mm=focal_length_mm,
        k1=k1, k2=k2, p1=p1, p2=p2, k3=k3,
        cx=cx, cy=cy, fx=fx, fy=fy,
        rms_error=rms,
        num_images=len(obj_points),
    )

    return point, used


def estimate_nodal_offset(
    rvecs: list[np.ndarray],
    tvecs: list[np.ndarray],
    focal_length_mm: float = 50.0,
) -> NodalOffset:
    """Estimate nodal offset from calibration rotation/translation vectors.
    
    This is a simplified estimation — for production accuracy, 
    a dedicated nodal point test rig with rotation around the entrance pupil is needed.
    """
    # Average translation as a rough nodal offset estimate
    translations = np.array([t.flatten() for t in tvecs])
    avg_t = np.mean(translations, axis=0)

    return NodalOffset(
        focal_length_mm=focal_length_mm,
        offset_x=float(avg_t[0]),
        offset_y=float(avg_t[1]),
        offset_z=float(avg_t[2]),
    )

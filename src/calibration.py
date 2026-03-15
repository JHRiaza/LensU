"""LensU core calibration and visualization helpers."""

from __future__ import annotations

import json
import math
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

try:
    from . import __version__
    from .temp_paths import lensu_tempdir
except ImportError:
    __version__ = "1.7.0"
    from temp_paths import lensu_tempdir

LENSU_VERSION = __version__


@dataclass
class CalibrationPoint:
    """Single calibration data point at a specific focal length."""

    focal_length_mm: float
    k1: float = 0.0
    k2: float = 0.0
    p1: float = 0.0
    p2: float = 0.0
    k3: float = 0.0
    cx: float = 0.5
    cy: float = 0.5
    fx: float = 0.0
    fy: float = 0.0
    rms_error: float = 0.0
    num_images: int = 0
    detection_mode: str = "Checkerboard"
    is_fisheye: bool = False
    fisheye_coeffs: list[float] = field(default_factory=list)
    anamorphic_desqueezed: Optional[dict[str, float]] = None
    anamorphic_squeezed: Optional[dict[str, float]] = None


@dataclass
class AnamorphicInfo:
    """Anamorphic lens parameters."""

    squeeze_ratio: float = 2.0
    desqueeze_applied: bool = False


@dataclass
class BreathingPoint:
    """Focal length measurement at a specific focus distance."""

    focus_distance_m: float
    measured_focal_length_mm: float
    nominal_focal_length_mm: float


@dataclass
class BreathingProfile:
    """Lens breathing curve for a specific nominal focal length."""

    nominal_focal_length_mm: float
    points: list[BreathingPoint] = field(default_factory=list)

    def breathing_ratio(self) -> float:
        if not self.points or not self.nominal_focal_length_mm:
            return 0.0
        focal_lengths = [point.measured_focal_length_mm for point in self.points]
        return (max(focal_lengths) - min(focal_lengths)) / self.nominal_focal_length_mm * 100.0


@dataclass
class NodalOffset:
    """Nodal point offset at a specific focal length."""

    focal_length_mm: float
    offset_x: float = 0.0
    offset_y: float = 0.0
    offset_z: float = 0.0
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0
    confidence: float = 0.0
    method: str = "manual"


@dataclass
class LensProfile:
    """Complete lens calibration profile."""

    lens_name: str = "Unknown Lens"
    lens_family: str = ""
    lens_type: str = "prime"
    sensor_width_mm: float = 36.0
    sensor_height_mm: float = 24.0
    image_width: int = 1920
    image_height: int = 1080
    calibration_points: list[CalibrationPoint] = field(default_factory=list)
    nodal_offsets: list[NodalOffset] = field(default_factory=list)
    breathing_profiles: list[BreathingProfile] = field(default_factory=list)
    anamorphic: Optional[AnamorphicInfo] = None
    notes: str = ""
    source: str = ""
    encoder_mappings: dict[str, list[dict[str, float]]] = field(default_factory=dict)

    def add_calibration(self, point: CalibrationPoint) -> None:
        self.calibration_points = [
            p for p in self.calibration_points if abs(p.focal_length_mm - point.focal_length_mm) > 0.1
        ]
        self.calibration_points.append(point)
        self.calibration_points.sort(key=lambda p: p.focal_length_mm)

    def add_nodal_offset(self, offset: NodalOffset) -> None:
        self.nodal_offsets = [
            n for n in self.nodal_offsets if abs(n.focal_length_mm - offset.focal_length_mm) > 0.1
        ]
        self.nodal_offsets.append(offset)
        self.nodal_offsets.sort(key=lambda n: n.focal_length_mm)

    def add_breathing_point(self, point: BreathingPoint) -> None:
        existing = next(
            (
                profile
                for profile in self.breathing_profiles
                if abs(profile.nominal_focal_length_mm - point.nominal_focal_length_mm) <= 0.1
            ),
            None,
        )
        if existing is None:
            existing = BreathingProfile(nominal_focal_length_mm=point.nominal_focal_length_mm)
            self.breathing_profiles.append(existing)
        existing.points = [
            item for item in existing.points if abs(item.focus_distance_m - point.focus_distance_m) > 0.01
        ]
        existing.points.append(point)
        existing.points.sort(key=lambda item: item.focus_distance_m)
        self.breathing_profiles.sort(key=lambda profile: profile.nominal_focal_length_mm)

    def to_dict(self) -> dict:
        return asdict(self)

    def save_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> "LensProfile":
        data = json.loads(path.read_text(encoding="utf-8"))
        return lens_profile_from_dict(data)


@dataclass
class CameraRig:
    """A collection of labeled cameras with their own lens profiles."""

    rig_name: str = "Default Rig"
    cameras: dict[str, LensProfile] = field(default_factory=dict)

    def add_camera(self, label: str, profile: LensProfile) -> None:
        cleaned = label.strip() or f"Camera {len(self.cameras) + 1}"
        self.cameras[cleaned] = profile

    def to_dict(self) -> dict:
        return {
            "rig_name": self.rig_name,
            "cameras": {label: profile.to_dict() for label, profile in self.cameras.items()},
        }

    def save_json(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> "CameraRig":
        data = json.loads(path.read_text(encoding="utf-8"))
        return camera_rig_from_dict(data)


@dataclass
class CalibrationImageResult:
    """Detection and fit details for a single source image."""

    image_name: str
    used: bool
    detection_mode: str
    point_count: int = 0
    reprojection_error: Optional[float] = None
    coverage_points: list[tuple[float, float]] = field(default_factory=list)


@dataclass
class CalibrationDiagnostics:
    """Structured calibration diagnostics for UI/reporting."""

    image_size: Optional[tuple[int, int]]
    image_results: list[CalibrationImageResult] = field(default_factory=list)

    @property
    def mean_image_error(self) -> float:
        errors = [item.reprojection_error for item in self.image_results if item.reprojection_error is not None]
        return float(np.mean(errors)) if errors else 0.0

    @property
    def outlier_names(self) -> list[str]:
        mean_error = self.mean_image_error
        if mean_error <= 0.0:
            return []
        return [
            item.image_name
            for item in self.image_results
            if item.reprojection_error is not None and item.reprojection_error > (2.0 * mean_error)
        ]


def lens_profile_from_dict(data: dict) -> LensProfile:
    profile = LensProfile(
        lens_name=data.get("lens_name", "Unknown"),
        lens_family=data.get("lens_family", ""),
        lens_type=data.get("lens_type", data.get("type", "prime")),
        sensor_width_mm=data.get("sensor_width_mm", 36.0),
        sensor_height_mm=data.get("sensor_height_mm", 24.0),
        image_width=data.get("image_width", 1920),
        image_height=data.get("image_height", 1080),
        notes=data.get("notes", ""),
        source=data.get("source", ""),
        encoder_mappings=data.get("encoder_mappings", {}) or {},
    )
    for point in data.get("calibration_points", []):
        profile.calibration_points.append(CalibrationPoint(**point))
    for offset in data.get("nodal_offsets", []):
        profile.nodal_offsets.append(NodalOffset(**offset))
    for breathing in data.get("breathing_profiles", []):
        profile.breathing_profiles.append(
            BreathingProfile(
                nominal_focal_length_mm=breathing.get("nominal_focal_length_mm", 0.0),
                points=[BreathingPoint(**point) for point in breathing.get("points", [])],
            )
        )
    anamorphic = data.get("anamorphic")
    if isinstance(anamorphic, dict):
        profile.anamorphic = AnamorphicInfo(**anamorphic)
    profile.calibration_points.sort(key=lambda point: point.focal_length_mm)
    profile.nodal_offsets.sort(key=lambda point: point.focal_length_mm)
    profile.breathing_profiles.sort(key=lambda point: point.nominal_focal_length_mm)
    return profile


def camera_rig_from_dict(data: dict) -> CameraRig:
    rig = CameraRig(rig_name=data.get("rig_name", "Default Rig"))
    cameras = data.get("cameras", {})
    if isinstance(cameras, dict):
        for label, profile_data in cameras.items():
            if isinstance(profile_data, dict):
                rig.add_camera(label, lens_profile_from_dict(profile_data))
    return rig


def _group_by_focal(items: list, focal_getter) -> dict[float, list]:
    grouped: dict[float, list] = {}
    for item in items:
        key = round(float(focal_getter(item)), 3)
        grouped.setdefault(key, []).append(item)
    return grouped


def _average_calibration_points(points: list[CalibrationPoint]) -> CalibrationPoint:
    if not points:
        raise ValueError("Cannot average an empty calibration point list.")
    template = points[-1]
    fisheye_len = max((len(point.fisheye_coeffs) for point in points), default=0)
    averaged_fisheye = [
        float(np.mean([point.fisheye_coeffs[index] if index < len(point.fisheye_coeffs) else 0.0 for point in points]))
        for index in range(fisheye_len)
    ]
    return CalibrationPoint(
        focal_length_mm=float(np.mean([point.focal_length_mm for point in points])),
        k1=float(np.mean([point.k1 for point in points])),
        k2=float(np.mean([point.k2 for point in points])),
        p1=float(np.mean([point.p1 for point in points])),
        p2=float(np.mean([point.p2 for point in points])),
        k3=float(np.mean([point.k3 for point in points])),
        cx=float(np.mean([point.cx for point in points])),
        cy=float(np.mean([point.cy for point in points])),
        fx=float(np.mean([point.fx for point in points])),
        fy=float(np.mean([point.fy for point in points])),
        rms_error=float(np.mean([point.rms_error for point in points])),
        num_images=int(sum(point.num_images for point in points)),
        detection_mode=template.detection_mode,
        is_fisheye=all(point.is_fisheye for point in points),
        fisheye_coeffs=averaged_fisheye,
        anamorphic_desqueezed=template.anamorphic_desqueezed,
        anamorphic_squeezed=template.anamorphic_squeezed,
    )


def _merge_encoder_mappings(profiles: list[LensProfile]) -> dict[str, list[dict[str, float]]]:
    merged: dict[str, list[dict[str, float]]] = {}
    for profile in profiles:
        for axis, samples in profile.encoder_mappings.items():
            if axis not in merged:
                merged[axis] = []
            for sample in samples:
                if sample not in merged[axis]:
                    merged[axis].append(sample)
    return merged


def merge_profiles(
    profiles: list[LensProfile],
    strategy: str = "best_rms",
) -> LensProfile:
    """Merge multiple profiles for the same lens.

    `latest` uses the order of the provided `profiles` list, with later entries
    treated as newer than earlier ones.
    """

    if not profiles:
        raise ValueError("At least one profile is required to merge.")
    if strategy not in {"best_rms", "average", "latest"}:
        raise ValueError(f"Unsupported merge strategy: {strategy}")

    latest_profile = profiles[-1]
    merged = LensProfile(
        lens_name=latest_profile.lens_name or profiles[0].lens_name,
        lens_family=latest_profile.lens_family or profiles[0].lens_family,
        lens_type=latest_profile.lens_type or profiles[0].lens_type,
        sensor_width_mm=latest_profile.sensor_width_mm or profiles[0].sensor_width_mm,
        sensor_height_mm=latest_profile.sensor_height_mm or profiles[0].sensor_height_mm,
        image_width=latest_profile.image_width or profiles[0].image_width,
        image_height=latest_profile.image_height or profiles[0].image_height,
        anamorphic=latest_profile.anamorphic or profiles[0].anamorphic,
        notes="\n".join(filter(None, [profile.notes for profile in profiles])),
        source=f"Merged {len(profiles)} profiles ({strategy})",
        encoder_mappings=_merge_encoder_mappings(profiles),
    )

    point_groups = _group_by_focal(
        [point for profile in profiles for point in profile.calibration_points],
        lambda item: item.focal_length_mm,
    )
    for focal in sorted(point_groups):
        candidates = point_groups[focal]
        if strategy == "average":
            merged.add_calibration(_average_calibration_points(candidates))
        elif strategy == "latest":
            merged.add_calibration(candidates[-1])
        else:
            merged.add_calibration(min(candidates, key=lambda point: (point.rms_error, -point.num_images)))

    offset_groups = _group_by_focal(
        [offset for profile in profiles for offset in profile.nodal_offsets],
        lambda item: item.focal_length_mm,
    )
    for focal in sorted(offset_groups):
        candidates = offset_groups[focal]
        if strategy == "average":
            merged.add_nodal_offset(
                NodalOffset(
                    focal_length_mm=float(np.mean([offset.focal_length_mm for offset in candidates])),
                    offset_x=float(np.mean([offset.offset_x for offset in candidates])),
                    offset_y=float(np.mean([offset.offset_y for offset in candidates])),
                    offset_z=float(np.mean([offset.offset_z for offset in candidates])),
                    rotation_x=float(np.mean([offset.rotation_x for offset in candidates])),
                    rotation_y=float(np.mean([offset.rotation_y for offset in candidates])),
                    rotation_z=float(np.mean([offset.rotation_z for offset in candidates])),
                    confidence=float(np.mean([offset.confidence for offset in candidates])),
                    method=candidates[-1].method,
                )
            )
        else:
            merged.add_nodal_offset(candidates[-1])

    breathing_groups = _group_by_focal(
        [breathing for profile in profiles for breathing in profile.breathing_profiles],
        lambda item: item.nominal_focal_length_mm,
    )
    for focal in sorted(breathing_groups):
        merged_profile = BreathingProfile(nominal_focal_length_mm=focal)
        distance_groups = _group_by_focal(
            [point for breathing in breathing_groups[focal] for point in breathing.points],
            lambda item: item.focus_distance_m,
        )
        for distance in sorted(distance_groups):
            candidates = distance_groups[distance]
            if strategy == "average":
                merged_profile.points.append(
                    BreathingPoint(
                        focus_distance_m=float(np.mean([point.focus_distance_m for point in candidates])),
                        measured_focal_length_mm=float(np.mean([point.measured_focal_length_mm for point in candidates])),
                        nominal_focal_length_mm=float(
                            np.mean([point.nominal_focal_length_mm for point in candidates])
                        ),
                    )
                )
            else:
                merged_profile.points.append(candidates[-1])
        merged.breathing_profiles.append(merged_profile)
    merged.breathing_profiles.sort(key=lambda item: item.nominal_focal_length_mm)
    return merged


def aruco_available() -> bool:
    return hasattr(cv2, "aruco")


def _decode_image(image_path: Path) -> Optional[np.ndarray]:
    return cv2.imread(str(image_path))


def _encode_image_path(image: np.ndarray, output_path: Path) -> None:
    suffix = output_path.suffix.lower() or ".png"
    extension = ".png" if suffix not in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"} else suffix
    success, encoded = cv2.imencode(extension, image)
    if not success:
        raise RuntimeError(f"Failed to encode transformed image: {output_path.name}")
    output_path.write_bytes(encoded.tobytes())


def _scale_image_horizontally(image: np.ndarray, scale: float) -> np.ndarray:
    if scale <= 0:
        raise ValueError("Horizontal scale must be positive.")
    width = max(int(round(image.shape[1] * scale)), 1)
    interpolation = cv2.INTER_CUBIC if scale >= 1.0 else cv2.INTER_AREA
    return cv2.resize(image, (width, image.shape[0]), interpolation=interpolation)


def _write_scaled_images(image_paths: list[Path], scale: float, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    transformed_paths: list[Path] = []
    for index, path in enumerate(image_paths):
        image = _decode_image(path)
        if image is None:
            continue
        transformed = _scale_image_horizontally(image, scale)
        target_path = output_dir / f"{index:03d}_{path.stem}.png"
        _encode_image_path(transformed, target_path)
        transformed_paths.append(target_path)
    return transformed_paths


def _anamorphic_payload(point: CalibrationPoint) -> dict[str, float]:
    return {
        "k1": point.k1,
        "k2": point.k2,
        "p1": point.p1,
        "p2": point.p2,
        "k3": point.k3,
        "cx": point.cx,
        "cy": point.cy,
        "fx": point.fx,
        "fy": point.fy,
        "rms_error": point.rms_error,
    }


def _merge_anamorphic_points(
    desqueezed_point: CalibrationPoint,
    squeezed_point: CalibrationPoint,
    squeeze_ratio: float,
) -> CalibrationPoint:
    desqueezed_point.anamorphic_desqueezed = _anamorphic_payload(desqueezed_point)
    desqueezed_point.anamorphic_squeezed = _anamorphic_payload(squeezed_point)
    desqueezed_point.detection_mode = f"{desqueezed_point.detection_mode} (Anamorphic {squeeze_ratio:.2f}x)"
    return desqueezed_point


def _create_checkerboard_object_points(
    pattern_size: tuple[int, int],
    square_size_mm: float,
) -> np.ndarray:
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0 : pattern_size[0], 0 : pattern_size[1]].T.reshape(-1, 2)
    objp *= square_size_mm
    return objp


def _create_charuco_board(
    board_size: tuple[int, int],
    square_length_mm: float,
    marker_length_mm: float,
    dictionary: int,
):
    if not aruco_available():
        raise RuntimeError("OpenCV ArUco module is not available in this environment.")

    aruco = cv2.aruco
    dictionary_obj = aruco.getPredefinedDictionary(dictionary)
    if hasattr(aruco, "CharucoBoard"):
        return aruco.CharucoBoard(board_size, square_length_mm, marker_length_mm, dictionary_obj)
    if hasattr(aruco, "CharucoBoard_create"):
        return aruco.CharucoBoard_create(
            board_size[0], board_size[1], square_length_mm, marker_length_mm, dictionary_obj
        )
    raise RuntimeError("This OpenCV build does not expose a ChArUco board constructor.")


def _charuco_board_corners(board) -> np.ndarray:
    if hasattr(board, "getChessboardCorners"):
        return board.getChessboardCorners()
    return board.chessboardCorners


def detect_checkerboard(
    image: np.ndarray,
    pattern_size: tuple[int, int] = (9, 6),
) -> tuple[bool, Optional[np.ndarray], np.ndarray]:
    """Detect checkerboard corners in an image."""

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    flags = cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE | cv2.CALIB_CB_FAST_CHECK
    found, corners = cv2.findChessboardCorners(gray, pattern_size, flags)

    if found and corners is not None:
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)

    display = image.copy()
    cv2.drawChessboardCorners(display, pattern_size, corners, found)
    return found, corners, display


def detect_charuco(
    image: np.ndarray,
    board_size: tuple[int, int] = (7, 5),
    square_length_mm: float = 30.0,
    marker_length_mm: float = 22.5,
    dictionary: int = cv2.aruco.DICT_6X6_250 if hasattr(cv2, "aruco") else 0,
) -> tuple[bool, Optional[np.ndarray], Optional[np.ndarray], np.ndarray]:
    """Detect ChArUco corners."""

    board = _create_charuco_board(board_size, square_length_mm, marker_length_mm, dictionary)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    aruco = cv2.aruco

    if hasattr(aruco, "ArucoDetector"):
        detector = aruco.ArucoDetector(aruco.getPredefinedDictionary(dictionary))
        marker_corners, marker_ids, _ = detector.detectMarkers(gray)
    else:
        marker_corners, marker_ids, _ = aruco.detectMarkers(
            gray, aruco.getPredefinedDictionary(dictionary)
        )

    display = image.copy()
    if marker_ids is not None and len(marker_ids):
        aruco.drawDetectedMarkers(display, marker_corners, marker_ids)

    if marker_ids is None or len(marker_ids) == 0:
        return False, None, None, display

    retval, charuco_corners, charuco_ids = aruco.interpolateCornersCharuco(
        marker_corners, marker_ids, gray, board
    )
    found = bool(retval and charuco_corners is not None and charuco_ids is not None and len(charuco_ids) >= 4)
    if found:
        aruco.drawDetectedCornersCharuco(display, charuco_corners, charuco_ids)
        return True, charuco_corners, charuco_ids, display
    return False, None, None, display


def _build_calibration_point(
    focal_length_mm: float,
    detection_mode: str,
    rms: float,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    image_size: tuple[int, int],
    num_images: int,
) -> CalibrationPoint:
    width, height = image_size
    return CalibrationPoint(
        focal_length_mm=focal_length_mm,
        k1=float(dist_coeffs[0, 0]),
        k2=float(dist_coeffs[0, 1]),
        p1=float(dist_coeffs[0, 2]),
        p2=float(dist_coeffs[0, 3]),
        k3=float(dist_coeffs[0, 4]) if dist_coeffs.shape[1] > 4 else 0.0,
        cx=float(camera_matrix[0, 2] / width),
        cy=float(camera_matrix[1, 2] / height),
        fx=float(camera_matrix[0, 0]),
        fy=float(camera_matrix[1, 1]),
        rms_error=float(rms),
        num_images=num_images,
        detection_mode=detection_mode,
    )


def _build_fisheye_calibration_point(
    focal_length_mm: float,
    rms: float,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    image_size: tuple[int, int],
    num_images: int,
) -> CalibrationPoint:
    width, height = image_size
    coeffs = np.asarray(dist_coeffs, dtype=np.float64).reshape(-1)
    padded = list(coeffs[:4]) + [0.0] * max(0, 4 - len(coeffs))
    return CalibrationPoint(
        focal_length_mm=focal_length_mm,
        k1=float(padded[0]),
        k2=float(padded[1]),
        p1=0.0,
        p2=0.0,
        k3=float(padded[2]),
        cx=float(camera_matrix[0, 2] / width),
        cy=float(camera_matrix[1, 2] / height),
        fx=float(camera_matrix[0, 0]),
        fy=float(camera_matrix[1, 1]),
        rms_error=float(rms),
        num_images=num_images,
        detection_mode="Fisheye Checkerboard",
        is_fisheye=True,
        fisheye_coeffs=[float(value) for value in padded],
    )


def _project_error(
    object_points: np.ndarray,
    image_points: np.ndarray,
    rvec: np.ndarray,
    tvec: np.ndarray,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> float:
    projected, _ = cv2.projectPoints(object_points, rvec, tvec, camera_matrix, dist_coeffs)
    error = cv2.norm(image_points, projected, cv2.NORM_L2) / len(projected)
    return float(error)


def calibrate_from_images(
    image_paths: list[Path],
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    focal_length_mm: float = 50.0,
) -> tuple[Optional[CalibrationPoint], CalibrationDiagnostics]:
    """Run checkerboard calibration and return fit diagnostics."""

    objp = _create_checkerboard_object_points(pattern_size, square_size_mm)
    obj_points: list[np.ndarray] = []
    img_points: list[np.ndarray] = []
    image_names: list[str] = []
    diagnostics = CalibrationDiagnostics(image_size=None)

    for path in image_paths:
        img = _decode_image(path)
        if img is None:
            diagnostics.image_results.append(
                CalibrationImageResult(image_name=path.name, used=False, detection_mode="Checkerboard")
            )
            continue

        current_size = (img.shape[1], img.shape[0])
        diagnostics.image_size = diagnostics.image_size or current_size

        found, corners, _ = detect_checkerboard(img, pattern_size)
        result = CalibrationImageResult(
            image_name=path.name,
            used=bool(found and corners is not None),
            detection_mode="Checkerboard",
            point_count=int(len(corners)) if corners is not None else 0,
            coverage_points=[],
        )
        if found and corners is not None:
            obj_points.append(objp.copy())
            img_points.append(corners)
            image_names.append(path.name)
            width, height = current_size
            result.coverage_points = [
                (float(pt[0][0] / width), float(pt[0][1] / height)) for pt in corners
            ]
        diagnostics.image_results.append(result)

    if len(obj_points) < 3 or diagnostics.image_size is None:
        return None, diagnostics

    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        obj_points, img_points, diagnostics.image_size, None, None
    )

    error_map = {
        name: _project_error(objp_i, imgp_i, rvec, tvec, camera_matrix, dist_coeffs)
        for name, objp_i, imgp_i, rvec, tvec in zip(image_names, obj_points, img_points, rvecs, tvecs)
    }
    for item in diagnostics.image_results:
        item.reprojection_error = error_map.get(item.image_name)

    point = _build_calibration_point(
        focal_length_mm=focal_length_mm,
        detection_mode="Checkerboard",
        rms=rms,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        image_size=diagnostics.image_size,
        num_images=len(obj_points),
    )
    return point, diagnostics


def calibrate_fisheye(
    image_paths: list[Path],
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    focal_length_mm: float = 14.0,
) -> tuple[Optional[CalibrationPoint], list[bool]]:
    """Calibrate a fisheye/ultra-wide lens using OpenCV's equidistant model."""

    objp = _create_checkerboard_object_points(pattern_size, square_size_mm)
    obj_points: list[np.ndarray] = []
    img_points: list[np.ndarray] = []
    used_flags: list[bool] = []
    image_size: tuple[int, int] | None = None

    for path in image_paths:
        image = _decode_image(path)
        if image is None:
            used_flags.append(False)
            continue
        image_size = image_size or (image.shape[1], image.shape[0])
        found, corners, _ = detect_checkerboard(image, pattern_size)
        used = bool(found and corners is not None)
        used_flags.append(used)
        if not used:
            continue
        obj_points.append(objp.reshape(1, -1, 3).astype(np.float64))
        img_points.append(corners.reshape(1, -1, 2).astype(np.float64))

    if len(obj_points) < 3 or image_size is None:
        return None, used_flags

    camera_matrix = np.eye(3, dtype=np.float64)
    dist_coeffs = np.zeros((4, 1), dtype=np.float64)
    flags = (
        cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC
        | cv2.fisheye.CALIB_CHECK_COND
        | cv2.fisheye.CALIB_FIX_SKEW
    )
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1e-6)

    try:
        rms, camera_matrix, dist_coeffs, _, _ = cv2.fisheye.calibrate(
            obj_points,
            img_points,
            image_size,
            camera_matrix,
            dist_coeffs,
            flags=flags,
            criteria=criteria,
        )
    except cv2.error:
        return None, used_flags

    point = _build_fisheye_calibration_point(
        focal_length_mm=focal_length_mm,
        rms=rms,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        image_size=image_size,
        num_images=len(obj_points),
    )
    return point, used_flags


def calibrate_anamorphic_detailed(
    image_paths: list[Path],
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    focal_length_mm: float = 50.0,
    squeeze_ratio: float = 2.0,
    desqueezed: bool = False,
) -> tuple[Optional[CalibrationPoint], CalibrationDiagnostics, CalibrationDiagnostics]:
    """Calibrate an anamorphic lens and keep both squeezed and desqueezed fits."""

    if squeeze_ratio <= 0:
        raise ValueError("Squeeze ratio must be positive.")

    with lensu_tempdir() as tmpdir:
        temp_dir = Path(tmpdir)
        if desqueezed:
            desqueezed_paths = image_paths
            squeezed_paths = _write_scaled_images(image_paths, 1.0 / squeeze_ratio, temp_dir / "squeezed")
        else:
            squeezed_paths = image_paths
            desqueezed_paths = _write_scaled_images(image_paths, squeeze_ratio, temp_dir / "desqueezed")

        if not desqueezed_paths or not squeezed_paths:
            empty = CalibrationDiagnostics(image_size=None)
            return None, empty, empty

        desqueezed_point, desqueezed_diagnostics = calibrate_from_images(
            desqueezed_paths,
            pattern_size=pattern_size,
            square_size_mm=square_size_mm,
            focal_length_mm=focal_length_mm,
        )
        squeezed_point, squeezed_diagnostics = calibrate_from_images(
            squeezed_paths,
            pattern_size=pattern_size,
            square_size_mm=square_size_mm,
            focal_length_mm=focal_length_mm,
        )

    if desqueezed_point is None or squeezed_point is None:
        return None, desqueezed_diagnostics, squeezed_diagnostics

    return (
        _merge_anamorphic_points(desqueezed_point, squeezed_point, squeeze_ratio),
        desqueezed_diagnostics,
        squeezed_diagnostics,
    )


def calibrate_anamorphic(
    image_paths: list[Path],
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    focal_length_mm: float = 50.0,
    squeeze_ratio: float = 2.0,
    desqueezed: bool = False,
) -> tuple[Optional[CalibrationPoint], list[bool]]:
    """Calibrate an anamorphic lens.

    If images are NOT desqueezed:
      1. Desqueeze images horizontally by `squeeze_ratio`
      2. Run standard calibration on the desqueezed set
      3. Also solve a squeezed-space fit for reporting

    If images ARE already desqueezed:
      1. Run standard calibration directly
      2. Re-squeeze copies of the input to recover squeezed-space parameters

    The returned `CalibrationPoint` stores the desqueezed parameters, which are
    the values Unreal Engine should use for the CG render.
    """

    point, diagnostics, _ = calibrate_anamorphic_detailed(
        image_paths=image_paths,
        pattern_size=pattern_size,
        square_size_mm=square_size_mm,
        focal_length_mm=focal_length_mm,
        squeeze_ratio=squeeze_ratio,
        desqueezed=desqueezed,
    )
    return point, [item.used for item in diagnostics.image_results]


def calibrate_from_charuco_images(
    image_paths: list[Path],
    board_size: tuple[int, int] = (7, 5),
    square_length_mm: float = 30.0,
    marker_length_mm: float = 22.5,
    dictionary: int = cv2.aruco.DICT_6X6_250 if hasattr(cv2, "aruco") else 0,
    focal_length_mm: float = 50.0,
) -> tuple[Optional[CalibrationPoint], CalibrationDiagnostics]:
    """Run ChArUco calibration and return fit diagnostics."""

    board = _create_charuco_board(board_size, square_length_mm, marker_length_mm, dictionary)
    board_corners = _charuco_board_corners(board)
    charuco_corners_list: list[np.ndarray] = []
    charuco_ids_list: list[np.ndarray] = []
    image_names: list[str] = []
    diagnostics = CalibrationDiagnostics(image_size=None)

    for path in image_paths:
        img = _decode_image(path)
        if img is None:
            diagnostics.image_results.append(
                CalibrationImageResult(image_name=path.name, used=False, detection_mode="ChArUco")
            )
            continue

        current_size = (img.shape[1], img.shape[0])
        diagnostics.image_size = diagnostics.image_size or current_size
        found, corners, ids, _ = detect_charuco(
            img,
            board_size=board_size,
            square_length_mm=square_length_mm,
            marker_length_mm=marker_length_mm,
            dictionary=dictionary,
        )

        result = CalibrationImageResult(
            image_name=path.name,
            used=bool(found and corners is not None and ids is not None),
            detection_mode="ChArUco",
            point_count=int(len(ids)) if ids is not None else 0,
            coverage_points=[],
        )
        if found and corners is not None and ids is not None:
            charuco_corners_list.append(corners)
            charuco_ids_list.append(ids)
            image_names.append(path.name)
            width, height = current_size
            result.coverage_points = [
                (float(pt[0][0] / width), float(pt[0][1] / height)) for pt in corners
            ]
        diagnostics.image_results.append(result)

    if len(charuco_corners_list) < 3 or diagnostics.image_size is None:
        return None, diagnostics

    aruco = cv2.aruco
    rms, camera_matrix, dist_coeffs, rvecs, tvecs = aruco.calibrateCameraCharuco(
        charucoCorners=charuco_corners_list,
        charucoIds=charuco_ids_list,
        board=board,
        imageSize=diagnostics.image_size,
        cameraMatrix=None,
        distCoeffs=None,
    )

    error_map: dict[str, float] = {}
    for name, corners, ids, rvec, tvec in zip(
        image_names, charuco_corners_list, charuco_ids_list, rvecs, tvecs
    ):
        object_points = board_corners[ids.flatten()]
        error_map[name] = _project_error(
            object_points.astype(np.float32),
            corners,
            rvec,
            tvec,
            camera_matrix,
            dist_coeffs,
        )

    for item in diagnostics.image_results:
        item.reprojection_error = error_map.get(item.image_name)

    point = _build_calibration_point(
        focal_length_mm=focal_length_mm,
        detection_mode="ChArUco",
        rms=rms,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        image_size=diagnostics.image_size,
        num_images=len(charuco_corners_list),
    )
    return point, diagnostics


def reconstruct_camera_matrix(point: CalibrationPoint, image_size: tuple[int, int]) -> np.ndarray:
    """Reconstruct an OpenCV camera matrix from a calibration point."""

    width, height = image_size
    return np.array(
        [
            [point.fx, 0.0, point.cx * width],
            [0.0, point.fy, point.cy * height],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )


def reconstruct_dist_coeffs(point: CalibrationPoint) -> np.ndarray:
    """Reconstruct Brown-Conrady coefficients from a calibration point."""

    if point.is_fisheye:
        coeffs = point.fisheye_coeffs or [point.k1, point.k2, point.k3, 0.0]
        return np.asarray(coeffs[:4], dtype=np.float32).reshape(4, 1)
    return np.array([[point.k1, point.k2, point.p1, point.p2, point.k3]], dtype=np.float32)


def normalized_focal_lengths(point: CalibrationPoint, image_size: tuple[int, int]) -> tuple[float, float]:
    width, height = image_size
    return float(point.fx / width), float(point.fy / height)


def measured_focal_length_mm(point: CalibrationPoint, sensor_width_mm: float, image_width: int) -> float:
    if not sensor_width_mm or not image_width:
        return 0.0
    return float(point.fx * sensor_width_mm / image_width)


def coverage_fraction(
    diagnostics: CalibrationDiagnostics,
    bins: tuple[int, int] = (4, 4),
) -> float:
    if not diagnostics.image_results:
        return 0.0
    occupied = np.zeros((bins[1], bins[0]), dtype=bool)
    for result in diagnostics.image_results:
        for x_norm, y_norm in result.coverage_points:
            x_idx = min(int(x_norm * bins[0]), bins[0] - 1)
            y_idx = min(int(y_norm * bins[1]), bins[1] - 1)
            occupied[y_idx, x_idx] = True
    return float(occupied.mean())


def undistort_image(
    image: np.ndarray,
    point: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Apply undistortion using calibration data."""

    camera_matrix = reconstruct_camera_matrix(point, image_size)
    dist_coeffs = reconstruct_dist_coeffs(point)
    if point.is_fisheye:
        return cv2.fisheye.undistortImage(image, camera_matrix, dist_coeffs, Knew=camera_matrix)
    return cv2.undistort(image, camera_matrix, dist_coeffs)


def distort_points(
    points: np.ndarray,
    point: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Project ideal undistorted image points through the lens model."""

    camera_matrix = reconstruct_camera_matrix(point, image_size)
    dist_coeffs = reconstruct_dist_coeffs(point)
    width, height = image_size
    cx_px = point.cx * width
    cy_px = point.cy * height

    undistorted = points.astype(np.float32).reshape(-1, 2)
    normalized = np.empty((len(undistorted), 1, 3), dtype=np.float32)
    normalized[:, 0, 0] = (undistorted[:, 0] - cx_px) / point.fx
    normalized[:, 0, 1] = (undistorted[:, 1] - cy_px) / point.fy
    normalized[:, 0, 2] = 1.0

    rvec = np.zeros((3, 1), dtype=np.float32)
    tvec = np.zeros((3, 1), dtype=np.float32)
    if point.is_fisheye:
        projected, _ = cv2.fisheye.projectPoints(normalized, rvec, tvec, camera_matrix, dist_coeffs)
    else:
        projected, _ = cv2.projectPoints(normalized, rvec, tvec, camera_matrix, dist_coeffs)
    return projected.reshape(-1, 2)


def generate_distortion_grid(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    grid_spacing: int = 50,
) -> np.ndarray:
    """Generate a distorted grid visualization."""

    width, height = image_size
    canvas = np.full((height, width, 3), 18, dtype=np.uint8)
    ideal_color = (50, 50, 50)
    distorted_color = (66, 214, 255)

    for x in range(0, width, grid_spacing):
        cv2.line(canvas, (x, 0), (x, height - 1), ideal_color, 1, cv2.LINE_AA)
    for y in range(0, height, grid_spacing):
        cv2.line(canvas, (0, y), (width - 1, y), ideal_color, 1, cv2.LINE_AA)

    for x in range(0, width, grid_spacing):
        line = np.array([[x, y] for y in range(0, height, max(4, grid_spacing // 4))], dtype=np.float32)
        warped = distort_points(line, point, image_size).astype(np.int32)
        cv2.polylines(canvas, [warped], False, distorted_color, 1, cv2.LINE_AA)

    for y in range(0, height, grid_spacing):
        line = np.array([[x, y] for x in range(0, width, max(4, grid_spacing // 4))], dtype=np.float32)
        warped = distort_points(line, point, image_size).astype(np.int32)
        cv2.polylines(canvas, [warped], False, distorted_color, 1, cv2.LINE_AA)

    cv2.putText(
        canvas,
        "Ideal grid (gray) vs distorted grid (cyan)",
        (20, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (220, 220, 220),
        2,
        cv2.LINE_AA,
    )
    return canvas


def generate_barrel_pincushion_visualization(
    point: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Visualize radial displacement magnitude and direction."""

    width, height = image_size
    sample_x = np.linspace(0, width - 1, 96, dtype=np.float32)
    sample_y = np.linspace(0, height - 1, 96, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(sample_x, sample_y)
    ideal = np.stack([grid_x, grid_y], axis=-1).reshape(-1, 2)
    warped = distort_points(ideal, point, image_size)

    center = np.array([width * point.cx, height * point.cy], dtype=np.float32)
    radial_before = np.linalg.norm(ideal - center, axis=1)
    radial_after = np.linalg.norm(warped - center, axis=1)
    delta = (radial_after - radial_before).reshape(96, 96)

    magnitude = np.abs(delta)
    if float(magnitude.max()) > 0:
        magnitude = magnitude / float(magnitude.max())
    heat = (magnitude * 255.0).astype(np.uint8)
    color = cv2.applyColorMap(heat, cv2.COLORMAP_TURBO)
    color[delta < 0] = color[delta < 0][:, ::-1]
    return cv2.resize(color, (width, height), interpolation=cv2.INTER_LINEAR)


def compute_coverage_heatmap(
    diagnostics: CalibrationDiagnostics,
    image_size: tuple[int, int],
    bins: tuple[int, int] = (32, 32),
) -> np.ndarray:
    """Create a simple sensor coverage heatmap from detected points."""

    width, height = image_size
    heatmap = np.zeros((bins[1], bins[0]), dtype=np.float32)
    for result in diagnostics.image_results:
        for x_norm, y_norm in result.coverage_points:
            x_idx = min(int(x_norm * bins[0]), bins[0] - 1)
            y_idx = min(int(y_norm * bins[1]), bins[1] - 1)
            heatmap[y_idx, x_idx] += 1.0

    if float(heatmap.max()) > 0:
        heatmap /= float(heatmap.max())
    heatmap_u8 = (heatmap * 255.0).astype(np.uint8)
    color = cv2.applyColorMap(heatmap_u8, cv2.COLORMAP_INFERNO)
    return cv2.resize(color, (width, height), interpolation=cv2.INTER_NEAREST)


def accuracy_grade(rms_error: float) -> str:
    if rms_error < 0.3:
        return "VP-Ready (<0.3px)"
    if rms_error < 0.5:
        return "Good (<0.5px)"
    if rms_error < 1.0:
        return "Acceptable (<1.0px)"
    return "Poor"


def estimate_nodal_offset(
    rvecs: list[np.ndarray],
    tvecs: list[np.ndarray],
    focal_length_mm: float = 50.0,
) -> NodalOffset:
    """Estimate nodal offset from translation vectors."""

    translations = np.array([t.flatten() for t in tvecs], dtype=np.float32)
    avg_t = np.mean(translations, axis=0)
    return NodalOffset(
        focal_length_mm=focal_length_mm,
        offset_x=float(avg_t[0]),
        offset_y=float(avg_t[1]),
        offset_z=float(avg_t[2]),
        confidence=0.25,
        method="pose-average",
    )


def estimate_nodal_from_parallax(
    images: list[np.ndarray],
    rotation_angles_deg: list[float],
    near_object_distance_m: float = 1.0,
    far_object_distance_m: float = 3.0,
) -> NodalOffset:
    """Estimate entrance pupil position from a rough parallax test image set."""

    if len(images) < 2 or len(images) != len(rotation_angles_deg):
        raise ValueError("Provide matching image and rotation-angle lists.")

    orb = cv2.ORB_create(nfeatures=1500)
    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    shifts: list[float] = []
    angle_terms: list[float] = []
    match_counts: list[int] = []

    for index in range(len(images) - 1):
        gray_a = cv2.cvtColor(images[index], cv2.COLOR_BGR2GRAY) if images[index].ndim == 3 else images[index]
        gray_b = (
            cv2.cvtColor(images[index + 1], cv2.COLOR_BGR2GRAY)
            if images[index + 1].ndim == 3
            else images[index + 1]
        )
        keypoints_a, descriptors_a = orb.detectAndCompute(gray_a, None)
        keypoints_b, descriptors_b = orb.detectAndCompute(gray_b, None)
        if descriptors_a is None or descriptors_b is None or not keypoints_a or not keypoints_b:
            continue

        matches = matcher.match(descriptors_a, descriptors_b)
        if len(matches) < 12:
            continue
        matches = sorted(matches, key=lambda match: match.distance)[:200]
        deltas = np.array(
            [
                keypoints_b[match.trainIdx].pt[0] - keypoints_a[match.queryIdx].pt[0]
                for match in matches
            ],
            dtype=np.float32,
        )
        shift_px = float(np.median(deltas))
        angle_a = math.radians(rotation_angles_deg[index])
        angle_b = math.radians(rotation_angles_deg[index + 1])
        angle_term = abs(math.sin(angle_b) - math.sin(angle_a))
        if angle_term <= 1e-6:
            continue
        shifts.append(shift_px)
        angle_terms.append(angle_term)
        match_counts.append(len(matches))

    if len(shifts) < 2:
        return NodalOffset(focal_length_mm=0.0, confidence=0.0, method="parallax-insufficient")

    shifts_np = np.asarray(shifts, dtype=np.float32)
    angle_np = np.asarray(angle_terms, dtype=np.float32)
    slope = float(np.dot(angle_np, shifts_np) / max(np.dot(angle_np, angle_np), 1e-6))
    baseline_term = max((1.0 / max(near_object_distance_m, 1e-3)) - (1.0 / max(far_object_distance_m, 1e-3)), 1e-6)
    estimated_offset_m = abs(slope) / max(2000.0 * baseline_term, 1e-6)
    residuals = shifts_np - slope * angle_np
    residual_std = float(np.std(residuals)) if len(residuals) > 1 else 0.0
    coverage_score = min(float(np.mean(match_counts)) / 80.0, 1.0)
    residual_score = max(0.0, 1.0 - residual_std / 10.0)
    confidence = max(0.0, min(1.0, 0.55 * coverage_score + 0.45 * residual_score))

    return NodalOffset(
        focal_length_mm=0.0,
        offset_z=float(estimated_offset_m * 1000.0),
        rotation_y=float(np.mean(rotation_angles_deg)),
        confidence=confidence,
        method="parallax-estimate",
    )

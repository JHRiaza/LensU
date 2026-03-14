"""LensU core calibration and visualization helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import cv2
import numpy as np


LENSU_VERSION = "Sprint1"


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


@dataclass
class LensProfile:
    """Complete lens calibration profile."""

    lens_name: str = "Unknown Lens"
    sensor_width_mm: float = 36.0
    sensor_height_mm: float = 24.0
    image_width: int = 1920
    image_height: int = 1080
    calibration_points: list[CalibrationPoint] = field(default_factory=list)
    nodal_offsets: list[NodalOffset] = field(default_factory=list)

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

    def to_dict(self) -> dict:
        return asdict(self)

    def save_json(self, path: Path) -> None:
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
        for point in data.get("calibration_points", []):
            profile.calibration_points.append(CalibrationPoint(**point))
        for offset in data.get("nodal_offsets", []):
            profile.nodal_offsets.append(NodalOffset(**offset))
        return profile


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


def aruco_available() -> bool:
    return hasattr(cv2, "aruco")


def _decode_image(image_path: Path) -> Optional[np.ndarray]:
    return cv2.imread(str(image_path))


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
    image_sizes: list[tuple[int, int]] = []
    diagnostics = CalibrationDiagnostics(image_size=None)

    for path in image_paths:
        img = _decode_image(path)
        if img is None:
            diagnostics.image_results.append(
                CalibrationImageResult(image_name=path.name, used=False, detection_mode="Checkerboard")
            )
            continue

        current_size = (img.shape[1], img.shape[0])
        image_sizes.append(current_size)
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

    return np.array([[point.k1, point.k2, point.p1, point.p2, point.k3]], dtype=np.float32)


def normalized_focal_lengths(point: CalibrationPoint, image_size: tuple[int, int]) -> tuple[float, float]:
    width, height = image_size
    return float(point.fx / width), float(point.fy / height)


def undistort_image(
    image: np.ndarray,
    point: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Apply undistortion using calibration data."""

    camera_matrix = reconstruct_camera_matrix(point, image_size)
    dist_coeffs = reconstruct_dist_coeffs(point)
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

    cv2.putText(canvas, "Ideal grid (gray) vs distorted grid (cyan)", (20, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (220, 220, 220), 2, cv2.LINE_AA)
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
    )

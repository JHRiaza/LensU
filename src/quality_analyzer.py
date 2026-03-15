"""Advanced calibration quality analysis helpers."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

try:
    from .calibration import (
        CalibrationPoint,
        _create_checkerboard_object_points,
        detect_checkerboard,
        reconstruct_camera_matrix,
        reconstruct_dist_coeffs,
    )
except ImportError:
    from calibration import (
        CalibrationPoint,
        _create_checkerboard_object_points,
        detect_checkerboard,
        reconstruct_camera_matrix,
        reconstruct_dist_coeffs,
    )


def _pairwise_mean_angle(vectors: list[np.ndarray]) -> float:
    if len(vectors) < 2:
        return 0.0
    angles: list[float] = []
    for index, first in enumerate(vectors[:-1]):
        for second in vectors[index + 1 :]:
            dot = float(np.clip(np.dot(first, second), -1.0, 1.0))
            angles.append(math.degrees(math.acos(dot)))
    return float(np.mean(angles)) if angles else 0.0


def _coverage_quadrants(points_norm: list[tuple[float, float]]) -> dict[str, float]:
    counts = {"NW": 0.0, "NE": 0.0, "SW": 0.0, "SE": 0.0, "Center": 0.0}
    if not points_norm:
        return counts

    for x_norm, y_norm in points_norm:
        if 0.33 <= x_norm <= 0.67 and 0.33 <= y_norm <= 0.67:
            counts["Center"] += 1.0
            continue
        if x_norm < 0.5 and y_norm < 0.5:
            counts["NW"] += 1.0
        elif x_norm >= 0.5 and y_norm < 0.5:
            counts["NE"] += 1.0
        elif x_norm < 0.5 and y_norm >= 0.5:
            counts["SW"] += 1.0
        else:
            counts["SE"] += 1.0

    total = float(len(points_norm))
    return {name: round(value / total, 4) for name, value in counts.items()}


def _coverage_score(points_norm: list[tuple[float, float]], bins: tuple[int, int] = (8, 6)) -> float:
    if not points_norm:
        return 0.0
    occupied = np.zeros((bins[1], bins[0]), dtype=bool)
    for x_norm, y_norm in points_norm:
        x_idx = min(int(x_norm * bins[0]), bins[0] - 1)
        y_idx = min(int(y_norm * bins[1]), bins[1] - 1)
        occupied[y_idx, x_idx] = True
    return float(occupied.mean())


def _grade_quality(
    rms_error: float,
    coverage_score: float,
    angle_diversity: float,
    outlier_count: int,
    max_error_px: float,
) -> str:
    if (
        rms_error <= 0.35
        and coverage_score >= 0.7
        and angle_diversity >= 0.55
        and outlier_count == 0
        and max_error_px <= 1.0
    ):
        return "VP-Ready"
    if rms_error <= 0.5 and coverage_score >= 0.55 and angle_diversity >= 0.4 and outlier_count <= 1:
        return "Good"
    if rms_error <= 1.0 and coverage_score >= 0.35:
        return "Acceptable"
    return "Poor"


def _recommendations(
    image_paths: list[Path],
    per_image_rms: list[float],
    coverage_score: float,
    quadrants: dict[str, float],
    angle_diversity: float,
    outlier_images: list[int],
    systematic: dict,
) -> list[str]:
    recommendations: list[str] = []
    if len(per_image_rms) < max(4, min(8, len(image_paths))):
        recommendations.append("Capture more usable frames; at least 6-10 clean checkerboard detections is a safer target.")
    if coverage_score < 0.55:
        recommendations.append("Move the checkerboard into the corners and edges to improve full-sensor coverage.")
    quadrant_floor = min((quadrants.get(name, 0.0) for name in ("NW", "NE", "SW", "SE")), default=0.0)
    if quadrant_floor < 0.12:
        recommendations.append("Balance captures across all four quadrants instead of clustering near one side of the frame.")
    if angle_diversity < 0.35:
        recommendations.append("Add stronger pitch, roll, and yaw changes between frames to improve pose diversity.")
    if outlier_images:
        recommendations.append(
            "Review or exclude the highest-error frames: "
            + ", ".join(str(index) for index in outlier_images[:5])
            + "."
        )
    if systematic["focus_error"]["detected"]:
        recommendations.append("Check focus consistency and board flatness; tangential distortion is unusually high.")
    if systematic["sample_bias"]["detected"]:
        recommendations.append("Reshoot with more varied angles and board positions; the current set is too repetitive.")
    if not recommendations:
        recommendations.append("Calibration quality is balanced. Keep this capture pattern as your baseline.")
    return recommendations


def _project_reprojection_error(
    corners: np.ndarray,
    object_points: np.ndarray,
    point: CalibrationPoint,
    image_size: tuple[int, int],
) -> tuple[float, float, np.ndarray] | None:
    camera_matrix = reconstruct_camera_matrix(point, image_size)
    dist_coeffs = reconstruct_dist_coeffs(point)
    ok, rvec, tvec = cv2.solvePnP(object_points, corners, camera_matrix, dist_coeffs)
    if not ok:
        return None
    projected, _ = cv2.projectPoints(object_points, rvec, tvec, camera_matrix, dist_coeffs)
    errors = np.linalg.norm(corners.reshape(-1, 2) - projected.reshape(-1, 2), axis=1)
    rotation, _ = cv2.Rodrigues(rvec)
    board_normal = rotation @ np.array([0.0, 0.0, 1.0], dtype=np.float64)
    board_normal /= max(float(np.linalg.norm(board_normal)), 1e-9)
    rms = float(np.sqrt(np.mean(np.square(errors))))
    return rms, float(errors.max(initial=0.0)), board_normal.astype(np.float32)


def _detected_corner_sets(
    image_paths: list[Path],
    pattern_size: tuple[int, int],
) -> tuple[list[np.ndarray], tuple[int, int] | None]:
    detections: list[np.ndarray] = []
    image_size: tuple[int, int] | None = None
    for image_path in image_paths:
        image = cv2.imread(str(image_path))
        if image is None:
            continue
        image_size = image_size or (image.shape[1], image.shape[0])
        found, corners, _ = detect_checkerboard(image, pattern_size=pattern_size)
        if found and corners is not None:
            detections.append(corners)
    return detections, image_size


def analyze_calibration_quality(
    image_paths: list[Path],
    calibration_point: CalibrationPoint,
    pattern_size: tuple[int, int] = (9, 6),
) -> dict:
    """Comprehensive calibration quality analysis."""

    detections, image_size = _detected_corner_sets(image_paths, pattern_size)
    per_image_rms: list[float] = []
    max_error_px = 0.0
    normals: list[np.ndarray] = []
    points_norm: list[tuple[float, float]] = []

    if image_size is not None:
        width, height = image_size
        object_points = _create_checkerboard_object_points(pattern_size, 1.0)
        for corners in detections:
            points_norm.extend((float(x / width), float(y / height)) for x, y in corners.reshape(-1, 2))
            projected = _project_reprojection_error(corners, object_points, calibration_point, image_size)
            if projected is None:
                continue
            rms, image_max_error, normal = projected
            per_image_rms.append(rms)
            max_error_px = max(max_error_px, image_max_error)
            normals.append(normal)

    coverage_score = _coverage_score(points_norm)
    quadrants = _coverage_quadrants(points_norm)
    mean_angle = _pairwise_mean_angle(normals)
    angle_diversity = float(np.clip(mean_angle / 35.0, 0.0, 1.0))
    mean_rms = float(np.mean(per_image_rms)) if per_image_rms else 0.0
    outlier_images = [
        index for index, value in enumerate(per_image_rms) if mean_rms > 0.0 and value > (2.0 * mean_rms)
    ]
    systematic = detect_systematic_error(calibration_point, image_paths, pattern_size)
    overall_grade = _grade_quality(
        calibration_point.rms_error,
        coverage_score,
        angle_diversity,
        len(outlier_images),
        max_error_px,
    )

    return {
        "rms_error": float(calibration_point.rms_error),
        "per_image_rms": [float(value) for value in per_image_rms],
        "max_error_px": float(max_error_px),
        "coverage_score": float(coverage_score),
        "coverage_quadrants": quadrants,
        "angle_diversity": float(angle_diversity),
        "outlier_images": outlier_images,
        "overall_grade": overall_grade,
        "recommendations": _recommendations(
            image_paths,
            per_image_rms,
            coverage_score,
            quadrants,
            angle_diversity,
            outlier_images,
            systematic,
        ),
    }


def generate_coverage_heatmap(
    image_paths: list[Path],
    pattern_size: tuple[int, int],
    image_size: tuple[int, int],
) -> np.ndarray:
    """Generate a heatmap image showing where checkerboard corners were detected."""

    width, height = image_size
    heat = np.zeros((height, width), dtype=np.float32)
    radius = max(6, min(width, height) // 30)

    detections, _ = _detected_corner_sets(image_paths, pattern_size)
    for corners in detections:
        for x_pos, y_pos in corners.reshape(-1, 2):
            cv2.circle(heat, (int(round(x_pos)), int(round(y_pos))), radius, 1.0, thickness=-1)

    if float(heat.max()) > 0:
        heat = cv2.GaussianBlur(heat, (0, 0), sigmaX=radius * 0.6, sigmaY=radius * 0.6)
        heat /= float(heat.max())
    heat_u8 = (heat * 255.0).astype(np.uint8)
    color = cv2.applyColorMap(heat_u8, cv2.COLORMAP_TURBO)
    overlay = cv2.addWeighted(np.full_like(color, 18), 0.35, color, 0.9, 0.0)
    return overlay


def detect_systematic_error(
    calibration_point: CalibrationPoint,
    image_paths: list[Path],
    pattern_size: tuple[int, int],
) -> dict:
    """Detect systematic errors in calibration."""

    detections, image_size = _detected_corner_sets(image_paths, pattern_size)
    points_norm: list[tuple[float, float]] = []
    normals: list[np.ndarray] = []
    quadrant_values = {"NW": 0.0, "NE": 0.0, "SW": 0.0, "SE": 0.0, "Center": 0.0}

    if image_size is not None:
        width, height = image_size
        object_points = _create_checkerboard_object_points(pattern_size, 1.0)
        for corners in detections:
            points_norm.extend((float(x / width), float(y / height)) for x, y in corners.reshape(-1, 2))
            projected = _project_reprojection_error(corners, object_points, calibration_point, image_size)
            if projected is not None:
                _, _, normal = projected
                normals.append(normal)
        quadrant_values = _coverage_quadrants(points_norm)

    center_offset = float(math.hypot(calibration_point.cx - 0.5, calibration_point.cy - 0.5))
    tangential_magnitude = float(math.hypot(calibration_point.p1, calibration_point.p2))
    diagonal_bias = abs(quadrant_values["NW"] + quadrant_values["SE"] - quadrant_values["NE"] - quadrant_values["SW"])
    angle_diversity = float(np.clip(_pairwise_mean_angle(normals) / 35.0, 0.0, 1.0))
    sample_bias_score = max(0.0, 1.0 - max(angle_diversity, _coverage_score(points_norm)))

    return {
        "tilted_sensor": {
            "detected": center_offset > 0.03,
            "severity": round(min(center_offset / 0.08, 1.0), 4),
            "details": "Principal point is materially offset from image center." if center_offset > 0.03 else "No strong principal-point asymmetry detected.",
        },
        "decentered_lens_element": {
            "detected": diagonal_bias > 0.18 or tangential_magnitude > 0.003,
            "severity": round(min(max(diagonal_bias, tangential_magnitude * 120.0), 1.0), 4),
            "details": "Tangential distortion or diagonal imbalance suggests asymmetric lens behavior." if diagonal_bias > 0.18 or tangential_magnitude > 0.003 else "No strong asymmetry pattern detected.",
        },
        "focus_error": {
            "detected": tangential_magnitude > 0.002,
            "severity": round(min(tangential_magnitude / 0.006, 1.0), 4),
            "details": "Tangential terms are high enough to justify checking focus consistency and board flatness." if tangential_magnitude > 0.002 else "Tangential terms are within a normal range.",
        },
        "sample_bias": {
            "detected": sample_bias_score > 0.45,
            "severity": round(min(sample_bias_score, 1.0), 4),
            "details": "Detected captures cluster around similar positions or orientations." if sample_bias_score > 0.45 else "Pose and coverage diversity are reasonably balanced.",
        },
    }

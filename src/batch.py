"""Batch calibration helpers."""

from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

try:
    from .calibration import (
        CalibrationImageResult,
        CalibrationDiagnostics,
        CalibrationPoint,
        LensProfile,
        calibrate_anamorphic_detailed,
        calibrate_fisheye,
        calibrate_from_charuco_images,
        calibrate_from_images,
    )
    from .video_extractor import extract_frames_from_video
    from .temp_paths import lensu_tempdir
except ImportError:
    from calibration import (
        CalibrationImageResult,
        CalibrationDiagnostics,
        CalibrationPoint,
        LensProfile,
        calibrate_anamorphic_detailed,
        calibrate_fisheye,
        calibrate_from_charuco_images,
        calibrate_from_images,
    )
    from video_extractor import extract_frames_from_video
    from temp_paths import lensu_tempdir


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".mxf", ".wmv", ".m4v"}


@dataclass
class BatchFolderResult:
    focal_length_mm: float
    folder_name: str
    source_count: int
    used_count: int
    success: bool
    rms_error: float = 0.0
    error: str = ""
    detection_mode: str = "checkerboard"


ProgressCallback = Callable[[int, int, BatchFolderResult], None]


def _extract_focal_length(name: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)", name)
    if not match:
        return None
    return float(match.group(1))


def _iter_focal_subfolders(base_dir: Path) -> list[tuple[float, Path]]:
    if not base_dir.exists() or not base_dir.is_dir():
        raise FileNotFoundError(f"Base directory does not exist: {base_dir}")
    subfolders: list[tuple[float, Path]] = []
    for path in sorted(base_dir.iterdir()):
        if not path.is_dir():
            continue
        focal = _extract_focal_length(path.name)
        if focal is None:
            continue
        subfolders.append((focal, path))
    if not subfolders:
        raise ValueError("No focal-length subfolders found. Expected names like 24mm, 35, FL50.")
    subfolders.sort(key=lambda item: item[0])
    return subfolders


def _calibrate_folder(
    focal_length_mm: float,
    folder: Path,
    pattern_size: tuple[int, int],
    square_size_mm: float,
    detection_mode: str,
    anamorphic_enabled: bool = False,
    fisheye_enabled: bool = False,
    squeeze_ratio: float = 2.0,
    anamorphic_desqueezed: bool = False,
) -> tuple[CalibrationPoint | None, CalibrationDiagnostics, int]:
    image_paths = [
        path for path in sorted(folder.iterdir()) if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    if not image_paths:
        return None, CalibrationDiagnostics(image_size=None), 0

    if fisheye_enabled:
        first_image = image_paths[0]
        point, used_flags = calibrate_fisheye(
            image_paths,
            pattern_size=pattern_size,
            square_size_mm=square_size_mm,
            focal_length_mm=focal_length_mm,
        )
        diagnostics = CalibrationDiagnostics(image_size=None)
        try:
            import cv2

            image = cv2.imread(str(first_image))
            if image is not None:
                diagnostics.image_size = (image.shape[1], image.shape[0])
        except Exception:
            pass
        diagnostics.image_results = [
            CalibrationImageResult(
                image_name=path.name,
                used=used,
                detection_mode="Fisheye Checkerboard",
            )
            for path, used in zip(image_paths, used_flags)
        ]
        return point, diagnostics, len(image_paths)

    if anamorphic_enabled and detection_mode.lower() != "charuco":
        point, diagnostics, _ = calibrate_anamorphic_detailed(
            image_paths,
            pattern_size=pattern_size,
            square_size_mm=square_size_mm,
            focal_length_mm=focal_length_mm,
            squeeze_ratio=squeeze_ratio,
            desqueezed=anamorphic_desqueezed,
        )
        return point, diagnostics, len(image_paths)

    if detection_mode.lower() == "charuco":
        marker_length = square_size_mm * 0.75
        return (
            *calibrate_from_charuco_images(
                image_paths,
                board_size=pattern_size,
                square_length_mm=square_size_mm,
                marker_length_mm=marker_length,
                focal_length_mm=focal_length_mm,
            ),
            len(image_paths),
        )

    return (
        *calibrate_from_images(
            image_paths,
            pattern_size=pattern_size,
            square_size_mm=square_size_mm,
            focal_length_mm=focal_length_mm,
        ),
        len(image_paths),
    )


def batch_calibrate_detailed(
    base_dir: Path,
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    detection_mode: str = "checkerboard",
    sensor_width_mm: float = 36.0,
    sensor_height_mm: float = 24.0,
    progress_callback: ProgressCallback | None = None,
    anamorphic_enabled: bool = False,
    fisheye_enabled: bool = False,
    squeeze_ratio: float = 2.0,
    anamorphic_desqueezed: bool = False,
) -> tuple[LensProfile, list[BatchFolderResult]]:
    """Batch calibrate from focal-length subfolders and return detailed results."""

    profile = LensProfile(
        lens_name=base_dir.name or "Batch Lens",
        sensor_width_mm=sensor_width_mm,
        sensor_height_mm=sensor_height_mm,
    )
    results: list[BatchFolderResult] = []
    subfolders = _iter_focal_subfolders(base_dir)

    for index, (focal_length, folder) in enumerate(subfolders, start=1):
        point, diagnostics, source_count = _calibrate_folder(
            focal_length,
            folder,
            pattern_size,
            square_size_mm,
            detection_mode,
            anamorphic_enabled=anamorphic_enabled,
            fisheye_enabled=fisheye_enabled,
            squeeze_ratio=squeeze_ratio,
            anamorphic_desqueezed=anamorphic_desqueezed,
        )
        used_count = sum(1 for item in diagnostics.image_results if item.used)
        if point is None:
            result = BatchFolderResult(
                focal_length_mm=focal_length,
                folder_name=folder.name,
                source_count=source_count,
                used_count=used_count,
                success=False,
                error="Calibration failed or not enough valid detections.",
                detection_mode=detection_mode,
            )
        else:
            profile.add_calibration(point)
            if diagnostics.image_size:
                profile.image_width, profile.image_height = diagnostics.image_size
            result = BatchFolderResult(
                focal_length_mm=focal_length,
                folder_name=folder.name,
                source_count=source_count,
                used_count=used_count,
                success=True,
                rms_error=point.rms_error,
                detection_mode=detection_mode,
            )
        results.append(result)
        if progress_callback is not None:
            progress_callback(index, len(subfolders), result)

    return profile, results


def batch_calibrate(
    base_dir: Path,
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    detection_mode: str = "checkerboard",
    sensor_width_mm: float = 36.0,
    sensor_height_mm: float = 24.0,
    anamorphic_enabled: bool = False,
    fisheye_enabled: bool = False,
    squeeze_ratio: float = 2.0,
    anamorphic_desqueezed: bool = False,
) -> LensProfile:
    """Batch calibrate from a folder structure and return a combined LensProfile."""

    profile, _ = batch_calibrate_detailed(
        base_dir=base_dir,
        pattern_size=pattern_size,
        square_size_mm=square_size_mm,
        detection_mode=detection_mode,
        sensor_width_mm=sensor_width_mm,
        sensor_height_mm=sensor_height_mm,
        anamorphic_enabled=anamorphic_enabled,
        fisheye_enabled=fisheye_enabled,
        squeeze_ratio=squeeze_ratio,
        anamorphic_desqueezed=anamorphic_desqueezed,
    )
    if not profile.calibration_points:
        raise RuntimeError("Batch calibration completed with no successful focal lengths.")
    return profile


def batch_calibrate_from_videos(
    base_dir: Path,
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    max_frames_per_video: int = 30,
    **kwargs,
) -> LensProfile:
    """Batch calibrate from focal-length folders that contain one video each."""

    detection_mode = str(kwargs.get("detection_mode", "checkerboard"))
    sensor_width_mm = float(kwargs.get("sensor_width_mm", 36.0))
    sensor_height_mm = float(kwargs.get("sensor_height_mm", 24.0))
    profile = LensProfile(
        lens_name=base_dir.name or "Batch Lens",
        sensor_width_mm=sensor_width_mm,
        sensor_height_mm=sensor_height_mm,
    )
    subfolders = _iter_focal_subfolders(base_dir)

    for focal_length, folder in subfolders:
        video_files = [
            path for path in sorted(folder.iterdir()) if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ]
        if not video_files:
            continue
        with lensu_tempdir() as tmpdir:
            frame_dir = Path(tmpdir)
            frame_paths = extract_frames_from_video(
                video_path=video_files[0],
                output_dir=frame_dir,
                interval_seconds=1.0,
                max_frames=max_frames_per_video,
            )
            if not frame_paths:
                continue
            if detection_mode.lower() == "charuco":
                marker_length = square_size_mm * 0.75
                point, diagnostics = calibrate_from_charuco_images(
                    frame_paths,
                    board_size=pattern_size,
                    square_length_mm=square_size_mm,
                    marker_length_mm=marker_length,
                    focal_length_mm=focal_length,
                )
            else:
                point, diagnostics = calibrate_from_images(
                    frame_paths,
                    pattern_size=pattern_size,
                    square_size_mm=square_size_mm,
                    focal_length_mm=focal_length,
                )
            if point is not None:
                profile.add_calibration(point)
                if diagnostics.image_size:
                    profile.image_width, profile.image_height = diagnostics.image_size

    if not profile.calibration_points:
        raise RuntimeError("Batch video calibration completed with no successful focal lengths.")
    return profile

"""Video frame extraction helpers for LensU."""

from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from calibration import detect_checkerboard


def _laplacian_variance(image: np.ndarray) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _open_video(video_path: Path) -> cv2.VideoCapture | None:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        return None
    return capture


def _frame_count(capture: cv2.VideoCapture) -> int:
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    return max(total, 0)


def _fps(capture: cv2.VideoCapture) -> float:
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    return fps if fps > 0 else 24.0


def _save_frame(output_dir: Path, index: int, frame_number: int, frame: np.ndarray) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"frame_{index:03d}_{frame_number:06d}.png"
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"Failed to save extracted frame: {path}")
    return path


def _checkerboard_coverage(corners: np.ndarray, frame_shape: tuple[int, int, int]) -> float:
    width = float(frame_shape[1])
    height = float(frame_shape[0])
    rect = cv2.minAreaRect(corners.astype(np.float32))
    area = rect[1][0] * rect[1][1]
    return float(area / (width * height)) if width and height else 0.0


def _checkerboard_angle(corners: np.ndarray, pattern_size: tuple[int, int]) -> float:
    cols = int(pattern_size[0])
    if len(corners) < cols:
        return 0.0
    first = corners[0, 0]
    last = corners[cols - 1, 0]
    angle = math.degrees(math.atan2(float(last[1] - first[1]), float(last[0] - first[0])))
    return (angle + 180.0) % 180.0


def extract_frames_from_video(
    video_path: Path,
    output_dir: Path,
    interval_seconds: float = 1.0,
    max_frames: int = 50,
    min_blur_threshold: float = 100.0,
) -> list[Path]:
    """Extract sharp frames from a video at regular intervals."""

    if interval_seconds <= 0 or max_frames <= 0:
        return []
    if not video_path.exists():
        return []

    capture = _open_video(video_path)
    if capture is None:
        return []

    saved_paths: list[Path] = []
    try:
        fps = _fps(capture)
        frame_step = max(int(round(interval_seconds * fps)), 1)
        total_frames = _frame_count(capture)
        candidate_frames = range(0, total_frames, frame_step) if total_frames else range(max_frames * frame_step)

        for frame_number in candidate_frames:
            if len(saved_paths) >= max_frames:
                break
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            if _laplacian_variance(frame) < min_blur_threshold:
                continue
            saved_paths.append(_save_frame(output_dir, len(saved_paths), frame_number, frame))
    finally:
        capture.release()

    return saved_paths


def extract_frames_with_checkerboard(
    video_path: Path,
    output_dir: Path,
    pattern_size: tuple[int, int] = (9, 6),
    max_frames: int = 30,
    min_coverage: float = 0.3,
    min_angle_diff: float = 10.0,
) -> list[Path]:
    """Smart extraction that keeps only diverse checkerboard frames."""

    if max_frames <= 0 or min_coverage < 0:
        return []
    if not video_path.exists():
        return []

    capture = _open_video(video_path)
    if capture is None:
        return []

    saved_paths: list[Path] = []
    kept_angles: list[float] = []
    kept_centers: list[tuple[float, float]] = []
    min_blur_threshold = 100.0

    try:
        total_frames = _frame_count(capture)
        sample_stride = max(total_frames // max(max_frames * 12, 1), 1) if total_frames else 5
        candidate_frames = range(0, total_frames, sample_stride) if total_frames else range(max_frames * sample_stride * 2)

        for frame_number in candidate_frames:
            if len(saved_paths) >= max_frames:
                break
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, frame = capture.read()
            if not ok or frame is None:
                continue
            if _laplacian_variance(frame) < min_blur_threshold:
                continue

            found, corners, _ = detect_checkerboard(frame, pattern_size)
            if not found or corners is None:
                continue

            coverage = _checkerboard_coverage(corners, frame.shape)
            if coverage < min_coverage:
                continue

            angle = _checkerboard_angle(corners, pattern_size)
            center = tuple(np.mean(corners[:, 0, :], axis=0).tolist())
            center_norm = (center[0] / frame.shape[1], center[1] / frame.shape[0])

            angle_is_new = not kept_angles or min(
                min(abs(angle - existing), 180.0 - abs(angle - existing)) for existing in kept_angles
            ) >= min_angle_diff
            coverage_is_new = not kept_centers or min(
                math.dist(center_norm, existing_center) for existing_center in kept_centers
            ) >= 0.1

            if not angle_is_new and not coverage_is_new:
                continue

            saved_paths.append(_save_frame(output_dir, len(saved_paths), frame_number, frame))
            kept_angles.append(angle)
            kept_centers.append(center_norm)
    finally:
        capture.release()

    return saved_paths

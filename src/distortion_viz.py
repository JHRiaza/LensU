"""Publication-oriented distortion visualization helpers."""

from __future__ import annotations

import cv2
import numpy as np

try:
    from .calibration import CalibrationPoint, distort_points
except ImportError:
    from calibration import CalibrationPoint, distort_points


def _label_image(image: np.ndarray, title: str, subtitle: str = "") -> np.ndarray:
    labeled = image.copy()
    cv2.putText(labeled, title, (24, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (24, 24, 24), 3, cv2.LINE_AA)
    cv2.putText(labeled, title, (24, 36), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (245, 245, 245), 1, cv2.LINE_AA)
    if subtitle:
        cv2.putText(labeled, subtitle, (24, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1, cv2.LINE_AA)
    return labeled


def _displacement_field(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    samples_x: int,
    samples_y: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    width, height = image_size
    xs = np.linspace(0, width - 1, samples_x, dtype=np.float32)
    ys = np.linspace(0, height - 1, samples_y, dtype=np.float32)
    grid_x, grid_y = np.meshgrid(xs, ys)
    ideal = np.stack([grid_x, grid_y], axis=-1).reshape(-1, 2)
    distorted = distort_points(ideal, point, image_size)
    displacement = distorted - ideal
    return ideal, distorted, displacement


def render_distortion_grid(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    grid_density: int = 20,
    scale_factor: float = 1.0,
) -> np.ndarray:
    """Render a distortion grid showing how straight lines bend."""

    width, height = image_size
    canvas = np.full((height, width, 3), 245, dtype=np.uint8)
    ideal_color = (220, 110, 50)
    distorted_color = (60, 60, 220)
    spacing_x = max(int(round(width / max(grid_density, 2))), 24)
    spacing_y = max(int(round(height / max(grid_density, 2))), 24)
    sample_step = max(6, min(spacing_x, spacing_y) // 5)

    for x_pos in range(0, width, spacing_x):
        cv2.line(canvas, (x_pos, 0), (x_pos, height - 1), ideal_color, 1, cv2.LINE_AA)
    for y_pos in range(0, height, spacing_y):
        cv2.line(canvas, (0, y_pos), (width - 1, y_pos), ideal_color, 1, cv2.LINE_AA)

    for x_pos in range(0, width, spacing_x):
        ideal_line = np.array([[x_pos, y] for y in range(0, height, sample_step)], dtype=np.float32)
        warped = distort_points(ideal_line, point, image_size)
        if scale_factor != 1.0:
            warped = ideal_line + (warped - ideal_line) * float(scale_factor)
        cv2.polylines(canvas, [warped.astype(np.int32)], False, distorted_color, 2, cv2.LINE_AA)

    for y_pos in range(0, height, spacing_y):
        ideal_line = np.array([[x, y_pos] for x in range(0, width, sample_step)], dtype=np.float32)
        warped = distort_points(ideal_line, point, image_size)
        if scale_factor != 1.0:
            warped = ideal_line + (warped - ideal_line) * float(scale_factor)
        cv2.polylines(canvas, [warped.astype(np.int32)], False, distorted_color, 2, cv2.LINE_AA)

    return _label_image(canvas, "Distortion Grid", "Blue: ideal grid, red: distorted grid")


def render_distortion_magnitude_map(
    point: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Render a color-coded map showing distortion magnitude across the image."""

    width, height = image_size
    ideal, _, displacement = _displacement_field(point, image_size, 140, 100)
    magnitude = np.linalg.norm(displacement, axis=1).reshape(100, 140)
    max_magnitude = float(magnitude.max(initial=0.0))
    if max_magnitude > 0.0:
        magnitude = magnitude / max_magnitude
    heat_u8 = (magnitude * 255.0).astype(np.uint8)
    heat = cv2.applyColorMap(heat_u8, cv2.COLORMAP_JET)
    heat = cv2.resize(heat, (width, height), interpolation=cv2.INTER_CUBIC)

    bar_width = 28
    bar = np.linspace(255, 0, height, dtype=np.uint8).reshape(height, 1)
    bar = np.repeat(bar, bar_width, axis=1)
    bar_color = cv2.applyColorMap(bar, cv2.COLORMAP_JET)
    heat[:, width - bar_width : width] = bar_color
    cv2.putText(heat, f"{max_magnitude:.2f}px", (width - 92, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (250, 250, 250), 1, cv2.LINE_AA)
    cv2.putText(heat, "0px", (width - 56, height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (250, 250, 250), 1, cv2.LINE_AA)
    return _label_image(heat, "Distortion Magnitude", "Pixel displacement from ideal image points")


def render_distortion_vector_field(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    arrow_density: int = 15,
) -> np.ndarray:
    """Render arrows showing distortion direction and magnitude at each point."""

    width, height = image_size
    canvas = np.full((height, width, 3), 250, dtype=np.uint8)
    samples = max(arrow_density, 3)
    ideal, _, displacement = _displacement_field(point, image_size, samples, samples)
    magnitudes = np.linalg.norm(displacement, axis=1)
    max_magnitude = float(magnitudes.max(initial=0.0))

    for start, delta, magnitude in zip(ideal, displacement, magnitudes):
        start_pt = tuple(np.round(start).astype(int))
        end_pt = tuple(np.round(start + delta).astype(int))
        color_weight = int(255.0 * (magnitude / max(max_magnitude, 1e-6)))
        color = (40, max(40, 255 - color_weight), min(255, 40 + color_weight))
        cv2.arrowedLine(canvas, start_pt, end_pt, color, 1, cv2.LINE_AA, tipLength=0.25)
        cv2.circle(canvas, start_pt, 1, (90, 90, 90), thickness=-1)

    return _label_image(canvas, "Distortion Vector Field", "Arrow direction and length show displacement")


def compare_distortion_profiles(
    point_a: CalibrationPoint,
    point_b: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Render side-by-side distortion comparison of two calibration points."""

    map_a = render_distortion_magnitude_map(point_a, image_size)
    map_b = render_distortion_magnitude_map(point_b, image_size)
    height = max(map_a.shape[0], map_b.shape[0])
    divider = np.full((height, 24, 3), 235, dtype=np.uint8)
    cv2.putText(divider, "vs", (2, max(height // 2, 24)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (70, 70, 70), 1, cv2.LINE_AA)
    combined = np.hstack([map_a, divider, map_b])
    return _label_image(combined, "Profile Comparison", "Left: profile A, right: profile B")

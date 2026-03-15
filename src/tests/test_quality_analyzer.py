from __future__ import annotations

import unittest

import cv2
import numpy as np

from calibration import CalibrationPoint, calibrate_from_images
from quality_analyzer import analyze_calibration_quality, detect_systematic_error, generate_coverage_heatmap
from test_support import workspace_tempdir


def _checkerboard_image(
    pattern_size: tuple[int, int] = (9, 6),
    square_px: int = 60,
    angle_deg: float = 0.0,
    shift_x: float = 0.0,
    shift_y: float = 0.0,
    scale: float = 1.0,
) -> np.ndarray:
    cols = pattern_size[0] + 1
    rows = pattern_size[1] + 1
    board = np.ones((rows * square_px, cols * square_px), dtype=np.uint8) * 255
    for y_pos in range(rows):
        for x_pos in range(cols):
            if (x_pos + y_pos) % 2 == 0:
                cv2.rectangle(
                    board,
                    (x_pos * square_px, y_pos * square_px),
                    ((x_pos + 1) * square_px, (y_pos + 1) * square_px),
                    0,
                    thickness=-1,
                )
    board_bgr = cv2.cvtColor(board, cv2.COLOR_GRAY2BGR)
    canvas = np.full((800, 1200, 3), 200, dtype=np.uint8)
    height, width = board.shape
    transform = cv2.getRotationMatrix2D((width / 2, height / 2), angle_deg, scale)
    transform[:, 2] += [350 + shift_x, 200 + shift_y]
    return cv2.warpAffine(board_bgr, transform, (canvas.shape[1], canvas.shape[0]), borderValue=(200, 200, 200))


def _write_checkerboard_set() -> tuple[list, CalibrationPoint]:
    with workspace_tempdir() as tmpdir:
        image_paths = []
        transforms = [
            (0.0, 0.0, 0.0, 1.0),
            (8.0, 40.0, 15.0, 0.94),
            (-7.0, -55.0, 22.0, 1.05),
            (12.0, 85.0, -30.0, 0.88),
        ]
        for index, args in enumerate(transforms):
            image = _checkerboard_image(angle_deg=args[0], shift_x=args[1], shift_y=args[2], scale=args[3])
            path = tmpdir / f"board_{index}.png"
            cv2.imwrite(str(path), image)
            image_paths.append(path)
        point, _ = calibrate_from_images(image_paths)
        if point is None:
            raise AssertionError("Synthetic checkerboard set did not calibrate.")
        return list(image_paths), point


class QualityAnalyzerTests(unittest.TestCase):
    def test_quality_analysis_returns_expected_fields(self):
        with workspace_tempdir() as tmpdir:
            image_paths = []
            transforms = [
                (0.0, 0.0, 0.0, 1.0),
                (8.0, 40.0, 15.0, 0.94),
                (-7.0, -55.0, 22.0, 1.05),
                (12.0, 85.0, -30.0, 0.88),
            ]
            for index, args in enumerate(transforms):
                image = _checkerboard_image(angle_deg=args[0], shift_x=args[1], shift_y=args[2], scale=args[3])
                path = tmpdir / f"board_{index}.png"
                cv2.imwrite(str(path), image)
                image_paths.append(path)

            point, _ = calibrate_from_images(image_paths)
            self.assertIsNotNone(point)
            analysis = analyze_calibration_quality(image_paths, point)

        self.assertEqual(
            set(analysis),
            {
                "rms_error",
                "per_image_rms",
                "max_error_px",
                "coverage_score",
                "coverage_quadrants",
                "angle_diversity",
                "outlier_images",
                "overall_grade",
                "recommendations",
            },
        )
        self.assertTrue(analysis["per_image_rms"])
        self.assertGreaterEqual(analysis["coverage_score"], 0.0)
        self.assertLessEqual(analysis["coverage_score"], 1.0)
        self.assertIsInstance(analysis["recommendations"], list)

    def test_coverage_heatmap_and_systematic_error_outputs(self):
        with workspace_tempdir() as tmpdir:
            image_paths = []
            transforms = [
                (0.0, 0.0, 0.0, 1.0),
                (8.0, 40.0, 15.0, 0.94),
                (-7.0, -55.0, 22.0, 1.05),
                (12.0, 85.0, -30.0, 0.88),
            ]
            for index, args in enumerate(transforms):
                image = _checkerboard_image(angle_deg=args[0], shift_x=args[1], shift_y=args[2], scale=args[3])
                path = tmpdir / f"board_{index}.png"
                cv2.imwrite(str(path), image)
                image_paths.append(path)

            point, diagnostics = calibrate_from_images(image_paths)
            self.assertIsNotNone(point)
            heatmap = generate_coverage_heatmap(image_paths, (9, 6), diagnostics.image_size)
            systematic = detect_systematic_error(point, image_paths, (9, 6))

        self.assertEqual(heatmap.shape, (diagnostics.image_size[1], diagnostics.image_size[0], 3))
        self.assertEqual(heatmap.dtype, np.uint8)
        self.assertIn("tilted_sensor", systematic)
        self.assertIn("sample_bias", systematic)


if __name__ == "__main__":
    unittest.main()

# AGENTS.md — LensU Sprint 1: Core Upgrades

## Goal
Upgrade LensU from prototype to production-quality lens calibration tool. Add ChArUco support, STMap generation, distortion preview, and improved UE export.

## Context
- Existing code: D:\LensU\src\ (calibration.py, ue_export.py, app.py)
- Research docs: D:\LensU\research\ (read INDEX.md for key facts)
- Stack: Python 3.12, OpenCV, Streamlit, NumPy
- This is a LOCAL tool for cinema lens calibration → Unreal Engine ULens export

## Tasks (priority order)

### 1. Add ChArUco Board Support (calibration.py)

Add alongside existing checkerboard:

```python
def detect_charuco(
    image: np.ndarray,
    board_size: tuple[int, int] = (7, 5),  # squares, not inner corners
    square_length_mm: float = 30.0,
    marker_length_mm: float = 22.5,
    dictionary: int = cv2.aruco.DICT_6X6_250,
) -> tuple[bool, Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
    """Detect ChArUco corners. Returns (found, charuco_corners, charuco_ids, display_image)"""
```

Also add `calibrate_from_charuco_images()` that works like `calibrate_from_images()` but uses ChArUco detection. ChArUco is better because it works with partial occlusion.

Update the Streamlit UI to let users choose between Checkerboard and ChArUco detection modes.

### 2. STMap Generation (NEW: stmap.py)

Create `src/stmap.py`:

```python
def generate_stmap(
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    image_size: tuple[int, int],
    output_size: Optional[tuple[int, int]] = None,  # defaults to image_size
) -> np.ndarray:
    """Generate an STMap (undistort map) as a float32 HxWx3 array.
    
    Red channel = normalized X coordinate mapping
    Green channel = normalized Y coordinate mapping
    Blue channel = 0 (unused)
    
    Uses cv2.initUndistortRectifyMap() internally.
    """

def save_stmap_exr(stmap: np.ndarray, output_path: Path):
    """Save STMap as 32-bit float EXR file."""
    # Use OpenCV's cv2.imwrite with EXR format
    # Requires: the image must be float32, 3 channels
    
def generate_stmap_from_calibration(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    output_path: Path,
) -> Path:
    """Convenience: generate and save STMap from a CalibrationPoint."""
    # Reconstruct camera_matrix from point.fx, point.fy, point.cx, point.cy
    # Reconstruct dist_coeffs from point.k1, k2, p1, p2, k3
    # Note: cx/cy in CalibrationPoint are normalized (0-1), need to denormalize
```

STMap format details (from research):
- EXR float32, 3 channels
- Red = S (X coordinate), Green = T (Y coordinate)
- Values are normalized 0-1 representing UV coordinates
- Maps FROM undistorted TO distorted (for UE's use)

### 3. Distortion Preview (calibration.py + app.py)

Add to calibration.py:
```python
def undistort_image(
    image: np.ndarray,
    point: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Apply undistortion to an image using calibration data."""
    # Reconstruct camera_matrix and dist_coeffs from CalibrationPoint
    # Use cv2.undistort()

def generate_distortion_grid(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    grid_spacing: int = 50,
) -> np.ndarray:
    """Generate a grid overlay showing distortion effect."""
    # Draw a regular grid, then apply distortion to show how lines bend
```

Add to app.py Calibration tab:
- After calibration, show side-by-side: original image vs undistorted
- Show distortion grid overlay
- Show barrel/pincushion visualization

### 4. Improved UE Export (ue_export.py)

Update based on research findings:

Key corrections:
- `FocalLengthInfo.fx_fy` is a Vector2D — export as `{"fx_fy": [fx, fy]}` not separate fields
- Image center (`ImageCenterInfo.principal_point`) is Vector2D normalized [0,1]
- `NodalPointOffset` has `location_offset` (Vector3) and `rotation_offset` (Rotator)
- Add `data_mode` field to JSON: "Parameters" or "STMap"
- Include sensor dimensions in lens_info
- Add `user_metadata` field with LensU version info

Update the UE Python import script to match the exact UE 5.7 API signatures:
```python
focal_length_info = unreal.FocalLengthInfo()
focal_length_info.fx_fy = unreal.Vector2D(fx, fy)

image_center_info = unreal.ImageCenterInfo()
image_center_info.principal_point = unreal.Vector2D(cx, cy)

nodal_offset = unreal.NodalPointOffset()
nodal_offset.location_offset = unreal.Vector(x, y, z)
nodal_offset.rotation_offset = unreal.Rotator(pitch, yaw, roll)
```

### 5. Zoom Lens Workflow (app.py)

Improve the multi-focal calibration UI:
- Add a "Zoom Lens Mode" toggle that enables a structured workflow:
  1. User enters zoom range (e.g., 24-70mm)
  2. Tool suggests calibration points (e.g., 24, 28, 35, 50, 70mm)
  3. For each focal length: upload images, calibrate, see results
  4. After all points: show interpolation curve for k1, k2 across zoom range
  5. Show total profile summary

### 6. Accuracy Reporting (app.py)

After calibration:
- Show per-image reprojection error (bar chart)
- Flag outlier images (>2x mean RMS) with option to exclude and re-calibrate
- Show coverage heatmap (where corners were detected across the sensor)
- Display accuracy grade: "VP-Ready (<0.3px)" / "Good (<0.5px)" / "Acceptable (<1.0px)" / "Poor"

## Quality Requirements

- All existing functionality must still work
- No new pip dependencies (OpenCV already has EXR support, Streamlit has charts)
- Code must be clean, typed, documented
- Test by running `streamlit run app.py` and verifying all tabs work

## Test Plan

1. Run `python -c "from calibration import *; from stmap import *; print('imports OK')"` — verify no import errors
2. Run `streamlit run app.py` — verify app launches without errors
3. Generate a synthetic checkerboard image for testing:
   ```python
   # Create a test with cv2.drawChessboardCorners or generate synthetic calibration
   ```
4. Test STMap generation with known calibration values
5. Test UE export produces valid JSON matching the documented API

## Important Notes
- Read D:\LensU\research\INDEX.md for key technical facts
- The OpenCV → UE coordinate mapping is critical: normalize everything to [0,1]
- STMap must be float32 EXR — OpenCV can write this natively
- Check if `opencv-python-headless` supports EXR writing (may need `opencv-contrib-python` or OpenEXR package)
- If EXR writing fails, fall back to .tiff float32 as alternative

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 1 -- Core upgrades (ChArUco, STMap, distortion preview, UE export)" --mode now

# AGENTS.md — LensU Sprint 11: Calibration Quality Analyzer + Distortion Heatmap + Profile Merge

## Goal
Add advanced analysis tools that make LensU the most technically capable free lens calibration tool available.

## Tasks

### 1. Calibration Quality Analyzer (NEW: src/quality_analyzer.py)

Deep analysis of calibration quality beyond simple RMS:

```python
def analyze_calibration_quality(
    image_paths: list[Path],
    calibration_point: CalibrationPoint,
    pattern_size: tuple[int, int] = (9, 6),
) -> dict:
    """Comprehensive calibration quality analysis.
    
    Returns dict with:
    - "rms_error": float (overall)
    - "per_image_rms": list[float] (per-image errors)
    - "max_error_px": float (worst single point error)
    - "coverage_score": float (0-1, how well images cover the sensor)
    - "coverage_quadrants": dict (NW/NE/SW/SE/Center coverage %)
    - "angle_diversity": float (0-1, variety of board orientations)
    - "outlier_images": list[int] (indices of images with >2x mean RMS)
    - "overall_grade": str ("VP-Ready" / "Good" / "Acceptable" / "Poor")
    - "recommendations": list[str] (actionable improvement tips)
    """

def generate_coverage_heatmap(
    image_paths: list[Path],
    pattern_size: tuple[int, int],
    image_size: tuple[int, int],
) -> np.ndarray:
    """Generate a heatmap image showing where checkerboard corners were detected.
    
    Returns a color-mapped image (hot = high coverage, cold = low).
    """

def detect_systematic_error(
    calibration_point: CalibrationPoint,
    image_paths: list[Path],
    pattern_size: tuple[int, int],
) -> dict:
    """Detect systematic errors in calibration.
    
    Checks for:
    - Tilted sensor (asymmetric image center)
    - Decentered lens element (asymmetric distortion)
    - Focus error (high tangential distortion)
    - Sample bias (all images from similar angles)
    """
```

### 2. Interactive Distortion Visualization (NEW: src/distortion_viz.py)

Generate publication-quality distortion visualizations:

```python
def render_distortion_grid(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    grid_density: int = 20,
    scale_factor: float = 1.0,
) -> np.ndarray:
    """Render a distortion grid showing how straight lines bend.
    Blue = undistorted grid, Red = distorted grid overlay.
    """

def render_distortion_magnitude_map(
    point: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Render a color-coded map showing distortion magnitude across the image.
    Center = low distortion (blue), edges = high distortion (red).
    Values in pixel displacement.
    """

def render_distortion_vector_field(
    point: CalibrationPoint,
    image_size: tuple[int, int],
    arrow_density: int = 15,
) -> np.ndarray:
    """Render arrows showing distortion direction and magnitude at each point."""

def compare_distortion_profiles(
    point_a: CalibrationPoint,
    point_b: CalibrationPoint,
    image_size: tuple[int, int],
) -> np.ndarray:
    """Render side-by-side distortion comparison of two calibration points."""
```

Add these visualizations to the Profile tab in Streamlit.

### 3. Profile Merge Tool (calibration.py)

Merge calibration data from multiple sessions:

```python
def merge_profiles(
    profiles: list[LensProfile],
    strategy: str = "best_rms",  # "best_rms", "average", "latest"
) -> LensProfile:
    """Merge multiple profiles for the same lens.
    
    Strategies:
    - "best_rms": For each focal length, keep the calibration with lowest RMS
    - "average": Average the distortion coefficients across profiles  
    - "latest": Keep the most recent calibration for each focal length
    
    Use case: calibrate the same lens multiple times over weeks/months,
    merge the best results into a single authoritative profile.
    """
```

Add merge UI in the Lens Library tab.

### 4. Update Tests

Add tests for quality analyzer, distortion visualization, and profile merge.

## Quality Requirements
- Heatmap must be visually clear and informative
- Quality analyzer recommendations must be actionable
- Profile merge must not lose data
- All existing tests pass + new tests

## Test Plan
1. All imports succeed
2. All tests pass
3. Quality analyzer returns valid dict for dummy data
4. Distortion grid renders to valid image array
5. Profile merge produces valid merged profile

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 11 -- Quality analyzer, distortion viz, profile merge" --mode now

# AGENTS.md — LensU Sprint 7: Fisheye Support + Encoder Mapping + pyproject.toml

## Goal
Add fisheye/ultra-wide lens calibration, FIZ encoder mapping tables, and package the project for pip install.

## Tasks

### 1. Fisheye Calibration (calibration.py)

Cinema productions increasingly use ultra-wide and fisheye lenses. OpenCV has a dedicated fisheye module:

```python
def calibrate_fisheye(
    image_paths: list[Path],
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    focal_length_mm: float = 14.0,
) -> tuple[Optional[CalibrationPoint], list[bool]]:
    """Calibrate a fisheye/ultra-wide lens using cv2.fisheye.
    
    Uses cv2.fisheye.calibrate() which uses the equidistant projection model
    with 4 distortion coefficients (k1-k4), different from the standard model.
    
    Steps:
    1. Detect checkerboard corners in images
    2. Run cv2.fisheye.calibrate() with appropriate flags
    3. Store results as CalibrationPoint with is_fisheye=True flag
    4. Map fisheye k1-k4 to the standard CalibrationPoint structure
    """
```

Add `is_fisheye: bool = False` and `fisheye_coeffs: list[float] = field(default_factory=list)` to CalibrationPoint.

Update Streamlit: add "Fisheye Mode" toggle in calibration tab. When enabled, use fisheye calibration. Show fisheye-specific info (equidistant model, FOV > 120 degrees).

Update UE export: fisheye lenses may need STMap-based export since UE's parametric model may not support equidistant projection. Always generate STMap for fisheye.

### 2. FIZ Encoder Mapping Tables (NEW: src/encoder_mapping.py)

Map raw encoder values (0-65535) from FreeD/OpenTrackIO to physical lens values:

```python
@dataclass
class EncoderMapping:
    """Maps raw encoder values to physical lens parameters."""
    lens_name: str
    # Focus mapping: [(encoder_value, focus_distance_m), ...]
    focus_map: list[tuple[int, float]] = field(default_factory=list)
    # Zoom mapping: [(encoder_value, focal_length_mm), ...]
    zoom_map: list[tuple[int, float]] = field(default_factory=list)
    # Iris mapping: [(encoder_value, t_stop), ...]
    iris_map: list[tuple[int, float]] = field(default_factory=list)

    def encoder_to_focus(self, raw: int) -> float:
        """Interpolate raw encoder value to focus distance in meters."""
        
    def encoder_to_zoom(self, raw: int) -> float:
        """Interpolate raw encoder value to focal length in mm."""

    def encoder_to_iris(self, raw: int) -> float:
        """Interpolate raw encoder value to T-stop."""

def create_mapping_from_samples(
    samples: list[tuple[int, float]],
) -> list[tuple[int, float]]:
    """Create a mapping table from measured samples.
    User measures encoder value at known physical positions.
    Returns sorted mapping table ready for interpolation.
    """
```

Add "Encoder Mapping" section in the Live Tracking tab:
- Table input: "At encoder value X, the lens is at Y mm/m/T"
- User fills in 5-10 calibration points
- Shows interpolation curve
- Save/load encoder mappings per lens
- Link to protocols: when FreeD/OpenTrackIO data arrives, auto-map using the table

### 3. Package as pip-installable (pyproject.toml)

Create proper Python packaging so users can `pip install lensu`:

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "lensu"
version = "1.5.0"
description = "Cinema lens calibration tool for Unreal Engine virtual production"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [{name = "Javier Herreros Riaza", email = "hello@javierherreros.xyz"}]
keywords = ["lens", "calibration", "unreal-engine", "virtual-production", "opencv", "cinema"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Topic :: Multimedia :: Video",
    "Topic :: Scientific/Engineering :: Image Processing",
]
dependencies = [
    "opencv-python-headless>=4.8",
    "streamlit>=1.20",
    "numpy>=1.24",
    "reportlab>=4.0",
    "matplotlib>=3.7",
]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[project.scripts]
lensu = "src.cli:main"
lensu-gui = "src.app:main"

[project.urls]
Homepage = "https://github.com/jhriaza/lensu"
```

Create `src/__init__.py` with version:
```python
__version__ = "1.5.0"
```

Update CLI to show version: `lensu --version`

Create `.gitignore`:
```
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
build/
.tmp_test/
*.tiff
*.exr
```

### 4. Clean Up Root Directory

The project has duplicate files in root and src/. Remove root-level duplicates:
- Delete: calibration.py, ue_export.py, app.py, stmap.py, board_generator.py, video_extractor.py, live_calibration.py, batch.py, lens_library.py, report.py, presets.py, lensu.py (root copies)
- Delete: protocols/ directory at root (keep src/protocols/)
- Delete: all __pycache__/ directories at root
- Keep only: src/, research/, README.md, requirements.txt, pyproject.toml, LICENSE, .gitignore, AGENTS.md

All imports should use `src.` prefix or update to work as a package.

## Quality Requirements
- `pip install -e .` must work (editable install)
- `lensu --version` must show 1.5.0
- `lensu-gui` must launch Streamlit
- All 13+ tests must still pass
- Fisheye calibration must handle lenses with FOV > 180 degrees gracefully
- No new external dependencies beyond what's already in requirements.txt

## Test Plan
1. Clean up root duplicates first
2. `pip install -e .` — editable install works
3. `lensu --version` — shows version
4. `python -m pytest src/tests/ -v` — all tests pass
5. `streamlit run src/app.py` — app works with fisheye toggle
6. Import test: `from src.encoder_mapping import *; print('OK')`

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 7 -- Fisheye, encoder mapping, packaging" --mode now

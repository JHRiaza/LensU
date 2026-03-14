# AGENTS.md — LensU Sprint 4: Batch Processing + Lens Library + CLI

## Goal
Make LensU production-ready for VP stages: batch calibration, reusable lens library, and a CLI for automated pipelines.

## Tasks

### 1. Lens Library (NEW: src/lens_library.py)

A local database of calibrated lens profiles that users can save, browse, and reuse:

```python
from pathlib import Path
import json

LIBRARY_DIR = Path.home() / ".lensu" / "library"

def save_to_library(profile: LensProfile) -> Path:
    """Save a calibrated lens profile to the local library.
    Creates: ~/.lensu/library/{lens_name}_{date}.json
    """

def list_library() -> list[dict]:
    """List all saved profiles with summary info.
    Returns: [{name, date, focal_lengths, sensor, rms_avg}, ...]
    """

def load_from_library(filename: str) -> LensProfile:
    """Load a profile from the library."""

def delete_from_library(filename: str) -> bool:
    """Delete a profile from the library."""

def search_library(lens_name: str = "", sensor_type: str = "") -> list[dict]:
    """Search library by lens name or sensor type."""
```

Add a "Lens Library" tab in Streamlit:
- Browse saved profiles with search/filter
- Load a profile into the current session
- Delete old profiles
- Export any library profile as UE package
- Show statistics: total profiles, lens families, date range

### 2. Batch Calibration (NEW: src/batch.py)

For calibrating multiple focal lengths in one go from organized folders:

```python
def batch_calibrate(
    base_dir: Path,
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    detection_mode: str = "checkerboard",  # or "charuco"
    sensor_width_mm: float = 36.0,
    sensor_height_mm: float = 24.0,
) -> LensProfile:
    """Batch calibrate from a folder structure:
    
    base_dir/
      24mm/
        img001.jpg
        img002.jpg
        ...
      35mm/
        img001.jpg
        ...
      50mm/
        ...
    
    Each subfolder name must contain the focal length in mm (e.g., "24mm", "24", "FL24").
    Extracts the number, calibrates each folder, builds a complete LensProfile.
    
    Returns a LensProfile with all focal lengths calibrated.
    """

def batch_calibrate_from_videos(
    base_dir: Path,
    pattern_size: tuple[int, int] = (9, 6),
    square_size_mm: float = 25.0,
    max_frames_per_video: int = 30,
    **kwargs,
) -> LensProfile:
    """Same as batch_calibrate but each subfolder contains a video file
    instead of images. Extracts frames automatically.
    
    base_dir/
      24mm/
        calibration.mp4
      50mm/
        calibration.mov
    """
```

Add batch calibration to Streamlit:
- Folder path input (or drag-drop folder structure description)
- Progress bar showing calibration progress per focal length
- Summary table with all results at the end

### 3. CLI Interface (NEW: src/cli.py)

Command-line interface for automated pipelines (no browser needed):

```python
# Usage:
# python -m lensu calibrate --images ./photos/50mm/ --focal-length 50 --sensor full-frame
# python -m lensu batch --dir ./calibration_shots/ --sensor super35
# python -m lensu export --profile my_lens.json --format ue --output ./export/
# python -m lensu board --type charuco --size A3 --output board.pdf
# python -m lensu library --list
# python -m lensu library --search "Cooke"
```

Use `argparse` (stdlib, no dependencies). Subcommands:

- `calibrate` — Single focal length calibration from images
  - `--images DIR` — Directory of calibration images
  - `--focal-length MM` — Focal length in mm
  - `--pattern SIZE` — Pattern size (default: 9x6)
  - `--square-size MM` — Square size (default: 25)
  - `--mode checkerboard|charuco` — Detection mode
  - `--sensor PRESET|WxH` — Sensor (full-frame, apsc-canon, apsc-sony, m43, super35, or WxHmm)
  - `--output FILE` — Output profile JSON path
  - `--save-library` — Also save to local library

- `batch` — Multi-focal-length batch calibration
  - `--dir DIR` — Base directory with focal length subfolders
  - `--sensor PRESET|WxH`
  - `--output FILE`
  - `--save-library`

- `export` — Export a profile to UE format
  - `--profile FILE` — Input profile JSON
  - `--format ue` — Export format (only UE for now)
  - `--output DIR` — Output directory
  - `--include-stmaps` — Include STMap files

- `board` — Generate printable calibration board
  - `--type checkerboard|charuco`
  - `--size A4|A3|A2|A1`
  - `--pattern SIZE` — Pattern size
  - `--square-size MM`
  - `--output FILE`

- `library` — Manage lens library
  - `--list` — List all profiles
  - `--search QUERY` — Search by name
  - `--delete FILENAME` — Delete a profile
  - `--export FILENAME` — Export from library

Also create `src/__main__.py` so `python -m lensu` works:
```python
from src.cli import main
if __name__ == "__main__":
    main()
```

### 4. Progress and Logging

Add proper progress reporting for CLI mode:
- Use `print()` with clear status messages
- Show per-image detection results
- Show calibration progress percentage
- Final summary with all metrics
- ASCII only (no unicode — Windows cp1252 compatibility!)

## Quality Requirements
- CLI must work standalone without Streamlit
- Batch calibration must handle 100+ images without memory issues
- Library must handle 100+ saved profiles
- All error messages must be clear and actionable
- No new pip dependencies

## Test Plan
1. `python -c "from src.lens_library import *; from src.batch import *; from src.cli import *; print('OK')"` — imports
2. `python -m src.cli board --type checkerboard --size A3 --output test_board.pdf` — generates PDF
3. `python -m src.cli library --list` — lists (empty) library
4. `streamlit run src/app.py` — app still works with new tabs
5. Clean up test outputs

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 4 -- Batch processing, lens library, CLI" --mode now

# AGENTS.md — LensU Sprint 10: Comprehensive Documentation + Examples

## Goal
Create thorough documentation and example workflows so users can get started immediately. This is the "release readiness" sprint.

## Tasks

### 1. Documentation (NEW: docs/ directory)

Create `docs/` with markdown files:

**docs/getting-started.md:**
- Installation (pip install, git clone, requirements)
- First calibration walkthrough (print board, take photos, upload, calibrate, export)
- Quick start with presets
- System requirements

**docs/calibration-guide.md:**
- Choosing checkerboard vs ChArUco
- Optimal number of images (15-30)
- Image coverage patterns (show diagram as ASCII art)
- Lighting requirements
- Common mistakes and how to avoid them
- Accuracy targets for VP (<0.3px RMS)
- Zoom lens calibration strategy

**docs/ue-integration.md:**
- Step-by-step UE import guide
- Camera Calibration plugin setup
- Assigning LensFile to CineCamera
- LiveLink streaming setup
- Troubleshooting common UE issues

**docs/nuke-integration.md:**
- Importing LensU .nk scripts
- Using the gizmo
- STMap workflow in Nuke
- Matching UE and Nuke distortion

**docs/api-reference.md:**
- REST API endpoints with curl examples
- Python API reference (key classes and methods)
- CLI command reference with examples

**docs/advanced.md:**
- Anamorphic lens calibration
- Fisheye/ultra-wide calibration
- Lens breathing measurement
- Nodal offset estimation
- FreeD/OpenTrackIO integration
- Multi-camera rigs
- Encoder mapping
- Batch calibration from video

### 2. Example Workflows (NEW: examples/ directory)

**examples/basic_calibration.py:**
```python
"""Example: Calibrate a 50mm prime lens from images."""
from src.calibration import calibrate_from_images, LensProfile
from src.ue_export import export_ue_json, export_ue_python_script
from pathlib import Path

# 1. Calibrate
images = list(Path("./my_photos").glob("*.jpg"))
point, used = calibrate_from_images(images, focal_length_mm=50)

# 2. Build profile
profile = LensProfile(lens_name="Cooke S4/i 50mm", sensor_width_mm=24.89, sensor_height_mm=18.66)
profile.add_calibration(point)

# 3. Export for UE
export_ue_json(profile, Path("./output"))
export_ue_python_script(profile, "calibration.json", Path("./output"))
```

**examples/zoom_lens_batch.py:**
```python
"""Example: Batch calibrate a zoom lens from organized folders."""
from src.batch import batch_calibrate
# Folder structure: ./shots/24mm/, ./shots/35mm/, ./shots/50mm/, ./shots/70mm/
profile = batch_calibrate(Path("./shots"), sensor_width_mm=24.89, sensor_height_mm=18.66)
profile.lens_name = "Angenieux EZ-1 30-90mm"
profile.save_json(Path("./angenieux_ez1.json"))
```

**examples/livelink_stream.py:**
```python
"""Example: Stream lens data to UE via LiveLink."""
from src.livelink_emitter import LiveLinkEmitter
from src.calibration import LensProfile
profile = LensProfile.load_json(Path("./my_lens.json"))
emitter = LiveLinkEmitter(target_ip="192.168.1.100", port=11111)
emitter.start_streaming(profile, fps=24)
```

**examples/api_client.py:**
```python
"""Example: Use LensU REST API from external tool."""
import requests
# Start server: lensu serve --port 8600
r = requests.get("http://localhost:8600/api/presets")
print(r.json())
r = requests.post("http://localhost:8600/api/calibrate", json={...})
```

### 3. CHANGELOG.md

Create a changelog documenting all versions:
```
# Changelog

## v1.7.0 (2026-03-15)
- LiveLink UDP emitter for streaming to UE
- Step-by-step calibration wizard
- Dark theme UI
- Session auto-save and recovery

## v1.6.0 (2026-03-15)
- REST API server (lensu serve)
- Multi-camera rig support
- Nuke export (.nk scripts and .gizmo)

## v1.5.0 (2026-03-15)
- Fisheye/ultra-wide lens calibration
- FIZ encoder mapping tables
- pip-installable package (pyproject.toml)
- Clean project structure

... (continue for all versions back to v1.0)
```

### 4. LICENSE

Verify MIT LICENSE file exists and is correct. If missing, create it.

### 5. Contributing Guide

Create `CONTRIBUTING.md`:
- How to set up dev environment
- Running tests
- Code style (type hints, docstrings)
- How to add new preset lenses
- How to add new export formats

## Quality Requirements
- All documentation must be accurate and match current code
- Examples must be runnable (correct imports, realistic parameters)
- No broken internal links
- Documentation should be beginner-friendly
- All existing tests must still pass

## Test Plan
1. All 25+ tests still pass
2. All example scripts parse without syntax errors: `python -c "import ast; ast.parse(open('examples/basic_calibration.py').read())"`
3. Documentation files exist and are non-empty
4. App still launches correctly

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 10 -- Docs, examples, changelog" --mode now

# AGENTS.md — LensU Sprint 8: REST API + Multi-Camera + Nuke Export

## Goal
Add a REST API for external tool integration, multi-camera calibration support, and Nuke-compatible export.

## Tasks

### 1. REST API Server (NEW: src/api.py)

A lightweight FastAPI/Flask server so external tools can trigger calibration programmatically:

Since we want NO new dependencies, use Python's built-in `http.server` with a simple JSON API:

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class LensUAPIHandler(BaseHTTPRequestHandler):
    """Simple REST API for LensU.
    
    Endpoints:
    
    GET /api/status
      Returns: {"status": "ok", "version": "1.5.0"}
    
    GET /api/library
      Returns: list of saved lens profiles
    
    GET /api/library/{name}
      Returns: specific profile data
    
    POST /api/calibrate
      Body: {"images_dir": "path", "focal_length_mm": 50, "pattern_size": [9,6], "sensor": "full-frame"}
      Returns: {"calibration_point": {...}, "rms_error": 0.3, "images_used": 15}
    
    POST /api/batch
      Body: {"base_dir": "path", "sensor": "super35"}
      Returns: {"profile": {...}, "focal_lengths_calibrated": [24, 35, 50]}
    
    POST /api/export
      Body: {"profile_name": "my_lens", "format": "ue", "include_stmaps": true}
      Returns: ZIP file as binary
    
    GET /api/presets
      Returns: list of available preset profiles
    
    GET /api/presets/{name}
      Returns: preset profile data
    """

def start_api_server(host: str = "0.0.0.0", port: int = 8600):
    """Start the LensU API server."""
```

Add CLI command: `lensu serve --port 8600`

### 2. Multi-Camera Support (calibration.py + app.py)

VP stages often have multiple cameras. Add ability to manage calibrations for multiple cameras in one session:

Add to calibration.py:
```python
@dataclass
class CameraRig:
    """A collection of cameras with their lens profiles."""
    rig_name: str = "Default Rig"
    cameras: dict[str, LensProfile] = field(default_factory=dict)
    # Key = camera label (e.g., "Camera A", "Main", "Witness")
    
    def add_camera(self, label: str, profile: LensProfile):
        self.cameras[label] = profile
    
    def to_dict(self) -> dict:
        return {
            "rig_name": self.rig_name,
            "cameras": {k: v.to_dict() for k, v in self.cameras.items()}
        }
    
    def save_json(self, path: Path):
        path.write_text(json.dumps(self.to_dict(), indent=2))
```

In Streamlit sidebar, add camera selector:
- "Add Camera" button
- Camera label input
- Switch between cameras
- Each camera has its own LensProfile
- Export all cameras as a multi-camera UE package

### 3. Nuke Export (NEW: src/nuke_export.py)

Export calibration data for The Foundry Nuke (common in VP post-production):

```python
def export_nuke_script(
    profile: LensProfile,
    output_path: Path,
) -> Path:
    """Generate a Nuke .nk script with LensDistortion node.
    
    Creates a Nuke script containing:
    - LensDistortion node with calibrated k1, k2, k3, p1, p2 values
    - Correct image format (resolution + pixel aspect)
    - STMap generator setup for undistortion
    - Read node placeholder for plate input
    
    Nuke LensDistortion node uses similar Brown-Conrady model to OpenCV.
    """

def export_nuke_gizmo(
    profile: LensProfile,
    output_path: Path,
) -> Path:
    """Generate a Nuke .gizmo for reusable lens correction.
    
    A gizmo is a reusable Nuke node group that:
    - Takes input plate
    - Applies undistortion using calibrated parameters
    - Has knobs for adjusting parameters
    - Includes lens info in label
    """
```

Add Nuke export option in the Export tab alongside UE export.

### 4. Update Tests

Add tests for:
- API endpoint responses (mock HTTP)
- CameraRig serialization
- Nuke script generation (check output contains expected node names)
- Encoder mapping interpolation accuracy

## Quality Requirements
- API server must be optional (not started by default)
- No new pip dependencies (use stdlib http.server)
- Multi-camera must not break single-camera workflow
- Nuke export must produce valid .nk syntax
- All existing tests must pass + new tests

## Test Plan
1. All imports succeed
2. `python -m pytest src/tests/ -v` — all tests pass
3. API server starts and responds to GET /api/status
4. Multi-camera CameraRig serializes/deserializes correctly
5. Nuke export generates parseable .nk file
6. `streamlit run src/app.py` — app works with multi-camera selector

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 8 -- REST API, multi-camera, Nuke export" --mode now

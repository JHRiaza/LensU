# AGENTS.md — LensU Sprint 9: LiveLink Emulator + Calibration Wizard + Polish

## Goal
Add a LiveLink-compatible data emitter so LensU can stream lens data directly into UE without file export, a guided calibration wizard for beginners, and final polish.

## Tasks

### 1. LiveLink UDP Emitter (NEW: src/livelink_emitter.py)

Stream calibrated lens data to UE via LiveLink protocol (UDP JSON):

```python
import socket
import json
import time

class LiveLinkEmitter:
    """Emit lens calibration data to UE LiveLink over UDP.
    
    UE's LiveLink can receive custom JSON data via UDP.
    This emitter sends lens parameters that UE can map to a CineCamera.
    
    Message format (UE LiveLink JSON):
    {
        "SubjectName": "LensU",
        "FrameNumber": 0,
        "FocalLength": 50.0,
        "Aperture": 2.8,
        "FocusDistance": 3.0,
        "DistortionParameters": [k1, k2, p1, p2, k3],
        "ImageCenter": [cx, cy],
        "NodalOffset": [x, y, z, pitch, yaw, roll]
    }
    """
    
    def __init__(self, target_ip: str = "127.0.0.1", port: int = 11111):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.target = (target_ip, port)
        self.frame = 0
    
    def send_static_profile(self, profile: LensProfile, focal_length_mm: float):
        """Send a static lens profile (useful for fixed prime lenses)."""
        
    def send_fiz_update(self, focus: float, iris: float, zoom: float, profile: LensProfile):
        """Send interpolated lens data based on current FIZ values.
        Uses the profile's calibration tables to interpolate distortion
        at the current focus/zoom position.
        """
    
    def start_streaming(self, profile: LensProfile, fps: int = 24):
        """Start continuous streaming at specified frame rate."""
        
    def stop_streaming(self):
        """Stop streaming."""
```

Add "LiveLink" section in the Live Tracking tab:
- Target IP and port configuration
- Start/Stop streaming buttons
- Frame counter display
- Option to stream static profile or receive FIZ from FreeD/OpenTrackIO and forward interpolated data

### 2. Calibration Wizard (NEW: src/wizard.py)

A step-by-step guided workflow for first-time users:

```python
def calibration_wizard_ui():
    """Streamlit multi-step wizard for complete lens calibration.
    
    Step 1: "Welcome" - Explain what LensU does, what you'll need
    Step 2: "Lens Info" - Name, type (prime/zoom/anamorphic), sensor size
    Step 3: "Calibration Board" - Generate and download a printable board
    Step 4: "Capture Images" - Instructions for good calibration shots
           - Upload images OR use live camera
           - Show real-time coverage feedback
    Step 5: "Calibrate" - Run calibration, show results
           - Accuracy grade with explanation
           - Option to exclude bad images and re-run
    Step 6: "Nodal Offset" - Optional: guided parallax test OR manual entry
    Step 7: "Zoom Points" - For zoom lenses: repeat steps 4-5 at each focal length
    Step 8: "Export" - Choose export format (UE, Nuke, or both)
           - Download package
           - Show UE import instructions
    Step 9: "Save" - Save to library with name and notes
    """
```

Add "Wizard" as the FIRST tab in Streamlit (before advanced tabs).

### 3. Final Polish

a) **Error recovery**: Wrap all calibration operations in try/except with user-friendly error messages. No tracebacks in the UI.

b) **Session auto-save**: Auto-save current work to `~/.lensu/autosave.json` every time a calibration is run or profile is modified. On app start, offer to restore autosaved session.

c) **Dark theme**: Add Streamlit theme config in `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#FF6B35"
backgroundColor = "#0E1117"
secondaryBackgroundColor = "#1E2130"
textColor = "#FAFAFA"
font = "sans serif"
```

d) **App icon and page config**: Update st.set_page_config with proper title, icon, and layout.

e) **Footer**: Add version number, link to docs, "Made for Virtual Production" tagline.

### 4. Update README

Add new features to README:
- LiveLink streaming
- REST API (`lensu serve`)
- Nuke export
- Multi-camera support
- Calibration wizard
- Complete feature list

## Quality Requirements
- LiveLink emitter must not block the UI
- Wizard must work for complete beginners (no assumed knowledge)
- Auto-save must not corrupt data on crash
- All 22+ tests must still pass
- No new pip dependencies

## Test Plan
1. All imports succeed
2. `python -m pytest src/tests/ -v` — all tests pass
3. `streamlit run src/app.py` — app launches with wizard as first tab
4. Dark theme applied
5. LiveLink emitter creates socket without error
6. Auto-save file created at ~/.lensu/autosave.json

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 9 -- LiveLink, wizard, polish" --mode now

# AGENTS.md — LensU Sprint 3: Live Camera Feed + Lens Breathing + Auto Nodal

## Goal
Add real-time calibration from live camera feed and advanced calibration features that no competitor offers.

## Tasks

### 1. Live Camera Feed Calibration (NEW: src/live_calibration.py)

Real-time calibration using webcam or capture card:

```python
import cv2
import streamlit as st

def live_calibration_ui():
    """Streamlit component for live camera calibration.
    
    Workflow:
    1. Select camera device (index or name)
    2. Show live feed with checkerboard/ChArUco overlay
    3. Auto-detect board in each frame
    4. When board detected, show green overlay + "Press CAPTURE" button
    5. Capture frames with good coverage diversity (track which quadrants are covered)
    6. Show coverage heatmap updating in real-time
    7. When enough frames captured (15+), enable "CALIBRATE" button
    8. Run calibration on captured frames
    """
```

Use `st.camera_input()` for Streamlit's native camera access. If that's not available or doesn't support continuous capture, use OpenCV's `cv2.VideoCapture(0)` with `st.image()` for display + a capture button.

Key features:
- Camera device selector (list available cameras)
- Live checkerboard/ChArUco detection overlay
- Coverage indicator showing which sensor regions have been captured
- "Auto-capture" mode that captures frames automatically when a new viewing angle is detected
- Minimum 15 frames before allowing calibration
- Real-time RMS error display after each new frame

### 2. Lens Breathing Compensation (calibration.py + app.py)

Cinema lenses shift focal length when focus changes (breathing). This affects VP tracking.

Add to calibration.py:
```python
@dataclass
class BreathingPoint:
    """Focal length measurement at a specific focus distance."""
    focus_distance_m: float  # focus distance in meters
    measured_focal_length_mm: float  # actual focal length at this focus
    nominal_focal_length_mm: float  # labeled focal length on the lens

@dataclass  
class BreathingProfile:
    """Lens breathing curve for a specific nominal focal length."""
    nominal_focal_length_mm: float
    points: list[BreathingPoint]
    
    def breathing_ratio(self) -> float:
        """Max breathing as a percentage of nominal focal length."""
        if not self.points:
            return 0.0
        fls = [p.measured_focal_length_mm for p in self.points]
        return (max(fls) - min(fls)) / self.nominal_focal_length_mm * 100
```

Add to LensProfile:
```python
breathing_profiles: list[BreathingProfile] = field(default_factory=list)
```

In the Streamlit UI, add a "Lens Breathing" tab:
- User calibrates at several focus distances (infinity, 3m, 1.5m, 1m, 0.5m)
- At each focus distance, system measures effective focal length from calibration
- Shows breathing curve graph (focus distance vs measured focal length)
- Reports breathing percentage
- Exports breathing data in the UE JSON (mapped to Focus axis in FIZ table)

### 3. Guided Nodal Offset Estimation (calibration.py + app.py)

Instead of manual entry, guide the user through measuring nodal offset:

Add to app.py Nodal Offset tab:
```
Guided Nodal Offset Test:

1. Mount camera on a calibrated tripod head (with distance markings)
2. Place two vertical objects at different distances (near: 1m, far: 3m)
3. Rotate camera left/right while looking at the parallax between objects
4. Take a photo at each rotation angle (-10°, -5°, 0°, +5°, +10°)
5. Upload the 5 photos
6. LensU analyzes the parallax shift to estimate the entrance pupil position
```

Add to calibration.py:
```python
def estimate_nodal_from_parallax(
    images: list[np.ndarray],
    rotation_angles_deg: list[float],
    near_object_distance_m: float = 1.0,
    far_object_distance_m: float = 3.0,
) -> NodalOffset:
    """Estimate entrance pupil position from parallax test images.
    
    Uses feature matching between images to measure parallax shift
    at known rotation angles. The nodal point is where the parallax
    is zero (entrance pupil).
    
    Simplified approach:
    1. Detect features in all images (ORB or SIFT)
    2. Match features between consecutive rotation pairs
    3. Measure horizontal shift of matched features
    4. Fit a linear model: shift = k * (distance_from_nodal * sin(angle))
    5. Solve for distance_from_nodal
    """
```

This doesn't need to be perfect — even a rough estimate is better than no nodal data. Show confidence level.

### 4. Update UE Export for New Data

Add to ue_export.py:
- Export breathing data as additional FocalLength points indexed by Focus value
- Include breathing_ratio in user_metadata
- STMaps generated per focal length included in ZIP

Update the UE Python import script to handle breathing data (map to focus-indexed focal length points).

## Dependencies
- No new pip installs needed
- OpenCV handles camera capture, feature matching

## Quality Requirements
- Live camera must work with standard USB webcams
- Breathing measurement should be accurate to ±0.5mm focal length
- Nodal estimation should be accurate to ±5mm (rough but useful)
- All existing features must still work
- App must not crash if camera is not available

## Test Plan
1. All imports succeed
2. Streamlit app launches without errors
3. Camera feed works (if webcam available) or shows graceful error
4. Breathing tab renders correctly with placeholder data
5. Nodal estimation works with test images (or shows clear instructions)

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 3 -- Live camera, breathing, auto nodal" --mode now

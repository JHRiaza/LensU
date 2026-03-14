# AGENTS.md — LensU Sprint 6: FreeD/OpenTrackIO Listener + Preset Lens Profiles + Tests

## Goal
Add real-time tracking protocol integration (FreeD + OpenTrackIO), ship preset lens profiles for common cinema lenses, and add automated tests.

## Tasks

### 1. FreeD Protocol Listener (NEW: src/protocols/freed.py)

FreeD is the industry-standard VP camera tracking protocol. Implement a listener that receives live FIZ data:

```python
import socket
import struct
from dataclasses import dataclass

@dataclass
class FreeDPacket:
    """Parsed FreeD D1 data packet."""
    camera_id: int
    pan: float      # degrees
    tilt: float     # degrees
    roll: float     # degrees
    pos_x: float    # mm
    pos_y: float    # mm
    pos_z: float    # mm
    zoom: int       # raw encoder value
    focus: int      # raw encoder value

def parse_freed_d1(data: bytes) -> FreeDPacket:
    """Parse a FreeD D1 packet (29 bytes).
    
    Format:
    - Byte 0: 0xD1 (packet type)
    - Byte 1: Camera ID
    - Bytes 2-4: Pan (24-bit signed, degrees * 32768)
    - Bytes 5-7: Tilt
    - Bytes 8-10: Roll
    - Bytes 11-13: X position (24-bit signed, mm)
    - Bytes 14-16: Y position
    - Bytes 17-19: Z position
    - Bytes 20-22: Zoom (24-bit unsigned)
    - Bytes 23-25: Focus (24-bit unsigned)
    - Bytes 26-27: Spare
    - Byte 28: Checksum
    """

def start_freed_listener(
    port: int = 6000,
    callback = None,  # called with FreeDPacket on each received packet
) -> socket.socket:
    """Start a UDP listener for FreeD packets.
    Returns the socket (caller manages lifecycle).
    """

def freed_to_fiz(packet: FreeDPacket, lens_profile: LensProfile) -> dict:
    """Map raw FreeD encoder values to calibrated FIZ values.
    Returns: {"focus_m": float, "iris": float, "zoom_mm": float}
    
    Requires a mapping table (encoder value -> physical value).
    If no mapping available, returns raw values normalized 0-1.
    """
```

### 2. OpenTrackIO Listener (NEW: src/protocols/opentrackio.py)

Mo-Sys led protocol, JSON/CBOR over UDP multicast:

```python
import json
from dataclasses import dataclass

@dataclass
class OpenTrackIOSample:
    """Parsed OpenTrackIO tracking sample."""
    timestamp: float
    # Camera transform
    translation: tuple[float, float, float]  # x, y, z in meters
    rotation: tuple[float, float, float]     # pan, tilt, roll in degrees
    # Lens data
    focal_length_mm: float = 0.0
    focus_distance_m: float = 0.0
    iris_fstop: float = 0.0
    # Optional distortion from tracking system
    distortion_coefficients: list[float] = None
    
def parse_opentrackio(data: bytes) -> OpenTrackIOSample:
    """Parse an OpenTrackIO JSON packet.
    
    Expected structure:
    {
      "protocol": "OpenTrackIO",
      "version": "0.9",
      "sample": {
        "timestamp": ...,
        "transforms": {"translation": [x,y,z], "rotation": [p,t,r]},
        "lens": {"focalLength": ..., "focusDistance": ..., "iris": ...},
        "distortion": {"coefficients": [...]}
      }
    }
    """

def start_opentrackio_listener(
    address: str = "239.1.1.1",  # multicast group
    port: int = 5555,
    callback = None,
) -> socket.socket:
    """Start a UDP multicast listener for OpenTrackIO packets."""
```

Add a "Live Tracking" tab in Streamlit:
- Protocol selector (FreeD / OpenTrackIO)
- Port/address configuration
- Start/Stop listener buttons
- Real-time display of incoming FIZ data
- Option to record FIZ data to CSV for later analysis
- Map incoming zoom values to calibrated focal lengths from current profile

### 3. Preset Lens Profiles (NEW: src/presets/)

Ship approximate distortion profiles for popular cinema lenses. These are starting points that users can refine with actual calibration:

Create `src/presets/` directory with JSON files:
- `cooke_s4i.json` — Cooke S4/i primes (typical set: 18, 25, 32, 50, 75, 100mm)
- `arri_signature.json` — ARRI Signature Primes
- `zeiss_cp3.json` — Zeiss CP.3 compact primes
- `sigma_cine.json` — Sigma Cine FF High Speed primes
- `canon_cne.json` — Canon CN-E primes

Each preset contains approximate values from research data (document 03):
```json
{
  "lens_name": "Cooke S4/i 50mm",
  "lens_family": "Cooke S4/i",
  "type": "prime",
  "calibration_points": [
    {
      "focal_length_mm": 50,
      "k1": -0.08,
      "k2": 0.01,
      "p1": 0.0,
      "p2": 0.0,
      "k3": 0.0,
      "cx": 0.5,
      "cy": 0.5,
      "fx": 0,
      "fy": 0,
      "rms_error": 0,
      "num_images": 0
    }
  ],
  "notes": "Approximate values. Calibrate with your specific lens copy for VP accuracy.",
  "source": "LensU research database"
}
```

Note: These are APPROXIMATE starting points with a big disclaimer. Real lenses vary copy-to-copy. The values should be reasonable ballpark numbers based on our research.

Add to Streamlit sidebar:
- "Load Preset" dropdown with all available preset lenses
- Warning: "Preset values are approximate. Always calibrate your specific lens for VP work."
- After loading, user can calibrate to refine the values

Create `src/presets/__init__.py`:
```python
def list_presets() -> list[dict]:
    """List all available preset profiles."""
    
def load_preset(name: str) -> LensProfile:
    """Load a preset profile."""
```

### 4. Automated Tests (NEW: src/tests/)

Create basic test suite using `pytest`:

```python
# src/tests/test_calibration.py
def test_calibration_point_creation():
    """Test CalibrationPoint dataclass."""

def test_lens_profile_add_calibration():
    """Test adding calibration points to profile."""

def test_lens_profile_json_roundtrip():
    """Test save/load profile JSON."""

def test_anamorphic_info():
    """Test anamorphic data structure."""

# src/tests/test_stmap.py
def test_stmap_generation():
    """Test STMap generation with known values."""

def test_stmap_dimensions():
    """Test STMap output dimensions match input."""

# src/tests/test_ue_export.py
def test_ue_json_structure():
    """Test exported JSON has correct UE structure."""

def test_ue_python_script_generated():
    """Test UE import script is generated."""

# src/tests/test_protocols.py
def test_freed_packet_parsing():
    """Test FreeD D1 packet parsing with known bytes."""

def test_opentrackio_parsing():
    """Test OpenTrackIO JSON parsing."""

# src/tests/test_library.py
def test_library_save_load():
    """Test saving and loading from library."""

def test_library_search():
    """Test library search functionality."""
```

## Dependencies
- No new pip installs (socket, struct, json are stdlib)
- pytest for tests (pip install pytest) — optional, tests can also run with unittest

## Quality Requirements
- Protocol listeners must handle malformed packets gracefully (no crashes)
- Preset values must be clearly marked as approximate
- All tests must pass
- No new pip dependencies for core features (pytest is dev-only)
- ASCII only in print statements

## Test Plan
1. All imports succeed
2. `python -m pytest src/tests/ -v` — all tests pass
3. `streamlit run src/app.py` — app launches with new tabs
4. FreeD parser handles valid D1 packet bytes correctly
5. Preset profiles load without errors

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 6 -- FreeD, OpenTrackIO, presets, tests" --mode now

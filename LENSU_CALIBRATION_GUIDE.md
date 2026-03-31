# LensU Calibration Guide
## Full Process: From Camera Feed to Unreal Engine ULens Import

---

## 1. Prerequisites

### Hardware
- **Camera** with the lens to calibrate
- **Calibration board**: ChArUco (recommended) or checkerboard pattern
  - LensU can generate printable boards (Board Generator tab)
  - ChArUco is more robust: works with partial occlusion and gives sub-pixel accuracy
- **Camera input** (one of):
  - USB webcam (direct)
  - SDI via **Blackmagic DeckLink** card (HD-SDI, 3G-SDI, 12G-SDI)
  - SDI via **AJA** card (Kona, Corvid series)
  - Video file (pre-recorded board footage)
  - Still images (pre-captured board photos)

### Software
- Python 3.10+
- LensU installed (`pip install -e .` from D:\LensU)
- Streamlit (`pip install streamlit`)
- For SDI cards: manufacturer drivers installed (DeckLink Desktop Video / AJA Desktop Software)
- For Unreal import: Unreal Engine 5.x with Camera Calibration plugin enabled

### Driver Setup for SDI Cards

**Blackmagic DeckLink:**
1. Install Blackmagic Desktop Video from blackmagicdesign.com/support
2. After install, open "Blackmagic Desktop Video Setup"
3. Set input connector to SDI (not HDMI)
4. Set input format to match your camera output (1080p25, 1080i50, etc.)
5. The card should appear in Windows Device Manager under "Sound, video and game controllers"
6. LensU accesses it via DirectShow. No additional SDK needed.

**AJA:**
1. Install AJA Desktop Software from aja.com/support
2. Open AJA Control Panel, configure input source and format
3. AJA cards expose a DirectShow capture filter automatically
4. LensU detects it the same way as DeckLink

---

## 2. Launching LensU

```bash
cd D:\LensU
streamlit run src/app.py
```

Opens at http://localhost:8501 by default.

---

## 3. Calibration Workflow

### Step 1: Configure Lens Parameters

In the sidebar:
- **Lens name**: e.g., "Cooke S4/i 32mm"
- **Manufacturer**: e.g., "Cooke"
- **Focal length (mm)**: The marked focal length of the lens
- **Sensor dimensions**: Width and height in mm (from camera spec sheet)
- **Resolution**: Sensor pixel resolution (e.g., 1920x1080, 4096x2160)
- **Lens type**: Spherical, Anamorphic, or Fisheye
- If Anamorphic: set squeeze ratio (1.3x, 1.5x, 2x) and whether input is desqueezed

### Step 2: Choose Calibration Mode

- **Image Upload**: Upload 15-30 pre-captured photos of the board
- **Video Extract**: Upload a video, LensU extracts diverse frames automatically
- **Live Camera**: Real-time capture from USB or SDI source

### Step 3: Live Camera Calibration (SDI workflow)

1. Select "OpenCV Camera" as capture source
2. LensU lists all detected devices. SDI cards appear as:
   - "Blackmagic DeckLink 0 (1920x1080) [DirectShow]"
   - "AJA 0 (1920x1080) [DirectShow]"
3. If an SDI card is detected, configure:
   - **SDI Format**: HD (1920x1080), UHD (3840x2160), or 720p
   - **Frame Rate**: 25, 29.97, 50, 59.94, 23.976, 24
4. Click "Refresh Preview" to confirm signal
5. Point the camera at the calibration board
6. LensU auto-detects the board and shows an overlay
7. **Auto-capture**: When enabled, LensU captures frames automatically when it detects a sufficiently different view (diversity threshold)
8. Move the board (or camera) to cover different regions and angles:
   - All four corners
   - Center
   - Various tilt angles (15-30 degrees)
   - Various distances (board filling 30-80% of frame)
9. Minimum **15 captures** required, **25-30 recommended** for production quality
10. Coverage heatmap shows which frame regions have been covered
11. Live RMS updates as captures accumulate (target: < 0.5px for cinema lenses)

### Step 4: Run Calibration

Once 15+ frames are captured:
1. Click "Calibrate Live Capture Set"
2. LensU computes:
   - Radial distortion coefficients (k1, k2, k3)
   - Tangential distortion (p1, p2)
   - Principal point (cx, cy)
   - Focal length in pixels (fx, fy)
   - RMS reprojection error
3. Quality grade: A+ (< 0.3px), A (< 0.5px), B (< 0.8px), C (< 1.2px), D (< 2.0px)

### Step 5: Review Results

- **Distortion visualization**: Shows barrel/pincushion distortion grid
- **Per-image diagnostics**: Which frames were used, which rejected
- **Coverage heatmap**: Confirms sensor area coverage
- **Breathing analysis** (if multiple focal distances captured)
- **Quality report**: Exportable PDF with all metrics

---

## 4. Export for Unreal Engine

### Step 6: Export ULens Package

In the Export tab, select "Unreal Engine (ULens)" and choose:

**Data Mode:**
- **Parameters**: Exports k1, k2, p1, p2, k3 coefficients directly. Unreal applies them analytically. Best for spherical lenses.
- **STMap**: Exports distortion/undistortion maps as EXR textures. Required for fisheye lenses. Also useful when the parametric model doesn't capture the distortion perfectly.

**Export produces:**
```
[LensName]_calibration/
  [LensName]_calibration.json      # All calibration data
  import_[LensName]_to_ue.py       # Auto-import Python script
  stmaps/                           # (if STMap mode or fisheye)
    [LensName]_32.0mm_stmap.exr
    [LensName]_50.0mm_stmap.exr
```

### Export JSON Structure

```json
{
  "data_mode": "Parameters",
  "lens_info": {
    "lens_name": "Cooke S4i 32mm",
    "sensor_width_mm": 36.0,
    "sensor_height_mm": 24.0,
    "image_width": 4096,
    "image_height": 2160
  },
  "distortion_table": [
    {
      "focus": 0.0,
      "zoom": 32.0,
      "distortion_info": {
        "parameters": [-0.1234, 0.0567, 0.0001, -0.0002, 0.0012]
      },
      "focal_length_info": {
        "fx_fy": [0.8932, 0.8945]
      }
    }
  ],
  "image_center_table": [...],
  "focal_length_table": [...],
  "nodal_offset_table": [...],
  "st_map_table": [...],
  "breathing_profiles": [...]
}
```

---

## 5. Importing into Unreal Engine

### Method A: Python Script (Recommended)

1. Copy the entire export folder to your UE project directory
2. In UE Editor, open **Window > Developer Tools > Output Log**
3. Run the Python script:
   ```
   py "C:/Path/To/import_Cooke_S4i_32mm_to_ue.py"
   ```
4. The script creates a **LensFile** asset at `/Game/LensU/[LensName]`
5. It populates:
   - Distortion parameters (or imports STMap textures)
   - Focal length table
   - Image center (principal point)
   - Nodal offset (if captured)
   - Breathing data (focus-dependent focal length shifts)

### Method B: Manual Import

1. Open UE Editor
2. Enable **Camera Calibration** plugin (Edit > Plugins > search "Camera Calibration")
3. Restart editor
4. Create a new **LensFile** asset: Right-click Content Browser > Miscellaneous > Lens File
5. Open the LensFile and manually enter:
   - **Distortion tab**: Add a point for each focal length
     - Set Focus = 0, Zoom = focal length in mm
     - Enter k1, k2, p1, p2, k3 from the JSON
   - **Focal Length tab**: Enter fx_fy normalized values
   - **Image Center tab**: Enter cx, cy principal point
   - **Nodal Offset tab**: Enter offsets if available

### Method C: STMap Import

1. Import the EXR STMap files into UE Content Browser
2. Set texture properties:
   - Compression: HDR (RGBA16F)
   - sRGB: OFF
   - Mip Gen: No Mipmaps
3. In the LensFile, switch Data Mode to "ST Map"
4. Add ST Map points linking each zoom value to its texture

---

## 6. Using the LensFile in Production

### CineCamera Setup

1. Place a **CineCameraActor** in the scene
2. In Details panel, find **Lens Settings**
3. Set **Lens File**: select your imported LensFile asset
4. Set **Evaluation Mode**: 
   - "Evaluate" for real-time lens distortion
   - "Calibrated" for using the full calibration data

### Live Link Integration

LensU includes a LiveLink emitter (`livelink_emitter.py`) that can stream calibration data to UE in real-time:

```bash
python -m lensu --livelink --host 192.168.1.100 --port 11111
```

This sends focus/zoom tracking data that UE's Camera Calibration system uses to interpolate between calibration points in the LensFile.

### Composure / Virtual Production

For VP work, the LensFile feeds into UE's compositing system:
1. In the CG layer, the LensFile undistorts/redistorts to match the physical lens
2. Ensures CG elements align precisely with the camera's optical characteristics
3. Focus breathing data ensures CG stays matched as the operator pulls focus

---

## 7. Calibration Tips for Best Results

### Board Placement
- Fill 30-80% of the frame with the board
- Avoid extreme angles (> 45 degrees)
- Cover all quadrants of the sensor
- Include some tilted views (15-30 degrees)

### Lighting
- Even, diffuse lighting on the board
- Avoid specular reflections
- Avoid shadows across the board
- Consistent exposure across all captures

### Common Mistakes
- All captures from the same distance/angle (low diversity)
- Board too small in frame (< 20% coverage)
- Motion blur (use adequate shutter speed)
- Dirty lens (calibrates the dirt, not the glass)
- Wrong sensor dimensions entered (invalidates all focal length data)

### Quality Targets
| Use Case | Target RMS | Min Captures |
|----------|-----------|--------------|
| Preview/rough match | < 1.0px | 15 |
| Broadcast/TV | < 0.5px | 20 |
| Cinema/VFX | < 0.3px | 30 |
| Scientific | < 0.2px | 40+ |

---

## 8. Troubleshooting

### SDI card not detected
- Check Device Manager for the capture device
- Ensure DeckLink Desktop Video / AJA Desktop Software is installed
- Try switching between DirectShow and Media Foundation in LensU
- Some cards require a valid input signal to appear as a capture device

### Low RMS but poor visual match
- Check sensor dimensions are correct
- Verify resolution matches actual capture resolution
- For anamorphic: ensure squeeze ratio and desqueeze state are correct

### UE import fails
- Ensure Camera Calibration plugin is enabled and editor restarted
- Check Python is enabled in your UE project (Edit > Plugins > Python)
- Verify JSON file is valid (no corruption during copy)

---

*Generated by LensU v1.9. For issues: github.com/JHRiaza/LensU*

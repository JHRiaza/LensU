# VIVE Mars CamTrack - Deep Dive Research

> Research Date: 2026-03-14
> Focus: Lens Calibration Tool, Workflow, File Formats, and Technical Details

## Overview

VIVE Mars CamTrack is HTC's camera tracking solution designed for virtual production, enabling real-time camera tracking to match physical cinema cameras with virtual cameras in engines like Unreal Engine and Aximmetry.

---

## 1. Calibration Workflow

### Pre-Calibration Requirements

**Hardware:**
- VIVE Mars system
- At least two VIVE Trackers (3.0) — one for the camera ("Rover"), one for the calibration board
- VIVE Base Stations (2.0)
- Calibration board (checkerboard pattern)
- Video capture device (camera)

**Environment:**
- Clear, stable area for the calibration board
- Avoid direct light/reflections on the board
- Tracking volume must be properly set up with base stations

**Setup:**
- Mount the tracker on the camera (using a lens cap or dedicated mount) with the front side of Rover parallel to the camera lens
- Note: The internal screw thread on the bottom of Rover has a depth of 5.5 mm. Exterior screw thread on camera should be no longer than 4.5 mm to avoid damage
- Attach a tracker to the calibration board
- Connect the camera rover to a port (e.g., port 1) and the board rover to another (e.g., port 3)

### Detailed Calibration Process

**Step 1: Launch Calibration Tool**
1. Download Camera Calibration Tool from: https://www.vive.com/mars/cct
2. Open the Camera Calibration Tool on PC
3. Enter the Mars IP and port number (found on Mars dashboard)
4. Click Connect

**Step 2: Configure Settings**
- Select video capture device from "Video source" dropdown
- If video feed is inverted on x-axis, select "Flip horizontally" to correct
- For "Save location", click folder icon and select destination for images and calibration data

**Step 3: Capture Data - First Set**
- Click the play button to start calibration
- Move camera so chessboard pattern falls inside the red frame
- Frame turns blue when properly positioned, tool captures image automatically
- Continue moving camera to capture additional images until prompted to rotate board

**Step 4: Rotate Board -45° (Counterclockwise)**
- Rotate calibration board 45 degrees counterclockwise
- Click Continue and capture second set of images

**Step 5: Rotate Board +45° (Clockwise)**
- Rotate calibration board 45 degrees clockwise (-45 degrees)
- Click Continue and capture third and final set of images

**Step 6: Process and Save**
- Camera Calibration Tool processes images and displays results
- Click "Show in folder" to open save location containing:
  - Calibration images
  - Calibration data (Calibration_Result.txt)

**For Zoom Lenses:**
- Repeat the entire process for multiple focal lengths (e.g., wide, medium, tight)
- Each focal length requires its own calibration set

---

## 2. Calibration File Export

### Output Files

**Primary Output: `Calibration_Result.txt`**
The calibration tool generates a text file containing:
- Focal length values (Fx, Fy)
- Distortion parameters
- Image center coordinates
- Nodal offset data
- Camera sensor information

**Integration with Unreal Engine:**
1. Open Calibration_Result.txt to view calibration data
2. In Unreal Engine, enable Camera Calibration plug-in
3. Create a Lens File asset (Miscellaneous → Lens File)
4. Enter Sensor Dimensions for your camera
5. Add lens data points:
   - Focal Length (Fx, Fy from Calibration_Result.txt)
   - Distortion
   - Image Center
   - Nodal Offset
6. Apply Lens File to CineCameraActor via LiveLinkComponent Controller

### Note on .ulens Files

VIVE Mars does **not** export .ulens files directly. Instead:
- Calibration data is saved as `Calibration_Result.txt`
- In Unreal Engine, this data is imported into a "Lens File" asset (.uasset format)
- The .ulens extension appears to be used in other contexts (possibly OpenCV or third-party tools), but VIVE's native workflow uses .txt → Lens File pipeline

---

## 3. Checkerboard Requirements

Based on the official documentation and workflow:

**Pattern Type:** Standard chessboard/checkerboard pattern

**Kit Contents:**
- VIVE provides a calibration kit that includes items for assembling the calibration board
- The board is placed inside the tracking area during camera calibration

**Capture Requirements:**
- Board must be visible within the red frame in the Camera Calibration Tool
- Frame turns blue when proper focus/positioning is achieved
- Three sets of captures required:
  1. Board straight (0°)
  2. Board rotated -45° (counterclockwise)
  3. Board rotated +45° (clockwise)

**Environment Considerations:**
- Avoid direct lighting on the board
- Avoid reflections on the board surface
- Clear, stable tracking environment required

---

## 4. Supported Distortion Models

VIVE Mars calibration computes the following lens parameters:

| Parameter | Description |
|-----------|-------------|
| **Focal Length** | Fx, Fy (horizontal and vertical) |
| **Distortion** | Lens distortion coefficients (radial and tangential) |
| **Image Center** | Principal point coordinates (cx, cy) |
| **Nodal Offset** | Distance between camera optical center and tracker mounting point |

**In Unreal Engine, these map to:**
- Lens File → Focal Length
- Lens File → Distortion
- Lens File → Image Center  
- Lens File → Nodal Offset

The specific mathematical distortion model (e.g., Brown-Conrady, Fisheye, etc.) is not explicitly documented in VIVE's public materials, but the parameters suggest standard pinhole + radial/tangential distortion model used in OpenCV and similar tools.

---

## 5. Accuracy Specifications

**Official VIVE Specifications:**
- VIVE Mars claims sub-millimeter tracking accuracy
- The system uses Lighthouse base stations (2.0) for tracking
- Combined with lens calibration, enables precise matching of virtual and real cameras

**Real-World Performance Factors:**
- Quality of checkerboard detection
- Number of calibration images captured
- Stability of tracker mounting
- Environmental conditions (tracking interference)
- Camera resolution and lens quality

**Compared to Other Tools:**

| System | Accuracy | Notes |
|--------|----------|-------|
| VIVE Mars | Sub-mm (claimed) | Lighthouse 2.0 tracking |
| OptiTrack | ~0.2mm | Marker-based, professional grade |
| SteamVR Tracking | ~0.2mm | Similar to Lighthouse |
| OpenCV Charuco | ~1-2px reprojection | Depends on checkerboard quality |

VIVE Mars is positioned as a mid-range solution between consumer-grade tracking and high-end professional systems (like OptiTrack).

---

## 6. Integration with Virtual Production Engines

### Unreal Engine
- Uses Camera Calibration plug-in
- Creates Lens File assets from calibration data
- Integrates via LiveLink for real-time tracking
- Supports multiple focal length presets for zoom lenses

### Aximmetry
- Dedicated VIVE Mars setup documentation
- Real-time camera + lens calibration integration
- Tracker-to-camera offset calibration

### Other Engines
VIVE Mars outputs tracking data via standard protocols (VRPN, LiveLink), allowing integration with various engines and applications that support these interfaces.

---

## 7. Key Resources and Documentation

### Official VIVE Support Pages
1. **Camera Calibration Overview:** https://www.vive.com/us/support/camtrack/category_howto/camera-calibration.html
2. **Collecting Calibration Data:** https://www.vive.com/us/support/camtrack/category_howto/collecting-calibration-data-using-the-camera-calibration-tool.html
3. **Importing to Unreal Engine:** https://www.vive.com/us/support/camtrack/category_howto/importing-calibration-data-into-unreal-engine.html
4. **Setting Up VIVE Mars:** https://www.vive.com/us/support/camtrack/category_howto/setting-up-vive-mars-camtrack.html

### Camera Calibration Tool Download
- **URL:** https://www.vive.com/mars/cct
- **Installer:** calibration-tool-installer_v1.2.5.3_signed.msi (version may vary)

### YouTube Tutorials
1. **Official VIVE Mars CamTrack - Camera Calibration (9:51):** https://www.youtube.com/watch?v=a5qW2lLcOuw
2. **VIVE Mars CamTrack lens & tracker calibration in Aximmetry:** https://www.youtube.com/watch?v=gufSQGqbhUA
3. **VIVE Mars Tutorials Playlist:** https://www.youtube.com/playlist?list=PLgyuuFPWR9JJw0d32PUJeh2RnosMomLBG

### Third-Party Resources
- **Aximmetry VIVE Mars Setup:** https://aximmetry.com/learn/virtual-production-workflow/tracking/setting-up-specific-tracking-systems/htc-vive-mars-setup/
- **VIVE Mars Notion (Calibration Kit):** https://vive-mars.notion.site/Calibration-kit-dff5145df825486aa1731941f9902758

---

## 8. Summary

VIVE Mars CamTrack provides a streamlined camera calibration workflow designed specifically for virtual production. The key findings:

1. **Workflow:** Checkerboard-based calibration with 3 capture positions (0°, -45°, +45°) using VIVE Trackers for both camera and calibration board

2. **Output Format:** Not .ulens, but `Calibration_Result.txt` which is imported into Unreal Engine's native Lens File system

3. **Checkerboard:** Standard chessboard pattern, provided in VIVE's calibration kit; requires clear visibility and multiple angles

4. **Distortion Models:** Standard lens distortion parameters (focal length, principal point, radial/tangential distortion, nodal offset) - exact mathematical model not publicly specified

5. **Accuracy:** Claims sub-millimeter tracking through Lighthouse 2.0; positioned between consumer and professional-grade solutions

6. **Best For:** Mid-budget virtual production, real-time tracking workflows with Unreal Engine or Aximmetry

---

*Research compiled from VIVE official documentation, support pages, and tutorial videos.*
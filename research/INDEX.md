# LensU Research Index

> **Purpose:** Quick-reference index so Opus can load exactly what it needs without reading ~170KB of raw research.
> **Usage:** Read this file first. Then `Read` only the specific sections needed from the source docs.
> **Compiled:** 2026-03-14 from 11 research agents (4 Sonnet, 7 Kimi/MiniMax)

## Documents

| # | File | KB | Topics |
|---|------|----|--------|
| 01 | `01_ue_lens_system.md` | 16 | ULens format, Python API, Camera Cal plugin, distortion models, STMaps |
| 02 | `02_commercial_calibration_systems.md` | 21 | Mo-Sys, Trackmen, VIVE Mars, Ncam, Stype, Kalibrate, comparison matrix |
| 03 | `03_cinema_lens_calibration.md` | 17 | Cinema lens families, FIZ encoders, nodal point methodology, zoom challenges |
| 04 | `04_opencv_calibration.md` | 42 | OpenCV calibration API, UE mapping, ChArUco vs checkerboard, code examples |
| 05 | `05_ue_version_changes.md` | 8 | UE 5.4-5.7 Camera Cal plugin changes, LiveLink, CineCamera |
| 06 | `06_mosys_deep_dive.md` | 15 | Mo-Sys VP Pro, StarTracker, OpenTrackIO protocol, Canon VP integration |
| 07 | `07_trackmen_deep_dive.md` | ~10 | Trackmen/Pixotope, VioTrack, FreeD protocol, lens cal workflow |
| 08 | `08_vive_mars_deep_dive.md` | 10 | VIVE Mars CamTrack, Calibration_Result.txt format, Lighthouse 2.0 |
| 09 | `09_stmap_deep_dive.md` | 24 | STMap format (EXR float), Python generation, Nuke-to-UE pipeline |
| 10 | `10_lens_metadata_protocols.md` | 10 | Cooke /i (v1/v2/v3), ARRI LDS/LBUS, Zeiss eXtended Data |

**Total: ~170KB of indexed research**

---

## Quick-Reference: Key Facts for Implementation

### UE LensFile API (from 01)
- **Class:** `unreal.LensFile` (plugin: CameraCalibrationCore)
- **Data indexed by:** Focus (float) + Zoom (float) — the FIZ paradigm
- **5 data tables:** Distortion, FocalLength, ImageCenter, NodalOffset, STMap
- **Key methods:** `add_distortion_point(focus, zoom, DistortionInfo, FocalLengthInfo)`, `add_focal_length_point(focus, zoom, FocalLengthInfo)`, `add_image_center_point(focus, zoom, ImageCenterInfo)`, `add_nodal_offset_point(focus, zoom, NodalPointOffset)`, `add_st_map_point(focus, zoom, STMapInfo)`
- **Evaluation:** `evaluate_distortion_parameters(focus, zoom)` — interpolates between calibrated points
- **Data modes:** Parameters (mathematical model) vs STMaps (texture-based)
- **Asset creation:** `unreal.AssetToolsHelpers.get_asset_tools().create_asset()`
- **.ulens format:** Internal Epic binary format — no public spec. Must create via UE Python API.

### OpenCV → UE Parameter Mapping (from 04)
- **OpenCV model:** Brown-Conrady with k1-k6, p1-p2, s1-s4, tauX, tauY (up to 14 coefficients)
- **UE DistortionInfo:** Generic `parameters` array — model-dependent
- **Coordinate diff:** OpenCV = top-left origin, pixel units → UE = normalized [0,1], center-relative
- **Image center conversion:** `ue_cx = opencv_cx / image_width`, `ue_cy = opencv_cy / image_height`
- **Focal length conversion:** `ue_fx = opencv_fx / image_width` (normalized)
- **Distortion coefficients:** k1, k2, p1, p2, k3 map directly (same mathematical model)

### VP Accuracy Standards (from 04)
- **Acceptable RMS error for VP:** <0.3 pixels
- **Good:** <0.5 pixels
- **Minimum images:** 15-40 depending on lens type
- **Coverage:** All 4 quadrants + center, multiple angles (15°-45° tilt)

### Cinema Lens Specifics (from 03)
- **T-stops ≠ F-stops** — T-stops measure actual light transmission
- **Lens breathing:** Focal length shifts with focus — needs dynamic calibration
- **ARRI Master Primes:** <0.1% distortion across most focal lengths
- **Metadata systems:** Cooke /i, ARRI LDS, Zeiss eXtended Data — provide real-time FIZ
- **Zoom calibration points:** Minimum 8-10 focal lengths for smooth interpolation
- **Nodal point varies** with focal length AND focus distance

### STMap Workflow (from 09)
- **Format:** EXR float, S=Red channel (X coords), T=Green channel (Y coords)
- **Resolution:** 512x512 preview, match plate resolution for production, UE uses 128x128 displacement maps typical
- **Generation:** From OpenCV calibration data using `cv2.initUndistortRectifyMap()`
- **UE import:** `lens_file.add_st_map_point(focus, zoom, STMapInfo)` with `data_mode = STMap`
- **vs Parametric:** STMaps handle complex distortion better, parameters are lighter/faster

### Tracking Protocols (from 06, 07)
- **FreeD:** UDP D1 packets (Pan/Tilt/Roll, X/Y/Z, Zoom, Focus) — industry standard, limited params
- **OpenTrackIO:** JSON/CBOR over UDP multicast — Mo-Sys led, SMPTE RIS-OSVP, includes distortion coefficients
- **Cooke /i:** Real-time FIZ + distortion maps + shading data (resistive sensing strips)
- **ARRI LDS:** LBUS interface, integrated with ALEXA 35/Mini LF, WCU-4

### Lens Metadata Protocols (from 10)
- **Cooke /i3 (Cubed, 2018):** Most data — distortion maps, shading, DOF, up to 285fps
- **ARRI LDS:** Focus/iris/zoom + timecode sync, LBUS hardware interface
- **Zeiss eXtended Data:** Focus/iris/zoom + distortion maps + vignetting, integrated into Cooke /i

### Commercial System Comparison (from 02, 06, 07, 08)
| System | Method | Protocol | UE Integration | Zoom | Price |
|--------|--------|----------|---------------|------|-------|
| Mo-Sys VP Pro | StarTracker optical | OpenTrackIO/FreeD | LiveLink plugin | Yes (encoder) | $$$$$ (subscription) |
| Trackmen/Pixotope | Optical markers | FreeD (UDP D1) | LiveLink | Yes | $$$$ |
| VIVE Mars CamTrack | Lighthouse 2.0 | Calibration_Result.txt | Camera Cal plugin import | Yes | $$$ |
| Stype RedSpy | IR markers + TWIM | Proprietary | Plugin | Yes | $$$$ |
| Ncam Reality | Pattern-based | Proprietary (Epic-owned) | Native | Yes | $$$$ |
| Kalibrate | Checkerboard | JSON export | Python script → .uasset | Manual | $100 |
| **LensU (ours)** | Checkerboard/ChArUco | JSON export | Python script → .ulens | Multi-focal | **Free** |

### Kalibrate Limitations (our competitive advantage)
- Only calibrates K1 distortion (single radial coefficient)
- No tangential distortion (P1, P2)
- No K2, K3 (higher-order radial)
- No nodal offset estimation
- No STMap generation
- No zoom lens multi-focal workflow (manual per focal length)
- LensU already does all of the above

### Key UE Version Notes (from 05)
- **UE 5.4:** Basic Camera Cal plugin + LensFile support
- **UE 5.5:** Enhanced LiveLink + lens distortion improvements
- **UE 5.6:** No documented Camera Cal changes
- **UE 5.7:** Camera Cal plugin docs restructured/redirected — may have moved modules
- **No breaking .ulens format changes documented** between 5.4-5.7

---

## Section Navigation (line numbers for targeted reads)

### 01_ue_lens_system.md (16KB)
- Lines 1-20: Overview + TOC
- Lines 21-80: Python API (LensFile class, all methods)
- Lines 80-150: Data structures (DistortionInfo, FocalLengthInfo, ImageCenterInfo, NodalPointOffset)
- Lines 150-250: Camera Calibration plugin workflow
- Lines 250-350: Distortion models in UE
- Lines 350+: STMap workflow

### 02_commercial_calibration_systems.md (21KB)
- Lines 1-15: TOC
- Lines 16-100: Mo-Sys (StarTracker, lens encoding, data format)
- Lines 100-150: Trackmen
- Lines 150-230: VIVE Mars CamTrack (.ulens export)
- Lines 230-280: Ncam
- Lines 280-340: Stype (RedSpy, TWIM)
- Lines 340-400: Kalibrate (JSON format, Python script, limitations)
- Lines 400+: Other tools + comparison matrix

### 03_cinema_lens_calibration.md (17KB)
- Lines 1-10: Executive summary
- Lines 11-60: Cinema lens characteristics (T-stops, breathing, families)
- Lines 60-130: Lens metadata systems (Cooke /i, ARRI LDS, Zeiss eXtended)
- Lines 130-200: FIZ encoders (Preston, Heden, ARRI WCU-4, Tilta)
- Lines 200-270: Nodal point calibration methodology
- Lines 270-340: Zoom lens challenges
- Lines 340-400: Distortion characteristics by lens family
- Lines 400+: Best practices

### 04_opencv_calibration.md (42KB)
- Lines 1-50: calibrateCamera() API + Brown-Conrady model
- Lines 50-150: All distortion coefficients explained (k1-k6, p1-p2, s1-s4)
- Lines 150-250: Calibration flags reference
- Lines 250-350: OpenCV → UE coordinate mapping + conversion formulas
- Lines 350-450: ChArUco vs Checkerboard comparison
- Lines 450-550: Accuracy standards + image count recommendations
- Lines 550-800: Complete Python code examples
- Lines 800+: Advanced techniques (rational model, fisheye, stereo)

### 05-10: Deep dives (read on demand)
- 05: UE 5.4-5.7 changes
- 06: Mo-Sys (OpenTrackIO protocol spec, Canon VP integration)
- 07: Trackmen/Pixotope (FreeD protocol, VioTrack)
- 08: VIVE Mars (Calibration_Result.txt format, Lighthouse workflow)
- 09: STMap (EXR generation, Python code, Nuke pipeline)
- 10: Lens metadata (Cooke /i3, ARRI LDS, Zeiss eXtended specs)

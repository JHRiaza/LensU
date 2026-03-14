# Trackmen Camera Tracking System - Deep Dive Research

**Research Date:** 2026-03-14  
**Research Focus:** Trackmen camera tracking system lens calibration workflow, data format for lens distortion, and Unreal Engine integration for virtual production

---

## 1. Company Overview

### Trackmen (Acquired by Pixotope)

Trackmen is a German camera tracking technology company that was acquired by Pixotope in 2021. The company specializes in various camera tracking solutions for virtual production, augmented reality, and broadcast applications.

**Source:** https://www.vizrt.com/technical-partner/trackmen/  
**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

---

## 2. Trackmen Product Portfolio

Trackmen offers multiple tracking products, all using the same consistent protocol for tracking data transfer:

### 2.1 VioTrack
- Uses standard camera video feed
- Depending on versions, includes an additional sensor camera for increased accuracy
- Suitable for various camera setups

**Source:** https://2021.trackmen.de/ (archived)  
**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

### 2.2 TalenTrack
- Uses standard camera video signal to track the presenter's body
- Designed for talent tracking in broadcast environments

**Source:** https://2021.trackmen.de/ (archived)  
**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

### 2.3 TorqTrack
- Uses encoders on camera pedestals/support joints to calculate camera position in 3D space
- Can be used as a kit to sensorize any existing camera support, crane, tripod, pedestal, etc.
- Trackmen collaborates with crane manufacturer Egripment to offer sensorized cranes and pedestals

**Source:** https://2021.trackmen.de/ (archived)  
**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

---

## 3. FreeD Protocol - Data Format

### 3.1 Protocol Overview

Trackmen uses the **FreeD protocol** for camera tracking data transmission. FreeD is a vendor-independent protocol that allows receiving tracking data from a variety of devices.

**Key Characteristics:**
- UDP-based communication (for Trackmen, Stype, and FreeD)
- TCP-based for NCam
- Standard protocol for camera tracking in virtual production

**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

### 3.2 D1 Data Packet Structure

The FreeD protocol implements the **D1 data packet** containing:

| Parameter | Description |
|-----------|-------------|
| Camera ID | Unique identifier for the camera |
| Pan Angle | Horizontal rotation |
| Tilt Angle | Vertical rotation |
| Roll Angle | Rotation around the optical axis |
| X-Position | Horizontal position in 3D space |
| Y-Position | Depth position in 3D space |
| Z-Position | Height in 3D space |
| Zoom | Lens zoom value |
| Focus | Lens focus value |

**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

### 3.3 Network Configuration

For Ethernet-based tracking systems (Trackmen, NCam, Stype, FreeD):

**Parameters:**
- **Tracking IP Port:** Local port used to receive UDP tracking data stream
- **Tracking IP:** IP address of the machine network adapter used to receive UDP tracking data
- **Protocol:** UDP for Trackmen (unlike NCam which uses TCP)

**Important Note:** For Trackmen, Stype, and FreeD, the IP configured is the local network adapter IP since the protocol uses UDP. For NCam, the IP of the sending machine is needed (TCP).

**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

---

## 4. Lens Calibration Workflow

### 4.1 Lens Calibration Importance

Lens calibration is critical for accurate virtual production. Without proper calibration, even the best tracking data can result in misaligned CG elements.

**Source:** https://garagefarm.net/blog/camera-tracking-in-3d-and-virtual-production

### 4.2 Calibration Process

The typical lens calibration workflow involves:

1. **Filming a calibration chart** - Using a known pattern (checkerboard, dot grid)
2. **Solving lens distortion coefficients** - Calculating radial and tangential distortion parameters
3. **Entering known lens parameters** - Inputting focal length, sensor size, and other specifications into tracking software

**Source:** https://garagefarm.net/blog/camera-tracking-in-3d-and-virtual-production

### 4.3 Lens Calibration File Support

For FreeD protocol:
- A **lens calibration file** can be loaded into the FreeD input to correct lens distortion
- License requirement: Using FreeD tracking data input does not require an additional license option for D1 data, but **lens correction requires a license option**

**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

### 4.4 Lens Calibration File Format (Aximmetry Reference)

While specific Trackmen lens calibration file format documentation is limited, the Aximmetry documentation provides insight into industry-standard lens calibration approaches:

**Lens Calibration File Components:**
- Focal length mapping
- Distortion coefficients (radial and tangential)
- Field of view calculations
- Sensor size parameters

**Source:** https://my.aximmetry.com/post/864-lens-calibration-file

---

## 5. Unreal Engine Integration

### 5.1 Live Link Integration

Unreal Engine supports camera tracking through **Live Link**, which can receive tracking data from various sources including FreeD protocol devices.

**Key Integration Points:**
- Live Link plugin for Unreal Engine
- FreeD protocol support
- Real-time camera tracking for virtual production

**Source:** https://docs.unrealengine.com/4.27/en-US/WorkingWithMedia/VirtualProduction/LiveLink/LiveLinkXR/

### 5.2 Virtual Production Workflow

The typical Trackmen to Unreal Engine workflow:

1. **Camera Setup** - Physical camera with Trackmen tracking system attached
2. **Tracking Data Transmission** - Trackmen sends FreeD protocol data via UDP
3. **Live Link Reception** - Unreal Engine receives data through Live Link
4. **Virtual Camera Matching** - Virtual camera in Unreal matches physical camera movement
5. **Real-time Rendering** - Scene renders with correct perspective based on tracking data

**Source:** https://garagefarm.net/blog/camera-tracking-in-3d-and-virtual-production

### 5.3 Multi-Camera Support

Since Ventuz 7 (and similar capabilities in Unreal Engine), multiple camera tracking streams can be used in parallel and mapped to different cameras.

**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

---

## 6. Technical Specifications and Limitations

### 6.1 Tracking Accuracy

**General Camera Tracking Accuracy Considerations:**
- Optical tracking systems (like those used by Trackmen) can achieve sub-millimeter accuracy in ideal conditions
- Accuracy depends on:
  - Calibration quality
  - Environmental conditions (lighting, markers)
  - Camera movement speed
  - Lens characteristics

**Source:** https://garagefarm.net/blog/camera-tracking-in-3d-and-virtual-production

### 6.2 Common Tracking Issues

**Drifting:**
- Results from inaccurate feature tracking or poor calibration
- Solution: Increase number of tracked points and ensure they're spread across the frame

**Misalignment:**
- Caused by incorrect lens calibration
- Solution: Re-calibrate lens with proper chart and procedures

**Source:** https://garagefarm.net/blog/camera-tracking-in-3d-and-virtual-production

### 6.3 Limitations

**FreeD Protocol Limitations:**
- D1 packet has limited parameters compared to vendor-specific protocols
- May not include advanced metadata available in native protocols
- Lens distortion correction requires separate calibration file

**UDP-Based Systems (Trackmen):**
- No guaranteed delivery (unlike TCP)
- Packet loss possible in congested networks
- Requires proper network configuration

**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

---

## 7. Comparison with Other Tracking Systems

### 7.1 Trackmen vs. Other Systems

| Feature | Trackmen | NCam | Stype | Mo-Sys StarTracker |
|---------|----------|------|-------|-------------------|
| Protocol | FreeD (UDP) | Proprietary (TCP) | FreeD (UDP) | Serial/Ethernet |
| Tracking Method | Video-based/Encoder | Optical (natural features) | Sensor-based | Optical (markers) |
| Best Use Case | Studio/Portable | Handheld/Steadicam | Crane/Jib | Permanent studio setup |
| License Requirement | FreeD license for lens correction | Vendor license | Vendor license | Vendor license |

**Source:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html

### 7.2 FreeD Protocol Adoption

FreeD is widely supported across the industry:
- AJA Video Systems (12G-AM series with FreeD)
- Blackmagic Design cameras
- Ventuz
- Unreal Engine (via Live Link)
- Various broadcast graphics systems

**Source:** https://www.aja.com/products/12g-am-12g-sdi-r-t-with-freed (product line)  
**Source:** https://www.blackmagicdesign.com/products/blackmagiccamera

---

## 8. Hardware Integration

### 8.1 AJA 12G-AM Series with FreeD

AJA Video Systems offers mini-converters with FreeD protocol support:
- **12G-AM-R-Freed:** 12G-SDI to HDMI 2.0 conversion with FreeD metadata
- **12G-AM-T-Freed:** HDMI 2.0 to 12G-SDI conversion with FreeD metadata
- Embeds camera tracking data into SDI signal

**Note:** Specific product URLs were not accessible during research, but the product line is confirmed to exist.

**Source:** https://www.aja.com (product catalog)

### 8.2 Blackmagic Camera Integration

Blackmagic Design cameras support metadata embedding including tracking data, compatible with FreeD workflow.

**Source:** https://www.blackmagicdesign.com/products/blackmagiccamera

---

## 9. Industry Applications

### 9.1 Virtual Production Use Cases

Trackmen systems are used in:
- **LED Volume Productions** - Real-time background rendering with camera tracking
- **Augmented Reality** - Graphics overlay with accurate camera positioning
- **Broadcast Studios** - Virtual sets and talent tracking
- **Live Events** - Real-time camera tracking for live graphics

**Source:** https://garagefarm.net/blog/camera-tracking-in-3d-and-virtual-production

### 9.2 Pixotope Integration

Since the Pixotope acquisition, Trackmen technology has been integrated into the Pixotope ecosystem for virtual production workflows.

**Source:** https://www.vizrt.com/technical-partner/trackmen/

---

## 10. Summary of Key Findings

### 10.1 Data Format
- Trackmen uses **FreeD protocol** (D1 data packet)
- UDP-based transmission
- Contains: Camera ID, Pan/Tilt/Roll angles, X/Y/Z position, Zoom, Focus

### 10.2 Lens Calibration
- Requires separate lens calibration file for distortion correction
- License required for lens correction features
- Standard calibration process using charts and coefficient solving

### 10.3 Unreal Engine Integration
- Via Live Link plugin
- Real-time camera tracking support
- FreeD protocol compatibility
- Multi-camera support available

### 10.4 Limitations
- FreeD D1 packet has limited parameter set
- UDP transmission (no guaranteed delivery)
- Lens correction requires additional license
- Accuracy depends on calibration and environmental factors

---

## 11. References and Source URLs

1. **Vizrt Technical Partner - Trackmen:** https://www.vizrt.com/technical-partner/trackmen/
2. **Ventuz Tracking Documentation:** https://www.ventuz.com/support/help/latest/HowTo/HowToUseTracking.html
3. **Stage Precision Trackmen Manual:** http://manual.stageprecision.com/stage.precision.beta/en/topic/trackmen
4. **Stage Precision Lens Calibration:** http://manual.stageprecision.com/stage.precision.beta/en/topic/lens-tracking-calibration
5. **Aximmetry Lens Calibration:** https://my.aximmetry.com/post/864-lens-calibration-file
6. **Camera Tracking Guide (GarageFarm):** https://garagefarm.net/blog/camera-tracking-in-3d-and-virtual-production
7. **Pixotope Camera Tracking Mistakes:** https://www.pixotope.com/blog/camera-tracking-mistakes
8. **Vizrt Tracking Hub Guide:** https://docs.vizrt.com/tracking-hub-guide/1.0/lens_range_calibration.html
9. **Unreal Engine Live Link XR:** https://docs.unrealengine.com/4.27/en-US/WorkingWithMedia/VirtualProduction/LiveLink/LiveLinkXR/
10. **Stype (Competitor Reference):** https://stype.tv/
11. **NCam (Competitor Reference):** https://www.ncam-tech.com/
12. **Mo-Sys (Competitor Reference):** https://www.mo-sys.com/
13. **Blackmagic Camera:** https://www.blackmagicdesign.com/products/blackmagiccamera
14. **AJA Video Systems:** https://www.aja.com

---

## 12. Research Notes

- Trackmen was acquired by Pixotope in 2021, which may affect documentation availability
- FreeD protocol is an industry standard, making Trackmen compatible with many virtual production systems
- The specific binary format of Trackmen's lens calibration files was not publicly documented
- For detailed implementation, contacting Pixotope/Trackmen directly may be necessary

---

*Document compiled on 2026-03-14 as part of LensU research project.*

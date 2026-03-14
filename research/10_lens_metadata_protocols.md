# Lens Metadata Protocols Technical Specification

## Executive Summary

This document provides a comprehensive technical specification of three major lens metadata protocols used in professional cinematography: Cooke /i, ARRI LDS (Lens Data System), and Zeiss eXtended Data. These protocols enable real-time transmission of lens parameters (focus, iris, zoom) and additional optical data for post-production and virtual production workflows.

---

## 1. Cooke /i Technology

### 1.1 Overview

Cooke /i Technology is a metadata protocol developed by Cooke Optics that enables film and digital cameras to automatically record key lens data for every frame shot. It is one of the most widely adopted lens metadata standards in the industry.

**Official Documentation:** https://cookeoptics.com/i-technology/

### 1.2 Real-Time Data Transmission

**Focus Data:**
- Focus distance in meters or feet (user-selectable)
- Absolute position values from resistive sensing strips calibrated in absolute values
- Data available instantly upon power application without initialization procedure

**Iris/T-Stop Data:**
- T-stop value (not f-stop) for accurate exposure
- Real-time T-stop readout for viewfinder display

**Zoom Data:**
- Focal length position
- Horizontal field of view calculation

**Frame Rate Support:**
- Up to 285 fps for film and digital cameras
- Data recorded for every frame

### 1.3 Additional Data Provided

**Lens Identification:**
- Serial number (format: xxxx.xxxx for /i2 and /i3, xxxx-xxxx for older lenses)
- Lens type/model
- Equipment identification via serial number

**Depth of Field Calculations:**
- Near focus limit
- Far focus limit
- Hyperfocal distance

**Optical Properties (via /i² and /i³ versions):**
- Entrance pupil position
- Distortion mapping data
- Shading/vignetting data

### 1.4 Technical Implementation

**Communication Protocol:**
- Proprietary Cooke /i protocol
- Lens electronics connect to resistive sensing strips calibrated in absolute values
- Continuous mode available for constantly updated data stream up to 285 fps

**Data Format:**
- Metric or Imperial (user-selectable)
- Digital storage for every frame
- Backward compatible with standard /i Technology software

### 1.5 Versions

| Version | Year Introduced | Key Features |
|---------|---------------|--------------|
| /i (original) | ~2002 | Basic focus, iris, zoom, T-stop |
| /i² | 2014 | Enhanced shading and distortion mapping |
| /i³ (Cubed) | 2018 | Full metadata including distortion/shading data |

### 1.6 Programmatic Access

Cooke provides downloadable shading and distortion mapping files by lens serial number:
- **Source:** https://www.cookeoptics.com/i-cubed-technology/
- **Data Portal:** https://www.cookeoptics.com/i-technology (look for "Shading & Distortion Mapping" section)

---

## 2. ARRI LDS (Lens Data System)

### 2.1 Overview

ARRI's Lens Data System (LDS) is a metadata standard developed by ARRI that transmits lens data through a digital interface. LDS is closely integrated with ARRI camera systems and the ARRI Electronic Control System (ECS).

**Reference:** https://www.arri.com/en/camera-systems/electronic-control-system

### 2.2 Real-Time Data Transmission

ARRI LDS transmits the following parameters in real-time:

**Core Parameters:**
- Focus distance
- T-stop/Iris position
- Zoom (focal length)
- Frame rate
- Shutter angle

**Data Output:**
- Digital output through LBUS (ARRI Lens Bus)
- Integrated with ARRI's Hi-5, WCU-4, and other hand units
- Support for lens motors with built-in encoders

### 2.3 Additional Data

ARRI's ecosystem provides:
- Lens metadata storage and recording
- Timecode synchronization
- Support for third-party lens motors via LDS-2 compatibility

### 2.4 Technical Integration

**Hardware Interface:**
- LBUS (Lens Bus) connection
- Compatible with ARRI EF Mount and other lens mounts
- Wireless connectivity via ARRI radio systems

**Camera Integration:**
- ALEXA 35, AMIRA, ALEXA Mini LF support
- Metadata recorded directly to camera's recording format
- Integration with ARRI Capture Drive and Codex recording systems

### 2.5 Documentation Reference

ARRI provides technical documentation through their electronic control system pages:
- **ECS Overview:** https://www.arri.com/en/camera-systems/electronic-control-system
- **Hi-5 Ecosystem:** https://www.arri.com/en/camera-systems/electronic-control-system/hi-5-ecosystem
- **LDS-2 Specification:** Available through ARRI partner program

---

## 3. Zeiss eXtended Data

### 3.1 Overview

Zeiss eXtended Data is a metadata protocol developed by Zeiss that provides comprehensive lens data including shading and distortion correction information. It was developed in collaboration with Cooke and is included in Cooke /i Technology.

**Reference:** https://www.cookeoptics.com/i-cubed-technology/ (mentions "ZEISS eXtended data is included in Cooke /i Technology")

### 3.2 Real-Time Data Transmission

**Core Parameters:**
- Focus distance
- Iris/T-stop
- Zoom position
- Serial number identification

### 3.3 Additional Data

**Optical Correction Data:**
- Shading/vignetting maps
- Distortion correction data
- These files can be downloaded post-shoot using lens serial numbers

**Post-Production Benefits:**
- Automatic lens distortion correction in VFX
- Shading compensation in DI (Digital Intermediate)
- More accurate 3D camera matching

### 3.4 Integration

Zeiss eXtended Data is compatible with:
- Cooke /i Technology ecosystem (data included in /i protocol)
- ARRI camera systems
- Various VFX software packages

---

## 4. Virtual Production Integration with Unreal Engine

### 4.1 Overview

Lens metadata is crucial for virtual production workflows using LED volumes and real-time rendering engines like Unreal Engine. Accurate lens data enables:

- Proper lens distortion correction in real-time
- Accurate camera matching between physical and virtual cameras
- Perspective-accurate compositing of rendered elements

### 4.2 Integration Methods

**Direct Camera Data Feed:**
- Lens metadata recorded from cameras with LDS or /i support
- Data routed to Unreal Engine via Spout, NDI, or custom plugins
- Real-time lens distortion and shading correction

**Camera Tracking Systems:**
- Integration with tracking systems (Stype, Mo-Sys, Black Trax)
- Lens data synchronized with camera position/orientation
-庚 [Note: Further technical details require specific VP system documentation]

### 4.3 Post-Production Workflow

The typical virtual production lens metadata workflow:

1. **On Set:** Lens metadata recorded via /i, LDS, or eXtended Data
2. **Export:** Metadata exported with footage or as separate files
3. **Processing:** Distortion/shading maps applied in compositing
4. **Integration:** Matched with 3D camera data for VFX plates

### 4.4 Technical Considerations

**Data Format Compatibility:**
- Cooke /i provides proprietary format
- ARRI LDS integrates with ARRIRAW workflow
- Zeiss eXtended Data delivered as downloadable correction files

**Unreal Engine Support:**
- Lens distortion plugins available
- Custom NDISpigot or Spout integration for real-time data
- [Specific plugin documentation required for implementation details]

---

## 5. Comparative Analysis

| Feature | Cooke /i | ARRI LDS | Zeiss eXtended Data |
|---------|----------|----------|---------------------|
| **Primary Manufacturer** | Cooke Optics | ARRI | Zeiss |
| **Focus Data** | Yes | Yes | Yes |
| **Iris/T-stop** | Yes | Yes | Yes |
| **Zoom Data** | Yes | Yes | Yes |
| **Distortion Maps** | Yes (/i², /i³) | Limited | Yes |
| **Shading Data** | Yes (/i², /i³) | Limited | Yes |
| **Frame Rate Support** | Up to 285 fps | Varies | Varies |
| **Camera Integration** | Multiple (RED, Sony, ARRI) | ARRI | Multiple |
| **Real-time Output** | Yes | Yes | Yes |

---

## 6. Programmatic Access and Implementation

### 6.1 Reading Lens Metadata

**Python/C++ Libraries:**
- No universal open-source library exists
- Manufacturer SDKs required for proprietary protocols

**Cooke /i Data Access:**
- Through Cinematography Electronics /i Lens Display Unit
- Third-party software: Pomfort, Codex, DaVinci Resolve

**ARRI LDS Data:**
- ARRI ALEXA API
- Codex recording systems
- Pomfort DIT tools

### 6.2 File Formats

- **Cooke:** Proprietary /i format, downloadable XML/JSON for correction data
- **ARRI:** Embedded in ARRIRAW, exported as sidecar files
- **Zeiss:** Downloadable distortion/shading maps (XML-based)

### 6.3 Recommended Development Resources

1. **Cooke Optics Partner Program:** For /i protocol specifications
2. **ARRI Developer Program:** For LDS integration
3. **Zeiss Cinema:** For eXtended Data specifications

---

## 7. Source URLs

| Topic | URL |
|-------|-----|
| Cooke /i Technology Overview | https://cookeoptics.com/i-technology/ |
| Cooke /i³ Technology | https://cookeoptics.com/i-cubed-technology/ |
| ARRI Electronic Control System | https://www.arri.com/en/camera-systems/electronic-control-system |
| ARRI Hi-5 Ecosystem | https://www.arri.com/en/camera-systems/electronic-control-system/hi-5-ecosystem |
| Zeiss eXtended Data (via Cooke) | https://cookeoptics.com/i-cubed-technology/ |

---

## 8. Further Research Needed

The following areas require additional investigation:

1. **Detailed Protocol Specifications:** Direct access to protocol documentation requires partnership/cooperation with manufacturers
2. **Unreal Engine Plugin Documentation:** Specific plugins for lens metadata ingestion need further research
3. **Open Source Implementations:** Community-developed parsers for these protocols need identification
4. **Real-time Data Streaming:** Technical details on TCP/IP or other network protocols for data transmission

---

*Document compiled: 2026-03-14*
*Research scope: Cooke /i, ARRI LDS, Zeiss eXtended Data protocols*
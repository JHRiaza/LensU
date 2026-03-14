# Mo-Sys Virtual Production Camera Tracking & Lens Calibration Deep Dive

**Research Date:** 2026-03-14  
**Researcher:** Subagent Research Sprint  
**Document Version:** 1.0

---

## Executive Summary

Mo-Sys Engineering is a leading innovator in camera tracking technology and Virtual Production (VP) solutions. Their ecosystem includes the StarTracker camera tracking systems, VP Pro Unreal Engine plugin, and the OpenTrackIO open protocol for camera and lens metadata. This document provides a comprehensive analysis of their calibration workflows, data formats, UE integration methods, accuracy specifications, and pricing models.

---

## 1. Product Overview

### 1.1 StarTracker Product Line

| Product | Description | Use Case |
|---------|-------------|----------|
| **StarTracker Max** | Full-scale studio tracking system with external processing | Large LED volumes, broadcast studios, film productions |
| **StarTracker Mini** | Ultra-compact all-in-one system (no external processing) | Content creators, in-house studios, educators, compact spaces |
| **StarTracker Classic** | Original StarTracker system | Established VP workflows |
| **StarTracker PTZ** | Pan-tilt-zoom tracking solution | Automated camera movements |

**Key Differentiator:** Mo-Sys uses **absolute tracking** (optical star map-based) rather than SLAM-based relative tracking, providing:
- Zero drift accumulation
- No re-calibration between setups required
- Immunity to light interference that disrupts SLAM systems
- Sub-millimeter precision

### 1.2 VP Pro Software

VP Pro is Mo-Sys' comprehensive Unreal Engine plugin for Virtual Production, providing:
- Real-time camera tracking integration
- Lens distortion and calibration management
- XR/ICVFX (In-Camera Visual Effects) workflows
- AR graphics compositing
- Multi-camera support

---

## 2. Lens Calibration Workflow

### 2.1 Traditional Calibration Process

Based on Mo-Sys Academy training materials and documentation:

**Step 1: Lens Profile Creation**
- Access the Mo-Sys Lens Library at https://lens.mo-sys.com
- Search for lens by manufacturer and model
- Download base lens file (free for VP Pro VFX/XR license holders)

**Step 2: Physical Setup**
- Mount camera with lens on tripod
- Position calibration chart at appropriate distance
- Ensure even lighting across chart

**Step 3: Calibration Capture**
- Use VP Pro calibration tools within Unreal Engine
- Capture images at multiple focus distances
- For zoom lenses: capture at multiple focal lengths
- System analyzes distortion patterns

**Step 4: Data Processing**
- VP Pro calculates lens distortion model
- Generates lens file with distortion coefficients
- Stores focal length, focus distance, and distortion data

**Step 5: Validation**
- Test calibration with virtual objects
- Verify alignment between real and virtual elements
- Fine-tune if necessary

### 2.2 Canon Virtual Production System Integration (Revolutionary Workflow)

**Major Advancement (September 2025):**
Canon and Mo-Sys collaborated to implement the **CV Protocol** with **OpenLensIO** support, enabling:

- **Single-cable connection**: Lens metadata flows from RF mount → camera body → StarTracker via Ethernet
- **No physical lens encoders required**: Optical data (zoom, focus, aperture, distortion) calculated internally
- **Real-time OpenLensIO output**: Direct JSON metadata transmission
- **Eliminates manual calibration**: Lens manufacturer provides precise optical parameters

**Technical Implementation:**
```
Canon RF Lens → Camera Body (CV Metadata) → Ethernet → StarTracker → OpenTrackIO → Unreal Engine
```

**Benefits:**
- Dramatically reduced setup time
- No personnel required for lens calibration
- Precise real-time data for focus pulls, zooming, framing
- Freely swap lenses without recalibration
- Precise bokeh rendering on CG backgrounds

Source: https://www.mo-sys.com/news/canon_mosys_openlensio_collaboration/

---

## 3. Data Format Specification

### 3.1 OpenTrackIO Protocol

Mo-Sys led the development of **OpenTrackIO**, an open-source protocol standardized by SMPTE RIS-OSVP group. This is the successor to proprietary protocols like FreeD.

**Protocol Characteristics:**
- **Format**: JSON (human-readable) or CBOR (binary)
- **Transport**: UDP multicast (IPv4), default port 55555
- **Rate**: Per-frame transmission (24fps, 30fps, 60fps, etc.)
- **Coordinate System**: Right-handed, Z-up, Y-forward

### 3.2 Sample OpenTrackIO Payload Structure

```json
{
  "protocol": {
    "name": "OpenTrackIO",
    "version": [1, 0, 1]
  },
  "sampleId": "urn:uuid:e925a0d4-206d-4d57-b418-08b076eac650",
  "sourceId": "urn:uuid:81eb1845-4bdc-4825-8333-e911640ebfdd",
  "sourceNumber": 1,
  
  "timing": {
    "mode": "external",
    "sampleRate": {"num": 24, "denom": 1},
    "timecode": {
      "hours": 1, "minutes": 2, "seconds": 3, "frames": 4,
      "frameRate": {"num": 24, "denom": 1}
    }
  },
  
  "transforms": [
    {
      "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
      "rotation": {"pan": 180.0, "tilt": 90.0, "roll": 45.0},
      "id": "Camera"
    }
  ],
  
  "lens": {
    "distortion": [
      {
        "radial": [1.0, 2.0, 3.0],
        "tangential": [1.0, 2.0],
        "overscan": 3.1
      }
    ],
    "encoders": {
      "focus": 0.1,
      "iris": 0.2,
      "zoom": 0.3
    },
    "entrancePupilOffset": 0.123,
    "fStop": 4.0,
    "pinholeFocalLength": 24.305,
    "focusDistance": 10.0,
    "projectionOffset": {"x": 0.1, "y": 0.2}
  },
  
  "tracker": {
    "notes": "Example generated sample.",
    "recording": false,
    "slate": "A101_A_4",
    "status": "Optical Good"
  }
}
```

### 3.3 Lens Data Fields Reference

| Field | Type | Description | Units |
|-------|------|-------------|-------|
| `pinholeFocalLength` | float | Effective focal length | millimeters |
| `focusDistance` | float | Distance to focal plane | meters |
| `fStop` | float | Aperture f-number | f-stop |
| `tStop` | float | Transmission t-number | t-stop |
| `entrancePupilOffset` | float | Entrance pupil position offset | meters |
| `projectionOffset.x` | float | Horizontal projection center offset | normalized |
| `projectionOffset.y` | float | Vertical projection center offset | normalized |
| `encoders.focus` | float | Focus encoder value | normalized (0-1) |
| `encoders.iris` | float | Iris encoder value | normalized (0-1) |
| `encoders.zoom` | float | Zoom encoder value | normalized (0-1) |
| `distortion.radial` | array | Radial distortion coefficients (k1, k2, k3...) | varies |
| `distortion.tangential` | array | Tangential distortion coefficients (p1, p2) | varies |
| `distortion.overscan` | float | Overscan factor for distortion | multiplier |

### 3.4 OpenLensIO Lens Model

OpenTrackIO employs the **OpenLensIO mathematical lens model** for spherical lens distortion in Virtual Production.

**Key Features:**
- Brown-Conrady distortion model support
- Projection matrix-based and field-of-view-based rendering
- Overscan calculation for distortion/undistortion
- Compatible with OpenCV conversion mathematics

**Distortion Model Options:**
- `Brown-Conrady U-D`: Undistortion model
- `Brown-Conrady D-U`: Distortion model
- Custom vendor-specific models (0x80+)

Source: https://www.opentrackio.org/ (SMPTE RIS-OSVP)

### 3.5 Legacy FreeD Protocol Support

VP Pro 5.5+ includes **FreeD tracking support with lens distortion**, enabling compatibility with third-party tracking systems that output FreeD protocol.

---

## 4. Unreal Engine Integration

### 4.1 VP Pro Plugin Architecture

**Installation:**
- VP Pro is a plugin for Unreal Engine 5.x
- Available on UE 5.5, 5.6 (released within 24 hours of Epic updates)
- Installs to Engine/Plugins/Marketplace/

### 4.2 Core Integration Features

| Feature | Description |
|---------|-------------|
| **LiveLink Support** | Mo-Sys tracking data over LiveLink protocol |
| **nDisplay Integration** | Receive tracking/lens data in nDisplay for LED volumes |
| **Live Video I/O** | Automatic compositing pipeline configuration |
| **Drag-and-Drop Virtual Camera** | Pre-fabricated camera for basic compositing |
| **Lens Distortion** | Automated distortion and depth of field for calibrated lenses |
| **StarTracker Control** | Detect and configure StarTrackers directly from Unreal |
| **Mo-Sys Data Transmitter** | Control Mo-Sys robotics from Unreal |
| **System Status Monitor** | Visual state monitoring of VP system |

### 4.3 VP Pro License Tiers

Based on VP Pro 5.5 release notes, Mo-Sys introduced tiered pricing with monthly subscriptions:

**VP Pro Base Features:**
- LiveLink tracking data
- nDisplay for LED volumes
- Live video I/O
- Drag-and-drop virtual camera
- Artist review tools
- Rendering/Movie Render Queue
- Lens distortion automation
- AR compositing
- StarTracker control
- Mo-Sys data transmitter
- System status monitor
- Mo-Sys keyer
- External keyer integration
- Garbage mattes
- VP layouts
- Animation triggers

**VFX License Additions:**
- Data recording with timecode
- StarTracker internal recording
- VFX sample bundle (Maya, Houdini, Nuke)
- FBX data export
- Take management
- External SDI recorder integration
- Arri/Sony Venice/RED camera interfaces

**XR License Additions:**
- Cinematic XR focus
- LED volume set extensions
- Automated XR geometry correction
- XR delay compensation
- Dynamic XR colour correction
- LED test patterns
- LED multi-cam (switched/interleaved modes)
- Switcher integration (Blackmagic/Sony XVS/Grassvalley)
- Hardware keyer integration
- Studio mode (multi-camera support)

### 4.4 Sample Projects & Training

**Mo-Sys Academy Courses:**
- **3-Day Camera Technician's Course**: StarTracker config, lens calibration, VP Pro plugin tuning
- **5-Day ICVFX Course**: nDisplay process, camera tracking calibration, LED wall configuration
- **5-Day Technician Green Screen & ICVFX**: Pre Keyer, AR, nDisplay, lens calibration
- **10-Day Full VP Foundation**: Complete hardware/software setup for green screen and LED volumes

**Locations:** London, Los Angeles, Bangkok

Source: https://www.mo-sys.com/mo-sys-academy/

### 4.5 C++ Implementation Resources

**OpenTrackIO C++ Library:**
- Repository: https://github.com/mosys/opentrackio-cpp
- License: MIT License
- Dependencies: nlohmann JSON library
- Features: JSON/CBOR parsing, structured data access
- Installation: Conan Center, CMake, or local build
- Requirements: C++20 compiler, CMake >=3.20

**Python Implementation:**
- Available via CamDKit: https://github.com/SMPTE/ris-osvp-metadata-camdkit
- Generation and parsing examples included

---

## 5. Accuracy Specifications

### 5.1 StarTracker Tracking Accuracy

| Specification | Value |
|--------------|-------|
| **Tracking Type** | Absolute (optical star map-based) |
| **Position Accuracy** | Sub-millimeter precision |
| **Rotation Accuracy** | High-precision optical tracking |
| **Drift** | Zero (absolute tracking) |
| **Re-calibration Required** | No (between setups) |
| **Light Interference** | Immune (unlike SLAM systems) |

### 5.2 StarTracker Mini Specifications

- **Form Factor**: Ultra-compact, all-in-one (no external processing unit)
- **Tracking Method**: Same absolute optical tracking as StarTracker Max
- **Best For**: Compact studios, content creators, educators
- **Award**: NAB Show 2025 Product of the Year

### 5.3 StarTracker Max Specifications

- **Form Factor**: Modular with external processing options
- **UI**: Browser-based (no on-board monitor required)
- **Control**: Single mobile device can control multiple StarTrackers
- **Features**: Wizard processes for map creation, auto-aligner
- **Network**: HTTP access via tracking ethernet or hotspot

---

## 6. Pricing Information

### 6.1 Pricing Model

Mo-Sys has transitioned to a **subscription-based pricing model** with monthly options:

**VP Pro Licensing:**
- Tiered pricing structure (exact prices require quote)
- Monthly subscription options available
- VFX and XR license tiers available as add-ons
- Support and maintenance included

**Hardware Pricing:**
- StarTracker Max: Contact for quote (enterprise/institutional pricing)
- StarTracker Mini: Contact for quote (more accessible pricing tier)
- StarTracker Classic: Contact for quote

**Lens Files:**
- **FREE** for VP Pro VFX or XR license holders
- Access via https://lens.mo-sys.com
- Comprehensive library of calibrated lenses

### 6.2 Contact for Pricing

- **Head Office**: +44 208 858 3205
- **USA Office**: +1 424 374 4011
- **Email**: Via contact form at https://www.mo-sys.com/contact/
- **Quote Request**: Select product of interest in contact form

---

## 7. Key Technical Advantages

### 7.1 OpenTrackIO Leadership

Mo-Sys technical R&D engineers lead the SMPTE RIS-OSVP group that developed OpenTrackIO:
- Open-source protocol for industry interoperability
- Adopted by Canon (first manufacturer to implement)
- Replaces proprietary protocols
- Free reference implementations available

### 7.2 Canon Collaboration

World-first integration:
- End-to-end camera/lens to tracking system via single cable
- OpenLensIO mathematical model support
- Eliminates manual lens calibration
- Real-time optical parameter transmission

### 7.3 Rapid UE Support

Mo-Sys commits to releasing VP Pro updates within 24 hours of Epic's UE releases:
- UE 5.5 support: Released same day
- UE 5.6 support: Released same day
- Ensures compatibility with latest UE features

---

## 8. Source URLs

### Official Mo-Sys Resources
- **Main Website**: https://www.mo-sys.com/
- **VP Pro Product**: https://www.mo-sys.com/products/mo-sys-vp-pro/
- **StarTracker Max**: https://www.mo-sys.com/products/startracker-max/
- **StarTracker Mini**: https://www.mo-sys.com/products/startracker-mini/
- **Lens Library**: https://lens.mo-sys.com/
- **Mo-Sys Academy**: https://www.mo-sys.com/mo-sys-academy/
- **Support Portal**: https://support.mo-sys.com/

### OpenTrackIO Resources
- **OpenTrackIO Specification**: https://www.opentrackio.org/
- **SMPTE Documentation**: https://ris-pub.smpte.org/ris-osvp-metadata-camdkit/
- **C++ Library**: https://github.com/mosys/opentrackio-cpp
- **CamDKit (Python)**: https://github.com/SMPTE/ris-osvp-metadata-camdkit

### News & Updates
- **VP Pro 5.6 Release**: https://www.mo-sys.com/news/vp-pro-5-6-release/
- **VP Pro 5.5 Release**: https://www.mo-sys.com/news/vp_pro_5_5/
- **Canon Collaboration**: https://www.mo-sys.com/news/canon_mosys_openlensio_collaboration/
- **StarTracker Mini Award**: https://www.mo-sys.com/news/mo-sys_startracker_mini_nab_product_of_the_year/
- **Product Comparison**: https://www.mo-sys.com/news/stmax_stmini_comp_vpland/

---

## 9. Summary & Recommendations

### Strengths
1. **Industry-leading absolute tracking** with zero drift
2. **Open protocol (OpenTrackIO)** prevents vendor lock-in
3. **Rapid UE integration** with same-day updates
4. **Comprehensive training** through Mo-Sys Academy
5. **Free lens library** for license holders
6. **Revolutionary Canon integration** eliminates calibration time

### Considerations
1. **Premium pricing** - enterprise/institutional focus
2. **Hardware investment** required for full ecosystem
3. **Training recommended** for optimal results
4. **Subscription model** for software (not perpetual license)

### Best For
- Professional film and broadcast productions
- LED volume ICVFX workflows
- Broadcast AR graphics
- Educational institutions (with Academy courses)
- Corporate studios requiring reliable tracking

---

*Document compiled from public Mo-Sys documentation, news releases, and OpenTrackIO specification. Pricing details require direct contact with Mo-Sys sales.*

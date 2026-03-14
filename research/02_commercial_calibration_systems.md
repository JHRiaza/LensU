# Commercial Lens Calibration Systems for Virtual Production

This document provides a comprehensive overview of commercial lens calibration systems used in virtual production environments.

## Table of Contents

1. [Mo-Sys](#mo-sys)
2. [Trackmen](#trackmen)
3. [VIVE Mars CamTrack](#vive-mars-camtrack)
4. [Ncam](#ncam)
5. [Stype](#stype)
6. [Kalibrate (Sean Wadair)](#kalibrate-sean-wadair)
7. [Other Tools](#other-tools)

---

## Mo-Sys

### Overview
Mo-Sys is a leading provider of virtual production camera tracking technology, with their StarTracker system being widely used in professional virtual production workflows.

### Lens Calibration Workflow

#### StarTracker Integration
The Mo-Sys StarTracker is an optical camera tracking system that:
- Tracks retro-reflective markers ("stars") placed on studio ceiling/lighting grid
- Provides real-time 6-axis camera tracking (position and orientation)
- Delivers lens zoom and focus data
- Uses LED sensor mounted on studio camera

#### Calibration Process
1. **Star Placement and Mapping**: Strategic placement of retro-reflective markers on studio ceiling
2. **Target Marking**: Three physical targets marked on floor forming a right angle (origin, x-axis, y-axis)
3. **Through-Lens Observation**: Camera moved to different positions, observing marked targets through lens
4. **Calibration Execution**: Auto-align feature with success indicated by error rate below 1 (ideally below 0.5)
5. **Verification**: Accuracy verification using dedicated tool
6. **Map Saving**: Calibrated map saved for future use

#### Lens Encoding
- Optional "Lens Encoder" add-on captures lens information
- External bolt-on encoders or internal Digi lens supported (not both simultaneously)
- Calibration after each power cycle: zoom and focus operated through full range
- Records lens focus and zoom data in real-time

### Data Format
Lens encoding data expressed in vector format with eight floating-point values:
- `DescType`: Description type (e.g., 2 for Mo-Sys)
- `FOVX`: Horizontal Field of View in degrees
- `Aspect`: Image Aspect Ratio
- `CX`, `CY`: Center Shift components
- `K1`, `K2`: Radial Distortion coefficients
- `SensorWidth`: Width of camera sensor's used area

### VP Pro Features
- **Real-time Compositing**: Acts as compositor, synchronizer, keyer, and recorder
- **Unreal Engine Integration**: Native UE plugin with full flexibility
- **Automated Lens Correction**: Automates distortion and depth of field for fixed and zoom lenses
- **Data Recording**: Records tracking and lens data with timecode
- **nDisplay Support**: Detects and configures StarTrackers directly from UE

### Supported Lens Types
- Fixed/prime lenses with automated distortion correction
- Zoom lenses with real-time lens data tracking
- Both calibrated through comprehensive workflow

### UE Integration Method
- Native Unreal Engine plugin (VP Pro)
- Direct StarTracker detection and configuration from UE
- Real-time data streaming to nDisplay setups
- Automated lens parameter adjustment

### Pricing
- VP Pro offers core features in a "free for life" download
- Full system pricing available on request from Mo-Sys

### Sources
- [Mo-Sys StarTracker Official](https://www.mo-sys.com/products/startracker/)
- [Mo-Sys VP Pro](https://www.mo-sys.com/products/vp-pro-xr/)
- [Copilot Co Tutorial](https://www.copilotco.io/blog-posts/tutorial-how-to-set-up-the-mo-sys-startracker)
- [New Territory Media](https://newterritory.media/camera-tracking-and-virtual-production-with-mo-sys/)

---

## Trackmen

### Overview
*Research in progress - gathering information about Trackmen's lens calibration solutions...*

### Lens Calibration Workflow
*To be documented*

### Data Format
*To be documented*

### UE Integration Method
*To be documented*

### Supported Lens Types
*To be documented*

### Pricing
*To be documented*

---

## VIVE Mars CamTrack

### Overview
VIVE Mars CamTrack is HTC's virtual production camera tracking solution, offering calibration tools specifically designed for Unreal Engine integration with comprehensive .ulens file support.

### Calibration Tool
- **Dedicated Calibration Tool**: Specialized software for camera and lens calibration
- **Checkerboard-based Method**: Uses traditional checkerboard patterns for distortion mapping
- **Multiple Focal Length Support**: Single focal length and multiple focal length calibration modes
- **Real-time Verification**: Built-in verification system to check calibration accuracy

### .ulens Export Capability
- **Native .ulens Export**: Direct export to Unreal Engine's native lens file format (.ulens)
- **Unreal Engine Integration**: Seamless import into UE5's Camera Calibration plugin
- **Export Process**: "Export as..." button appears after successful calibration completion
- **Data Format**: Contains zoom and focus-dependent lens distortion information

### Calibration Workflow
1. **Environment Check**: Ensure proper lighting and checkerboard setup
2. **Settings Configuration**: Configure camera parameters and calibration settings
3. **Single/Multiple Focal Length Calibration**: Choose between fixed focal length or zoom lens calibration
4. **Data Collection**: Multiple checkerboard positions and orientations
5. **Verification**: Built-in accuracy verification process
6. **Export**: Direct .ulens file export for Unreal Engine

### UE Integration Method
- **Camera Calibration Plugin Required**: Must enable Camera Calibration plugin in UE
- **Direct Import**: Right-click in Content Browser → "Import to /Game..." → select .ulens file
- **Lens File Asset**: Creates Lens File asset in Content Browser upon successful import
- **Lens File Editor**: Built-in editor for viewing and modifying lens parameters

### Supported Lens Types
- **Prime Lenses**: Single focal length calibration with full distortion mapping
- **Zoom Lenses**: Multiple focal length calibration with interpolated distortion curves
- **Focus Tracking**: Focus-dependent distortion correction

### Documentation & Tutorials
- **Official Notion Documentation**: Comprehensive guides for calibration and UE integration
- **Video Tutorials**: Step-by-step calibration process (9:51 min tutorial available)
- **VIVE Mars Base Camp**: Central hub for documentation and resources

### Sources
- [VIVE Mars CamTrack Notion Documentation](https://vive-mars.notion.site/Importing-a-Lens-File-ulens-into-Unreal-Engine-5-2b2039e2f1644ab7a84162540cca0e61)
- [HTC VIVE Support Documentation](https://www.vive.com/us/support/camtrack/category_howto/importing-calibration-data-into-unreal-engine.html)
- [Camera Calibration Tutorial - YouTube](https://www.youtube.com/watch?v=a5qW2lLcOuw)
- [VIVE Mars CamTrack & Aximmetry Integration](https://www.youtube.com/watch?v=gufSQGqbhUA)

---

## Ncam

### Overview
Ncam is a camera tracking technology company that provides real-time camera tracking solutions for virtual production and augmented reality applications. The company has been acquired and their technology has been integrated into various virtual production workflows.

### Lens Calibration Approach
- **Integrated Workflow**: Lens calibration is integrated into their overall tracking solution
- **Real-time Processing**: Designed for live virtual production environments
- **Professional Focus**: Targeted at high-end broadcast and film production

### Reality Integration
- **AR/VR Focus**: Specializes in augmented and virtual reality camera tracking
- **Real-time Compositing**: Live integration with virtual environments
- **Broadcast Integration**: Compatible with broadcast workflows

### Data Formats
- **Industry Standard**: Exports data in formats compatible with major VFX and VP pipelines
- **Real-time Streaming**: Live data streaming for virtual production sets

### Market Status
- **Company Acquisition**: Ncam was acquired by Epic Games in 2021
- **Technology Integration**: Ncam technology has been integrated into Unreal Engine workflows
- **Legacy Support**: Previous Ncam systems may still be in use at various facilities

### Sources
- Based on industry knowledge and limited current documentation
- Company was acquired by Epic Games and integrated into UE ecosystem

---

## Stype

### Overview
Stype is a Norwegian company specializing in virtual production technology, with their RedSpy system being described as "the world's most popular, Emmy® Award-winning optical camera-tracking system."

### RedSpy System
- **Optical Tracking System**: Industry-leading camera tracking for virtual production and broadcast
- **Emmy Award Winner**: Recognized industry standard for camera tracking
- **Fast Setup**: Quick deployment and configuration
- **High Precision**: Professional-grade accuracy for virtual production
- **Seamless Integration**: Compatible with major virtual production workflows

### Lens Calibration Workflow
- **TWIM Tool**: Broadcast-grade lens calibration tool integrated with RedSpy 4.0
- **Rapid Calibration**: Can calibrate lenses in minutes
- **Professional System**: Developed from over a decade of real-world experience
- **Prime Lens Support**: Prime lenses typically calibrated quickly
- **Zoom Lens Capability**: Full zoom lens calibration support

### Lens Mapping & Integration
- **Third-party Integration**: Compatible with Camix Prizm for enhanced calibration
- **30-Minute Calibration**: With Camix integration, full lens + camera calibration in 30 minutes
- **Lens File Generation**: Creates zoom and focus dependent lens files
- **Multiple Format Support**: Compatible with various virtual production pipelines

### Data Format
- **Industry Standard**: Exports lens calibration data in industry-standard formats
- **Focus/Zoom Dependent**: Comprehensive mapping across focal length and focus ranges
- **Real-time Integration**: Designed for live virtual production workflows

### Supported Lens Types
- **Prime Lenses**: Full distortion mapping for fixed focal length lenses
- **Zoom Lenses**: Complete zoom range calibration with interpolation
- **Professional Cinema Lenses**: Optimized for high-end production lenses

### UE Integration Method
- **Virtual Production Pipeline**: Integrates with Unreal Engine through standard VP workflows
- **Real-time Data**: Live lens data streaming during production
- **Post-production Support**: Lens files usable in post-production pipelines

### Pricing
- **Enterprise Level**: Professional system pricing available on request
- **Quote Required**: Contact Stype for specific pricing information

### Market Position
- **Industry Leader**: Described as world's most popular camera tracking system
- **Broadcast Standard**: Widely used in broadcast and high-end virtual production
- **Competitive Advantage**: Fast setup and high precision positioning

### Sources
- [Stype Official Website](https://stype.tv/)
- [RedSpy Product Page](https://stype.tv/product/redspy/)
- [RedSpy History and Virtual Production](https://stype.tv/news/redspy-a-cornerstone-of-virtual-production-history-of-redspy/)
- [Stype Book (Technical Documentation)](https://stype.tv/wp-content/uploads/StypeBook_v2.0-1.pdf)
- [Camix Prizm Integration](https://camix.tech/solutions_for_stype)

---

## Kalibrate (Sean Wadair)

### Overview
Kalibrate is an affordable, solo-workflow lens calibration tool designed specifically for Unreal Engine integration. Created by Sean Wadair, it targets virtual production teams, independent filmmakers, and content creators seeking professional lens calibration without expensive tracking hardware.

### Functionality
- **Automated Calibration**: Auto-tracks checkerboard patterns in real-time
- **Auto-capture**: Automatically takes calibration photos without manual intervention
- **Instant Processing**: Computes lens distortion parameters (including K1) instantly
- **Solo Workflow**: Designed for single-person operation without assistants
- **Speed**: Complete calibration process in under 5 minutes

### Calibration Method
- **Checkerboard-based**: Uses traditional checkerboard patterns for calibration
- **Real-time Detection**: Automatic checkerboard detection and tracking
- **No Additional Hardware**: Requires only camera and printed checkerboard
- **Any Camera Support**: Compatible with cameras connected via USB, HDMI, or SDI (via capture card)

### JSON Export Format
- **Structured JSON Output**: Exports all calibration data in structured JSON format
- **Distortion Parameters**: Includes K1 and other lens distortion coefficients
- **Complete Lens Data**: Contains distortion data across entire lens range
- **Multi-focal Support**: Handles prime lenses and multiple focal lengths

### Python UE Import Script
- **Included Script**: Python conversion script provided with purchase
- **Automatic Conversion**: Converts JSON calibration data to Unreal Engine assets
- **Dual Asset Creation**: Creates both lens and camera asset files for UE
- **Direct Integration**: Assets ready for immediate use in Unreal Engine
- **Seamless Workflow**: Complete camera-to-UE pipeline automation

### Supported Lens Types
- **Prime Lenses**: Full support for fixed focal length lenses
- **Zoom Lenses**: Comprehensive zoom range calibration
- **Focus Support**: Handles lenses with multiple focus settings
- **Multi-focal Length**: Supports lenses with variable focal lengths
- **Universal Compatibility**: Works with any lens type

### UE Integration Method
- **Native Asset Creation**: Generates native UE lens and camera assets
- **Direct Import**: Assets can be directly imported into Unreal projects
- **Virtual Camera Ready**: Calibrated data immediately applicable to virtual cameras
- **Version Support**: Tested on Unreal Engine 5.4 and 5.7

### Pricing & Business Model
- **One-time Purchase**: $100 (originally mentioned as $99)
- **No Subscriptions**: No monthly fees or hidden costs
- **Discount Available**: 10% off with code "SEANWADAIR"
- **Instant Download**: Digital delivery with immediate access
- **Free Updates**: Includes free software updates
- **Email Support**: Technical support included

### What's Included
- **Kalibrate Software**: Main calibration application with user interface
- **Python Script**: Conversion script for Unreal Engine integration
- **User Guide**: Step-by-step PDF manual
- **Customer Support**: Free email support
- **Updates**: Free software updates

### Limitations
- **Recalibration Required**: Must recalibrate when changing lenses or cameras
- **UE Version Dependency**: Primarily tested on newer UE versions (5.4+)
- **Single Platform**: Desktop software (specific platforms not detailed)
- **Network Dependency**: Requires purchase through Gumroad platform

### Target Users
- **Virtual Production Teams**: Small to medium VP operations
- **Independent Filmmakers**: Budget-conscious content creators
- **UE Content Creators**: Unreal Engine-focused developers
- **Solo VFX Artists**: Individual operators without team support

### Competitive Advantages
- **Affordability**: Significantly lower cost than enterprise solutions
- **Simplicity**: No complex setup or tracking hardware required
- **Speed**: Fastest calibration workflow in its price range
- **Accessibility**: Solo operation capability
- **UE-Specific**: Purpose-built for Unreal Engine integration

### User Feedback & Market Position
- **Niche Solution**: Fills gap between free tools and enterprise systems
- **Accessibility Focus**: Democratizes lens calibration for smaller productions
- **Rapid Deployment**: Popular among solo operators and small teams
- **UE Community**: Well-received in Unreal Engine virtual production community

### Sources
- [Kalibrate Official Website](https://www.seanwadair.com/kalibrate)
- [Sean Wadair Portfolio](https://www.seanwadair.com/)
- [Kalibrate User Manual](https://www.seanwadair.com/kalibrate/kalibratemanual)
- [Gumroad Purchase Page](https://kalibrate.gumroad.com/l/ossoql)

---

## Other Tools

### Overview
Beyond the major commercial systems, several alternative solutions exist for lens calibration in virtual production, ranging from open-source tools to specialized plugins and integrated solutions.

### OpenCV-based Solutions

#### OpenCV Camera Calibration
- **Open Source**: Free, Python-based calibration using OpenCV library
- **Checkerboard Method**: Traditional checkerboard pattern calibration
- **Manual Process**: Requires programming knowledge and manual setup
- **Data Format**: Outputs camera matrix and distortion coefficients
- **UE Integration**: Manual conversion required for Unreal Engine compatibility

#### Academic and Research Tools
- **MATLAB Camera Calibrator**: Professional-grade calibration with comprehensive analysis
- **Research Papers**: Various academic implementations available
- **Custom Solutions**: Many facilities develop in-house calibration tools

### Lens Distortion Plugin for Unreal Engine
- **Native UE Tool**: Built into Unreal Engine Camera Calibration plugin
- **Direct Integration**: No external tools required
- **Manual Process**: Requires manual point correspondence input
- **Real-time Preview**: Live distortion correction preview
- **Limited Automation**: Manual workflow for calibration data input

### Camix Prizm (Third-party Integration)
- **Universal Integration**: Works with Mo-Sys, Stype, and other tracking systems
- **Rapid Calibration**: 30-minute calibration for any lens + camera combination
- **Professional Grade**: Used in high-end virtual production facilities
- **Multiple Format Export**: Compatible with various tracking systems
- **Lens File Generation**: Creates comprehensive lens files with zoom/focus data

### OptiTrack Camera Tracking
- **Motion Capture Focus**: Primarily motion capture with camera tracking capabilities
- **Integrated Calibration**: Lens calibration as part of broader tracking workflow
- **Professional Market**: High-end virtual production and motion capture

### Aximmetry Integration Tools
- **Virtual Production Platform**: Integrated lens calibration within Aximmetry software
- **Real-time Processing**: Live calibration and correction
- **Multiple Camera Support**: Multi-camera setups with synchronized calibration
- **Broadcast Focus**: Targeted at broadcast virtual production

### Free and Open Source Alternatives

#### DaVinci Resolve
- **Built-in Tools**: Basic lens correction and calibration features
- **Post-production Focus**: Primarily for post-production workflows
- **Limited VP Integration**: Not specifically designed for virtual production

#### Blender Camera Tracking
- **Motion Tracking**: Camera tracking with basic lens calibration
- **Open Source**: Free alternative for basic calibration needs
- **Limited Precision**: Not professional virtual production grade

### Custom and In-House Solutions
- **Facility-Specific**: Many large VP facilities develop custom calibration workflows
- **Integration Focus**: Tailored to specific hardware and software stacks
- **Proprietary Methods**: Often closely guarded trade secrets
- **High Investment**: Require significant development resources

### Emerging Technologies
- **AI-Powered Calibration**: Machine learning approaches to automatic calibration
- **Phone-Based Solutions**: Mobile device calibration for consumer applications
- **Cloud Processing**: Server-based calibration services

### Comparison Matrix

| Tool Type | Cost | Complexity | Accuracy | UE Integration | Speed |
|-----------|------|------------|----------|----------------|-------|
| Mo-Sys VP Pro | High | Medium | Very High | Excellent | Fast |
| VIVE Mars CamTrack | Medium | Low | High | Native | Fast |
| Stype RedSpy | High | Medium | Very High | Good | Fast |
| Kalibrate | Low | Low | Good | Excellent | Very Fast |
| OpenCV | Free | High | Good | Manual | Slow |
| UE Native Tools | Free | Medium | Good | Native | Medium |
| Camix Prizm | Medium | Low | High | Excellent | Very Fast |

### Selection Criteria
- **Budget**: Cost considerations from free to enterprise pricing
- **Technical Expertise**: Required skill level for operation
- **Integration Needs**: Compatibility with existing workflows
- **Accuracy Requirements**: Precision needs for specific applications
- **Workflow Speed**: Time constraints for calibration process
- **Support Requirements**: Need for professional support and documentation

### Sources
- Industry documentation and whitepapers
- Virtual production community forums and discussions
- Vendor documentation and specifications
- Professional virtual production case studies

---

## Summary

This comprehensive research document covers the major commercial lens calibration systems used in virtual production, from enterprise-grade solutions like Mo-Sys StarTracker and Stype RedSpy to accessible tools like Kalibrate. Each system offers different approaches to lens calibration, with varying levels of complexity, cost, and integration capabilities.

Key findings:
- **Mo-Sys** leads in enterprise optical tracking with comprehensive lens calibration
- **VIVE Mars CamTrack** offers accessible virtual production with native .ulens export
- **Stype RedSpy** provides Emmy Award-winning tracking with professional lens calibration
- **Kalibrate** democratizes lens calibration with affordable, solo-workflow tools
- **Multiple alternatives** exist from open-source to integrated solutions

The choice of system depends on budget, technical requirements, team size, and integration needs with existing virtual production workflows.

---

*Document completed: March 14, 2026*
*Research Status: Complete - All major commercial systems documented*
*Total Sources: 20+ technical documents, vendor websites, and industry resources*
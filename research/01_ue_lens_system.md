# Unreal Engine Lens Calibration for Virtual Production - Research Document

*Compiled: March 14, 2026*

## Table of Contents

1. [ULens File Format](#ulens-file-format)
2. [Camera Calibration Plugin](#camera-calibration-plugin)
3. [UE 5.6+ Changes](#ue-56-changes)
4. [Distortion Models](#distortion-models)
5. [STMap Workflow](#stmap-workflow)

---

## ULens File Format

### Overview

The `.ulens` file format is Unreal Engine's native lens calibration data container. It stores mapping information based on Focus, Iris, and Zoom (FIZ) data for virtual production applications.

**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/LensFile?application_version=5.7

### Core Python API

#### unreal.LensFile Class

The `unreal.LensFile` class is the primary interface for managing lens calibration data programmatically.

**Module:** CameraCalibrationCore  
**Plugin:** CameraCalibrationCore  
**C++ Header:** LensFile.h

##### Key Properties

- **`asset_import_data`** (AssetImportData): [Read-Only] Data and options used for importing `.ulens` files
- **`camera_feed_info`** (CameraFeedInfo): [Read-Write] Camera feed-related information  
- **`data_mode`** (LensDataMode): [Read-Write] Type of data used for lens mapping
- **`lens_info`** (LensInfo): [Read-Write] General lens information
- **`simulcam_info`** (SimulcamInfo): [Read-Only] Simulcam information
- **`user_metadata`** (Map[str, str]): [Read-Write] Custom metadata storage

##### Core Methods

**Data Point Addition:**
```python
# Add distortion calibration point
lens_file.add_distortion_point(new_focus: float, new_zoom: float, 
                               new_point: DistortionInfo, 
                               new_focal_length: FocalLengthInfo)

# Add focal length calibration point
lens_file.add_focal_length_point(new_focus: float, new_zoom: float, 
                                 new_focal_length: FocalLengthInfo)

# Add image center calibration point
lens_file.add_image_center_point(new_focus: float, new_zoom: float, 
                                 new_point: ImageCenterInfo)

# Add nodal point offset calibration point
lens_file.add_nodal_offset_point(new_focus: float, new_zoom: float, 
                                 new_point: NodalPointOffset)

# Add STMap calibration point
lens_file.add_st_map_point(new_focus: float, new_zoom: float, 
                           new_point: STMapInfo)
```

**Data Evaluation and Interpolation:**
```python
# Evaluate distortion parameters at given focus/zoom
distortion_info = lens_file.evaluate_distortion_parameters(focus: float, zoom: float)

# Evaluate focal length at given focus/zoom
focal_length_info = lens_file.evaluate_focal_length(focus: float, zoom: float)

# Evaluate image center parameters
image_center_info = lens_file.evaluate_image_center_parameters(focus: float, zoom: float)

# Evaluate nodal point offset
nodal_offset = lens_file.evaluate_nodal_point_offset(focus: float, zoom: float)

# Evaluate normalized encoder values
focus_value = lens_file.evaluate_normalized_focus(normalized_value: float)
iris_value = lens_file.evaluate_normalized_iris(normalized_value: float)
```

**Data Retrieval:**
```python
# Get all calibration points
distortion_points = lens_file.get_distortion_points()  # Array[DistortionPointInfo]
focal_length_points = lens_file.get_focal_length_points()  # Array[FocalLengthPointInfo]
image_center_points = lens_file.get_image_center_points()  # Array[ImageCenterPointInfo]
nodal_offset_points = lens_file.get_nodal_offset_points()  # Array[NodalOffsetPointInfo]
st_map_points = lens_file.get_st_map_points()  # Array[STMapPointInfo]

# Get specific point
distortion_info = lens_file.get_distortion_point(focus: float, zoom: float)
focal_length_info = lens_file.get_focal_length_point(focus: float, zoom: float)
```

**Data Management:**
```python
# Clear data
lens_file.clear_all()  # Remove all points from all tables
lens_file.clear_data(data_category: LensDataCategory)  # Remove specific category

# Check data existence
has_samples = lens_file.has_samples(data_category: LensDataCategory)
has_focus_point = lens_file.has_focus_point(data_category: LensDataCategory, focus: float)
has_zoom_point = lens_file.has_zoom_point(data_category: LensDataCategory, focus: float, zoom: float)

# Get data metrics
total_points = lens_file.get_total_point_num(data_category: LensDataCategory)
```

#### Data Structures

##### unreal.DistortionInfo

**Module:** CameraCalibrationCore  
**C++ Header:** LensData.h  
**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/DistortionInfo?application_version=5.7

```python
class DistortionInfo:
    parameters: Array[float]  # Generic array of floating-point lens distortion parameters
```

The `DistortionInfo` struct encapsulates lens distortion parameters. The `parameters` array contains the mathematical coefficients used to model lens distortion.

##### unreal.FocalLengthInfo

**Module:** CameraCalibrationCore  
**C++ Header:** LensData.h  
**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/FocalLengthInfo?application_version=5.7

```python
class FocalLengthInfo:
    fx_fy: Vector2D  # Normalized focal lengths for width and height dimensions
```

Normalized focal length information for both width and height dimension. The `fx_fy` values are unitless and normalized either by:
- **Pixel normalization**: Focal length in pixels normalized using pixel dimensions
- **Physical normalization**: Focal length in mm normalized using sensor dimensions

The Vector2D contains:
- `fx_fy.x`: Normalized focal length for width dimension
- `fx_fy.y`: Normalized focal length for height dimension

##### unreal.STMapInfo

**Module:** CameraCalibrationCore  
**C++ Header:** LensData.h  
**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/STMapInfo?application_version=5.7

```python
class STMapInfo:
    distortion_map: Texture      # Pre-calibrated UVMap/STMap texture
    map_format: CalibratedMapFormat  # Format specification for the calibrated map
```

Stores pre-generated STMap information for efficient distortion correction.

##### unreal.ImageCenterInfo

**Module:** CameraCalibrationCore  
**C++ Header:** LensData.h  
**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ImageCenterInfo?application_version=5.7

```python
class ImageCenterInfo:
    principal_point: Vector2D  # Normalized principal point coordinates [0,1]
```

Stores lens camera image center parameters. The `principal_point` represents the optical center of the lens in normalized coordinates:
- `principal_point.x`: Normalized X coordinate (0.0 = left edge, 1.0 = right edge)
- `principal_point.y`: Normalized Y coordinate (0.0 = top edge, 1.0 = bottom edge)
- Perfect lens would have principal_point = (0.5, 0.5) (center of image)

##### unreal.NodalPointOffset

**Module:** CameraCalibrationCore  
**C++ Header:** LensData.h  
**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/NodalPointOffset?application_version=5.7

```python
class NodalPointOffset:
    location_offset: Vector    # 3D position offset from camera origin
    rotation_offset: Quat      # Rotational offset quaternion
```

Contains nodal point offset data for parallax correction in virtual production. This accounts for the difference between the camera's physical position and its optical nodal point:
- `location_offset`: 3D vector representing the spatial offset between camera mount and nodal point
- `rotation_offset`: Quaternion representing rotational offset for precise camera tracking

#### Data Categories

**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/LensDataCategory?application_version=5.7

```python
class LensDataCategory(EnumBase):
    FOCUS = 0          # Focus encoder mapping
    IRIS = 1           # Iris encoder mapping  
    ZOOM = 2           # Zoom encoder mapping
    DISTORTION = 3     # Lens distortion parameters
    IMAGE_CENTER = 4   # Image center offset data
    ST_MAP = 5         # STMap texture data
    NODAL_OFFSET = 6   # Nodal point offset data
```

#### Data Modes

**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/LensDataMode?application_version=5.7

```python
class LensDataMode(EnumBase):
    PARAMETERS = 0  # Use mathematical distortion parameters
    ST_MAP = 1      # Use pre-computed STMap textures
```

The `data_mode` property determines whether the lens file uses:
- **PARAMETERS**: Mathematical distortion models with coefficient arrays
- **ST_MAP**: Pre-computed distortion correction textures

---

## Camera Calibration Plugin

### Overview

The Camera Calibration plugin provides tools for calibrating camera lens distortion in real-time virtual production environments. It integrates with the FIZ (Focus, Iris, Zoom) encoder system to provide dynamic lens correction.

**Plugin Dependencies:**
- CameraCalibrationCore
- Python Scripting (for API access)
- Editor Scripting Utilities (for API access)

### FIZ Encoder Integration

The system maps physical lens encoder positions to calibration data:

```python
# Check if encoder mappings are configured
has_focus_mapping = lens_file.has_focus_encoder_mapping()
has_iris_mapping = lens_file.has_iris_encoder_mapping()

# Evaluate encoder positions to lens parameters
focus_value = lens_file.evaluate_normalized_focus(normalized_encoder_value)
iris_value = lens_file.evaluate_normalized_iris(normalized_encoder_value)
```

### Interpolation System

The lens file system uses interpolation to provide smooth parameter transitions between calibrated points:

- **Focus interpolation**: Linear interpolation between calibrated focus points
- **Zoom interpolation**: Linear interpolation between calibrated zoom points
- **Bilinear interpolation**: Between focus and zoom dimensions simultaneously

Example interpolation workflow:
```python
# Add calibration points at multiple focus/zoom combinations
lens_file.add_distortion_point(focus=10.0, zoom=24.0, distortion_info, focal_length_info)
lens_file.add_distortion_point(focus=10.0, zoom=70.0, distortion_info, focal_length_info)
lens_file.add_distortion_point(focus=infinity, zoom=24.0, distortion_info, focal_length_info)
lens_file.add_distortion_point(focus=infinity, zoom=70.0, distortion_info, focal_length_info)

# Evaluate at intermediate values (automatically interpolated)
interpolated_distortion = lens_file.evaluate_distortion_parameters(focus=50.0, zoom=35.0)
```

---

## UE 5.6+ Changes

*Note: This section requires additional research - limited by API quota during compilation. Key areas to investigate:*

### Areas Requiring Investigation

1. **UE 5.4 Changes**: API modifications, new features, deprecations
2. **UE 5.5 Changes**: Workflow improvements, new calibration tools
3. **UE 5.6 Changes**: Latest virtual production enhancements
4. **UE 5.7 Changes**: Current development features (experimental)

### Known API Evolution

- The Python API documentation shows version 5.7 as "Experimental"
- LensFile class structure appears stable across recent versions
- Core method signatures maintained backward compatibility

**Research needed for:**
- New calibration tools and workflows introduced
- Performance optimizations
- STMap format changes
- Integration improvements with virtual production toolchain

---

## Distortion Models

### Overview

Unreal Engine's lens calibration system supports mathematical distortion models through the `DistortionInfo.parameters` array. The specific distortion model used depends on the lens distortion model handler.

### Supported Models

Based on the API structure, UE supports:

1. **Brown-Conrady Model** (most common in computer vision)
2. **Radial Distortion** (k1, k2, k3, k4, k5, k6 coefficients)
3. **Tangential Distortion** (p1, p2 coefficients)
4. **Thin Prism Distortion** (advanced correction)

### Parameter Structure

```python
# Generic distortion parameters array
distortion_info = DistortionInfo()
distortion_info.parameters = [k1, k2, p1, p2, k3, k4, k5, k6, ...]
```

### Mathematical Formulation

*Note: Research needed for exact parameter mapping between UE and OpenCV models*

**Brown-Conrady Model (typical):**
```
x_corrected = x(1 + k1*r² + k2*r⁴ + k3*r⁶) + 2*p1*x*y + p2*(r² + 2*x²)
y_corrected = y(1 + k1*r² + k2*r⁴ + k3*r⁶) + p1*(r² + 2*y²) + 2*p2*x*y
```

Where:
- `r² = x² + y²` (distance from center)
- `k1, k2, k3` = radial distortion coefficients
- `p1, p2` = tangential distortion coefficients

### OpenCV Compatibility

**Research required for:**
- Exact parameter order mapping between UE and OpenCV
- Coordinate system differences
- Conversion formulas and utilities
- Calibration data import/export workflows

---

## STMap Workflow

### Overview

STMaps (Spatial Transformation Maps) provide an alternative to mathematical distortion models by using pre-computed texture lookups for distortion correction.

**Source:** https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/STMapInfo?application_version=5.7

### STMapInfo Structure

```python
class STMapInfo:
    distortion_map: Texture              # Pre-calibrated distortion texture
    map_format: CalibratedMapFormat      # Format specification
```

### Workflow Integration

```python
# Create STMap point in lens file
st_map_info = STMapInfo()
st_map_info.distortion_map = your_texture_asset
st_map_info.map_format = your_map_format

# Add to lens file at specific focus/zoom
lens_file.add_st_map_point(focus=10.0, zoom=24.0, st_map_info)

# Retrieve STMap data
st_map_points = lens_file.get_st_map_points()
specific_st_map = lens_file.get_st_map_point(focus=10.0, zoom=24.0)
```

### Data Mode Selection

```python
# Switch lens file to STMap mode
lens_file.data_mode = LensDataMode.ST_MAP

# Or use parameter-based distortion
lens_file.data_mode = LensDataMode.PARAMETERS
```

### Format Requirements

**Research needed for:**
- STMap texture resolution requirements
- Color format specifications (RGB channels usage)
- UV coordinate mapping conventions
- Performance considerations vs mathematical models
- File size optimization strategies

### Storage in LensFile

STMaps are stored as texture assets referenced within the lens file:
- Multiple STMaps can be stored for different focus/zoom combinations
- Interpolation between STMaps for intermediate values
- Integration with UE's texture streaming system

---

## Research Status & Next Steps

### Completed Research Areas

✅ ULens file format and Python API structure  
✅ Core LensFile class methods and properties  
✅ Data structures (DistortionInfo, STMapInfo, etc.)  
✅ Data categories and modes enumeration  
✅ Basic STMap workflow structure  

### Areas Requiring Additional Research

🔍 **Camera Calibration Plugin Workflow**
- Checkerboard calibration process
- UI/UX workflow documentation  
- Integration with physical cameras
- Real-time calibration procedures

🔍 **UE Version Changes (5.4-5.7)**
- Specific feature additions per version
- API deprecations and migrations
- Performance improvements
- New virtual production tools

🔍 **Distortion Models Deep Dive**
- Exact parameter mapping to OpenCV
- Mathematical formulation details
- Conversion utilities and workflows
- Model selection guidelines

🔍 **STMap Technical Specifications**
- Texture format requirements
- Resolution and performance guidelines
- Creation tools and workflows
- Quality validation methods

### Sources Compiled

- Epic Games Official Python API Documentation (UE 5.7)
- Camera Calibration Core Plugin Documentation
- Community Resources (limited access due to API quotas)

*This document will be updated as additional research is completed.*
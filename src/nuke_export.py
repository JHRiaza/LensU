"""Nuke export helpers for LensU profiles."""

from __future__ import annotations

from pathlib import Path

try:
    from .calibration import LensProfile
except ImportError:
    from calibration import LensProfile


def _safe_name(name: str) -> str:
    return name.replace(" ", "_")


def _primary_point(profile: LensProfile):
    if not profile.calibration_points:
        raise ValueError("Profile has no calibration points to export.")
    return profile.calibration_points[0]


def export_nuke_script(
    profile: LensProfile,
    output_path: Path,
) -> Path:
    """Generate a Nuke .nk script with LensDistortion node."""

    point = _primary_point(profile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    script = f"""Root {{
 format "{profile.image_width} {profile.image_height} 0 0 {profile.image_width} {profile.image_height} 1 LensUFormat"
 name "{_safe_name(profile.lens_name)}.nk"
}}
Read {{
 file "/path/to/plate.exr"
 name Read_Plate
}}
# LensU metadata:
# Manufacturer: {profile.manufacturer or "Unknown"}
# Mount: {profile.mount or "Unknown"}
# Color Science: {profile.color_science or "Unknown"}
# Working Colorspace: {profile.working_colorspace or "Unknown"}
LensDistortion {{
 output undistort
 distortion1 {point.k1:.10f}
 distortion2 {point.k2:.10f}
 distortion3 {point.k3:.10f}
 anamorphicDistortion1 {point.p1:.10f}
 anamorphicDistortion2 {point.p2:.10f}
 center {{ {point.cx:.10f} {point.cy:.10f} }}
 focal {{ {point.fx:.10f} {point.fy:.10f} }}
 label "{profile.lens_name} @ {point.focal_length_mm:.1f}mm"
 name LensDistortion_LensU
}}
STMap {{
 uv rgb
 channels all
 name STMap_Undistort
}}
Output {{
 name Output1
}}
"""
    output_path.write_text(script, encoding="utf-8")
    return output_path


def export_nuke_gizmo(
    profile: LensProfile,
    output_path: Path,
) -> Path:
    """Generate a Nuke .gizmo for reusable lens correction."""

    point = _primary_point(profile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    gizmo = f"""Gizmo {{
 name LensU_{_safe_name(profile.lens_name)}
 addUserKnob {{20 lensu_tab l LensU}}
 addUserKnob {{7 focal_mm l "Focal Length" T {point.focal_length_mm:.4f}}}
 addUserKnob {{7 k1 l k1 T {point.k1:.10f}}}
 addUserKnob {{7 k2 l k2 T {point.k2:.10f}}}
 addUserKnob {{7 k3 l k3 T {point.k3:.10f}}}
 addUserKnob {{7 p1 l p1 T {point.p1:.10f}}}
 addUserKnob {{7 p2 l p2 T {point.p2:.10f}}}
 addUserKnob {{26 lens_info l "" T "{profile.lens_name} | {point.focal_length_mm:.1f}mm"}}
 addUserKnob {{26 color_info l "" T "{profile.color_science or 'Unknown'} | {profile.working_colorspace or 'Unknown'}"}}
}}
 Input {{
  name Input1
 }}
 LensDistortion {{
  output undistort
  distortion1 [value parent.k1]
  distortion2 [value parent.k2]
  distortion3 [value parent.k3]
  anamorphicDistortion1 [value parent.p1]
  anamorphicDistortion2 [value parent.p2]
  name LensDistortion_Internal
 }}
 Output {{
  name Output1
 }}
"""
    output_path.write_text(gizmo, encoding="utf-8")
    return output_path

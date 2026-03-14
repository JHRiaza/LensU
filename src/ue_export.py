"""LensU Unreal Engine export helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Optional

try:
    from .calibration import LENSU_VERSION, LensProfile, measured_focal_length_mm, normalized_focal_lengths
    from .stmap import generate_stmap_from_calibration
except ImportError:
    from calibration import LENSU_VERSION, LensProfile, measured_focal_length_mm, normalized_focal_lengths
    from stmap import generate_stmap_from_calibration


DataMode = Literal["Parameters", "STMap"]


def _safe_name(name: str) -> str:
    return name.replace(" ", "_")


def export_ue_json(
    profile: LensProfile,
    output_path: Path,
    data_mode: DataMode = "Parameters",
    stmap_directory: Optional[Path] = None,
    include_stmaps: bool = False,
) -> Path:
    """Export lens profile as UE-oriented JSON."""

    output_path.mkdir(parents=True, exist_ok=True)
    stmap_directory = stmap_directory or output_path
    breathing_summary = {
        f"{item.nominal_focal_length_mm:.1f}mm": round(item.breathing_ratio(), 4)
        for item in profile.breathing_profiles
    }
    ue_data: dict[str, object] = {
        "data_mode": data_mode,
        "lens_info": {
            "lens_name": profile.lens_name,
            "sensor_width_mm": profile.sensor_width_mm,
            "sensor_height_mm": profile.sensor_height_mm,
            "image_width": profile.image_width,
            "image_height": profile.image_height,
            "anamorphic": (
                {
                    "squeeze_ratio": profile.anamorphic.squeeze_ratio,
                    "desqueeze_applied": profile.anamorphic.desqueeze_applied,
                }
                if profile.anamorphic is not None
                else None
            ),
        },
        "user_metadata": {
            "generator": "LensU",
            "version": LENSU_VERSION,
            "breathing_ratio_by_focal_length": breathing_summary,
            "anamorphic": (
                {
                    "squeeze_ratio": profile.anamorphic.squeeze_ratio,
                    "desqueeze_applied": profile.anamorphic.desqueeze_applied,
                    "calibration_space": "desqueezed",
                }
                if profile.anamorphic is not None
                else None
            ),
        },
        "distortion_table": [],
        "focal_length_table": [],
        "image_center_table": [],
        "nodal_offset_table": [],
        "st_map_table": [],
        "breathing_profiles": [],
    }

    calibration_lookup = {round(point.focal_length_mm, 3): point for point in profile.calibration_points}

    for point in profile.calibration_points:
        focus = 0.0
        zoom = point.focal_length_mm
        fx_norm, fy_norm = normalized_focal_lengths(point, (profile.image_width, profile.image_height))
        focal_length_info = {"fx_fy": [fx_norm, fy_norm]}

        ue_data["distortion_table"].append(
            {
                "focus": focus,
                "zoom": zoom,
                "distortion_info": {"parameters": [point.k1, point.k2, point.p1, point.p2, point.k3]},
                "focal_length_info": focal_length_info,
            }
        )
        ue_data["focal_length_table"].append(
            {"focus": focus, "zoom": zoom, "focal_length_info": focal_length_info}
        )
        ue_data["image_center_table"].append(
            {
                "focus": focus,
                "zoom": zoom,
                "image_center_info": {"principal_point": [point.cx, point.cy]},
            }
        )

        if point.is_fisheye and data_mode != "STMap":
            data_mode = "STMap"
            ue_data["data_mode"] = "STMap"

        if data_mode == "STMap" or include_stmaps or point.is_fisheye:
            stmap_name = f"{_safe_name(profile.lens_name)}_{zoom:.1f}mm_stmap.exr"
            stmap_path = generate_stmap_from_calibration(
                point,
                (profile.image_width, profile.image_height),
                stmap_directory / stmap_name,
            )
            ue_data["st_map_table"].append(
                {
                    "focus": focus,
                    "zoom": zoom,
                    "st_map_info": {
                        "distortion_map": stmap_path.name,
                        "map_format": "RGBA",
                        "projection_model": "equidistant" if point.is_fisheye else "brown-conrady",
                    },
                }
            )

    for breathing_profile in profile.breathing_profiles:
        source_point = calibration_lookup.get(round(breathing_profile.nominal_focal_length_mm, 3))
        source_fx = source_point.fx if source_point is not None else 0.0
        source_fy = source_point.fy if source_point is not None else 0.0
        source_measured = (
            measured_focal_length_mm(source_point, profile.sensor_width_mm, profile.image_width)
            if source_point is not None
            else breathing_profile.nominal_focal_length_mm
        )
        source_measured = source_measured or breathing_profile.nominal_focal_length_mm
        profile_payload = {
            "nominal_focal_length_mm": breathing_profile.nominal_focal_length_mm,
            "breathing_ratio": breathing_profile.breathing_ratio(),
            "points": [],
        }
        for breathing_point in breathing_profile.points:
            scale = breathing_point.measured_focal_length_mm / max(source_measured, 1e-6)
            fx_scaled = source_fx * scale
            fy_scaled = source_fy * scale
            fx_norm = fx_scaled / profile.image_width if profile.image_width else 0.0
            fy_norm = fy_scaled / profile.image_height if profile.image_height else 0.0
            ue_data["focal_length_table"].append(
                {
                    "focus": breathing_point.focus_distance_m,
                    "zoom": breathing_profile.nominal_focal_length_mm,
                    "focal_length_info": {"fx_fy": [fx_norm, fy_norm]},
                }
            )
            profile_payload["points"].append(
                {
                    "focus_distance_m": breathing_point.focus_distance_m,
                    "measured_focal_length_mm": breathing_point.measured_focal_length_mm,
                }
            )
        ue_data["breathing_profiles"].append(profile_payload)

    for offset in profile.nodal_offsets:
        ue_data["nodal_offset_table"].append(
            {
                "focus": 0.0,
                "zoom": offset.focal_length_mm,
                "nodal_offset": {
                    "location_offset": [offset.offset_x, offset.offset_y, offset.offset_z],
                    "rotation_offset": [offset.rotation_x, offset.rotation_y, offset.rotation_z],
                    "confidence": offset.confidence,
                    "method": offset.method,
                },
            }
        )

    json_path = output_path / f"{_safe_name(profile.lens_name)}_calibration.json"
    json_path.write_text(json.dumps(ue_data, indent=2), encoding="utf-8")
    return json_path


def export_ue_python_script(
    profile: LensProfile,
    json_filename: str,
    output_path: Path,
    data_mode: DataMode = "Parameters",
) -> Path:
    """Generate a UE Python import script for the exported JSON."""

    script = f'''"""
LensU auto-generated Unreal Engine import script.
Lens: {profile.lens_name}
Data mode: {data_mode}
"""

import json
import os

import unreal


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, "{json_filename}")
ASSET_NAME = "{_safe_name(profile.lens_name)}"
PACKAGE_PATH = "/Game/LensU"
ASSET_PATH = f"{{PACKAGE_PATH}}/{{ASSET_NAME}}"
STMAP_PACKAGE_PATH = f"{{PACKAGE_PATH}}/STMaps"


def import_texture(filename: str):
    source_path = os.path.join(SCRIPT_DIR, "stmaps", filename)
    if not os.path.exists(source_path):
        source_path = os.path.join(SCRIPT_DIR, filename)
    if not os.path.exists(source_path):
        unreal.log_warning(f"STMap source not found: {{source_path}}")
        return None

    task = unreal.AssetImportTask()
    task.filename = source_path
    task.destination_path = STMAP_PACKAGE_PATH
    task.automated = True
    task.save = True
    task.replace_existing = True
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset_name = os.path.splitext(os.path.basename(filename))[0]
    asset = unreal.EditorAssetLibrary.load_asset(f"{{STMAP_PACKAGE_PATH}}/{{asset_name}}")
    if asset is not None:
        try:
            asset.compression_settings = unreal.TextureCompressionSettings.TC_HDR
            asset.srgb = False
            unreal.EditorAssetLibrary.save_loaded_asset(asset)
        except Exception as exc:
            unreal.log_warning(f"Unable to tweak STMap texture settings: {{exc}}")
    return asset


def create_lens_file():
    with open(JSON_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
    lens_file = asset_tools.create_asset(
        asset_name=ASSET_NAME,
        package_path=PACKAGE_PATH,
        asset_class=unreal.LensFile,
        factory=unreal.LensFileFactory(),
    )

    if lens_file is None:
        unreal.log_error("Failed to create LensFile asset")
        return

    lens_file.user_metadata = data.get("user_metadata", {{}})
    if data.get("data_mode") == "STMap":
        lens_file.data_mode = unreal.LensDataMode.ST_MAP
    else:
        lens_file.data_mode = unreal.LensDataMode.PARAMETERS

    for entry in data.get("distortion_table", []):
        distortion_info = unreal.DistortionInfo()
        distortion_info.parameters = entry["distortion_info"]["parameters"]

        fx, fy = entry["focal_length_info"]["fx_fy"]
        focal_length_info = unreal.FocalLengthInfo()
        focal_length_info.fx_fy = unreal.Vector2D(fx, fy)
        lens_file.add_distortion_point(entry["focus"], entry["zoom"], distortion_info, focal_length_info)

    for entry in data.get("focal_length_table", []):
        fx, fy = entry["focal_length_info"]["fx_fy"]
        focal_length_info = unreal.FocalLengthInfo()
        focal_length_info.fx_fy = unreal.Vector2D(fx, fy)
        lens_file.add_focal_length_point(entry["focus"], entry["zoom"], focal_length_info)

    for entry in data.get("image_center_table", []):
        cx, cy = entry["image_center_info"]["principal_point"]
        image_center_info = unreal.ImageCenterInfo()
        image_center_info.principal_point = unreal.Vector2D(cx, cy)
        lens_file.add_image_center_point(entry["focus"], entry["zoom"], image_center_info)

    for entry in data.get("nodal_offset_table", []):
        location = entry["nodal_offset"]["location_offset"]
        rotation = entry["nodal_offset"]["rotation_offset"]
        nodal_offset = unreal.NodalPointOffset()
        nodal_offset.location_offset = unreal.Vector(location[0], location[1], location[2])
        nodal_offset.rotation_offset = unreal.Rotator(rotation[0], rotation[1], rotation[2])
        lens_file.add_nodal_offset_point(entry["focus"], entry["zoom"], nodal_offset)

    for entry in data.get("st_map_table", []):
        texture = import_texture(entry["st_map_info"]["distortion_map"])
        if texture is None:
            continue
        st_map_info = unreal.STMapInfo()
        st_map_info.distortion_map = texture
        try:
            st_map_info.map_format = unreal.CalibratedMapFormat.RGBA
        except Exception:
            pass
        lens_file.add_st_map_point(entry["focus"], entry["zoom"], st_map_info)

    unreal.EditorAssetLibrary.save_asset(ASSET_PATH)
    unreal.log(f"LensFile created at {{ASSET_PATH}}")


if __name__ == "__main__":
    create_lens_file()
'''

    output_path.mkdir(parents=True, exist_ok=True)
    script_path = output_path / f"import_{_safe_name(profile.lens_name)}_to_ue.py"
    script_path.write_text(script, encoding="utf-8")
    return script_path

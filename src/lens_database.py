"""Open LensU community database helpers."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from .calibration import CalibrationPoint, LENSU_VERSION, LensProfile, NodalOffset, lens_profile_from_dict
except ImportError:
    from calibration import CalibrationPoint, LENSU_VERSION, LensProfile, NodalOffset, lens_profile_from_dict


OPEN_FORMAT_VERSION = "lensu-open-v1"
VALID_LENS_TYPES = {"prime", "zoom", "anamorphic"}


def _profile_payload(profile: LensProfile) -> dict[str, object]:
    return {
        "format": OPEN_FORMAT_VERSION,
        "lens": {
            "name": profile.lens_name,
            "manufacturer": profile.manufacturer,
            "type": profile.lens_type,
            "mount": profile.mount,
        },
        "sensor": {
            "width_mm": profile.sensor_width_mm,
            "height_mm": profile.sensor_height_mm,
            "resolution": [profile.image_width, profile.image_height],
        },
        "color_pipeline": {
            "sensor_color_science": profile.color_science,
            "working_colorspace": profile.working_colorspace,
        },
        "calibrations": [point.__dict__ for point in profile.calibration_points],
        "nodal_offsets": [offset.__dict__ for offset in profile.nodal_offsets],
        "breathing": [
            {
                "nominal_focal_length_mm": breathing.nominal_focal_length_mm,
                "points": [point.__dict__ for point in breathing.points],
            }
            for breathing in profile.breathing_profiles
        ],
        "metadata": {
            "calibrated_by": profile.source,
            "date": datetime.now(timezone.utc).isoformat(),
            "tool": f"LensU v{LENSU_VERSION}",
            "notes": profile.notes,
            "lens_family": profile.lens_family,
        },
    }


def export_open_format(profile: LensProfile, output_path: Path) -> Path:
    """Export profile in LensU Open Database Format (.lensu.json)."""

    destination = output_path
    if destination.suffixes[-2:] != [".lensu", ".json"]:
        if destination.suffix.lower() == ".json":
            destination = destination.with_suffix(".lensu.json")
        else:
            destination = destination / f"{profile.lens_name.replace(' ', '_')}.lensu.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(_profile_payload(profile), indent=2), encoding="utf-8")
    return destination


def import_open_format(path: Path) -> LensProfile:
    """Import a .lensu.json file."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    valid, errors = validate_open_format(path)
    if not valid:
        raise ValueError("; ".join(errors))

    lens = payload["lens"]
    sensor = payload["sensor"]
    metadata = payload.get("metadata", {})
    color_pipeline = payload.get("color_pipeline", {})
    profile = lens_profile_from_dict(
        {
            "lens_name": lens.get("name", "Unknown Lens"),
            "lens_family": metadata.get("lens_family", ""),
            "manufacturer": lens.get("manufacturer", ""),
            "lens_type": lens.get("type", "prime"),
            "mount": lens.get("mount", ""),
            "sensor_width_mm": sensor.get("width_mm", 36.0),
            "sensor_height_mm": sensor.get("height_mm", 24.0),
            "image_width": sensor.get("resolution", [1920, 1080])[0],
            "image_height": sensor.get("resolution", [1920, 1080])[1],
            "notes": metadata.get("notes", ""),
            "source": metadata.get("calibrated_by", ""),
            "color_science": color_pipeline.get("sensor_color_science", ""),
            "working_colorspace": color_pipeline.get("working_colorspace", ""),
            "calibration_points": payload.get("calibrations", []),
            "nodal_offsets": payload.get("nodal_offsets", []),
            "breathing_profiles": payload.get("breathing", []),
        }
    )
    return profile


def _validate_calibration(index: int, calibration: object, errors: list[str]) -> None:
    if not isinstance(calibration, dict):
        errors.append(f"calibrations[{index}] must be an object.")
        return
    focal = calibration.get("focal_length_mm")
    if not isinstance(focal, (int, float)) or focal <= 0:
        errors.append(f"calibrations[{index}].focal_length_mm must be > 0.")
    for key in ("cx", "cy"):
        value = calibration.get(key)
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            errors.append(f"calibrations[{index}].{key} must be between 0 and 1.")


def _validate_nodal(index: int, offset: object, errors: list[str]) -> None:
    if not isinstance(offset, dict):
        errors.append(f"nodal_offsets[{index}] must be an object.")
        return
    focal = offset.get("focal_length_mm")
    if not isinstance(focal, (int, float)) or focal <= 0:
        errors.append(f"nodal_offsets[{index}].focal_length_mm must be > 0.")
    confidence = offset.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        errors.append(f"nodal_offsets[{index}].confidence must be between 0 and 1.")


def _validate_breathing(index: int, breathing: object, errors: list[str]) -> None:
    if not isinstance(breathing, dict):
        errors.append(f"breathing[{index}] must be an object.")
        return
    focal = breathing.get("nominal_focal_length_mm")
    if not isinstance(focal, (int, float)) or focal <= 0:
        errors.append(f"breathing[{index}].nominal_focal_length_mm must be > 0.")
    points = breathing.get("points", [])
    if not isinstance(points, list):
        errors.append(f"breathing[{index}].points must be a list.")
        return
    for point_index, point in enumerate(points):
        if not isinstance(point, dict):
            errors.append(f"breathing[{index}].points[{point_index}] must be an object.")
            continue
        focus_distance = point.get("focus_distance_m")
        measured = point.get("measured_focal_length_mm")
        if not isinstance(focus_distance, (int, float)) or focus_distance <= 0:
            errors.append(f"breathing[{index}].points[{point_index}].focus_distance_m must be > 0.")
        if not isinstance(measured, (int, float)) or measured <= 0:
            errors.append(f"breathing[{index}].points[{point_index}].measured_focal_length_mm must be > 0.")


def validate_open_format(path: Path) -> tuple[bool, list[str]]:
    """Validate a .lensu.json file against the schema. Returns (valid, errors)."""

    errors: list[str] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"Invalid JSON: {exc}"]

    if not isinstance(payload, dict):
        return False, ["Root payload must be an object."]
    if payload.get("format") != OPEN_FORMAT_VERSION:
        errors.append(f"format must be '{OPEN_FORMAT_VERSION}'.")

    lens = payload.get("lens")
    if not isinstance(lens, dict):
        errors.append("lens must be an object.")
    else:
        if not str(lens.get("name", "")).strip():
            errors.append("lens.name is required.")
        if not str(lens.get("manufacturer", "")).strip():
            errors.append("lens.manufacturer is required.")
        lens_type = lens.get("type", "")
        if lens_type not in VALID_LENS_TYPES:
            errors.append(f"lens.type must be one of {sorted(VALID_LENS_TYPES)}.")
        if not str(lens.get("mount", "")).strip():
            errors.append("lens.mount is required.")

    sensor = payload.get("sensor")
    if not isinstance(sensor, dict):
        errors.append("sensor must be an object.")
    else:
        for key in ("width_mm", "height_mm"):
            value = sensor.get(key)
            if not isinstance(value, (int, float)) or value <= 0:
                errors.append(f"sensor.{key} must be > 0.")
        resolution = sensor.get("resolution")
        if (
            not isinstance(resolution, list)
            or len(resolution) != 2
            or any(not isinstance(value, int) or value <= 0 for value in resolution)
        ):
            errors.append("sensor.resolution must be [width, height] with positive integers.")

    color_pipeline = payload.get("color_pipeline", {})
    if color_pipeline and not isinstance(color_pipeline, dict):
        errors.append("color_pipeline must be an object.")

    calibrations = payload.get("calibrations", [])
    if not isinstance(calibrations, list) or not calibrations:
        errors.append("calibrations must be a non-empty list.")
    elif isinstance(calibrations, list):
        for index, calibration in enumerate(calibrations):
            _validate_calibration(index, calibration, errors)

    nodal_offsets = payload.get("nodal_offsets", [])
    if not isinstance(nodal_offsets, list):
        errors.append("nodal_offsets must be a list.")
    else:
        for index, offset in enumerate(nodal_offsets):
            _validate_nodal(index, offset, errors)

    breathing_profiles = payload.get("breathing", [])
    if not isinstance(breathing_profiles, list):
        errors.append("breathing must be a list.")
    else:
        for index, breathing in enumerate(breathing_profiles):
            _validate_breathing(index, breathing, errors)

    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object.")

    return not errors, errors

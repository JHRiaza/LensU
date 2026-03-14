"""Local lens profile library helpers."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from calibration import LensProfile, lens_profile_from_dict


LIBRARY_DIR = Path.home() / ".lensu" / "library"


def _sanitize_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "lens_profile"


def _profile_summary(path: Path) -> dict:
    profile = LensProfile.load_json(path)
    focal_lengths = sorted(round(point.focal_length_mm, 3) for point in profile.calibration_points)
    rms_values = [point.rms_error for point in profile.calibration_points]
    created_dt = datetime.fromtimestamp(path.stat().st_mtime)
    sensor_text = f"{profile.sensor_width_mm:.2f}x{profile.sensor_height_mm:.2f}"
    return {
        "filename": path.name,
        "name": profile.lens_name,
        "date": created_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "date_iso": created_dt.isoformat(timespec="seconds"),
        "focal_lengths": focal_lengths,
        "sensor": sensor_text,
        "rms_avg": (sum(rms_values) / len(rms_values)) if rms_values else 0.0,
    }


def save_to_library(profile: LensProfile) -> Path:
    """Save a calibrated lens profile to the local library."""

    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{_sanitize_name(profile.lens_name)}_{stamp}.json"
    output_path = LIBRARY_DIR / filename
    profile.save_json(output_path)
    return output_path


def list_library() -> list[dict]:
    """List all saved profiles with summary info."""

    if not LIBRARY_DIR.exists():
        return []
    profiles: list[dict] = []
    for path in sorted(LIBRARY_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            profiles.append(_profile_summary(path))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            continue
    return profiles


def load_from_library(filename: str) -> LensProfile:
    """Load a profile from the library."""

    path = (LIBRARY_DIR / filename).resolve()
    if path.parent != LIBRARY_DIR.resolve():
        raise ValueError("Invalid library filename.")
    if not path.exists():
        raise FileNotFoundError(f"Profile not found in library: {filename}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return lens_profile_from_dict(data)


def delete_from_library(filename: str) -> bool:
    """Delete a profile from the library."""

    path = (LIBRARY_DIR / filename).resolve()
    if path.parent != LIBRARY_DIR.resolve():
        return False
    if not path.exists():
        return False
    try:
        path.unlink()
    except OSError:
        return False
    return True


def search_library(lens_name: str = "", sensor_type: str = "") -> list[dict]:
    """Search library by lens name or sensor type."""

    lens_query = lens_name.strip().lower()
    sensor_query = sensor_type.strip().lower()
    matches: list[dict] = []
    for item in list_library():
        if lens_query and lens_query not in item["name"].lower():
            continue
        if sensor_query and sensor_query not in item["sensor"].lower():
            continue
        matches.append(item)
    return matches

"""Preset cinema lens profiles."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from ..calibration import LensProfile, lens_profile_from_dict
except ImportError:
    from calibration import LensProfile, lens_profile_from_dict


PRESET_DIR = Path(__file__).resolve().parent


def list_presets() -> list[dict]:
    """List all available preset profiles."""

    presets: list[dict] = []
    for path in sorted(PRESET_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        presets.append(
            {
                "name": path.stem,
                "file": path.name,
                "lens_name": data.get("lens_name", path.stem),
                "lens_family": data.get("lens_family", ""),
                "type": data.get("type", "prime"),
                "notes": data.get("notes", ""),
            }
        )
    return presets


def load_preset(name: str) -> LensProfile:
    """Load a preset profile."""

    normalized = name.strip().lower().replace(".json", "")
    for path in sorted(PRESET_DIR.glob("*.json")):
        if path.stem.lower() != normalized:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        return lens_profile_from_dict(data)
    raise FileNotFoundError(f"Preset not found: {name}")

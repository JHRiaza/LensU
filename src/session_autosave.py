"""Session autosave and restore helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from .calibration import CameraRig, camera_rig_from_dict
except ImportError:
    from calibration import CameraRig, camera_rig_from_dict


def _state_dir() -> Path:
    preferred = Path.home() / ".lensu"
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except OSError:
        fallback = Path.cwd() / ".tmp_test" / "lensu_state"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


AUTOSAVE_PATH = _state_dir() / "autosave.json"


def autosave_exists(path: Path = AUTOSAVE_PATH) -> bool:
    return path.exists()


def write_autosave(
    rig: CameraRig,
    selected_camera_label: str,
    calibration_runs: dict[str, Any] | None = None,
    path: Path = AUTOSAVE_PATH,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "rig": rig.to_dict(),
        "selected_camera_label": selected_camera_label,
        "calibration_run_keys": sorted((calibration_runs or {}).keys()),
    }
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)
    return path


def load_autosave(path: Path = AUTOSAVE_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("rig"), dict):
        return None
    rig = camera_rig_from_dict(data["rig"])
    selected_camera_label = str(data.get("selected_camera_label") or next(iter(rig.cameras), "Camera A"))
    return {
        "rig": rig,
        "selected_camera_label": selected_camera_label,
        "calibration_runs": {},
    }

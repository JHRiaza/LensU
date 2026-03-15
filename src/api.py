"""Builtin HTTP API server for LensU."""

from __future__ import annotations

import json
import threading
import zipfile
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

try:
    from . import __version__
    from .batch import batch_calibrate_detailed
    from .calibration import CalibrationPoint, LensProfile, calibrate_from_images
    from .lens_library import list_library, load_from_library
    from .nuke_export import export_nuke_gizmo, export_nuke_script
    from .presets import list_presets, load_preset
    from .temp_paths import lensu_tempdir
    from .ue_export import export_ue_json, export_ue_python_script
except ImportError:
    __version__ = "1.7.0"
    from batch import batch_calibrate_detailed
    from calibration import CalibrationPoint, LensProfile, calibrate_from_images
    from lens_library import list_library, load_from_library
    from nuke_export import export_nuke_gizmo, export_nuke_script
    from presets import list_presets, load_preset
    from temp_paths import lensu_tempdir
    from ue_export import export_ue_json, export_ue_python_script


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
SENSOR_PRESETS = {
    "full-frame": (36.0, 24.0),
    "apsc-canon": (22.3, 14.9),
    "apsc-sony": (23.5, 15.6),
    "m43": (17.3, 13.0),
    "super35": (24.89, 18.66),
}


def _parse_pattern(value: Any) -> tuple[int, int]:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        cols = int(value[0])
        rows = int(value[1])
        return cols, rows
    raw = str(value).strip().lower().replace(" ", "")
    for separator in ("x", ",", ":"):
        if separator in raw:
            left, right = raw.split(separator, maxsplit=1)
            return int(left), int(right)
    raise ValueError("Pattern must be like 9x6.")


def _parse_sensor(value: str) -> tuple[float, float]:
    raw = value.strip().lower()
    if raw in SENSOR_PRESETS:
        return SENSOR_PRESETS[raw]
    for separator in ("x", ",", ":"):
        if separator in raw:
            left, right = raw.split(separator, maxsplit=1)
            return float(left), float(right)
    raise ValueError("Sensor must be a preset name or WxH, for example full-frame or 36x24.")


def _image_paths_from_dir(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Images directory not found: {directory}")
    return [path for path in sorted(directory.iterdir()) if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]


def _json_response(handler: BaseHTTPRequestHandler, status_code: int, payload: Any) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _binary_response(
    handler: BaseHTTPRequestHandler,
    status_code: int,
    payload: bytes,
    content_type: str,
    filename: str | None = None,
) -> None:
    handler.send_response(status_code)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    if filename:
        handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
    handler.end_headers()
    handler.wfile.write(payload)


def _error_response(handler: BaseHTTPRequestHandler, status_code: int, message: str) -> None:
    _json_response(handler, status_code, {"error": message})


def _read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    raw = handler.rfile.read(length) if length > 0 else b"{}"
    data = json.loads(raw.decode("utf-8") or "{}")
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object.")
    return data


def _resolve_library_profile(name: str) -> LensProfile:
    for item in list_library():
        if item["filename"] == name or item["name"] == name:
            return load_from_library(item["filename"])
    raise FileNotFoundError(f"Profile not found in library: {name}")


def _resolve_preset(name: str) -> LensProfile:
    normalized = name.strip().lower().replace(".json", "")
    return load_preset(normalized)


def _calibration_payload(point: CalibrationPoint | None, diagnostics) -> dict[str, Any]:
    return {
        "calibration_point": asdict(point) if point is not None else None,
        "rms_error": float(point.rms_error) if point is not None else None,
        "images_used": int(point.num_images) if point is not None else 0,
        "images_total": len(diagnostics.image_results),
    }


def _build_export_zip(profile: LensProfile, export_format: str, include_stmaps: bool) -> tuple[str, bytes]:
    export_format = export_format.lower()
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        if export_format == "ue":
            with lensu_tempdir() as tmpdir:
                tmp_path = Path(tmpdir)
                stmap_dir = tmp_path / "stmaps"
                json_path = export_ue_json(
                    profile=profile,
                    output_path=tmp_path,
                    data_mode="STMap" if include_stmaps else "Parameters",
                    stmap_directory=stmap_dir,
                    include_stmaps=include_stmaps,
                )
                script_path = export_ue_python_script(
                    profile=profile,
                    json_filename=json_path.name,
                    output_path=tmp_path,
                    data_mode="STMap" if include_stmaps else "Parameters",
                )
                archive.write(json_path, json_path.name)
                archive.write(script_path, script_path.name)
                if include_stmaps and stmap_dir.exists():
                    for stmap_file in sorted(stmap_dir.iterdir()):
                        archive.write(stmap_file, f"stmaps/{stmap_file.name}")
        elif export_format == "nuke":
            with lensu_tempdir() as tmpdir:
                tmp_path = Path(tmpdir)
                script_path = export_nuke_script(profile, tmp_path / f"{profile.lens_name.replace(' ', '_')}.nk")
                gizmo_path = export_nuke_gizmo(profile, tmp_path / f"{profile.lens_name.replace(' ', '_')}.gizmo")
                archive.write(script_path, script_path.name)
                archive.write(gizmo_path, gizmo_path.name)
        else:
            raise ValueError(f"Unsupported export format: {export_format}")
    return f"LensU_{profile.lens_name.replace(' ', '_')}_{export_format}.zip", buffer.getvalue()


class LensUAPIHandler(BaseHTTPRequestHandler):
    """Simple REST API for LensU."""

    server_version = "LensUAPI/1.7.0"

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            if path == "/api/status":
                _json_response(self, 200, {"status": "ok", "version": __version__})
                return
            if path == "/api/library":
                _json_response(self, 200, list_library())
                return
            if path.startswith("/api/library/"):
                name = unquote(path.split("/api/library/", 1)[1])
                profile = _resolve_library_profile(name)
                _json_response(self, 200, profile.to_dict())
                return
            if path == "/api/presets":
                _json_response(self, 200, list_presets())
                return
            if path.startswith("/api/presets/"):
                name = unquote(path.split("/api/presets/", 1)[1])
                profile = _resolve_preset(name)
                _json_response(self, 200, profile.to_dict())
                return
            _error_response(self, 404, f"Unknown endpoint: {path}")
        except FileNotFoundError as exc:
            _error_response(self, 404, str(exc))
        except Exception as exc:
            _error_response(self, 500, str(exc))

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        try:
            body = _read_json_body(self)
            if path == "/api/calibrate":
                images_dir = Path(str(body["images_dir"]))
                focal_length = float(body.get("focal_length_mm", 50.0))
                pattern_size = _parse_pattern(body.get("pattern_size", "9x6"))
                sensor_width, sensor_height = _parse_sensor(str(body.get("sensor", "full-frame")))
                image_paths = _image_paths_from_dir(images_dir)
                point, diagnostics = calibrate_from_images(
                    image_paths=image_paths,
                    pattern_size=pattern_size,
                    focal_length_mm=focal_length,
                    square_size_mm=float(body.get("square_size_mm", 25.0)),
                )
                profile = LensProfile(
                    lens_name=body.get("lens_name", f"{images_dir.name}_{focal_length:.1f}mm"),
                    sensor_width_mm=sensor_width,
                    sensor_height_mm=sensor_height,
                )
                if point is not None:
                    profile.add_calibration(point)
                    if diagnostics.image_size:
                        profile.image_width, profile.image_height = diagnostics.image_size
                payload = _calibration_payload(point, diagnostics)
                payload["profile"] = profile.to_dict()
                _json_response(self, 200, payload)
                return
            if path == "/api/batch":
                base_dir = Path(str(body["base_dir"]))
                sensor_width, sensor_height = _parse_sensor(str(body.get("sensor", "full-frame")))
                pattern_size = _parse_pattern(body.get("pattern_size", "9x6"))
                profile, results = batch_calibrate_detailed(
                    base_dir=base_dir,
                    pattern_size=pattern_size,
                    square_size_mm=float(body.get("square_size_mm", 25.0)),
                    detection_mode=str(body.get("mode", "checkerboard")),
                    sensor_width_mm=sensor_width,
                    sensor_height_mm=sensor_height,
                )
                _json_response(
                    self,
                    200,
                    {
                        "profile": profile.to_dict(),
                        "focal_lengths_calibrated": [point.focal_length_mm for point in profile.calibration_points],
                        "results": [asdict(result) for result in results],
                    },
                )
                return
            if path == "/api/export":
                profile_name = str(body["profile_name"])
                export_format = str(body.get("format", "ue"))
                include_stmaps = bool(body.get("include_stmaps", False))
                source = str(body.get("source", "library")).lower()
                profile = _resolve_preset(profile_name) if source == "preset" else _resolve_library_profile(profile_name)
                filename, payload = _build_export_zip(profile, export_format, include_stmaps)
                _binary_response(self, 200, payload, "application/zip", filename)
                return
            _error_response(self, 404, f"Unknown endpoint: {path}")
        except KeyError as exc:
            _error_response(self, 400, f"Missing required field: {exc.args[0]}")
        except (ValueError, FileNotFoundError) as exc:
            _error_response(self, 400, str(exc))
        except Exception as exc:
            _error_response(self, 500, str(exc))


def create_api_server(host: str = "0.0.0.0", port: int = 8600) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), LensUAPIHandler)


def start_api_server(host: str = "0.0.0.0", port: int = 8600) -> ThreadingHTTPServer:
    """Start the LensU API server."""

    server = create_api_server(host=host, port=port)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return server


def start_api_server_in_thread(host: str = "127.0.0.1", port: int = 8600) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = create_api_server(host=host, port=port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread

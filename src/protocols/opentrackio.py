"""OpenTrackIO parsing and UDP multicast listener helpers."""

from __future__ import annotations

import json
import socket
import struct
import threading
from dataclasses import dataclass
from typing import Callable

try:
    from ..calibration import LensProfile
    from ..encoder_mapping import EncoderMapping, create_mapping_from_samples
except ImportError:
    try:
        from calibration import LensProfile
        from encoder_mapping import EncoderMapping, create_mapping_from_samples
    except ImportError:
        LensProfile = None  # type: ignore[assignment]
        EncoderMapping = None  # type: ignore[assignment]
        create_mapping_from_samples = None  # type: ignore[assignment]


@dataclass
class OpenTrackIOSample:
    """Parsed OpenTrackIO tracking sample."""

    timestamp: float
    translation: tuple[float, float, float]
    rotation: tuple[float, float, float]
    focal_length_mm: float = 0.0
    focus_distance_m: float = 0.0
    iris_fstop: float = 0.0
    zoom_encoder: int | None = None
    focus_encoder: int | None = None
    iris_encoder: int | None = None
    distortion_coefficients: list[float] | None = None


def parse_opentrackio(data: bytes) -> OpenTrackIOSample:
    """Parse an OpenTrackIO JSON packet."""

    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid OpenTrackIO JSON payload.") from exc

    if payload.get("protocol") != "OpenTrackIO":
        raise ValueError("Unsupported protocol payload.")

    sample = payload.get("sample")
    if not isinstance(sample, dict):
        raise ValueError("Missing OpenTrackIO sample payload.")

    transforms = sample.get("transforms", {})
    translation = tuple(float(value) for value in transforms.get("translation", [0.0, 0.0, 0.0]))
    rotation = tuple(float(value) for value in transforms.get("rotation", [0.0, 0.0, 0.0]))
    if len(translation) != 3 or len(rotation) != 3:
        raise ValueError("OpenTrackIO transforms must contain three translation and rotation values.")

    lens = sample.get("lens", {})
    encoders = sample.get("encoders", {})
    distortion = sample.get("distortion", {})
    coefficients = distortion.get("coefficients")
    if coefficients is not None:
        coefficients = [float(value) for value in coefficients]

    return OpenTrackIOSample(
        timestamp=float(sample.get("timestamp", 0.0)),
        translation=translation,
        rotation=rotation,
        focal_length_mm=float(lens.get("focalLength", 0.0)),
        focus_distance_m=float(lens.get("focusDistance", 0.0)),
        iris_fstop=float(lens.get("iris", 0.0)),
        zoom_encoder=int(encoders["zoom"]) if "zoom" in encoders else None,
        focus_encoder=int(encoders["focus"]) if "focus" in encoders else None,
        iris_encoder=int(encoders["iris"]) if "iris" in encoders else None,
        distortion_coefficients=coefficients,
    )


def map_opentrackio_fiz(sample: OpenTrackIOSample, lens_profile: LensProfile) -> dict[str, float]:
    """Prefer physical values from the packet, but apply encoder maps when raw values are present."""

    if EncoderMapping is None or create_mapping_from_samples is None:
        return {
            "zoom_mm": sample.focal_length_mm,
            "focus_m": sample.focus_distance_m,
            "iris": sample.iris_fstop,
        }

    mappings = lens_profile.encoder_mappings or {}
    mapping = EncoderMapping(
        lens_name=lens_profile.lens_name,
        focus_map=create_mapping_from_samples(
            [(int(item["encoder"]), float(item["value"])) for item in mappings.get("focus", [])]
        ),
        zoom_map=create_mapping_from_samples(
            [(int(item["encoder"]), float(item["value"])) for item in mappings.get("zoom", [])]
        ),
        iris_map=create_mapping_from_samples(
            [(int(item["encoder"]), float(item["value"])) for item in mappings.get("iris", [])]
        ),
    )
    return {
        "zoom_mm": (
            mapping.encoder_to_zoom(sample.zoom_encoder)
            if sample.zoom_encoder is not None and mapping.zoom_map
            else sample.focal_length_mm
        ),
        "focus_m": (
            mapping.encoder_to_focus(sample.focus_encoder)
            if sample.focus_encoder is not None and mapping.focus_map
            else sample.focus_distance_m
        ),
        "iris": (
            mapping.encoder_to_iris(sample.iris_encoder)
            if sample.iris_encoder is not None and mapping.iris_map
            else sample.iris_fstop
        ),
    }


def _listener_loop(sock: socket.socket, callback: Callable[[OpenTrackIOSample], None] | None) -> None:
    while True:
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            sample = parse_opentrackio(data)
        except ValueError:
            continue

        if callback is None:
            continue
        try:
            callback(sample)
        except Exception:
            continue


def start_opentrackio_listener(
    address: str = "239.1.1.1",
    port: int = 5555,
    callback: Callable[[OpenTrackIOSample], None] | None = None,
) -> socket.socket:
    """Start a UDP multicast listener for OpenTrackIO packets."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind(("", int(port)))
    except OSError:
        sock.bind((address, int(port)))
    membership = socket.inet_aton(address) + struct.pack("=I", socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
    sock.settimeout(0.5)
    thread = threading.Thread(target=_listener_loop, args=(sock, callback), daemon=True)
    thread.start()
    return sock

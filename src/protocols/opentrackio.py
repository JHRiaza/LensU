"""OpenTrackIO parsing and UDP multicast listener helpers."""

from __future__ import annotations

import json
import socket
import struct
import threading
from dataclasses import dataclass
from typing import Callable


@dataclass
class OpenTrackIOSample:
    """Parsed OpenTrackIO tracking sample."""

    timestamp: float
    translation: tuple[float, float, float]
    rotation: tuple[float, float, float]
    focal_length_mm: float = 0.0
    focus_distance_m: float = 0.0
    iris_fstop: float = 0.0
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
        distortion_coefficients=coefficients,
    )


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


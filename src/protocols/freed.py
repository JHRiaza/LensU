"""FreeD protocol parsing and UDP listener helpers."""

from __future__ import annotations

import socket
import struct
import threading
from dataclasses import dataclass
from typing import Callable

from calibration import LensProfile


MAX_24BIT = float((1 << 24) - 1)


@dataclass
class FreeDPacket:
    """Parsed FreeD D1 data packet."""

    camera_id: int
    pan: float
    tilt: float
    roll: float
    pos_x: float
    pos_y: float
    pos_z: float
    zoom: int
    focus: int


def _signed_int24(payload: bytes) -> int:
    value = struct.unpack(">I", b"\x00" + payload)[0]
    if value & 0x800000:
        value -= 0x1000000
    return value


def _unsigned_int24(payload: bytes) -> int:
    return struct.unpack(">I", b"\x00" + payload)[0]


def _checksum_valid(data: bytes) -> bool:
    checksum = data[28]
    payload_sum = sum(data[:28]) & 0xFF
    return checksum == payload_sum or checksum == ((-payload_sum) & 0xFF)


def parse_freed_d1(data: bytes) -> FreeDPacket:
    """Parse a FreeD D1 packet (29 bytes)."""

    if len(data) != 29:
        raise ValueError("FreeD D1 packets must be exactly 29 bytes.")
    if data[0] != 0xD1:
        raise ValueError("Unsupported FreeD packet type.")
    if not _checksum_valid(data):
        raise ValueError("Invalid FreeD checksum.")

    return FreeDPacket(
        camera_id=int(data[1]),
        pan=_signed_int24(data[2:5]) / 32768.0,
        tilt=_signed_int24(data[5:8]) / 32768.0,
        roll=_signed_int24(data[8:11]) / 32768.0,
        pos_x=float(_signed_int24(data[11:14])),
        pos_y=float(_signed_int24(data[14:17])),
        pos_z=float(_signed_int24(data[17:20])),
        zoom=_unsigned_int24(data[20:23]),
        focus=_unsigned_int24(data[23:26]),
    )


def _listener_loop(sock: socket.socket, callback: Callable[[FreeDPacket], None] | None) -> None:
    while True:
        try:
            data, _ = sock.recvfrom(4096)
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            packet = parse_freed_d1(data)
        except ValueError:
            continue

        if callback is None:
            continue
        try:
            callback(packet)
        except Exception:
            continue


def start_freed_listener(
    port: int = 6000,
    callback: Callable[[FreeDPacket], None] | None = None,
) -> socket.socket:
    """Start a UDP listener for FreeD packets."""

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", int(port)))
    sock.settimeout(0.5)
    thread = threading.Thread(target=_listener_loop, args=(sock, callback), daemon=True)
    thread.start()
    return sock


def _interpolate_mapping(entries: list[dict[str, float]], encoder_value: int) -> float:
    ordered = sorted(entries, key=lambda item: float(item["encoder"]))
    if not ordered:
        return float(encoder_value) / MAX_24BIT
    if encoder_value <= ordered[0]["encoder"]:
        return float(ordered[0]["value"])
    if encoder_value >= ordered[-1]["encoder"]:
        return float(ordered[-1]["value"])

    for left, right in zip(ordered, ordered[1:]):
        left_encoder = float(left["encoder"])
        right_encoder = float(right["encoder"])
        if left_encoder <= encoder_value <= right_encoder:
            span = max(right_encoder - left_encoder, 1.0)
            alpha = (float(encoder_value) - left_encoder) / span
            return float(left["value"]) + alpha * (float(right["value"]) - float(left["value"]))
    return float(encoder_value) / MAX_24BIT


def freed_to_fiz(packet: FreeDPacket, lens_profile: LensProfile) -> dict:
    """Map raw FreeD encoder values to calibrated FIZ values."""

    mappings = lens_profile.encoder_mappings or {}
    focus_map = mappings.get("focus", [])
    iris_map = mappings.get("iris", [])
    zoom_map = mappings.get("zoom", [])

    if not zoom_map and lens_profile.calibration_points:
        ordered_points = sorted(lens_profile.calibration_points, key=lambda item: item.focal_length_mm)
        if len(ordered_points) == 1:
            zoom_mm = float(ordered_points[0].focal_length_mm)
        else:
            alpha = float(packet.zoom) / MAX_24BIT
            zoom_mm = float(ordered_points[0].focal_length_mm) + alpha * (
                float(ordered_points[-1].focal_length_mm) - float(ordered_points[0].focal_length_mm)
            )
    else:
        zoom_mm = _interpolate_mapping(zoom_map, packet.zoom)

    return {
        "focus_m": _interpolate_mapping(focus_map, packet.focus),
        "iris": _interpolate_mapping(iris_map, packet.focus) if iris_map else 0.0,
        "zoom_mm": zoom_mm,
    }

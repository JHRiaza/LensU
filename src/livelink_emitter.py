"""LiveLink-compatible UDP JSON emitter for Unreal Engine workflows."""

from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any

try:
    from .calibration import CalibrationPoint, LensProfile, NodalOffset
except ImportError:
    from calibration import CalibrationPoint, LensProfile, NodalOffset


def _lerp(left: float, right: float, alpha: float) -> float:
    return left + alpha * (right - left)


def _interpolate_point(points: list[CalibrationPoint], focal_length_mm: float) -> CalibrationPoint | None:
    ordered = sorted(points, key=lambda item: item.focal_length_mm)
    if not ordered:
        return None
    if len(ordered) == 1 or focal_length_mm <= ordered[0].focal_length_mm:
        return ordered[0]
    if focal_length_mm >= ordered[-1].focal_length_mm:
        return ordered[-1]

    for left, right in zip(ordered, ordered[1:]):
        if left.focal_length_mm <= focal_length_mm <= right.focal_length_mm:
            span = max(right.focal_length_mm - left.focal_length_mm, 1e-6)
            alpha = (focal_length_mm - left.focal_length_mm) / span
            return CalibrationPoint(
                focal_length_mm=focal_length_mm,
                k1=_lerp(left.k1, right.k1, alpha),
                k2=_lerp(left.k2, right.k2, alpha),
                p1=_lerp(left.p1, right.p1, alpha),
                p2=_lerp(left.p2, right.p2, alpha),
                k3=_lerp(left.k3, right.k3, alpha),
                cx=_lerp(left.cx, right.cx, alpha),
                cy=_lerp(left.cy, right.cy, alpha),
                fx=_lerp(left.fx, right.fx, alpha),
                fy=_lerp(left.fy, right.fy, alpha),
                rms_error=_lerp(left.rms_error, right.rms_error, alpha),
                num_images=max(left.num_images, right.num_images),
                detection_mode=left.detection_mode,
                is_fisheye=left.is_fisheye or right.is_fisheye,
                fisheye_coeffs=list(left.fisheye_coeffs or right.fisheye_coeffs),
            )
    return ordered[-1]


def _interpolate_nodal(offsets: list[NodalOffset], focal_length_mm: float) -> NodalOffset:
    ordered = sorted(offsets, key=lambda item: item.focal_length_mm)
    if not ordered:
        return NodalOffset(focal_length_mm=focal_length_mm)
    if len(ordered) == 1 or focal_length_mm <= ordered[0].focal_length_mm:
        return ordered[0]
    if focal_length_mm >= ordered[-1].focal_length_mm:
        return ordered[-1]

    for left, right in zip(ordered, ordered[1:]):
        if left.focal_length_mm <= focal_length_mm <= right.focal_length_mm:
            span = max(right.focal_length_mm - left.focal_length_mm, 1e-6)
            alpha = (focal_length_mm - left.focal_length_mm) / span
            return NodalOffset(
                focal_length_mm=focal_length_mm,
                offset_x=_lerp(left.offset_x, right.offset_x, alpha),
                offset_y=_lerp(left.offset_y, right.offset_y, alpha),
                offset_z=_lerp(left.offset_z, right.offset_z, alpha),
                rotation_x=_lerp(left.rotation_x, right.rotation_x, alpha),
                rotation_y=_lerp(left.rotation_y, right.rotation_y, alpha),
                rotation_z=_lerp(left.rotation_z, right.rotation_z, alpha),
                confidence=_lerp(left.confidence, right.confidence, alpha),
                method=left.method,
            )
    return ordered[-1]


class LiveLinkEmitter:
    """Emit lens calibration data to UE LiveLink over UDP."""

    def __init__(self, target_ip: str = "127.0.0.1", port: int = 11111, subject_name: str = "LensU"):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.target = (target_ip, int(port))
        self.subject_name = subject_name
        self.frame = 0
        self.last_payload: dict[str, Any] | None = None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def _payload_from_values(
        self,
        profile: LensProfile,
        focal_length_mm: float,
        aperture: float,
        focus_distance_m: float,
    ) -> dict[str, Any]:
        point = _interpolate_point(profile.calibration_points, focal_length_mm)
        offset = _interpolate_nodal(profile.nodal_offsets, focal_length_mm)
        distortion = (
            [point.k1, point.k2, point.p1, point.p2, point.k3]
            if point is not None
            else [0.0, 0.0, 0.0, 0.0, 0.0]
        )
        image_center = [point.cx, point.cy] if point is not None else [0.5, 0.5]
        return {
            "SubjectName": self.subject_name,
            "FrameNumber": self.frame,
            "FocalLength": float(focal_length_mm),
            "Aperture": float(aperture),
            "FocusDistance": float(focus_distance_m),
            "DistortionParameters": [float(value) for value in distortion],
            "ImageCenter": [float(value) for value in image_center],
            "NodalOffset": [
                float(offset.offset_x),
                float(offset.offset_y),
                float(offset.offset_z),
                float(offset.rotation_x),
                float(offset.rotation_y),
                float(offset.rotation_z),
            ],
            "Lens": {
                "Name": profile.lens_name,
                "Type": profile.lens_type,
                "SensorWidthMm": float(profile.sensor_width_mm),
                "SensorHeightMm": float(profile.sensor_height_mm),
            },
        }

    def _send_payload(self, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.socket.sendto(encoded, self.target)
        with self._lock:
            self.frame += 1
            self.last_payload = dict(payload)
            self.last_payload["FrameNumber"] = self.frame - 1

    def send_static_profile(self, profile: LensProfile, focal_length_mm: float):
        """Send a static lens profile."""

        payload = self._payload_from_values(profile, focal_length_mm, aperture=2.8, focus_distance_m=3.0)
        self._send_payload(payload)

    def send_fiz_update(self, focus: float, iris: float, zoom: float, profile: LensProfile):
        """Send interpolated lens data based on current FIZ values."""

        payload = self._payload_from_values(
            profile=profile,
            focal_length_mm=float(zoom),
            aperture=float(iris),
            focus_distance_m=float(focus),
        )
        self._send_payload(payload)

    def start_streaming(self, profile: LensProfile, fps: int = 24):
        """Start continuous streaming at specified frame rate."""

        fps = max(int(fps), 1)
        interval = 1.0 / fps
        self.stop_streaming()
        self._stop_event.clear()

        def _loop() -> None:
            focal_length = (
                float(profile.calibration_points[0].focal_length_mm) if profile.calibration_points else 50.0
            )
            while not self._stop_event.is_set():
                with self._lock:
                    cached = dict(self.last_payload) if self.last_payload is not None else None
                if cached is None:
                    cached = self._payload_from_values(profile, focal_length, aperture=2.8, focus_distance_m=3.0)
                cached["FrameNumber"] = self.frame
                try:
                    self._send_payload(cached)
                except OSError:
                    self._stop_event.set()
                    break
                time.sleep(interval)

        self._thread = threading.Thread(target=_loop, daemon=True, name="lensu-livelink")
        self._thread.start()

    def stop_streaming(self):
        """Stop streaming."""

        self._stop_event.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        self._thread = None

    def close(self) -> None:
        self.stop_streaming()
        try:
            self.socket.close()
        except OSError:
            pass

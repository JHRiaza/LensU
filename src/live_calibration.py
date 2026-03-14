"""Live calibration helpers and Streamlit UI."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import streamlit as st

from calibration import (
    CalibrationDiagnostics,
    CalibrationPoint,
    accuracy_grade,
    calibrate_anamorphic_detailed,
    calibrate_from_charuco_images,
    calibrate_from_images,
    compute_coverage_heatmap,
)


def _state() -> dict[str, Any]:
    if "live_calibration_state" not in st.session_state:
        st.session_state.live_calibration_state = {
            "captures": [],
            "preview_bytes": None,
            "preview_name": None,
            "preview_overlay": None,
            "last_signature": None,
            "last_rms": None,
        }
    return st.session_state.live_calibration_state


def list_camera_devices(max_devices: int = 5) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for index in range(max_devices):
        capture = cv2.VideoCapture(index)
        if capture.isOpened():
            ok, frame = capture.read()
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            if ok and frame is not None:
                height = int(frame.shape[0])
                width = int(frame.shape[1])
            devices.append(
                {
                    "index": index,
                    "label": f"Camera {index}" + (f" ({width}x{height})" if width and height else ""),
                }
            )
        capture.release()
    return devices


def _decode_uploaded(uploaded_file: Any) -> np.ndarray | None:
    file_bytes = uploaded_file.getvalue()
    buffer = np.frombuffer(file_bytes, dtype=np.uint8)
    return cv2.imdecode(buffer, cv2.IMREAD_COLOR)


def _detect_frame(image: np.ndarray, mode: str, settings: dict[str, Any]) -> tuple[bool, np.ndarray, np.ndarray | None]:
    from calibration import detect_charuco, detect_checkerboard

    if mode == "ChArUco":
        found, _, _, overlay = detect_charuco(
            image,
            board_size=settings["charuco_board_size"],
            square_length_mm=settings["charuco_square_mm"],
            marker_length_mm=settings["charuco_marker_mm"],
            dictionary=settings["charuco_dictionary"],
        )
    else:
        found, _, overlay = detect_checkerboard(image, settings["checkerboard_pattern"])

    signature = None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    signature = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
    return found, overlay, signature


def _signature_distance(current: np.ndarray | None, previous: np.ndarray | None) -> float:
    if current is None or previous is None:
        return 1.0
    diff = np.mean(np.abs(current.astype(np.float32) - previous.astype(np.float32)))
    return float(diff / 255.0)


def _calibrate_captures(
    captures: list[dict[str, Any]],
    focal_length_mm: float,
    mode: str,
    settings: dict[str, Any],
) -> tuple[CalibrationPoint | None, CalibrationDiagnostics]:
    with tempfile.TemporaryDirectory() as tmpdir:
        paths: list[Path] = []
        for index, capture in enumerate(captures):
            path = Path(tmpdir) / f"live_{index:03d}.png"
            path.write_bytes(capture["bytes"])
            paths.append(path)
        if settings.get("anamorphic_enabled") and mode != "ChArUco":
            point, diagnostics, _ = calibrate_anamorphic_detailed(
                paths,
                pattern_size=settings["checkerboard_pattern"],
                square_size_mm=settings["checker_square_mm"],
                focal_length_mm=focal_length_mm,
                squeeze_ratio=settings["squeeze_ratio"],
                desqueezed=settings["anamorphic_desqueezed"],
            )
            return point, diagnostics
        if settings.get("anamorphic_enabled") and mode == "ChArUco":
            desqueezed = bool(settings["anamorphic_desqueezed"])
            squeeze_ratio = float(settings["squeeze_ratio"])
            with tempfile.TemporaryDirectory() as tmpdir_charuco:
                temp_dir = Path(tmpdir_charuco)
                if desqueezed:
                    desqueezed_paths = paths
                    squeezed_paths: list[Path] = []
                    for index, path in enumerate(paths):
                        image = cv2.imread(str(path))
                        if image is None:
                            continue
                        squeezed = cv2.resize(
                            image,
                            (max(1, int(round(image.shape[1] / squeeze_ratio))), image.shape[0]),
                            interpolation=cv2.INTER_AREA,
                        )
                        target = temp_dir / f"squeezed_{index:03d}.png"
                        cv2.imwrite(str(target), squeezed)
                        squeezed_paths.append(target)
                else:
                    squeezed_paths = paths
                    desqueezed_paths = []
                    for index, path in enumerate(paths):
                        image = cv2.imread(str(path))
                        if image is None:
                            continue
                        desqueezed_image = cv2.resize(
                            image,
                            (max(1, int(round(image.shape[1] * squeeze_ratio))), image.shape[0]),
                            interpolation=cv2.INTER_CUBIC,
                        )
                        target = temp_dir / f"desqueezed_{index:03d}.png"
                        cv2.imwrite(str(target), desqueezed_image)
                        desqueezed_paths.append(target)
                point, diagnostics = calibrate_from_charuco_images(
                    desqueezed_paths,
                    board_size=settings["charuco_board_size"],
                    square_length_mm=settings["charuco_square_mm"],
                    marker_length_mm=settings["charuco_marker_mm"],
                    dictionary=settings["charuco_dictionary"],
                    focal_length_mm=focal_length_mm,
                )
                squeezed_point, _ = calibrate_from_charuco_images(
                    squeezed_paths,
                    board_size=settings["charuco_board_size"],
                    square_length_mm=settings["charuco_square_mm"],
                    marker_length_mm=settings["charuco_marker_mm"],
                    dictionary=settings["charuco_dictionary"],
                    focal_length_mm=focal_length_mm,
                )
                if point is not None and squeezed_point is not None:
                    point.anamorphic_desqueezed = {
                        "k1": point.k1,
                        "k2": point.k2,
                        "p1": point.p1,
                        "p2": point.p2,
                        "k3": point.k3,
                        "cx": point.cx,
                        "cy": point.cy,
                        "fx": point.fx,
                        "fy": point.fy,
                        "rms_error": point.rms_error,
                    }
                    point.anamorphic_squeezed = {
                        "k1": squeezed_point.k1,
                        "k2": squeezed_point.k2,
                        "p1": squeezed_point.p1,
                        "p2": squeezed_point.p2,
                        "k3": squeezed_point.k3,
                        "cx": squeezed_point.cx,
                        "cy": squeezed_point.cy,
                        "fx": squeezed_point.fx,
                        "fy": squeezed_point.fy,
                        "rms_error": squeezed_point.rms_error,
                    }
                    point.detection_mode = f"{point.detection_mode} (Anamorphic {squeeze_ratio:.2f}x)"
                return point, diagnostics
        if mode == "ChArUco":
            return calibrate_from_charuco_images(
                paths,
                board_size=settings["charuco_board_size"],
                square_length_mm=settings["charuco_square_mm"],
                marker_length_mm=settings["charuco_marker_mm"],
                dictionary=settings["charuco_dictionary"],
                focal_length_mm=focal_length_mm,
            )
        return calibrate_from_images(
            paths,
            pattern_size=settings["checkerboard_pattern"],
            square_size_mm=settings["checker_square_mm"],
            focal_length_mm=focal_length_mm,
        )


def _coverage_metrics(diagnostics: CalibrationDiagnostics) -> tuple[float, np.ndarray | None]:
    if diagnostics.image_size is None:
        return 0.0, None
    heatmap = compute_coverage_heatmap(diagnostics, diagnostics.image_size)
    occupied = 0
    total = 16
    grid = np.zeros((4, 4), dtype=bool)
    for result in diagnostics.image_results:
        for x_norm, y_norm in result.coverage_points:
            grid[min(int(y_norm * 4), 3), min(int(x_norm * 4), 3)] = True
    occupied = int(grid.sum())
    return occupied / float(total), heatmap


def _capture_preview_frame(camera_index: int) -> tuple[np.ndarray | None, str | None]:
    capture = cv2.VideoCapture(camera_index)
    if not capture.isOpened():
        capture.release()
        return None, "Camera is not available."
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        return None, "Could not read a frame from the camera."
    return frame, None


def live_calibration_ui(
    focal_length_mm: float,
    mode: str,
    settings: dict[str, Any],
) -> dict[str, Any] | None:
    """Render the live calibration workflow and return a completed calibration result."""

    state = _state()
    st.header("Live Camera Calibration")
    st.info(
        "Use Streamlit camera capture for browser devices, or probe a local USB webcam with OpenCV. LensU tracks frame diversity and unlocks calibration after 15 usable captures."
    )

    devices = list_camera_devices()
    source_mode = st.radio("Capture Source", ["Streamlit Camera", "OpenCV Camera"], horizontal=True)
    auto_capture = st.toggle("Auto-capture diverse views", value=True)
    auto_threshold = st.slider("New-view threshold", min_value=0.02, max_value=0.30, value=0.08, step=0.01)

    if st.button("Clear Live Capture Set"):
        state["captures"] = []
        state["last_signature"] = None
        state["last_rms"] = None
        st.rerun()

    frame: np.ndarray | None = None
    frame_name: str | None = None
    source_error: str | None = None

    if source_mode == "Streamlit Camera":
        captured = st.camera_input("Capture board frame")
        if captured is not None:
            frame = _decode_uploaded(captured)
            frame_name = captured.name or f"camera_{int(time.time())}.jpg"
    else:
        if not devices:
            st.warning("No OpenCV camera devices were detected.")
        else:
            selected_label = st.selectbox("Camera Device", [device["label"] for device in devices])
            selected_device = next(device for device in devices if device["label"] == selected_label)
            if st.button("Refresh Preview"):
                preview, source_error = _capture_preview_frame(int(selected_device["index"]))
                if preview is not None:
                    success, encoded = cv2.imencode(".png", preview)
                    if success:
                        state["preview_bytes"] = encoded.tobytes()
                        state["preview_name"] = f"opencv_{int(time.time())}.png"
            if state.get("preview_bytes"):
                buffer = np.frombuffer(state["preview_bytes"], dtype=np.uint8)
                frame = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
                frame_name = state.get("preview_name") or f"opencv_{int(time.time())}.png"
            if source_error:
                st.warning(source_error)

    if frame is not None:
        found, overlay, signature = _detect_frame(frame, mode, settings)
        caption = "Board detected" if found else "Board not detected"
        st.image(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB), caption=caption, use_container_width=True)

        if found:
            diversity = _signature_distance(signature, state.get("last_signature"))
            st.caption(f"View diversity score: {diversity:.3f}")
            if auto_capture and diversity >= auto_threshold:
                success, encoded = cv2.imencode(".png", frame)
                if success:
                    state["captures"].append({"name": frame_name or f"frame_{len(state['captures'])}.png", "bytes": encoded.tobytes()})
                    state["last_signature"] = signature
                    if len(state["captures"]) >= 3:
                        point, diagnostics = _calibrate_captures(state["captures"], focal_length_mm, mode, settings)
                        state["last_rms"] = point.rms_error if point is not None else None
                    st.success(f"Auto-captured frame {len(state['captures'])}.")
            elif st.button("Capture This Frame", type="primary"):
                success, encoded = cv2.imencode(".png", frame)
                if success:
                    state["captures"].append({"name": frame_name or f"frame_{len(state['captures'])}.png", "bytes": encoded.tobytes()})
                    state["last_signature"] = signature
                    if len(state["captures"]) >= 3:
                        point, diagnostics = _calibrate_captures(state["captures"], focal_length_mm, mode, settings)
                        state["last_rms"] = point.rms_error if point is not None else None
                    st.success(f"Captured frame {len(state['captures'])}.")
        else:
            st.caption("Aim for the board filling different regions and angles of frame.")

    diagnostics = CalibrationDiagnostics(image_size=None)
    point: CalibrationPoint | None = None
    if len(state["captures"]) >= 3:
        point, diagnostics = _calibrate_captures(state["captures"], focal_length_mm, mode, settings)

    coverage_ratio, heatmap = _coverage_metrics(diagnostics)
    stat_cols = st.columns(4)
    stat_cols[0].metric("Captured Frames", str(len(state["captures"])))
    stat_cols[1].metric("Min Required", "15")
    stat_cols[2].metric("Coverage", f"{coverage_ratio * 100:.0f}%")
    stat_cols[3].metric(
        "Live RMS",
        f"{state['last_rms']:.4f}px" if state.get("last_rms") is not None else "Need 3+ frames",
    )

    if heatmap is not None:
        st.image(cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB), caption="Coverage heatmap", use_container_width=True)

    if state["captures"]:
        preview_count = min(6, len(state["captures"]))
        cols = st.columns(preview_count)
        for index, capture in enumerate(state["captures"][-preview_count:]):
            buffer = np.frombuffer(capture["bytes"], dtype=np.uint8)
            image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
            if image is None:
                continue
            with cols[index % preview_count]:
                st.image(cv2.cvtColor(image, cv2.COLOR_BGR2RGB), caption=capture["name"], use_container_width=True)

    if len(state["captures"]) < 15:
        st.caption("Capture at least 15 diverse board views before final calibration.")
        return None
    if point is None:
        st.warning("Not enough valid detections yet to solve calibration.")
        return None

    st.success(f"Ready to calibrate. Current RMS {point.rms_error:.4f}px ({accuracy_grade(point.rms_error)}).")
    if st.button("Calibrate Live Capture Set", type="primary"):
        return {
            "point": point,
            "diagnostics": diagnostics,
            "files": list(state["captures"]),
        }
    return None

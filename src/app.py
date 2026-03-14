"""LensU Streamlit application."""

from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import streamlit as st
import streamlit.components.v1 as components

from board_generator import generate_charuco_pdf, generate_checkerboard_pdf
from batch import BatchFolderResult, batch_calibrate_detailed
from calibration import (
    AnamorphicInfo,
    BreathingPoint,
    CalibrationDiagnostics,
    CalibrationPoint,
    LensProfile,
    NodalOffset,
    accuracy_grade,
    aruco_available,
    calibrate_anamorphic_detailed,
    calibrate_from_charuco_images,
    calibrate_from_images,
    compute_coverage_heatmap,
    detect_charuco,
    detect_checkerboard,
    estimate_nodal_from_parallax,
    generate_barrel_pincushion_visualization,
    generate_distortion_grid,
    lens_profile_from_dict,
    measured_focal_length_mm,
    undistort_image,
)
from lens_library import (
    delete_from_library,
    list_library,
    load_from_library,
    save_to_library,
    search_library,
)
from live_calibration import live_calibration_ui
from report import generate_calibration_report, generate_comparison_report
from ue_export import export_ue_json, export_ue_python_script
from video_extractor import extract_frames_from_video, extract_frames_with_checkerboard


APP_VERSION = "v1.3"
PROFILE_STATE_PATH = Path.home() / ".lensu" / "current_profile.json"

st.set_page_config(page_title="LensU", page_icon="L", layout="wide")


class MemoryUpload:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data


def _load_persisted_profile() -> LensProfile:
    try:
        if PROFILE_STATE_PATH.exists():
            return LensProfile.load_json(PROFILE_STATE_PATH)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        pass
    return LensProfile()


def _save_profile(profile: LensProfile) -> None:
    PROFILE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    profile.save_json(PROFILE_STATE_PATH)


if "profile" not in st.session_state:
    st.session_state.profile = _load_persisted_profile()
if "calibration_runs" not in st.session_state:
    st.session_state.calibration_runs = {}
if "extracted_frames" not in st.session_state:
    st.session_state.extracted_frames = []
if "board_download" not in st.session_state:
    st.session_state.board_download = None
if "export_bundle" not in st.session_state:
    st.session_state.export_bundle = None
if "batch_results" not in st.session_state:
    st.session_state.batch_results = []
if "library_export_bundle" not in st.session_state:
    st.session_state.library_export_bundle = None
if "report_download" not in st.session_state:
    st.session_state.report_download = None
if "comparison_report_download" not in st.session_state:
    st.session_state.comparison_report_download = None


def _run_key(focal_length_mm: float) -> str:
    return f"{focal_length_mm:.3f}"


def _bytes_to_image(file_bytes: bytes) -> np.ndarray | None:
    array = np.frombuffer(file_bytes, dtype=np.uint8)
    return cv2.imdecode(array, cv2.IMREAD_COLOR)


def _detect_preview(
    image: np.ndarray,
    mode: str,
    checkerboard_pattern: tuple[int, int],
    checker_square_mm: float,
    charuco_board_size: tuple[int, int],
    charuco_square_mm: float,
    charuco_marker_mm: float,
    charuco_dictionary: int,
) -> tuple[bool, np.ndarray]:
    if mode == "ChArUco":
        found, _, _, display = detect_charuco(
            image,
            board_size=charuco_board_size,
            square_length_mm=charuco_square_mm,
            marker_length_mm=charuco_marker_mm,
            dictionary=charuco_dictionary,
        )
        return found, display

    found, _, display = detect_checkerboard(image, checkerboard_pattern)
    return found, display


def _anamorphic_payload(point: CalibrationPoint) -> dict[str, float]:
    return {
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


def _scale_image_bytes_horizontally(file_bytes: bytes, scale: float) -> bytes:
    array = np.frombuffer(file_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        return file_bytes
    resized = cv2.resize(
        image,
        (max(1, int(round(image.shape[1] * scale))), image.shape[0]),
        interpolation=cv2.INTER_CUBIC if scale >= 1.0 else cv2.INTER_AREA,
    )
    success, encoded = cv2.imencode(".png", resized)
    if not success:
        return file_bytes
    return encoded.tobytes()


def _calibrate_charuco_anamorphic(
    image_paths: list[Path],
    board_size: tuple[int, int],
    square_length_mm: float,
    marker_length_mm: float,
    dictionary: int,
    focal_length_mm: float,
    squeeze_ratio: float,
    desqueezed: bool,
) -> tuple[CalibrationPoint | None, CalibrationDiagnostics]:
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        if desqueezed:
            desqueezed_paths = image_paths
            squeezed_paths = []
            for index, path in enumerate(image_paths):
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
            squeezed_paths = image_paths
            desqueezed_paths = []
            for index, path in enumerate(image_paths):
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

        desqueezed_point, desqueezed_diagnostics = calibrate_from_charuco_images(
            desqueezed_paths,
            board_size=board_size,
            square_length_mm=square_length_mm,
            marker_length_mm=marker_length_mm,
            dictionary=dictionary,
            focal_length_mm=focal_length_mm,
        )
        squeezed_point, _ = calibrate_from_charuco_images(
            squeezed_paths,
            board_size=board_size,
            square_length_mm=square_length_mm,
            marker_length_mm=marker_length_mm,
            dictionary=dictionary,
            focal_length_mm=focal_length_mm,
        )

    if desqueezed_point is None or squeezed_point is None:
        return None, desqueezed_diagnostics

    desqueezed_point.anamorphic_desqueezed = _anamorphic_payload(desqueezed_point)
    desqueezed_point.anamorphic_squeezed = _anamorphic_payload(squeezed_point)
    desqueezed_point.detection_mode = f"{desqueezed_point.detection_mode} (Anamorphic {squeeze_ratio:.2f}x)"
    return desqueezed_point, desqueezed_diagnostics


def _calibrate_files(
    uploaded_files: list[Any],
    focal_length: float,
    mode: str,
    checkerboard_pattern: tuple[int, int],
    checker_square_mm: float,
    charuco_board_size: tuple[int, int],
    charuco_square_mm: float,
    charuco_marker_mm: float,
    charuco_dictionary: int,
    anamorphic_enabled: bool = False,
    squeeze_ratio: float = 2.0,
    anamorphic_desqueezed: bool = False,
    excluded_names: set[str] | None = None,
) -> tuple[CalibrationPoint | None, CalibrationDiagnostics, list[dict[str, Any]]]:
    excluded_names = excluded_names or set()
    file_payloads: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        image_paths: list[Path] = []
        for uploaded in uploaded_files:
            file_bytes = uploaded.getvalue()
            if uploaded.name in excluded_names:
                file_payloads.append({"name": uploaded.name, "bytes": file_bytes, "excluded": True})
                continue
            path = Path(tmpdir) / uploaded.name
            path.write_bytes(file_bytes)
            image_paths.append(path)
            file_payloads.append({"name": uploaded.name, "bytes": file_bytes, "excluded": False})

        if anamorphic_enabled and mode == "ChArUco":
            point, diagnostics = _calibrate_charuco_anamorphic(
                image_paths=image_paths,
                board_size=charuco_board_size,
                square_length_mm=charuco_square_mm,
                marker_length_mm=charuco_marker_mm,
                dictionary=charuco_dictionary,
                focal_length_mm=focal_length,
                squeeze_ratio=squeeze_ratio,
                desqueezed=anamorphic_desqueezed,
            )
        elif anamorphic_enabled:
            point, diagnostics, _ = calibrate_anamorphic_detailed(
                image_paths,
                pattern_size=checkerboard_pattern,
                square_size_mm=checker_square_mm,
                focal_length_mm=focal_length,
                squeeze_ratio=squeeze_ratio,
                desqueezed=anamorphic_desqueezed,
            )
        elif mode == "ChArUco":
            point, diagnostics = calibrate_from_charuco_images(
                image_paths,
                board_size=charuco_board_size,
                square_length_mm=charuco_square_mm,
                marker_length_mm=charuco_marker_mm,
                dictionary=charuco_dictionary,
                focal_length_mm=focal_length,
            )
        else:
            point, diagnostics = calibrate_from_images(
                image_paths,
                pattern_size=checkerboard_pattern,
                square_size_mm=checker_square_mm,
                focal_length_mm=focal_length,
            )
    return point, diagnostics, file_payloads


def _store_run(
    focal_length: float,
    mode: str,
    point: CalibrationPoint,
    diagnostics: CalibrationDiagnostics,
    files: list[dict[str, Any]],
    settings: dict[str, Any],
) -> None:
    st.session_state.calibration_runs[_run_key(focal_length)] = {
        "focal_length": focal_length,
        "mode": mode,
        "point": point,
        "diagnostics": diagnostics,
        "files": files,
        "settings": settings,
    }


def _render_vega_bar_chart(
    values: list[dict[str, Any]], x_field: str, y_field: str, title: str
) -> None:
    if not values:
        return
    st.vega_lite_chart(
        {
            "data": {"values": values},
            "mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3},
            "encoding": {
                "x": {"field": x_field, "type": "nominal", "sort": None, "title": ""},
                "y": {"field": y_field, "type": "quantitative", "title": title},
                "color": {"value": "#2C7FB8"},
            },
            "height": 260,
        },
        use_container_width=True,
    )


def _render_vega_line_chart(values: list[dict[str, Any]], title: str) -> None:
    st.vega_lite_chart(
        {
            "data": {"values": values},
            "mark": {"type": "line", "point": True},
            "encoding": {
                "x": {
                    "field": "focal_length_mm",
                    "type": "quantitative",
                    "title": "Focal Length (mm)",
                },
                "y": {"field": "value", "type": "quantitative", "title": title},
                "color": {"field": "parameter", "type": "nominal", "title": ""},
            },
            "height": 280,
        },
        use_container_width=True,
    )


def _suggest_zoom_points(min_mm: float, max_mm: float) -> list[float]:
    if max_mm <= min_mm:
        return [round(min_mm, 1)]
    anchors = {min_mm, max_mm, (min_mm + max_mm) / 2.0}
    anchors.add(min_mm + (max_mm - min_mm) * 0.25)
    anchors.add(min_mm + (max_mm - min_mm) * 0.6)
    return sorted({round(value, 1) for value in anchors})


def _load_profile_from_upload(payload: bytes) -> LensProfile:
    data = json.loads(payload)
    return lens_profile_from_dict(data)


def _copy_text_button(label: str, text: str, key: str) -> None:
    if st.button(label, key=key):
        components.html(
            f"<script>navigator.clipboard.writeText({json.dumps(text)});</script>",
            height=0,
        )
        st.success("Copied to clipboard.")


def _format_zip_size(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{num_bytes} B"


def _render_header() -> None:
    st.markdown(
        f"""
        <div style="padding: 0.4rem 0 1rem 0;">
            <div style="font-size: 2rem; font-weight: 700; letter-spacing: 0.02em;">LensU</div>
            <div style="color: #6b7280;">{APP_VERSION} | Free lens calibration for virtual production</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_footer() -> None:
    st.divider()
    st.caption("LensU v1.3 - Free lens calibration for virtual production")


def _render_board_generator_sidebar(dictionary_names: dict[str, int]) -> None:
    st.divider()
    st.header("Print Calibration Board")
    board_type = st.radio(
        "Board PDF Type",
        ["Checkerboard", "ChArUco"],
        horizontal=True,
        disabled=not aruco_available(),
        help="Create a printable PDF board at a fixed real-world size for stage or studio calibration.",
    )
    if board_type == "Checkerboard":
        b1, b2 = st.columns(2)
        with b1:
            board_cols = st.number_input("Cols", value=9, min_value=3, max_value=20, key="board_cb_cols")
        with b2:
            board_rows = st.number_input("Rows", value=6, min_value=3, max_value=20, key="board_cb_rows")
        board_square_mm = st.number_input(
            "Square Size (mm)",
            value=25.0,
            step=1.0,
            format="%.1f",
            key="board_cb_square",
            help="Physical square size on paper. This must match the size used during calibration.",
        )
    else:
        b1, b2 = st.columns(2)
        with b1:
            board_cols = st.number_input("Cols", value=7, min_value=3, max_value=20, key="board_ch_cols")
        with b2:
            board_rows = st.number_input("Rows", value=5, min_value=3, max_value=20, key="board_ch_rows")
        board_square_mm = st.number_input(
            "Square Length (mm)",
            value=30.0,
            step=1.0,
            format="%.1f",
            key="board_ch_square",
            help="Physical ChArUco chessboard square size on the printed page.",
        )
        marker_mm = st.number_input(
            "Marker Length (mm)",
            value=22.5,
            step=0.5,
            format="%.1f",
            key="board_ch_marker",
            help="Black ArUco marker size inside each square. This must stay smaller than the square length.",
        )
        dictionary_name = st.selectbox("Dictionary", list(dictionary_names.keys()), key="board_dict")

    page_size = st.selectbox("Page Size", ["A4", "A3", "A2", "A1"], index=1)
    include_metadata = st.toggle("Include Metadata", value=True)

    if st.button("Generate Board PDF", use_container_width=True):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / f"{board_type.lower()}_{page_size.lower()}.pdf"
                if board_type == "Checkerboard":
                    generate_checkerboard_pdf(
                        pattern_size=(int(board_cols), int(board_rows)),
                        square_size_mm=float(board_square_mm),
                        page_size=page_size,
                        output_path=output_path,
                        include_metadata=include_metadata,
                    )
                else:
                    generate_charuco_pdf(
                        board_size=(int(board_cols), int(board_rows)),
                        square_length_mm=float(board_square_mm),
                        marker_length_mm=float(marker_mm),
                        dictionary=int(dictionary_names[dictionary_name]),
                        page_size=page_size,
                        output_path=output_path,
                        include_metadata=include_metadata,
                    )
                st.session_state.board_download = {
                    "name": output_path.name,
                    "bytes": output_path.read_bytes(),
                }
        except Exception as exc:
            st.error(f"Board generation failed: {exc}")

    board_download = st.session_state.board_download
    if board_download:
        st.download_button(
            "Download Board PDF",
            data=board_download["bytes"],
            file_name=board_download["name"],
            mime="application/pdf",
            use_container_width=True,
        )


def _render_calibration_visuals(run: dict[str, Any]) -> None:
    point: CalibrationPoint = run["point"]
    diagnostics: CalibrationDiagnostics = run["diagnostics"]
    settings = run["settings"]
    files = [entry for entry in run["files"] if not entry.get("excluded")]
    image_size = diagnostics.image_size
    if not image_size or not files:
        return

    sample_image = None
    for entry in files:
        sample_image = _bytes_to_image(entry["bytes"])
        if sample_image is not None:
            break
    if sample_image is None:
        return

    undistorted = undistort_image(sample_image, point, image_size)
    grid = generate_distortion_grid(point, image_size)
    barrel_map = generate_barrel_pincushion_visualization(point, image_size)
    coverage = compute_coverage_heatmap(diagnostics, image_size)

    st.subheader("Distortion Preview")
    col1, col2 = st.columns(2)
    with col1:
        st.image(cv2.cvtColor(sample_image, cv2.COLOR_BGR2RGB), caption="Original", use_container_width=True)
    with col2:
        st.image(cv2.cvtColor(undistorted, cv2.COLOR_BGR2RGB), caption="Undistorted", use_container_width=True)

    col3, col4 = st.columns(2)
    with col3:
        st.image(cv2.cvtColor(grid, cv2.COLOR_BGR2RGB), caption="Distortion Grid", use_container_width=True)
    with col4:
        label = "Barrel" if point.k1 < 0 else "Pincushion" if point.k1 > 0 else "Neutral"
        st.image(
            cv2.cvtColor(barrel_map, cv2.COLOR_BGR2RGB),
            caption=f"Barrel/Pincushion Visualization ({label})",
            use_container_width=True,
        )

    st.subheader("Accuracy Reporting")
    stats = st.columns(4)
    stats[0].metric(
        "RMS Error",
        f"{point.rms_error:.4f} px",
        help="Root-mean-square reprojection error. Lower means the fitted lens model matches detections more closely.",
    )
    stats[1].metric("Grade", accuracy_grade(point.rms_error))
    stats[2].metric("Used Images", str(point.num_images))
    stats[3].metric("Detection Mode", point.detection_mode)

    if point.anamorphic_desqueezed and point.anamorphic_squeezed:
        st.subheader("Anamorphic Parameters")
        st.dataframe(
            [
                {
                    "space": "Desqueezed",
                    "k1": round(point.anamorphic_desqueezed["k1"], 6),
                    "k2": round(point.anamorphic_desqueezed["k2"], 6),
                    "p1": round(point.anamorphic_desqueezed["p1"], 6),
                    "p2": round(point.anamorphic_desqueezed["p2"], 6),
                    "k3": round(point.anamorphic_desqueezed["k3"], 6),
                    "cx": round(point.anamorphic_desqueezed["cx"], 4),
                    "cy": round(point.anamorphic_desqueezed["cy"], 4),
                },
                {
                    "space": "Squeezed",
                    "k1": round(point.anamorphic_squeezed["k1"], 6),
                    "k2": round(point.anamorphic_squeezed["k2"], 6),
                    "p1": round(point.anamorphic_squeezed["p1"], 6),
                    "p2": round(point.anamorphic_squeezed["p2"], 6),
                    "k3": round(point.anamorphic_squeezed["k3"], 6),
                    "cx": round(point.anamorphic_squeezed["cx"], 4),
                    "cy": round(point.anamorphic_squeezed["cy"], 4),
                },
            ],
            use_container_width=True,
        )

    bar_values = [
        {"image_name": item.image_name, "error_px": item.reprojection_error}
        for item in diagnostics.image_results
        if item.reprojection_error is not None
    ]
    _render_vega_bar_chart(bar_values, "image_name", "error_px", "Per-image reprojection error (px)")
    st.image(cv2.cvtColor(coverage, cv2.COLOR_BGR2RGB), caption="Coverage Heatmap", use_container_width=True)

    outliers = diagnostics.outlier_names
    if outliers:
        st.warning("Outliers flagged (>2x mean reprojection error): " + ", ".join(outliers))
        selected = st.multiselect(
            "Exclude images and re-calibrate",
            [entry["name"] for entry in files],
            default=outliers,
            key=f"exclude_{_run_key(point.focal_length_mm)}",
            help="Drop bad detections or motion-blurred frames and rerun calibration with the remaining set.",
        )
        if st.button("Re-calibrate Without Selected Images", key=f"recal_{_run_key(point.focal_length_mm)}"):
            remaining = [entry for entry in files if entry["name"] not in set(selected)]
            if len(remaining) < 3:
                st.error("Need at least 3 valid images after exclusion.")
            else:
                point_new, diagnostics_new, files_new = _calibrate_files(
                    [MemoryUpload(entry["name"], entry["bytes"]) for entry in remaining],
                    focal_length=point.focal_length_mm,
                    mode=run["mode"],
                    checkerboard_pattern=settings["checkerboard_pattern"],
                    checker_square_mm=settings["checker_square_mm"],
                    charuco_board_size=settings["charuco_board_size"],
                    charuco_square_mm=settings["charuco_square_mm"],
                    charuco_marker_mm=settings["charuco_marker_mm"],
                    charuco_dictionary=settings["charuco_dictionary"],
                    anamorphic_enabled=settings["anamorphic_enabled"],
                    squeeze_ratio=settings["squeeze_ratio"],
                    anamorphic_desqueezed=settings["anamorphic_desqueezed"],
                )
                if point_new is None:
                    st.error("Re-calibration failed with the remaining images.")
                else:
                    st.session_state.profile.add_calibration(point_new)
                    st.session_state.profile.image_width = diagnostics_new.image_size[0]
                    st.session_state.profile.image_height = diagnostics_new.image_size[1]
                    _store_run(point_new.focal_length_mm, run["mode"], point_new, diagnostics_new, files_new, settings)
                    _save_profile(st.session_state.profile)
                    st.rerun()

    st.subheader("Detection Results")
    columns = st.columns(min(4, max(1, len(files))))
    for index, entry in enumerate(files):
        image = _bytes_to_image(entry["bytes"])
        if image is None:
            continue
        found, preview = _detect_preview(
            image,
            run["mode"],
            settings["checkerboard_pattern"],
            settings["checker_square_mm"],
            settings["charuco_board_size"],
            settings["charuco_square_mm"],
            settings["charuco_marker_mm"],
            settings["charuco_dictionary"],
        )
        with columns[index % len(columns)]:
            st.image(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB), caption=entry["name"], use_container_width=True)
            st.caption("OK" if found else "FAILED")


def _compare_profiles(current: LensProfile, other: LensProfile) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current_points = {round(point.focal_length_mm, 3): point for point in current.calibration_points}
    other_points = {round(point.focal_length_mm, 3): point for point in other.calibration_points}
    for focal in sorted(set(current_points) | set(other_points)):
        point_a = current_points.get(focal)
        point_b = other_points.get(focal)
        rows.append(
            {
                "type": "Calibration",
                "focal_length_mm": focal,
                "k1_diff": (point_b.k1 - point_a.k1) if point_a and point_b else None,
                "k2_diff": (point_b.k2 - point_a.k2) if point_a and point_b else None,
                "p1_diff": (point_b.p1 - point_a.p1) if point_a and point_b else None,
                "p2_diff": (point_b.p2 - point_a.p2) if point_a and point_b else None,
                "k3_diff": (point_b.k3 - point_a.k3) if point_a and point_b else None,
            }
        )

    current_offsets = {round(offset.focal_length_mm, 3): offset for offset in current.nodal_offsets}
    other_offsets = {round(offset.focal_length_mm, 3): offset for offset in other.nodal_offsets}
    for focal in sorted(set(current_offsets) | set(other_offsets)):
        offset_a = current_offsets.get(focal)
        offset_b = other_offsets.get(focal)
        rows.append(
            {
                "type": "Nodal",
                "focal_length_mm": focal,
                "offset_x_diff": (offset_b.offset_x - offset_a.offset_x) if offset_a and offset_b else None,
                "offset_y_diff": (offset_b.offset_y - offset_a.offset_y) if offset_a and offset_b else None,
                "offset_z_diff": (offset_b.offset_z - offset_a.offset_z) if offset_a and offset_b else None,
                "rotation_x_diff": (offset_b.rotation_x - offset_a.rotation_x) if offset_a and offset_b else None,
                "rotation_y_diff": (offset_b.rotation_y - offset_a.rotation_y) if offset_a and offset_b else None,
                "rotation_z_diff": (offset_b.rotation_z - offset_a.rotation_z) if offset_a and offset_b else None,
            }
        )

    current_breathing = {
        round(profile.nominal_focal_length_mm, 3): profile for profile in current.breathing_profiles
    }
    other_breathing = {
        round(profile.nominal_focal_length_mm, 3): profile for profile in other.breathing_profiles
    }
    for focal in sorted(set(current_breathing) | set(other_breathing)):
        profile_a = current_breathing.get(focal)
        profile_b = other_breathing.get(focal)
        rows.append(
            {
                "type": "Breathing",
                "focal_length_mm": focal,
                "ratio_diff": (
                    profile_b.breathing_ratio() - profile_a.breathing_ratio()
                    if profile_a and profile_b
                    else None
                ),
                "points_a": len(profile_a.points) if profile_a else 0,
                "points_b": len(profile_b.points) if profile_b else 0,
            }
        )
    return rows


def _focus_display_label(distance_m: float) -> str:
    if distance_m >= 999.0:
        return "Infinity"
    return f"{distance_m:.2f} m"


def _render_breathing_chart(profile) -> None:
    chart_values: list[dict[str, Any]] = []
    for point in profile.points:
        chart_values.append(
            {
                "focus_distance_m": point.focus_distance_m,
                "measured_focal_length_mm": point.measured_focal_length_mm,
                "focus_label": _focus_display_label(point.focus_distance_m),
            }
        )
    if not chart_values:
        return
    st.vega_lite_chart(
        {
            "data": {"values": chart_values},
            "mark": {"type": "line", "point": True},
            "encoding": {
                "x": {"field": "focus_distance_m", "type": "quantitative", "title": "Focus Distance (m)"},
                "y": {
                    "field": "measured_focal_length_mm",
                    "type": "quantitative",
                    "title": "Measured Focal Length (mm)",
                },
                "tooltip": [
                    {"field": "focus_label", "type": "nominal", "title": "Focus"},
                    {"field": "measured_focal_length_mm", "type": "quantitative", "title": "Measured mm"},
                ],
            },
            "height": 280,
        },
        use_container_width=True,
    )


def _prepare_export_bundle(profile: LensProfile, data_mode: str, include_stmaps: bool) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        stmap_dir = tmp_path / "stmaps"
        package_stmaps = include_stmaps or data_mode == "STMap"
        json_path = export_ue_json(
            profile,
            tmp_path,
            data_mode=data_mode,
            stmap_directory=stmap_dir,
            include_stmaps=package_stmaps,
        )
        script_path = export_ue_python_script(profile, json_path.name, tmp_path, data_mode=data_mode)

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(json_path, json_path.name)
            archive.write(script_path, script_path.name)
            if package_stmaps and stmap_dir.exists():
                for stmap_file in sorted(stmap_dir.iterdir()):
                    archive.write(stmap_file, f"stmaps/{stmap_file.name}")
        zip_bytes = zip_buffer.getvalue()
        return {
            "name": f"LensU_{profile.lens_name.replace(' ', '_')}_{data_mode}.zip",
            "bytes": zip_bytes,
            "zip_size": len(zip_bytes),
            "json_text": json_path.read_text(encoding="utf-8"),
            "script_text": script_path.read_text(encoding="utf-8"),
        }


def _batch_table_rows(results: list[BatchFolderResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in results:
        rows.append(
            {
                "focal_length_mm": round(item.focal_length_mm, 3),
                "folder": item.folder_name,
                "status": "OK" if item.success else "FAILED",
                "used_images": item.used_count,
                "total_images": item.source_count,
                "rms_error_px": round(item.rms_error, 5) if item.success else None,
                "error": item.error,
            }
        )
    return rows


def _library_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "total_profiles": 0,
            "families": 0,
            "date_min": "-",
            "date_max": "-",
        }
    names = [row.get("name", "Unknown") for row in rows]
    unique_names = len(set(names))
    dates = [row.get("date", "") for row in rows if row.get("date")]
    return {
        "total_profiles": len(rows),
        "families": unique_names,
        "date_min": min(dates) if dates else "-",
        "date_max": max(dates) if dates else "-",
    }


def main() -> None:
    profile: LensProfile = st.session_state.profile
    _render_header()

    with st.sidebar:
        st.header("Lens Setup")
        profile.lens_name = st.text_input(
            "Lens Name",
            value=profile.lens_name,
            help="Profile name used in JSON and Unreal export file names.",
        )

        st.subheader("Sensor")
        col1, col2 = st.columns(2)
        with col1:
            profile.sensor_width_mm = st.number_input(
                "Width (mm)",
                value=profile.sensor_width_mm,
                step=0.1,
                format="%.1f",
                help="Physical sensor width. This affects focal normalization in the export data.",
            )
        with col2:
            profile.sensor_height_mm = st.number_input(
                "Height (mm)",
                value=profile.sensor_height_mm,
                step=0.1,
                format="%.1f",
                help="Physical sensor height. Match the camera gate or recording crop used for calibration.",
            )

        sensor_presets = {
            "Full Frame (36x24)": (36.0, 24.0),
            "APS-C Canon (22.3x14.9)": (22.3, 14.9),
            "APS-C Sony/Nikon (23.5x15.6)": (23.5, 15.6),
            "Micro 4/3 (17.3x13)": (17.3, 13.0),
            "Super 35 (24.89x18.66)": (24.89, 18.66),
        }
        preset = st.selectbox("Sensor Preset", ["Custom"] + list(sensor_presets.keys()))
        if preset != "Custom":
            profile.sensor_width_mm, profile.sensor_height_mm = sensor_presets[preset]

        st.subheader("Detection")
        detection_mode = st.radio(
            "Board Type",
            ["Checkerboard", "ChArUco"],
            index=0,
            disabled=not aruco_available(),
            help="Checkerboard is simplest. ChArUco is more robust when the board is partially occluded or near frame edges.",
        )
        if not aruco_available():
            st.caption("This OpenCV build does not expose `cv2.aruco`; ChArUco mode is unavailable.")

        st.subheader("Checkerboard")
        cb1, cb2 = st.columns(2)
        with cb1:
            pattern_cols = st.number_input(
                "Inner Corners (cols)",
                value=9,
                min_value=3,
                max_value=20,
                help="Number of detectable inner checkerboard corners horizontally.",
            )
        with cb2:
            pattern_rows = st.number_input(
                "Inner Corners (rows)",
                value=6,
                min_value=3,
                max_value=20,
                help="Number of detectable inner checkerboard corners vertically.",
            )
        checker_square_mm = st.number_input(
            "Square Size (mm)",
            value=25.0,
            step=1.0,
            format="%.1f",
            help="Real checkerboard square size. This sets the calibration board scale.",
        )

        st.subheader("ChArUco")
        ch1, ch2 = st.columns(2)
        with ch1:
            charuco_cols = st.number_input("Squares (cols)", value=7, min_value=3, max_value=20)
        with ch2:
            charuco_rows = st.number_input("Squares (rows)", value=5, min_value=3, max_value=20)
        charuco_square_mm = st.number_input(
            "Square Length (mm)",
            value=30.0,
            step=1.0,
            format="%.1f",
            help="Outer square size for ChArUco calibration boards.",
        )
        charuco_marker_mm = st.number_input(
            "Marker Length (mm)",
            value=22.5,
            step=0.5,
            format="%.1f",
            help="Inner ArUco marker size. Keep this slightly smaller than the square length.",
        )
        dictionary_names = {
            "DICT_4X4_50": cv2.aruco.DICT_4X4_50 if aruco_available() else 0,
            "DICT_5X5_100": cv2.aruco.DICT_5X5_100 if aruco_available() else 0,
            "DICT_6X6_250": cv2.aruco.DICT_6X6_250 if aruco_available() else 0,
        }
        charuco_dictionary_name = st.selectbox(
            "Dictionary",
            list(dictionary_names.keys()),
            index=2 if aruco_available() else 0,
        )

        st.subheader("Zoom Lens Workflow")
        zoom_mode = st.toggle(
            "Zoom Lens Mode",
            value=False,
            help="Track multiple focal lengths in one profile and use the suggested calibration anchors across the zoom range.",
        )
        zoom_min = zoom_max = 0.0
        suggested_points: list[float] = []
        if zoom_mode:
            z1, z2 = st.columns(2)
            with z1:
                zoom_min = st.number_input("Zoom Range Min (mm)", value=24.0, step=1.0, format="%.1f")
            with z2:
                zoom_max = st.number_input("Zoom Range Max (mm)", value=70.0, step=1.0, format="%.1f")
            suggested_points = _suggest_zoom_points(float(zoom_min), float(zoom_max))
            st.caption("Suggested calibration points: " + ", ".join(f"{value:.1f}" for value in suggested_points))

        st.subheader("Anamorphic")
        anamorphic_enabled = st.toggle(
            "Enable Anamorphic Lens Mode",
            value=profile.anamorphic is not None,
            help="Use separate squeezed and desqueezed calibration views for anamorphic glass.",
        )
        squeeze_ratio = 2.0
        anamorphic_desqueezed = False
        if anamorphic_enabled:
            ratio_choice = st.selectbox("Squeeze Ratio", ["2.0x", "1.5x", "1.33x", "Custom"], index=0)
            if ratio_choice == "Custom":
                squeeze_ratio = st.number_input(
                    "Custom Squeeze Ratio",
                    value=profile.anamorphic.squeeze_ratio if profile.anamorphic is not None else 2.0,
                    min_value=1.01,
                    max_value=4.0,
                    step=0.01,
                    format="%.2f",
                )
            else:
                squeeze_ratio = float(ratio_choice.replace("x", ""))
            anamorphic_desqueezed = st.checkbox(
                "Images are desqueezed",
                value=profile.anamorphic.desqueeze_applied if profile.anamorphic is not None else False,
                help="Enable this when the source images were already horizontally expanded before import.",
            )
            profile.anamorphic = AnamorphicInfo(
                squeeze_ratio=float(squeeze_ratio),
                desqueeze_applied=bool(anamorphic_desqueezed),
            )
        else:
            profile.anamorphic = None

        _render_board_generator_sidebar(dictionary_names)

    settings = {
        "checkerboard_pattern": (int(pattern_cols), int(pattern_rows)),
        "checker_square_mm": float(checker_square_mm),
        "charuco_board_size": (int(charuco_cols), int(charuco_rows)),
        "charuco_square_mm": float(charuco_square_mm),
        "charuco_marker_mm": float(charuco_marker_mm),
        "charuco_dictionary": int(dictionary_names[charuco_dictionary_name]),
        "anamorphic_enabled": anamorphic_enabled,
        "squeeze_ratio": float(squeeze_ratio),
        "anamorphic_desqueezed": bool(anamorphic_desqueezed),
    }

    tab_calibrate, tab_live, tab_video, tab_batch, tab_breathing, tab_nodal, tab_profile, tab_library, tab_export = st.tabs(
        [
            "Distortion Calibration",
            "Live Calibration",
            "Video Calibration",
            "Batch Calibration",
            "Lens Breathing",
            "Nodal Offset",
            "Lens Profile",
            "Lens Library",
            "UE Export",
        ]
    )

    with tab_calibrate:
        st.header("Distortion Calibration")
        st.info(
            "Calibrate at one focal length per run. ChArUco is more tolerant of partial occlusion; checkerboard remains the simplest setup."
        )

        if zoom_mode and suggested_points:
            completed = {round(point.focal_length_mm, 1) for point in profile.calibration_points}
            st.caption(
                "Workflow: "
                + "  ".join(
                    f"{value:.1f}mm [{'done' if round(value, 1) in completed else 'pending'}]"
                    for value in suggested_points
                )
            )
            focal_length = st.selectbox("Calibration Point", suggested_points, key="zoom_focal_select")
        else:
            focal_length = st.number_input(
                "Focal Length (mm)",
                value=50.0,
                step=1.0,
                format="%.1f",
                key="cal_focal",
                help="Actual focal length used for this image set. LensU stores one distortion fit per focal length.",
            )

        uploaded_files = st.file_uploader(
            "Upload calibration images",
            type=["jpg", "jpeg", "png", "bmp", "tiff"],
            accept_multiple_files=True,
            key=f"cal_images_{_run_key(float(focal_length))}_{detection_mode}",
            help="Use a spread of angles, distances, and frame coverage for a stable calibration.",
        )

        if uploaded_files and st.button("Run Calibration", type="primary"):
            with st.spinner("Running calibration..."):
                point, diagnostics, files = _calibrate_files(
                    uploaded_files,
                    focal_length=float(focal_length),
                    mode=detection_mode,
                    checkerboard_pattern=settings["checkerboard_pattern"],
                    checker_square_mm=settings["checker_square_mm"],
                    charuco_board_size=settings["charuco_board_size"],
                    charuco_square_mm=settings["charuco_square_mm"],
                    charuco_marker_mm=settings["charuco_marker_mm"],
                    charuco_dictionary=settings["charuco_dictionary"],
                    anamorphic_enabled=settings["anamorphic_enabled"],
                    squeeze_ratio=settings["squeeze_ratio"],
                    anamorphic_desqueezed=settings["anamorphic_desqueezed"],
                )
            if point is None:
                used_images = sum(1 for item in diagnostics.image_results if item.used)
                st.error(
                    f"Calibration failed. Only {used_images}/{len(diagnostics.image_results)} images produced usable detections."
                )
            else:
                profile.add_calibration(point)
                if diagnostics.image_size:
                    profile.image_width, profile.image_height = diagnostics.image_size
                _store_run(float(focal_length), detection_mode, point, diagnostics, files, settings)
                _save_profile(profile)
                st.success(
                    f"Calibration complete. RMS: {point.rms_error:.4f}px, grade: {accuracy_grade(point.rms_error)}."
                )

        current_run = st.session_state.calibration_runs.get(_run_key(float(focal_length)))
        if current_run:
            _render_calibration_visuals(current_run)

    with tab_live:
        live_focal_length = st.number_input(
            "Live Calibration Focal Length (mm)",
            value=50.0,
            step=1.0,
            format="%.1f",
            key="live_focal",
            help="Focal length represented by the live capture set.",
        )
        live_result = live_calibration_ui(float(live_focal_length), detection_mode, settings)
        if live_result:
            point = live_result["point"]
            diagnostics = live_result["diagnostics"]
            files = live_result["files"]
            profile.add_calibration(point)
            if diagnostics.image_size:
                profile.image_width, profile.image_height = diagnostics.image_size
            _store_run(float(live_focal_length), detection_mode, point, diagnostics, files, settings)
            _save_profile(profile)
            st.success(f"Live calibration complete. RMS: {point.rms_error:.4f}px.")

    with tab_video:
        st.header("Video Calibration")
        st.info(
            "Extract usable frames from a stage recording, review detection overlays, then calibrate directly from the extracted set."
        )
        video_focal_length = st.number_input(
            "Video Focal Length (mm)",
            value=50.0,
            step=1.0,
            format="%.1f",
            key="video_focal",
            help="Focal length represented by the uploaded video clip.",
        )
        video_file = st.file_uploader(
            "Upload calibration video",
            type=["mp4", "mov", "avi", "mkv", "mxf"],
            key="video_upload",
            help="Common H.264, H.265, ProRes, and similar formats should work if your local OpenCV build can decode them.",
        )
        extraction_mode = st.radio(
            "Extraction Mode",
            ["Regular interval", "Smart (checkerboard-aware)"],
            horizontal=True,
            help="Regular interval samples frames by time. Smart mode keeps only diverse checkerboard views.",
        )
        if extraction_mode == "Regular interval":
            interval_seconds = st.number_input(
                "Interval (seconds)",
                value=1.0,
                min_value=0.1,
                step=0.1,
                format="%.1f",
                help="Extract one frame every N seconds from the recording.",
            )
            max_video_frames = st.slider("Max Frames", min_value=5, max_value=100, value=30)
            blur_threshold = st.number_input(
                "Blur Threshold",
                value=100.0,
                min_value=0.0,
                step=10.0,
                format="%.1f",
                help="Laplacian variance threshold. Higher values reject more soft or motion-blurred frames.",
            )
        else:
            max_video_frames = st.slider("Max Frames", min_value=5, max_value=60, value=20)
            min_coverage = st.slider(
                "Minimum Coverage",
                min_value=0.05,
                max_value=0.9,
                value=0.3,
                step=0.05,
                help="Minimum image fraction covered by the checkerboard bounding area.",
            )
            min_angle_diff = st.slider(
                "Minimum Angle Difference",
                min_value=1.0,
                max_value=45.0,
                value=10.0,
                step=1.0,
                help="Reject near-duplicate board orientations and keep more viewpoint diversity.",
            )

        if video_file is not None and st.button("Extract Frames", type="primary"):
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir)
                suffix = Path(video_file.name).suffix or ".mp4"
                video_path = tmp_path / f"uploaded_video{suffix}"
                video_path.write_bytes(video_file.getvalue())
                output_dir = tmp_path / "frames"
                try:
                    if extraction_mode == "Regular interval":
                        extracted = extract_frames_from_video(
                            video_path=video_path,
                            output_dir=output_dir,
                            interval_seconds=float(interval_seconds),
                            max_frames=int(max_video_frames),
                            min_blur_threshold=float(blur_threshold),
                        )
                    else:
                        extracted = extract_frames_with_checkerboard(
                            video_path=video_path,
                            output_dir=output_dir,
                            pattern_size=settings["checkerboard_pattern"],
                            max_frames=int(max_video_frames),
                            min_coverage=float(min_coverage),
                            min_angle_diff=float(min_angle_diff),
                        )
                except Exception as exc:
                    extracted = []
                    st.error(f"Video extraction failed: {exc}")

                st.session_state.extracted_frames = [
                    {"name": path.name, "bytes": path.read_bytes()} for path in extracted if path.exists()
                ]

            if st.session_state.extracted_frames:
                st.success(f"Extracted {len(st.session_state.extracted_frames)} frame(s).")
            else:
                st.warning("No usable frames were extracted. Try lowering the blur threshold or coverage requirements.")

        extracted_frames: list[dict[str, Any]] = st.session_state.extracted_frames
        if extracted_frames:
            st.subheader("Extracted Frames")
            preview_columns = st.columns(min(4, len(extracted_frames)))
            for index, entry in enumerate(extracted_frames):
                image = _bytes_to_image(entry["bytes"])
                if image is None:
                    continue
                found, preview = _detect_preview(
                    image,
                    detection_mode,
                    settings["checkerboard_pattern"],
                    settings["checker_square_mm"],
                    settings["charuco_board_size"],
                    settings["charuco_square_mm"],
                    settings["charuco_marker_mm"],
                    settings["charuco_dictionary"],
                )
                with preview_columns[index % len(preview_columns)]:
                    st.image(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB), caption=entry["name"], use_container_width=True)
                    st.caption("Detected" if found else "No board detected")

            if st.button("Calibrate From Extracted Frames", type="primary"):
                uploads = [MemoryUpload(entry["name"], entry["bytes"]) for entry in extracted_frames]
                with st.spinner("Calibrating from extracted frames..."):
                    point, diagnostics, files = _calibrate_files(
                        uploads,
                        focal_length=float(video_focal_length),
                        mode=detection_mode,
                        checkerboard_pattern=settings["checkerboard_pattern"],
                        checker_square_mm=settings["checker_square_mm"],
                        charuco_board_size=settings["charuco_board_size"],
                        charuco_square_mm=settings["charuco_square_mm"],
                        charuco_marker_mm=settings["charuco_marker_mm"],
                        charuco_dictionary=settings["charuco_dictionary"],
                        anamorphic_enabled=settings["anamorphic_enabled"],
                        squeeze_ratio=settings["squeeze_ratio"],
                        anamorphic_desqueezed=settings["anamorphic_desqueezed"],
                    )
                if point is None:
                    used_images = sum(1 for item in diagnostics.image_results if item.used)
                    st.error(
                        f"Calibration failed. Only {used_images}/{len(diagnostics.image_results)} extracted frames were usable."
                    )
                else:
                    profile.add_calibration(point)
                    if diagnostics.image_size:
                        profile.image_width, profile.image_height = diagnostics.image_size
                    _store_run(float(video_focal_length), detection_mode, point, diagnostics, files, settings)
                    _save_profile(profile)
                    st.success(f"Calibration complete from video frames. RMS: {point.rms_error:.4f}px.")

            current_video_run = st.session_state.calibration_runs.get(_run_key(float(video_focal_length)))
            if current_video_run:
                _render_calibration_visuals(current_video_run)

    with tab_batch:
        st.header("Batch Calibration")
        st.info(
            "Calibrate multiple focal lengths from subfolders such as 24mm, 35mm, and 50mm inside one base directory."
        )
        if settings["anamorphic_enabled"] and detection_mode == "ChArUco":
            st.warning("Batch anamorphic calibration currently uses checkerboard mode only. Switch board type to Checkerboard for anamorphic batch runs.")
        batch_base_dir = st.text_input(
            "Batch Folder Path",
            value="",
            help="Example: D:/calibration_shots. Each subfolder should contain one focal length image set.",
        ).strip()
        st.text_area(
            "Folder Structure Notes (optional)",
            value="",
            height=90,
            help="Optional notes only. LensU calibrates from the directory path above.",
        )
        if st.button("Run Batch Calibration", type="primary"):
            if not batch_base_dir:
                st.error("Enter a valid base folder path.")
            else:
                base_dir = Path(batch_base_dir)
                progress = st.progress(0)
                status = st.empty()

                def _progress(current: int, total: int, result: BatchFolderResult) -> None:
                    ratio = current / max(total, 1)
                    progress.progress(ratio)
                    state = "OK" if result.success else "FAILED"
                    status.caption(
                        f"{current}/{total} | {result.focal_length_mm:.1f}mm | {state} | "
                        f"used {result.used_count}/{result.source_count}"
                    )

                try:
                    batch_pattern = (
                        settings["charuco_board_size"]
                        if detection_mode == "ChArUco"
                        else settings["checkerboard_pattern"]
                    )
                    batch_square = (
                        settings["charuco_square_mm"]
                        if detection_mode == "ChArUco"
                        else settings["checker_square_mm"]
                    )
                    batch_profile, results = batch_calibrate_detailed(
                        base_dir=base_dir,
                        pattern_size=batch_pattern,
                        square_size_mm=batch_square,
                        detection_mode=detection_mode.lower(),
                        sensor_width_mm=profile.sensor_width_mm,
                        sensor_height_mm=profile.sensor_height_mm,
                        progress_callback=_progress,
                        anamorphic_enabled=settings["anamorphic_enabled"] and detection_mode.lower() != "charuco",
                        squeeze_ratio=settings["squeeze_ratio"],
                        anamorphic_desqueezed=settings["anamorphic_desqueezed"],
                    )
                    if settings["anamorphic_enabled"]:
                        profile.anamorphic = AnamorphicInfo(
                            squeeze_ratio=settings["squeeze_ratio"],
                            desqueeze_applied=settings["anamorphic_desqueezed"],
                        )
                    st.session_state.batch_results = results
                    for batch_point in batch_profile.calibration_points:
                        profile.add_calibration(batch_point)
                    if batch_profile.calibration_points:
                        profile.image_width = batch_profile.image_width
                        profile.image_height = batch_profile.image_height
                        _save_profile(profile)
                    success_count = sum(1 for item in results if item.success)
                    st.success(
                        f"Batch complete. {success_count}/{len(results)} focal folders calibrated successfully."
                    )
                except Exception as exc:
                    st.error(f"Batch calibration failed: {exc}")

        batch_rows = _batch_table_rows(st.session_state.batch_results)
        if batch_rows:
            st.subheader("Batch Summary")
            st.dataframe(batch_rows, use_container_width=True)

    with tab_breathing:
        st.header("Lens Breathing")
        st.info(
            "Measure effective focal length at multiple focus distances for the same nominal focal length. LensU stores the curve and exports it as focus-indexed focal data for Unreal."
        )
        breathing_nominal = st.number_input(
            "Nominal Focal Length (mm)",
            value=50.0,
            step=1.0,
            format="%.1f",
            key="breathing_nominal",
        )
        focus_presets = {"Infinity": 1000.0, "3m": 3.0, "1.5m": 1.5, "1m": 1.0, "0.5m": 0.5}
        selected_focus_label = st.selectbox("Focus Distance", list(focus_presets.keys()), key="breathing_focus")
        selected_focus_m = float(focus_presets[selected_focus_label])
        breathing_uploads = st.file_uploader(
            "Upload breathing calibration images",
            type=["jpg", "jpeg", "png", "bmp", "tiff"],
            accept_multiple_files=True,
            key="breathing_images",
            help="Capture a focused checkerboard/ChArUco set at this focus distance and solve effective focal length from it.",
        )

        if breathing_uploads and st.button("Measure Breathing Point", type="primary"):
            with st.spinner("Measuring effective focal length..."):
                point, diagnostics, _ = _calibrate_files(
                    breathing_uploads,
                    focal_length=float(breathing_nominal),
                    mode=detection_mode,
                    checkerboard_pattern=settings["checkerboard_pattern"],
                    checker_square_mm=settings["checker_square_mm"],
                    charuco_board_size=settings["charuco_board_size"],
                    charuco_square_mm=settings["charuco_square_mm"],
                    charuco_marker_mm=settings["charuco_marker_mm"],
                    charuco_dictionary=settings["charuco_dictionary"],
                    anamorphic_enabled=settings["anamorphic_enabled"],
                    squeeze_ratio=settings["squeeze_ratio"],
                    anamorphic_desqueezed=settings["anamorphic_desqueezed"],
                )
            if point is None:
                st.error("Breathing measurement failed. Capture more diverse, sharper board views.")
            else:
                measured_mm = measured_focal_length_mm(point, profile.sensor_width_mm, diagnostics.image_size[0])
                profile.add_breathing_point(
                    BreathingPoint(
                        focus_distance_m=selected_focus_m,
                        measured_focal_length_mm=measured_mm,
                        nominal_focal_length_mm=float(breathing_nominal),
                    )
                )
                _save_profile(profile)
                st.success(
                    f"Saved breathing point at {_focus_display_label(selected_focus_m)}: {measured_mm:.2f} mm effective focal length."
                )

        breathing_profile = next(
            (
                item
                for item in profile.breathing_profiles
                if abs(item.nominal_focal_length_mm - float(breathing_nominal)) <= 0.1
            ),
            None,
        )
        if breathing_profile and breathing_profile.points:
            metric_cols = st.columns(3)
            metric_cols[0].metric("Samples", str(len(breathing_profile.points)))
            metric_cols[1].metric("Breathing Ratio", f"{breathing_profile.breathing_ratio():.2f}%")
            metric_cols[2].metric(
                "Range",
                f"{min(point.measured_focal_length_mm for point in breathing_profile.points):.2f}-{max(point.measured_focal_length_mm for point in breathing_profile.points):.2f} mm",
            )
            _render_breathing_chart(breathing_profile)
            st.dataframe(
                [
                    {
                        "focus": _focus_display_label(point.focus_distance_m),
                        "focus_distance_m": point.focus_distance_m,
                        "measured_focal_length_mm": round(point.measured_focal_length_mm, 3),
                    }
                    for point in breathing_profile.points
                ],
                use_container_width=True,
            )
        else:
            st.caption("No breathing samples yet. Start with Infinity, 3m, 1.5m, 1m, and 0.5m.")

    with tab_nodal:
        st.header("Nodal Offset")
        st.info(
            "Save manual nodal offsets, or run a guided parallax test from five uploaded photos for a rough entrance-pupil estimate."
        )

        nodal_focal = st.number_input(
            "Focal Length (mm)",
            value=50.0,
            step=1.0,
            format="%.1f",
            key="nodal_focal",
            help="Focal length associated with this nodal or entrance-pupil offset measurement.",
        )
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Location Offset (mm)")
            nx = st.number_input(
                "X",
                value=0.0,
                step=0.1,
                format="%.2f",
                key="nx",
                help="Lateral offset in millimeters.",
            )
            ny = st.number_input(
                "Y",
                value=0.0,
                step=0.1,
                format="%.2f",
                key="ny",
                help="Vertical offset in millimeters.",
            )
            nz = st.number_input(
                "Z",
                value=0.0,
                step=0.1,
                format="%.2f",
                key="nz",
                help="Depth offset in millimeters from the tracked camera reference point.",
            )
        with col2:
            st.subheader("Rotation Offset (deg)")
            rx = st.number_input(
                "Pitch",
                value=0.0,
                step=0.1,
                format="%.2f",
                key="rx",
                help="Tilt adjustment in degrees.",
            )
            ry = st.number_input(
                "Yaw",
                value=0.0,
                step=0.1,
                format="%.2f",
                key="ry",
                help="Pan adjustment in degrees.",
            )
            rz = st.number_input(
                "Roll",
                value=0.0,
                step=0.1,
                format="%.2f",
                key="rz",
                help="Roll adjustment in degrees.",
            )

        if st.button("Save Nodal Offset", type="primary"):
            profile.add_nodal_offset(
                NodalOffset(
                    focal_length_mm=float(nodal_focal),
                    offset_x=float(nx),
                    offset_y=float(ny),
                    offset_z=float(nz),
                    rotation_x=float(rx),
                    rotation_y=float(ry),
                    rotation_z=float(rz),
                )
            )
            _save_profile(profile)
            st.success(f"Nodal offset saved for {nodal_focal:.1f}mm.")

        st.divider()
        st.subheader("Guided Nodal Offset Test")
        st.markdown(
            """
1. Mount the camera on a tripod head with calibrated distance markings.
2. Place two vertical objects at different distances, ideally near `1m` and `3m`.
3. Rotate the camera and watch the parallax between the near and far object.
4. Capture frames at `-10°`, `-5°`, `0°`, `+5°`, and `+10°`.
5. Upload all five images below.
6. LensU estimates the entrance pupil shift and confidence from the parallax trend.
            """
        )
        near_distance = st.number_input("Near Object Distance (m)", value=1.0, step=0.1, format="%.1f")
        far_distance = st.number_input("Far Object Distance (m)", value=3.0, step=0.1, format="%.1f")
        nodal_test_uploads = st.file_uploader(
            "Upload 5 parallax test photos",
            type=["jpg", "jpeg", "png", "bmp", "tiff"],
            accept_multiple_files=True,
            key="guided_nodal_uploads",
        )

        if nodal_test_uploads:
            st.caption("Expected order: -10°, -5°, 0°, +5°, +10°.")
        if nodal_test_uploads and st.button("Estimate From Parallax", type="primary"):
            if len(nodal_test_uploads) != 5:
                st.error("Upload exactly 5 images for the guided nodal test.")
            else:
                images = [_bytes_to_image(upload.getvalue()) for upload in nodal_test_uploads]
                if any(image is None for image in images):
                    st.error("At least one uploaded nodal-test image could not be decoded.")
                else:
                    estimate = estimate_nodal_from_parallax(
                        images=[image for image in images if image is not None],
                        rotation_angles_deg=[-10.0, -5.0, 0.0, 5.0, 10.0],
                        near_object_distance_m=float(near_distance),
                        far_object_distance_m=float(far_distance),
                    )
                    estimate.focal_length_mm = float(nodal_focal)
                    profile.add_nodal_offset(estimate)
                    _save_profile(profile)
                    st.success(
                        f"Estimated nodal Z offset: {estimate.offset_z:.2f} mm | confidence {estimate.confidence:.2f}"
                    )

    with tab_profile:
        st.header("Lens Profile")
        if profile.anamorphic is not None:
            st.info(
                f"Anamorphic profile: {profile.anamorphic.squeeze_ratio:.2f}x | "
                f"{'desqueezed input' if profile.anamorphic.desqueeze_applied else 'raw squeezed input'}"
            )
        if not profile.calibration_points and not profile.nodal_offsets and not profile.breathing_profiles:
            st.warning("No calibration data recorded yet.")
        else:
            if profile.calibration_points:
                st.subheader("Calibration Points")
                for point in profile.calibration_points:
                    with st.expander(
                        f"{point.focal_length_mm:.1f}mm | {point.detection_mode} | RMS {point.rms_error:.4f}px"
                    ):
                        cols = st.columns(4)
                        cols[0].metric(
                            "K1",
                            f"{point.k1:.6f}",
                            help="Primary radial distortion term. Often dominates barrel or pincushion shape.",
                        )
                        cols[1].metric(
                            "K2",
                            f"{point.k2:.6f}",
                            help="Secondary radial distortion term that refines edge behavior.",
                        )
                        cols[2].metric(
                            "P1/P2",
                            f"{point.p1:.6f} / {point.p2:.6f}",
                            help="Tangential distortion terms, usually caused by lens element decentering.",
                        )
                        cols[3].metric("Center", f"{point.cx:.4f}, {point.cy:.4f}")
                        st.caption(
                            f"Focal length in pixels: fx={point.fx:.2f}, fy={point.fy:.2f}. Images used: {point.num_images}."
                        )
                        if point.anamorphic_desqueezed and point.anamorphic_squeezed:
                            st.dataframe(
                                [
                                    {
                                        "space": "Desqueezed",
                                        "k1": round(point.anamorphic_desqueezed["k1"], 6),
                                        "k2": round(point.anamorphic_desqueezed["k2"], 6),
                                        "p1": round(point.anamorphic_desqueezed["p1"], 6),
                                        "p2": round(point.anamorphic_desqueezed["p2"], 6),
                                        "k3": round(point.anamorphic_desqueezed["k3"], 6),
                                    },
                                    {
                                        "space": "Squeezed",
                                        "k1": round(point.anamorphic_squeezed["k1"], 6),
                                        "k2": round(point.anamorphic_squeezed["k2"], 6),
                                        "p1": round(point.anamorphic_squeezed["p1"], 6),
                                        "p2": round(point.anamorphic_squeezed["p2"], 6),
                                        "k3": round(point.anamorphic_squeezed["k3"], 6),
                                    },
                                ],
                                use_container_width=True,
                            )

            if len(profile.calibration_points) >= 2:
                st.subheader("Zoom Interpolation")
                series: list[dict[str, Any]] = []
                for point in profile.calibration_points:
                    series.append({"focal_length_mm": point.focal_length_mm, "parameter": "k1", "value": point.k1})
                    series.append({"focal_length_mm": point.focal_length_mm, "parameter": "k2", "value": point.k2})
                _render_vega_line_chart(series, "Distortion coefficient")
                st.caption("Use at least 8-10 zoom points for production interpolation quality on cinema zooms.")

                summary_cols = st.columns(3)
                summary_cols[0].metric(
                    "Calibrated Range",
                    f"{profile.calibration_points[0].focal_length_mm:.1f}-{profile.calibration_points[-1].focal_length_mm:.1f}mm",
                )
                summary_cols[1].metric("Points", str(len(profile.calibration_points)))
                summary_cols[2].metric(
                    "Best Grade",
                    min((accuracy_grade(p.rms_error) for p in profile.calibration_points), default="N/A"),
                )

            st.subheader("Nodal Offsets")
            if profile.nodal_offsets:
                for offset in profile.nodal_offsets:
                    st.write(
                        f"{offset.focal_length_mm:.1f}mm | "
                        f"Loc ({offset.offset_x:.2f}, {offset.offset_y:.2f}, {offset.offset_z:.2f}) mm | "
                        f"Rot ({offset.rotation_x:.2f}, {offset.rotation_y:.2f}, {offset.rotation_z:.2f}) deg | "
                        f"Confidence {offset.confidence:.2f} | {offset.method}"
                    )
            else:
                st.caption("No nodal offsets recorded.")

            st.subheader("Breathing Profiles")
            if profile.breathing_profiles:
                for breathing_profile in profile.breathing_profiles:
                    with st.expander(
                        f"{breathing_profile.nominal_focal_length_mm:.1f}mm | {breathing_profile.breathing_ratio():.2f}% breathing"
                    ):
                        _render_breathing_chart(breathing_profile)
                        st.dataframe(
                            [
                                {
                                    "focus": _focus_display_label(point.focus_distance_m),
                                    "focus_distance_m": point.focus_distance_m,
                                    "measured_focal_length_mm": round(point.measured_focal_length_mm, 3),
                                }
                                for point in breathing_profile.points
                            ],
                            use_container_width=True,
                        )
            else:
                st.caption("No breathing profiles recorded.")

            st.divider()
            st.subheader("Profile Comparison")
            uploaded_compare = st.file_uploader(
                "Upload second profile JSON",
                type=["json"],
                key="compare_profile",
                help="Compare this calibration against another day or another body setup to spot drift.",
            )
            if uploaded_compare is not None:
                other_profile = _load_profile_from_upload(uploaded_compare.getvalue().decode("utf-8"))
                comparison_rows = _compare_profiles(profile, other_profile)
                st.dataframe(comparison_rows, use_container_width=True)
                if st.button("Generate Comparison Report", key="generate_comparison_report"):
                    with tempfile.TemporaryDirectory() as tmpdir:
                        report_path = generate_comparison_report(
                            profile,
                            other_profile,
                            Path(tmpdir) / f"{profile.lens_name.replace(' ', '_')}_comparison_report.pdf",
                        )
                        st.session_state.comparison_report_download = {
                            "name": report_path.name,
                            "bytes": report_path.read_bytes(),
                        }
            comparison_report = st.session_state.comparison_report_download
            if comparison_report:
                st.download_button(
                    "Download Comparison Report (PDF)",
                    data=comparison_report["bytes"],
                    file_name=comparison_report["name"],
                    mime="application/pdf",
                )

            st.divider()
            profile_json = profile.to_dict()
            st.download_button(
                "Download Profile (JSON)",
                data=json.dumps(profile_json, indent=2),
                file_name=f"{profile.lens_name.replace(' ', '_')}_profile.json",
                mime="application/json",
            )
            uploaded_profile = st.file_uploader("Load Profile", type=["json"], key="load_profile")
            if uploaded_profile is not None:
                st.session_state.profile = _load_profile_from_upload(uploaded_profile.getvalue().decode("utf-8"))
                _save_profile(st.session_state.profile)
                st.success(f"Loaded profile: {st.session_state.profile.lens_name}")
                st.rerun()

    with tab_library:
        st.header("Lens Library")
        st.info("Browse, load, delete, and export profiles stored in your local LensU library.")

        c1, c2 = st.columns(2)
        with c1:
            library_search_name = st.text_input("Search Lens Name", value="")
        with c2:
            library_search_sensor = st.text_input("Filter Sensor", value="")

        library_rows = search_library(lens_name=library_search_name, sensor_type=library_search_sensor)
        stats = _library_stats(list_library())
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Total Profiles", str(stats["total_profiles"]))
        s2.metric("Lens Families", str(stats["families"]))
        s3.metric("Date Range Start", stats["date_min"])
        s4.metric("Date Range End", stats["date_max"])

        if st.button("Save Current Profile To Library", key="save_current_profile_library"):
            saved_path = save_to_library(profile)
            st.success(f"Saved: {saved_path.name}")
            st.rerun()

        if not library_rows:
            st.caption("No profiles found in library with current filters.")
        else:
            st.dataframe(library_rows, use_container_width=True)
            selected_filename = st.selectbox(
                "Select Library Profile",
                [row["filename"] for row in library_rows],
                key="library_selected_filename",
            )
            selected_row = next((row for row in library_rows if row["filename"] == selected_filename), None)

            action_cols = st.columns(3)
            with action_cols[0]:
                if st.button("Load Into Session", type="primary", key="library_load_button"):
                    st.session_state.profile = load_from_library(selected_filename)
                    _save_profile(st.session_state.profile)
                    st.success(f"Loaded: {selected_filename}")
                    st.rerun()
            with action_cols[1]:
                if st.button("Delete Profile", key="library_delete_button"):
                    if delete_from_library(selected_filename):
                        st.success(f"Deleted: {selected_filename}")
                        st.rerun()
                    else:
                        st.error("Could not delete selected library profile.")
            with action_cols[2]:
                export_mode = st.selectbox(
                    "Export Data Mode",
                    ["Parameters", "STMap"],
                    key="library_export_mode",
                )
                include_stmaps = export_mode == "STMap"
                if st.button("Export Selected To UE ZIP", key="library_export_button"):
                    selected_profile = load_from_library(selected_filename)
                    st.session_state.library_export_bundle = _prepare_export_bundle(
                        selected_profile, export_mode, include_stmaps
                    )

            library_bundle = st.session_state.library_export_bundle
            if library_bundle:
                st.download_button(
                    "Download Selected UE Export",
                    data=library_bundle["bytes"],
                    file_name=library_bundle["name"],
                    mime="application/zip",
                    key="library_export_download",
                )

            if selected_row is not None:
                st.caption(
                    f"Selected: {selected_row['name']} | Sensor {selected_row['sensor']} | "
                    f"Focals {selected_row['focal_lengths']} | RMS avg {selected_row['rms_avg']:.4f}"
                )

    with tab_export:
        st.header("Export to Unreal Engine")
        if not profile.calibration_points:
            st.warning("No calibration data available. Run at least one distortion calibration first.")
        else:
            data_mode = st.radio(
                "UE Data Mode",
                ["Parameters", "STMap"],
                horizontal=True,
                help="Parameters exports Brown-Conrady coefficients. STMap exports texture maps and JSON entries for texture-driven distortion.",
            )
            include_stmaps = st.checkbox(
                "Include STMaps in ZIP",
                value=data_mode == "STMap",
                help="Package generated STMap textures inside the ZIP even when exporting parameter-driven data.",
            )
            st.caption("STMaps are useful for texture-driven workflows or for inspection alongside the parameter fit.")

            if st.button("Generate UE Export Package", type="primary"):
                st.session_state.export_bundle = _prepare_export_bundle(profile, data_mode, include_stmaps)
            if st.button("Generate Report"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    report_path = generate_calibration_report(
                        profile,
                        Path(tmpdir) / f"{profile.lens_name.replace(' ', '_')}_calibration_report.pdf",
                        include_charts=True,
                    )
                    st.session_state.report_download = {
                        "name": report_path.name,
                        "bytes": report_path.read_bytes(),
                    }

            bundle = st.session_state.export_bundle
            if bundle:
                st.metric("ZIP Size", _format_zip_size(bundle["zip_size"]))
                st.download_button(
                    "Download UE Export Package (.zip)",
                    data=bundle["bytes"],
                    file_name=bundle["name"],
                    mime="application/zip",
                )

                st.subheader("Generated Files Preview")
                with st.expander("Calibration JSON"):
                    st.json(json.loads(bundle["json_text"]))
                with st.expander("UE Python Script"):
                    st.code(bundle["script_text"], language="python")
                    _copy_text_button("Copy to clipboard", bundle["script_text"], key="copy_ue_script")
            report_bundle = st.session_state.report_download
            if report_bundle:
                st.download_button(
                    "Download Calibration Report (PDF)",
                    data=report_bundle["bytes"],
                    file_name=report_bundle["name"],
                    mime="application/pdf",
                )

            st.divider()
            st.markdown(
                """
1. Enable the **Camera Calibration** and **Python Editor Script Plugin** plugins in Unreal Engine.
2. Unzip the export package into a convenient project-local folder.
3. Run the generated Python script through **Tools > Execute Python Script**.
4. The script creates `/Game/LensU/<LensName>` and imports STMaps when `STMap` mode is selected.
                """
            )

    _save_profile(profile)
    _render_footer()


if __name__ == "__main__":
    main()

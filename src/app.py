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

from calibration import (
    CalibrationDiagnostics,
    CalibrationPoint,
    LensProfile,
    NodalOffset,
    accuracy_grade,
    aruco_available,
    calibrate_from_charuco_images,
    calibrate_from_images,
    compute_coverage_heatmap,
    detect_charuco,
    detect_checkerboard,
    generate_barrel_pincushion_visualization,
    generate_distortion_grid,
    undistort_image,
)
from ue_export import export_ue_json, export_ue_python_script


st.set_page_config(page_title="LensU", page_icon="📷", layout="wide")


if "profile" not in st.session_state:
    st.session_state.profile = LensProfile()
if "calibration_runs" not in st.session_state:
    st.session_state.calibration_runs = {}


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

        if mode == "ChArUco":
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


def _render_vega_bar_chart(values: list[dict[str, Any]], x_field: str, y_field: str, title: str) -> None:
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
                "x": {"field": "focal_length_mm", "type": "quantitative", "title": "Focal Length (mm)"},
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
    loaded = LensProfile(
        lens_name=data.get("lens_name", "Unknown"),
        sensor_width_mm=data.get("sensor_width_mm", 36.0),
        sensor_height_mm=data.get("sensor_height_mm", 24.0),
        image_width=data.get("image_width", 1920),
        image_height=data.get("image_height", 1080),
    )
    for point in data.get("calibration_points", []):
        loaded.calibration_points.append(CalibrationPoint(**point))
    for offset in data.get("nodal_offsets", []):
        loaded.nodal_offsets.append(NodalOffset(**offset))
    return loaded


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
    stats[0].metric("RMS Error", f"{point.rms_error:.4f} px")
    stats[1].metric("Grade", accuracy_grade(point.rms_error))
    stats[2].metric("Used Images", str(point.num_images))
    stats[3].metric("Detection Mode", point.detection_mode)

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
        default_selection = outliers
        selected = st.multiselect(
            "Exclude images and re-calibrate",
            [entry["name"] for entry in files],
            default=default_selection,
            key=f"exclude_{_run_key(point.focal_length_mm)}",
        )
        if st.button("Re-calibrate Without Selected Images", key=f"recal_{_run_key(point.focal_length_mm)}"):
            remaining = [entry for entry in files if entry["name"] not in set(selected)]
            if len(remaining) < 3:
                st.error("Need at least 3 valid images after exclusion.")
            else:
                class MemoryUpload:
                    def __init__(self, name: str, data: bytes):
                        self.name = name
                        self._data = data

                    def getvalue(self) -> bytes:
                        return self._data

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
                )
                if point_new is None:
                    st.error("Re-calibration failed with the remaining images.")
                else:
                    st.session_state.profile.add_calibration(point_new)
                    st.session_state.profile.image_width = diagnostics_new.image_size[0]
                    st.session_state.profile.image_height = diagnostics_new.image_size[1]
                    _store_run(point_new.focal_length_mm, run["mode"], point_new, diagnostics_new, files_new, settings)
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


def main() -> None:
    st.title("LensU")
    st.caption("Cinema lens calibration and Unreal Engine LensFile export")

    with st.sidebar:
        st.header("Lens Setup")
        profile: LensProfile = st.session_state.profile
        profile.lens_name = st.text_input("Lens Name", value=profile.lens_name)

        st.subheader("Sensor")
        col1, col2 = st.columns(2)
        with col1:
            profile.sensor_width_mm = st.number_input("Width (mm)", value=profile.sensor_width_mm, step=0.1, format="%.1f")
        with col2:
            profile.sensor_height_mm = st.number_input("Height (mm)", value=profile.sensor_height_mm, step=0.1, format="%.1f")

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
        )
        if not aruco_available():
            st.caption("This OpenCV build does not expose `cv2.aruco`; ChArUco mode is unavailable.")

        st.subheader("Checkerboard")
        cb1, cb2 = st.columns(2)
        with cb1:
            pattern_cols = st.number_input("Inner Corners (cols)", value=9, min_value=3, max_value=20)
        with cb2:
            pattern_rows = st.number_input("Inner Corners (rows)", value=6, min_value=3, max_value=20)
        checker_square_mm = st.number_input("Square Size (mm)", value=25.0, step=1.0, format="%.1f")

        st.subheader("ChArUco")
        ch1, ch2 = st.columns(2)
        with ch1:
            charuco_cols = st.number_input("Squares (cols)", value=7, min_value=3, max_value=20)
        with ch2:
            charuco_rows = st.number_input("Squares (rows)", value=5, min_value=3, max_value=20)
        charuco_square_mm = st.number_input("Square Length (mm)", value=30.0, step=1.0, format="%.1f")
        charuco_marker_mm = st.number_input("Marker Length (mm)", value=22.5, step=0.5, format="%.1f")
        dictionary_names = {
            "DICT_4X4_50": cv2.aruco.DICT_4X4_50 if aruco_available() else 0,
            "DICT_5X5_100": cv2.aruco.DICT_5X5_100 if aruco_available() else 0,
            "DICT_6X6_250": cv2.aruco.DICT_6X6_250 if aruco_available() else 0,
        }
        charuco_dictionary_name = st.selectbox("Dictionary", list(dictionary_names.keys()), index=2 if aruco_available() else 0)

        st.subheader("Zoom Lens Workflow")
        zoom_mode = st.toggle("Zoom Lens Mode", value=False)
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

    tab_calibrate, tab_nodal, tab_profile, tab_export = st.tabs(
        ["Distortion Calibration", "Nodal Offset", "Lens Profile", "UE Export"]
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
                    f"{value:.1f}mm [{'done' if round(value, 1) in completed else 'pending'}]" for value in suggested_points
                )
            )
            focal_length = st.selectbox("Calibration Point", suggested_points, key="zoom_focal_select")
        else:
            focal_length = st.number_input("Focal Length (mm)", value=50.0, step=1.0, format="%.1f", key="cal_focal")

        uploaded_files = st.file_uploader(
            "Upload calibration images",
            type=["jpg", "jpeg", "png", "bmp", "tiff"],
            accept_multiple_files=True,
            key=f"cal_images_{_run_key(float(focal_length))}_{detection_mode}",
        )

        settings = {
            "checkerboard_pattern": (int(pattern_cols), int(pattern_rows)),
            "checker_square_mm": float(checker_square_mm),
            "charuco_board_size": (int(charuco_cols), int(charuco_rows)),
            "charuco_square_mm": float(charuco_square_mm),
            "charuco_marker_mm": float(charuco_marker_mm),
            "charuco_dictionary": int(dictionary_names[charuco_dictionary_name]),
        }

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
                )
            if point is None:
                used_images = sum(1 for item in diagnostics.image_results if item.used)
                st.error(f"Calibration failed. Only {used_images}/{len(diagnostics.image_results)} images produced usable detections.")
            else:
                profile.add_calibration(point)
                if diagnostics.image_size:
                    profile.image_width, profile.image_height = diagnostics.image_size
                _store_run(float(focal_length), detection_mode, point, diagnostics, files, settings)
                st.success(f"Calibration complete. RMS: {point.rms_error:.4f}px, grade: {accuracy_grade(point.rms_error)}.")

        current_run = st.session_state.calibration_runs.get(_run_key(float(focal_length)))
        if current_run:
            _render_calibration_visuals(current_run)

    with tab_nodal:
        st.header("Nodal Offset")
        st.info("Measure these manually if you have a nodal rail or entrance-pupil test. LensU stores them per focal length for UE import.")

        nodal_focal = st.number_input("Focal Length (mm)", value=50.0, step=1.0, format="%.1f", key="nodal_focal")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Location Offset (mm)")
            nx = st.number_input("X", value=0.0, step=0.1, format="%.2f", key="nx")
            ny = st.number_input("Y", value=0.0, step=0.1, format="%.2f", key="ny")
            nz = st.number_input("Z", value=0.0, step=0.1, format="%.2f", key="nz")
        with col2:
            st.subheader("Rotation Offset (deg)")
            rx = st.number_input("Pitch", value=0.0, step=0.1, format="%.2f", key="rx")
            ry = st.number_input("Yaw", value=0.0, step=0.1, format="%.2f", key="ry")
            rz = st.number_input("Roll", value=0.0, step=0.1, format="%.2f", key="rz")

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
            st.success(f"Nodal offset saved for {nodal_focal:.1f}mm.")

    with tab_profile:
        st.header("Lens Profile")
        if not profile.calibration_points and not profile.nodal_offsets:
            st.warning("No calibration data recorded yet.")
        else:
            if profile.calibration_points:
                st.subheader("Calibration Points")
                for point in profile.calibration_points:
                    with st.expander(f"{point.focal_length_mm:.1f}mm | {point.detection_mode} | RMS {point.rms_error:.4f}px"):
                        cols = st.columns(4)
                        cols[0].metric("K1", f"{point.k1:.6f}")
                        cols[1].metric("K2", f"{point.k2:.6f}")
                        cols[2].metric("P1/P2", f"{point.p1:.6f} / {point.p2:.6f}")
                        cols[3].metric("Center", f"{point.cx:.4f}, {point.cy:.4f}")
                        st.caption(f"Focal length in pixels: fx={point.fx:.2f}, fy={point.fy:.2f}. Images used: {point.num_images}.")

            if len(profile.calibration_points) >= 2:
                st.subheader("Zoom Interpolation")
                series: list[dict[str, Any]] = []
                for point in profile.calibration_points:
                    series.append({"focal_length_mm": point.focal_length_mm, "parameter": "k1", "value": point.k1})
                    series.append({"focal_length_mm": point.focal_length_mm, "parameter": "k2", "value": point.k2})
                _render_vega_line_chart(series, "Distortion coefficient")
                st.caption("Use at least 8-10 zoom points for production interpolation quality on cinema zooms.")

                summary_cols = st.columns(3)
                summary_cols[0].metric("Calibrated Range", f"{profile.calibration_points[0].focal_length_mm:.1f}-{profile.calibration_points[-1].focal_length_mm:.1f}mm")
                summary_cols[1].metric("Points", str(len(profile.calibration_points)))
                summary_cols[2].metric("Best Grade", min((accuracy_grade(p.rms_error) for p in profile.calibration_points), default="N/A"))

            st.subheader("Nodal Offsets")
            if profile.nodal_offsets:
                for offset in profile.nodal_offsets:
                    st.write(
                        f"{offset.focal_length_mm:.1f}mm | "
                        f"Loc ({offset.offset_x:.2f}, {offset.offset_y:.2f}, {offset.offset_z:.2f}) mm | "
                        f"Rot ({offset.rotation_x:.2f}, {offset.rotation_y:.2f}, {offset.rotation_z:.2f}) deg"
                    )
            else:
                st.caption("No nodal offsets recorded.")

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
                st.success(f"Loaded profile: {st.session_state.profile.lens_name}")
                st.rerun()

    with tab_export:
        st.header("Export to Unreal Engine")
        if not profile.calibration_points:
            st.warning("No calibration data available. Run at least one distortion calibration first.")
        else:
            data_mode = st.radio("UE Data Mode", ["Parameters", "STMap"], horizontal=True)
            st.caption("Parameters exports Brown-Conrady coefficients. STMap also packages float maps and imports them as textures in UE.")

            if st.button("Generate UE Export Package", type="primary"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)
                    stmap_dir = tmp_path / "stmaps"
                    json_path = export_ue_json(profile, tmp_path, data_mode=data_mode, stmap_directory=stmap_dir)
                    script_path = export_ue_python_script(profile, json_path.name, tmp_path, data_mode=data_mode)

                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                        archive.write(json_path, json_path.name)
                        archive.write(script_path, script_path.name)
                        if stmap_dir.exists():
                            for stmap_file in stmap_dir.iterdir():
                                archive.write(stmap_file, stmap_file.name)
                    zip_buffer.seek(0)

                    st.download_button(
                        "Download UE Export Package (.zip)",
                        data=zip_buffer,
                        file_name=f"LensU_{profile.lens_name.replace(' ', '_')}_{data_mode}.zip",
                        mime="application/zip",
                    )

                    st.subheader("Generated Files Preview")
                    with st.expander("Calibration JSON"):
                        st.json(json.loads(json_path.read_text(encoding="utf-8")))
                    with st.expander("UE Python Script"):
                        st.code(script_path.read_text(encoding="utf-8"), language="python")

            st.divider()
            st.markdown(
                """
1. Enable the **Camera Calibration** and **Python Editor Script Plugin** plugins in Unreal Engine.
2. Unzip the export package into a convenient project-local folder.
3. Run the generated Python script through **Tools > Execute Python Script**.
4. The script creates `/Game/LensU/<LensName>` and imports STMaps when `STMap` mode is selected.
                """
            )


if __name__ == "__main__":
    main()

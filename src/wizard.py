"""Beginner-friendly calibration wizard UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import streamlit as st

try:
    from .board_generator import generate_charuco_pdf, generate_checkerboard_pdf
    from .calibration import (
        AnamorphicInfo,
        BreathingPoint,
        CalibrationDiagnostics,
        CalibrationImageResult,
        LensProfile,
        NodalOffset,
        accuracy_grade,
        calibrate_anamorphic_detailed,
        calibrate_fisheye,
        calibrate_from_charuco_images,
        calibrate_from_images,
        compute_coverage_heatmap,
        detect_charuco,
        detect_checkerboard,
        estimate_nodal_from_parallax,
        measured_focal_length_mm,
    )
    from .lens_library import save_to_library
    from .temp_paths import lensu_tempdir
except ImportError:
    from board_generator import generate_charuco_pdf, generate_checkerboard_pdf
    from calibration import (
        AnamorphicInfo,
        BreathingPoint,
        CalibrationDiagnostics,
        CalibrationImageResult,
        LensProfile,
        NodalOffset,
        accuracy_grade,
        calibrate_anamorphic_detailed,
        calibrate_fisheye,
        calibrate_from_charuco_images,
        calibrate_from_images,
        compute_coverage_heatmap,
        detect_charuco,
        detect_checkerboard,
        estimate_nodal_from_parallax,
        measured_focal_length_mm,
    )
    from lens_library import save_to_library
    from temp_paths import lensu_tempdir


def _context() -> dict[str, Any]:
    return st.session_state.get("wizard_context", {})


def _state() -> dict[str, Any]:
    if "wizard_state" not in st.session_state:
        st.session_state.wizard_state = {
            "step": 0,
            "uploads": [],
            "last_point": None,
            "last_diagnostics": None,
            "last_bundle": None,
            "board_download": None,
        }
    return st.session_state.wizard_state


def _profile() -> LensProfile:
    profile = _context().get("profile")
    if profile is None:
        raise RuntimeError("Wizard context is not configured.")
    return profile


def _settings() -> dict[str, Any]:
    return dict(_context().get("settings", {}))


def _dictionary_names() -> dict[str, int]:
    return dict(_context().get("dictionary_names", {}))


def _save_session() -> None:
    save_profile = _context().get("save_profile")
    save_rig = _context().get("save_rig")
    rig = _context().get("rig")
    profile = _profile()
    if callable(save_profile):
        save_profile(profile)
    if callable(save_rig) and rig is not None:
        save_rig(rig)


def _decode_upload(uploaded: Any) -> np.ndarray | None:
    return cv2.imdecode(np.frombuffer(uploaded.getvalue(), dtype=np.uint8), cv2.IMREAD_COLOR)


def _preview_detection(image: np.ndarray, mode: str, settings: dict[str, Any]) -> tuple[bool, np.ndarray]:
    if mode == "ChArUco":
        found, _, _, overlay = detect_charuco(
            image,
            board_size=settings["charuco_board_size"],
            square_length_mm=settings["charuco_square_mm"],
            marker_length_mm=settings["charuco_marker_mm"],
            dictionary=settings["charuco_dictionary"],
        )
        return found, overlay
    found, _, overlay = detect_checkerboard(image, settings["checkerboard_pattern"])
    return found, overlay


def _calibrate_uploads(
    uploads: list[Any],
    focal_length_mm: float,
    mode: str,
    settings: dict[str, Any],
    excluded_names: set[str] | None = None,
) -> tuple[Any, CalibrationDiagnostics]:
    excluded_names = excluded_names or set()
    with lensu_tempdir() as tmpdir:
        image_paths: list[Path] = []
        image_size: tuple[int, int] | None = None
        for uploaded in uploads:
            if uploaded.name in excluded_names:
                continue
            path = Path(tmpdir) / uploaded.name
            payload = uploaded.getvalue()
            path.write_bytes(payload)
            if image_size is None:
                image = cv2.imdecode(np.frombuffer(payload, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is not None:
                    image_size = (image.shape[1], image.shape[0])
            image_paths.append(path)

        if settings.get("fisheye_enabled"):
            point, used_flags = calibrate_fisheye(
                image_paths,
                pattern_size=settings["checkerboard_pattern"],
                square_size_mm=settings["checker_square_mm"],
                focal_length_mm=focal_length_mm,
            )
            diagnostics = CalibrationDiagnostics(image_size=image_size)
            diagnostics.image_results = [
                CalibrationImageResult(
                    image_name=path.name,
                    used=used,
                    detection_mode="Fisheye Checkerboard",
                )
                for path, used in zip(image_paths, used_flags)
            ]
            return point, diagnostics
        if settings.get("anamorphic_enabled") and mode != "ChArUco":
            point, diagnostics, _ = calibrate_anamorphic_detailed(
                image_paths,
                pattern_size=settings["checkerboard_pattern"],
                square_size_mm=settings["checker_square_mm"],
                focal_length_mm=focal_length_mm,
                squeeze_ratio=settings["squeeze_ratio"],
                desqueezed=settings["anamorphic_desqueezed"],
            )
            return point, diagnostics
        if mode == "ChArUco":
            return calibrate_from_charuco_images(
                image_paths,
                board_size=settings["charuco_board_size"],
                square_length_mm=settings["charuco_square_mm"],
                marker_length_mm=settings["charuco_marker_mm"],
                dictionary=settings["charuco_dictionary"],
                focal_length_mm=focal_length_mm,
            )
        return calibrate_from_images(
            image_paths,
            pattern_size=settings["checkerboard_pattern"],
            square_size_mm=settings["checker_square_mm"],
            focal_length_mm=focal_length_mm,
        )


def calibration_wizard_ui():
    """Streamlit multi-step wizard for complete lens calibration."""

    state = _state()
    profile = _profile()
    settings = _settings()
    dictionary_names = _dictionary_names()
    steps = [
        "1. Welcome",
        "2. Lens Info",
        "3. Calibration Board",
        "4. Capture Images",
        "5. Calibrate",
        "6. Nodal Offset",
        "7. Zoom Points",
        "8. Export",
        "9. Save",
    ]

    st.header("Calibration Wizard")
    st.caption("A guided path from lens setup to export.")
    selected_step = st.radio("Wizard Step", steps, index=int(state["step"]), horizontal=True)
    state["step"] = steps.index(selected_step)

    if state["step"] == 0:
        st.info("LensU helps you build a lens profile for Unreal Engine and Nuke.")
        st.markdown(
            """
You will need:
1. A printed checkerboard or ChArUco board.
2. 10-15 sharp photos per focal length.
3. Sensor size and focal length information.
4. Optional parallax photos for nodal offsets.
            """
        )
        return

    if state["step"] == 1:
        col1, col2 = st.columns(2)
        with col1:
            profile.lens_name = st.text_input("Lens Name", value=profile.lens_name, key="wizard_lens_name")
            profile.lens_type = st.selectbox(
                "Lens Type",
                ["prime", "zoom", "anamorphic"],
                index=max(["prime", "zoom", "anamorphic"].index(profile.lens_type or "prime"), 0),
                key="wizard_lens_type",
            )
        with col2:
            profile.sensor_width_mm = st.number_input(
                "Sensor Width (mm)", value=float(profile.sensor_width_mm), step=0.1, format="%.2f"
            )
            profile.sensor_height_mm = st.number_input(
                "Sensor Height (mm)", value=float(profile.sensor_height_mm), step=0.1, format="%.2f"
            )
        if profile.lens_type == "anamorphic":
            squeeze_ratio = st.number_input(
                "Squeeze Ratio", min_value=1.1, value=float(settings.get("squeeze_ratio", 2.0)), step=0.1
            )
            profile.anamorphic = AnamorphicInfo(
                squeeze_ratio=float(squeeze_ratio),
                desqueeze_applied=bool(settings.get("anamorphic_desqueezed", False)),
            )
        _save_session()
        st.success("Lens information updated.")
        return

    if state["step"] == 2:
        board_type = st.radio("Board Type", ["Checkerboard", "ChArUco"], horizontal=True)
        page_size = st.selectbox("Page Size", ["A4", "A3", "A2", "A1"], index=1)
        if board_type == "Checkerboard":
            cols = st.number_input("Columns", value=settings["checkerboard_pattern"][0], min_value=3, max_value=20)
            rows = st.number_input("Rows", value=settings["checkerboard_pattern"][1], min_value=3, max_value=20)
            square_mm = st.number_input("Square Size (mm)", value=float(settings["checker_square_mm"]), step=1.0)
        else:
            cols = st.number_input("Columns", value=settings["charuco_board_size"][0], min_value=3, max_value=20)
            rows = st.number_input("Rows", value=settings["charuco_board_size"][1], min_value=3, max_value=20)
            square_mm = st.number_input("Square Length (mm)", value=float(settings["charuco_square_mm"]), step=1.0)
            marker_mm = st.number_input("Marker Length (mm)", value=float(settings["charuco_marker_mm"]), step=0.5)
            dictionary_name = st.selectbox("Dictionary", list(dictionary_names.keys()))
        if st.button("Generate Printable Board", type="primary"):
            try:
                with lensu_tempdir() as tmpdir:
                    output_path = Path(tmpdir) / f"wizard_{board_type.lower()}_{page_size.lower()}.pdf"
                    if board_type == "Checkerboard":
                        generate_checkerboard_pdf(
                            pattern_size=(int(cols), int(rows)),
                            square_size_mm=float(square_mm),
                            page_size=page_size,
                            output_path=output_path,
                            include_metadata=True,
                        )
                    else:
                        generate_charuco_pdf(
                            board_size=(int(cols), int(rows)),
                            square_length_mm=float(square_mm),
                            marker_length_mm=float(marker_mm),
                            dictionary=int(dictionary_names[dictionary_name]),
                            page_size=page_size,
                            output_path=output_path,
                            include_metadata=True,
                        )
                    state["board_download"] = {"name": output_path.name, "bytes": output_path.read_bytes()}
            except Exception as exc:
                st.error(f"Could not generate the board PDF. {exc}")
        if state.get("board_download"):
            st.download_button(
                "Download Board PDF",
                data=state["board_download"]["bytes"],
                file_name=state["board_download"]["name"],
                mime="application/pdf",
            )
        return

    if state["step"] == 3:
        st.markdown(
            """
Capture tips:
1. Fill the center and corners of frame.
2. Tilt the board to vary perspective.
3. Keep every image sharp.
4. Avoid repeated angles.
            """
        )
        mode = st.radio("Detection Mode", ["Checkerboard", "ChArUco"], horizontal=True, key="wizard_mode")
        focal_length = st.number_input("Current Focal Length (mm)", value=50.0, step=1.0, format="%.1f")
        uploads = st.file_uploader(
            "Upload calibration images",
            type=["jpg", "jpeg", "png", "bmp", "tiff"],
            accept_multiple_files=True,
            key="wizard_uploads",
        )
        state["uploads"] = uploads or []
        st.session_state["wizard_focal_length"] = float(focal_length)
        if state["uploads"]:
            detected = 0
            preview_cols = st.columns(min(4, len(state["uploads"])))
            for index, uploaded in enumerate(state["uploads"]):
                image = _decode_upload(uploaded)
                if image is None:
                    continue
                found, overlay = _preview_detection(image, mode, settings)
                detected += 1 if found else 0
                with preview_cols[index % len(preview_cols)]:
                    st.image(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB), caption=uploaded.name, use_container_width=True)
                    st.caption("Board detected" if found else "Board not detected")
            st.metric("Usable previews", f"{detected}/{len(state['uploads'])}")
        return

    if state["step"] == 4:
        uploads = list(state.get("uploads") or [])
        if not uploads:
            st.warning("Go back to Step 4 and upload a calibration set first.")
            return
        mode = st.session_state.get("wizard_mode", "Checkerboard")
        focal_length = float(st.session_state.get("wizard_focal_length", 50.0))
        excluded = st.multiselect("Exclude bad images", [item.name for item in uploads], default=[])
        if st.button("Run Wizard Calibration", type="primary"):
            try:
                point, diagnostics = _calibrate_uploads(
                    uploads,
                    focal_length_mm=focal_length,
                    mode=mode,
                    settings=settings,
                    excluded_names=set(excluded),
                )
                state["last_point"] = point
                state["last_diagnostics"] = diagnostics
            except Exception as exc:
                st.error(f"Calibration could not be completed. {exc}")
        point = state.get("last_point")
        diagnostics = state.get("last_diagnostics")
        if point is not None and diagnostics is not None:
            used_images = sum(1 for item in diagnostics.image_results if item.used)
            st.success(f"Calibration complete. RMS {point.rms_error:.4f}px, grade {accuracy_grade(point.rms_error)}.")
            if diagnostics.image_size is not None:
                heatmap = compute_coverage_heatmap(diagnostics, diagnostics.image_size)
                st.image(cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB), caption="Coverage heatmap", use_container_width=True)
            st.write({"usable_images": used_images, "total_images": len(diagnostics.image_results)})
            if st.button("Accept Calibration"):
                profile.add_calibration(point)
                if diagnostics.image_size:
                    profile.image_width, profile.image_height = diagnostics.image_size
                store_run = _context().get("store_run")
                if callable(store_run):
                    store_run(focal_length, mode, point, diagnostics, [], settings)
                _save_session()
                st.success("Calibration added to the active lens profile.")
        return

    if state["step"] == 5:
        nodal_mode = st.radio("Nodal Input", ["Manual", "Guided Parallax"], horizontal=True)
        focal_length = float(st.session_state.get("wizard_focal_length", 50.0))
        if nodal_mode == "Manual":
            c1, c2 = st.columns(2)
            with c1:
                offset_x = st.number_input("X (mm)", value=0.0, step=0.1, format="%.2f", key="wizard_nx")
                offset_y = st.number_input("Y (mm)", value=0.0, step=0.1, format="%.2f", key="wizard_ny")
                offset_z = st.number_input("Z (mm)", value=0.0, step=0.1, format="%.2f", key="wizard_nz")
            with c2:
                rot_x = st.number_input("Pitch", value=0.0, step=0.1, format="%.2f", key="wizard_rx")
                rot_y = st.number_input("Yaw", value=0.0, step=0.1, format="%.2f", key="wizard_ry")
                rot_z = st.number_input("Roll", value=0.0, step=0.1, format="%.2f", key="wizard_rz")
            if st.button("Save Manual Nodal Offset"):
                profile.add_nodal_offset(
                    NodalOffset(
                        focal_length_mm=focal_length,
                        offset_x=float(offset_x),
                        offset_y=float(offset_y),
                        offset_z=float(offset_z),
                        rotation_x=float(rot_x),
                        rotation_y=float(rot_y),
                        rotation_z=float(rot_z),
                        method="manual",
                    )
                )
                _save_session()
                st.success("Manual nodal offset saved.")
        else:
            uploaded = st.file_uploader(
                "Upload 2-5 parallax test images",
                type=["jpg", "jpeg", "png", "bmp", "tiff"],
                accept_multiple_files=True,
                key="wizard_nodal_uploads",
            )
            angles_text = st.text_input("Pan angles (deg, comma-separated)", value="-10,-5,0,5,10")
            near_distance = st.number_input("Near object distance (m)", min_value=0.1, value=1.0, step=0.1)
            far_distance = st.number_input("Far object distance (m)", min_value=0.2, value=3.0, step=0.1)
            if uploaded and st.button("Estimate Nodal Offset"):
                try:
                    images = [image for image in (_decode_upload(item) for item in uploaded) if image is not None]
                    angles = [float(part.strip()) for part in angles_text.split(",") if part.strip()]
                    estimate = estimate_nodal_from_parallax(
                        images,
                        rotation_angles_deg=angles[: len(images)],
                        near_object_distance_m=float(near_distance),
                        far_object_distance_m=float(far_distance),
                    )
                    estimate.focal_length_mm = focal_length
                    profile.add_nodal_offset(estimate)
                    _save_session()
                    st.success(f"Estimated nodal Z offset {estimate.offset_z:.2f} mm.")
                except Exception as exc:
                    st.error(f"Nodal estimation failed. {exc}")
        return

    if state["step"] == 6:
        st.caption("Zoom lenses need repeated calibration at several focal lengths.")
        st.write({"completed_points_mm": [point.focal_length_mm for point in profile.calibration_points]})
        breathing_focus = st.number_input("Optional focus sample (m)", min_value=0.1, value=3.0, step=0.1)
        if profile.calibration_points and st.button("Add Breathing Sample From Latest Calibration"):
            latest = profile.calibration_points[-1]
            measured_mm = measured_focal_length_mm(latest, profile.sensor_width_mm, max(profile.image_width, 1))
            profile.add_breathing_point(
                BreathingPoint(
                    focus_distance_m=float(breathing_focus),
                    measured_focal_length_mm=float(measured_mm),
                    nominal_focal_length_mm=float(latest.focal_length_mm),
                )
            )
            _save_session()
            st.success("Breathing sample saved from the latest calibration point.")
        return

    if state["step"] == 7:
        export_type = st.radio("Export Format", ["UE", "Nuke", "Both"], horizontal=True)
        prepare_bundle = _context().get("prepare_export_bundle")
        prepare_nuke_bundle = _context().get("prepare_nuke_bundle")
        if st.button("Build Export Package", type="primary"):
            try:
                bundle = None
                if export_type == "UE":
                    bundle = prepare_bundle(profile, "Parameters", True) if callable(prepare_bundle) else None
                elif export_type == "Nuke":
                    bundle = prepare_nuke_bundle(profile) if callable(prepare_nuke_bundle) else None
                else:
                    ue_bundle = prepare_bundle(profile, "Parameters", True) if callable(prepare_bundle) else None
                    nuke_bundle = prepare_nuke_bundle(profile) if callable(prepare_nuke_bundle) else None
                    bundle = {
                        "name": "wizard_exports.json",
                        "bytes": json.dumps({"ue": bool(ue_bundle), "nuke": bool(nuke_bundle)}).encode("utf-8"),
                    }
                state["last_bundle"] = bundle
            except Exception as exc:
                st.error(f"Export failed. {exc}")
        if state.get("last_bundle"):
            st.download_button(
                "Download Export Package",
                data=state["last_bundle"]["bytes"],
                file_name=state["last_bundle"]["name"],
                mime="application/zip" if state["last_bundle"]["name"].endswith(".zip") else "application/json",
            )
        st.markdown(
            """
Unreal Engine import:
1. Enable Camera Calibration and Python Editor Script Plugin.
2. Unzip the package.
3. Run the generated Python script inside Unreal.
            """
        )
        return

    if state["step"] == 8:
        profile.notes = st.text_area("Notes", value=profile.notes, height=100)
        if st.button("Save To Library", type="primary"):
            try:
                saved = save_to_library(profile)
                _save_session()
                st.success(f"Saved to library as {saved.name}.")
            except Exception as exc:
                st.error(f"Could not save the profile. {exc}")

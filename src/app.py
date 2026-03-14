"""LensU — Streamlit UI for lens calibration and UE export."""

import streamlit as st
import cv2
import numpy as np
import tempfile
import zipfile
import io
from pathlib import Path
from calibration import (
    CalibrationPoint,
    LensProfile,
    NodalOffset,
    detect_checkerboard,
    calibrate_from_images,
)
from ue_export import export_ue_json, export_ue_python_script


st.set_page_config(
    page_title="LensU",
    page_icon="📷",
    layout="wide",
)

# --- Session State Init ---
if "profile" not in st.session_state:
    st.session_state.profile = LensProfile()
if "calibration_results" not in st.session_state:
    st.session_state.calibration_results = {}


def main():
    st.title("📷 LensU")
    st.caption("Lens calibration tool for Unreal Engine (ULens export)")

    # Sidebar — Lens & Sensor Setup
    with st.sidebar:
        st.header("Lens Setup")
        profile = st.session_state.profile

        profile.lens_name = st.text_input("Lens Name", value=profile.lens_name)

        st.subheader("Sensor")
        col1, col2 = st.columns(2)
        with col1:
            profile.sensor_width_mm = st.number_input(
                "Width (mm)", value=profile.sensor_width_mm, step=0.1, format="%.1f"
            )
        with col2:
            profile.sensor_height_mm = st.number_input(
                "Height (mm)", value=profile.sensor_height_mm, step=0.1, format="%.1f"
            )

        sensor_presets = {
            "Full Frame (36x24)": (36.0, 24.0),
            "APS-C Canon (22.3x14.9)": (22.3, 14.9),
            "APS-C Sony/Nikon (23.5x15.6)": (23.5, 15.6),
            "Micro 4/3 (17.3x13)": (17.3, 13.0),
            "Super 35 (24.89x18.66)": (24.89, 18.66),
        }
        preset = st.selectbox("Sensor Preset", ["Custom"] + list(sensor_presets.keys()))
        if preset != "Custom" and preset in sensor_presets:
            w, h = sensor_presets[preset]
            profile.sensor_width_mm = w
            profile.sensor_height_mm = h

        st.subheader("Checkerboard")
        col1, col2 = st.columns(2)
        with col1:
            pattern_cols = st.number_input("Inner Corners (cols)", value=9, min_value=3, max_value=20)
        with col2:
            pattern_rows = st.number_input("Inner Corners (rows)", value=6, min_value=3, max_value=20)
        square_size = st.number_input(
            "Square Size (mm)", value=25.0, step=1.0, format="%.1f"
        )

    # Main content — Tabs
    tab_calibrate, tab_nodal, tab_profile, tab_export = st.tabs(
        ["Distortion Calibration", "Nodal Offset", "Lens Profile", "UE Export"]
    )

    # --- TAB 1: Distortion Calibration ---
    with tab_calibrate:
        st.header("Distortion Calibration")
        st.info(
            "Upload checkerboard images taken at a specific focal length. "
            "For zoom lenses, calibrate at multiple focal lengths."
        )

        focal_length = st.number_input(
            "Focal Length (mm)",
            value=50.0,
            step=1.0,
            format="%.1f",
            key="cal_focal",
        )

        uploaded_files = st.file_uploader(
            "Upload checkerboard images",
            type=["jpg", "jpeg", "png", "bmp", "tiff"],
            accept_multiple_files=True,
            key="cal_images",
        )

        if uploaded_files and st.button("Run Calibration", type="primary"):
            with st.spinner("Detecting checkerboard patterns..."):
                # Save uploaded files to temp directory
                with tempfile.TemporaryDirectory() as tmpdir:
                    image_paths = []
                    for f in uploaded_files:
                        p = Path(tmpdir) / f.name
                        p.write_bytes(f.read())
                        image_paths.append(p)

                    pattern_size = (int(pattern_cols), int(pattern_rows))
                    result, used = calibrate_from_images(
                        image_paths,
                        pattern_size=pattern_size,
                        square_size_mm=square_size,
                        focal_length_mm=focal_length,
                    )

                if result is None:
                    st.error(
                        f"Calibration failed. Only {sum(used)}/{len(used)} images had "
                        f"detectable checkerboards. Need at least 3."
                    )
                else:
                    profile.add_calibration(result)
                    profile.image_width = cv2.imread(str(image_paths[0])).shape[1] if image_paths else profile.image_width
                    profile.image_height = cv2.imread(str(image_paths[0])).shape[0] if image_paths else profile.image_height
                    st.session_state.calibration_results[focal_length] = result

                    st.success(
                        f"Calibration complete! RMS error: {result.rms_error:.4f} px "
                        f"({result.num_images} images used)"
                    )

                    # Show results
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("K1 (radial)", f"{result.k1:.6f}")
                        st.metric("K2 (radial)", f"{result.k2:.6f}")
                        st.metric("K3 (radial)", f"{result.k3:.6f}")
                    with col2:
                        st.metric("P1 (tangential)", f"{result.p1:.6f}")
                        st.metric("P2 (tangential)", f"{result.p2:.6f}")
                        st.metric("Image Center", f"({result.cx:.4f}, {result.cy:.4f})")

                # Show detection results per image
                st.subheader("Detection Results")
                cols = st.columns(min(4, len(uploaded_files)))
                for i, (f, was_used) in enumerate(zip(uploaded_files, used)):
                    with cols[i % len(cols)]:
                        f.seek(0)
                        file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
                        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                        if img is not None:
                            found, corners, display = detect_checkerboard(
                                img, (int(pattern_cols), int(pattern_rows))
                            )
                            display_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
                            st.image(display_rgb, caption=f.name, use_container_width=True)
                            st.caption("OK" if was_used else "FAILED")

    # --- TAB 2: Nodal Offset ---
    with tab_nodal:
        st.header("Nodal Offset")
        st.info(
            "Enter nodal offset values manually. For precise measurement, "
            "rotate the camera around the entrance pupil and observe parallax."
        )

        nodal_focal = st.number_input(
            "Focal Length (mm)",
            value=50.0,
            step=1.0,
            format="%.1f",
            key="nodal_focal",
        )

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Translation (mm)")
            nx = st.number_input("X offset", value=0.0, step=0.1, format="%.2f", key="nx")
            ny = st.number_input("Y offset", value=0.0, step=0.1, format="%.2f", key="ny")
            nz = st.number_input("Z offset", value=0.0, step=0.1, format="%.2f", key="nz")
        with col2:
            st.subheader("Rotation (degrees)")
            rx = st.number_input("Pitch", value=0.0, step=0.1, format="%.2f", key="rx")
            ry = st.number_input("Yaw", value=0.0, step=0.1, format="%.2f", key="ry")
            rz = st.number_input("Roll", value=0.0, step=0.1, format="%.2f", key="rz")

        if st.button("Save Nodal Offset", type="primary"):
            offset = NodalOffset(
                focal_length_mm=nodal_focal,
                offset_x=nx, offset_y=ny, offset_z=nz,
                rotation_x=rx, rotation_y=ry, rotation_z=rz,
            )
            profile.add_nodal_offset(offset)
            st.success(f"Nodal offset saved for {nodal_focal}mm")

    # --- TAB 3: Lens Profile ---
    with tab_profile:
        st.header("Lens Profile")

        if not profile.calibration_points and not profile.nodal_offsets:
            st.warning("No calibration data yet. Use the Calibration tab to add data points.")
        else:
            st.subheader("Calibration Points")
            if profile.calibration_points:
                for point in profile.calibration_points:
                    with st.expander(f"{point.focal_length_mm}mm (RMS: {point.rms_error:.4f})"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**K1:** {point.k1:.6f}")
                            st.write(f"**K2:** {point.k2:.6f}")
                            st.write(f"**K3:** {point.k3:.6f}")
                        with col2:
                            st.write(f"**P1:** {point.p1:.6f}")
                            st.write(f"**P2:** {point.p2:.6f}")
                        with col3:
                            st.write(f"**Center:** ({point.cx:.4f}, {point.cy:.4f})")
                            st.write(f"**Focal (px):** {point.fx:.1f} x {point.fy:.1f}")
                            st.write(f"**Images:** {point.num_images}")

            st.subheader("Nodal Offsets")
            if profile.nodal_offsets:
                for offset in profile.nodal_offsets:
                    with st.expander(f"{offset.focal_length_mm}mm"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**X:** {offset.offset_x:.2f}mm")
                            st.write(f"**Y:** {offset.offset_y:.2f}mm")
                            st.write(f"**Z:** {offset.offset_z:.2f}mm")
                        with col2:
                            st.write(f"**Pitch:** {offset.rotation_x:.2f} deg")
                            st.write(f"**Yaw:** {offset.rotation_y:.2f} deg")
                            st.write(f"**Roll:** {offset.rotation_z:.2f} deg")
            else:
                st.info("No nodal offsets recorded.")

            # Save/Load profile
            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                profile_json = profile.to_dict()
                st.download_button(
                    "Download Profile (JSON)",
                    data=json.dumps(profile_json, indent=2),
                    file_name=f"{profile.lens_name.replace(' ', '_')}_profile.json",
                    mime="application/json",
                )
            with col2:
                uploaded_profile = st.file_uploader("Load Profile", type=["json"], key="load_profile")
                if uploaded_profile:
                    import json
                    data = json.loads(uploaded_profile.read())
                    loaded = LensProfile(
                        lens_name=data.get("lens_name", "Unknown"),
                        sensor_width_mm=data.get("sensor_width_mm", 36.0),
                        sensor_height_mm=data.get("sensor_height_mm", 24.0),
                        image_width=data.get("image_width", 1920),
                        image_height=data.get("image_height", 1080),
                    )
                    for p in data.get("calibration_points", []):
                        loaded.calibration_points.append(CalibrationPoint(**p))
                    for n in data.get("nodal_offsets", []):
                        loaded.nodal_offsets.append(NodalOffset(**n))
                    st.session_state.profile = loaded
                    st.success(f"Loaded profile: {loaded.lens_name}")
                    st.rerun()

    # --- TAB 4: UE Export ---
    with tab_export:
        st.header("Export to Unreal Engine")

        if not profile.calibration_points:
            st.warning("No calibration data. Run a calibration first.")
        else:
            st.info(
                "Export generates two files:\n"
                "1. **Calibration JSON** — lens data in UE-compatible format\n"
                "2. **UE Python Script** — run inside UE to create the .ulens asset\n\n"
                "Compatible with UE 5.6+ (Camera Calibration plugin required)"
            )

            if st.button("Generate UE Export Package", type="primary"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)

                    # Generate files
                    json_path = export_ue_json(profile, tmp_path)
                    script_path = export_ue_python_script(
                        profile, json_path.name, tmp_path
                    )

                    # Create ZIP
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        zf.write(json_path, json_path.name)
                        zf.write(script_path, script_path.name)
                    zip_buffer.seek(0)

                    st.download_button(
                        "Download UE Export Package (.zip)",
                        data=zip_buffer,
                        file_name=f"LensU_{profile.lens_name.replace(' ', '_')}_UE_Export.zip",
                        mime="application/zip",
                    )

                    # Show preview of generated files
                    st.subheader("Generated Files Preview")
                    with st.expander("Calibration JSON"):
                        st.json(json.loads(json_path.read_text()))
                    with st.expander("UE Python Script"):
                        st.code(script_path.read_text(), language="python")

            st.divider()
            st.subheader("How to Import in Unreal Engine")
            st.markdown("""
1. Enable the **Camera Calibration** plugin in UE
2. Unzip the export package into your UE project's `Content/Python/` folder
3. Open **Tools > Execute Python Script** (or the Python console)
4. Run the import script — it creates a LensFile at `/Game/LensU/`
5. Assign the LensFile to your CineCamera Actor
            """)


import json  # needed for profile tab

if __name__ == "__main__":
    main()

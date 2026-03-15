"""PDF reporting helpers for LensU."""

from __future__ import annotations

import tempfile
import zlib
from datetime import datetime
from pathlib import Path
from typing import Iterable

import cv2
import numpy as np

try:
    from .calibration import (
        CalibrationPoint,
        LensProfile,
        accuracy_grade,
        generate_distortion_grid,
    )
    from .temp_paths import lensu_tempdir
except ImportError:
    from calibration import (
        CalibrationPoint,
        LensProfile,
        accuracy_grade,
        generate_distortion_grid,
    )
    from temp_paths import lensu_tempdir

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    MATPLOTLIB_AVAILABLE = True
except ModuleNotFoundError:
    plt = None
    MATPLOTLIB_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    REPORTLAB_AVAILABLE = True
except ModuleNotFoundError:
    colors = None
    A4 = (595.2755905511812, 841.8897637795277)
    mm = 72.0 / 25.4
    ParagraphStyle = object
    Paragraph = object
    SimpleDocTemplate = object
    Spacer = object
    Table = object
    TableStyle = object
    Image = object
    PageBreak = object
    REPORTLAB_AVAILABLE = False


REPORT_VERSION = "LensU v1.3"


def _simple_pdf_bytes(lines: list[str]) -> bytes:
    page_width, page_height = A4
    commands: list[str] = []
    y = page_height - 50
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"BT /F1 11 Tf 40 {y:.1f} Td ({safe}) Tj ET\n")
        y -= 16
        if y < 60:
            break
    stream = zlib.compress("".join(commands).encode("latin-1", "replace"))
    objects = [
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} /Filter /FlateDecode >>\nstream\n".encode("latin-1") + stream + b"\nendstream",
        f"<< /Type /Page /Parent 4 0 R /MediaBox [0 0 {page_width:.1f} {page_height:.1f}] /Resources << /Font << /F1 1 0 R >> >> /Contents 2 0 R >>".encode("latin-1"),
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Catalog /Pages 4 0 R >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("latin-1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    startxref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 5 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode("latin-1")
    )
    return bytes(pdf)


def _styles() -> dict[str, ParagraphStyle]:
    stylesheet = getSampleStyleSheet()
    return {
        "title": stylesheet["Title"],
        "heading": stylesheet["Heading1"],
        "subheading": stylesheet["Heading2"],
        "body": stylesheet["BodyText"],
        "small": ParagraphStyle("LensUSmall", parent=stylesheet["BodyText"], fontSize=8, leading=10),
    }


def _build_doc(output_path: Path) -> SimpleDocTemplate:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=output_path.stem,
        author="LensU",
    )


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#5B6570"))
    canvas.drawString(doc.leftMargin, 8 * mm, REPORT_VERSION)
    canvas.drawRightString(A4[0] - doc.rightMargin, 8 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(text.replace("\n", "<br/>"), style)


def _table(data: list[list[object]], column_widths: Iterable[float] | None = None) -> Table:
    table = Table(data, colWidths=list(column_widths) if column_widths is not None else None, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F2933")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7CDD4")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F7FA")]),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LEADING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _save_figure(fig, output_path: Path) -> Path:
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _write_bgr_image(image: np.ndarray, output_path: Path) -> Path:
    cv2.imwrite(str(output_path), image)
    return output_path


def _blank_chart(title: str, size: tuple[int, int] = (1100, 650)) -> np.ndarray:
    image = np.full((size[1], size[0], 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (70, 50), (size[0] - 40, size[1] - 70), (220, 225, 230), 1)
    cv2.putText(image, title, (70, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 41, 59), 2, cv2.LINE_AA)
    return image


def _plot_series_cv(
    title: str,
    x_values: list[float],
    y_values: list[float],
    output_path: Path,
    series_color: tuple[int, int, int] = (152, 93, 18),
) -> Path:
    image = _blank_chart(title)
    if not x_values or not y_values:
        cv2.putText(image, "No data available", (80, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (90, 98, 108), 2, cv2.LINE_AA)
        return _write_bgr_image(image, output_path)

    left, top = 90, 90
    right, bottom = image.shape[1] - 50, image.shape[0] - 90
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    if abs(x_max - x_min) < 1e-6:
        x_max = x_min + 1.0
    if abs(y_max - y_min) < 1e-6:
        y_max = y_min + 1.0

    points: list[tuple[int, int]] = []
    for x_val, y_val in zip(x_values, y_values):
        x_px = int(left + (x_val - x_min) / (x_max - x_min) * (right - left))
        y_px = int(bottom - (y_val - y_min) / (y_max - y_min) * (bottom - top))
        points.append((x_px, y_px))

    cv2.line(image, (left, bottom), (right, bottom), (120, 128, 136), 2, cv2.LINE_AA)
    cv2.line(image, (left, bottom), (left, top), (120, 128, 136), 2, cv2.LINE_AA)
    cv2.polylines(image, [np.array(points, dtype=np.int32)], False, series_color, 3, cv2.LINE_AA)
    for point in points:
        cv2.circle(image, point, 5, series_color, -1, cv2.LINE_AA)
    return _write_bgr_image(image, output_path)


def _plot_distortion_grid(point: CalibrationPoint, image_size: tuple[int, int], output_path: Path) -> Path:
    grid = generate_distortion_grid(point, image_size)
    if not MATPLOTLIB_AVAILABLE:
        return _write_bgr_image(grid, output_path)
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.imshow(grid[:, :, ::-1])
    ax.set_title(f"Distortion Grid - {point.focal_length_mm:.1f}mm")
    ax.axis("off")
    return _save_figure(fig, output_path)


def _plot_coverage_map(point: CalibrationPoint, output_path: Path) -> Path:
    if not MATPLOTLIB_AVAILABLE:
        image = np.full((800, 800, 3), 255, dtype=np.uint8)
        center = (int(point.cx * 800), int(point.cy * 800))
        for radius in (120, 220, 320, 380):
            cv2.circle(image, center, radius, (215, 220, 225), 2, cv2.LINE_AA)
        cv2.line(image, (center[0], 0), (center[0], 799), (160, 170, 180), 1, cv2.LINE_AA)
        cv2.line(image, (0, center[1]), (799, center[1]), (160, 170, 180), 1, cv2.LINE_AA)
        cv2.circle(image, center, 10, (40, 40, 210), -1, cv2.LINE_AA)
        cv2.putText(image, "Coverage / Principal Point", (40, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 41, 59), 2, cv2.LINE_AA)
        return _write_bgr_image(image, output_path)
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    center = np.array([point.cx, point.cy])
    radius = np.linspace(0.15, 0.48, 5)
    theta = np.linspace(0, 2 * np.pi, 180)
    for r in radius:
        ax.plot(center[0] + np.cos(theta) * r, center[1] + np.sin(theta) * r, color="#D0D7DE", linewidth=0.8)
    ax.axvline(center[0], color="#A0AEC0", linewidth=0.8, linestyle="--")
    ax.axhline(center[1], color="#A0AEC0", linewidth=0.8, linestyle="--")
    ax.scatter([point.cx], [point.cy], color="#D14343", s=50, label="Image center")
    ax.set_xlim(0, 1)
    ax.set_ylim(1, 0)
    ax.set_title("Coverage / Principal Point")
    ax.set_xlabel("Normalized X")
    ax.set_ylabel("Normalized Y")
    ax.grid(alpha=0.25)
    ax.legend(loc="lower right")
    return _save_figure(fig, output_path)


def _plot_zoom_curve(profile: LensProfile, output_path: Path) -> Path:
    if not MATPLOTLIB_AVAILABLE:
        return _plot_series_cv(
            "Zoom Summary - k1 Across Focal Range",
            [point.focal_length_mm for point in profile.calibration_points],
            [point.k1 for point in profile.calibration_points],
            output_path,
        )
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    focals = [point.focal_length_mm for point in profile.calibration_points]
    k1_values = [point.k1 for point in profile.calibration_points]
    ax.plot(focals, k1_values, marker="o", color="#125D98", linewidth=2)
    ax.set_title("Zoom Summary - k1 Across Focal Range")
    ax.set_xlabel("Focal Length (mm)")
    ax.set_ylabel("k1")
    ax.grid(alpha=0.3)
    return _save_figure(fig, output_path)


def _plot_breathing_curve(profile: LensProfile, output_path: Path) -> Path:
    if not MATPLOTLIB_AVAILABLE:
        first_profile = profile.breathing_profiles[0] if profile.breathing_profiles else None
        x_values = [point.focus_distance_m for point in first_profile.points] if first_profile else []
        y_values = [point.measured_focal_length_mm for point in first_profile.points] if first_profile else []
        return _plot_series_cv("Lens Breathing", x_values, y_values, output_path, series_color=(22, 98, 149))
    fig, ax = plt.subplots(figsize=(6.8, 3.8))
    for breathing in profile.breathing_profiles:
        xs = [point.focus_distance_m for point in breathing.points]
        ys = [point.measured_focal_length_mm for point in breathing.points]
        ax.plot(xs, ys, marker="o", linewidth=1.8, label=f"{breathing.nominal_focal_length_mm:.1f}mm")
    ax.set_title("Lens Breathing")
    ax.set_xlabel("Focus Distance (m)")
    ax.set_ylabel("Measured Focal Length (mm)")
    ax.grid(alpha=0.3)
    if profile.breathing_profiles:
        ax.legend()
    return _save_figure(fig, output_path)


def _plot_overlay_grid(point_a: CalibrationPoint, point_b: CalibrationPoint, image_size: tuple[int, int], output_path: Path) -> Path:
    grid_a = generate_distortion_grid(point_a, image_size)
    grid_b = generate_distortion_grid(point_b, image_size)
    if not MATPLOTLIB_AVAILABLE:
        blended = cv2.addWeighted(grid_a, 0.5, grid_b, 0.5, 0.0)
        return _write_bgr_image(blended, output_path)
    fig, ax = plt.subplots(figsize=(7.0, 4.4))
    ax.imshow(grid_a[:, :, ::-1], alpha=0.55)
    ax.imshow(grid_b[:, :, ::-1], alpha=0.55)
    ax.set_title("Overlay Distortion Grid")
    ax.axis("off")
    return _save_figure(fig, output_path)


def _grade_color(delta: float, yellow: float, red: float) -> colors.Color:
    magnitude = abs(delta)
    if magnitude > red:
        return colors.HexColor("#B42318")
    if magnitude > yellow:
        return colors.HexColor("#B54708")
    return colors.HexColor("#027A48")


def _comparison_recommendation(profile_a: LensProfile, profile_b: LensProfile) -> str:
    points_a = {round(point.focal_length_mm, 3): point for point in profile_a.calibration_points}
    points_b = {round(point.focal_length_mm, 3): point for point in profile_b.calibration_points}
    for focal in sorted(set(points_a) & set(points_b)):
        point_a = points_a[focal]
        point_b = points_b[focal]
        if abs(point_a.k1 - point_b.k1) > 0.02:
            return "Recalibration recommended"
        center_drift = max(abs(point_a.cx - point_b.cx), abs(point_a.cy - point_b.cy))
        if center_drift > 0.02:
            return "Recalibration recommended"

    offsets_a = {round(offset.focal_length_mm, 3): offset for offset in profile_a.nodal_offsets}
    offsets_b = {round(offset.focal_length_mm, 3): offset for offset in profile_b.nodal_offsets}
    for focal in sorted(set(offsets_a) & set(offsets_b)):
        offset_a = offsets_a[focal]
        offset_b = offsets_b[focal]
        if max(
            abs(offset_a.offset_x - offset_b.offset_x),
            abs(offset_a.offset_y - offset_b.offset_y),
            abs(offset_a.offset_z - offset_b.offset_z),
        ) > 5.0:
            return "Recalibration recommended"
    return "Lens is stable"


def generate_calibration_report(
    profile: LensProfile,
    output_path: Path,
    include_charts: bool = True,
) -> Path:
    """Generate a comprehensive PDF calibration report."""

    if not REPORTLAB_AVAILABLE:
        lines = [
            profile.lens_name,
            "Calibration Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Sensor: {profile.sensor_width_mm:.2f} x {profile.sensor_height_mm:.2f} mm",
            f"Image Size: {profile.image_width} x {profile.image_height}",
            (
                f"Anamorphic: {profile.anamorphic.squeeze_ratio:.2f}x"
                if profile.anamorphic is not None
                else "Anamorphic: No"
            ),
        ]
        for point in profile.calibration_points:
            lines.append(
                f"{point.focal_length_mm:.1f}mm | k1={point.k1:.6f} k2={point.k2:.6f} "
                f"p1={point.p1:.6f} p2={point.p2:.6f} k3={point.k3:.6f} RMS={point.rms_error:.4f}"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(_simple_pdf_bytes(lines))
        return output_path

    doc = _build_doc(output_path)
    styles = _styles()
    story: list[object] = []
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    story.append(_paragraph(profile.lens_name, styles["title"]))
    story.append(Spacer(1, 6 * mm))
    story.append(_paragraph("Calibration Report", styles["heading"]))
    story.append(Spacer(1, 4 * mm))
    story.append(_paragraph(f"Generated: {generated_at}<br/>Calibrated by: LensU user", styles["body"]))
    story.append(Spacer(1, 6 * mm))

    anamorphic_text = "No"
    if profile.anamorphic is not None:
        anamorphic_text = (
            f"Yes - {profile.anamorphic.squeeze_ratio:.2f}x "
            f"({'desqueezed input' if profile.anamorphic.desqueeze_applied else 'raw squeezed input'})"
        )
    story.append(
        _table(
            [
                ["Lens", "Sensor", "Image Size", "Anamorphic"],
                [
                    profile.lens_name,
                    f"{profile.sensor_width_mm:.2f} x {profile.sensor_height_mm:.2f} mm",
                    f"{profile.image_width} x {profile.image_height}",
                    anamorphic_text,
                ],
            ],
            column_widths=[48 * mm, 42 * mm, 35 * mm, 48 * mm],
        )
    )
    story.append(Spacer(1, 8 * mm))

    if not profile.calibration_points:
        story.append(_paragraph("No calibration points are available in this profile.", styles["body"]))
    with lensu_tempdir() as tmpdir:
        temp_dir = Path(tmpdir)
        for index, point in enumerate(profile.calibration_points):
            if index > 0:
                story.append(PageBreak())
            story.append(_paragraph(f"Focal Length {point.focal_length_mm:.1f}mm", styles["heading"]))
            story.append(Spacer(1, 3 * mm))
            story.append(
                _table(
                    [
                        ["Metric", "Value", "Metric", "Value"],
                        ["k1", f"{point.k1:.6f}", "k2", f"{point.k2:.6f}"],
                        ["p1", f"{point.p1:.6f}", "p2", f"{point.p2:.6f}"],
                        ["k3", f"{point.k3:.6f}", "RMS", f"{point.rms_error:.4f} px"],
                        ["Grade", accuracy_grade(point.rms_error), "Center", f"{point.cx:.4f}, {point.cy:.4f}"],
                    ],
                    column_widths=[26 * mm, 36 * mm, 26 * mm, 52 * mm],
                )
            )
            story.append(Spacer(1, 4 * mm))
            if profile.anamorphic is not None and point.anamorphic_squeezed and point.anamorphic_desqueezed:
                story.append(_paragraph("Anamorphic Parameters", styles["subheading"]))
                story.append(
                    _table(
                        [
                            ["Space", "k1", "k2", "p1", "p2", "k3"],
                            [
                                "Desqueezed",
                                f"{point.anamorphic_desqueezed['k1']:.6f}",
                                f"{point.anamorphic_desqueezed['k2']:.6f}",
                                f"{point.anamorphic_desqueezed['p1']:.6f}",
                                f"{point.anamorphic_desqueezed['p2']:.6f}",
                                f"{point.anamorphic_desqueezed['k3']:.6f}",
                            ],
                            [
                                "Squeezed",
                                f"{point.anamorphic_squeezed['k1']:.6f}",
                                f"{point.anamorphic_squeezed['k2']:.6f}",
                                f"{point.anamorphic_squeezed['p1']:.6f}",
                                f"{point.anamorphic_squeezed['p2']:.6f}",
                                f"{point.anamorphic_squeezed['k3']:.6f}",
                            ],
                        ],
                        column_widths=[28 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm, 24 * mm],
                    )
                )
                story.append(Spacer(1, 4 * mm))
            if include_charts and profile.image_width and profile.image_height:
                grid_path = _plot_distortion_grid(
                    point,
                    (profile.image_width, profile.image_height),
                    temp_dir / f"grid_{index}.png",
                )
                coverage_path = _plot_coverage_map(point, temp_dir / f"coverage_{index}.png")
                story.append(Image(str(grid_path), width=175 * mm, height=108 * mm))
                story.append(Spacer(1, 3 * mm))
                story.append(Image(str(coverage_path), width=90 * mm, height=90 * mm))
                story.append(Spacer(1, 3 * mm))

        if len(profile.calibration_points) > 1:
            story.append(PageBreak())
            story.append(_paragraph("Zoom Lens Summary", styles["heading"]))
            story.append(Spacer(1, 3 * mm))
            summary_rows = [["Focal Length", "k1", "RMS", "Grade"]]
            for point in profile.calibration_points:
                summary_rows.append(
                    [
                        f"{point.focal_length_mm:.1f}mm",
                        f"{point.k1:.6f}",
                        f"{point.rms_error:.4f}px",
                        accuracy_grade(point.rms_error),
                    ]
                )
            story.append(_table(summary_rows, column_widths=[35 * mm, 35 * mm, 35 * mm, 55 * mm]))
            story.append(Spacer(1, 4 * mm))
            if include_charts:
                zoom_path = _plot_zoom_curve(profile, temp_dir / "zoom_curve.png")
                story.append(Image(str(zoom_path), width=170 * mm, height=95 * mm))

        if profile.breathing_profiles:
            story.append(PageBreak())
            story.append(_paragraph("Breathing Data", styles["heading"]))
            story.append(Spacer(1, 3 * mm))
            rows = [["Nominal", "Samples", "Breathing %"]]
            for breathing in profile.breathing_profiles:
                rows.append(
                    [
                        f"{breathing.nominal_focal_length_mm:.1f}mm",
                        str(len(breathing.points)),
                        f"{breathing.breathing_ratio():.2f}%",
                    ]
                )
            story.append(_table(rows, column_widths=[45 * mm, 35 * mm, 35 * mm]))
            story.append(Spacer(1, 4 * mm))
            if include_charts:
                breathing_path = _plot_breathing_curve(profile, temp_dir / "breathing.png")
                story.append(Image(str(breathing_path), width=170 * mm, height=95 * mm))

        if profile.nodal_offsets:
            story.append(PageBreak())
            story.append(_paragraph("Nodal Offset Data", styles["heading"]))
            rows = [["Focal", "Offset XYZ (mm)", "Rotation XYZ (deg)", "Confidence", "Method"]]
            for offset in profile.nodal_offsets:
                rows.append(
                    [
                        f"{offset.focal_length_mm:.1f}mm",
                        f"{offset.offset_x:.2f}, {offset.offset_y:.2f}, {offset.offset_z:.2f}",
                        f"{offset.rotation_x:.2f}, {offset.rotation_y:.2f}, {offset.rotation_z:.2f}",
                        f"{offset.confidence:.2f}",
                        offset.method,
                    ]
                )
            story.append(_table(rows, column_widths=[22 * mm, 53 * mm, 53 * mm, 22 * mm, 30 * mm]))

        story.append(PageBreak())
        story.append(_paragraph("UE Import Instructions", styles["heading"]))
        story.append(
            _paragraph(
                "1. Enable Camera Calibration and Python Editor Script Plugin.<br/>"
                "2. Export the LensU UE package from the app.<br/>"
                "3. Unzip the package into the Unreal project workspace.<br/>"
                "4. Run the generated Python import script from Tools > Execute Python Script.<br/>"
                "5. Use the resulting LensFile in the camera calibration workflow.",
                styles["body"],
            )
        )

        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path


def generate_comparison_report(
    profile_a: LensProfile,
    profile_b: LensProfile,
    output_path: Path,
) -> Path:
    """Compare two profiles and generate a diff report."""

    if not REPORTLAB_AVAILABLE:
        lines = [
            f"{profile_a.lens_name} vs {profile_b.lens_name}",
            "Comparison Report",
            f"Recommendation: {_comparison_recommendation(profile_a, profile_b)}",
        ]
        points_a = {round(point.focal_length_mm, 3): point for point in profile_a.calibration_points}
        points_b = {round(point.focal_length_mm, 3): point for point in profile_b.calibration_points}
        for focal in sorted(set(points_a) | set(points_b)):
            point_a = points_a.get(focal)
            point_b = points_b.get(focal)
            if point_a is None or point_b is None:
                lines.append(f"{focal:.1f}mm | missing in one profile")
                continue
            lines.append(
                f"{focal:.1f}mm | k1 delta={point_b.k1 - point_a.k1:+.6f} "
                f"center delta=({point_b.cx - point_a.cx:+.4f}, {point_b.cy - point_a.cy:+.4f}) "
                f"rms={point_a.rms_error:.4f}/{point_b.rms_error:.4f}"
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(_simple_pdf_bytes(lines))
        return output_path

    doc = _build_doc(output_path)
    styles = _styles()
    story: list[object] = []
    story.append(_paragraph(f"{profile_a.lens_name} vs {profile_b.lens_name}", styles["title"]))
    story.append(Spacer(1, 4 * mm))
    story.append(_paragraph("Comparison Report", styles["heading"]))
    story.append(Spacer(1, 4 * mm))
    recommendation = _comparison_recommendation(profile_a, profile_b)
    story.append(_paragraph(f"Recommendation: <b>{recommendation}</b>", styles["body"]))
    story.append(Spacer(1, 5 * mm))

    points_a = {round(point.focal_length_mm, 3): point for point in profile_a.calibration_points}
    points_b = {round(point.focal_length_mm, 3): point for point in profile_b.calibration_points}
    rows = [["Focal", "k1 A", "k1 B", "Delta", "Center A", "Center B", "RMS A/B"]]
    for focal in sorted(set(points_a) | set(points_b)):
        point_a = points_a.get(focal)
        point_b = points_b.get(focal)
        if point_a is None or point_b is None:
            rows.append([f"{focal:.1f}mm", "-", "-", "-", "-", "-", "-"])
            continue
        rows.append(
            [
                f"{focal:.1f}mm",
                f"{point_a.k1:.6f}",
                f"{point_b.k1:.6f}",
                f"{point_b.k1 - point_a.k1:+.6f}",
                f"{point_a.cx:.4f}, {point_a.cy:.4f}",
                f"{point_b.cx:.4f}, {point_b.cy:.4f}",
                f"{point_a.rms_error:.4f} / {point_b.rms_error:.4f}",
            ]
        )
    comparison_table = _table(rows, column_widths=[22 * mm, 22 * mm, 22 * mm, 24 * mm, 34 * mm, 34 * mm, 28 * mm])
    for index, focal in enumerate(sorted(set(points_a) | set(points_b)), start=1):
        point_a = points_a.get(focal)
        point_b = points_b.get(focal)
        if point_a is None or point_b is None:
            continue
        comparison_table.setStyle(
            TableStyle(
                [
                    ("TEXTCOLOR", (3, index), (3, index), _grade_color(point_b.k1 - point_a.k1, 0.005, 0.02)),
                    (
                        "TEXTCOLOR",
                        (5, index),
                        (5, index),
                        _grade_color(max(abs(point_b.cx - point_a.cx), abs(point_b.cy - point_a.cy)), 0.005, 0.02),
                    ),
                ]
            )
        )
    story.append(comparison_table)

    offsets_a = {round(offset.focal_length_mm, 3): offset for offset in profile_a.nodal_offsets}
    offsets_b = {round(offset.focal_length_mm, 3): offset for offset in profile_b.nodal_offsets}
    if offsets_a or offsets_b:
        story.append(Spacer(1, 5 * mm))
        nodal_rows = [["Focal", "Offset A", "Offset B", "Delta X/Y/Z"]]
        for focal in sorted(set(offsets_a) | set(offsets_b)):
            offset_a = offsets_a.get(focal)
            offset_b = offsets_b.get(focal)
            if offset_a is None or offset_b is None:
                nodal_rows.append([f"{focal:.1f}mm", "-", "-", "-"])
                continue
            nodal_rows.append(
                [
                    f"{focal:.1f}mm",
                    f"{offset_a.offset_x:.2f}, {offset_a.offset_y:.2f}, {offset_a.offset_z:.2f}",
                    f"{offset_b.offset_x:.2f}, {offset_b.offset_y:.2f}, {offset_b.offset_z:.2f}",
                    (
                        f"{offset_b.offset_x - offset_a.offset_x:+.2f}, "
                        f"{offset_b.offset_y - offset_a.offset_y:+.2f}, "
                        f"{offset_b.offset_z - offset_a.offset_z:+.2f}"
                    ),
                ]
            )
        nodal_table = _table(nodal_rows, column_widths=[22 * mm, 48 * mm, 48 * mm, 48 * mm])
        for index, focal in enumerate(sorted(set(offsets_a) | set(offsets_b)), start=1):
            offset_a = offsets_a.get(focal)
            offset_b = offsets_b.get(focal)
            if offset_a is None or offset_b is None:
                continue
            drift = max(
                abs(offset_b.offset_x - offset_a.offset_x),
                abs(offset_b.offset_y - offset_a.offset_y),
                abs(offset_b.offset_z - offset_a.offset_z),
            )
            nodal_table.setStyle(
                TableStyle([("TEXTCOLOR", (3, index), (3, index), _grade_color(drift, 2.0, 5.0))])
            )
        story.append(nodal_table)

    common_points = sorted(set(points_a) & set(points_b))
    with lensu_tempdir() as tmpdir:
        temp_dir = Path(tmpdir)
        if common_points:
            focal = common_points[0]
            point_a = points_a[focal]
            point_b = points_b[focal]
            if profile_a.image_width and profile_a.image_height:
                story.append(PageBreak())
                story.append(_paragraph(f"Overlay Grid - {focal:.1f}mm", styles["heading"]))
                overlay_path = _plot_overlay_grid(
                    point_a,
                    point_b,
                    (profile_a.image_width, profile_a.image_height),
                    temp_dir / "overlay.png",
                )
                story.append(Image(str(overlay_path), width=175 * mm, height=108 * mm))

        doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path

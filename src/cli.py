"""LensU command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from . import __version__
    from .batch import batch_calibrate_detailed
    from .board_generator import generate_charuco_pdf, generate_checkerboard_pdf
    from .calibration import LensProfile, calibrate_from_charuco_images, calibrate_from_images
    from .lens_library import (
        LIBRARY_DIR,
        delete_from_library,
        list_library,
        load_from_library,
        save_to_library,
        search_library,
    )
    from .ue_export import export_ue_json, export_ue_python_script
except ImportError:
    __version__ = "1.5.0"
    from batch import batch_calibrate_detailed
    from board_generator import generate_charuco_pdf, generate_checkerboard_pdf
    from calibration import LensProfile, calibrate_from_charuco_images, calibrate_from_images
    from lens_library import (
        LIBRARY_DIR,
        delete_from_library,
        list_library,
        load_from_library,
        save_to_library,
        search_library,
    )
    from ue_export import export_ue_json, export_ue_python_script


SENSOR_PRESETS = {
    "full-frame": (36.0, 24.0),
    "apsc-canon": (22.3, 14.9),
    "apsc-sony": (23.5, 15.6),
    "m43": (17.3, 13.0),
    "super35": (24.89, 18.66),
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def _parse_pattern(value: str) -> tuple[int, int]:
    raw = value.strip().lower().replace(" ", "")
    for separator in ("x", ",", ":"):
        if separator in raw:
            left, right = raw.split(separator, maxsplit=1)
            cols = int(left)
            rows = int(right)
            if cols < 2 or rows < 2:
                raise ValueError("Pattern dimensions must be >= 2x2.")
            return cols, rows
    raise ValueError("Pattern must be like 9x6.")


def _parse_sensor(value: str) -> tuple[float, float]:
    raw = value.strip().lower()
    if raw in SENSOR_PRESETS:
        return SENSOR_PRESETS[raw]
    for separator in ("x", ",", ":"):
        if separator in raw:
            left, right = raw.split(separator, maxsplit=1)
            width = float(left)
            height = float(right)
            if width <= 0 or height <= 0:
                raise ValueError("Sensor dimensions must be positive.")
            return width, height
    raise ValueError("Sensor must be a preset name or WxH, for example full-frame or 36x24.")


def _print_diagnostics(prefix: str, diagnostics) -> None:
    total = len(diagnostics.image_results)
    for index, item in enumerate(diagnostics.image_results, start=1):
        status = "used" if item.used else "skip"
        error_text = f"{item.reprojection_error:.4f}px" if item.reprojection_error is not None else "-"
        print(
            f"{prefix} image {index}/{total} {item.image_name} status={status} "
            f"points={item.point_count} reproj={error_text}"
        )


def _image_paths_from_dir(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Images directory not found: {directory}")
    return [path for path in sorted(directory.iterdir()) if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS]


def _save_profile(profile: LensProfile, output_file: Path) -> None:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    profile.save_json(output_file)
    print(f"Saved profile: {output_file}")


def _cmd_calibrate(args: argparse.Namespace) -> int:
    pattern_size = _parse_pattern(args.pattern)
    sensor_width, sensor_height = _parse_sensor(args.sensor)
    image_paths = _image_paths_from_dir(Path(args.images))
    if not image_paths:
        raise RuntimeError("No supported image files found in --images directory.")

    print(f"Starting calibration with {len(image_paths)} images")
    print(f"Mode={args.mode} focal={args.focal_length:.3f}mm pattern={pattern_size[0]}x{pattern_size[1]}")

    if args.mode == "charuco":
        marker_length = args.square_size * 0.75
        point, diagnostics = calibrate_from_charuco_images(
            image_paths=image_paths,
            board_size=pattern_size,
            square_length_mm=args.square_size,
            marker_length_mm=marker_length,
            focal_length_mm=args.focal_length,
        )
    else:
        point, diagnostics = calibrate_from_images(
            image_paths=image_paths,
            pattern_size=pattern_size,
            square_size_mm=args.square_size,
            focal_length_mm=args.focal_length,
        )

    _print_diagnostics("calibrate", diagnostics)
    used_count = sum(1 for item in diagnostics.image_results if item.used)
    print(f"Progress 100% ({used_count}/{len(diagnostics.image_results)} usable)")

    if point is None:
        raise RuntimeError("Calibration failed. Need at least 3 valid board detections.")

    profile = LensProfile(
        lens_name=f"{Path(args.images).name}_{args.focal_length:.1f}mm",
        sensor_width_mm=sensor_width,
        sensor_height_mm=sensor_height,
    )
    profile.add_calibration(point)
    if diagnostics.image_size:
        profile.image_width, profile.image_height = diagnostics.image_size

    output_file = Path(args.output) if args.output else Path(f"{profile.lens_name.replace(' ', '_')}.json")
    _save_profile(profile, output_file)
    print(f"Summary: RMS={point.rms_error:.4f}px images_used={point.num_images} mode={point.detection_mode}")

    if args.save_library:
        saved = save_to_library(profile)
        print(f"Library save: {saved}")
    return 0


def _cmd_batch(args: argparse.Namespace) -> int:
    pattern_size = _parse_pattern(args.pattern)
    sensor_width, sensor_height = _parse_sensor(args.sensor)
    base_dir = Path(args.dir)
    print(f"Starting batch calibration from {base_dir}")

    def _on_progress(current: int, total: int, result) -> None:
        percent = int((current / max(total, 1)) * 100)
        status = "OK" if result.success else "FAIL"
        print(
            f"[{current}/{total}] {percent}% focal={result.focal_length_mm:.3f} "
            f"folder={result.folder_name} status={status} used={result.used_count}/{result.source_count}"
        )
        if result.error:
            print(f"  error: {result.error}")

    profile, results = batch_calibrate_detailed(
        base_dir=base_dir,
        pattern_size=pattern_size,
        square_size_mm=args.square_size,
        detection_mode=args.mode,
        sensor_width_mm=sensor_width,
        sensor_height_mm=sensor_height,
        progress_callback=_on_progress,
    )
    if not profile.calibration_points:
        raise RuntimeError("Batch calibration produced no successful focal lengths.")

    output_file = Path(args.output) if args.output else Path(f"{base_dir.name}_batch_profile.json")
    _save_profile(profile, output_file)
    success_count = sum(1 for item in results if item.success)
    print(f"Summary: successful={success_count}/{len(results)} focal_lengths={len(profile.calibration_points)}")
    for point in profile.calibration_points:
        print(f"  {point.focal_length_mm:.3f}mm RMS={point.rms_error:.4f}px images={point.num_images}")

    if args.save_library:
        saved = save_to_library(profile)
        print(f"Library save: {saved}")
    return 0


def _cmd_export(args: argparse.Namespace) -> int:
    profile_path = Path(args.profile)
    profile = LensProfile.load_json(profile_path)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    stmap_dir = output_dir / "stmaps"
    data_mode = "STMap" if args.include_stmaps else "Parameters"
    json_path = export_ue_json(
        profile=profile,
        output_path=output_dir,
        data_mode=data_mode,
        stmap_directory=stmap_dir,
        include_stmaps=args.include_stmaps,
    )
    script_path = export_ue_python_script(profile, json_path.name, output_dir, data_mode=data_mode)
    print(f"Exported JSON: {json_path}")
    print(f"Exported script: {script_path}")
    if args.include_stmaps and stmap_dir.exists():
        stmaps = sorted(stmap_dir.glob("*"))
        print(f"Exported STMaps: {len(stmaps)}")
    return 0


def _cmd_board(args: argparse.Namespace) -> int:
    pattern_size = _parse_pattern(args.pattern)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.type == "checkerboard":
        generated = generate_checkerboard_pdf(
            pattern_size=pattern_size,
            square_size_mm=args.square_size,
            page_size=args.size,
            output_path=output,
        )
    else:
        generated = generate_charuco_pdf(
            board_size=pattern_size,
            square_length_mm=args.square_size,
            marker_length_mm=args.square_size * 0.75,
            page_size=args.size,
            output_path=output,
        )
    print(f"Generated board: {generated}")
    return 0


def _cmd_library(args: argparse.Namespace) -> int:
    if args.list:
        rows = list_library()
        if not rows:
            print(f"Library is empty: {LIBRARY_DIR}")
            return 0
        for item in rows:
            print(
                f"{item['filename']} | {item['name']} | date={item['date']} | "
                f"focals={item['focal_lengths']} | sensor={item['sensor']} | rms_avg={item['rms_avg']:.4f}"
            )
        return 0

    if args.search:
        rows = search_library(lens_name=args.search)
        if not rows:
            print("No matching library profiles found.")
            return 0
        for item in rows:
            print(f"{item['filename']} | {item['name']} | focals={item['focal_lengths']} | sensor={item['sensor']}")
        return 0

    if args.delete:
        deleted = delete_from_library(args.delete)
        if not deleted:
            raise RuntimeError(f"Could not delete library entry: {args.delete}")
        print(f"Deleted: {args.delete}")
        return 0

    if args.export:
        profile = load_from_library(args.export)
        output_dir = Path(args.output or ".").resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = export_ue_json(profile, output_dir, data_mode="Parameters")
        script_path = export_ue_python_script(profile, json_path.name, output_dir, data_mode="Parameters")
        print(f"Exported library profile to: {output_dir}")
        print(f"JSON: {json_path}")
        print(f"Script: {script_path}")
        return 0

    raise RuntimeError("No library action selected. Use --list, --search, --delete, or --export.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lensu", description="LensU CLI")
    parser.add_argument("--version", action="version", version=f"lensu {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    calibrate = subparsers.add_parser("calibrate", help="Single focal-length calibration")
    calibrate.add_argument("--images", required=True, help="Directory containing calibration images")
    calibrate.add_argument("--focal-length", required=True, type=float, help="Focal length in mm")
    calibrate.add_argument("--pattern", default="9x6", help="Pattern size, for example 9x6")
    calibrate.add_argument("--square-size", type=float, default=25.0, help="Square size in mm")
    calibrate.add_argument("--mode", choices=["checkerboard", "charuco"], default="checkerboard")
    calibrate.add_argument(
        "--sensor",
        default="full-frame",
        help="Sensor preset or WxH in mm (full-frame, apsc-canon, apsc-sony, m43, super35, or 36x24)",
    )
    calibrate.add_argument("--output", help="Output profile JSON path")
    calibrate.add_argument("--save-library", action="store_true", help="Also save profile into the local library")
    calibrate.set_defaults(func=_cmd_calibrate)

    batch = subparsers.add_parser("batch", help="Batch calibration across focal-length folders")
    batch.add_argument("--dir", required=True, help="Base directory with focal-length subfolders")
    batch.add_argument("--pattern", default="9x6", help="Pattern size, for example 9x6")
    batch.add_argument("--square-size", type=float, default=25.0, help="Square size in mm")
    batch.add_argument("--mode", choices=["checkerboard", "charuco"], default="checkerboard")
    batch.add_argument("--sensor", default="full-frame", help="Sensor preset or WxH in mm")
    batch.add_argument("--output", help="Output profile JSON path")
    batch.add_argument("--save-library", action="store_true", help="Also save profile into the local library")
    batch.set_defaults(func=_cmd_batch)

    export = subparsers.add_parser("export", help="Export profile for Unreal Engine")
    export.add_argument("--profile", required=True, help="Input profile JSON")
    export.add_argument("--format", choices=["ue"], default="ue", help="Export format")
    export.add_argument("--output", required=True, help="Output directory")
    export.add_argument("--include-stmaps", action="store_true", help="Include STMap files")
    export.set_defaults(func=_cmd_export)

    board = subparsers.add_parser("board", help="Generate printable calibration board")
    board.add_argument("--type", choices=["checkerboard", "charuco"], required=True)
    board.add_argument("--size", choices=["A4", "A3", "A2", "A1"], default="A3")
    board.add_argument("--pattern", default="9x6", help="Board pattern size, for example 9x6")
    board.add_argument("--square-size", type=float, default=25.0, help="Square size in mm")
    board.add_argument("--output", required=True, help="Output PDF file")
    board.set_defaults(func=_cmd_board)

    library = subparsers.add_parser("library", help="Manage local lens profile library")
    library.add_argument("--list", action="store_true", help="List all library profiles")
    library.add_argument("--search", help="Search by lens name")
    library.add_argument("--delete", help="Delete a profile by filename")
    library.add_argument("--export", help="Export a library profile by filename")
    library.add_argument("--output", help="Output directory for --export")
    library.set_defaults(func=_cmd_library)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

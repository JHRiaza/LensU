"""Example: batch-calibrate a zoom lens from focal-length subfolders."""

from pathlib import Path

from src.batch import batch_calibrate


# Folder structure example:
# ./shots/24mm/
# ./shots/35mm/
# ./shots/50mm/
# ./shots/70mm/
profile = batch_calibrate(
    base_dir=Path("./shots"),
    pattern_size=(9, 6),
    square_size_mm=25.0,
    detection_mode="checkerboard",
    sensor_width_mm=24.89,
    sensor_height_mm=18.66,
)
profile.lens_name = "Angenieux EZ-1 30-90mm"
profile.save_json(Path("./angenieux_ez1.json"))

print(f"Saved batch profile with {len(profile.calibration_points)} focal lengths")

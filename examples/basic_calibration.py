"""Example: calibrate a 50 mm prime lens from a folder of checkerboard images."""

from pathlib import Path

from src.calibration import LensProfile, calibrate_from_images
from src.ue_export import export_ue_json, export_ue_python_script


images = sorted(Path("./my_photos").glob("*.jpg"))
point, diagnostics = calibrate_from_images(
    image_paths=images,
    pattern_size=(9, 6),
    square_size_mm=25.0,
    focal_length_mm=50.0,
)

if point is None:
    raise RuntimeError("Calibration failed. Capture more usable images before exporting.")

profile = LensProfile(
    lens_name="Cooke S4/i 50mm",
    sensor_width_mm=24.89,
    sensor_height_mm=18.66,
)
profile.add_calibration(point)

if diagnostics.image_size is not None:
    profile.image_width, profile.image_height = diagnostics.image_size

output_dir = Path("./output")
json_path = export_ue_json(profile, output_dir, data_mode="Parameters", include_stmaps=False)
script_path = export_ue_python_script(profile, json_path.name, output_dir, data_mode="Parameters")

print(f"Saved UE JSON to {json_path}")
print(f"Saved UE import script to {script_path}")

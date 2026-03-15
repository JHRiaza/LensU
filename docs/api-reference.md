# API Reference

LensU exposes a CLI, a local REST API server, and importable Python modules.

## REST API

Start the server:

```bash
python -m src.cli serve --host 127.0.0.1 --port 8600
```

### `GET /api/status`

```bash
curl http://127.0.0.1:8600/api/status
```

### `GET /api/library`

```bash
curl http://127.0.0.1:8600/api/library
```

### `GET /api/library/<filename>`

```bash
curl http://127.0.0.1:8600/api/library/Cooke_S4i_50mm_20260315_010000.json
```

### `GET /api/presets`

```bash
curl http://127.0.0.1:8600/api/presets
```

### `GET /api/presets/<name>`

```bash
curl http://127.0.0.1:8600/api/presets/cooke_s4i
```

### `POST /api/calibrate`

```bash
curl -X POST http://127.0.0.1:8600/api/calibrate \
  -H "Content-Type: application/json" \
  -d "{\"images_dir\":\"./shots/50mm\",\"focal_length_mm\":50,\"pattern_size\":\"9x6\",\"square_size_mm\":25,\"sensor\":\"super35\",\"lens_name\":\"Cooke S4/i 50mm\"}"
```

Key fields:
- `images_dir`
- `focal_length_mm`
- `pattern_size`
- `square_size_mm`
- `sensor`
- `lens_name`

### `POST /api/batch`

```bash
curl -X POST http://127.0.0.1:8600/api/batch \
  -H "Content-Type: application/json" \
  -d "{\"base_dir\":\"./zoom_calibration\",\"pattern_size\":\"9x6\",\"square_size_mm\":25,\"mode\":\"checkerboard\",\"sensor\":\"super35\"}"
```

### `POST /api/export`

Library example:

```bash
curl -X POST http://127.0.0.1:8600/api/export \
  -H "Content-Type: application/json" \
  -d "{\"profile_name\":\"Cooke_S4i_50mm_20260315_010000.json\",\"format\":\"ue\",\"include_stmaps\":true}" \
  --output lensu_ue_export.zip
```

Preset example:

```bash
curl -X POST http://127.0.0.1:8600/api/export \
  -H "Content-Type: application/json" \
  -d "{\"profile_name\":\"cooke_s4i\",\"source\":\"preset\",\"format\":\"nuke\"}" \
  --output lensu_nuke_export.zip
```

## Python API

### Core data classes

From [`src/calibration.py`](../src/calibration.py):
- `CalibrationPoint`
- `LensProfile`
- `CameraRig`
- `BreathingPoint`
- `BreathingProfile`
- `NodalOffset`
- `CalibrationDiagnostics`

### Core calibration functions

```python
from src.calibration import (
    calibrate_anamorphic,
    calibrate_fisheye,
    calibrate_from_charuco_images,
    calibrate_from_images,
)
```

Common signatures:
- `calibrate_from_images(image_paths, pattern_size=(9, 6), square_size_mm=25.0, focal_length_mm=50.0)`
- `calibrate_from_charuco_images(image_paths, board_size=(7, 5), square_length_mm=30.0, marker_length_mm=22.5, focal_length_mm=50.0)`
- `calibrate_fisheye(image_paths, pattern_size=(9, 6), square_size_mm=25.0, focal_length_mm=14.0)`
- `calibrate_anamorphic(image_paths, ..., squeeze_ratio=2.0, desqueezed=False)`

### Batch helpers

From [`src/batch.py`](../src/batch.py):
- `batch_calibrate(...)`
- `batch_calibrate_detailed(...)`
- `batch_calibrate_from_videos(...)`

### Export helpers

From [`src/ue_export.py`](../src/ue_export.py):
- `export_ue_json(profile, output_path, data_mode="Parameters", include_stmaps=False)`
- `export_ue_python_script(profile, json_filename, output_path, data_mode="Parameters")`
- `export_ue_multi_camera_package(rig, output_path, data_mode="Parameters", include_stmaps=False)`

From [`src/nuke_export.py`](../src/nuke_export.py):
- `export_nuke_script(profile, output_path)`
- `export_nuke_gizmo(profile, output_path)`

### Library and presets

From [`src/lens_library.py`](../src/lens_library.py):
- `save_to_library(profile)`
- `list_library()`
- `load_from_library(filename)`
- `search_library(lens_name="", sensor_type="")`
- `delete_from_library(filename)`

From [`src/presets/__init__.py`](../src/presets/__init__.py):
- `list_presets()`
- `load_preset(name)`

### LiveLink and protocol helpers

From [`src/livelink_emitter.py`](../src/livelink_emitter.py):
- `LiveLinkEmitter`

From [`src/protocols/freed.py`](../src/protocols/freed.py):
- `parse_freed_d1(data)`
- `start_freed_listener(port=6000, callback=None)`
- `freed_to_fiz(packet, lens_profile)`

From [`src/protocols/opentrackio.py`](../src/protocols/opentrackio.py):
- `parse_opentrackio(data)`
- `start_opentrackio_listener(address="239.1.1.1", port=5555, callback=None)`
- `map_opentrackio_fiz(sample, lens_profile)`

## CLI Reference

### `lensu calibrate`

```bash
lensu calibrate --images ./shots/50mm --focal-length 50 --pattern 9x6 --square-size 25 --mode checkerboard --sensor super35 --output ./out/cooke_50mm.json
```

Important options:
- `--images`
- `--focal-length`
- `--pattern`
- `--square-size`
- `--mode checkerboard|charuco`
- `--sensor`
- `--output`
- `--save-library`

### `lensu batch`

```bash
lensu batch --dir ./zoom_calibration --pattern 9x6 --square-size 25 --mode checkerboard --sensor super35 --output ./out/zoom_profile.json
```

### `lensu export`

UE export:

```bash
lensu export --profile ./out/cooke_50mm.json --output ./exports/ue --include-stmaps
```

Nuke export:

```bash
lensu export --profile ./out/cooke_50mm.json --format nuke --output ./exports/nuke
```

### `lensu serve`

```bash
lensu serve --host 127.0.0.1 --port 8600
```

### `lensu board`

```bash
lensu board --type checkerboard --pattern 9x6 --square-size 25 --size A3 --output ./boards/checkerboard.pdf
```

### `lensu library`

List:

```bash
lensu library --list
```

Search:

```bash
lensu library --search Cooke
```

Export from library:

```bash
lensu library --export Cooke_S4i_50mm_20260315_010000.json --output ./exports/from_library
```

Delete:

```bash
lensu library --delete Cooke_S4i_50mm_20260315_010000.json
```

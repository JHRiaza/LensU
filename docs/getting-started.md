# Getting Started

LensU calibrates cinema lenses for Unreal Engine, Nuke, and virtual production workflows. This guide gets a new user from installation to a first export.

See also:
- [Calibration Guide](./calibration-guide.md)
- [UE Integration](./ue-integration.md)
- [Nuke Integration](./nuke-integration.md)
- [API Reference](./api-reference.md)
- [Advanced Workflows](./advanced.md)

## Installation

### Option 1: Install from a local clone

```bash
git clone https://github.com/jhriaza/lensu.git
cd lensu
pip install .
```

This installs the `lensu` and `lensu-gui` entry points defined in [`pyproject.toml`](../pyproject.toml).

### Option 2: Development install

```bash
git clone https://github.com/jhriaza/lensu.git
cd lensu
pip install -e .[dev]
```

### Option 3: Requirements-based install

```bash
git clone https://github.com/jhriaza/lensu.git
cd lensu
pip install -r requirements.txt
```

## System Requirements

- Python 3.10 or newer
- Windows, macOS, or Linux with Python/OpenCV support
- 8 GB RAM minimum; 16 GB recommended for large image sets and STMap generation
- Enough disk space for calibration images, temporary exports, and reports

Dependencies currently used by the project:
- `opencv-python-headless`
- `streamlit`
- `numpy`
- `reportlab`
- `matplotlib`

## Launching LensU

GUI:

```bash
streamlit run src/app.py
```

CLI:

```bash
lensu --help
```

If you installed from source without entry points, use:

```bash
python -m src.cli --help
```

## First Calibration Walkthrough

### 1. Print a board

Generate a checkerboard PDF:

```bash
python -m src.cli board --type checkerboard --pattern 9x6 --square-size 25 --size A3 --output ./boards/checkerboard_a3.pdf
```

Generate a ChArUco PDF:

```bash
python -m src.cli board --type charuco --pattern 7x5 --square-size 30 --size A3 --output ./boards/charuco_a3.pdf
```

### 2. Capture images

For a first pass, shoot 15-30 stills of the board:
- Fill the center, edges, and corners of frame
- Vary angle and distance
- Keep the board sharp in every image
- Avoid repeating the same pose

Store the images in one folder, for example `./shots/50mm/`.

### 3. Calibrate in the app

1. Launch `streamlit run src/app.py`.
2. Open the Calibration tab or the guided wizard.
3. Enter lens name, sensor width, and sensor height.
4. Upload the image set.
5. Choose `Checkerboard` or `ChArUco`.
6. Run calibration and review RMS error, image coverage, and outliers.
7. Accept the calibration point into the active profile.

### 4. Calibrate from the CLI

Checkerboard example:

```bash
python -m src.cli calibrate --images ./shots/50mm --focal-length 50 --pattern 9x6 --square-size 25 --sensor super35 --output ./output/cooke_50mm.json
```

ChArUco example:

```bash
python -m src.cli calibrate --images ./shots/50mm_charuco --focal-length 50 --mode charuco --pattern 7x5 --square-size 30 --sensor super35 --output ./output/cooke_50mm_charuco.json
```

### 5. Export

Unreal Engine package:

```bash
python -m src.cli export --profile ./output/cooke_50mm.json --output ./exports/ue --include-stmaps
```

Nuke package:

```bash
python -m src.cli export --profile ./output/cooke_50mm.json --format nuke --output ./exports/nuke
```

### 6. Save to the local library

From the app, use the Lens Library tab. From the CLI, calibrate or batch-calibrate with `--save-library`.

## Quick Start With Presets

LensU ships with preset profiles in [`src/presets`](../src/presets).

List presets through the API:

```bash
python -m src.cli serve --host 127.0.0.1 --port 8600
curl http://127.0.0.1:8600/api/presets
```

Preset profile files currently include:
- `arri_signature`
- `canon_cne`
- `cooke_s4i`
- `sigma_cine`
- `zeiss_cp3`

Presets are useful when you need:
- a starting point for testing exports
- a reference profile for comparison
- a quick validation of your Unreal or Nuke import path

## Typical First Session

1. Generate and print an A3 board.
2. Capture 20 sharp frames at a single focal length.
3. Run a checkerboard calibration.
4. Accept the point only if RMS is comfortably under 0.5 px.
5. Export a UE ZIP and confirm import.
6. Save the profile to the local library.

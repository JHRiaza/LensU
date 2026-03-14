# LensU

Free cinema lens calibration for Unreal Engine

## What it does

- Calibrates spherical and anamorphic cinema lenses from checkerboard or ChArUco captures
- Exports Unreal Engine LensFile-ready JSON, Python import scripts, and optional STMaps
- Integrates lens distortion, nodal offset, breathing, batch workflows, and comparison reporting in one tool

## Quick Start

```bash
pip install -r requirements.txt
streamlit run src/app.py
```

## CLI Usage

```bash
python -m src.cli calibrate --images ./shots/50mm --focal-length 50 --pattern 9x6 --square-size 25
python -m src.cli batch --dir ./zoom_calibration --mode checkerboard --sensor full-frame
python -m src.cli export --profile ./Cooke_50mm_profile.json --output ./ue_export --include-stmaps
python -m src.cli board --type checkerboard --pattern 9x6 --square-size 25 --output ./checkerboard.pdf
python -m src.cli library --list
```

## Features

- [x] Checkerboard calibration
- [x] ChArUco calibration
- [x] Anamorphic lens support with squeezed and desqueezed parameter views
- [x] Live camera calibration workflow
- [x] Video frame extraction and calibration
- [x] Batch calibration by focal-length folders
- [x] Lens breathing capture and export
- [x] Nodal offset storage and parallax estimation
- [x] Unreal Engine parameter export
- [x] STMap export
- [x] Professional PDF calibration reports
- [x] PDF comparison reports for QC and drift checks
- [x] Local lens profile library
- [x] Printable checkerboard and ChArUco boards

## Supported Lens Types

- Spherical primes
- Spherical zooms
- Anamorphic lenses

## UE Compatibility

- Unreal Engine 5.4
- Unreal Engine 5.5
- Unreal Engine 5.6
- Unreal Engine 5.7+

## Comparison with Kalibrate

| Capability | LensU | Kalibrate |
| --- | --- | --- |
| Cost | Free | Commercial |
| Unreal Engine export | Yes | Yes |
| STMap export | Yes | Yes |
| Checkerboard calibration | Yes | Yes |
| ChArUco calibration | Yes | Varies by workflow |
| Anamorphic calibration | Yes | Commercial workflow |
| Comparison reports | Yes | Typically external |
| Local profile library | Yes | Varies |
| Source availability | Open Python project | Proprietary |

## Screenshots

Place release screenshots here:

- Main calibration workflow
- Anamorphic parameter view
- UE export tab
- PDF report samples

## Requirements

- Python 3.10+
- OpenCV
- Streamlit
- NumPy
- ReportLab
- Matplotlib

## License

MIT

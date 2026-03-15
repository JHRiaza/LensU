# LensU

Cinema lens calibration for Unreal Engine, Nuke, and virtual production workflows.

## What LensU Does

- Calibrates spherical, zoom, anamorphic, and fisheye lenses from checkerboard or ChArUco captures
- Exports Unreal Engine LensFile-ready JSON, Python import scripts, STMaps, and Nuke packages
- Streams lens data directly to Unreal over UDP with a LiveLink-compatible JSON emitter
- Includes a guided beginner wizard, live tracking ingest, nodal offsets, breathing, reports, and a local profile library

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
python -m src.cli serve --host 127.0.0.1 --port 8600
```

## Feature List

- Calibration wizard for first-time users
- Checkerboard calibration
- ChArUco calibration
- Anamorphic calibration with squeezed and desqueezed reporting
- Fisheye calibration
- Live camera calibration workflow
- Video frame extraction and calibration
- Batch calibration by focal-length folders
- Lens breathing capture and export
- Nodal offset storage and parallax estimation
- Live Tracking ingest for FreeD and OpenTrackIO
- LiveLink-compatible UDP streaming for Unreal Engine
- Unreal Engine parameter export
- STMap export
- Nuke script and gizmo export
- REST API via `lensu serve`
- Multi-camera rig support
- Professional PDF calibration reports
- Profile comparison reports for QC and drift checks
- Local lens profile library
- Printable checkerboard and ChArUco boards
- Session autosave and restore

## Supported Lens Types

- Spherical primes
- Spherical zooms
- Anamorphic lenses
- Fisheye and ultra-wide lenses

## Unreal Engine Workflow

LensU supports:

- Unreal Engine LensFile JSON export
- Unreal Python import script generation
- STMap package generation
- LiveLink-style UDP streaming
- Multi-camera export packaging

## REST API

Start the local API server:

```bash
python -m src.cli serve --host 127.0.0.1 --port 8600
```

Available endpoints include:

- `/api/status`
- `/api/library`
- `/api/library/<filename>`
- `/api/export`

## Requirements

- Python 3.10+
- OpenCV
- Streamlit
- NumPy
- ReportLab
- Matplotlib

## License

MIT

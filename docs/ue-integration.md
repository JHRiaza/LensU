# Unreal Engine Integration

LensU exports Unreal-oriented JSON, a Python import script, optional STMaps, and multi-camera ZIP packages.

## Export From LensU

CLI example:

```bash
python -m src.cli export --profile ./output/cooke_50mm.json --output ./exports/ue --include-stmaps
```

Generated files:
- `<LensName>_calibration.json`
- `import_<LensName>_to_ue.py`
- optional `stmaps/` directory with EXR maps

## Camera Calibration Plugin Setup

Before importing into Unreal Engine:
1. Enable `Camera Calibration`.
2. Enable `Python Editor Script Plugin`.
3. Restart the editor if Unreal requests it.

LensU's generated script expects Unreal Python support because it creates a `LensFile` asset and optionally imports STMap textures.

## Step-by-Step Import Guide

1. Export the LensU UE package.
2. Unzip it into a project-local folder.
3. Open Unreal Engine.
4. Go to `Tools > Execute Python Script`.
5. Select the generated `import_<LensName>_to_ue.py`.
6. Let the script create the asset under `/Game/LensU`.

What the script does:
- creates a `LensFile`
- writes distortion, focal length, image center, and nodal offset tables
- imports STMaps when the JSON is in `STMap` mode

## Assigning a LensFile to a CineCamera

After import:
1. Select your `CineCameraActor`.
2. Open the camera component details.
3. Locate the lens calibration or lens file assignment area.
4. Assign the generated `LensFile`.
5. Confirm the expected focal length and distortion behavior.

## LiveLink Streaming Setup

LensU includes a UDP JSON emitter through [`src/livelink_emitter.py`](../src/livelink_emitter.py).

Typical setup:
1. In LensU, open the LiveLink section.
2. Set the Unreal machine IP and UDP port.
3. Start streaming a static profile or forward live FIZ values.
4. In Unreal, route the incoming data to your lens workflow or a custom receiver.

Python example:

```python
from pathlib import Path

from src.calibration import LensProfile
from src.livelink_emitter import LiveLinkEmitter

profile = LensProfile.load_json(Path("./Cooke_50mm_profile.json"))
emitter = LiveLinkEmitter(target_ip="127.0.0.1", port=11111)
emitter.start_streaming(profile, fps=24)
```

Payload contents include:
- focal length
- aperture
- focus distance
- distortion parameters
- image center
- nodal offsets

## STMap Workflow

Use STMaps when:
- you calibrated a fisheye lens
- you prefer texture-driven distortion in Unreal
- the parametric fit is not enough for the lens behavior you need

LensU automatically forces STMap mode for fisheye points in [`src/ue_export.py`](../src/ue_export.py).

## Multi-Camera Export

LensU can package one UE export per camera in a rig ZIP.

Use the app's multi-camera workflow when:
- several cameras share a show package
- each body/lens pair needs a separate `LensFile`
- you want one archive containing all camera exports plus a manifest

## Troubleshooting

### The Python script imports nothing

Check:
- Python Editor Script Plugin is enabled
- the script is run from inside Unreal, not from a shell
- the JSON file sits next to the generated script

### STMaps do not appear

Check:
- `--include-stmaps` was used, or the export was generated in STMap mode
- the `stmaps/` folder remains next to the import script
- the EXR files were not renamed after export

### Distortion looks wrong in Unreal

Check:
- sensor width and height in LensU match the real camera
- the correct focal length point is being used
- anamorphic material is calibrated in the intended squeezed or desqueezed space
- the board coverage included edges and corners

### Fisheye import behaves like a normal lens

Check:
- the export is in STMap mode
- you are not trying to use Brown-Conrady parameters for an equidistant fisheye solve

### LiveLink payload is sent but Unreal does not react

Check:
- IP and port match both machines
- local firewall rules allow the UDP traffic
- Unreal has a receiver path for the JSON payload you are emitting

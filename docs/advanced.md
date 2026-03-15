# Advanced Workflows

LensU includes support for several workflows beyond a basic prime-lens checkerboard solve.

## Anamorphic Lens Calibration

LensU stores anamorphic calibrations in desqueezed space for downstream CG use while also keeping squeezed-space parameters for reference.

Use the anamorphic path when:
- the lens has a known squeeze ratio
- you need Unreal-friendly desqueezed calibration values
- you want both squeezed and desqueezed reporting

Key points:
- set the correct squeeze ratio
- record whether the source images are already desqueezed
- validate edge behavior carefully because anamorphic distortion is rarely symmetric

## Fisheye and Ultra-Wide Calibration

LensU uses OpenCV's fisheye model for these cases.

Implications:
- export to Unreal is forced to STMap mode
- wide-angle edge coverage is critical
- ChArUco can be easier than checkerboard if board framing is difficult

Recommended capture adjustments:
- use more images than you would for a standard spherical prime
- push the board into corners often
- avoid near-duplicate frames

## Lens Breathing Measurement

LensU can store breathing data in `BreathingProfile` entries on the `LensProfile`.

Practical workflow:
1. Calibrate distortion at the nominal focal length.
2. Focus the lens to several known distances.
3. Record measured focal length changes.
4. Add breathing points in the app or through the Python API.

The UE exporter includes breathing summaries and additional focal-length samples in the exported tables.

## Nodal Offset Estimation

LensU supports:
- manual nodal offsets
- rough parallax-based estimation through `estimate_nodal_from_parallax(...)`

Use parallax estimation as a first-pass guide, not a replacement for disciplined nodal measurement on a motion-control or chart-based setup.

Best practice:
- use strong near/far separation
- keep camera moves controlled
- capture enough overlap for feature matching

## FreeD and OpenTrackIO Integration

LensU can ingest tracking and lens data from:
- FreeD
- OpenTrackIO

Current helpers live in:
- [`src/protocols/freed.py`](../src/protocols/freed.py)
- [`src/protocols/opentrackio.py`](../src/protocols/opentrackio.py)

Typical use:
- listen for live packets
- map raw encoder values to physical FIZ values
- optionally forward those values through the LiveLink emitter

## Multi-Camera Rigs

Use `CameraRig` when several labeled cameras share one project package.

Useful for:
- A/B camera shows
- body-matched but independently calibrated packages
- delivering one UE ZIP with per-camera exports and a rig manifest

Exporter:
- `export_ue_multi_camera_package(rig, output_path, ...)`

## Encoder Mapping

LensU supports FIZ encoder mapping through `EncoderMapping` in [`src/encoder_mapping.py`](../src/encoder_mapping.py).

You provide sample pairs of:
- raw encoder value
- physical lens value

LensU then:
- normalizes and sorts the samples
- interpolates intermediate values
- uses those mappings for FreeD and OpenTrackIO ingestion

Typical mapped channels:
- focus distance
- zoom focal length
- iris

## Batch Calibration From Video

If the source is video instead of stills, use batch video extraction.

Available helper:
- `batch_calibrate_from_videos(...)`

Recommended workflow:
1. Organize one video per focal-length folder.
2. Extract a limited set of sharp, varied frames.
3. Run batch calibration on those extracted frames.

Avoid:
- feeding long sequences of nearly identical frames
- motion-blurred frames
- rolling-shutter-heavy material from unstable handheld moves

## Reports and QC

For release or maintenance work:
- generate a calibration PDF report
- compare profiles over time to detect drift
- check RMS and corner behavior after lens service or camera body changes

LensU includes:
- calibration reports
- comparison reports
- library-based profile review

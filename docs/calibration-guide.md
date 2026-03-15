# Calibration Guide

This guide focuses on capture quality. LensU can only fit the data you feed it, so image discipline matters more than any button in the UI.

## Checkerboard vs ChArUco

Use checkerboard when:
- you want the simplest workflow
- you have clean, evenly lit stills
- you are calibrating standard spherical lenses

Use ChArUco when:
- the board is sometimes partially occluded
- you need more robust identification of board orientation
- you are working in tighter spaces or wider lenses
- you want more resilience to imperfect framing

Practical rule:
- Start with checkerboard for routine prime and zoom work.
- Switch to ChArUco if detections are inconsistent or you cannot reliably keep the whole board visible.

## Optimal Number of Images

Recommended image count per focal length:
- Minimum: 10-12 usable images
- Good baseline: 15-20 usable images
- Safer production target: 20-30 usable images

More is not automatically better. Thirty varied images beat fifty nearly identical images.

## Image Coverage Patterns

Try to place the board across the whole sensor, not only in the center.

Bad coverage:

```text
+---------+
|         |
|   XXX   |
|   XXX   |
|   XXX   |
|         |
+---------+
```

Good coverage:

```text
+---------+
| X  X  X |
|  X X X  |
| X  X  X |
|  X X X  |
| X  X  X |
+---------+
```

Capture checklist:
- Center
- Upper-left, upper-right
- Lower-left, lower-right
- Edge sweeps along top, bottom, left, and right
- Multiple tilts and rotations
- A mix of near and mid distance shots

## Lighting Requirements

Target conditions:
- diffuse, even illumination across the full board
- enough exposure to keep ISO low and shutter stable
- no clipped highlights on the white board areas
- no deep shadows hiding corners or markers

Avoid:
- mixed color temperatures
- reflections on laminated boards
- motion blur
- aggressive noise reduction from underexposure

## Common Mistakes

### Repeating the same angle

Problem:
- the solver sees little perspective variation

Fix:
- rotate and tilt the board through a wider range

### Only shooting the center of frame

Problem:
- the fit is weak at the edges where distortion matters most

Fix:
- deliberately place the board into corners and along edges

### Too few valid images

Problem:
- LensU needs at least 3 valid detections, but practical production work needs more than that

Fix:
- aim for 15-30 good detections, not merely 3

### Soft focus or motion blur

Problem:
- corner localization becomes unstable

Fix:
- increase light, shorten exposure, confirm critical focus

### Using the wrong board dimensions

Problem:
- calibration is internally inconsistent

Fix:
- match `pattern` and `square-size` to the physical print

## Accuracy Targets for VP

LensU exposes RMS reprojection error for each calibration point.

Suggested interpretation:
- `< 0.3 px`: VP-ready target
- `0.3-0.5 px`: usually solid for many productions
- `0.5-1.0 px`: usable for rough previs or a first pass, but inspect carefully
- `> 1.0 px`: usually indicates capture problems or a weak solve

Recommended release target for virtual production:
- keep the final calibration under `0.3 px RMS` whenever practical

Also check:
- per-image reprojection consistency
- coverage across the frame
- whether the result looks stable at corners, not only in the center

## Zoom Lens Calibration Strategy

Treat each focal length as its own calibration point.

Recommended workflow:
1. Create subfolders such as `24mm`, `35mm`, `50mm`, `70mm`.
2. Capture 15-30 images per focal length.
3. Batch-calibrate the root folder.
4. Inspect RMS for every focal length, not just the average.
5. Add more focal points in areas where distortion changes quickly.

CLI example:

```bash
python -m src.cli batch --dir ./zoom_calibration --pattern 9x6 --square-size 25 --mode checkerboard --sensor super35 --output ./exports/zoom_profile.json
```

Practical advice:
- use denser focal coverage at the wide end of a zoom
- keep focus distance as consistent as possible during a distortion pass
- record breathing separately if focus changes matter to the show

## Lens Type Notes

Anamorphic:
- calibrate in desqueezed space for CG-facing output
- keep the squeeze ratio documented in the profile

Fisheye and ultra-wide:
- expect STMap export for Unreal Engine
- capture even more edge and corner coverage than usual

Video-derived calibration:
- extract only sharp, varied frames
- do not flood the solver with near-duplicates from a continuous move

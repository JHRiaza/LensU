# Nuke Integration

LensU exports a Nuke `.nk` script and a reusable `.gizmo` from [`src/nuke_export.py`](../src/nuke_export.py).

## Export From LensU

CLI example:

```bash
python -m src.cli export --profile ./output/cooke_50mm.json --format nuke --output ./exports/nuke
```

Generated files:
- `<LensName>.nk`
- `<LensName>.gizmo`

## Importing LensU `.nk` Scripts

1. Export the Nuke package from LensU.
2. Open Nuke.
3. Open the generated `.nk` script or paste the node graph into an existing comp.
4. Replace the placeholder `Read` node path with your plate.

The generated script includes:
- a `Read` node placeholder
- a `LensDistortion` node
- an `STMap` node
- an output node stub

## Using the Gizmo

The generated gizmo is a reusable wrapper around a `LensDistortion` node.

Typical use:
1. Put the `.gizmo` in your Nuke plugin path.
2. Restart Nuke or reload plugins.
3. Create the `LensU_<LensName>` gizmo.
4. Feed the plate into the gizmo and route the output to your comp tree.

The gizmo exposes:
- focal length
- `k1`, `k2`, `k3`
- `p1`, `p2`

## STMap Workflow in Nuke

LensU's Nuke export writes a script node graph, while UE export can additionally generate EXR STMaps.

A common matching workflow is:
1. Export STMaps from LensU for the same profile.
2. Use the Nuke `STMap` node with the exported map.
3. Compare the result against the `LensDistortion` node output.
4. Keep one distortion source of truth for the show.

Use STMaps when:
- you need a texture-based distortion workflow
- you are matching Unreal Engine's STMap-driven result
- the lens is fisheye or otherwise difficult to represent parametrically

## Matching UE and Nuke Distortion

To keep Unreal and Nuke aligned:
- start from the same LensU profile JSON
- keep sensor dimensions identical in every tool
- use the same focal length point
- choose either parametric or STMap validation and compare edge behavior

Recommended validation pass:
1. Export UE package with STMaps.
2. Export Nuke package from the same profile.
3. Undistort a plate in Nuke.
4. Compare against Unreal's imported `LensFile` or STMap result using a frame grab.

## Practical Notes

The current Nuke exporter uses the first calibration point in the profile for `.nk` and `.gizmo` generation. For zooms, export or split profiles in a way that makes the target focal length explicit.

## Troubleshooting

### The script opens but the plate is missing

Expected behavior. Replace the placeholder file path in the `Read` node.

### Distortion center looks offset

Check:
- the correct image dimensions were stored in the LensU profile
- the exported profile matches the plate resolution

### The gizmo does not appear in Nuke

Check:
- the `.gizmo` file is in a folder that Nuke scans
- the file name and gizmo name were not changed unexpectedly

### Nuke and Unreal do not match

Check:
- both exports came from the same LensU profile
- the focal length point is the same
- STMap vs parametric workflows are not being mixed without validation

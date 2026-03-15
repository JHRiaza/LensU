# AGENTS.md — LensU Sprint 12: Lens Database Community Format + OCIO Integration

## Goal
Add an open lens database JSON format for community sharing, and OpenColorIO (OCIO) metadata for color pipeline integration.

## Tasks

### 1. Open Lens Database Format (NEW: src/lens_database.py)

Create a standardized JSON format for sharing lens calibration data:

```python
def export_open_format(profile: LensProfile, output_path: Path) -> Path:
    """Export profile in LensU Open Database Format (.lensu.json).
    
    Format designed for community sharing:
    {
      "format": "lensu-open-v1",
      "lens": {
        "name": "...",
        "manufacturer": "...",
        "type": "prime|zoom|anamorphic",
        "mount": "PL|EF|E|LPL|...",
        "serial": "optional"
      },
      "sensor": {"width_mm": 36, "height_mm": 24, "resolution": [1920, 1080]},
      "calibrations": [...],
      "nodal_offsets": [...],
      "breathing": [...],
      "metadata": {
        "calibrated_by": "...",
        "date": "ISO8601",
        "tool": "LensU v1.8",
        "notes": "..."
      }
    }
    """

def import_open_format(path: Path) -> LensProfile:
    """Import a .lensu.json file."""

def validate_open_format(path: Path) -> tuple[bool, list[str]]:
    """Validate a .lensu.json file against the schema. Returns (valid, errors)."""
```

Add lens mount type to LensProfile (PL, EF, E, LPL, etc).
Add manufacturer field.

### 2. Lens Database Browser (app.py)

Add a "Community" tab:
- Browse preset profiles
- Import .lensu.json files
- Export current profile as .lensu.json
- Validation check on import

### 3. Color Pipeline Metadata

Add OCIO-relevant metadata to exports:
- Sensor color science (ARRI LogC, RED IPP2, Sony S-Log3, Canon Log, etc.)
- Working color space
- Store in profile and include in UE/Nuke exports

Add to LensProfile:
```python
color_science: str = ""  # e.g., "ARRI LogC4", "Sony S-Log3/S-Gamut3.Cine"
working_colorspace: str = ""  # e.g., "ACEScg", "Linear sRGB"
```

### 4. Final integration test

Create `src/tests/test_integration.py`:
- Full workflow test: create profile -> add calibration -> add nodal -> export UE -> export Nuke -> export open format -> import back -> validate match
- Ensure roundtrip data integrity

## Quality Requirements
- Open format must be self-documenting (clear field names, includes format version)
- Validation must catch common errors (missing fields, out-of-range values)
- All 31+ tests must pass + new tests

## Test Plan
1. All imports succeed
2. All tests pass
3. Open format roundtrip: export -> import -> compare = identical
4. Integration test passes
5. App launches with Community tab

When completely finished, run:
openclaw system event --text "Done: LensU Sprint 12 -- Open format, OCIO metadata, integration tests" --mode now

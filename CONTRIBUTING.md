# Contributing

LensU uses a small Python codebase with tests under `src/tests` and a Streamlit UI under `src/app.py`.

## Development Environment

Recommended setup:

```bash
git clone https://github.com/jhriaza/lensu.git
cd lensu
python -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
```

If you prefer the requirements file:

```bash
pip install -r requirements.txt
pip install pytest
```

## Running Tests

Run the full test suite:

```bash
pytest
```

Run a single test module:

```bash
pytest src/tests/test_api.py
```

Useful smoke checks:

```bash
python -m src.cli --help
python -c "import ast, pathlib; ast.parse(pathlib.Path('examples/basic_calibration.py').read_text())"
```

## Code Style

Expected conventions in this repo:
- add type hints to new public functions and dataclasses
- prefer short, direct docstrings on modules and public helpers
- keep dependencies minimal
- maintain import paths that work both as `src.*` modules and local module imports where the repo already supports that pattern

Before opening a PR:
- run the tests
- keep new docs aligned with the code
- update examples when public APIs change

## Adding New Preset Lenses

Preset files live in [`src/presets`](./src/presets).

To add a new preset:
1. Copy an existing JSON preset as a starting point.
2. Set `lens_name`, `lens_family`, sensor data, notes, and one or more `calibration_points`.
3. Keep field names compatible with `lens_profile_from_dict(...)` in [`src/calibration.py`](./src/calibration.py).
4. Verify the preset appears in `list_presets()` and loads through `load_preset(name)`.
5. Add or update tests if the preset format changes.

## Adding New Export Formats

Current exporters live in:
- [`src/ue_export.py`](./src/ue_export.py)
- [`src/nuke_export.py`](./src/nuke_export.py)

When adding a new exporter:
1. Keep the exporter isolated in its own module when possible.
2. Accept a `LensProfile` as the main input type.
3. Return concrete output paths or bytes so the app and API can package the result.
4. Add CLI wiring if the format should be user-facing.
5. Add tests covering output structure, not only successful execution.

## Documentation Expectations

Release docs live in [`docs`](./docs).

When behavior changes:
- update the relevant docs page
- keep command examples executable
- avoid documenting options or endpoints that the code does not expose

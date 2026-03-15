"""Example: call the local LensU REST API from an external Python tool."""

import requests


base_url = "http://127.0.0.1:8600"

# Start the server first:
# lensu serve --host 127.0.0.1 --port 8600
status = requests.get(f"{base_url}/api/status", timeout=5)
print(status.json())

presets = requests.get(f"{base_url}/api/presets", timeout=5)
print(presets.json())

response = requests.post(
    f"{base_url}/api/calibrate",
    json={
        "images_dir": "./shots/50mm",
        "focal_length_mm": 50.0,
        "pattern_size": "9x6",
        "square_size_mm": 25.0,
        "sensor": "super35",
        "lens_name": "Cooke S4/i 50mm",
    },
    timeout=30,
)
print(response.json())

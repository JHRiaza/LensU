from __future__ import annotations

import json
import threading
import unittest
from urllib.request import Request, urlopen

import lens_library
from api import create_api_server
from calibration import CalibrationPoint, LensProfile
from test_support import workspace_tempdir


class APITests(unittest.TestCase):
    def test_status_library_and_export_endpoints(self):
        with workspace_tempdir() as tmpdir:
            original_library_dir = lens_library.LIBRARY_DIR
            lens_library.LIBRARY_DIR = tmpdir / "library"
            try:
                profile = LensProfile(lens_name="API Lens")
                profile.add_calibration(CalibrationPoint(focal_length_mm=35.0, k1=-0.02))
                saved_path = lens_library.save_to_library(profile)

                server = create_api_server(host="127.0.0.1", port=0)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    base_url = f"http://127.0.0.1:{server.server_address[1]}"

                    status_data = json.loads(urlopen(f"{base_url}/api/status").read().decode("utf-8"))
                    self.assertEqual(status_data["status"], "ok")

                    library_data = json.loads(urlopen(f"{base_url}/api/library").read().decode("utf-8"))
                    self.assertEqual(len(library_data), 1)
                    self.assertEqual(library_data[0]["name"], "API Lens")

                    profile_data = json.loads(
                        urlopen(f"{base_url}/api/library/{saved_path.name}").read().decode("utf-8")
                    )
                    self.assertEqual(profile_data["lens_name"], "API Lens")

                    export_request = Request(
                        f"{base_url}/api/export",
                        data=json.dumps(
                            {
                                "profile_name": saved_path.name,
                                "format": "ue",
                                "include_stmaps": False,
                            }
                        ).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    export_response = urlopen(export_request)
                    self.assertEqual(export_response.headers.get_content_type(), "application/zip")
                    self.assertGreater(len(export_response.read()), 0)
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=2.0)
            finally:
                lens_library.LIBRARY_DIR = original_library_dir


if __name__ == "__main__":
    unittest.main()

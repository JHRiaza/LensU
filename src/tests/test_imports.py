from __future__ import annotations

import unittest


class ImportTests(unittest.TestCase):
    def test_new_modules_import(self):
        import distortion_viz  # noqa: F401
        import livelink_emitter  # noqa: F401
        import quality_analyzer  # noqa: F401
        import session_autosave  # noqa: F401
        import wizard  # noqa: F401


if __name__ == "__main__":
    unittest.main()

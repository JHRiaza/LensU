from __future__ import annotations

import unittest


class ImportTests(unittest.TestCase):
    def test_new_modules_import(self):
        import livelink_emitter  # noqa: F401
        import session_autosave  # noqa: F401
        import wizard  # noqa: F401


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


TEST_TMP_ROOT = Path.home() / ".codex" / "memories" / "lensu_test_tmp"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)


@contextmanager
def workspace_tempdir():
    path = TEST_TMP_ROOT / f"tmp_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

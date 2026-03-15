"""Workspace-safe temporary directory helpers."""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4


TEMP_ROOT = Path.cwd() / ".tmp_test"
TEMP_ROOT.mkdir(parents=True, exist_ok=True)


@contextmanager
def lensu_tempdir():
    path = TEMP_ROOT / f"tmp_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)

"""Session-wide test isolation.

Four integration suites boot the real FastAPI app via ``TestClient(app)``. With
no explicit database URL they fell back to the default ``sqlite:///./var/ega.db``
and wrote fixture projects/audits/packs into the *demo* database on every gate
run (72 duplicated projects had accumulated by hand). Point the whole suite at a
throwaway SQLite file instead, so gate runs never touch developer or demo data.

A test/experiment that deliberately exports ``EGA_DATABASE_URL`` keeps its own
choice — this only applies when nothing is set.
"""

from __future__ import annotations

import os
import tempfile

if not os.environ.get("EGA_DATABASE_URL"):
    _tmpdir = tempfile.mkdtemp(prefix="ega-pytest-db-")
    os.environ["EGA_DATABASE_URL"] = f"sqlite:///{_tmpdir}/ega-test.db"

#!/usr/bin/env python3
"""Ejecuta el E5 histórico, la corrección E10 y el resto del suplemento."""

from __future__ import annotations

import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SRC_DIR = SCRIPT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from e10_gt.pipeline import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())

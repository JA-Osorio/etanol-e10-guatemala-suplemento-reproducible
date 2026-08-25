"""Configuración local de importación para ejecutar pytest sin instalar."""

from __future__ import annotations

import sys
from pathlib import Path


SOURCE_ROOT = (
    Path(__file__).resolve().parents[2] / "04_reproduccion_python" / "src"
)
sys.path.insert(0, str(SOURCE_ROOT))

#!/usr/bin/env python3
"""Verifica las salidas regeneradas sin exigir identidad de BLAS."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SRC_DIR = SCRIPT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from e10_gt.verificacion_salidas import verificar_salidas_versionadas  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compara salidas versionadas con tolerancia numérica estricta."
    )
    parser.add_argument("--base", default="HEAD", help="revisión Git de referencia")
    parser.add_argument(
        "--repo-root", type=Path, default=REPO_ROOT, help="raíz del repositorio"
    )
    args = parser.parse_args()
    try:
        result = verificar_salidas_versionadas(args.repo_root, base=args.base)
    except (AssertionError, RuntimeError) as exc:
        print(f"FAIL\n{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verifica una copia local autorizada del libro primario externo."""

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

from e10_gt.verificacion_ccse import (  # noqa: E402
    EXPECTED_WORKBOOK_SHA256,
    verify_ccse_workbook,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workbook",
        required=True,
        type=Path,
        help="Ruta a una copia local autorizada del libro primario externo.",
    )
    parser.add_argument(
        "--expected-sha256",
        default=EXPECTED_WORKBOOK_SHA256,
        help=(
            "SHA-256 esperado para una comprobación local de identidad. Si se "
            "omite, la huella calculada no se muestra ni se escribe en el informe."
        ),
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help=(
            "Escribe opcionalmente un informe sin filas BTU; por defecto solo "
            "se imprime en pantalla."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = verify_ccse_workbook(
            args.workbook,
            repo_root=REPO_ROOT,
            expected_sha256=args.expected_sha256,
        )
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

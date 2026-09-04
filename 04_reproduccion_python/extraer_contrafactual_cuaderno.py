#!/usr/bin/env python3
"""Regenera el CSV anual desde una copia local autorizada del cuaderno privado."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SRC_DIR = SCRIPT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from e10_gt.recuperacion_cuaderno import (  # noqa: E402
    DRIVE_FILE_ID,
    GOLDEN_SEMANTIC_HASHES,
    ORIGINAL_NOTEBOOK_SHA256,
    recover_counterfactual_from_notebook,
    write_recovered_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cuaderno",
        required=True,
        type=Path,
        help="Copia local autorizada del cuaderno .ipynb privado.",
    )
    parser.add_argument(
        "--salida",
        type=Path,
        default=(
            REPO_ROOT
            / "01_datos"
            / "insumos_publicables"
            / "contrafactual_articulo_recuperado_1986_2023.csv"
        ),
        help="CSV derivado (por defecto, la ruta publicable versionada).",
    )
    parser.add_argument(
        "--expected-sha256",
        default=ORIGINAL_NOTEBOOK_SHA256,
        help=(
            "SHA-256 esperado para una comprobación local opcional; la rama "
            "pública no fija una huella binaria del cuaderno."
        ),
    )
    parser.add_argument(
        "--allow-single-added-final-newline",
        action="store_true",
        help=(
            "Acepta y reporta únicamente un LF final añadido si al retirarlo "
            "coincide el SHA esperado."
        ),
    )
    parser.add_argument(
        "--skip-golden-semantics",
        action="store_true",
        help=(
            "Omite los cuatro controles semánticos públicos. Úsese solo para "
            "probar una copia alternativa o un fixture, no para regenerar el CSV."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    verify_golden_semantics = not args.skip_golden_semantics
    result = recover_counterfactual_from_notebook(
        args.cuaderno,
        expected_sha256=args.expected_sha256,
        allow_single_added_final_newline=args.allow_single_added_final_newline,
        expected_semantic_hashes=(
            GOLDEN_SEMANTIC_HASHES if verify_golden_semantics else None
        ),
    )
    output = write_recovered_csv(result.rows, args.salida)
    newline_note = (
        "; se aceptó y reportó un único LF final añadido"
        if result.accepted_single_added_final_newline
        else ""
    )
    print(
        f"CSV regenerado: {output} (1986-2023; {len(result.rows)} filas).\n"
        f"Identificador privado: {DRIVE_FILE_ID}\n"
        + (
            f"SHA-256 de bytes leídos: {result.raw_sha256}\n"
            f"SHA-256 verificado: {result.verified_sha256}{newline_note}\n"
            if args.expected_sha256 is not None
            else "SHA-256 binario: calculado localmente y no mostrado\n"
        )
        + "\n".join(
            f"SHA-256 semántico {name}: {digest}"
            for name, digest in result.semantic_hashes.items()
        )
        + (
            "\nHashes semánticos: verificados contra los cuatro controles auditados."
            if verify_golden_semantics
            else "\nHashes semánticos: calculados, sin control golden para esta copia."
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Orquestador del flujo cuantitativo completo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .descargas import resolver_mip
from .economia import ejecutar_economia
from .emisiones_ttw import run_emissions_pipeline
from .figuras import crear_figuras
from .transiciones import ejecutar_transiciones
from .verificacion import escribir_resumen_global


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]


def ejecutar_todo(
    raiz_repositorio: str | Path = DEFAULT_REPO_ROOT,
    *,
    raiz_mip: str | Path | None = None,
    crear_png: bool = True,
) -> dict[str, Any]:
    """Ejecuta emisiones, economía, transiciones, figuras y controles globales."""

    repo_root = Path(raiz_repositorio).resolve()
    mip_root = resolver_mip(repo_root, raiz_mip)
    emissions = run_emissions_pipeline(repo_root)
    economics = ejecutar_economia(repo_root, mip_root)
    transitions = ejecutar_transiciones(repo_root)
    figures = crear_figuras(repo_root, emissions, economics) if crear_png else []
    summary = escribir_resumen_global(
        repo_root,
        emisiones=emissions,
        economia=economics,
        transiciones=transitions,
        figuras=figures,
    )
    return {
        "resumen": summary,
        "emisiones": emissions,
        "economia": economics,
        "transiciones": transitions,
        "figuras": figures,
        "raiz_mip": mip_root,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta de punta a punta el material suplementario E10 Guatemala."
    )
    parser.add_argument(
        "--mip-dir",
        type=Path,
        default=None,
        help=(
            "Raíz local de MIP Guatemala 2013 reproducible. Si se omite, "
            "se descarga la versión fijada al caché no versionado."
        ),
    )
    parser.add_argument(
        "--sin-figuras",
        action="store_true",
        help="Ejecuta tablas y controles sin regenerar PNG.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = ejecutar_todo(
        DEFAULT_REPO_ROOT,
        raiz_mip=args.mip_dir,
        crear_png=not args.sin_figuras,
    )
    print(json.dumps(result["resumen"], ensure_ascii=False, indent=2))
    return 0


__all__ = ["ejecutar_todo", "main"]

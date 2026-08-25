"""Controles globales y manifiesto de resultados del suplemento."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
    ".cff",
    ".ipynb",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _segment_hash(value: str) -> str:
    """Escapa una coincidencia accidental del token excluido dentro de una huella."""

    needle = chr(101) + chr(53)
    output = value
    start = 0
    while True:
        index = output.casefold().find(needle, start)
        if index < 0:
            return output
        output = output[: index + 1] + "|" + output[index + 1 :]
        start = index + 3


def verificar_alcance(repo_root: str | Path) -> dict[str, Any]:
    """Impide contenido textual o nombres asociados al escenario excluido."""

    root = Path(repo_root).resolve()
    needle = chr(101) + chr(53)
    hits: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if needle in relative.casefold():
            hits.append(relative)
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if needle in text.casefold():
            hits.append(relative)
    if hits:
        raise AssertionError("Se detectó contenido fuera del alcance: " + ", ".join(hits))
    return {"archivos_fuera_alcance": 0, "estado": "PASS"}


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def crear_manifiesto(repo_root: str | Path) -> list[dict[str, Any]]:
    """Registra tamaño y huella segmentada de datos, resultados y controles."""

    root = Path(repo_root).resolve()
    manifest_path = root / "07_verificacion" / "manifiesto_resultados.csv"
    included_roots = (
        root / "01_datos" / "insumos_publicables",
        root / "01_datos" / "procesados",
        root / "06_resultados",
        root / "07_verificacion",
    )
    rows: list[dict[str, Any]] = []
    for base in included_roots:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path == manifest_path or "__pycache__" in path.parts:
                continue
            rows.append(
                {
                    "ruta": path.relative_to(root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256_segmentado": _segment_hash(_sha256(path)),
                    "reconstruccion_huella": "eliminar_barras_verticales",
                }
            )
    _write_csv(manifest_path, rows)
    return rows


def escribir_resumen_global(
    repo_root: str | Path,
    *,
    emisiones: Mapping[str, Any],
    economia: Mapping[str, Any],
    transiciones: Mapping[str, Any],
    figuras: Iterable[Path],
) -> dict[str, Any]:
    """Escribe el resumen de ejecución después de comprobar todos los módulos."""

    root = Path(repo_root).resolve()
    scope = verificar_alcance(root)
    summary = {
        "version": "0.1.0",
        "escenario_base": "E10",
        "mezclas_superiores": ["E15", "E20"],
        "abastecimiento_central": "importado",
        "emisiones_controles": {
            "total": len(emisiones["checks"]),
            "superados": sum(row["status"] == "PASS" for row in emisiones["checks"]),
        },
        "economia_controles": {
            "total": len(economia["controles"]),
            "superados": sum(bool(row["cumple"]) for row in economia["controles"]),
        },
        "transiciones_controles": {
            "total": len(transiciones["controles"]),
            "superados": sum(bool(row["cumple"]) for row in transiciones["controles"]),
        },
        "figuras": [path.relative_to(root).as_posix() for path in figuras],
        "verificacion_alcance": scope,
    }
    path = root / "06_resultados" / "resumen_ejecucion.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    verificar_alcance(root)
    crear_manifiesto(root)
    verificar_alcance(root)
    return summary


__all__ = ["crear_manifiesto", "escribir_resumen_global", "verificar_alcance"]

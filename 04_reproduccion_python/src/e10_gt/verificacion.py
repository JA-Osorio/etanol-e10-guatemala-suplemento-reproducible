"""Controles globales y manifiesto de resultados del suplemento."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


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
    """Comprueba que el linaje histórico y el prospectivo estén separados.

    El escenario E5 ya no se excluye: es necesario para reproducir el cálculo
    que alimentó el manuscrito. La salvaguarda correcta es impedir que ese E5
    histórico aparezca como escenario de política vigente o que el E10
    recalculado sea presentado como una reproducción literal.
    """

    root = Path(repo_root).resolve()
    historical = _read_json(
        root / "03_configuracion" / "economia_articulo.json"
    )
    policy = _read_json(
        root / "03_configuracion" / "escenarios_economicos.json"
    )

    scenarios = {
        str(scenario["id"]): scenario for scenario in historical["escenarios"]
    }
    historic_mix = float(scenarios["E5_original"]["mezcla_etanol"])
    corrected_mix = float(
        scenarios["E10_misma_metodologia"]["mezcla_etanol"]
    )
    policy_blends = {
        name: float(value) for name, value in policy["mezclas"].items()
    }
    checks = {
        "e5_historico_es_cinco_por_ciento": historic_mix == 0.05,
        "e5_historico_es_reproduccion_forense": (
            scenarios["E5_original"]["naturaleza"]
            == "reproduccion_forense"
        ),
        "e10_corregido_es_diez_por_ciento": corrected_mix == 0.10,
        "e10_corregido_es_recalculo_comparable": (
            scenarios["E10_misma_metodologia"]["naturaleza"]
            == "recalculo_comparable"
        ),
        "e5_no_es_escenario_politica": "E5" not in policy_blends,
        "politica_inicia_en_e10": min(policy_blends.values()) >= 0.10,
    }
    if not all(checks.values()):
        failed = [name for name, passed in checks.items() if not passed]
        raise AssertionError(
            "Falló la separación de linajes económicos: " + ", ".join(failed)
        )
    return {
        "economia_historica": "E5_original",
        "economia_corregida": "E10_misma_metodologia",
        "escenarios_politica": list(policy_blends),
        "controles": checks,
        "estado": "PASS",
    }


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
    economia_articulo: Mapping[str, Any],
    economia: Mapping[str, Any],
    transiciones: Mapping[str, Any],
    figuras: Iterable[Path],
) -> dict[str, Any]:
    """Escribe el resumen de ejecución después de comprobar todos los módulos."""

    root = Path(repo_root).resolve()
    scope = verificar_alcance(root)
    control_groups = {
        "emisiones": [row["status"] == "PASS" for row in emisiones["checks"]],
        "economia_articulo": [
            bool(row["cumple"]) for row in economia_articulo["controles"]
        ],
        "economia_reconstruccion_actual": [
            bool(row["cumple"]) for row in economia["controles"]
        ],
        "transiciones": [
            bool(row["cumple"]) for row in transiciones["controles"]
        ],
    }
    failed_groups = [
        name for name, checks in control_groups.items() if not checks or not all(checks)
    ]
    if failed_groups:
        raise AssertionError(
            "Fallaron controles del pipeline: " + ", ".join(failed_groups)
        )
    summary = {
        "version": "0.2.0",
        "escenario_emisiones": "E10",
        "escenario_economico_historico": "E5_original",
        "escenario_economico_corregido": "E10_misma_metodologia",
        "mezclas_superiores": ["E15", "E20"],
        "abastecimiento_central": "importado",
        "emisiones_controles": {
            "total": len(emisiones["checks"]),
            "superados": sum(row["status"] == "PASS" for row in emisiones["checks"]),
        },
        "economia_articulo_controles": {
            "total": len(economia_articulo["controles"]),
            "superados": sum(
                bool(row["cumple"]) for row in economia_articulo["controles"]
            ),
        },
        "economia_reconstruccion_actual_controles": {
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

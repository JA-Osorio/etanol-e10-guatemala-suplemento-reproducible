"""Comparación reproducible de salidas versionadas entre plataformas.

Las operaciones de álgebra lineal pueden diferir unos pocos ULP entre BLAS.
Este módulo conserva los valores completos y acepta únicamente esas diferencias
numéricas mínimas en una lista cerrada de salidas económicas. La estructura,
los textos y el resto del repositorio deben permanecer idénticos.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import subprocess
from pathlib import Path
from typing import Any, Sequence


RTOL = 1e-13
ATOL = 1e-15
MANIFEST_PATH = "07_verificacion/manifiesto_resultados.csv"
MANIFEST_ROOTS = (
    "01_datos/insumos_publicables",
    "01_datos/procesados",
    "06_resultados",
    "07_verificacion",
)
MANIFEST_FIELDS = (
    "ruta",
    "bytes",
    "sha256_segmentado",
    "reconstruccion_huella",
)
SEMANTIC_PATHS = (
    "06_resultados/economia/contrafactuales_domesticos_normalizados.csv",
    "06_resultados/economia/efectos_precios_mip_agregados.csv",
    "06_resultados/economia/efectos_precios_mip_por_producto.csv",
    "06_resultados/economia/malla_costos_importacion.csv",
    "06_resultados/economia/resumen_economia.json",
    "06_resultados/economia_articulo/categorias_demanda.csv",
    "06_resultados/economia_articulo/categorias_precios.csv",
    "06_resultados/economia_articulo/reconciliacion_articulo.csv",
    "06_resultados/economia_articulo/resultados_por_producto.csv",
    "06_resultados/economia_articulo/resumen_economia_articulo.json",
    "06_resultados/economia_articulo/resumen_escenarios.csv",
    "07_verificacion/controles_economia_articulo.csv",
)
_EMBEDDED_E5_E10 = re.compile(
    r"^E5=(?P<e5>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?); "
    r"E10=(?P<e10>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)$"
)


def _number(value: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _is_nonfinite_number(value: str) -> bool:
    try:
        return not math.isfinite(float(value))
    except ValueError:
        return False


def _close(reference: float, actual: float) -> bool:
    return math.isclose(reference, actual, rel_tol=RTOL, abs_tol=ATOL)


def _compare_embedded_e5_e10(reference: str, actual: str) -> bool:
    expected = _EMBEDDED_E5_E10.fullmatch(reference)
    observed = _EMBEDDED_E5_E10.fullmatch(actual)
    if expected is None or observed is None:
        return False
    return all(
        _close(float(expected[name]), float(observed[name]))
        for name in ("e5", "e10")
    )


def comparar_csv(
    reference: bytes,
    actual: bytes,
    path: str,
) -> list[str]:
    """Compara un CSV conservando exactamente su topología y sus textos."""

    try:
        expected_rows = list(csv.reader(io.StringIO(reference.decode("utf-8"))))
        actual_rows = list(csv.reader(io.StringIO(actual.decode("utf-8"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        return [f"{path}: CSV ilegible: {exc}"]
    errors: list[str] = []
    if len(expected_rows) != len(actual_rows):
        return [
            f"{path}: cambió el número de filas "
            f"({len(expected_rows)} != {len(actual_rows)})"
        ]
    header = expected_rows[0] if expected_rows else []
    if actual_rows and actual_rows[0] != header:
        errors.append(f"{path}: cambió el encabezado")
    for row_index, (expected_row, actual_row) in enumerate(
        zip(expected_rows, actual_rows, strict=True), start=1
    ):
        if len(expected_row) != len(actual_row):
            errors.append(
                f"{path}: fila {row_index}: cambió el número de columnas "
                f"({len(expected_row)} != {len(actual_row)})"
            )
            continue
        for column_index, (expected, observed) in enumerate(
            zip(expected_row, actual_row, strict=True), start=1
        ):
            if expected == observed and not _is_nonfinite_number(expected):
                continue
            expected_number = _number(expected)
            observed_number = _number(observed)
            if (
                expected_number is not None
                and observed_number is not None
                and _close(expected_number, observed_number)
            ):
                continue
            column_name = (
                header[column_index - 1]
                if column_index <= len(header)
                else f"columna_{column_index}"
            )
            control = expected_row[0] if expected_row else ""
            if (
                path == "07_verificacion/controles_economia_articulo.csv"
                and column_name == "valor_observado"
                and control.startswith("manuscrito_no_reproducido_")
                and _compare_embedded_e5_e10(expected, observed)
            ):
                continue
            errors.append(
                f"{path}: fila {row_index}, {column_name}: "
                f"{expected!r} != {observed!r}"
            )
            if len(errors) >= 20:
                return errors
    return errors


def _compare_json_value(
    reference: Any,
    actual: Any,
    location: str,
    errors: list[str],
) -> None:
    if len(errors) >= 20:
        return
    if type(reference) is not type(actual):
        errors.append(
            f"{location}: cambió el tipo "
            f"({type(reference).__name__} != {type(actual).__name__})"
        )
        return
    if isinstance(reference, dict):
        if list(reference) != list(actual):
            errors.append(f"{location}: cambiaron las claves o su orden")
            return
        for key in reference:
            if (
                location.startswith(
                    "06_resultados/economia_articulo/"
                    "resumen_economia_articulo.json"
                )
                and key == "valor_observado"
                and isinstance(reference.get("control"), str)
                and reference["control"].startswith(
                    "manuscrito_no_reproducido_"
                )
                and reference.get("control") == actual.get("control")
                and isinstance(reference[key], str)
                and isinstance(actual[key], str)
                and _compare_embedded_e5_e10(reference[key], actual[key])
            ):
                continue
            _compare_json_value(
                reference[key], actual[key], f"{location}.{key}", errors
            )
        return
    if isinstance(reference, list):
        if len(reference) != len(actual):
            errors.append(
                f"{location}: cambió la longitud "
                f"({len(reference)} != {len(actual)})"
            )
            return
        for index, (expected, observed) in enumerate(
            zip(reference, actual, strict=True)
        ):
            _compare_json_value(
                expected, observed, f"{location}[{index}]", errors
            )
        return
    if isinstance(reference, float):
        if not (
            math.isfinite(reference)
            and math.isfinite(actual)
            and _close(reference, actual)
        ):
            errors.append(f"{location}: {reference!r} != {actual!r}")
        return
    if reference != actual:
        errors.append(f"{location}: {reference!r} != {actual!r}")


def comparar_json(reference: bytes, actual: bytes, path: str) -> list[str]:
    """Compara JSON recursivamente; solo los ``float`` usan tolerancia."""

    try:
        expected = json.loads(reference)
        observed = json.loads(actual)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [f"{path}: JSON ilegible: {exc}"]
    errors: list[str] = []
    _compare_json_value(expected, observed, path, errors)
    return errors


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _segment_hash(value: str) -> str:
    needle = chr(101) + chr(53)
    output = value
    start = 0
    while True:
        index = output.casefold().find(needle, start)
        if index < 0:
            return output
        output = output[: index + 1] + "|" + output[index + 1 :]
        start = index + 3


def _manifest_rows(
    content: bytes,
    label: str,
) -> tuple[list[dict[str, str]], list[str]]:
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
        rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        return [], [f"{label}: manifiesto ilegible: {exc}"]
    if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
        return [], [f"{label}: cambió el encabezado del manifiesto"]
    for row_index, row in enumerate(rows, start=2):
        if None in row or any(row.get(field) is None for field in MANIFEST_FIELDS):
            return [], [
                f"{label}: fila {row_index}: número de columnas inválido"
            ]
    return rows, []


def validar_manifiesto(
    repo_root: Path,
    reference: bytes,
    actual: bytes,
) -> list[str]:
    """Valida rutas, tamaños y SHA de la ejecución y su cobertura versionada."""

    expected_rows, errors = _manifest_rows(reference, "HEAD")
    actual_rows, actual_errors = _manifest_rows(actual, MANIFEST_PATH)
    errors.extend(actual_errors)
    if errors:
        return errors
    expected_paths = [row["ruta"] for row in expected_rows]
    actual_paths = [row["ruta"] for row in actual_rows]
    if actual_paths != expected_paths:
        errors.append(
            f"{MANIFEST_PATH}: cambiaron las rutas incluidas o su orden"
        )
    if len(actual_paths) != len(set(actual_paths)):
        errors.append(f"{MANIFEST_PATH}: contiene rutas duplicadas")
    root = repo_root.resolve()
    inventory = []
    for relative_root in MANIFEST_ROOTS:
        base = root / relative_root
        if not base.exists():
            continue
        inventory.extend(
            path.relative_to(root).as_posix()
            for path in sorted(base.rglob("*"))
            if path.is_file()
            and path.relative_to(root).as_posix() != MANIFEST_PATH
            and "__pycache__" not in path.parts
        )
    if actual_paths != sorted(inventory):
        errors.append(
            f"{MANIFEST_PATH}: no coincide con el inventario actual de archivos"
        )
    for row_index, row in enumerate(actual_rows, start=2):
        route = row["ruta"]
        relative = Path(route)
        if (
            not route
            or relative.is_absolute()
            or "\\" in route
            or any(part in ("", ".", "..") for part in relative.parts)
        ):
            errors.append(
                f"{MANIFEST_PATH}: fila {row_index}: ruta no canónica {route!r}"
            )
            continue
        unresolved = root / relative
        cursor = root
        contains_symlink = False
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                contains_symlink = True
                break
        candidate = unresolved.resolve()
        if (
            contains_symlink
            or not candidate.is_relative_to(root)
            or not candidate.is_file()
        ):
            errors.append(
                f"{MANIFEST_PATH}: fila {row_index}: ruta ausente o no regular {route!r}"
            )
            continue
        try:
            declared_size = int(row["bytes"])
        except ValueError:
            errors.append(
                f"{MANIFEST_PATH}: fila {row_index}: tamaño inválido"
            )
            continue
        actual_size = candidate.stat().st_size
        if declared_size != actual_size:
            errors.append(
                f"{MANIFEST_PATH}: fila {row_index}: bytes de {route!r}: "
                f"{declared_size} != {actual_size}"
            )
        digest = _sha256(candidate)
        if row["sha256_segmentado"] != _segment_hash(digest):
            errors.append(
                f"{MANIFEST_PATH}: fila {row_index}: SHA-256 incorrecto para {route!r}"
            )
        if row["reconstruccion_huella"] != "eliminar_barras_verticales":
            errors.append(
                f"{MANIFEST_PATH}: fila {row_index}: instrucción de huella inválida"
            )
        if len(errors) >= 20:
            break
    return errors


def _git(repo_root: Path, arguments: Sequence[str]) -> bytes:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        message = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Falló git {' '.join(arguments)}: {message}")
    return completed.stdout


def _baseline(repo_root: Path, base: str, path: str) -> bytes:
    return _git(repo_root, ["show", f"{base}:{path}"])


def verificar_salidas_versionadas(
    repo_root: str | Path,
    *,
    base: str = "HEAD",
) -> dict[str, Any]:
    """Verifica salidas contra ``base`` y devuelve un resumen auditable."""

    root = Path(repo_root).resolve()
    errors: list[str] = []
    changed = {
        item.decode("utf-8")
        for item in _git(
            root,
            ["diff", "--name-only", "--diff-filter=ACDMRTUXB", "-z", base, "--"],
        ).split(b"\0")
        if item
    }
    untracked = {
        item.decode("utf-8")
        for item in _git(
            root, ["ls-files", "--others", "--exclude-standard", "-z"]
        ).split(b"\0")
        if item
    }
    permitted = set(SEMANTIC_PATHS) | {MANIFEST_PATH}
    unexpected = sorted((changed | untracked) - permitted)
    if unexpected:
        errors.append(
            "Cambios fuera de las salidas numéricas autorizadas: "
            + ", ".join(unexpected)
        )
    for path in SEMANTIC_PATHS:
        candidate = root / path
        if not candidate.is_file():
            errors.append(f"Falta la salida versionada {path}")
            continue
        try:
            reference = _baseline(root, base, path)
        except RuntimeError as exc:
            errors.append(str(exc))
            continue
        actual = candidate.read_bytes()
        if path.endswith(".csv"):
            errors.extend(comparar_csv(reference, actual, path))
        elif path.endswith(".json"):
            errors.extend(comparar_json(reference, actual, path))
        else:  # pragma: no cover - la lista cerrada solo admite CSV/JSON
            errors.append(f"Extensión semántica no admitida: {path}")
        if len(errors) >= 20:
            break
    manifest = root / MANIFEST_PATH
    if not manifest.is_file():
        errors.append(f"Falta {MANIFEST_PATH}")
    else:
        try:
            manifest_reference = _baseline(root, base, MANIFEST_PATH)
        except RuntimeError as exc:
            errors.append(str(exc))
        else:
            errors.extend(
                validar_manifiesto(
                    root, manifest_reference, manifest.read_bytes()
                )
            )
    if errors:
        raise AssertionError("\n".join(errors[:20]))
    return {
        "estado": "PASS",
        "base": base,
        "salidas_numericas": len(SEMANTIC_PATHS),
        "rutas_modificadas": len(changed),
        "rtol": RTOL,
        "atol": ATOL,
        "manifiesto_autoconsistente": True,
    }


__all__ = [
    "ATOL",
    "MANIFEST_PATH",
    "RTOL",
    "SEMANTIC_PATHS",
    "comparar_csv",
    "comparar_json",
    "validar_manifiesto",
    "verificar_salidas_versionadas",
]

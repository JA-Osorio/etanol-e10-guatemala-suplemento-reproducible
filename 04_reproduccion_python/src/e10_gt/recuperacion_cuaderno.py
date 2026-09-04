"""Recupera la serie anual incrustada en las salidas Plotly del cuaderno.

El libro de trabajo original no se conserva en el repositorio. Esta utilidad
extrae los valores que sí quedaron serializados en un ``.ipynb`` privado y deja
explícito que ``btu_recovered`` es una inversión algebraica de la curva E0, no
una observación independiente del libro perdido. La rama pública omite el ID y
la huella del cuaderno privado.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


DRIVE_FILE_ID = "omitido_en_rama_publica"
ORIGINAL_NOTEBOOK_SHA256: str | None = None
BTU_TO_MJ = 0.001055056
GASOLINE_LHV_MJ_PER_LITER = 32.0
ETHANOL_LHV_MJ_PER_LITER = 21.1
LITER_TO_US_GALLON = 0.2641720524
E10_VOLUMETRIC_SHARE = 0.10
CO2_FACTOR_TONNES_PER_TJ = 69.3
VALUE_STATUS = "recovered_from_embedded_notebook_plotly_output"
CSV_FIELDS = (
    "year",
    "btu_recovered",
    "reference_co2_tonnes_notebook_output",
    "million_us_gallons_notebook_output",
    "value_status",
)
GOLDEN_SEMANTIC_HASHES = {
    "retrospective_1986_2023": (
        "59b7d173279092a1559322cb5e21c91952244351997355ec7698c4a6b8ba6573"
    ),
    "prospective_2024_2030": (
        "582dc512fa3c9d46e7010db40315f77bf611db3e931987b4c10ea99e5813311d"
    ),
    "volume_1986_2030": (
        "0e2385356bebe4ae99ce37fe0e451f83f0fcb581d2672983d9ef00061bd41198"
    ),
    "integrated_1986_2030": (
        "9d39deacc3edf10bfa183792d4960da8c5508fff1250e8e7412496c7d50d57f2"
    ),
}


class NotebookRecoveryError(ValueError):
    """El cuaderno no contiene una recuperación inequívoca y coherente."""


@dataclass(frozen=True)
class PlotlyTrace:
    """Traza Plotly con su localización para mensajes de diagnóstico."""

    name: str
    payload: dict[str, Any]
    cell_index: int
    output_index: int
    plot_index: int
    trace_index: int

    @property
    def location(self) -> str:
        return (
            f"celda {self.cell_index}, salida {self.output_index}, "
            f"gráfica {self.plot_index}"
        )


@dataclass(frozen=True)
class RecoveryResult:
    """Datos publicables y evidencias mínimas de la extracción."""

    rows: list[dict[str, Any]]
    historical_base_ktonnes: dict[int, float]
    historical_e10_ktonnes: dict[int, float]
    volume_million_us_gallons: dict[int, float]
    prospective_base_ktonnes: dict[int, float]
    prospective_e10_ktonnes: dict[int, float]
    integrated_base_ktonnes: dict[int, float]
    integrated_e10_ktonnes: dict[int, float]
    semantic_hashes: dict[str, str]
    raw_sha256: str
    verified_sha256: str
    accepted_single_added_final_newline: bool
    drive_file_id: str = DRIVE_FILE_ID


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_notebook_json(
    notebook_path: str | Path,
    *,
    expected_sha256: str | None = None,
    allow_single_added_final_newline: bool = False,
) -> tuple[dict[str, Any], str, str, bool]:
    """Lee el JSON y, si se solicita, valida estrictamente su identidad.

    ``allow_single_added_final_newline`` acepta únicamente el caso comprobable
    en que la copia local tiene un byte ``LF`` adicional. Se reportan ambos
    hashes; la normalización nunca ocurre silenciosamente.
    """

    path = Path(notebook_path)
    raw = path.read_bytes()
    raw_sha256 = _sha256(raw)
    verified_sha256 = raw_sha256
    accepted_newline = False

    if expected_sha256 is not None and raw_sha256 != expected_sha256:
        without_final_newline = raw[:-1] if raw.endswith(b"\n") else raw
        normalized_sha256 = _sha256(without_final_newline)
        if (
            allow_single_added_final_newline
            and len(without_final_newline) + 1 == len(raw)
            and normalized_sha256 == expected_sha256
        ):
            verified_sha256 = normalized_sha256
            accepted_newline = True
        else:
            raise NotebookRecoveryError(
                f"SHA-256 inesperado para {path}: {raw_sha256}; "
                f"se esperaba {expected_sha256}"
            )

    try:
        notebook = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NotebookRecoveryError(f"El archivo no es un ipynb JSON válido: {path}") from exc
    if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
        raise NotebookRecoveryError("El ipynb no contiene una lista 'cells' válida")
    return notebook, raw_sha256, verified_sha256, accepted_newline


def _html_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        return "".join(value)
    raise NotebookRecoveryError(
        "La salida Plotly text/html debe ser una cadena o una lista de cadenas"
    )


def _plotly_data_arrays(html: str) -> Iterable[list[dict[str, Any]]]:
    """Decodifica el segundo argumento JSON de cada ``Plotly.newPlot``."""

    marker = "Plotly.newPlot("
    decoder = json.JSONDecoder()
    position = 0
    while True:
        start = html.find(marker, position)
        if start < 0:
            return
        cursor = start + len(marker)
        try:
            _plot_id, consumed = decoder.raw_decode(html[cursor:].lstrip())
            cursor += len(html[cursor:]) - len(html[cursor:].lstrip()) + consumed
            while cursor < len(html) and html[cursor].isspace():
                cursor += 1
            if cursor >= len(html) or html[cursor] != ",":
                raise NotebookRecoveryError(
                    "No se encontró el arreglo de trazas tras Plotly.newPlot"
                )
            cursor += 1
            traces, consumed = decoder.raw_decode(html[cursor:].lstrip())
            cursor += len(html[cursor:]) - len(html[cursor:].lstrip()) + consumed
        except (json.JSONDecodeError, TypeError) as exc:
            raise NotebookRecoveryError(
                "No se pudo decodificar el JSON incrustado de Plotly.newPlot"
            ) from exc
        if not isinstance(traces, list) or not all(
            isinstance(trace, dict) for trace in traces
        ):
            raise NotebookRecoveryError("El argumento de trazas Plotly no es un arreglo")
        yield traces
        position = cursor


def iter_plotly_traces(notebook: dict[str, Any]) -> Iterable[PlotlyTrace]:
    """Recorre trazas por nombre sin depender del índice fijo de una celda."""

    for cell_index, cell in enumerate(notebook["cells"]):
        if not isinstance(cell, dict):
            continue
        outputs = cell.get("outputs", [])
        if not isinstance(outputs, list):
            continue
        for output_index, output in enumerate(outputs):
            if not isinstance(output, dict):
                continue
            data = output.get("data", {})
            if not isinstance(data, dict) or "text/html" not in data:
                continue
            html = _html_text(data["text/html"])
            for plot_index, traces in enumerate(_plotly_data_arrays(html)):
                for trace_index, trace in enumerate(traces):
                    name = trace.get("name")
                    if isinstance(name, str):
                        yield PlotlyTrace(
                            name=name,
                            payload=trace,
                            cell_index=cell_index,
                            output_index=output_index,
                            plot_index=plot_index,
                            trace_index=trace_index,
                        )


def _numeric_series(trace: PlotlyTrace) -> dict[int, float]:
    x_values = trace.payload.get("x")
    y_values = trace.payload.get("y")
    if not isinstance(x_values, list) or not isinstance(y_values, list):
        raise NotebookRecoveryError(
            f"La traza '{trace.name}' en {trace.location} no contiene arreglos x/y"
        )
    if len(x_values) != len(y_values) or not x_values:
        raise NotebookRecoveryError(
            f"La traza '{trace.name}' en {trace.location} tiene arreglos x/y "
            "vacíos o de longitudes diferentes"
        )

    series: dict[int, float] = {}
    for raw_year, raw_value in zip(x_values, y_values):
        if isinstance(raw_year, bool) or not isinstance(raw_year, (int, float)):
            raise NotebookRecoveryError(
                f"Año no numérico en la traza '{trace.name}' ({trace.location})"
            )
        year = int(raw_year)
        if not math.isclose(float(raw_year), year, rel_tol=0.0, abs_tol=1e-9):
            raise NotebookRecoveryError(
                f"Año no entero en la traza '{trace.name}' ({trace.location})"
            )
        if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
            raise NotebookRecoveryError(
                f"Valor no numérico para {year} en '{trace.name}'"
            )
        value = float(raw_value)
        if not math.isfinite(value) or value <= 0:
            raise NotebookRecoveryError(
                f"Valor no positivo o no finito para {year} en '{trace.name}'"
            )
        if year in series:
            raise NotebookRecoveryError(
                f"Año duplicado {year} en la traza '{trace.name}'"
            )
        series[year] = value
    return series


def _select_figure(
    traces: list[PlotlyTrace],
    *,
    ordered_names: tuple[str, ...],
    start_year: int,
    end_year: int,
    label: str,
) -> list[PlotlyTrace]:
    """Localiza una gráfica por nombres y cobertura, preservando sus trazas."""

    grouped: dict[tuple[int, int, int], list[PlotlyTrace]] = {}
    for trace in traces:
        key = (trace.cell_index, trace.output_index, trace.plot_index)
        grouped.setdefault(key, []).append(trace)

    required = set(range(start_year, end_year + 1))
    candidates: list[tuple[list[PlotlyTrace], list[dict[int, float]]]] = []
    errors: list[str] = []
    for figure_traces in grouped.values():
        by_name = {trace.name: trace for trace in figure_traces}
        if not set(ordered_names).issubset(by_name):
            continue
        selected = [by_name[name] for name in ordered_names]
        try:
            series = [_numeric_series(trace) for trace in selected]
        except NotebookRecoveryError as exc:
            errors.append(str(exc))
            continue
        if not all(set(values) == required for values in series):
            errors.append(
                f"gráfica en {selected[0].location} no tiene cobertura exacta "
                f"{start_year}-{end_year}"
            )
            continue
        # El orden semántico debe ser el orden serializado, no el de búsqueda.
        selected.sort(key=lambda trace: trace.trace_index)
        candidates.append((selected, series))

    if not candidates:
        detail = "; ".join(errors) or "no apareció el conjunto de nombres"
        raise NotebookRecoveryError(
            f"No se pudo localizar la gráfica {label} con trazas "
            f"{ordered_names} y cobertura {start_year}-{end_year}: {detail}"
        )

    reference_payload = _semantic_payload(candidates[0][0])
    for selected, _series in candidates[1:]:
        if _semantic_payload(selected) != reference_payload:
            raise NotebookRecoveryError(f"Selección ambigua de la gráfica {label}")
    return candidates[0][0]


def _semantic_payload(traces: list[PlotlyTrace]) -> list[dict[str, Any]]:
    """Reduce una gráfica a los valores científicos, excluyendo el estilo."""

    return [
        {
            "name": trace.name,
            "x": trace.payload.get("x"),
            "y": trace.payload.get("y"),
        }
        for trace in traces
    ]


def semantic_trace_hash(traces: list[PlotlyTrace]) -> str:
    """SHA-256 de ``[{name,x,y},…]`` en JSON compacto y ASCII determinista."""

    payload = json.dumps(
        _semantic_payload(traces),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _canonical_float(value: float) -> float:
    """Replica la precisión de 15 cifras usada en el derivado versionado."""

    return float(format(value, ".15g"))


def recover_counterfactual_from_notebook(
    notebook_path: str | Path,
    *,
    expected_sha256: str | None = None,
    allow_single_added_final_newline: bool = False,
    expected_semantic_hashes: dict[str, str] | None = None,
) -> RecoveryResult:
    """Extrae, valida y transforma las curvas incrustadas del cuaderno."""

    notebook, raw_hash, verified_hash, accepted_newline = load_notebook_json(
        notebook_path,
        expected_sha256=expected_sha256,
        allow_single_added_final_newline=allow_single_added_final_newline,
    )
    traces = list(iter_plotly_traces(notebook))
    if not traces:
        raise NotebookRecoveryError("El cuaderno no contiene salidas Plotly.newPlot")

    retrospective_figure = _select_figure(
        traces,
        ordered_names=("Con E10 (contrafactual)", "Base (E0)"),
        start_year=1986,
        end_year=2023,
        label="retrospectiva",
    )
    prospective_figure = _select_figure(
        traces,
        ordered_names=("Con E10 (escenario)", "Base (E0)"),
        start_year=2024,
        end_year=2030,
        label="prospectiva",
    )
    volume_figure = _select_figure(
        traces,
        ordered_names=("Consumo final (mill. gal/año)",),
        start_year=1986,
        end_year=2030,
        label="de volumen",
    )
    integrated_figure = _select_figure(
        traces,
        ordered_names=("Con E10 (contrafactual + escenario)", "Base (E0)"),
        start_year=1986,
        end_year=2030,
        label="integrada",
    )

    def figure_series(figure: list[PlotlyTrace]) -> dict[str, dict[int, float]]:
        return {trace.name: _numeric_series(trace) for trace in figure}

    retrospective = figure_series(retrospective_figure)
    prospective = figure_series(prospective_figure)
    volume_data = figure_series(volume_figure)
    integrated = figure_series(integrated_figure)
    base = retrospective["Base (E0)"]
    e10 = retrospective["Con E10 (contrafactual)"]
    volume = volume_data["Consumo final (mill. gal/año)"]
    prospective_base = prospective["Base (E0)"]
    prospective_e10 = prospective["Con E10 (escenario)"]
    integrated_base = integrated["Base (E0)"]
    integrated_e10 = integrated["Con E10 (contrafactual + escenario)"]

    semantic_hashes = {
        "retrospective_1986_2023": semantic_trace_hash(retrospective_figure),
        "prospective_2024_2030": semantic_trace_hash(prospective_figure),
        "volume_1986_2030": semantic_trace_hash(volume_figure),
        "integrated_1986_2030": semantic_trace_hash(integrated_figure),
    }
    if expected_semantic_hashes is not None:
        if set(expected_semantic_hashes) != set(semantic_hashes):
            raise NotebookRecoveryError(
                "Las claves de hashes semánticos esperados no son las cuatro "
                "gráficas auditadas"
            )
        mismatches = {
            key: (expected_semantic_hashes[key], semantic_hashes[key])
            for key in semantic_hashes
            if expected_semantic_hashes[key] != semantic_hashes[key]
        }
        if mismatches:
            raise NotebookRecoveryError(
                f"Hashes semánticos Plotly inesperados: {mismatches}"
            )

    blend_energy = (
        (1.0 - E10_VOLUMETRIC_SHARE) * GASOLINE_LHV_MJ_PER_LITER
        + E10_VOLUMETRIC_SHARE * ETHANOL_LHV_MJ_PER_LITER
    )
    ethanol_energy_fraction = (
        E10_VOLUMETRIC_SHARE * ETHANOL_LHV_MJ_PER_LITER / blend_energy
    )

    rows: list[dict[str, Any]] = []
    for year in range(1986, 2024):
        expected_e10 = base[year] * (1.0 - ethanol_energy_fraction)
        if not math.isclose(e10[year], expected_e10, rel_tol=2e-12, abs_tol=1e-9):
            raise NotebookRecoveryError(
                f"Incoherencia Base/E10 en {year}: {base[year]} y {e10[year]}"
            )

        reference_tonnes_raw = base[year] * 1_000.0
        btu_raw = (
            reference_tonnes_raw
            * 1_000_000.0
            / (CO2_FACTOR_TONNES_PER_TJ * BTU_TO_MJ)
        )
        expected_volume = (
            btu_raw
            * BTU_TO_MJ
            / GASOLINE_LHV_MJ_PER_LITER
            * LITER_TO_US_GALLON
            / 1_000_000.0
        )
        if not math.isclose(
            volume[year], expected_volume, rel_tol=2e-12, abs_tol=1e-9
        ):
            raise NotebookRecoveryError(
                f"Incoherencia Base/volumen en {year}: "
                f"{base[year]} ktCO2 y {volume[year]} millones de galones"
            )

        rows.append(
            {
                "year": year,
                "btu_recovered": _canonical_float(btu_raw),
                "reference_co2_tonnes_notebook_output": _canonical_float(
                    reference_tonnes_raw
                ),
                "million_us_gallons_notebook_output": _canonical_float(
                    volume[year]
                ),
                "value_status": VALUE_STATUS,
            }
        )

    # Las gráficas prospectiva e integrada proceden de la misma proyección de
    # volumen. Primero se reconstruye E0 desde esa curva independiente.
    for year in range(2024, 2031):
        energy_tj_from_volume = (
            volume[year]
            * GASOLINE_LHV_MJ_PER_LITER
            / LITER_TO_US_GALLON
        )
        expected_base = (
            energy_tj_from_volume * CO2_FACTOR_TONNES_PER_TJ / 1_000.0
        )
        for context, actual in (
            ("prospectiva", prospective_base[year]),
            ("integrada", integrated_base[year]),
        ):
            if not math.isclose(actual, expected_base, rel_tol=2e-12, abs_tol=1e-9):
                raise NotebookRecoveryError(
                    f"Incoherencia volumen/E0 {context} en {year}: "
                    f"{volume[year]} millones de galones y {actual} ktCO2"
                )

        prospective_factor = (
            1.0 if year in (2024, 2025) else 1.0 - ethanol_energy_fraction
        )
        if not math.isclose(
            prospective_e10[year],
            prospective_base[year] * prospective_factor,
            rel_tol=2e-12,
            abs_tol=1e-9,
        ):
            raise NotebookRecoveryError(
                f"Regla prospectiva E0/E10 incumplida en {year}"
            )
        if not math.isclose(
            integrated_e10[year],
            integrated_base[year] * (1.0 - ethanol_energy_fraction),
            rel_tol=2e-12,
            abs_tol=1e-9,
        ):
            raise NotebookRecoveryError(
                f"Regla E10 integrada incumplida en {year}"
            )

    for year in range(1986, 2031):
        expected_base = base[year] if year <= 2023 else prospective_base[year]
        expected_e10 = e10[year] if year <= 2023 else (
            prospective_base[year] * (1.0 - ethanol_energy_fraction)
        )
        if not math.isclose(
            integrated_base[year], expected_base, rel_tol=2e-12, abs_tol=1e-9
        ):
            raise NotebookRecoveryError(f"E0 integrada inconsistente en {year}")
        if not math.isclose(
            integrated_e10[year], expected_e10, rel_tol=2e-12, abs_tol=1e-9
        ):
            raise NotebookRecoveryError(f"E10 integrada inconsistente en {year}")

    return RecoveryResult(
        rows=rows,
        historical_base_ktonnes=base,
        historical_e10_ktonnes=e10,
        volume_million_us_gallons=volume,
        prospective_base_ktonnes=prospective_base,
        prospective_e10_ktonnes=prospective_e10,
        integrated_base_ktonnes=integrated_base,
        integrated_e10_ktonnes=integrated_e10,
        semantic_hashes=semantic_hashes,
        raw_sha256=raw_hash,
        verified_sha256=verified_hash,
        accepted_single_added_final_newline=accepted_newline,
    )


def write_recovered_csv(rows: list[dict[str, Any]], output_path: str | Path) -> Path:
    """Escribe el derivado forense con esquema y orden estables."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "year": int(row["year"]),
                    "btu_recovered": format(float(row["btu_recovered"]), ".15g"),
                    "reference_co2_tonnes_notebook_output": format(
                        float(row["reference_co2_tonnes_notebook_output"]), ".15g"
                    ),
                    "million_us_gallons_notebook_output": format(
                        float(row["million_us_gallons_notebook_output"]), ".15g"
                    ),
                    "value_status": row["value_status"],
                }
            )
    return path

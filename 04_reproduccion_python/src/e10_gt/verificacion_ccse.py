"""Verificación opcional de una copia local del libro primario externo.

El libro no se copia ni se redistribuye. Esta utilidad valida una copia local y
comprueba que sus 38 valores BTU regeneren las salidas embebidas en el cuaderno
histórico. La identidad binaria se puede comprobar con una huella suministrada
por el usuario; la rama pública no fija ni muestra esa huella por defecto. El
lector OOXML usa únicamente la biblioteca estándar para no añadir una
dependencia de Excel al flujo público ordinario.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import posixpath
import re
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

import numpy as np


DEFAULT_REPO_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_WORKBOOK_SHA256: str | None = None
EXPECTED_SHEET_NAME = "1.CONSUMO FINAL"
EXPECTED_HEADERS = ("No", "año", "BTU")
EXPECTED_YEARS = tuple(range(1986, 2024))

BTU_ABSOLUTE_TOLERANCE = 0.1
BTU_RELATIVE_TOLERANCE = 5e-15
CO2_ABSOLUTE_TOLERANCE_TONNES = 1e-7
VOLUME_ABSOLUTE_TOLERANCE_MILLION_GALLONS = 1e-9
FIT_ABSOLUTE_TOLERANCE = 1e-12
PROJECTION_CO2_TOLERANCE_TONNES = 1e-3
PROJECTION_VOLUME_TOLERANCE_MILLION_GALLONS = 1e-9

_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE_REL_NS = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
)
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REFERENCE = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")


@dataclass(frozen=True)
class CcseRecord:
    """Una observación primaria del libro."""

    sequence: int
    year: int
    btu: float


@dataclass(frozen=True)
class RecoveredRecord:
    """Control público recuperado desde las salidas del cuaderno."""

    year: int
    btu: float
    reference_co2_tonnes: float
    million_us_gallons: float


def sha256_file(path: str | Path) -> str:
    """Calcula la huella SHA-256 sin cargar el libro completo en memoria."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _column_number(reference: str) -> int:
    match = _CELL_REFERENCE.fullmatch(reference)
    if match is None:
        raise ValueError(f"Referencia de celda OOXML inesperada: {reference!r}")
    number = 0
    for character in match.group(1):
        number = number * 26 + ord(character) - ord("A") + 1
    return number


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    text_tag = f"{{{_MAIN_NS}}}t"
    return [
        "".join(node.text or "" for node in item.iter(text_tag))
        for item in root.findall(f"{{{_MAIN_NS}}}si")
    ]


def _cell_value(cell: ET.Element, shared_strings: Sequence[str]) -> Any:
    if cell.find(f"{{{_MAIN_NS}}}f") is not None:
        raise ValueError(
            f"La celda {cell.attrib.get('r', '?')} contiene una fórmula; "
            "el insumo esperado debe contener valores primarios."
        )
    cell_type = cell.attrib.get("t", "n")
    if cell_type == "inlineStr":
        text_tag = f"{{{_MAIN_NS}}}t"
        inline = cell.find(f"{{{_MAIN_NS}}}is")
        return "" if inline is None else "".join(
            node.text or "" for node in inline.iter(text_tag)
        )
    value = cell.find(f"{{{_MAIN_NS}}}v")
    if value is None or value.text is None:
        return None
    if cell_type == "s":
        index = int(value.text)
        try:
            return shared_strings[index]
        except IndexError as error:
            raise ValueError(
                f"Índice de texto compartido fuera de rango: {index}"
            ) from error
    if cell_type in {"str", "e"}:
        return value.text
    if cell_type == "b":
        return value.text == "1"
    try:
        return float(value.text)
    except ValueError as error:
        raise ValueError(
            f"Valor numérico OOXML inválido en {cell.attrib.get('r', '?')}: "
            f"{value.text!r}"
        ) from error


def _worksheet_path(archive: ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationship_id = None
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        if sheet.attrib.get("name") == sheet_name:
            relationship_id = sheet.attrib.get(f"{{{_OFFICE_REL_NS}}}id")
            break
    if not relationship_id:
        names = [
            sheet.attrib.get("name", "")
            for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet")
        ]
        raise ValueError(
            f"No se encontró la hoja {sheet_name!r}; hojas disponibles: {names}"
        )

    relationships = ET.fromstring(
        archive.read("xl/_rels/workbook.xml.rels")
    )
    target = None
    for relationship in relationships.findall(
        f"{{{_PACKAGE_REL_NS}}}Relationship"
    ):
        if relationship.attrib.get("Id") == relationship_id:
            target = relationship.attrib.get("Target")
            break
    if not target:
        raise ValueError(
            f"No se resolvió la relación OOXML {relationship_id!r} de la hoja."
        )
    if target.startswith("/"):
        path = target.lstrip("/")
    else:
        path = posixpath.normpath(posixpath.join("xl", target))
    if path not in archive.namelist():
        raise ValueError(f"La parte OOXML de la hoja no existe: {path}")
    return path


def _integer(value: Any, label: str) -> int:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} no es numérico: {value!r}") from error
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise ValueError(f"{label} no es un entero finito: {value!r}")
    return int(numeric)


def read_ccse_workbook(
    workbook_path: str | Path,
    *,
    sheet_name: str = EXPECTED_SHEET_NAME,
) -> list[CcseRecord]:
    """Lee la tabla primaria desde OOXML y valida su estructura tabular."""

    path = Path(workbook_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.casefold() != ".xlsx":
        raise ValueError(f"Se esperaba un archivo .xlsx: {path.name}")

    try:
        with ZipFile(path) as archive:
            shared_strings = _shared_strings(archive)
            worksheet = ET.fromstring(
                archive.read(_worksheet_path(archive, sheet_name))
            )
    except (BadZipFile, KeyError, ET.ParseError) as error:
        raise ValueError(f"Libro XLSX/OOXML inválido: {path.name}") from error

    rows: dict[int, dict[int, Any]] = {}
    for row in worksheet.findall(f".//{{{_MAIN_NS}}}sheetData/{{{_MAIN_NS}}}row"):
        row_number = int(row.attrib.get("r", "0"))
        values: dict[int, Any] = {}
        for cell in row.findall(f"{{{_MAIN_NS}}}c"):
            reference = cell.attrib.get("r", "")
            value = _cell_value(cell, shared_strings)
            if value is not None:
                values[_column_number(reference)] = value
        if values:
            rows[row_number] = values

    if 1 not in rows:
        raise ValueError("La hoja no contiene encabezados en la fila 1.")
    max_header_column = max(rows[1])
    headers = tuple(
        str(rows[1].get(column, "")).strip()
        for column in range(1, max_header_column + 1)
    )
    if headers != EXPECTED_HEADERS:
        raise ValueError(
            f"Columnas inesperadas en {sheet_name}: {headers}; "
            f"se esperaban {EXPECTED_HEADERS}."
        )

    records: list[CcseRecord] = []
    for row_number in sorted(number for number in rows if number > 1):
        values = rows[row_number]
        if set(values) != {1, 2, 3}:
            raise ValueError(
                f"La fila Excel {row_number} no contiene exactamente No, año y BTU."
            )
        try:
            btu = float(values[3])
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"BTU no numérico en la fila Excel {row_number}: {values[3]!r}"
            ) from error
        records.append(
            CcseRecord(
                sequence=_integer(values[1], f"No de la fila {row_number}"),
                year=_integer(values[2], f"año de la fila {row_number}"),
                btu=btu,
            )
        )
    validate_ccse_records(records)
    return records


def validate_ccse_records(records: Sequence[CcseRecord]) -> None:
    """Exige la cobertura, secuencia y dominio observados en el libro recuperado."""

    expected_sequence = list(range(1, len(EXPECTED_YEARS) + 1))
    sequence = [record.sequence for record in records]
    years = [record.year for record in records]
    if len(records) != len(EXPECTED_YEARS):
        raise ValueError(
            f"Cobertura inesperada: {len(records)} filas; "
            f"se esperaban {len(EXPECTED_YEARS)}."
        )
    if sequence != expected_sequence:
        raise ValueError(
            f"La columna No no es la secuencia 1..{len(EXPECTED_YEARS)}."
        )
    if years != list(EXPECTED_YEARS):
        raise ValueError("Los años no son la serie única y continua 1986–2023.")
    if any(not math.isfinite(record.btu) or record.btu <= 0 for record in records):
        raise ValueError("Todos los valores BTU deben ser finitos y positivos.")


def load_recovered_controls(csv_path: str | Path) -> list[RecoveredRecord]:
    """Carga los valores públicos recuperados que funcionan como control."""

    path = Path(csv_path)
    required = {
        "year",
        "btu_recovered",
        "reference_co2_tonnes_notebook_output",
        "million_us_gallons_notebook_output",
    }
    rows: list[RecoveredRecord] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"Columnas de control ausentes en {path}")
        for raw in reader:
            rows.append(
                RecoveredRecord(
                    year=int(raw["year"]),
                    btu=float(raw["btu_recovered"]),
                    reference_co2_tonnes=float(
                        raw["reference_co2_tonnes_notebook_output"]
                    ),
                    million_us_gallons=float(
                        raw["million_us_gallons_notebook_output"]
                    ),
                )
            )
    if [row.year for row in rows] != list(EXPECTED_YEARS):
        raise ValueError("El CSV de control no cubre exactamente 1986–2023.")
    return rows


def _round_half_up(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _max_abs(values: Iterable[float]) -> float:
    return max((abs(float(value)) for value in values), default=0.0)


def _check(
    check_id: str,
    passed: bool,
    computed: Any,
    expected: Any,
    *,
    tolerance: float | str = 0,
) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "computed": computed,
        "expected": expected,
        "tolerance": tolerance,
        "status": "PASS" if passed else "FAIL",
    }


def compare_ccse_records(
    records: Sequence[CcseRecord],
    recovered: Sequence[RecoveredRecord],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Compara valores, conversiones, ``np.polyfit`` literal y totales."""

    validate_ccse_records(records)
    if [row.year for row in recovered] != list(EXPECTED_YEARS):
        raise ValueError("Los controles recuperados no cubren 1986–2023.")
    by_year = {row.year: row for row in recovered}
    if len(by_year) != len(recovered):
        raise ValueError("El CSV recuperado contiene años duplicados.")

    lineage = config["article_recovered_lineage"]
    btu_to_mj = float(lineage["btu_to_mj"])
    gasoline_lhv = float(lineage["gasoline_lhv_mj_per_liter"])
    ethanol_lhv = float(lineage["ethanol_lhv_mj_per_liter"])
    liter_to_us_gallon = float(lineage["liter_to_us_gallon"])
    blend_share = float(lineage["e10_volumetric_share"])
    co2_factor = float(lineage["co2_factor_tonnes_per_tj"])

    years = np.asarray([record.year for record in records], dtype=float)
    btu = np.asarray([record.btu for record in records], dtype=float)
    energy_tj = btu * btu_to_mj / 1e6
    liters = energy_tj * 1e6 / gasoline_lhv
    reference_co2 = energy_tj * co2_factor
    million_gallons = liters * liter_to_us_gallon / 1e6

    btu_residuals = np.asarray(
        [record.btu - by_year[record.year].btu for record in records]
    )
    btu_relative = np.abs(btu_residuals / btu)
    co2_residuals = np.asarray(
        [
            reference_co2[index]
            - by_year[record.year].reference_co2_tonnes
            for index, record in enumerate(records)
        ]
    )
    volume_residuals = np.asarray(
        [
            million_gallons[index]
            - by_year[record.year].million_us_gallons
            for index, record in enumerate(records)
        ]
    )

    fit_start = int(lineage["fit_start_year"])
    fit_end = int(lineage["fit_end_year"])
    fit_mask = (years >= fit_start) & (years <= fit_end)
    fit_years = years[fit_mask]
    fit_log_liters = np.log(liters[fit_mask])
    slope, intercept = np.polyfit(fit_years, fit_log_liters, deg=1)
    fitted = intercept + slope * fit_years
    residuals = fit_log_liters - fitted
    ss_residual = float(np.sum(residuals**2))
    ss_total = float(np.sum((fit_log_liters - np.mean(fit_log_liters)) ** 2))
    r_squared = 1.0 - ss_residual / ss_total if ss_total else 1.0
    rmse = math.sqrt(ss_residual / len(fit_years))
    annual_growth = math.exp(float(slope)) - 1.0

    center_year = int(lineage["golden_log_linear_fit_recalculated"]["center_year"])
    centered_energy_intercept = (
        float(intercept)
        + float(slope) * center_year
        - math.log(1e6 / gasoline_lhv)
    )
    forecast_years = np.arange(
        int(lineage["forecast_start_year"]),
        int(lineage["forecast_end_year"]) + 1,
        dtype=float,
    )
    forecast_liters = np.exp(float(intercept) + float(slope) * forecast_years)
    forecast_energy_tj = forecast_liters * gasoline_lhv / 1e6
    forecast_co2 = forecast_energy_tj * co2_factor
    forecast_million_gallons = (
        forecast_liters * liter_to_us_gallon / 1e6
    )

    rho = ethanol_lhv / gasoline_lhv
    reduction = (
        blend_share * rho / ((1.0 - blend_share) + blend_share * rho)
    )
    historical_reference = float(np.sum(reference_co2))
    historical_scenario = historical_reference * (1.0 - reduction)
    historical_avoided = historical_reference - historical_scenario

    prospective_mask = forecast_years >= int(lineage["policy_start_year"])
    prospective_reference = float(np.sum(forecast_co2[prospective_mask]))
    prospective_scenario = prospective_reference * (1.0 - reduction)
    prospective_avoided = prospective_reference - prospective_scenario

    integrated_reference = historical_reference + float(np.sum(forecast_co2))
    integrated_scenario = integrated_reference * (1.0 - reduction)
    integrated_avoided = integrated_reference - integrated_scenario

    checks: list[dict[str, Any]] = []
    max_btu_absolute = _max_abs(btu_residuals)
    max_btu_relative = _max_abs(btu_relative)
    btu_matches = all(
        math.isclose(
            record.btu,
            by_year[record.year].btu,
            rel_tol=BTU_RELATIVE_TOLERANCE,
            abs_tol=BTU_ABSOLUTE_TOLERANCE,
        )
        for record in records
    )
    checks.append(
        _check(
            "ccse_btu_matches_recovered_output",
            btu_matches,
            {
                "max_absolute_btu": max_btu_absolute,
                "max_relative": max_btu_relative,
            },
            {"max_absolute_btu": 0.0, "max_relative": 0.0},
            tolerance=(
                f"math.isclose(abs={BTU_ABSOLUTE_TOLERANCE}, "
                f"rel={BTU_RELATIVE_TOLERANCE})"
            ),
        )
    )
    max_co2_residual = _max_abs(co2_residuals)
    checks.append(
        _check(
            "ccse_conversion_matches_embedded_co2",
            max_co2_residual <= CO2_ABSOLUTE_TOLERANCE_TONNES,
            max_co2_residual,
            0.0,
            tolerance=CO2_ABSOLUTE_TOLERANCE_TONNES,
        )
    )
    max_volume_residual = _max_abs(volume_residuals)
    checks.append(
        _check(
            "ccse_conversion_matches_embedded_volume",
            max_volume_residual
            <= VOLUME_ABSOLUTE_TOLERANCE_MILLION_GALLONS,
            max_volume_residual,
            0.0,
            tolerance=VOLUME_ABSOLUTE_TOLERANCE_MILLION_GALLONS,
        )
    )

    actual_fit = {
        "intercept_log_liters_uncentered": float(intercept),
        "slope_per_year": float(slope),
        "annual_growth_rate": annual_growth,
        "r_squared_log_scale": r_squared,
        "rmse_log_scale": rmse,
        "intercept_log_energy_tj_at_center": centered_energy_intercept,
        "fit_start_year": fit_start,
        "fit_end_year": fit_end,
        "n_observations": int(np.sum(fit_mask)),
    }
    golden_fit = lineage["golden_log_linear_fit_recalculated"]
    fit_fields = {
        "slope_per_year": "slope_per_year",
        "annual_growth_rate": "annual_growth_rate",
        "r_squared_log_scale": "r_squared_log_scale",
        "rmse_log_scale": "rmse_log_scale",
        "intercept_log_energy_tj_at_center": "intercept_at_center",
    }
    for actual_name, golden_name in fit_fields.items():
        actual = float(actual_fit[actual_name])
        expected = float(golden_fit[golden_name])
        checks.append(
            _check(
                f"ccse_literal_np_polyfit_{actual_name}",
                abs(actual - expected) <= FIT_ABSOLUTE_TOLERANCE,
                actual,
                expected,
                tolerance=FIT_ABSOLUTE_TOLERANCE,
            )
        )

    golden_projection = lineage["golden_projection_notebook_outputs"]
    projection_co2_residuals: list[float] = []
    projection_volume_residuals: list[float] = []
    projection_scenario_residuals: list[float] = []
    for index, numeric_year in enumerate(forecast_years):
        year = str(int(numeric_year))
        expected = golden_projection[year]
        projection_co2_residuals.append(
            float(forecast_co2[index])
            - float(expected["reference_co2_tonnes"])
        )
        projection_volume_residuals.append(
            float(forecast_million_gallons[index])
            - float(expected["million_us_gallons"])
        )
        applied_reduction = (
            reduction if int(numeric_year) >= int(lineage["policy_start_year"]) else 0.0
        )
        calculated_scenario = float(forecast_co2[index]) * (1.0 - applied_reduction)
        projection_scenario_residuals.append(
            calculated_scenario
            - float(expected["scenario_co2_tonnes_policy_context"])
        )
    max_projection_co2 = _max_abs(projection_co2_residuals)
    max_projection_volume = _max_abs(projection_volume_residuals)
    max_projection_scenario = _max_abs(projection_scenario_residuals)
    checks.extend(
        [
            _check(
                "ccse_projection_matches_embedded_co2",
                max_projection_co2 <= PROJECTION_CO2_TOLERANCE_TONNES,
                max_projection_co2,
                0.0,
                tolerance=PROJECTION_CO2_TOLERANCE_TONNES,
            ),
            _check(
                "ccse_projection_matches_embedded_volume",
                max_projection_volume
                <= PROJECTION_VOLUME_TOLERANCE_MILLION_GALLONS,
                max_projection_volume,
                0.0,
                tolerance=PROJECTION_VOLUME_TOLERANCE_MILLION_GALLONS,
            ),
            _check(
                "ccse_projection_matches_embedded_policy_scenario",
                max_projection_scenario <= PROJECTION_CO2_TOLERANCE_TONNES,
                max_projection_scenario,
                0.0,
                tolerance=PROJECTION_CO2_TOLERANCE_TONNES,
            ),
        ]
    )

    historical = {
        "reference_co2_tonnes": historical_reference,
        "scenario_co2_tonnes": historical_scenario,
        "avoided_co2_tonnes": historical_avoided,
    }
    prospective = {
        "reference_co2_tonnes": prospective_reference,
        "scenario_co2_tonnes": prospective_scenario,
        "avoided_co2_tonnes": prospective_avoided,
    }
    integrated = {
        "reference_co2_tonnes": integrated_reference,
        "scenario_co2_tonnes": integrated_scenario,
        "avoided_co2_tonnes": integrated_avoided,
    }
    for field, expected in lineage["golden_historical_notebook_totals"].items():
        checks.append(
            _check(
                f"ccse_historical_total_{field}",
                abs(historical[field] - float(expected)) <= 1e-6,
                historical[field],
                float(expected),
                tolerance=1e-6,
            )
        )
    for field, expected in lineage["golden_integrated_figure_notebook_totals"].items():
        checks.append(
            _check(
                f"ccse_integrated_total_{field}",
                abs(integrated[field] - float(expected))
                <= PROJECTION_CO2_TOLERANCE_TONNES,
                integrated[field],
                float(expected),
                tolerance=PROJECTION_CO2_TOLERANCE_TONNES,
            )
        )

    published_by_period = {
        row["period_id"]: row for row in config["published_controls"]
    }
    for period_id, totals in (
        ("historical_1986_2023", historical),
        ("prospective_2026_2030", prospective),
    ):
        expected = published_by_period[period_id]
        for computed_name, expected_name in (
            ("reference_co2_tonnes", "reference_co2_tonnes"),
            ("scenario_co2_tonnes", "E10_co2_tonnes"),
            ("avoided_co2_tonnes", "E10_avoided_co2_tonnes"),
        ):
            rounded = _round_half_up(totals[computed_name])
            checks.append(
                _check(
                    f"ccse_published_rounding_{period_id}_{computed_name}",
                    rounded == int(expected[expected_name]),
                    rounded,
                    int(expected[expected_name]),
                )
            )

    return {
        "checks": checks,
        "max_residuals": {
            "btu_absolute": max_btu_absolute,
            "btu_relative": max_btu_relative,
            "co2_tonnes": max_co2_residual,
            "million_us_gallons": max_volume_residual,
            "projection_co2_tonnes": max_projection_co2,
            "projection_million_us_gallons": max_projection_volume,
            "projection_policy_co2_tonnes": max_projection_scenario,
        },
        "fit_literal_np_polyfit": actual_fit,
        "totals": {
            "historical_1986_2023": historical,
            "prospective_2026_2030": prospective,
            "integrated_figure_1986_2030": integrated,
        },
        "parameters": {
            "btu_to_mj": btu_to_mj,
            "gasoline_lhv_mj_per_liter": gasoline_lhv,
            "ethanol_lhv_mj_per_liter": ethanol_lhv,
            "liter_to_us_gallon": liter_to_us_gallon,
            "e10_volumetric_share": blend_share,
            "e10_energy_fraction": reduction,
            "co2_factor_tonnes_per_tj": co2_factor,
        },
    }


def verify_ccse_workbook(
    workbook_path: str | Path,
    *,
    repo_root: str | Path = DEFAULT_REPO_ROOT,
    expected_sha256: str | None = EXPECTED_WORKBOOK_SHA256,
) -> dict[str, Any]:
    """Verifica una copia autorizada sin incorporarla al repositorio.

    Si ``expected_sha256`` es ``None``, el digest se calcula únicamente para el
    proceso local y no se incluye en el informe retornado. Si se proporciona una
    huella, se conserva la verificación estricta y el informe sí muestra ambos
    valores para poder diagnosticar una discrepancia.
    """

    root = Path(repo_root).resolve()
    path = Path(workbook_path).resolve()
    actual_sha256 = sha256_file(path)
    records = read_ccse_workbook(path)
    with (root / "03_configuracion" / "emisiones_ttw.json").open(
        encoding="utf-8"
    ) as handle:
        config = json.load(handle)
    recovered_path = root / config["article_recovered_lineage"]["source_csv"]
    comparison = compare_ccse_records(
        records,
        load_recovered_controls(recovered_path),
        config,
    )
    if expected_sha256 is None:
        identity_check = _check(
            "ccse_workbook_identifier_sanitized",
            True,
            "calculated_locally_not_published",
            "identifier_omitted_in_public_review_branch",
            tolerance="not_applicable",
        )
    else:
        identity_check = _check(
            "ccse_workbook_sha256",
            actual_sha256 == expected_sha256,
            actual_sha256,
            expected_sha256,
        )

    checks = [
        identity_check,
        _check(
            "ccse_workbook_outside_repository",
            not path.is_relative_to(root),
            not path.is_relative_to(root),
            True,
        ),
        _check(
            "ccse_sheet_columns_rows",
            True,
            {
                "sheet": EXPECTED_SHEET_NAME,
                "columns": list(EXPECTED_HEADERS),
                "rows": len(records),
                "years": [records[0].year, records[-1].year],
            },
            {
                "sheet": EXPECTED_SHEET_NAME,
                "columns": list(EXPECTED_HEADERS),
                "rows": len(EXPECTED_YEARS),
                "years": [EXPECTED_YEARS[0], EXPECTED_YEARS[-1]],
            },
        ),
        *comparison["checks"],
    ]
    status = "PASS" if all(row["status"] == "PASS" for row in checks) else "FAIL"
    workbook_report: dict[str, Any] = {
        "filename": path.name,
        "sha256_publication": (
            "reported_for_explicit_local_identity_check"
            if expected_sha256 is not None
            else "calculated_locally_not_published"
        ),
        "sheet": EXPECTED_SHEET_NAME,
        "columns": list(EXPECTED_HEADERS),
        "row_count": len(records),
        "year_start": records[0].year,
        "year_end": records[-1].year,
        "stored_in_repository": path.is_relative_to(root),
        "redistributed_by_verifier": False,
    }
    if expected_sha256 is not None:
        workbook_report.update(
            {
                "sha256": actual_sha256,
                "expected_sha256": expected_sha256,
            }
        )

    return {
        "status": status,
        "workbook": workbook_report,
        "interpretation": {
            "computational_equivalence": (
                "Los valores del libro reproducen las salidas recuperadas del "
                "cuaderno y los totales reportados cuando todos los controles "
                "pasan."
            ),
            "binary_identity_limit": (
                "El cuaderno histórico no registró una huella del libro. La "
                "equivalencia computacional no demuestra identidad binaria con "
                "el archivo de la sesión original. Puede suministrarse una huella "
                "local explícita para controlar una copia concreta."
            ),
            "license_limit": (
                "No se infiere una licencia y el verificador no copia ni "
                "redistribuye el libro."
            ),
        },
        "checks": checks,
        "max_residuals": comparison["max_residuals"],
        "fit_literal_np_polyfit": comparison["fit_literal_np_polyfit"],
        "totals": comparison["totals"],
        "parameters": comparison["parameters"],
    }


__all__ = [
    "BTU_ABSOLUTE_TOLERANCE",
    "BTU_RELATIVE_TOLERANCE",
    "CcseRecord",
    "EXPECTED_HEADERS",
    "EXPECTED_SHEET_NAME",
    "EXPECTED_WORKBOOK_SHA256",
    "EXPECTED_YEARS",
    "RecoveredRecord",
    "compare_ccse_records",
    "load_recovered_controls",
    "read_ccse_workbook",
    "sha256_file",
    "validate_ccse_records",
    "verify_ccse_workbook",
]

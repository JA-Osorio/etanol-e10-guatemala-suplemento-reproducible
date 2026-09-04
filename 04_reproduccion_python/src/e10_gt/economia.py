"""Reconstrucción económica contemporánea para E10, E15 y E20.

La función pública :func:`ejecutar_economia` está diseñada para ser llamada por
el script maestro. Lee los parámetros trazables del repositorio, verifica los
CSV canónicos de la MIP fijada y mantiene separados:

* el escenario central de abastecimiento 100% importado, cuyo choque de demanda
  final doméstica es exactamente cero;
* la transmisión de costos por P068; y
* tres contrafactuales domésticos normalizados, nunca combinados entre sí.

Este módulo no reproduce las cifras económicas del manuscrito. Ese linaje se
trata en :mod:`e10_gt.economia_articulo`. Los recargos de entrega son
sensibilidades ilustrativas y el precio FOB no se presenta como costo entregado
observado en Guatemala.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


FUEL_CODE = "P068"
EXPECTED_MIP_VERSION = "1.0.0"
EXPECTED_MIP_DOI = "10.5281/zenodo.22086008"


@dataclass(frozen=True)
class MatrixData:
    codes: tuple[str, ...]
    labels: dict[str, str]
    values: np.ndarray


@dataclass(frozen=True)
class ModelInputs:
    codes: tuple[str, ...]
    labels: dict[str, str]
    a_domestic: np.ndarray
    a_imported: np.ndarray
    a_total: np.ndarray
    leontief_domestic: np.ndarray
    value_added_coeff: np.ndarray
    output_base: np.ndarray
    jobs_coeff: np.ndarray
    dependency_checks: tuple[dict[str, Any], ...]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_matrix(path: Path) -> MatrixData:
    rows = _read_rows(path)
    if not rows:
        raise ValueError(f"Matriz vacía: {path}")
    numeric_columns = tuple(
        column for column in rows[0] if column not in {"codigo", "producto"}
    )
    codes = tuple(row["codigo"] for row in rows)
    if numeric_columns != codes:
        raise ValueError(f"Filas y columnas no coinciden en {path}")
    values = np.array(
        [[float(row[column]) for column in numeric_columns] for row in rows],
        dtype=float,
    )
    labels = {row["codigo"]: row["producto"] for row in rows}
    return MatrixData(codes=codes, labels=labels, values=values)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _resolve_mip_files(
    mip_root: Path, dependency: Mapping[str, Any]
) -> tuple[dict[str, Path], tuple[dict[str, Any], ...]]:
    paths: dict[str, Path] = {}
    checks: list[dict[str, Any]] = []
    for item in dependency["archivos"]:
        path = mip_root / item["ruta"]
        if not path.is_file():
            raise FileNotFoundError(f"Falta el CSV canónico de la MIP: {path}")
        expected = item.get("sha256")
        if expected is None:
            expected = "".join(item["sha256_partes"])
        observed = _sha256(path)
        matches = observed == expected
        checks.append(
            {
                "control": f"sha256_{item['id']}",
                "valor": "coincide" if matches else "difiere",
                "esperado": "coincide",
                "cumple": matches,
            }
        )
        if not matches:
            raise ValueError(f"Huella SHA-256 inesperada para {path}")
        paths[item["id"]] = path
    return paths, tuple(checks)


def _load_inputs(mip_root: Path, dependency: Mapping[str, Any]) -> ModelInputs:
    files, dependency_checks = _resolve_mip_files(mip_root, dependency)
    products = _read_rows(files["productos"])
    codes = tuple(row["codigo"] for row in products)
    labels = {row["codigo"]: row["producto"] for row in products}

    matrices = {
        "a_domestic": _read_matrix(files["a_domestica"]),
        "a_imported": _read_matrix(files["a_importada"]),
        "a_total": _read_matrix(files["a_total"]),
        "leontief_domestic": _read_matrix(files["leontief_domestica"]),
    }
    for name, matrix in matrices.items():
        if matrix.codes != codes:
            raise ValueError(f"Orden de productos inconsistente en {name}")

    primary_rows = _read_rows(files["coeficientes_primarios"])
    production_rows = _read_rows(files["produccion_utilizacion"])
    if tuple(row["codigo"] for row in primary_rows) != codes:
        raise ValueError("Orden inconsistente en coeficientes primarios")
    if tuple(row["codigo"] for row in production_rows) != codes:
        raise ValueError("Orden inconsistente en producción y utilización")

    value_added_coeff = np.array(
        [float(row["valor_agregado_bruto"]) for row in primary_rows], dtype=float
    )
    output = np.array(
        [float(row["produccion_precios_basicos"]) for row in production_rows],
        dtype=float,
    )
    jobs = np.array(
        [float(row["puestos_trabajo"]) for row in production_rows], dtype=float
    )
    jobs_coeff = np.divide(jobs, output, out=np.zeros_like(jobs), where=output > 0)

    return ModelInputs(
        codes=codes,
        labels=labels,
        a_domestic=matrices["a_domestic"].values,
        a_imported=matrices["a_imported"].values,
        a_total=matrices["a_total"].values,
        leontief_domestic=matrices["leontief_domestic"].values,
        value_added_coeff=value_added_coeff,
        output_base=output,
        jobs_coeff=jobs_coeff,
        dependency_checks=dependency_checks,
    )


def calcular_costo_servicio(
    fraccion_alcohol: float,
    precio_gasolina_usd_galon: float,
    precio_alcohol_fob_usd_galon: float,
    razon_pci_alcohol_gasolina: float,
    recargo_entrega_ilustrativo: float,
) -> dict[str, float]:
    """Calcula costo y volúmenes relativos para servicio energético constante."""

    if not 0.0 < fraccion_alcohol < 1.0:
        raise ValueError("La fracción de alcohol debe estar entre cero y uno")
    if precio_gasolina_usd_galon <= 0 or precio_alcohol_fob_usd_galon <= 0:
        raise ValueError("Los precios deben ser positivos")
    if razon_pci_alcohol_gasolina <= 0:
        raise ValueError("La razón de PCI debe ser positiva")
    if recargo_entrega_ilustrativo < 0:
        raise ValueError("El recargo ilustrativo no puede ser negativo")

    energia_relativa = (
        1.0 - fraccion_alcohol
        + fraccion_alcohol * razon_pci_alcohol_gasolina
    )
    precio_ajustado = precio_alcohol_fob_usd_galon * (
        1.0 + recargo_entrega_ilustrativo
    )
    precio_nominal_mezcla = (
        (1.0 - fraccion_alcohol) * precio_gasolina_usd_galon
        + fraccion_alcohol * precio_ajustado
    )
    costo_servicio = precio_nominal_mezcla / energia_relativa
    return {
        "energia_relativa_mezcla": energia_relativa,
        "precio_alcohol_fob_referencia_usd_galon": precio_alcohol_fob_usd_galon,
        "precio_alcohol_ajustado_recargo_ilustrativo_usd_galon": precio_ajustado,
        "precio_nominal_mezcla_usd_galon": precio_nominal_mezcla,
        "costo_servicio_energetico_usd_galon_equivalente": costo_servicio,
        "cambio_precio_nominal_fraccion": (
            precio_nominal_mezcla / precio_gasolina_usd_galon - 1.0
        ),
        "cambio_costo_servicio_fraccion": (
            costo_servicio / precio_gasolina_usd_galon - 1.0
        ),
    }


def calcular_fraccion_referencia_comercial(
    referencia_galones: float, requerimiento_alcohol_galones: float
) -> float:
    """Devuelve referencia/requerimiento sin atribuir ejecución contractual."""

    if referencia_galones < 0:
        raise ValueError("La referencia comercial no puede ser negativa")
    if requerimiento_alcohol_galones <= 0:
        raise ValueError("El requerimiento de alcohol debe ser positivo")
    return referencia_galones / requerimiento_alcohol_galones


def transmitir_choque_costos(
    a_total: np.ndarray,
    leontief_domestic: np.ndarray,
    fuel_index: int,
    participacion_gasolina_p068: float,
    cambio_costo_servicio_fraccion: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Aplica ``A_total[P068,:] * s_gas * delta`` y propaga con ``L_d.T``."""

    if not 0.0 <= participacion_gasolina_p068 <= 1.0:
        raise ValueError("La participación de gasolina debe estar entre cero y uno")
    direct = (
        a_total[fuel_index, :]
        * participacion_gasolina_p068
        * cambio_costo_servicio_fraccion
    )
    propagated = leontief_domestic.T @ direct
    return direct, propagated


def calcular_contrafactuales_normalizados(
    leontief_domestic: np.ndarray,
    codes: Sequence[str],
    labels: Mapping[str, str],
    proxy_codes: Sequence[str],
    shock_million_q2013: float,
    value_added_coeff: np.ndarray,
    jobs_coeff: np.ndarray,
) -> list[dict[str, Any]]:
    """Resuelve una sensibilidad normalizada independiente para cada proxy."""

    if shock_million_q2013 <= 0:
        raise ValueError("El choque normalizado debe ser positivo")
    code_to_index = {code: index for index, code in enumerate(codes)}
    results: list[dict[str, Any]] = []
    for proxy_code in proxy_codes:
        if proxy_code not in code_to_index:
            raise ValueError(f"Proxy ausente de la MIP: {proxy_code}")
        proxy_index = code_to_index[proxy_code]
        final_demand = np.zeros(len(codes), dtype=float)
        final_demand[proxy_index] = shock_million_q2013
        output_change = leontief_domestic @ final_demand
        total_output = float(output_change.sum())
        value_added = float(value_added_coeff @ output_change)
        jobs = float(jobs_coeff @ output_change)
        results.append(
            {
                "codigo_proxy": proxy_code,
                "producto_proxy": labels[proxy_code],
                "naturaleza": "sensibilidad_domestica_normalizada_no_observada",
                "es_escenario_central": False,
                "choque_demanda_final_millones_q_2013": shock_million_q2013,
                "componentes_no_cero_choque": int(np.count_nonzero(final_demand)),
                "cambio_produccion_total_millones_q_2013": total_output,
                "cambio_produccion_indirecta_millones_q_2013": (
                    total_output - shock_million_q2013
                ),
                "multiplicador_produccion": total_output / shock_million_q2013,
                "cambio_valor_agregado_millones_q_2013": value_added,
                "multiplicador_valor_agregado": value_added / shock_million_q2013,
                "cambio_puestos_trabajo_modelados": jobs,
                "produccion_propia_proxy_millones_q_2013": float(
                    output_change[proxy_index]
                ),
            }
        )
    return results


def _validate_price_inputs(
    price_rows: Sequence[Mapping[str, str]], config: Mapping[str, Any]
) -> tuple[float, float, list[dict[str, Any]]]:
    gasoline_values = [
        float(row["valor_usd_galon"])
        for row in price_rows
        if row["producto"] == "gasolina_regular"
        and row["uso"] == "calculo_promedio"
    ]
    alcohol_values = [
        float(row["valor_usd_galon"])
        for row in price_rows
        if row["producto"] == "alcohol_carburante"
        and row["uso"] == "referencia_precio"
    ]
    if not gasoline_values or len(alcohol_values) != 1:
        raise ValueError("El archivo de precios no contiene las observaciones esperadas")
    gasoline_average = float(np.mean(gasoline_values))
    alcohol_fob = alcohol_values[0]
    controls = [
        {
            "control": "precio_gasolina_config_vs_promedio_csv",
            "valor": gasoline_average,
            "esperado": float(config["precio_gasolina_usd_galon"]),
            "cumple": bool(
                np.isclose(
                    gasoline_average,
                    float(config["precio_gasolina_usd_galon"]),
                    atol=1e-12,
                    rtol=0.0,
                )
            ),
        },
        {
            "control": "precio_alcohol_config_vs_referencia_fob_csv",
            "valor": alcohol_fob,
            "esperado": float(config["precio_alcohol_carburante_fob_usd_galon"]),
            "cumple": bool(
                np.isclose(
                    alcohol_fob,
                    float(config["precio_alcohol_carburante_fob_usd_galon"]),
                    atol=1e-12,
                    rtol=0.0,
                )
            ),
        },
    ]
    if not all(control["cumple"] for control in controls):
        raise ValueError("Los precios configurados no coinciden con precios_referencia.csv")
    return gasoline_average, alcohol_fob, controls


def _build_analytical_groups(
    codes: Sequence[str], rows: Sequence[Mapping[str, str]]
) -> list[dict[str, Any]]:
    """Expande rangos Pnnn y exige cobertura única de todos los productos."""

    def number(code: str) -> int:
        if len(code) != 4 or not code.startswith("P") or not code[1:].isdigit():
            raise ValueError(f"Código MIP inesperado: {code}")
        return int(code[1:])

    groups: list[dict[str, Any]] = []
    covered: list[str] = []
    for row in rows:
        start = number(row["codigo_inicio"])
        end = number(row["codigo_fin"])
        selected = tuple(
            index for index, code in enumerate(codes) if start <= number(code) <= end
        )
        if not selected:
            raise ValueError(f"Agregación vacía: {row['grupo_analitico']}")
        selected_codes = tuple(codes[index] for index in selected)
        covered.extend(selected_codes)
        groups.append(
            {
                "grupo_analitico": row["grupo_analitico"],
                "descripcion": row["descripcion"],
                "indices": selected,
                "codigos": selected_codes,
            }
        )
    if Counter(covered) != Counter(codes):
        raise ValueError("Los rangos analíticos no cubren cada producto exactamente una vez")
    return groups


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No hay filas para escribir en {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_json_ready(dict(payload)), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _format_report(
    grid_rows: Sequence[Mapping[str, Any]],
    aggregate_rows: Sequence[Mapping[str, Any]],
    counterfactual_rows: Sequence[Mapping[str, Any]],
    controls: Sequence[Mapping[str, Any]],
) -> str:
    lines = [
        "# Reconstrucción económica contemporánea E10/E15/E20",
        "",
        "## Lectura correcta",
        "",
        "Esta malla no reproduce las cifras económicas del manuscrito; es una reconstrucción separada con precios contemporáneos y la MIP canónica.",
        "",
        "El abastecimiento central es 100% importado y su choque de demanda final doméstica es cero. Los recargos de 0%, 15% y 30% tienen el mismo estatus: son sensibilidades ilustrativas aplicadas a una referencia FOB y no observaciones de costo entregado en Guatemala.",
        "",
        "## Malla de costos",
        "",
        "| Mezcla | Recargo ilustrativo | Cambio costo por servicio | Etanol requerido (millones gal) | Referencia comercial / requerimiento | Variación costo total (millones USD) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in grid_rows:
        if float(row["participacion_gasolina_en_p068"]) != min(
            float(item["participacion_gasolina_en_p068"]) for item in grid_rows
        ):
            continue
        lines.append(
            f"| {row['escenario']} | {float(row['recargo_entrega_ilustrativo_fraccion']):.0%} | "
            f"{float(row['cambio_costo_servicio_pct']):.6f}% | "
            f"{float(row['volumen_alcohol_millones_gal']):.3f} | "
            f"{float(row['porcentaje_requerimiento_alcohol_cubierto_por_referencia_comercial']):.2f}% | "
            f"{float(row['variacion_costo_total_millones_usd']):.3f} |"
        )
    lines.extend(
        [
            "",
            "La participación de gasolina dentro de P068 no modifica el costo físico de la mezcla; solo escala la transmisión IO. La tabla completa conserva 45.0% y 50.2% como sensibilidades paralelas.",
            "",
            "La referencia comercial de 50 millones de galones anuales se divide entre el requerimiento modelado de cada mezcla. Es una referencia de procedencia y escala: no se codifica como compra observada ni como contrato de adquisición.",
            "",
            "## Agregados E10 comparables",
            "",
            "Promedio ponderado por producción básica de 2013, con participación de gasolina en P068 de 45%:",
            "",
            "| Grupo | Recargo | Cambio propagado ponderado |",
            "|---|---:|---:|",
        ]
    )
    highlighted = {
        "agricultura_pesca_silvicultura",
        "quimica_farmaceutica",
        "transporte_logistica",
        "servicios_privados",
    }
    for row in aggregate_rows:
        if (
            row["escenario"] == "E10"
            and float(row["participacion_gasolina_en_p068"]) == 0.45
            and row["grupo_analitico"] in highlighted
        ):
            lines.append(
                f"| {row['grupo_analitico']} | "
                f"{float(row['recargo_entrega_ilustrativo_fraccion']):.0%} | "
                f"{float(row['efecto_precio_ponderado_produccion_pct']):.6f}% |"
            )
    lines.extend(
        [
            "",
            "## Contrafactuales domésticos normalizados",
            "",
            "| Proxy | Choque (millones Q 2013) | Multiplicador producción | Valor agregado | Puestos modelados |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in counterfactual_rows:
        lines.append(
            f"| {row['codigo_proxy']} | "
            f"{float(row['choque_demanda_final_millones_q_2013']):.2f} | "
            f"{float(row['multiplicador_produccion']):.6f} | "
            f"{float(row['cambio_valor_agregado_millones_q_2013']):.6f} | "
            f"{float(row['cambio_puestos_trabajo_modelados']):.3f} |"
        )
    failed = sum(not bool(row["cumple"]) for row in controls)
    lines.extend(
        [
            "",
            "## Verificación",
            "",
            f"Controles ejecutados: {len(controls)}. Fallos: {failed}.",
            "",
            "## Limitaciones decisivas",
            "",
            "- La referencia FOB y los recargos ilustrativos no sustituyen una cotización CIF o mayorista comparable en Guatemala.",
            "- P068 combina gasolina, diésel y fuel oils; 45.0% y 50.2% son sensibilidades de atribución.",
            "- La MIP es de 2013 y no identifica un producto específico de alcohol carburante.",
            "- P010, P052 y P055 son aproximaciones alternativas; sus efectos no deben sumarse.",
            "- Los puestos modelados escalan coeficientes medios de 2013 y no equivalen a empleo neto observado.",
            "",
        ]
    )
    return "\n".join(lines)


def ejecutar_economia(
    raiz_repositorio: str | Path,
    raiz_mip: str | Path,
    *,
    escribir_resultados: bool = True,
) -> dict[str, Any]:
    """Ejecuta el bloque económico y devuelve todas sus tablas en memoria.

    Parameters
    ----------
    raiz_repositorio:
        Raíz del suplemento que contiene configuración, precios y concordancia.
    raiz_mip:
        Raíz de la dependencia MIP fijada; debe conservar sus rutas canónicas.
    escribir_resultados:
        Si es verdadero, escribe tablas en ``06_resultados/economia`` y
        controles en ``07_verificacion``.
    """

    repo_root = Path(raiz_repositorio).resolve()
    mip_root = Path(raiz_mip).resolve()
    dependency = _read_json(repo_root / "03_configuracion" / "dependencia_mip.json")
    config = _read_json(repo_root / "03_configuracion" / "escenarios_economicos.json")
    price_rows = _read_rows(
        repo_root / "01_datos" / "insumos_publicables" / "precios_referencia.csv"
    )
    concordance_rows = _read_rows(
        repo_root / "02_concordancias" / "concordancia_mip_etanol.csv"
    )
    aggregation_rows = _read_rows(
        repo_root / "02_concordancias" / "agregaciones_economia.csv"
    )

    model = _load_inputs(mip_root, dependency)
    analytical_groups = _build_analytical_groups(model.codes, aggregation_rows)
    gasoline_price, alcohol_fob_price, price_controls = _validate_price_inputs(
        price_rows, config
    )
    code_to_index = {code: index for index, code in enumerate(model.codes)}
    if FUEL_CODE not in code_to_index:
        raise ValueError(f"{FUEL_CODE} no existe en la MIP")
    fuel_index = code_to_index[FUEL_CODE]

    proxy_codes = tuple(config["contrafactual_domestico"]["productos_alternativos"])
    concordance_proxies = tuple(
        row["codigo"]
        for row in concordance_rows
        if row["uso_en_modelo"] == "contrafactual_domestico"
    )
    if set(proxy_codes) != set(concordance_proxies):
        raise ValueError("Configuración y concordancia discrepan sobre los proxies")
    if not any(
        row["codigo"] == FUEL_CODE and row["uso_en_modelo"] == "transmision_costos"
        for row in concordance_rows
    ):
        raise ValueError("La concordancia no identifica P068 para transmisión de costos")

    recargos = tuple(float(value) for value in config["recargos_entrega_sensibilidad"])
    fuel_shares = tuple(
        float(value)
        for value in config["participaciones_gasolina_en_p068_sensibilidad"]
    )
    blends = tuple((name, float(value)) for name, value in config["mezclas"].items())
    baseline_gallons = float(config["volumen_referencia_gasolina_galones"])
    commercial_reference_gallons = float(
        config["referencia_comercial_eeuu_galones_anuales"]
    )
    lhv_ratio = float(config["razon_pci_alcohol_gasolina"])

    grid_rows: list[dict[str, Any]] = []
    price_effect_rows: list[dict[str, Any]] = []
    aggregate_effect_rows: list[dict[str, Any]] = []
    central_rows: list[dict[str, Any]] = []
    energy_residuals: list[float] = []
    cost_identity_residuals: list[float] = []
    commercial_reference_residuals: list[float] = []

    baseline_cost = baseline_gallons * gasoline_price
    for blend_name, alpha in blends:
        for surcharge in recargos:
            cost = calcular_costo_servicio(
                alpha,
                gasoline_price,
                alcohol_fob_price,
                lhv_ratio,
                surcharge,
            )
            energy_ratio = cost["energia_relativa_mezcla"]
            blend_gallons = baseline_gallons / energy_ratio
            alcohol_gallons = alpha * blend_gallons
            commercial_reference_fraction = calcular_fraccion_referencia_comercial(
                commercial_reference_gallons, alcohol_gallons
            )
            gasoline_gallons = (1.0 - alpha) * blend_gallons
            adjusted_alcohol_price = cost[
                "precio_alcohol_ajustado_recargo_ilustrativo_usd_galon"
            ]
            blend_total_cost = (
                gasoline_gallons * gasoline_price
                + alcohol_gallons * adjusted_alcohol_price
            )
            energy_residuals.append(
                abs(blend_gallons * energy_ratio - baseline_gallons)
            )
            cost_identity_residuals.append(
                abs(
                    blend_total_cost / baseline_cost
                    - 1.0
                    - cost["cambio_costo_servicio_fraccion"]
                )
            )
            commercial_reference_residuals.append(
                abs(
                    commercial_reference_fraction * alcohol_gallons
                    - commercial_reference_gallons
                )
            )

            for fuel_share in fuel_shares:
                direct, propagated = transmitir_choque_costos(
                    model.a_total,
                    model.leontief_domestic,
                    fuel_index,
                    fuel_share,
                    cost["cambio_costo_servicio_fraccion"],
                )
                largest_index = int(np.argmax(np.abs(propagated)))
                scenario_id = (
                    f"{blend_name}_r{int(round(surcharge * 100)):02d}_"
                    f"p068_{int(round(fuel_share * 1000)):03d}"
                )
                row = {
                    "id_escenario": scenario_id,
                    "escenario": blend_name,
                    "fraccion_alcohol": alpha,
                    "recargo_entrega_ilustrativo_fraccion": surcharge,
                    "recargo_es_dato_observado": False,
                    "participacion_gasolina_en_p068": fuel_share,
                    "energia_relativa_mezcla": energy_ratio,
                    "precio_gasolina_referencia_usd_galon": gasoline_price,
                    "precio_alcohol_fob_referencia_usd_galon": alcohol_fob_price,
                    "precio_alcohol_ajustado_recargo_ilustrativo_usd_galon": adjusted_alcohol_price,
                    "precio_ajustado_es_costo_entregado_observado": False,
                    "cambio_precio_nominal_pct": cost[
                        "cambio_precio_nominal_fraccion"
                    ]
                    * 100.0,
                    "cambio_costo_servicio_pct": cost[
                        "cambio_costo_servicio_fraccion"
                    ]
                    * 100.0,
                    "volumen_mezcla_millones_gal": blend_gallons / 1_000_000,
                    "volumen_alcohol_millones_gal": alcohol_gallons / 1_000_000,
                    "volumen_gasolina_millones_gal": gasoline_gallons / 1_000_000,
                    "gasolina_desplazada_millones_gal": (
                        baseline_gallons - gasoline_gallons
                    )
                    / 1_000_000,
                    "valor_alcohol_importado_fob_millones_usd": (
                        alcohol_gallons * alcohol_fob_price / 1_000_000
                    ),
                    "valor_alcohol_con_recargo_ilustrativo_millones_usd": (
                        alcohol_gallons * adjusted_alcohol_price / 1_000_000
                    ),
                    "referencia_comercial_eeuu_millones_gal_anuales": (
                        commercial_reference_gallons / 1_000_000
                    ),
                    "referencia_comercial_es_compra_observada": False,
                    "referencia_comercial_es_contrato_adquisicion": False,
                    "fraccion_requerimiento_alcohol_cubierta_por_referencia_comercial": (
                        commercial_reference_fraction
                    ),
                    "porcentaje_requerimiento_alcohol_cubierto_por_referencia_comercial": (
                        commercial_reference_fraction * 100.0
                    ),
                    "costo_total_mezcla_millones_usd": blend_total_cost / 1_000_000,
                    "variacion_costo_total_millones_usd": (
                        blend_total_cost - baseline_cost
                    )
                    / 1_000_000,
                    "procedencia_central": "100% importado",
                    "choque_demanda_final_domestica_millones_q_2013": 0.0,
                    "codigo_mayor_efecto_precio": model.codes[largest_index],
                    "mayor_efecto_precio_pct": float(propagated[largest_index] * 100.0),
                }
                grid_rows.append(row)
                central_rows.append(
                    {
                        "id_escenario": scenario_id,
                        "escenario": blend_name,
                        "recargo_entrega_ilustrativo_fraccion": surcharge,
                        "participacion_gasolina_en_p068": fuel_share,
                        "procedencia": "100% importado",
                        "choque_demanda_final_domestica_millones_q_2013": 0.0,
                        "cambio_produccion_domestica_millones_q_2013": 0.0,
                        "cambio_valor_agregado_domestico_millones_q_2013": 0.0,
                        "volumen_alcohol_importado_millones_gal": alcohol_gallons
                        / 1_000_000,
                        "referencia_comercial_eeuu_millones_gal_anuales": (
                            commercial_reference_gallons / 1_000_000
                        ),
                        "fraccion_requerimiento_alcohol_cubierta_por_referencia_comercial": (
                            commercial_reference_fraction
                        ),
                    }
                )
                for group in analytical_groups:
                    indices = np.array(group["indices"], dtype=int)
                    weights = model.output_base[indices]
                    total_weight = float(weights.sum())
                    weighted_effect = (
                        float(np.dot(propagated[indices], weights) / total_weight)
                        if total_weight > 0
                        else 0.0
                    )
                    aggregate_effect_rows.append(
                        {
                            "id_escenario": scenario_id,
                            "escenario": blend_name,
                            "recargo_entrega_ilustrativo_fraccion": surcharge,
                            "participacion_gasolina_en_p068": fuel_share,
                            "grupo_analitico": group["grupo_analitico"],
                            "descripcion": group["descripcion"],
                            "codigo_inicio": group["codigos"][0],
                            "codigo_fin": group["codigos"][-1],
                            "numero_productos": len(group["indices"]),
                            "produccion_base_millones_q_2013": total_weight,
                            "efecto_precio_ponderado_produccion_pct": weighted_effect
                            * 100.0,
                            "efecto_precio_minimo_producto_pct": float(
                                propagated[indices].min() * 100.0
                            ),
                            "efecto_precio_maximo_producto_pct": float(
                                propagated[indices].max() * 100.0
                            ),
                        }
                    )
                for index, code in enumerate(model.codes):
                    price_effect_rows.append(
                        {
                            "id_escenario": scenario_id,
                            "escenario": blend_name,
                            "recargo_entrega_ilustrativo_fraccion": surcharge,
                            "participacion_gasolina_en_p068": fuel_share,
                            "codigo": code,
                            "producto": model.labels[code],
                            "efecto_costo_directo_pct": float(direct[index] * 100.0),
                            "efecto_precio_propagado_pct": float(
                                propagated[index] * 100.0
                            ),
                        }
                    )

    counterfactual_rows = calcular_contrafactuales_normalizados(
        model.leontief_domestic,
        model.codes,
        model.labels,
        proxy_codes,
        float(
            config["contrafactual_domestico"][
                "choque_demanda_final_millones_quetzales"
            ]
        ),
        model.value_added_coeff,
        model.jobs_coeff,
    )

    identity = np.eye(len(model.codes))
    inverse_residual = float(
        np.max(
            np.abs(
                (identity - model.a_domestic) @ model.leontief_domestic - identity
            )
        )
    )
    decomposition_residual = float(
        np.max(np.abs(model.a_total - model.a_domestic - model.a_imported))
    )
    surcharge_counts = Counter(
        float(row["recargo_entrega_ilustrativo_fraccion"]) for row in grid_rows
    )
    controls: list[dict[str, Any]] = [
        *model.dependency_checks,
        *price_controls,
        {
            "control": "version_mip_fijada",
            "valor": dependency["version_dataset"],
            "esperado": EXPECTED_MIP_VERSION,
            "cumple": dependency["version_dataset"] == EXPECTED_MIP_VERSION,
        },
        {
            "control": "doi_mip_fijado",
            "valor": dependency["doi"],
            "esperado": EXPECTED_MIP_DOI,
            "cumple": dependency["doi"] == EXPECTED_MIP_DOI,
        },
        {
            "control": "residuo_inversa_leontief_domestica",
            "valor": inverse_residual,
            "esperado": "<=1e-10",
            "cumple": inverse_residual <= 1e-10,
        },
        {
            "control": "residuo_a_total_menos_domestica_importada",
            "valor": decomposition_residual,
            "esperado": "<=1e-12",
            "cumple": decomposition_residual <= 1e-12,
        },
        {
            "control": "malla_recargos_esperada",
            "valor": json.dumps(list(recargos)),
            "esperado": json.dumps([0.0, 0.15, 0.30]),
            "cumple": set(recargos) == {0.0, 0.15, 0.30},
        },
        {
            "control": "malla_participaciones_p068_esperada",
            "valor": json.dumps(list(fuel_shares)),
            "esperado": json.dumps([0.45, 0.502]),
            "cumple": set(fuel_shares) == {0.45, 0.502},
        },
        {
            "control": "malla_balanceada_por_recargo",
            "valor": json.dumps(dict(sorted(surcharge_counts.items()))),
            "esperado": "igual número de combinaciones por recargo",
            "cumple": len(set(surcharge_counts.values())) == 1,
        },
        {
            "control": "numero_combinaciones_malla",
            "valor": len(grid_rows),
            "esperado": len(blends) * len(recargos) * len(fuel_shares),
            "cumple": len(grid_rows)
            == len(blends) * len(recargos) * len(fuel_shares),
        },
        {
            "control": "cobertura_agregaciones_productos",
            "valor": sum(len(group["indices"]) for group in analytical_groups),
            "esperado": len(model.codes),
            "cumple": sum(len(group["indices"]) for group in analytical_groups)
            == len(model.codes),
        },
        {
            "control": "numero_filas_agregadas",
            "valor": len(aggregate_effect_rows),
            "esperado": len(grid_rows) * len(analytical_groups),
            "cumple": len(aggregate_effect_rows)
            == len(grid_rows) * len(analytical_groups),
        },
        {
            "control": "equivalencia_energetica_max_residuo_gal",
            "valor": max(energy_residuals),
            "esperado": "<=1e-6",
            "cumple": max(energy_residuals) <= 1e-6,
        },
        {
            "control": "identidad_costo_servicio_max_residuo",
            "valor": max(cost_identity_residuals),
            "esperado": "<=1e-12",
            "cumple": max(cost_identity_residuals) <= 1e-12,
        },
        {
            "control": "identidad_referencia_comercial_sobre_requerimiento_max_residuo_gal",
            "valor": max(commercial_reference_residuals),
            "esperado": "<=1e-6",
            "cumple": max(commercial_reference_residuals) <= 1e-6,
        },
        {
            "control": "escenario_central_sin_choque_domestico",
            "valor": max(
                abs(float(row["choque_demanda_final_domestica_millones_q_2013"]))
                for row in central_rows
            ),
            "esperado": 0.0,
            "cumple": all(
                float(row["choque_demanda_final_domestica_millones_q_2013"])
                == 0.0
                for row in central_rows
            ),
        },
        {
            "control": "recargos_no_marcados_como_observados",
            "valor": sum(bool(row["recargo_es_dato_observado"]) for row in grid_rows),
            "esperado": 0,
            "cumple": all(
                not bool(row["recargo_es_dato_observado"]) for row in grid_rows
            ),
        },
        {
            "control": "precios_ajustados_no_marcados_como_costo_entregado_observado",
            "valor": sum(
                bool(row["precio_ajustado_es_costo_entregado_observado"])
                for row in grid_rows
            ),
            "esperado": 0,
            "cumple": all(
                not bool(row["precio_ajustado_es_costo_entregado_observado"])
                for row in grid_rows
            ),
        },
        {
            "control": "contrafactuales_proxy_no_combinados",
            "valor": max(
                int(row["componentes_no_cero_choque"])
                for row in counterfactual_rows
            ),
            "esperado": 1,
            "cumple": all(
                int(row["componentes_no_cero_choque"]) == 1
                for row in counterfactual_rows
            ),
        },
        {
            "control": "escenario_minimo_diez_por_ciento",
            "valor": min(alpha for _, alpha in blends),
            "esperado": 0.10,
            "cumple": min(alpha for _, alpha in blends) >= 0.10,
        },
    ]
    if not all(bool(control["cumple"]) for control in controls):
        failures = [
            str(control["control"]) for control in controls if not control["cumple"]
        ]
        raise AssertionError("Fallaron controles económicos: " + ", ".join(failures))

    summary = {
        "dependencia_mip": {
            "version": dependency["version_dataset"],
            "doi": dependency["doi"],
            "commit_segmentado": "|".join(dependency["commit_fijado_partes"]),
            "reconstruccion_commit": "eliminar_barras_verticales",
        },
        "alcance": {
            "abastecimiento_central": "100% importado",
            "choque_demanda_final_domestica_central": 0.0,
            "recargos_entrega": (
                "sensibilidades ilustrativas sin jerarquía de dato observado"
            ),
            "contrafactuales_domesticos": "normalizados y separados",
        },
        "parametros": {
            "precio_gasolina_usd_galon": gasoline_price,
            "precio_alcohol_fob_usd_galon": alcohol_fob_price,
            "recargos_entrega_ilustrativos": list(recargos),
            "participaciones_gasolina_en_p068": list(fuel_shares),
            "razon_pci_alcohol_gasolina": lhv_ratio,
            "razon_pci_procedencia": dict(config["razon_pci_procedencia"]),
            "volumen_referencia_gasolina_galones": baseline_gallons,
            "referencia_comercial_eeuu_galones_anuales": (
                commercial_reference_gallons
            ),
            "referencia_comercial_es_compra_observada": False,
            "referencia_comercial_es_contrato_adquisicion": False,
        },
        "filas": {
            "malla": len(grid_rows),
            "efectos_precios": len(price_effect_rows),
            "efectos_agregados": len(aggregate_effect_rows),
            "contrafactuales_domesticos": len(counterfactual_rows),
        },
        "rangos": {
            "cambio_costo_servicio_pct": [
                min(float(row["cambio_costo_servicio_pct"]) for row in grid_rows),
                max(float(row["cambio_costo_servicio_pct"]) for row in grid_rows),
            ],
            "mayor_efecto_precio_pct": [
                min(float(row["mayor_efecto_precio_pct"]) for row in grid_rows),
                max(float(row["mayor_efecto_precio_pct"]) for row in grid_rows),
            ],
        },
        "controles_superados": True,
    }

    if escribir_resultados:
        economic_output = repo_root / "06_resultados" / "economia"
        _write_csv(economic_output / "malla_costos_importacion.csv", grid_rows)
        _write_csv(
            economic_output / "efectos_precios_mip_por_producto.csv",
            price_effect_rows,
        )
        _write_csv(
            economic_output / "efectos_precios_mip_agregados.csv",
            aggregate_effect_rows,
        )
        _write_csv(
            economic_output / "escenario_central_importado.csv", central_rows
        )
        _write_csv(
            economic_output / "contrafactuales_domesticos_normalizados.csv",
            counterfactual_rows,
        )
        _write_json(economic_output / "resumen_economia.json", summary)
        (economic_output / "informe_economia.md").write_text(
            _format_report(
                grid_rows,
                aggregate_effect_rows,
                counterfactual_rows,
                controls,
            ),
            encoding="utf-8",
        )
        _write_csv(repo_root / "07_verificacion" / "controles_economia.csv", controls)

    return {
        "malla": grid_rows,
        "efectos_precios": price_effect_rows,
        "efectos_agregados": aggregate_effect_rows,
        "escenario_central": central_rows,
        "contrafactuales_domesticos": counterfactual_rows,
        "controles": controls,
        "resumen": summary,
    }

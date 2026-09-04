"""Reproduccion forense del bloque economico del manuscrito.

Este modulo mantiene una frontera explicita entre tres ejercicios:

* ``E5_original`` reproduce el cuaderno historico recuperado;
* ``E10_misma_metodologia`` cambia solamente la fraccion de mezcla; y
* ``E10_penalizacion_lhv`` sustituye la penalizacion fija por el factor de
  energia de la mezcla. Este ultimo es una sensibilidad, no una reconstruccion
  del resultado historico.

Solo se usa NumPy y la biblioteca estandar. La instantanea histórica se
reconstruye desde la MIP v1.0.0 licenciada, con el offset P105 documentado, sin
redistribuir los artefactos del paquete E5 cuya licencia quedó pendiente.
"""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .descargas import resolver_mip


CONFIG_RELATIVE_PATH = Path("03_configuracion/economia_articulo.json")
EXPECTED_CODES = tuple(f"P{number:03d}" for number in range(1, 153))


@dataclass(frozen=True)
class LegacyInputs:
    """Instantánea histórica reconstruida, alineada por producto."""

    codes: tuple[str, ...]
    labels: dict[str, str]
    z: np.ndarray
    x: np.ndarray
    non_intermediate_residual: np.ndarray
    a_recomputed: np.ndarray
    leontief: np.ndarray
    category_by_code: dict[str, str]
    category_order: tuple[str, ...]
    input_hashes: tuple[dict[str, Any], ...]
    reconstruction_metadata: dict[str, Any]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _expected_hash(item: Mapping[str, Any]) -> str:
    if "sha256" in item:
        return str(item["sha256"])
    parts = item.get("sha256_partes")
    if not isinstance(parts, list) or not parts:
        raise ValueError(f"No hay huella para {item.get('id', 'archivo')}")
    return "".join(str(part) for part in parts)


def _read_canonical_matrix(
    path: Path,
) -> tuple[tuple[str, ...], dict[str, str], np.ndarray]:
    rows = _read_rows(path)
    if not rows:
        raise ValueError(f"Matriz vacía: {path}")
    codes = tuple(row["codigo"].strip() for row in rows)
    numeric_columns = tuple(
        column for column in rows[0] if column not in {"codigo", "producto"}
    )
    if codes != numeric_columns:
        raise ValueError(f"Filas y columnas no coinciden en {path}")
    labels = {row["codigo"].strip(): row["producto"].strip() for row in rows}
    values = np.array(
        [[float(row[code]) for code in codes] for row in rows], dtype=float
    )
    if not np.all(np.isfinite(values)):
        raise ValueError(f"Hay valores no finitos en {path}")
    return codes, labels, values


def _expand_code_spec(specification: str) -> set[str]:
    """Expande códigos individuales y rangos inclusivos como P001-P030."""

    codes: set[str] = set()
    for raw_token in specification.split(";"):
        token = raw_token.strip()
        if not token:
            continue
        if "-" not in token:
            if token not in EXPECTED_CODES:
                raise ValueError(f"Código desconocido en concordancia: {token}")
            codes.add(token)
            continue
        start_text, end_text = (part.strip() for part in token.split("-", 1))
        if start_text not in EXPECTED_CODES or end_text not in EXPECTED_CODES:
            raise ValueError(f"Rango desconocido en concordancia: {token}")
        start = int(start_text[1:])
        end = int(end_text[1:])
        if start > end:
            raise ValueError(f"Rango descendente en concordancia: {token}")
        codes.update(f"P{number:03d}" for number in range(start, end + 1))
    return codes


def _load_categories(
    repo_root: Path, config: Mapping[str, Any]
) -> tuple[dict[str, str], tuple[str, ...], dict[str, Any]]:
    """Lee y valida la concordancia sectorial usada por las salidas."""

    concordance = config["concordancia_agregaciones"]
    relative_path = Path(str(concordance["archivo"]))
    path = repo_root / relative_path
    observed_hash = _sha256(path)
    expected_hash = str(concordance["sha256"])
    if observed_hash != expected_hash:
        raise ValueError(
            f"Huella SHA-256 inesperada en {path}: {observed_hash}"
        )
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_fields = {
        "categoria",
        "codigos_incluidos",
        "codigos_excluidos",
        "uso",
        "origen",
    }
    if not rows or set(rows[0]) != expected_fields:
        raise ValueError(f"Concordancia vacía o con columnas inesperadas: {path}")

    category_by_code: dict[str, str] = {}
    category_order: list[str] = []
    complement_category: str | None = None
    for row in rows:
        category = row["categoria"].strip()
        if not category or category in category_order:
            raise ValueError(f"Categoría vacía o duplicada en {path}: {category!r}")
        category_order.append(category)
        included_spec = row["codigos_incluidos"].strip()
        if included_spec.casefold() == "complemento":
            if complement_category is not None:
                raise ValueError(f"Más de una categoría complemento en {path}")
            complement_category = category
            continue
        included = _expand_code_spec(included_spec)
        excluded = _expand_code_spec(row["codigos_excluidos"].strip())
        selected = included - excluded
        for code in sorted(selected):
            if code in category_by_code:
                raise ValueError(
                    f"Código {code} asignado a más de una categoría en {path}"
                )
            category_by_code[code] = category

    if complement_category is None:
        raise ValueError(f"Falta una categoría complemento en {path}")
    for code in EXPECTED_CODES:
        category_by_code.setdefault(code, complement_category)
    if set(category_by_code) != set(EXPECTED_CODES):
        raise ValueError(f"La concordancia no cubre exactamente P001-P152: {path}")
    hash_row = {
        "archivo": relative_path.as_posix(),
        "sha256_observado": observed_hash,
        "sha256_esperado": expected_hash,
        "coincide": True,
    }
    return category_by_code, tuple(category_order), hash_row


def _load_inputs(
    repo_root: Path, mip_root: Path, config: Mapping[str, Any]
) -> LegacyInputs:
    dependency = _read_json(
        repo_root / "03_configuracion" / "dependencia_mip.json"
    )
    items = {str(item["id"]): item for item in dependency["archivos"]}
    required_ids = ("productos", "z_domestica", "produccion_utilizacion")
    paths: dict[str, Path] = {}
    hash_rows: list[dict[str, Any]] = []
    for item_id in required_ids:
        item = items[item_id]
        path = mip_root / str(item["ruta"])
        if not path.is_file():
            raise FileNotFoundError(f"Falta el insumo canónico de la MIP: {path}")
        expected_hash = _expected_hash(item)
        observed_hash = _sha256(path)
        matches = observed_hash == expected_hash
        hash_rows.append(
            {
                "archivo": str(item["ruta"]),
                "sha256_observado": observed_hash,
                "sha256_esperado": expected_hash,
                "coincide": matches,
            }
        )
        if not matches:
            raise ValueError(
                f"Huella SHA-256 inesperada en {path}: {observed_hash}"
            )
        paths[item_id] = path

    product_rows = _read_rows(paths["productos"])
    codes_products = tuple(row["codigo"].strip() for row in product_rows)
    labels = {
        row["codigo"].strip(): row["producto"].strip()
        for row in product_rows
    }
    codes_z, labels_z, z = _read_canonical_matrix(paths["z_domestica"])
    production_rows = _read_rows(paths["produccion_utilizacion"])
    codes_x = tuple(row["codigo"].strip() for row in production_rows)
    if any(
        codes != EXPECTED_CODES for codes in (codes_products, codes_z, codes_x)
    ):
        raise ValueError("Los insumos canónicos no conservan el orden P001-P152")
    if labels != labels_z:
        raise ValueError("Las etiquetas de productos difieren dentro de la MIP")

    x = np.array(
        [
            float(row["total_utilizacion_precios_basicos"])
            for row in production_rows
        ],
        dtype=float,
    )
    reconstruction = config["reconstruccion_instantanea_historica"]
    adjustment = reconstruction["ajuste_x_historico"]
    adjusted_code = str(adjustment["codigo"])
    adjusted_index = EXPECTED_CODES.index(adjusted_code)
    canonical_value = float(x[adjusted_index])
    amount_subtracted = float(adjustment["restar_millones_q_2013"])
    x[adjusted_index] -= amount_subtracted
    expected_historical_value = float(
        adjustment["valor_resultante_millones_q_2013"]
    )
    if not np.isclose(
        x[adjusted_index],
        expected_historical_value,
        atol=5e-12,
        rtol=0.0,
    ):
        raise ValueError("El offset histórico P105 no produce el valor esperado")

    a_recomputed = np.divide(
        z,
        x[np.newaxis, :],
        out=np.zeros_like(z),
        where=x[np.newaxis, :] != 0.0,
    )
    leontief = np.linalg.inv(np.eye(len(EXPECTED_CODES)) - a_recomputed)
    non_intermediate_residual = x - np.sum(z, axis=0)
    category_by_code, category_order, category_hash = _load_categories(
        repo_root, config
    )
    hash_rows.append(category_hash)
    return LegacyInputs(
        codes=EXPECTED_CODES,
        labels=labels,
        z=z,
        x=x,
        non_intermediate_residual=non_intermediate_residual,
        a_recomputed=a_recomputed,
        leontief=leontief,
        category_by_code=category_by_code,
        category_order=category_order,
        input_hashes=tuple(hash_rows),
        reconstruction_metadata={
            "codigo_ajustado": adjusted_code,
            "x_canonico_millones_q_2013": canonical_value,
            "ajuste_restar_millones_q_2013": amount_subtracted,
            "x_historico_reconstruido_millones_q_2013": float(
                x[adjusted_index]
            ),
            "x_historico_esperado_millones_q_2013": expected_historical_value,
        },
    )


def _energy_factor(
    scenario: Mapping[str, Any], parameters: Mapping[str, Any]
) -> float:
    method = str(scenario["metodo_penalizacion"])
    mix = float(scenario["mezcla_etanol"])
    if method == "fija_original":
        return 1.0 + float(parameters["penalizacion_energetica_fija"])
    if method == "factor_lhv":
        gasoline_lhv = float(parameters["lhv_gasolina_mj_por_litro"])
        ethanol_lhv = float(parameters["lhv_etanol_mj_por_litro"])
        blend_lhv = (1.0 - mix) * gasoline_lhv + mix * ethanol_lhv
        return gasoline_lhv / blend_lhv
    raise ValueError(f"Metodo de penalizacion desconocido: {method}")


def _calculate_scenario(
    scenario: Mapping[str, Any],
    parameters: Mapping[str, Any],
    model: LegacyInputs,
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    mix = float(scenario["mezcla_etanol"])
    alpha = float(parameters["participacion_gasolina_en_p068"])
    gasoline_price = float(parameters["precio_gasolina_q_por_litro"])
    ethanol_price = float(parameters["precio_etanol_q_por_litro"])
    domestic_share = float(parameters["participacion_domestica_etanol"])
    if not (0.0 < mix < 1.0):
        raise ValueError("La mezcla de etanol debe estar entre cero y uno")
    if not (0.0 < alpha <= 1.0 and 0.0 < domestic_share <= 1.0):
        raise ValueError("Las participaciones deben ser mayores que cero y hasta uno")
    if gasoline_price <= 0.0 or ethanol_price <= 0.0:
        raise ValueError("Los precios deben ser positivos")

    fuel_code = str(parameters["codigo_combustibles"])
    cane_code = str(parameters["codigo_cana"])
    fuel_index = model.codes.index(fuel_code)
    cane_index = model.codes.index(cane_code)
    factor = _energy_factor(scenario, parameters)
    blend_price = (1.0 - mix) * gasoline_price + mix * ethanol_price
    r = (blend_price * factor / gasoline_price) - 1.0

    direct_price = r * alpha * model.a_recomputed[fuel_index, :]
    propagated_price = direct_price @ model.leontief

    total_p068_use = float(np.sum(model.z[fuel_index, :]))
    gasoline_base = total_p068_use * alpha
    total_ethanol_value = mix * gasoline_base
    domestic_ethanol_value = total_ethanol_value * domestic_share
    delta_y = np.zeros(len(model.codes), dtype=float)
    delta_y[cane_index] = domestic_ethanol_value
    delta_x = model.leontief @ delta_y
    residual_coeff = np.divide(
        model.non_intermediate_residual,
        model.x,
        out=np.zeros_like(model.non_intermediate_residual),
        where=model.x != 0.0,
    )
    delta_residual = residual_coeff * delta_x
    delta_y_total = float(np.sum(delta_y))
    delta_x_total = float(np.sum(delta_x))

    transport_indices = np.array(
        [model.codes.index("P104"), model.codes.index("P105")], dtype=int
    )
    summary = {
        "id_escenario": str(scenario["id"]),
        "etiqueta": str(scenario["etiqueta"]),
        "naturaleza": str(scenario["naturaleza"]),
        "mezcla_etanol_fraccion": mix,
        "metodo_penalizacion": str(scenario["metodo_penalizacion"]),
        "factor_energetico_aplicado": factor,
        "penalizacion_efectiva_fraccion": factor - 1.0,
        "precio_mezcla_q_por_litro": blend_price,
        "r_fraccion": float(r),
        "r_porcentaje": float(r * 100.0),
        "uso_total_p068_millones_q_2013": total_p068_use,
        "gasto_gasolina_base_millones_q_2013": gasoline_base,
        "valor_etanol_total_millones_q_2013": total_ethanol_value,
        "valor_etanol_domestico_millones_q_2013": domestic_ethanol_value,
        "delta_precio_directo_promedio_fraccion": float(np.mean(direct_price)),
        "delta_precio_total_promedio_fraccion": float(
            np.mean(propagated_price)
        ),
        "delta_precio_transporte_p104_p105_promedio_fraccion": float(
            np.mean(propagated_price[transport_indices])
        ),
        "delta_y_total_millones_q_2013": delta_y_total,
        "delta_x_total_millones_q_2013": delta_x_total,
        "delta_residual_no_intermedio_domestico_total_millones_q_2013": float(
            np.sum(delta_residual)
        ),
        "delta_x_p010_millones_q_2013": float(delta_x[cane_index]),
        "multiplicador_produccion": delta_x_total / delta_y_total,
    }
    arrays = {
        "delta_precio_directo": direct_price,
        "delta_precio_total": propagated_price,
        "delta_y": delta_y,
        "delta_x": delta_x,
        "delta_residual_no_intermedio_domestico": delta_residual,
    }
    return summary, arrays


def _product_rows(
    summaries: Sequence[Mapping[str, Any]],
    scenario_arrays: Mapping[str, Mapping[str, np.ndarray]],
    model: LegacyInputs,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        scenario_id = str(summary["id_escenario"])
        arrays = scenario_arrays[scenario_id]
        for index, code in enumerate(model.codes):
            rows.append(
                {
                    "id_escenario": scenario_id,
                    "naturaleza": summary["naturaleza"],
                    "codigo": code,
                    "producto": model.labels[code],
                    "categoria": model.category_by_code[code],
                    "delta_precio_directo_fraccion": float(
                        arrays["delta_precio_directo"][index]
                    ),
                    "delta_precio_total_fraccion": float(
                        arrays["delta_precio_total"][index]
                    ),
                    "delta_y_millones_q_2013": float(arrays["delta_y"][index]),
                    "delta_x_millones_q_2013": float(arrays["delta_x"][index]),
                    "delta_residual_no_intermedio_domestico_millones_q_2013": float(
                        arrays["delta_residual_no_intermedio_domestico"][index]
                    ),
                }
            )
    return rows


def _category_rows(
    summaries: Sequence[Mapping[str, Any]],
    scenario_arrays: Mapping[str, Mapping[str, np.ndarray]],
    model: LegacyInputs,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    indices_by_category = {
        category: np.array(
            [
                index
                for index, code in enumerate(model.codes)
                if model.category_by_code[code] == category
            ],
            dtype=int,
        )
        for category in model.category_order
    }
    demand_rows: list[dict[str, Any]] = []
    price_rows: list[dict[str, Any]] = []
    for summary in summaries:
        scenario_id = str(summary["id_escenario"])
        arrays = scenario_arrays[scenario_id]
        for category in model.category_order:
            indices = indices_by_category[category]
            demand_rows.append(
                {
                    "id_escenario": scenario_id,
                    "naturaleza": summary["naturaleza"],
                    "categoria": category,
                    "numero_productos": int(indices.size),
                    "delta_y_millones_q_2013": float(
                        np.sum(arrays["delta_y"][indices])
                    ),
                    "delta_x_millones_q_2013": float(
                        np.sum(arrays["delta_x"][indices])
                    ),
                    "delta_residual_no_intermedio_domestico_millones_q_2013": float(
                        np.sum(
                            arrays["delta_residual_no_intermedio_domestico"][
                                indices
                            ]
                        )
                    ),
                }
            )
            price_rows.append(
                {
                    "id_escenario": scenario_id,
                    "naturaleza": summary["naturaleza"],
                    "categoria": category,
                    "numero_productos": int(indices.size),
                    "delta_precio_directo_promedio_fraccion": float(
                        np.mean(arrays["delta_precio_directo"][indices])
                    ),
                    "delta_precio_total_promedio_fraccion": float(
                        np.mean(arrays["delta_precio_total"][indices])
                    ),
                    "delta_precio_total_minimo_fraccion": float(
                        np.min(arrays["delta_precio_total"][indices])
                    ),
                    "delta_precio_total_maximo_fraccion": float(
                        np.max(arrays["delta_precio_total"][indices])
                    ),
                }
            )
    return demand_rows, price_rows


def _row_value(
    rows: Sequence[Mapping[str, Any]], scenario_id: str, category: str, field: str
) -> float:
    return float(
        next(
            row[field]
            for row in rows
            if row["id_escenario"] == scenario_id and row["categoria"] == category
        )
    )


def _rounded_match(observed: float, published: float, decimals: int) -> bool:
    return round(float(observed), decimals) == round(float(published), decimals)


def _reconciliation_rows(
    summaries: Sequence[Mapping[str, Any]],
    demand_rows: Sequence[Mapping[str, Any]],
    price_rows: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_id = {str(row["id_escenario"]): row for row in summaries}
    e5 = by_id["E5_original"]
    e10 = by_id["E10_misma_metodologia"]
    reported = config["valores_reportados_manuscrito"]
    rows: list[dict[str, Any]] = []

    price_categories = {
        "Transporte": "Transporte y logistica",
        "Industria quimica": "Industria quimica ampliada",
        "Servicios": "Servicios (sin transporte y logistica)",
        "Agricultura": "Agricultura, silvicultura y pesca (sin P010)",
    }
    for label, category in price_categories.items():
        reported_value = float(reported["cost_push_porcentaje"][label])
        is_transport = label == "Transporte"
        if is_transport:
            value_e5 = 100.0 * float(
                e5["delta_precio_transporte_p104_p105_promedio_fraccion"]
            )
            value_e10 = 100.0 * float(
                e10["delta_precio_transporte_p104_p105_promedio_fraccion"]
            )
            comparable_metric = (
                "promedio de delta p propagado en P104-P105, como en el "
                "resumen historico"
            )
        else:
            value_e5 = 100.0 * _row_value(
                price_rows,
                "E5_original",
                category,
                "delta_precio_total_promedio_fraccion",
            )
            value_e10 = 100.0 * _row_value(
                price_rows,
                "E10_misma_metodologia",
                category,
                "delta_precio_total_promedio_fraccion",
            )
            comparable_metric = (
                "promedio simple de delta p propagado por categoria"
            )
        rows.append(
            {
                "id_afirmacion_manuscrito": f"cost_push_{label.lower().replace(' ', '_')}",
                "bloque": "cost_push",
                "etiqueta_manuscrito": label,
                "valor_reportado_manuscrito": reported_value,
                "unidad": "porcentaje",
                "metrica_comparable": comparable_metric,
                "valor_e5_recalculado": value_e5,
                "valor_e10_misma_metodologia": value_e10,
                "coincide_e5_con_manuscrito": _rounded_match(
                    value_e5, reported_value, 2
                ),
                "coincide_e10_con_manuscrito": _rounded_match(
                    value_e10, reported_value, 2
                ),
                "valor_alternativo_que_coincide": (
                    float(e5["r_porcentaje"]) if is_transport else None
                ),
                "metrica_alternativa": (
                    "r E5, choque inicial de la mezcla"
                    if is_transport
                    else ""
                ),
                "diagnostico": (
                    "1.53% coincide por redondeo con r del E5; no con el efecto propagado de transporte."
                    if is_transport
                    else "El porcentaje del manuscrito no se reproduce con la agregacion analitica explicita y la formula heredada."
                ),
            }
        )

    demand_categories = {
        "Cana de azucar": "Cana de azucar",
        "Industria quimica": "Industria quimica ampliada",
        "Servicios": "Servicios (sin transporte y logistica)",
        "Transporte": "Transporte y logistica",
    }
    for label, category in demand_categories.items():
        reported_value = float(
            reported["demand_pull_millones_q_2013"][label]
        )
        value_e5 = _row_value(
            demand_rows,
            "E5_original",
            category,
            "delta_x_millones_q_2013",
        )
        value_e10 = _row_value(
            demand_rows,
            "E10_misma_metodologia",
            category,
            "delta_x_millones_q_2013",
        )
        is_cane = label == "Cana de azucar"
        rows.append(
            {
                "id_afirmacion_manuscrito": f"demand_pull_{label.lower().replace(' ', '_')}",
                "bloque": "demand_pull",
                "etiqueta_manuscrito": label,
                "valor_reportado_manuscrito": reported_value,
                "unidad": "millones Q de 2013",
                "metrica_comparable": "delta x agregado por categoria",
                "valor_e5_recalculado": value_e5,
                "valor_e10_misma_metodologia": value_e10,
                "coincide_e5_con_manuscrito": _rounded_match(
                    value_e5, reported_value, 2
                ),
                "coincide_e10_con_manuscrito": _rounded_match(
                    value_e10, reported_value, 2
                ),
                "valor_alternativo_que_coincide": (
                    float(e5["delta_x_total_millones_q_2013"])
                    if is_cane
                    else None
                ),
                "metrica_alternativa": (
                    "delta x total E5" if is_cane else ""
                ),
                "diagnostico": (
                    "3.17 coincide por redondeo con delta x total E5; no con la produccion P010."
                    if is_cane
                    else "El valor del manuscrito no se reproduce con la agregacion analitica explicita y la formula heredada."
                ),
            }
        )

    total_reported = float(reported["demand_pull_millones_q_2013"]["Total"])
    rows.append(
        {
            "id_afirmacion_manuscrito": "demand_pull_total",
            "bloque": "demand_pull",
            "etiqueta_manuscrito": "Total",
            "valor_reportado_manuscrito": total_reported,
            "unidad": "millones Q de 2013",
            "metrica_comparable": "delta x total",
            "valor_e5_recalculado": float(
                e5["delta_x_total_millones_q_2013"]
            ),
            "valor_e10_misma_metodologia": float(
                e10["delta_x_total_millones_q_2013"]
            ),
            "coincide_e5_con_manuscrito": _rounded_match(
                float(e5["delta_x_total_millones_q_2013"]), total_reported, 2
            ),
            "coincide_e10_con_manuscrito": _rounded_match(
                float(e10["delta_x_total_millones_q_2013"]), total_reported, 2
            ),
            "valor_alternativo_que_coincide": None,
            "metrica_alternativa": "",
            "diagnostico": "4.77 no se reproduce ni para E5 ni para E10 con la logica heredada.",
        }
    )
    discussion_total = float(
        reported["inconsistencias_internas"][
            "demand_pull_total_discusion_millones_q_2013"
        ]
    )
    rows.append(
        {
            "id_afirmacion_manuscrito": "demand_pull_total_discusion",
            "bloque": "demand_pull",
            "etiqueta_manuscrito": "Total (discusion)",
            "valor_reportado_manuscrito": discussion_total,
            "unidad": "millones Q de 2013",
            "metrica_comparable": "delta x total",
            "valor_e5_recalculado": float(
                e5["delta_x_total_millones_q_2013"]
            ),
            "valor_e10_misma_metodologia": float(
                e10["delta_x_total_millones_q_2013"]
            ),
            "coincide_e5_con_manuscrito": _rounded_match(
                float(e5["delta_x_total_millones_q_2013"]),
                discussion_total,
                2,
            ),
            "coincide_e10_con_manuscrito": _rounded_match(
                float(e10["delta_x_total_millones_q_2013"]),
                discussion_total,
                2,
            ),
            "valor_alternativo_que_coincide": None,
            "metrica_alternativa": "",
            "diagnostico": (
                "La discusion dice 4.75, mientras el abstract, el resumen y "
                "la tabla demand-pull dicen 4.77; ninguno se reproduce con "
                "la logica heredada."
            ),
        }
    )
    multiplier_reported = float(reported["multiplicador_produccion"])
    rows.append(
        {
            "id_afirmacion_manuscrito": "multiplicador_produccion",
            "bloque": "demand_pull",
            "etiqueta_manuscrito": "Multiplicador",
            "valor_reportado_manuscrito": multiplier_reported,
            "unidad": "razon",
            "metrica_comparable": "delta x total / delta y total",
            "valor_e5_recalculado": float(e5["multiplicador_produccion"]),
            "valor_e10_misma_metodologia": float(e10["multiplicador_produccion"]),
            "coincide_e5_con_manuscrito": _rounded_match(
                float(e5["multiplicador_produccion"]), multiplier_reported, 2
            ),
            "coincide_e10_con_manuscrito": _rounded_match(
                float(e10["multiplicador_produccion"]), multiplier_reported, 2
            ),
            "valor_alternativo_que_coincide": None,
            "metrica_alternativa": "",
            "diagnostico": "1.13 no se reproduce; la matriz heredada arroja aproximadamente 1.687.",
        }
    )
    return rows


def _control(
    name: str,
    observed: Any,
    expected: Any,
    passes: bool,
    *,
    tolerance: float | None = None,
    interpretation: str = "",
) -> dict[str, Any]:
    return {
        "control": name,
        "valor_observado": observed,
        "valor_esperado": expected,
        "tolerancia_absoluta": tolerance,
        "cumple": bool(passes),
        "interpretacion": interpretation,
    }


def _controls(
    model: LegacyInputs,
    summaries: Sequence[Mapping[str, Any]],
    reconciliation: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    for row in model.input_hashes:
        controls.append(
            _control(
                f"sha256_{row['archivo']}",
                row["sha256_observado"],
                row["sha256_esperado"],
                bool(row["coincide"]),
            )
        )
    controls.append(
        _control(
            "dimension_productos",
            len(model.codes),
            152,
            len(model.codes) == 152,
        )
    )
    reconstruction = model.reconstruction_metadata
    controls.append(
        _control(
            "ajuste_historico_p105",
            reconstruction["x_historico_reconstruido_millones_q_2013"],
            reconstruction["x_historico_esperado_millones_q_2013"],
            bool(
                np.isclose(
                    reconstruction[
                        "x_historico_reconstruido_millones_q_2013"
                    ],
                    reconstruction["x_historico_esperado_millones_q_2013"],
                    atol=5e-12,
                    rtol=0.0,
                )
            ),
            tolerance=5e-12,
            interpretation=(
                "Se resta el offset P105 para reconstruir la variante de x "
                "usada por el cuaderno; la diferencia frente al ajuste "
                "CIF/FOB público es solo de redondeo."
            ),
        )
    )
    residual_definition_error = float(
        np.max(
            np.abs(
                model.non_intermediate_residual
                - (model.x - np.sum(model.z, axis=0))
            )
        )
    )
    controls.append(
        _control(
            "definicion_residual_no_intermedio_domestico",
            residual_definition_error,
            0.0,
            residual_definition_error <= 1e-12,
            tolerance=1e-12,
            interpretation="Es x menos la suma por columna de Z domestica; no VAB.",
        )
    )
    inverse_residual = float(
        np.max(
            np.abs(
                (np.eye(len(model.codes)) - model.a_recomputed)
                @ model.leontief
                - np.eye(len(model.codes))
            )
        )
    )
    controls.append(
        _control(
            "identidad_inversa_leontief",
            inverse_residual,
            0.0,
            inverse_residual <= 1e-12,
            tolerance=1e-12,
        )
    )
    by_id = {str(row["id_escenario"]): row for row in summaries}
    tolerance = float(config["tolerancia_golden_absoluta"])
    numeric_references = {
        "E5_original": config["golden_e5_cuaderno_recuperado"],
        "E10_misma_metodologia": config[
            "referencia_e10_recalculo_misma_metodologia"
        ],
    }
    for scenario_id, expected_metrics in numeric_references.items():
        actual = by_id[scenario_id]
        for field, expected in expected_metrics.items():
            observed = float(actual[field])
            controls.append(
                _control(
                    f"golden_{scenario_id}_{field}",
                    observed,
                    float(expected),
                    bool(np.isclose(observed, expected, atol=tolerance, rtol=0.0)),
                    tolerance=tolerance,
                )
            )

    recon_by_id = {
        str(row["id_afirmacion_manuscrito"]): row for row in reconciliation
    }
    transport = recon_by_id["cost_push_transporte"]
    cane = recon_by_id["demand_pull_cana_de_azucar"]
    controls.extend(
        [
            _control(
                "1_53_es_r_e5_por_redondeo",
                float(by_id["E5_original"]["r_porcentaje"]),
                1.53,
                _rounded_match(
                    float(by_id["E5_original"]["r_porcentaje"]), 1.53, 2
                ),
                interpretation="Es el choque inicial r, no el precio propagado de transporte.",
            ),
            _control(
                "1_53_no_es_transporte_propagado",
                float(transport["valor_e5_recalculado"]),
                1.53,
                not bool(transport["coincide_e5_con_manuscrito"]),
            ),
            _control(
                "3_17_es_delta_x_total_e5_por_redondeo",
                float(
                    by_id["E5_original"]["delta_x_total_millones_q_2013"]
                ),
                3.17,
                _rounded_match(
                    float(
                        by_id["E5_original"][
                            "delta_x_total_millones_q_2013"
                        ]
                    ),
                    3.17,
                    2,
                ),
                interpretation="Es el total de produccion E5, no la produccion de P010.",
            ),
            _control(
                "3_17_no_es_delta_x_p010",
                float(cane["valor_e5_recalculado"]),
                3.17,
                not bool(cane["coincide_e5_con_manuscrito"]),
            ),
        ]
    )
    non_reproducible_ids = (
        "cost_push_industria_quimica",
        "cost_push_servicios",
        "cost_push_agricultura",
        "demand_pull_industria_quimica",
        "demand_pull_servicios",
        "demand_pull_transporte",
        "demand_pull_total",
        "demand_pull_total_discusion",
        "multiplicador_produccion",
    )
    for result_id in non_reproducible_ids:
        row = recon_by_id[result_id]
        controls.append(
            _control(
                f"manuscrito_no_reproducido_{result_id}",
                f"E5={row['valor_e5_recalculado']}; E10={row['valor_e10_misma_metodologia']}",
                "no coincide con el valor reportado en el manuscrito",
                not bool(row["coincide_e5_con_manuscrito"])
                and not bool(row["coincide_e10_con_manuscrito"]),
            )
        )
    return controls


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No hay filas para escribir en {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rows[0]), lineterminator="\n"
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
    summaries: Sequence[Mapping[str, Any]],
    reconciliation: Sequence[Mapping[str, Any]],
    controls: Sequence[Mapping[str, Any]],
    manuscript_source: Mapping[str, Any],
) -> str:
    by_id = {str(row["id_escenario"]): row for row in summaries}
    e5 = by_id["E5_original"]
    lines = [
        "# Reconciliacion del calculo economico del manuscrito",
        "",
        "## Version del manuscrito",
        "",
        f"Titulo: *{manuscript_source['titulo']}*.",
        "",
        f"Archivo no redistribuido: `{manuscript_source['archivo_origen']}`.",
        "",
        f"SHA-256: `{manuscript_source['sha256']}`.",
        "",
        "## Resultado principal",
        "",
        "El calculo recuperado es un escenario E5. El 1.53% reportado en el manuscrito coincide con el choque inicial `r` de E5, no con el efecto de precios propagado para transporte. De forma analoga, Q3.17 millones coincide con el cambio de produccion total de E5, no con la produccion de cana P010.",
        "",
        "## Escenarios calculados",
        "",
        "| Escenario | Naturaleza | Mezcla | Penalizacion efectiva | r | Delta y (millones Q 2013) | Delta x (millones Q 2013) | Residual no intermedio domestico (millones Q 2013) | Multiplicador |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        lines.append(
            f"| {row['id_escenario']} | {row['naturaleza']} | "
            f"{float(row['mezcla_etanol_fraccion']):.0%} | "
            f"{float(row['penalizacion_efectiva_fraccion']):.6%} | "
            f"{float(row['r_porcentaje']):.6f}% | "
            f"{float(row['delta_y_total_millones_q_2013']):.6f} | "
            f"{float(row['delta_x_total_millones_q_2013']):.6f} | "
            f"{float(row['delta_residual_no_intermedio_domestico_total_millones_q_2013']):.6f} | "
            f"{float(row['multiplicador_produccion']):.6f} |"
        )
    lines.extend(
        [
            "",
            "Con la penalizacion fija de 3%, cambiar solo la mezcla de 5% a 10% reduce `r` de 1.528571% a 0.057143%. Esto es una consecuencia aritmetica de los precios heredados (Q10.50 y Q7.50 por litro), no una hipotesis nueva.",
            "",
            "La fila `E10_penalizacion_lhv` reemplaza el factor fijo 1.03 por `32 / ((1-mix)*32 + mix*21.2)`. Se reporta como sensibilidad fisica separada y no se usa para afirmar que el cuaderno original calculo E10.",
            "",
            "La sensibilidad LHV modifica solo el canal de precios. Conserva sin cambios el choque de demanda del E10 comparable; no ajusta volumen de etanol ni demanda por servicio energetico.",
            "",
            "La columna de residual reproduce la variable historica llamada `Delta VA`, pero `VA_2013_total.csv` es `x - suma Z domestica`; no representa valor agregado bruto y no debe interpretarse como VAB.",
            "",
            "## Reconciliacion de cifras reportadas en el manuscrito",
            "",
            "| Bloque | Cifra/etiqueta | Manuscrito | E5 recalculado | E10 misma metodologia | Diagnostico |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in reconciliation:
        lines.append(
            f"| {row['bloque']} | {row['etiqueta_manuscrito']} | "
            f"{float(row['valor_reportado_manuscrito']):.6f} | "
            f"{float(row['valor_e5_recalculado']):.6f} | "
            f"{float(row['valor_e10_misma_metodologia']):.6f} | "
            f"{row['diagnostico']} |"
        )
    failed = sum(not bool(row["cumple"]) for row in controls)
    lines.extend(
        [
            "",
            "## Lectura forense",
            "",
            f"- E5 reproducido: `r={float(e5['r_fraccion']):.15f}`, `Delta x={float(e5['delta_x_total_millones_q_2013']):.12f}` y `Delta x P010={float(e5['delta_x_p010_millones_q_2013']):.12f}`.",
            "- Los valores Q0.8 millones (quimica), Q0.5 millones (servicios), Q0.3 millones (transporte), Q4.77 millones (total del abstract, resumen y tabla demand-pull), Q4.75 millones (total de la discusion) y el multiplicador 1.13 no salen de los CSV y formulas recuperados.",
            "- Los resultados por producto permiten rastrear cada agregado hasta P001-P152.",
            "",
            "## Verificacion",
            "",
            f"Controles ejecutados: {len(controls)}. Fallos: {failed}.",
            "",
        ]
    )
    return "\n".join(lines)


def ejecutar_economia_articulo(
    repo_root: str | Path,
    escribir_resultados: bool = True,
    *,
    raiz_mip: str | Path | None = None,
) -> dict[str, Any]:
    """Ejecuta la reproduccion E5 y los dos recalculos E10.

    Parameters
    ----------
    repo_root:
        Raiz del repositorio.
    raiz_mip:
        Raíz local opcional de la MIP fijada. Si se omite, se usa el resolvedor
        verificado del suplemento.
    escribir_resultados:
        Si es verdadero, escribe siete salidas de resultados y la tabla de
        controles en las rutas declaradas en la configuracion.
    """

    root = Path(repo_root).resolve()
    config = _read_json(root / CONFIG_RELATIVE_PATH)
    mip_root = resolver_mip(root, raiz_mip)
    model = _load_inputs(root, mip_root, config)
    parameters = config["parametros_originales"]

    summaries: list[dict[str, Any]] = []
    arrays_by_scenario: dict[str, dict[str, np.ndarray]] = {}
    for scenario in config["escenarios"]:
        summary, arrays = _calculate_scenario(scenario, parameters, model)
        summaries.append(summary)
        arrays_by_scenario[str(summary["id_escenario"])] = arrays

    product_rows = _product_rows(summaries, arrays_by_scenario, model)
    demand_rows, price_rows = _category_rows(
        summaries, arrays_by_scenario, model
    )
    reconciliation = _reconciliation_rows(
        summaries, demand_rows, price_rows, config
    )
    controls = _controls(model, summaries, reconciliation, config)
    all_controls_pass = all(bool(row["cumple"]) for row in controls)
    report = _format_report(
        summaries, reconciliation, controls, config["fuente_manuscrito"]
    )
    payload: dict[str, Any] = {
        "estado": "controles_aprobados" if all_controls_pass else "controles_fallidos",
        "lectura_principal": {
            "escenario_historico_identificado": "E5_original",
            "1_53_por_ciento": "r E5; no efecto propagado de transporte",
            "3_17_millones_q_2013": "delta x total E5; no produccion P010",
            "sensibilidad_lhv_separada": True,
            "sensibilidad_lhv_solo_canal_precios": True,
            "variable_va_historica_es_residual_no_vab": True,
        },
        "fuente_manuscrito": config["fuente_manuscrito"],
        "reconstruccion_instantanea_historica": model.reconstruction_metadata,
        "escenarios": summaries,
        "resultados_por_producto": product_rows,
        "categorias_demanda": demand_rows,
        "categorias_precios": price_rows,
        "reconciliacion_articulo": reconciliation,
        "controles": controls,
        "insumos": list(model.input_hashes),
        "todos_los_controles_cumplen": all_controls_pass,
    }

    if not all_controls_pass:
        failed = [
            str(row["control"]) for row in controls if not bool(row["cumple"])
        ]
        raise AssertionError(
            "Fallaron controles de la economía del manuscrito: "
            + ", ".join(failed)
        )

    if escribir_resultados:
        output_dir = root / str(config["salidas"]["directorio"])
        paths = {
            "resumen_escenarios": output_dir / "resumen_escenarios.csv",
            "resultados_por_producto": output_dir
            / "resultados_por_producto.csv",
            "categorias_demanda": output_dir / "categorias_demanda.csv",
            "categorias_precios": output_dir / "categorias_precios.csv",
            "reconciliacion_articulo": output_dir
            / "reconciliacion_articulo.csv",
            "resumen_json": output_dir / "resumen_economia_articulo.json",
            "informe": output_dir / "informe_reconciliacion.md",
            "controles": root / str(config["salidas"]["controles"]),
        }
        _write_csv(paths["resumen_escenarios"], summaries)
        _write_csv(paths["resultados_por_producto"], product_rows)
        _write_csv(paths["categorias_demanda"], demand_rows)
        _write_csv(paths["categorias_precios"], price_rows)
        _write_csv(paths["reconciliacion_articulo"], reconciliation)
        _write_csv(paths["controles"], controls)
        summary_for_json = {
            "estado": payload["estado"],
            "lectura_principal": payload["lectura_principal"],
            "fuente_manuscrito": payload["fuente_manuscrito"],
            "reconstruccion_instantanea_historica": payload[
                "reconstruccion_instantanea_historica"
            ],
            "escenarios": summaries,
            "reconciliacion_articulo": reconciliation,
            "controles": controls,
            "insumos": list(model.input_hashes),
            "todos_los_controles_cumplen": all_controls_pass,
        }
        _write_json(paths["resumen_json"], summary_for_json)
        paths["informe"].write_text(report, encoding="utf-8")
        payload["archivos_escritos"] = {
            key: str(path.relative_to(root)) for key, path in paths.items()
        }
    else:
        payload["archivos_escritos"] = {}
    return payload


__all__ = ["ejecutar_economia_articulo"]

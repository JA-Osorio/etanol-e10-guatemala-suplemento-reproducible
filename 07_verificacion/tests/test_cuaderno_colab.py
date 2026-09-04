"""Pruebas estructurales del cuaderno Colab auditable."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = (
    REPO_ROOT / "05_cuaderno_colab" / "reproducir_resultados_e10.ipynb"
)
README_PATH = REPO_ROOT / "README.md"

EXPECTED_IDS = [
    "portada",
    "mapa-auditoria",
    "preparar-entorno",
    "ejecutar-pipeline",
    "cargar-salidas",
    "linaje-explicacion",
    "mostrar-linaje",
    "mat-mip",
    "resultado-mip",
    "mat-cost-push",
    "resultado-cost-push",
    "mat-demand-pull",
    "resultado-demand-pull",
    "reconciliacion-explicacion",
    "mostrar-reconciliacion",
    "alcance-contrafactual-recuperado",
    "mat-emisiones-historicas",
    "resultado-emisiones-historicas",
    "mat-consumo-articulo",
    "resultado-consumo-articulo",
    "mat-proyeccion-articulo",
    "resultado-proyeccion-articulo",
    "mat-integracion-articulo",
    "resultado-integracion-articulo",
    "conciliacion-agregada-explicacion",
    "resultado-conciliacion-agregada",
    "separacion-eia",
    "mat-proyeccion-eia",
    "resultado-proyeccion-eia-opcional",
    "mat-emisiones-eia",
    "resultado-emisiones-eia-opcional",
    "controles-explicacion",
    "mostrar-controles",
]


def _notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _source(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def test_readme_opens_the_same_review_branch_in_colab() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    expected = (
        "https://colab.research.google.com/github/JA-Osorio/"
        "etanol-e10-guatemala-suplemento-reproducible/blob/"
        "revision-e5-e10-trazabilidad/05_cuaderno_colab/"
        "reproducir_resultados_e10.ipynb"
    )
    assert expected in readme


def test_notebook_is_clean_and_has_stable_unique_ids() -> None:
    notebook = _notebook()
    ids = [cell.get("id") for cell in notebook["cells"]]
    assert ids == EXPECTED_IDS
    assert len(ids) == len(set(ids))
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            assert cell["execution_count"] is None
            assert cell["outputs"] == []


def test_every_code_cell_is_folded_in_colab_and_jupyter() -> None:
    code_cells = [
        cell for cell in _notebook()["cells"] if cell["cell_type"] == "code"
    ]
    assert code_cells
    for cell in code_cells:
        source = _source(cell)
        first_line = source.splitlines()[0]
        assert first_line.startswith("#@title ")
        assert '{ display-mode: "form" }' in first_line
        assert cell["metadata"]["cellView"] == "form"
        assert cell["metadata"]["jupyter"]["source_hidden"] is True
        assert "hide-input" in cell["metadata"]["tags"]


def test_notebook_exposes_math_and_numeric_substitution_before_results() -> None:
    notebook = _notebook()
    by_id = {cell["id"]: _source(cell) for cell in notebook["cells"]}
    required_math = {
        "mat-mip": ["A_{ij}", "L=(I-A)^{-1}", "v^{\\mathrm{res}}_j"],
        "mat-cost-push": ["r_s", "A_{P068,j}", "\\Delta p"],
        "mat-demand-pull": ["\\Delta y", "\\Delta x=L\\Delta y", "m="],
        "mat-emisiones-historicas": [
            "q=\\frac{21.1}{32}",
            "f_e=",
            "E_t[\\mathrm{TJ}]",
            "C_{E10,t}",
        ],
        "mat-consumo-articulo": [
            "Litros_t",
            "G_t[\\mathrm{millones\\ de\\ gal}]",
        ],
        "mat-proyeccion-articulo": [
            "\\ln(Litros_t)",
            "\\ln(E_t)",
            "\\widehat E_t",
            "b=\\beta_1",
            "Litros_t=E_t10^6/32",
            "2014",
            "2026",
        ],
        "mat-integracion-articulo": [
            "s_t^{integrada}=0.10",
            "C_{s,t}^{integrada}",
            "2024–2025",
        ],
        "mat-proyeccion-eia": [
            "\\ln(E_t)",
            "\\widehat E_t",
            "g=\\exp(b)-1",
        ],
        "mat-emisiones-eia": ["C_{E0,t}", "C_{E10,t}", "C_{evitado,t}"],
    }
    for cell_id, fragments in required_math.items():
        for fragment in fragments:
            assert fragment in by_id[cell_id]

    result_cells = {
        "resultado-mip",
        "resultado-cost-push",
        "resultado-demand-pull",
        "resultado-emisiones-historicas",
        "resultado-consumo-articulo",
        "resultado-proyeccion-articulo",
        "resultado-integracion-articulo",
        "resultado-proyeccion-eia-opcional",
        "resultado-emisiones-eia-opcional",
    }
    for cell_id in result_cells:
        assert "Sustituci" in by_id[cell_id]


def test_each_dynamic_figure_has_its_math_first() -> None:
    cells = _notebook()["cells"]
    positions = {cell["id"]: index for index, cell in enumerate(cells)}
    mappings = {
        "crear_figura_cost_push(": ("mat-cost-push", "resultado-cost-push"),
        "crear_figura_demand_pull(": (
            "mat-demand-pull",
            "resultado-demand-pull",
        ),
        "crear_figura_emisiones_articulo_historica(": (
            "mat-emisiones-historicas",
            "resultado-emisiones-historicas",
        ),
        "crear_figura_consumo_articulo(": (
            "mat-consumo-articulo",
            "resultado-consumo-articulo",
        ),
        "crear_figura_emisiones_articulo_prospectiva(": (
            "mat-proyeccion-articulo",
            "resultado-proyeccion-articulo",
        ),
        "crear_figura_emisiones_articulo_integrada(": (
            "mat-integracion-articulo",
            "resultado-integracion-articulo",
        ),
        "crear_figura_emisiones_eia(": (
            "mat-proyeccion-eia",
            "resultado-proyeccion-eia-opcional",
        ),
        "crear_figura_emisiones_evitadas(": (
            "mat-emisiones-eia",
            "resultado-emisiones-eia-opcional",
        ),
    }
    for call, (math_id, result_id) in mappings.items():
        source = _source(cells[positions[result_id]])
        assert call in source
        assert positions[math_id] < positions[result_id]
        assert cells[positions[math_id]]["cell_type"] == "markdown"


def test_figures_are_plotly_and_no_static_image_stack_is_used() -> None:
    all_source = "\n".join(_source(cell) for cell in _notebook()["cells"])
    lower = all_source.lower()
    assert "plotly" in lower
    assert "visualizaciones_interactivas" in all_source
    assert ".png" not in lower
    assert "matplotlib" not in lower
    assert "ipython.display import image" not in lower
    assert "write_image" not in lower


def test_pipeline_tests_and_fixed_references_are_explicit() -> None:
    all_source = "\n".join(_source(cell) for cell in _notebook()["cells"])
    assert "REF_REPO" in all_source
    assert 'DEFAULT_REF_REPO = "revision-e5-e10-trazabilidad"' in all_source
    assert "REF_REPO_SOLICITADA or DEFAULT_REF_REPO" in all_source
    assert "referencia mutable" in all_source
    assert '"git", "status", "--porcelain"' in all_source
    assert "cambios sin commit" in all_source
    assert "v1.0.0" in all_source
    assert "5056c15fdeb4527bbee47c9e53d1c3d8dcee3ae3" in all_source
    assert '"--sin-figuras"' in all_source
    assert '"pytest", "-q", "07_verificacion/tests"' in all_source


def test_only_generated_csv_json_are_read_for_quantitative_results() -> None:
    all_source = "\n".join(_source(cell) for cell in _notebook()["cells"])
    assert "pd.read_csv(ruta_salida(nombre))" in all_source
    assert '"06_resultados/' in all_source
    assert '"07_verificacion/' in all_source
    assert '"01_datos/' not in all_source
    assert '"03_configuracion/' not in all_source
    assert "read_excel" not in all_source


def test_scope_separates_economy_recovered_article_and_eia_update() -> None:
    all_source = "\n".join(_source(cell) for cell in _notebook()["cells"])
    lower = all_source.lower()
    assert "contrafactual anual recuperado del artículo" in lower
    assert "copia recuperada del libro primario externo" in lower
    assert "coinciden 38/38 observaciones" in lower
    assert "libro primario externo" in lower
    assert "nombres, ids y huellas" in lower
    assert "no se publica" in lower
    assert "licencia permanecen pendientes" in lower
    assert "no valores" in lower
    assert "calibrados contra el total publicado" in lower
    assert "q=\\frac{21.1}{32}=0.659375" in all_source
    assert "0.0682626981559366" in all_source
    assert "2014–2023" in all_source
    assert "2024–2025" in all_source
    assert "integrated_figure_1986_2030" in all_source
    assert "prospective_policy_2024_2030" in all_source
    assert "reported_periods_combined_excluding_2024_2025" in all_source
    assert "actualización anual eia: linaje separado" in lower
    assert "opcional y está desactivado por defecto" in lower
    assert "nunca se usan para rellenar" in lower
    assert "E5_original" in all_source
    assert "E10_misma_metodologia" in all_source
    assert "E10_penalizacion_lhv" in all_source
    assert "E15" not in all_source
    assert "E20" not in all_source
    assert "06_resultados/economia/" not in all_source


def test_notebook_omits_private_artifact_identifiers() -> None:
    all_source = "\n".join(_source(cell) for cell in _notebook()["cells"])
    assert "omitido en rama pública" in all_source
    assert "drive_file_id" not in all_source
    assert "original_sha256" not in all_source
    assert 'manuscrito["sha256"]' not in all_source


def test_four_article_figures_are_present_and_eia_is_opt_in() -> None:
    all_source = "\n".join(_source(cell) for cell in _notebook()["cells"])
    for constructor in (
        "crear_figura_emisiones_articulo_historica(",
        "crear_figura_consumo_articulo(",
        "crear_figura_emisiones_articulo_prospectiva(",
        "crear_figura_emisiones_articulo_integrada(",
    ):
        assert all_source.count(constructor) == 1
    assert "MOSTRAR_ACTUALIZACION_EIA = False" in all_source
    assert "if MOSTRAR_ACTUALIZACION_EIA:" in all_source


def test_original_fit_scale_and_integrated_gap_are_explicit() -> None:
    notebook = _notebook()
    by_id = {cell["id"]: _source(cell) for cell in notebook["cells"]}
    projection_math = by_id["mat-proyeccion-articulo"]
    assert "El código original ajusta **litros**" in projection_math
    assert "algebraicamente equivalente" in projection_math
    assert "\\ln(Litros_t)=\\beta_0+\\beta_1t" in projection_math

    integration_result = by_id["resultado-integracion-articulo"]
    for fragment in (
        "total_evitado_integrado",
        "total_evitado_union",
        "diferencia_2024_2025",
        "evitado_2024_2025",
        "assert abs(diferencia_2024_2025 - evitado_2024_2025) < 1e-6",
        "45\\ años",
        "43\\ años",
    ):
        assert fragment in integration_result


def test_lineage_and_controls_are_visible() -> None:
    notebook = _notebook()
    ids = {cell["id"] for cell in notebook["cells"]}
    assert {"linaje-explicacion", "mostrar-linaje"}.issubset(ids)
    assert {"controles-explicacion", "mostrar-controles"}.issubset(ids)
    controls_source = _source(
        next(cell for cell in notebook["cells"] if cell["id"] == "mostrar-controles")
    )
    assert "assert economia_ok.all()" in controls_source
    assert "assert emisiones_ok.all()" in controls_source

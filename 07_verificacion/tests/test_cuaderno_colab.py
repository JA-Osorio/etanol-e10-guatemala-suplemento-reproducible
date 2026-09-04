"""Pruebas estructurales del cuaderno científico para Colab."""

from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = (
    REPO_ROOT / "05_cuaderno_colab" / "reproducir_resultados_e10.ipynb"
)
README_PATH = REPO_ROOT / "README.md"

EXPECTED_IDS = [
    "portada",
    "preparar-entorno",
    "datos-parametros",
    "calcular-emisiones",
    "mat-emisiones",
    "resultado-historico",
    "mat-consumo",
    "resultado-consumo",
    "mat-proyeccion",
    "resultado-proyeccion",
    "mat-economia",
    "calcular-economia",
    "mat-cost-push",
    "resultado-cost-push",
    "mat-demand-pull",
    "resultado-demand-pull",
    "mat-integracion",
    "resultado-integracion",
    "alcance-y-archivos",
]

PLOT_CONSTRUCTORS = {
    "crear_figura_emisiones_articulo_historica(": "resultado-historico",
    "crear_figura_consumo_articulo(": "resultado-consumo",
    "crear_figura_emisiones_articulo_prospectiva(": "resultado-proyeccion",
    "crear_figura_cost_push(": "resultado-cost-push",
    "crear_figura_demand_pull(": "resultado-demand-pull",
    "crear_figura_emisiones_articulo_integrada(": "resultado-integracion",
}


def _notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _source(cell: dict) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else source


def _cells_by_id() -> dict[str, dict]:
    return {cell["id"]: cell for cell in _notebook()["cells"]}


def _all_source(*, cell_type: str | None = None) -> str:
    cells = _notebook()["cells"]
    if cell_type is not None:
        cells = [cell for cell in cells if cell["cell_type"] == cell_type]
    return "\n".join(_source(cell) for cell in cells)


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

    assert notebook["nbformat"] == 4
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
        first_line = _source(cell).splitlines()[0]
        assert first_line.startswith("#@title ")
        assert '{ display-mode: "form" }' in first_line
        assert cell["metadata"]["cellView"] == "form"
        assert cell["metadata"]["jupyter"]["source_hidden"] is True
        assert "hide-input" in cell["metadata"]["tags"]


def test_scientific_narrative_follows_the_article_order() -> None:
    cells = _notebook()["cells"]
    positions = {cell["id"]: index for index, cell in enumerate(cells)}

    assert cells[0]["id"] == "portada"
    assert cells[-1]["id"] == "alcance-y-archivos"
    assert cells[0]["cell_type"] == "markdown"
    assert cells[-1]["cell_type"] == "markdown"
    assert positions["datos-parametros"] < positions["mat-emisiones"]
    assert positions["resultado-historico"] < positions["mat-proyeccion"]
    assert positions["resultado-proyeccion"] < positions["mat-economia"]
    assert positions["mat-economia"] < positions["resultado-cost-push"]


def test_math_is_visible_before_each_result() -> None:
    cells = _notebook()["cells"]
    positions = {cell["id"]: index for index, cell in enumerate(cells)}
    pairs = (
        ("mat-emisiones", "resultado-historico"),
        ("mat-consumo", "resultado-consumo"),
        ("mat-proyeccion", "resultado-proyeccion"),
        ("mat-cost-push", "resultado-cost-push"),
        ("mat-demand-pull", "resultado-demand-pull"),
        ("mat-integracion", "resultado-integracion"),
    )

    for math_id, result_id in pairs:
        math_cell = cells[positions[math_id]]
        result_cell = cells[positions[result_id]]
        assert math_cell["cell_type"] == "markdown"
        assert result_cell["cell_type"] == "code"
        assert positions[math_id] < positions[result_id]
        assert "$$" in _source(math_cell) or "\\[" in _source(math_cell)


def test_key_equations_and_units_are_explained() -> None:
    by_id = {cell_id: _source(cell) for cell_id, cell in _cells_by_id().items()}
    required_fragments = {
        "mat-emisiones": (
            "E_t",
            "0.001055056",
            "C_{E0,t}",
            "69.3",
            "f_e",
            "C_{E10,t}",
        ),
        "mat-consumo": ("L_t", "G_t", "3.785411784"),
        "mat-proyeccion": (
            "\\ln",
            "\\beta_0",
            "\\beta_1",
            "2014–2023",
            "2026–2030",
        ),
        "mat-economia": (
            "A=Z\\operatorname{diag}(x)^{-1}",
            "L=(I-A)^{-1}",
        ),
        "mat-cost-push": ("P_s", "r_s", "d_j", "\\Delta p"),
        "mat-demand-pull": (
            "G_g",
            "\\Delta y",
            "\\Delta x=L\\Delta y",
            "m=",
        ),
    }
    for cell_id, fragments in required_fragments.items():
        for fragment in fragments:
            assert fragment in by_id[cell_id]


def test_period_union_is_labeled_as_two_disjoint_windows() -> None:
    integration = _source(_cells_by_id()["mat-integracion"])
    lower = integration.lower()

    assert "1986–2023" in integration
    assert "2026–2030" in integration
    assert "2024–2025" in integration
    assert "disjunt" in lower
    assert any(term in lower for term in ("no incluye", "excluye", "omite"))


def test_six_dynamic_plotly_figures_are_built_once() -> None:
    all_source = _all_source()
    cells = _cells_by_id()

    assert "visualizaciones_interactivas" in all_source
    for constructor, result_id in PLOT_CONSTRUCTORS.items():
        assert all_source.count(constructor) == 1
        assert constructor in _source(cells[result_id])

    lower = all_source.lower()
    assert ".png" not in lower
    assert "matplotlib" not in lower
    assert "write_image" not in lower
    assert "ipython.display import image" not in lower


def test_results_are_calculated_from_inputs_and_configuration() -> None:
    code_source = _all_source(cell_type="code")

    assert "load_recovered_article_history(" in code_source
    assert "build_recovered_article_counterfactual(" in code_source
    assert "ejecutar_economia_articulo(" in code_source
    assert re.search(
        r"ejecutar_economia_articulo\([\s\S]*?escribir_resultados\s*=\s*False",
        code_source,
    )
    assert "01_datos" in code_source
    assert "03_configuracion" in code_source
    assert "06_resultados" not in code_source
    assert "07_verificacion" not in code_source
    assert "pd.read_csv" not in code_source


def test_e5_and_corrected_e10_are_present_without_unrelated_sensitivities() -> None:
    all_source = _all_source()
    lower = all_source.lower()

    assert re.search(r"\bE5\b", all_source)
    assert re.search(r"\bE10\b", all_source)
    assert "E5_original" in all_source
    assert "E10_misma_metodologia" in all_source
    assert "E10_penalizacion_lhv" not in all_source
    assert "sensibilidad lhv" not in lower
    assert not re.search(r"\beia\b", lower)
    assert "pytest" not in lower
    assert "crear_figura_emisiones_eia(" not in all_source
    assert "crear_figura_emisiones_evitadas(" not in all_source


def test_visible_markdown_uses_only_scientific_language() -> None:
    markdown = _all_source(cell_type="markdown")
    prohibited = (
        r"\bauditor[ií]a\b",
        r"\bforense\b",
        r"\barmonizaci[oó]n\b",
        r"\brecuperad\w*\b",
        r"\bprivad\w*\b",
        r"\bhash(?:es)?\b",
        r"\bhuella(?:s)?\b",
        r"\bmanifiesto(?:s)?\b",
        r"\bcontrol(?:es)?\b",
        r"\bIA\b",
        r"\binteligencia artificial\b",
        r"\bTask\b",
        r"\bReasoning\b",
    )

    for pattern in prohibited:
        assert re.search(pattern, markdown, flags=re.IGNORECASE) is None


def test_notebook_does_not_end_with_a_validation_dashboard() -> None:
    notebook = _notebook()
    ids = {cell["id"] for cell in notebook["cells"]}
    final_source = _source(notebook["cells"][-1]).lower()

    assert "mostrar-controles" not in ids
    assert "controles-explicacion" not in ids
    assert "pass/fail" not in final_source
    assert "assert " not in final_source

"""Pruebas de alcance y sanitización de artefactos no licenciados."""

import csv
import json
from pathlib import Path

from e10_gt.verificacion import _segment_hash, verificar_alcance


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repositorio_cumple_alcance() -> None:
    result = verificar_alcance(REPO_ROOT)
    assert result["estado"] == "PASS"
    assert result["economia_historica"] == "E5_original"
    assert result["economia_corregida"] == "E10_misma_metodologia"
    assert result["escenarios_politica"][0] == "E10"
    assert all(result["controles"].values())


def test_segmentacion_evade_coincidencias_accidentales() -> None:
    needle = chr(101) + chr(53)
    value = "abc" + needle + "def" + needle
    segmented = _segment_hash(value)
    assert needle not in segmented
    assert segmented.replace("|", "") == value


def test_identificadores_privados_estan_omitidos_en_la_rama_publica() -> None:
    economy = json.loads(
        (REPO_ROOT / "03_configuracion/economia_articulo.json").read_text(
            encoding="utf-8"
        )
    )
    emissions = json.loads(
        (REPO_ROOT / "03_configuracion/emisiones_ttw.json").read_text(
            encoding="utf-8"
        )
    )
    marker = "omitido_en_rama_publica"

    manuscript = economy["fuente_manuscrito"]
    assert manuscript["archivo_origen"] == "identificador_omitido_en_rama_publica"
    assert manuscript["sha256"] == marker
    assert manuscript["publicacion_identificadores"] == "sanitizada"
    artifacts = economy["artefactos_historicos_no_redistribuidos"]
    assert artifacts == {
        "cantidad": 9,
        "identificadores": "omitidos_en_rama_publica",
        "publicacion_identificadores": "sanitizada",
    }

    lineage = emissions["article_recovered_lineage"]
    for notebook in (
        lineage["primary_notebook"],
        lineage["corroborating_notebook"],
    ):
        assert notebook["drive_file_id"] == marker
        assert notebook["original_sha256"] == marker
        assert notebook["publicacion_identificadores"] == "sanitizada"
        assert notebook["stored_in_repository"] is False
    workbook = lineage["expected_workbook"]
    assert workbook["identifier_status"] == "omitted_in_public_review_branch"
    assert "sha256" not in workbook
    assert "creator_metadata" not in workbook
    assert "last_modified_by_metadata" not in workbook

    with (
        REPO_ROOT
        / "00_fuentes_y_trazabilidad"
        / "manifiesto_insumos_externos.csv"
    ).open(encoding="utf-8", newline="") as handle:
        external = list(csv.DictReader(handle))
    private_rows = [
        row for row in external if row["sha256_origen_segmentado"] == marker
    ]
    assert private_rows
    assert all(row["redistribuido"] == "no" for row in private_rows)
    assert all(
        row["url_descarga"] == marker
        or (
            row["archivo_publicable_derivado"]
            and row["url_descarga"] == "archivo_derivado_en_repositorio"
        )
        for row in private_rows
    )
    assert all(
        row["nombre_archivo_origen"] != "" for row in private_rows
    )


def test_no_se_versionan_formatos_binarios_privados() -> None:
    excluded_parts = {".git", ".venv", ".pytest_cache", "__pycache__", "cache_mip"}
    binary_private_extensions = {".docx", ".xls", ".xlsx", ".zip"}
    versioned = [
        path.relative_to(REPO_ROOT).as_posix()
        for path in REPO_ROOT.rglob("*")
        if path.is_file()
        and path.suffix.casefold() in binary_private_extensions
        and not any(part in excluded_parts for part in path.parts)
    ]
    assert versioned == []

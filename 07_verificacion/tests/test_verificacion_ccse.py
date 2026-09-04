"""Pruebas del verificador opcional del libro CCSE no redistribuido."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from e10_gt.verificacion_ccse import (
    CcseRecord,
    EXPECTED_WORKBOOK_SHA256,
    compare_ccse_records,
    load_recovered_controls,
    read_ccse_workbook,
    validate_ccse_records,
    verify_ccse_workbook,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _records_from_public_control() -> list[CcseRecord]:
    config = json.loads(
        (REPO_ROOT / "03_configuracion" / "emisiones_ttw.json").read_text(
            encoding="utf-8"
        )
    )
    recovered = load_recovered_controls(
        REPO_ROOT / config["article_recovered_lineage"]["source_csv"]
    )
    return [
        CcseRecord(sequence=index, year=row.year, btu=row.btu)
        for index, row in enumerate(recovered, start=1)
    ]


def _write_minimal_xlsx(
    path: Path,
    records: list[CcseRecord],
    *,
    headers: tuple[str, str, str] = ("No", "año", "BTU"),
) -> None:
    header_cells = "".join(
        f'<c r="{column}1" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
        for column, value in zip(("A", "B", "C"), headers)
    )
    data_rows = []
    for excel_row, record in enumerate(records, start=2):
        data_rows.append(
            f'<row r="{excel_row}">'
            f'<c r="A{excel_row}"><v>{record.sequence}</v></c>'
            f'<c r="B{excel_row}"><v>{record.year}</v></c>'
            f'<c r="C{excel_row}"><v>{record.btu!r}</v></c>'
            "</row>"
        )
    worksheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData><row r="1">{header_cells}</row>{"".join(data_rows)}</sheetData>'
        "</worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="1.CONSUMO FINAL" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.'
        'openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.'
        'spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
        'relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", worksheet)


def test_expected_private_copy_identifier_is_omitted() -> None:
    config = json.loads(
        (REPO_ROOT / "03_configuracion" / "emisiones_ttw.json").read_text(
            encoding="utf-8"
        )
    )
    workbook = config["article_recovered_lineage"]["expected_workbook"]
    assert EXPECTED_WORKBOOK_SHA256 is None
    assert "sha256" not in workbook
    assert workbook["identifier_status"] == "omitted_in_public_review_branch"
    assert workbook["recovery_status"] == "recovered_external_copy_verified"
    assert workbook["stored_in_repository"] is False
    assert workbook["redistribution_allowed"] is False


def test_record_validation_rejects_sequence_year_and_btu_errors() -> None:
    records = _records_from_public_control()
    validate_ccse_records(records)

    bad_sequence = [*records]
    bad_sequence[0] = CcseRecord(2, bad_sequence[0].year, bad_sequence[0].btu)
    with pytest.raises(ValueError, match="columna No"):
        validate_ccse_records(bad_sequence)

    bad_year = [*records]
    bad_year[-1] = CcseRecord(38, 2022, bad_year[-1].btu)
    with pytest.raises(ValueError, match="años"):
        validate_ccse_records(bad_year)

    bad_btu = [*records]
    bad_btu[-1] = CcseRecord(38, 2023, 0.0)
    with pytest.raises(ValueError, match="BTU"):
        validate_ccse_records(bad_btu)


def test_pure_comparison_reproduces_fit_conversions_and_totals() -> None:
    config = json.loads(
        (REPO_ROOT / "03_configuracion" / "emisiones_ttw.json").read_text(
            encoding="utf-8"
        )
    )
    recovered = load_recovered_controls(
        REPO_ROOT / config["article_recovered_lineage"]["source_csv"]
    )
    result = compare_ccse_records(
        _records_from_public_control(), recovered, config
    )

    assert {row["status"] for row in result["checks"]} == {"PASS"}
    assert result["fit_literal_np_polyfit"]["fit_start_year"] == 2014
    assert result["fit_literal_np_polyfit"]["fit_end_year"] == 2023
    assert result["fit_literal_np_polyfit"]["n_observations"] == 10
    assert (
        round(result["totals"]["historical_1986_2023"]["avoided_co2_tonnes"])
        == 7_121_034
    )
    assert (
        round(result["totals"]["prospective_2026_2030"]["avoided_co2_tonnes"])
        == 2_848_499
    )


def test_minimal_xlsx_reader_and_full_verifier(tmp_path: Path) -> None:
    workbook = tmp_path / "libro_primario.xlsx"
    _write_minimal_xlsx(workbook, _records_from_public_control())
    digest = hashlib.sha256(workbook.read_bytes()).hexdigest()

    records = read_ccse_workbook(workbook)
    assert len(records) == 38
    assert (records[0].sequence, records[0].year) == (1, 1986)
    assert (records[-1].sequence, records[-1].year) == (38, 2023)

    report = verify_ccse_workbook(
        workbook,
        repo_root=REPO_ROOT,
        expected_sha256=digest,
    )
    assert report["status"] == "PASS"
    assert report["workbook"]["redistributed_by_verifier"] is False
    assert report["workbook"]["stored_in_repository"] is False
    assert all(row["status"] == "PASS" for row in report["checks"])

    sanitized_report = verify_ccse_workbook(workbook, repo_root=REPO_ROOT)
    assert sanitized_report["status"] == "PASS"
    assert sanitized_report["workbook"]["sha256_publication"] == (
        "calculated_locally_not_published"
    )
    assert "sha256" not in sanitized_report["workbook"]
    assert "expected_sha256" not in sanitized_report["workbook"]
    by_id = {row["check_id"]: row for row in sanitized_report["checks"]}
    assert by_id["ccse_workbook_identifier_sanitized"]["status"] == "PASS"


def test_hash_mismatch_is_reported_as_failure(tmp_path: Path) -> None:
    workbook = tmp_path / "libro_primario.xlsx"
    _write_minimal_xlsx(workbook, _records_from_public_control())

    report = verify_ccse_workbook(
        workbook,
        repo_root=REPO_ROOT,
        expected_sha256="0" * 64,
    )
    assert report["status"] == "FAIL"
    by_id = {row["check_id"]: row for row in report["checks"]}
    assert by_id["ccse_workbook_sha256"]["status"] == "FAIL"
    assert by_id["ccse_conversion_matches_embedded_co2"]["status"] == "PASS"


def test_wrong_headers_are_rejected(tmp_path: Path) -> None:
    workbook = tmp_path / "libro_primario.xlsx"
    _write_minimal_xlsx(
        workbook,
        _records_from_public_control(),
        headers=("No", "year", "BTU"),
    )
    with pytest.raises(ValueError, match="Columnas inesperadas"):
        read_ccse_workbook(workbook)

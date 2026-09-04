import csv
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from e10_gt.recuperacion_cuaderno import (
    BTU_TO_MJ,
    CO2_FACTOR_TONNES_PER_TJ,
    CSV_FIELDS,
    E10_VOLUMETRIC_SHARE,
    ETHANOL_LHV_MJ_PER_LITER,
    GASOLINE_LHV_MJ_PER_LITER,
    GOLDEN_SEMANTIC_HASHES,
    LITER_TO_US_GALLON,
    NotebookRecoveryError,
    recover_counterfactual_from_notebook,
    write_recovered_csv,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI_PATH = REPO_ROOT / "04_reproduccion_python" / "extraer_contrafactual_cuaderno.py"


def _plot_html(traces: list[dict]) -> str:
    return (
        '<div><script>Plotly.newPlot("id-aleatorio",'
        + json.dumps(traces, ensure_ascii=False, separators=(",", ":"))
        + ',{"title":"fixture"},{"responsive":true});</script></div>'
    )


def _fixture_notebook(*, omit: str | None = None, inconsistent: str | None = None) -> dict:
    historical_years = list(range(1986, 2024))
    all_years = list(range(1986, 2031))
    blend_energy = (
        (1 - E10_VOLUMETRIC_SHARE) * GASOLINE_LHV_MJ_PER_LITER
        + E10_VOLUMETRIC_SHARE * ETHANOL_LHV_MJ_PER_LITER
    )
    reduction = E10_VOLUMETRIC_SHARE * ETHANOL_LHV_MJ_PER_LITER / blend_energy

    btu = {year: 1.0e12 * (1.015 ** (year - 1986)) for year in all_years}
    base_all = {
        year: (
            btu[year]
            * BTU_TO_MJ
            / 1_000_000
            * CO2_FACTOR_TONNES_PER_TJ
            / 1_000
        )
        for year in all_years
    }
    base = {year: base_all[year] for year in historical_years}
    e10 = {year: base[year] * (1 - reduction) for year in historical_years}
    prospective_e10 = {
        year: base_all[year] * (1 if year in (2024, 2025) else 1 - reduction)
        for year in range(2024, 2031)
    }
    integrated_e10 = {year: base_all[year] * (1 - reduction) for year in all_years}
    volume = {
        year: (
            btu[year]
            * BTU_TO_MJ
            / GASOLINE_LHV_MJ_PER_LITER
            * LITER_TO_US_GALLON
            / 1_000_000
        )
        for year in all_years
    }
    if inconsistent == "e10":
        e10[2000] *= 0.9
    if inconsistent == "volume":
        volume[2000] *= 1.1
    if inconsistent == "prospective":
        prospective_e10[2026] *= 0.9
    if inconsistent == "integrated":
        integrated_e10[2027] *= 0.9

    base_trace = {
        "name": "Base (E0)",
        "x": historical_years,
        "y": [base[year] for year in historical_years],
    }
    e10_trace = {
        "name": "Con E10 (contrafactual)",
        "x": historical_years,
        "y": [e10[year] for year in historical_years],
    }
    volume_trace = {
        "name": "Consumo final (mill. gal/año)",
        "x": all_years,
        "y": [volume[year] for year in all_years],
    }
    prospective_trace = {
        "name": "Con E10 (escenario)",
        "x": list(range(2024, 2031)),
        "y": [prospective_e10[year] for year in range(2024, 2031)],
    }
    prospective_base_trace = {
        "name": "Base (E0)",
        "x": list(range(2024, 2031)),
        "y": [base_all[year] for year in range(2024, 2031)],
    }
    integrated_trace = {
        "name": "Con E10 (contrafactual + escenario)",
        "x": all_years,
        "y": [integrated_e10[year] for year in all_years],
    }
    integrated_base_trace = {
        "name": "Base (E0)",
        "x": all_years,
        "y": [base_all[year] for year in all_years],
    }
    named = {"base": base_trace, "e10": e10_trace, "volume": volume_trace}
    selected = {key: value for key, value in named.items() if key != omit}

    # El orden, la celda y la salida no coinciden con los del cuaderno real.
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "cells": [
            {"cell_type": "markdown", "source": ["# Fixture"]},
            {
                "cell_type": "code",
                "source": ["# volumen"],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "text/html": [_plot_html([selected["volume"]])]
                            if "volume" in selected
                            else ["<p>sin gráfica</p>"]
                        },
                    }
                ],
            },
            {
                "cell_type": "code",
                "source": ["# contrafactual"],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "text/html": _plot_html(
                                [
                                    selected[key]
                                    for key in ("e10", "base")
                                    if key in selected
                                ]
                            )
                        },
                    }
                ],
            },
            {
                "cell_type": "code",
                "source": ["# integrada"],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "text/html": _plot_html(
                                [integrated_trace, integrated_base_trace]
                            )
                        },
                    }
                ],
            },
            {
                "cell_type": "code",
                "source": ["# prospectiva"],
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {
                            "text/html": _plot_html(
                                [prospective_trace, prospective_base_trace]
                            )
                        },
                    }
                ],
            },
        ],
    }


class NotebookRecoveryTests(unittest.TestCase):
    def _write_fixture(self, root: Path, **kwargs) -> Path:
        path = root / "fixture.ipynb"
        path.write_text(
            json.dumps(_fixture_notebook(**kwargs), ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_extracts_by_trace_name_and_validates_identities(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-notebook-") as temp_dir:
            path = self._write_fixture(Path(temp_dir))
            result = recover_counterfactual_from_notebook(path)

        self.assertEqual(len(result.rows), 38)
        self.assertEqual([result.rows[0]["year"], result.rows[-1]["year"]], [1986, 2023])
        self.assertEqual(list(result.rows[0]), list(CSV_FIELDS))
        self.assertEqual(len(result.volume_million_us_gallons), 45)
        self.assertEqual(len(result.prospective_base_ktonnes), 7)
        self.assertEqual(len(result.integrated_base_ktonnes), 45)
        self.assertEqual(
            set(result.semantic_hashes),
            {
                "retrospective_1986_2023",
                "prospective_2024_2030",
                "volume_1986_2030",
                "integrated_1986_2030",
            },
        )
        self.assertTrue(
            all(len(digest) == 64 for digest in result.semantic_hashes.values())
        )
        first = result.rows[0]
        self.assertTrue(math.isclose(first["btu_recovered"], 1.0e12, rel_tol=2e-14))
        self.assertEqual(
            first["value_status"],
            "recovered_from_embedded_notebook_plotly_output",
        )

    def test_hash_is_strict_and_single_final_lf_exception_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-notebook-hash-") as temp_dir:
            path = self._write_fixture(Path(temp_dir))
            original = path.read_bytes()
            expected = hashlib.sha256(original).hexdigest()
            path.write_bytes(original + b"\n")

            with self.assertRaisesRegex(NotebookRecoveryError, "SHA-256 inesperado"):
                recover_counterfactual_from_notebook(path, expected_sha256=expected)
            result = recover_counterfactual_from_notebook(
                path,
                expected_sha256=expected,
                allow_single_added_final_newline=True,
            )

        self.assertNotEqual(result.raw_sha256, expected)
        self.assertEqual(result.verified_sha256, expected)
        self.assertTrue(result.accepted_single_added_final_newline)

    def test_missing_named_trace_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-notebook-missing-") as temp_dir:
            path = self._write_fixture(Path(temp_dir), omit="volume")
            with self.assertRaisesRegex(
                NotebookRecoveryError, "No se pudo localizar la gráfica de volumen"
            ):
                recover_counterfactual_from_notebook(path)

    def test_missing_arrays_fails_clearly(self) -> None:
        notebook = _fixture_notebook()
        html = notebook["cells"][2]["outputs"][0]["data"]["text/html"]
        notebook["cells"][2]["outputs"][0]["data"]["text/html"] = html.replace(
            '"name":"Base (E0)","x"',
            '"name":"Base (E0)","x_missing"',
        )
        with tempfile.TemporaryDirectory(prefix="e10-notebook-arrays-") as temp_dir:
            path = Path(temp_dir) / "fixture.ipynb"
            path.write_text(json.dumps(notebook, ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(NotebookRecoveryError, "arreglos x/y"):
                recover_counterfactual_from_notebook(path)

    def test_inconsistent_e10_or_volume_is_rejected(self) -> None:
        for variable, message in (("e10", "Base/E10"), ("volume", "Base/volumen")):
            with self.subTest(variable=variable), tempfile.TemporaryDirectory(
                prefix="e10-notebook-inconsistent-"
            ) as temp_dir:
                path = self._write_fixture(Path(temp_dir), inconsistent=variable)
                with self.assertRaisesRegex(NotebookRecoveryError, message):
                    recover_counterfactual_from_notebook(path)

    def test_prospective_and_integrated_rules_are_enforced(self) -> None:
        for variable, message in (
            ("prospective", "Regla prospectiva E0/E10"),
            ("integrated", "Regla E10 integrada"),
        ):
            with self.subTest(variable=variable), tempfile.TemporaryDirectory(
                prefix="e10-notebook-context-"
            ) as temp_dir:
                path = self._write_fixture(Path(temp_dir), inconsistent=variable)
                with self.assertRaisesRegex(NotebookRecoveryError, message):
                    recover_counterfactual_from_notebook(path)

    def test_semantic_hashes_do_not_depend_on_cell_positions(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-notebook-semantic-") as temp_dir:
            root = Path(temp_dir)
            first_path = self._write_fixture(root)
            first = recover_counterfactual_from_notebook(first_path)
            notebook = _fixture_notebook()
            notebook["cells"] = list(reversed(notebook["cells"]))
            second_path = root / "reordered.ipynb"
            second_path.write_text(json.dumps(notebook, ensure_ascii=False), encoding="utf-8")
            second = recover_counterfactual_from_notebook(second_path)

        self.assertEqual(first.semantic_hashes, second.semantic_hashes)

    def test_semantic_golden_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-notebook-semantic-bad-") as temp_dir:
            path = self._write_fixture(Path(temp_dir))
            wrong = {key: "0" * 64 for key in GOLDEN_SEMANTIC_HASHES}
            with self.assertRaisesRegex(
                NotebookRecoveryError, "Hashes semánticos Plotly inesperados"
            ):
                recover_counterfactual_from_notebook(
                    path, expected_semantic_hashes=wrong
                )

    def test_writer_and_cli_create_the_public_schema(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-notebook-cli-") as temp_dir:
            root = Path(temp_dir)
            notebook = self._write_fixture(root)
            expected_hash = hashlib.sha256(notebook.read_bytes()).hexdigest()
            direct_output = root / "direct.csv"
            cli_output = root / "cli.csv"
            result = recover_counterfactual_from_notebook(notebook)
            write_recovered_csv(result.rows, direct_output)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(CLI_PATH),
                    "--cuaderno",
                    str(notebook),
                    "--salida",
                    str(cli_output),
                    "--expected-sha256",
                    expected_hash,
                    "--skip-golden-semantics",
                ],
                cwd=REPO_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(direct_output.read_bytes(), cli_output.read_bytes())
            self.assertIn("SHA-256 semántico", completed.stdout)
            self.assertIn("sin control golden para esta copia", completed.stdout)
            with cli_output.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(tuple(reader.fieldnames or ()), CSV_FIELDS)
            self.assertEqual(len(rows), 38)


if __name__ == "__main__":
    unittest.main()

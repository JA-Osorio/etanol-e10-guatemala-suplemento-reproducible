import csv
import json
import math
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from e10_gt.emisiones_ttw import (
    blend_metrics,
    load_config,
    load_eia_observations,
    round_half_up_integer,
    run_emissions_pipeline,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


class EmissionsTtwTests(unittest.TestCase):
    def test_e10_physical_identities(self) -> None:
        share = 0.10
        rho = 0.659375
        metrics = blend_metrics(share, rho)
        expected_r = (1.0 - share) + share * rho
        expected_f = (1.0 - share) / expected_r

        self.assertTrue(
            math.isclose(
                metrics["relative_blend_energy"],
                expected_r,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        )
        self.assertTrue(
            math.isclose(
                metrics["fossil_emissions_factor"],
                expected_f,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        )
        self.assertTrue(
            math.isclose(
                metrics["ttw_reduction_fraction"],
                0.0682626981559366,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        )

    def test_configuration_discloses_scope_and_notebook_rho(self) -> None:
        config = load_config(REPO_ROOT)
        lineage = config["published_aggregate_lineage"]
        rho = config["rho_parameter_provenance"]

        self.assertEqual(
            lineage["calculation_scope"],
            "aggregate_arithmetic_reconciliation_only",
        )
        self.assertEqual(lineage["excluded_gap_years"], [2024, 2025])
        self.assertFalse(lineage["original_annual_file_in_repository"])
        self.assertTrue(lineage["annual_recovered_input_in_repository"])
        self.assertEqual(
            lineage["annual_reproduction_status"],
            "primary_workbook_copy_recovered_and_computationally_verified",
        )
        self.assertEqual(rho["status"], "explicit_notebook_parameter_ratio")
        self.assertFalse(rho["independent_empirical_input"])
        self.assertEqual(rho["value"], config["ethanol_to_gasoline_lhv_ratio"])
        self.assertEqual(
            rho["value"],
            rho["ethanol_lhv_mj_per_liter"]
            / rho["gasoline_lhv_mj_per_liter"],
        )

    def test_rounding_contract_is_half_up(self) -> None:
        self.assertEqual(round_half_up_integer(Decimal("1.5")), 2)
        self.assertEqual(round_half_up_integer(Decimal("2.5")), 3)
        self.assertEqual(round_half_up_integer(Decimal("2.49")), 2)

    def test_eia_source_hash_and_metadata_are_fixed(self) -> None:
        config = load_config(REPO_ROOT)
        observations, metadata = load_eia_observations(REPO_ROOT, config)

        self.assertEqual(metadata["source_sha256"], config["source_sha256"])
        self.assertEqual(metadata["series_id"], config["eia_series_id"])
        self.assertEqual(metadata["units"], config["source_metadata_expected"]["units"])
        self.assertEqual(metadata["row_count"], 39)
        self.assertEqual(
            [observations[0]["year"], observations[-1]["year"]], [1986, 2024]
        )
        self.assertEqual(
            {row["source_lineage"] for row in observations},
            {"EIA_open_data_observed"},
        )

    def test_wrong_source_hash_is_rejected(self) -> None:
        config = load_config(REPO_ROOT)
        with tempfile.TemporaryDirectory(prefix="e10-ttw-hash-") as temp_dir:
            root = Path(temp_dir)
            source = root / config["source_csv"]
            source.parent.mkdir(parents=True)
            shutil.copy2(REPO_ROOT / config["source_csv"], source)
            config["source_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "SHA-256 inesperado"):
                load_eia_observations(root, config)

    def test_pipeline_checks_traceability_and_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-ttw-test-") as temp_dir:
            result = run_emissions_pipeline(REPO_ROOT, output_root=Path(temp_dir))

            self.assertGreaterEqual(len(result["checks"]), 50)
            self.assertEqual({row["status"] for row in result["checks"]}, {"PASS"})
            check_ids = {row["check_id"] for row in result["checks"]}
            required = {
                "eia_source_sha256",
                "rho_notebook_parameter_ratio",
                "rho_not_independent_empirical_input",
                "identity_r_E10",
                "identity_F_E10",
                "identity_d_E10",
                "annual_identity_C0",
                "annual_identity_Cs",
                "annual_identity_A",
                "annual_balance_C0_Cs_A",
                "unique_year_scenario_rows",
                "open_summary_sums",
                "published_periods_disjoint",
                "published_period_gap_2024_2025",
                "aggregate_round_half_up",
                "golden_forecast_energy_tj",
                "lineages_remain_separate",
                "article_recovered_source_sha256",
                "article_private_notebook_identifiers_sanitized",
                "article_primary_workbook_copy_recovered",
                "article_primary_workbook_identifier_sanitized",
                "article_primary_workbook_cross_validation_complete",
                "article_primary_workbook_not_redistributed_without_license",
                "article_roundtrip_BTU_to_C0",
                "article_roundtrip_BTU_to_million_us_gallons",
                "article_golden_projection_C0",
                "article_golden_projection_policy_scenario",
                "article_context_year_coverage_unique",
                "article_2024_2025_context_difference_explicit",
                "article_summary_gap_2024_2025",
                "article_golden_integrated_figure_avoided_co2_tonnes",
                "article_integrated_minus_reported_disjoint_avoided",
            }
            self.assertTrue(required.issubset(check_ids), required - check_ids)

            for path in result["output_paths"].values():
                self.assertTrue(path.is_file(), path)

            checks_path = result["output_paths"]["checks"]
            with checks_path.open(encoding="utf-8", newline="") as handle:
                written_checks = list(csv.DictReader(handle))
            self.assertEqual(len(written_checks), len(result["checks"]))
            self.assertTrue(
                {"scope", "evidence", "tolerance"}.issubset(written_checks[0])
            )

    def test_recovered_article_outputs_have_three_explicit_contexts(self) -> None:
        result = run_emissions_pipeline(REPO_ROOT, write_outputs=False)

        self.assertEqual(len(result["article_series"]), 45)
        self.assertEqual(len(result["article_counterfactual"]), 90)
        by_context: dict[str, list[dict[str, object]]] = {}
        for row in result["article_counterfactual"]:
            by_context.setdefault(str(row["scenario_context"]), []).append(row)
        self.assertEqual(
            {key: len(value) for key, value in by_context.items()},
            {
                "historical_counterfactual_1986_2023": 38,
                "prospective_policy_2024_2030": 7,
                "integrated_figure_1986_2030": 45,
            },
        )

        policy_gap = [
            row
            for row in by_context["prospective_policy_2024_2030"]
            if int(row["year"]) in (2024, 2025)
        ]
        integrated_gap = [
            row
            for row in by_context["integrated_figure_1986_2030"]
            if int(row["year"]) in (2024, 2025)
        ]
        self.assertEqual({row["scenario_id"] for row in policy_gap}, {"E0"})
        self.assertEqual({row["blend_share_applied"] for row in policy_gap}, {0.0})
        self.assertEqual({row["scenario_id"] for row in integrated_gap}, {"E10"})
        self.assertEqual(
            {row["blend_share_applied"] for row in integrated_gap}, {0.1}
        )

    def test_annual_reconstruction_matches_published_rounded_rows(self) -> None:
        result = run_emissions_pipeline(REPO_ROOT, write_outputs=False)
        summary = {row["period_id"]: row for row in result["article_summary"]}

        historical = summary["historical_1986_2023"]
        self.assertEqual(historical["reference_co2_tonnes_rounded"], 104318087)
        self.assertEqual(historical["scenario_co2_tonnes_rounded"], 97197053)
        self.assertEqual(historical["avoided_co2_tonnes_rounded"], 7121034)

        prospective = summary["prospective_2026_2030"]
        self.assertEqual(prospective["reference_co2_tonnes_rounded"], 41728481)
        self.assertEqual(prospective["scenario_co2_tonnes_rounded"], 38879982)
        self.assertEqual(prospective["avoided_co2_tonnes_rounded"], 2848499)

        combined = summary["reported_periods_combined_excluding_2024_2025"]
        self.assertEqual(combined["year_coverage"], "1986-2023|2026-2030")
        self.assertEqual(combined["excluded_years"], "2024|2025")
        self.assertEqual(combined["n_years"], 43)

        integrated = [
            row
            for row in result["article_counterfactual"]
            if row["scenario_context"] == "integrated_figure_1986_2030"
        ]
        integrated_avoided = sum(row["avoided_co2_tonnes"] for row in integrated)
        self.assertTrue(
            math.isclose(
                integrated_avoided,
                10899357.621420981,
                rel_tol=0.0,
                abs_tol=1e-3,
            )
        )
        self.assertTrue(
            math.isclose(
                integrated_avoided - combined["avoided_co2_tonnes"],
                929824.8283222113,
                rel_tol=0.0,
                abs_tol=1e-3,
            )
        )

    def test_published_aggregate_values_are_golden_controls(self) -> None:
        result = run_emissions_pipeline(REPO_ROOT, write_outputs=False)
        rows = result["published_aggregate_reconciliation"]

        self.assertEqual({row["scenario_id"] for row in rows}, {"E10"})
        self.assertEqual(
            {row["calculation_scope"] for row in rows},
            {"aggregate_arithmetic_reconciliation_only"},
        )
        self.assertEqual(
            {row["annual_reproduction_status"] for row in rows},
            {"primary_workbook_copy_recovered_and_computationally_verified"},
        )
        self.assertEqual(
            {row["source_lineage"] for row in rows},
            {"manuscript_reported_aggregate_totals"},
        )
        checks = {row["check_id"] for row in result["checks"]}
        for period_id in ("historical_1986_2023", "prospective_2026_2030"):
            for metric_id in ("C0", "C10", "A"):
                self.assertIn(
                    f"published_aggregate_{period_id}_row_{metric_id}", checks
                )

        extensions = result["published_aggregate_extensions"]
        self.assertEqual(
            {row["scenario_id"] for row in extensions}, {"E15", "E20"}
        )
        self.assertEqual(
            {row["control_status"] for row in extensions},
            {"derived_not_published"},
        )

    def test_eia_annual_keys_lineages_balances_and_golden_projection(self) -> None:
        result = run_emissions_pipeline(REPO_ROOT, write_outputs=False)
        rows = result["open_annual"]
        keys = [(row["year"], row["scenario_id"]) for row in rows]

        self.assertEqual(len(rows), 45 * 3)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(
            {row["source_lineage"] for row in rows},
            {
                "EIA_open_data_observed",
                "EIA_open_data_log_linear_projection",
            },
        )
        for row in rows:
            self.assertTrue(
                math.isclose(
                    row["reference_co2_tonnes"],
                    row["scenario_co2_tonnes"] + row["avoided_co2_tonnes"],
                    rel_tol=0.0,
                    abs_tol=1e-8,
                )
            )

        projected = {
            str(row["year"]): row["energy_tj"]
            for row in result["annual_energy"]
            if row["data_status"] == "projected_log_linear"
        }
        self.assertEqual(projected, result["config"]["golden_forecast_energy_tj"])

    def test_diagnostics_preserve_separate_lineages(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-ttw-diagnostics-") as temp_dir:
            result = run_emissions_pipeline(REPO_ROOT, output_root=Path(temp_dir))
            path = result["output_paths"]["forecast_diagnostics"]
            with path.open(encoding="utf-8") as handle:
                diagnostics = json.load(handle)

            self.assertEqual(
                diagnostics["lineage"]["published_aggregates"]["calculation_scope"],
                "aggregate_arithmetic_reconciliation_only",
            )
            self.assertFalse(
                diagnostics["lineage"]["rho"]["independent_empirical_input"]
            )
            self.assertEqual(
                diagnostics["source_metadata"]["source_sha256"],
                load_config(REPO_ROOT)["source_sha256"],
            )

    def test_pipeline_outputs_are_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-ttw-determinism-") as temp_dir:
            root = Path(temp_dir)
            first = run_emissions_pipeline(REPO_ROOT, output_root=root / "first")
            second = run_emissions_pipeline(REPO_ROOT, output_root=root / "second")

            self.assertEqual(first["output_paths"].keys(), second["output_paths"].keys())
            for key in first["output_paths"]:
                self.assertEqual(
                    first["output_paths"][key].read_bytes(),
                    second["output_paths"][key].read_bytes(),
                    key,
                )


if __name__ == "__main__":
    unittest.main()

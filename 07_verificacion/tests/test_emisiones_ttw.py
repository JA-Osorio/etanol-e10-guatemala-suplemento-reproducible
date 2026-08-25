import math
import tempfile
import unittest
from pathlib import Path

from e10_gt.emisiones_ttw import blend_metrics, run_emissions_pipeline


REPO_ROOT = Path(__file__).resolve().parents[2]


class EmissionsTtwTests(unittest.TestCase):
    def test_e10_physical_identity(self) -> None:
        metrics = blend_metrics(0.10, 0.659375)
        self.assertTrue(
            math.isclose(
                metrics["ttw_reduction_fraction"],
                0.0682626981559366,
                rel_tol=0.0,
                abs_tol=1e-15,
            )
        )

    def test_pipeline_smoke(self) -> None:
        with tempfile.TemporaryDirectory(prefix="e10-ttw-test-") as temp_dir:
            result = run_emissions_pipeline(REPO_ROOT, output_root=Path(temp_dir))
            self.assertEqual(len(result["checks"]), 9)
            self.assertEqual(
                {row["status"] for row in result["checks"]}, {"PASS"}
            )
            self.assertEqual(
                {
                    row["scenario_id"]
                    for row in result["published_reproduction"]
                },
                {"E10"},
            )
            self.assertEqual(
                {
                    row["scenario_id"]
                    for row in result["published_aggregate_extensions"]
                },
                {"E15", "E20"},
            )
            for path in result["output_paths"].values():
                self.assertTrue(path.is_file())

    def test_repository_text_excludes_discarded_token(self) -> None:
        forbidden = chr(101) + chr(53)
        text_suffixes = {".csv", ".json", ".md", ".py", ".toml", ".txt"}
        for path in REPO_ROOT.rglob("*"):
            if path.is_file() and path.suffix.lower() in text_suffixes:
                self.assertNotIn(
                    forbidden, path.read_text(encoding="utf-8").lower()
                )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest
from pathlib import Path

from lift.data.load import load_csv
from lift.data.schema import infer_schema, prepare_rows, validate_rows
from lift.trust.diagnostics import diagnose


class FixtureTest(unittest.TestCase):
    def test_observational_fixture_warns(self) -> None:
        rows = load_csv(Path("fixtures") / "observational_coupon.csv")
        schema = infer_schema(rows)
        validation = validate_rows(rows, schema)
        self.assertTrue(validation["valid"], validation)
        trust = diagnose(prepare_rows(rows, schema), schema, validation)
        self.assertIn(trust["trust_level"], {"medium", "low"})
        self.assertTrue(trust["observational"])
        self.assertEqual(trust["overlap_status"], "ok")
        self.assertIn("p50", trust["propensity_percentiles"])
        self.assertTrue(any("hidden confounding" in warning for warning in trust["warnings"]))

    def test_leakage_fixture_excludes_columns(self) -> None:
        rows = load_csv(Path("fixtures") / "leakage_coupon.csv")
        schema = infer_schema(rows)
        self.assertIn("coupon_used", schema.excluded_feature_columns)
        self.assertIn("post_campaign_purchase_count", schema.excluded_feature_columns)
        self.assertIn("revenue_after_coupon", schema.excluded_feature_columns)
        validation = validate_rows(rows, schema)
        trust = diagnose(prepare_rows(rows, schema), schema, validation)
        self.assertEqual(trust["trust_level"], "medium")
        self.assertEqual(trust["leakage_action"], "excluded_from_features")
        self.assertTrue(any("Likely leakage columns" in warning for warning in trust["warnings"]))

    def test_low_overlap_fixture_is_low_trust(self) -> None:
        rows = load_csv(Path("fixtures") / "low_overlap_coupon.csv")
        schema = infer_schema(rows)
        validation = validate_rows(rows, schema)
        self.assertTrue(validation["valid"], validation)
        trust = diagnose(prepare_rows(rows, schema), schema, validation)
        self.assertEqual(trust["trust_level"], "low")
        self.assertEqual(trust["overlap_status"], "poor")
        self.assertEqual(trust["low_overlap_count"], 6)
        self.assertGreater(trust["low_overlap_rate"], 0.2)

    def test_explicit_feature_columns_and_exclusions(self) -> None:
        rows = load_csv(Path("fixtures") / "randomized_coupon.csv")
        schema = infer_schema(
            rows,
            feature_columns=["feature_1", "feature_2"],
            exclude_feature_columns=["feature_2"],
        )
        self.assertEqual(schema.feature_columns, ["feature_1"])
        self.assertIn("feature_2", schema.excluded_feature_columns)


if __name__ == "__main__":
    unittest.main()

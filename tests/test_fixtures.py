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
        self.assertTrue(any("hidden confounding" in warning for warning in trust["warnings"]))

    def test_leakage_fixture_excludes_columns(self) -> None:
        rows = load_csv(Path("fixtures") / "leakage_coupon.csv")
        schema = infer_schema(rows)
        self.assertIn("coupon_used", schema.excluded_feature_columns)
        self.assertIn("post_campaign_purchase_count", schema.excluded_feature_columns)
        self.assertIn("revenue_after_coupon", schema.excluded_feature_columns)


if __name__ == "__main__":
    unittest.main()

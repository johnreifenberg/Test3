import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from backend.models.stream import Distribution, DistributionType, Stream, StreamType
from backend.models.model import FinancialModel, ModelSettings
from backend.engine.breakeven import BreakevenAnalyzer


def make_breakeven_model():
    """Model with upfront cost and revenue — has a meaningful breakeven."""
    model = FinancialModel(
        "Breakeven Test",
        ModelSettings(
            forecast_months=60,
            discount_rate=Distribution(DistributionType.FIXED, {"value": 0.10}),
            terminal_growth_rate=0.02,
        ),
    )
    model.add_stream(Stream(
        id="cost",
        name="Investment",
        stream_type=StreamType.COST,
        start_month=0,
        end_month=0,
        amount=Distribution(DistributionType.FIXED, {"value": 100000}),
    ))
    model.add_stream(Stream(
        id="rev",
        name="Revenue",
        stream_type=StreamType.REVENUE,
        start_month=1,
        amount=Distribution(DistributionType.NORMAL, {"mean": 5000, "std": 500}),
    ))
    return model


class TestBreakevenParameters:
    def test_lists_parameters(self):
        model = make_breakeven_model()
        analyzer = BreakevenAnalyzer(model)
        params = analyzer.get_solvable_parameters()
        names = [p["parameter_name"] for p in params]
        assert "Revenue - Amount" in names
        assert "Discount Rate" in names
        assert "Investment - Amount" in names

    def test_no_duplicates(self):
        model = make_breakeven_model()
        analyzer = BreakevenAnalyzer(model)
        params = analyzer.get_solvable_parameters()
        keys = [(p["stream_id"], p["parameter_name"]) for p in params]
        assert len(keys) == len(set(keys))


class TestBreakevenSolve:
    def test_revenue_breakeven(self):
        """Find the revenue amount that makes NPV = 0."""
        model = make_breakeven_model()
        analyzer = BreakevenAnalyzer(model)
        result = analyzer.run_breakeven("rev", "Revenue - Amount", target_npv=0.0)
        assert result["found"] is True
        # Breakeven revenue should be less than 5000 (since 5000 gives positive NPV)
        # but more than 0
        assert 0 < result["breakeven_value"] < 5000

    def test_discount_rate_breakeven(self):
        """Find the discount rate that makes NPV = 0."""
        model = make_breakeven_model()
        analyzer = BreakevenAnalyzer(model)
        result = analyzer.run_breakeven("__settings__", "Discount Rate", target_npv=0.0)
        assert result["found"] is True
        assert result["breakeven_value"] > 0

    def test_breakeven_not_found(self):
        """When NPV can't cross zero, should report not found."""
        model = FinancialModel(
            "No Breakeven",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.10}),
                terminal_growth_rate=0.02,
            ),
        )
        model.add_stream(Stream(
            id="rev",
            name="Revenue",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 10000}),
        ))
        analyzer = BreakevenAnalyzer(model)
        # All-positive cashflows — NPV is always positive regardless of revenue amount (when >= 0)
        # But with target_npv very high, it won't be found
        result = analyzer.run_breakeven("rev", "Revenue - Amount", target_npv=999999999.0)
        assert result["found"] is False

    def test_invalid_parameter(self):
        model = make_breakeven_model()
        analyzer = BreakevenAnalyzer(model)
        result = analyzer.run_breakeven("nonexistent", "Fake Param")
        assert result["found"] is False
        assert "not found" in result["error"]

    def test_custom_target_npv(self):
        """Breakeven with non-zero target NPV."""
        model = make_breakeven_model()
        analyzer = BreakevenAnalyzer(model)
        result = analyzer.run_breakeven("rev", "Revenue - Amount", target_npv=50000.0)
        assert result["found"] is True
        assert result["target_npv"] == 50000.0
        # Higher target NPV → need higher revenue
        result_zero = analyzer.run_breakeven("rev", "Revenue - Amount", target_npv=0.0)
        assert result["breakeven_value"] > result_zero["breakeven_value"]

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest
from backend.models.stream import Distribution, DistributionType, Stream, StreamType
from backend.models.model import FinancialModel, ModelSettings
from backend.engine.calculator import DCFCalculator
from backend.engine.terminal_value import identify_perpetual_streams, calculate_terminal_value


def make_simple_model():
    model = FinancialModel(
        "Test Model",
        ModelSettings(
            forecast_months=12,
            discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
            terminal_growth_rate=0.025,
        ),
    )
    model.add_stream(Stream(
        id="rev",
        name="Revenue",
        stream_type=StreamType.REVENUE,
        start_month=0,
        amount=Distribution(DistributionType.FIXED, {"value": 10000}),
    ))
    return model


class TestDeterministic:
    def test_basic_npv(self):
        model = make_simple_model()
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        assert result["mode"] == "deterministic"
        assert result["npv"] > 0
        assert len(result["cashflows"]) == 12

    def test_constant_cashflows(self):
        model = make_simple_model()
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        for cf in result["cashflows"]:
            assert abs(cf - 10000) < 0.01

    def test_cost_stream_negative(self):
        model = make_simple_model()
        model.add_stream(Stream(
            id="cost",
            name="Cost",
            stream_type=StreamType.COST,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 3000}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        for cf in result["cashflows"]:
            assert abs(cf - 7000) < 0.01

    def test_single_month_stream(self):
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
            ),
        )
        model.add_stream(Stream(
            id="one_shot",
            name="One-Time Cost",
            stream_type=StreamType.COST,
            start_month=5,
            end_month=5,
            amount=Distribution(DistributionType.FIXED, {"value": 50000}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        cfs = result["stream_details"]["one_shot"]
        for m in range(12):
            if m == 5:
                assert abs(cfs[m] - (-50000)) < 0.01
            else:
                assert cfs[m] == 0.0

    def test_bounded_stream_end_inclusive(self):
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
            ),
        )
        model.add_stream(Stream(
            id="bounded",
            name="Bounded Revenue",
            stream_type=StreamType.REVENUE,
            start_month=2,
            end_month=4,
            amount=Distribution(DistributionType.FIXED, {"value": 1000}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        cfs = result["stream_details"]["bounded"]
        assert cfs[0] == 0.0
        assert cfs[1] == 0.0
        assert abs(cfs[2] - 1000) < 0.01
        assert abs(cfs[3] - 1000) < 0.01
        assert abs(cfs[4] - 1000) < 0.01
        assert cfs[5] == 0.0


class TestChildStreamRatio:
    """Test child streams in ratio mode (amount_is_ratio=True)."""

    def test_child_ratio_concurrent(self):
        """Child with no periodicity or delay takes fraction of parent each month."""
        model = make_simple_model()
        model.add_stream(Stream(
            id="commission",
            name="Sales Commission",
            stream_type=StreamType.COST,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0.10}),
            parent_stream_id="rev",
            conversion_rate=1.0,
            amount_is_ratio=True,
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        child_cfs = result["stream_details"]["commission"]
        # Each month: abs(10000) * 0.10 * 1.0 = 1000, negated for COST
        for m in range(12):
            assert abs(child_cfs[m] - (-1000)) < 0.01

    def test_child_ratio_with_conversion(self):
        """Conversion rate scales child value."""
        model = make_simple_model()
        model.add_stream(Stream(
            id="child",
            name="Child Revenue",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0.2}),
            parent_stream_id="rev",
            conversion_rate=0.5,
            amount_is_ratio=True,
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        child_cfs = result["stream_details"]["child"]
        # abs(10000) * 0.2 * 0.5 = 1000
        for m in range(12):
            assert abs(child_cfs[m] - 1000) < 0.01

    def test_child_ratio_with_delay(self):
        """Trigger delay shifts child events."""
        model = make_simple_model()
        model.add_stream(Stream(
            id="child",
            name="Delayed Child",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0.5}),
            parent_stream_id="rev",
            conversion_rate=1.0,
            trigger_delay_months=3,
            amount_is_ratio=True,
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        child_cfs = result["stream_details"]["child"]
        # Parent at month 0 → child at month 3, parent at month 1 → child at month 4, etc.
        assert child_cfs[0] == 0.0
        assert child_cfs[1] == 0.0
        assert child_cfs[2] == 0.0
        # Month 3: parent at month 0 triggers child: abs(10000) * 0.5 * 1.0 = 5000
        assert abs(child_cfs[3] - 5000) < 0.01

    def test_child_ratio_with_periodicity(self):
        """Child with periodicity repeats at interval, locked at original parent value."""
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=24,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
            ),
        )
        # Parent only has cashflow in month 2
        model.add_stream(Stream(
            id="parent",
            name="License Sale",
            stream_type=StreamType.REVENUE,
            start_month=2,
            end_month=2,
            amount=Distribution(DistributionType.FIXED, {"value": 100000}),
        ))
        # Child renews every 12 months
        model.add_stream(Stream(
            id="maintenance",
            name="Annual Maintenance",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0.20}),
            parent_stream_id="parent",
            conversion_rate=0.85,
            trigger_delay_months=0,
            periodicity_months=12,
            amount_is_ratio=True,
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        maint_cfs = result["stream_details"]["maintenance"]
        expected_val = 100000 * 0.20 * 0.85  # 17000
        assert abs(maint_cfs[2] - expected_val) < 0.01
        assert abs(maint_cfs[14] - expected_val) < 0.01
        assert maint_cfs[0] == 0.0
        assert maint_cfs[1] == 0.0
        assert maint_cfs[3] == 0.0
        assert maint_cfs[13] == 0.0

    def test_child_ratio_with_delay_and_periodicity(self):
        """Child with both delay and periodicity."""
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=36,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
            ),
        )
        model.add_stream(Stream(
            id="parent",
            name="License Sale",
            stream_type=StreamType.REVENUE,
            start_month=2,
            end_month=2,
            amount=Distribution(DistributionType.FIXED, {"value": 100000}),
        ))
        model.add_stream(Stream(
            id="maint",
            name="Maintenance",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0.20}),
            parent_stream_id="parent",
            conversion_rate=0.85,
            trigger_delay_months=12,
            periodicity_months=12,
            amount_is_ratio=True,
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        maint_cfs = result["stream_details"]["maint"]
        expected_val = 100000 * 0.20 * 0.85  # 17000
        # Parent at month 2, delay 12 → first at month 14, then 26
        assert maint_cfs[2] == 0.0
        assert abs(maint_cfs[14] - expected_val) < 0.01
        assert abs(maint_cfs[26] - expected_val) < 0.01
        assert maint_cfs[13] == 0.0
        assert maint_cfs[15] == 0.0


class TestChildStreamAbsolute:
    """Test child streams in absolute mode (amount_is_ratio=False)."""

    def test_child_absolute_concurrent(self):
        model = make_simple_model()
        model.add_stream(Stream(
            id="child",
            name="Fixed Fee",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 500}),
            parent_stream_id="rev",
            conversion_rate=1.0,
            amount_is_ratio=False,
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        child_cfs = result["stream_details"]["child"]
        # Absolute: 500 * 1.0 = 500 per event
        for m in range(12):
            assert abs(child_cfs[m] - 500) < 0.01

    def test_child_absolute_with_conversion(self):
        model = make_simple_model()
        model.add_stream(Stream(
            id="child",
            name="Service Fee",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 1000}),
            parent_stream_id="rev",
            conversion_rate=0.5,
            amount_is_ratio=False,
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        child_cfs = result["stream_details"]["child"]
        # Absolute: 1000 * 0.5 = 500
        for m in range(12):
            assert abs(child_cfs[m] - 500) < 0.01


class TestEscalationRate:
    def test_escalation_increases_cashflows(self):
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
                escalation_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
            ),
        )
        model.add_stream(Stream(
            id="rev",
            name="Revenue",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 10000}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        cfs = result["stream_details"]["rev"]
        assert abs(cfs[0] - 10000) < 0.01
        assert cfs[6] > cfs[0]
        assert cfs[11] > cfs[6]

    def test_no_escalation_flat(self):
        model = make_simple_model()
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        cfs = result["stream_details"]["rev"]
        for cf in cfs:
            assert abs(cf - 10000) < 0.01

    def test_escalation_applied_to_child(self):
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=24,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
                escalation_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
            ),
        )
        model.add_stream(Stream(
            id="parent",
            name="Revenue",
            stream_type=StreamType.REVENUE,
            start_month=2,
            end_month=2,
            amount=Distribution(DistributionType.FIXED, {"value": 100000}),
        ))
        model.add_stream(Stream(
            id="child",
            name="Maintenance",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0.20}),
            parent_stream_id="parent",
            conversion_rate=1.0,
            trigger_delay_months=0,
            periodicity_months=12,
            amount_is_ratio=True,
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        child_cfs = result["stream_details"]["child"]
        # At month 14 (12 months after month 2) escalation should increase value
        assert child_cfs[14] > child_cfs[2]


class TestLinearAdoption:
    def test_linear_adoption_constant_cashflow(self):
        """Stream with LINEAR adoption should have constant monthly cashflow."""
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=24,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
            ),
        )
        model.add_stream(Stream(
            id="rev",
            name="Revenue",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 100000}),
            adoption_curve=Distribution(DistributionType.LINEAR, {"rate": 0.05, "amplitude": 1.0}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        # Each month: 100000 * 0.05 = 5000
        for cf in result["cashflows"]:
            assert abs(cf - 5000) < 0.01


class TestUnitValueMarketUnits:
    def test_unit_value_product(self):
        """unit_value * market_units should be used instead of amount."""
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
            ),
        )
        model.add_stream(Stream(
            id="rev",
            name="Revenue",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 50}),
            market_units=Distribution(DistributionType.FIXED, {"value": 1000}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        # Each month: 50 * 1000 = 50000
        for cf in result["cashflows"]:
            assert abs(cf - 50000) < 0.01

    def test_fallback_to_amount(self):
        """When unit_value/market_units are None, amount is used."""
        model = make_simple_model()
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        for cf in result["cashflows"]:
            assert abs(cf - 10000) < 0.01

    def test_unit_value_serialization(self):
        """Stream with unit_value/market_units round-trips through to_dict/from_dict."""
        stream = Stream(
            id="rev",
            name="Revenue",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.NORMAL, {"mean": 50, "std": 5}),
            market_units=Distribution(DistributionType.UNIFORM, {"min": 800, "max": 1200}),
        )
        data = stream.to_dict()
        restored = Stream.from_dict(data)
        assert restored.unit_value.dist_type == DistributionType.NORMAL
        assert restored.unit_value.params["mean"] == 50
        assert restored.market_units.dist_type == DistributionType.UNIFORM
        assert restored.market_units.params["min"] == 800

    def test_unit_value_with_adoption(self):
        """unit_value * market_units should work with adoption curves."""
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=24,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
            ),
        )
        model.add_stream(Stream(
            id="rev",
            name="Revenue",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 100}),
            market_units=Distribution(DistributionType.FIXED, {"value": 1000}),
            adoption_curve=Distribution(DistributionType.LINEAR, {"rate": 0.05, "amplitude": 1.0}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        # Each month: 100 * 1000 * 0.05 = 5000
        for cf in result["cashflows"]:
            assert abs(cf - 5000) < 0.01


class TestMonteCarlo:
    def test_runs_without_error(self):
        model = make_simple_model()
        model.streams["rev"].amount = Distribution(DistributionType.NORMAL, {"mean": 10000, "std": 1000})
        calc = DCFCalculator(model)
        result = calc.run_monte_carlo(n_simulations=100)
        assert result["mode"] == "monte_carlo"
        assert result["n_simulations"] == 100
        assert len(result["npv_distribution"]) == 100

    def test_statistics_reasonable(self):
        model = make_simple_model()
        model.streams["rev"].amount = Distribution(DistributionType.NORMAL, {"mean": 10000, "std": 1000})
        calc = DCFCalculator(model)
        result = calc.run_monte_carlo(n_simulations=500)
        assert result["npv_p10"] < result["npv_median"] < result["npv_p90"]


class TestTerminalValue:
    def test_perpetual_stream_identified(self):
        model = make_simple_model()
        perp = identify_perpetual_streams(model)
        assert "rev" in perp

    def test_bounded_stream_not_perpetual(self):
        model = make_simple_model()
        model.streams["rev"].end_month = 6
        perp = identify_perpetual_streams(model)
        assert "rev" not in perp

    def test_terminal_value_positive(self):
        tv = calculate_terminal_value(10000, 0.025, 0.12, 60)
        assert tv > 0

    def test_terminal_value_zero_when_rate_invalid(self):
        tv = calculate_terminal_value(10000, 0.12, 0.10, 60)
        assert tv == 0.0


class TestNPVandIRR:
    def test_npv_calculation(self):
        calc = DCFCalculator(make_simple_model())
        cashflows = np.array([10000.0] * 12)
        npv = calc.calculate_npv(cashflows, 0.12)
        assert npv > 0
        assert npv < 120000

    def test_irr_with_investment(self):
        calc = DCFCalculator(make_simple_model())
        cashflows = np.array([-100000.0] + [12000.0] * 11)
        irr, error = calc.calculate_irr(cashflows)
        assert irr is not None
        assert error is None

    def test_irr_no_sign_change(self):
        """IRR should return error when all cashflows are positive."""
        calc = DCFCalculator(make_simple_model())
        cashflows = np.array([10000.0] * 12)
        irr, error = calc.calculate_irr(cashflows)
        assert irr is None
        assert "No sign change" in error


class TestIRRMode:
    def test_deterministic_irr_mode(self):
        """IRR mode returns IRR as primary result."""
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
                calculation_mode="IRR",
            ),
        )
        model.add_stream(Stream(
            id="cost",
            name="Initial Investment",
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
            amount=Distribution(DistributionType.FIXED, {"value": 15000}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        assert result["calculation_mode"] == "IRR"
        assert result["irr"] is not None
        assert result["irr"] > 0
        assert result["terminal_value"] is None
        assert result["discount_rate"] is None

    def test_deterministic_irr_no_sign_change(self):
        """IRR mode with no sign change returns error."""
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
                calculation_mode="IRR",
            ),
        )
        model.add_stream(Stream(
            id="rev",
            name="Revenue",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 10000}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        assert result["irr"] is None
        assert result["irr_error"] is not None

    def test_npv_mode_unchanged(self):
        """NPV mode continues to work as before."""
        model = make_simple_model()
        assert model.settings.calculation_mode == "NPV"
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        assert result["calculation_mode"] == "NPV"
        assert result["npv"] > 0
        assert result["terminal_value"] is not None

    def test_monte_carlo_irr_mode(self):
        """IRR Monte Carlo produces IRR distribution."""
        model = FinancialModel(
            "Test",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
                calculation_mode="IRR",
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
            amount=Distribution(DistributionType.NORMAL, {"mean": 15000, "std": 1000}),
        ))
        calc = DCFCalculator(model)
        result = calc.run_monte_carlo(n_simulations=50)
        assert result["calculation_mode"] == "IRR"
        assert result["irr_mean"] is not None
        assert len(result["irr_distribution"]) > 0

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from backend.models.stream import Distribution, DistributionType, Stream, StreamType
from backend.models.model import (
    FinancialModel, ModelSettings,
    ModelValidationError, CircularDependencyError,
)


def make_stream(sid, name="Test", stype=StreamType.REVENUE, parent_id=None, **kwargs):
    return Stream(
        id=sid, name=name, stream_type=stype, start_month=0,
        amount=Distribution(DistributionType.FIXED, {"value": 1000}),
        parent_stream_id=parent_id,
        **kwargs,
    )


class TestFinancialModel:
    def test_add_and_remove_stream(self):
        model = FinancialModel("Test")
        s = make_stream("s1")
        model.add_stream(s)
        assert "s1" in model.streams
        model.remove_stream("s1")
        assert "s1" not in model.streams

    def test_remove_nonexistent_raises(self):
        model = FinancialModel("Test")
        with pytest.raises(ModelValidationError):
            model.remove_stream("missing")

    def test_remove_parent_clears_child_ref(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("p"))
        model.add_stream(make_stream("c", parent_id="p"))
        model.remove_stream("p")
        assert model.streams["c"].parent_stream_id is None

    def test_get_children(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("p"))
        model.add_stream(make_stream("c1", parent_id="p"))
        model.add_stream(make_stream("c2", parent_id="p"))
        model.add_stream(make_stream("other"))
        children = model.get_children("p")
        assert len(children) == 2
        assert {c.id for c in children} == {"c1", "c2"}


class TestValidation:
    def test_missing_parent_raises(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("c", parent_id="missing"))
        with pytest.raises(ModelValidationError, match="non-existent parent"):
            model.validate()

    def test_invalid_conversion_rate_raises(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("p"))
        model.add_stream(make_stream("c", parent_id="p", conversion_rate=1.5))
        with pytest.raises(ModelValidationError, match="Conversion rate"):
            model.validate()

    def test_conversion_rate_zero_ok(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("p"))
        model.add_stream(make_stream("c", parent_id="p", conversion_rate=0.0))
        model.validate()  # Should not raise

    def test_circular_dependency_detected(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("a"))
        model.add_stream(make_stream("b", parent_id="a"))
        # Force circular reference
        model.streams["a"].parent_stream_id = "b"
        with pytest.raises(CircularDependencyError):
            model.validate()

    def test_valid_model_passes(self):
        model = FinancialModel(
            "Test",
            ModelSettings(
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.12}),
                terminal_growth_rate=0.025,
            ),
        )
        model.add_stream(make_stream("p"))
        model.add_stream(make_stream("c", parent_id="p", conversion_rate=0.5))
        model.validate()  # Should not raise


class TestTopologicalSort:
    def test_simple_order(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("a"))
        model.add_stream(make_stream("b", parent_id="a"))
        order = model.get_execution_order()
        assert order.index("a") < order.index("b")

    def test_multi_level_order(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("a"))
        model.add_stream(make_stream("b", parent_id="a"))
        model.add_stream(make_stream("c", parent_id="b"))
        order = model.get_execution_order()
        assert order.index("a") < order.index("b") < order.index("c")

    def test_no_deps_includes_all(self):
        model = FinancialModel("Test")
        model.add_stream(make_stream("x"))
        model.add_stream(make_stream("y"))
        order = model.get_execution_order()
        assert set(order) == {"x", "y"}


class TestEscalationRate:
    def test_settings_with_escalation(self):
        settings = ModelSettings(
            escalation_rate=Distribution(DistributionType.FIXED, {"value": 0.04}),
        )
        assert settings.escalation_rate is not None
        data = settings.to_dict()
        assert data["escalation_rate"]["type"] == "FIXED"
        restored = ModelSettings.from_dict(data)
        assert restored.escalation_rate.params["value"] == 0.04

    def test_settings_without_escalation(self):
        settings = ModelSettings()
        assert settings.escalation_rate is None
        data = settings.to_dict()
        assert data["escalation_rate"] is None
        restored = ModelSettings.from_dict(data)
        assert restored.escalation_rate is None


class TestSerialization:
    def test_round_trip(self):
        model = FinancialModel(
            "Round Trip",
            ModelSettings(
                forecast_months=36,
                discount_rate=Distribution(DistributionType.NORMAL, {"mean": 0.10, "std": 0.02}),
                terminal_growth_rate=0.03,
                escalation_rate=Distribution(DistributionType.FIXED, {"value": 0.03}),
            ),
        )
        model.add_stream(make_stream("s1", "Stream One"))
        model.add_stream(make_stream("c1", "Child One", parent_id="s1",
                                     conversion_rate=0.8, trigger_delay_months=3,
                                     periodicity_months=12, amount_is_ratio=True))

        data = model.to_dict()
        restored = FinancialModel.from_dict(data)
        assert restored.name == "Round Trip"
        assert restored.settings.forecast_months == 36
        assert restored.settings.escalation_rate is not None
        assert "s1" in restored.streams
        assert "c1" in restored.streams
        child = restored.streams["c1"]
        assert child.parent_stream_id == "s1"
        assert child.conversion_rate == 0.8
        assert child.trigger_delay_months == 3
        assert child.periodicity_months == 12
        assert child.amount_is_ratio is True

    def test_stream_round_trip_preserves_child_fields(self):
        stream = Stream(
            id="maint", name="Maintenance", stream_type=StreamType.REVENUE,
            start_month=0, end_month=48,
            amount=Distribution(DistributionType.NORMAL, {"mean": 0.2, "std": 0.03}),
            parent_stream_id="license",
            conversion_rate=0.85,
            trigger_delay_months=12,
            periodicity_months=12,
            amount_is_ratio=True,
        )
        data = stream.to_dict()
        restored = Stream.from_dict(data)
        assert restored.parent_stream_id == "license"
        assert restored.conversion_rate == 0.85
        assert restored.trigger_delay_months == 12
        assert restored.periodicity_months == 12
        assert restored.amount_is_ratio is True
        assert restored.end_month == 48


class TestCalculationMode:
    def test_default_is_npv(self):
        settings = ModelSettings()
        assert settings.calculation_mode == "NPV"

    def test_calculation_mode_serialization(self):
        settings = ModelSettings(calculation_mode="IRR")
        data = settings.to_dict()
        assert data["calculation_mode"] == "IRR"
        restored = ModelSettings.from_dict(data)
        assert restored.calculation_mode == "IRR"

    def test_missing_calculation_mode_defaults_to_npv(self):
        data = {
            "forecast_months": 60,
            "discount_rate": {"type": "FIXED", "params": {"value": 0.10}},
            "terminal_growth_rate": 0.025,
        }
        settings = ModelSettings.from_dict(data)
        assert settings.calculation_mode == "NPV"

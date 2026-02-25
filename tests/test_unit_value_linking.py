import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from backend.models.stream import Distribution, DistributionType, Stream, StreamType
from backend.models.model import FinancialModel, ModelSettings, ModelValidationError, CircularDependencyError
from backend.engine.calculator import DCFCalculator


def make_model_with_unit_prices():
    """Create a model with two streams using unit pricing."""
    model = FinancialModel(
        "Unit Price Test",
        ModelSettings(
            forecast_months=12,
            discount_rate=Distribution(DistributionType.FIXED, {"value": 0.10}),
            terminal_growth_rate=0.02,
        ),
    )
    # Source stream - Enterprise licenses
    model.add_stream(Stream(
        id="enterprise",
        name="Enterprise",
        stream_type=StreamType.REVENUE,
        start_month=0,
        amount=Distribution(DistributionType.FIXED, {"value": 0}),  # Dummy
        unit_value=Distribution(DistributionType.FIXED, {"value": 50000}),
        market_units=Distribution(DistributionType.FIXED, {"value": 10}),
    ))
    return model


class TestUnitValueLinkingValidation:
    def test_valid_link_to_source_stream(self):
        """Linking to a valid source stream should succeed."""
        model = make_model_with_unit_prices()
        # Add SMB stream that links to Enterprise unit price
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),  # Own value (will be overridden)
            market_units=Distribution(DistributionType.FIXED, {"value": 50}),
            unit_value_source_stream_id="enterprise",
        ))
        model.validate()  # Should not raise

    def test_link_to_nonexistent_stream_fails(self):
        """Linking to a non-existent stream should fail validation."""
        model = make_model_with_unit_prices()
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),
            market_units=Distribution(DistributionType.FIXED, {"value": 50}),
            unit_value_source_stream_id="nonexistent",
        ))
        with pytest.raises(ModelValidationError, match="non-existent unit value source"):
            model.validate()

    def test_link_to_child_stream_fails(self):
        """Linking to a child stream should fail validation."""
        model = make_model_with_unit_prices()
        # Add a child stream
        model.add_stream(Stream(
            id="support",
            name="Support",
            stream_type=StreamType.REVENUE,
            start_month=0,
            parent_stream_id="enterprise",
            amount=Distribution(DistributionType.FIXED, {"value": 0.2}),
        ))
        # Try to link to the child stream
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),
            market_units=Distribution(DistributionType.FIXED, {"value": 50}),
            unit_value_source_stream_id="support",
        ))
        with pytest.raises(ModelValidationError, match="cannot link to child stream"):
            model.validate()

    def test_link_to_stream_without_unit_value_fails(self):
        """Linking to a stream without unit_value should fail validation."""
        model = make_model_with_unit_prices()
        # Add a stream with no unit_value
        model.add_stream(Stream(
            id="consulting",
            name="Consulting",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 100000}),
        ))
        # Try to link to it
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),
            market_units=Distribution(DistributionType.FIXED, {"value": 50}),
            unit_value_source_stream_id="consulting",
        ))
        with pytest.raises(ModelValidationError, match="has no unit_value"):
            model.validate()

    def test_circular_reference_detected(self):
        """Circular unit value references should be detected."""
        model = make_model_with_unit_prices()
        # Stream B links to A
        model.add_stream(Stream(
            id="stream_b",
            name="B",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),
            market_units=Distribution(DistributionType.FIXED, {"value": 50}),
            unit_value_source_stream_id="enterprise",
        ))
        # Manually create circular reference by modifying enterprise
        model.streams["enterprise"].unit_value_source_stream_id = "stream_b"
        with pytest.raises(CircularDependencyError, match="Circular unit value reference"):
            model.validate()

    def test_remove_source_clears_references(self):
        """Removing a source stream should clear references to it."""
        model = make_model_with_unit_prices()
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),
            market_units=Distribution(DistributionType.FIXED, {"value": 50}),
            unit_value_source_stream_id="enterprise",
        ))
        model.remove_stream("enterprise")
        # Reference should be cleared
        assert model.streams["smb"].unit_value_source_stream_id is None


class TestUnitValueLinkingCalculation:
    def test_linked_unit_value_used_in_calculation(self):
        """Calculator should use source unit value when linked."""
        model = make_model_with_unit_prices()
        # SMB stream links to Enterprise unit price ($50k)
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),  # Own value (ignored)
            market_units=Distribution(DistributionType.FIXED, {"value": 20}),  # 20 units
            unit_value_source_stream_id="enterprise",  # Use $50k from enterprise
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        # Enterprise: $50k × 10 = $500k/month
        # SMB: $50k × 20 = $1M/month (uses enterprise price, not its own $10k)
        # Total monthly = $1.5M
        expected_monthly = 50000 * 10 + 50000 * 20
        assert abs(result["cashflows"][0] - expected_monthly) < 1

    def test_independent_unit_value_when_not_linked(self):
        """Without linking, stream should use its own unit value."""
        model = make_model_with_unit_prices()
        # SMB stream without linking
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),  # Own $10k price
            market_units=Distribution(DistributionType.FIXED, {"value": 20}),
            # No unit_value_source_stream_id
        ))
        calc = DCFCalculator(model)
        result = calc.run_deterministic()
        # Enterprise: $50k × 10 = $500k/month
        # SMB: $10k × 20 = $200k/month (uses own price)
        # Total monthly = $700k
        expected_monthly = 50000 * 10 + 10000 * 20
        assert abs(result["cashflows"][0] - expected_monthly) < 1

    def test_linked_stochastic_distribution(self):
        """Linked unit value should follow source distribution in Monte Carlo."""
        model = FinancialModel(
            "Stochastic Test",
            ModelSettings(
                forecast_months=12,
                discount_rate=Distribution(DistributionType.FIXED, {"value": 0.10}),
                terminal_growth_rate=0.02,
            ),
        )
        # Source with NORMAL distribution
        model.add_stream(Stream(
            id="enterprise",
            name="Enterprise",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.NORMAL, {"mean": 50000, "std": 5000}),
            market_units=Distribution(DistributionType.FIXED, {"value": 10}),
        ))
        # Linked stream
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),  # Ignored
            market_units=Distribution(DistributionType.FIXED, {"value": 20}),
            unit_value_source_stream_id="enterprise",
        ))
        calc = DCFCalculator(model)
        result = calc.run_monte_carlo(n_simulations=1000)
        # NPV should vary due to stochastic unit price
        assert result["npv_std"] > 0

    def test_serialization_preserves_link(self):
        """Unit value source should be preserved in serialization."""
        model = make_model_with_unit_prices()
        model.add_stream(Stream(
            id="smb",
            name="SMB",
            stream_type=StreamType.REVENUE,
            start_month=0,
            amount=Distribution(DistributionType.FIXED, {"value": 0}),
            unit_value=Distribution(DistributionType.FIXED, {"value": 10000}),
            market_units=Distribution(DistributionType.FIXED, {"value": 50}),
            unit_value_source_stream_id="enterprise",
        ))
        # Serialize and deserialize
        data = model.to_dict()
        model2 = FinancialModel.from_dict(data)
        assert model2.streams["smb"].unit_value_source_stream_id == "enterprise"

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pytest
from backend.models.stream import Distribution, DistributionType
from backend.engine.distributions import DistributionEngine


class TestFixedDistribution:
    def test_sample_returns_constant(self):
        dist = Distribution(DistributionType.FIXED, {"value": 42.0})
        samples = DistributionEngine.sample(dist, size=100)
        assert all(s == 42.0 for s in samples)

    def test_deterministic_value(self):
        dist = Distribution(DistributionType.FIXED, {"value": 100.0})
        assert DistributionEngine.get_deterministic_value(dist) == 100.0

    def test_preview_flat_line(self):
        dist = Distribution(DistributionType.FIXED, {"value": 50.0})
        preview = DistributionEngine.preview_timeseries(dist, months=12)
        assert len(preview) == 12
        assert all(p["value"] == 50.0 for p in preview)


class TestNormalDistribution:
    def test_sample_shape(self):
        dist = Distribution(DistributionType.NORMAL, {"mean": 100, "std": 10})
        samples = DistributionEngine.sample(dist, size=5000)
        assert len(samples) == 5000
        assert abs(np.mean(samples) - 100) < 2

    def test_deterministic_returns_mean(self):
        dist = Distribution(DistributionType.NORMAL, {"mean": 50, "std": 5})
        assert DistributionEngine.get_deterministic_value(dist) == 50


class TestLognormalDistribution:
    def test_all_positive(self):
        dist = Distribution(DistributionType.LOGNORMAL, {"mean": 3, "std": 0.5})
        samples = DistributionEngine.sample(dist, size=1000)
        assert all(s > 0 for s in samples)

    def test_deterministic_formula(self):
        dist = Distribution(DistributionType.LOGNORMAL, {"mean": 3, "std": 0.5})
        expected = np.exp(3 + 0.5**2 / 2)
        assert abs(DistributionEngine.get_deterministic_value(dist) - expected) < 0.01


class TestUniformDistribution:
    def test_within_bounds(self):
        dist = Distribution(DistributionType.UNIFORM, {"min": 10, "max": 20})
        samples = DistributionEngine.sample(dist, size=1000)
        assert all(10 <= s <= 20 for s in samples)

    def test_deterministic_midpoint(self):
        dist = Distribution(DistributionType.UNIFORM, {"min": 10, "max": 20})
        assert DistributionEngine.get_deterministic_value(dist) == 15


class TestTriangularDistribution:
    def test_within_bounds(self):
        dist = Distribution(DistributionType.TRIANGULAR, {"min": 5, "likely": 10, "max": 20})
        samples = DistributionEngine.sample(dist, size=1000)
        assert all(5 <= s <= 20 for s in samples)

    def test_deterministic_average(self):
        dist = Distribution(DistributionType.TRIANGULAR, {"min": 6, "likely": 12, "max": 18})
        assert DistributionEngine.get_deterministic_value(dist) == 12


class TestLogisticDistribution:
    def test_incremental_not_cumulative(self):
        """Logistic must return incremental adoption (derivative), not cumulative."""
        dist = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3})
        # At midpoint, incremental = k/4
        val = DistributionEngine.get_deterministic_value(dist, month=12)
        assert abs(val - 0.3 / 4) < 0.001

    def test_peak_at_midpoint(self):
        dist = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3})
        values = [DistributionEngine.get_deterministic_value(dist, month=m) for m in range(25)]
        peak_month = values.index(max(values))
        assert peak_month == 12

    def test_incremental_sums_to_one(self):
        dist = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3})
        total = sum(DistributionEngine.get_deterministic_value(dist, month=m) for m in range(200))
        assert abs(total - 1.0) < 0.05

    def test_preview_bell_shaped(self):
        dist = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3})
        preview = DistributionEngine.preview_timeseries(dist, months=25)
        values = [p["value"] for p in preview]
        # Should increase then decrease (bell shape)
        assert values[12] > values[0]
        assert values[12] > values[24]

    def test_returns_zero_without_month(self):
        dist = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3})
        assert DistributionEngine.get_deterministic_value(dist) == 0.0

    def test_amplitude_scales_peak(self):
        """Amplitude should scale all incremental values proportionally."""
        dist_unit = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3, "amplitude": 1.0})
        dist_scaled = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3, "amplitude": 500000})
        peak_unit = DistributionEngine.get_deterministic_value(dist_unit, month=12)
        peak_scaled = DistributionEngine.get_deterministic_value(dist_scaled, month=12)
        assert abs(peak_scaled - peak_unit * 500000) < 0.01

    def test_amplitude_scales_total(self):
        """Sum of incremental values should approach amplitude."""
        amplitude = 250000
        dist = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3, "amplitude": amplitude})
        total = sum(DistributionEngine.get_deterministic_value(dist, month=m) for m in range(200))
        assert abs(total - amplitude) < amplitude * 0.05

    def test_amplitude_default_is_one(self):
        """Omitting amplitude should behave as amplitude=1.0."""
        dist_no_amp = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3})
        dist_amp_one = Distribution(DistributionType.LOGISTIC, {"midpoint": 12, "steepness": 0.3, "amplitude": 1.0})
        val_no = DistributionEngine.get_deterministic_value(dist_no_amp, month=6)
        val_one = DistributionEngine.get_deterministic_value(dist_amp_one, month=6)
        assert val_no == val_one


class TestPreviewTimeseries:
    def test_stochastic_has_bands(self):
        dist = Distribution(DistributionType.NORMAL, {"mean": 100, "std": 10})
        preview = DistributionEngine.preview_timeseries(dist, months=5)
        assert "p10" in preview[0]
        assert "p90" in preview[0]
        assert "mean" in preview[0]

    def test_deterministic_has_value(self):
        dist = Distribution(DistributionType.FIXED, {"value": 42})
        preview = DistributionEngine.preview_timeseries(dist, months=3)
        assert "value" in preview[0]

    def test_fixed_respects_time_bounds(self):
        dist = Distribution(DistributionType.FIXED, {"value": 100})
        preview = DistributionEngine.preview_timeseries(dist, months=10, start_month=3, end_month=5)
        values = [p["value"] for p in preview]
        # Only months 3, 4, 5 should be active (end_month inclusive)
        assert values[0] == 0.0
        assert values[2] == 0.0
        assert values[3] == 100
        assert values[4] == 100
        assert values[5] == 100
        assert values[6] == 0.0
        assert values[9] == 0.0

    def test_single_month_preview(self):
        dist = Distribution(DistributionType.FIXED, {"value": 500})
        preview = DistributionEngine.preview_timeseries(dist, months=10, start_month=5, end_month=5)
        values = [p["value"] for p in preview]
        assert values[4] == 0.0
        assert values[5] == 500
        assert values[6] == 0.0

    def test_stochastic_respects_time_bounds(self):
        dist = Distribution(DistributionType.NORMAL, {"mean": 100, "std": 10})
        preview = DistributionEngine.preview_timeseries(dist, months=10, start_month=2, end_month=4)
        assert preview[0]["mean"] == 0.0
        assert preview[1]["mean"] == 0.0
        assert preview[2]["mean"] > 0
        assert preview[4]["mean"] > 0
        assert preview[5]["mean"] == 0.0


class TestLinearDistribution:
    def test_constant_value(self):
        dist = Distribution(DistributionType.LINEAR, {"rate": 0.05, "amplitude": 1.0})
        val_m0 = DistributionEngine.get_deterministic_value(dist, month=0)
        val_m10 = DistributionEngine.get_deterministic_value(dist, month=10)
        assert abs(val_m0 - 0.05) < 0.001
        assert abs(val_m10 - 0.05) < 0.001

    def test_amplitude_scaling(self):
        dist = Distribution(DistributionType.LINEAR, {"rate": 0.05, "amplitude": 500000})
        val = DistributionEngine.get_deterministic_value(dist)
        assert abs(val - 25000) < 0.01

    def test_cumulative_reaches_amplitude(self):
        rate = 0.05
        dist = Distribution(DistributionType.LINEAR, {"rate": rate, "amplitude": 1.0})
        n_months = int(1 / rate)  # 20
        total = sum(DistributionEngine.get_deterministic_value(dist) for _ in range(n_months))
        assert abs(total - 1.0) < 0.001

    def test_sample_shape(self):
        dist = Distribution(DistributionType.LINEAR, {"rate": 0.05})
        samples = DistributionEngine.sample(dist, size=100)
        assert len(samples) == 100
        assert all(abs(s - 0.05) < 0.001 for s in samples)

    def test_default_amplitude_is_one(self):
        dist = Distribution(DistributionType.LINEAR, {"rate": 0.1})
        val = DistributionEngine.get_deterministic_value(dist)
        assert abs(val - 0.1) < 0.001

    def test_preview_respects_time_bounds(self):
        dist = Distribution(DistributionType.LINEAR, {"rate": 0.05, "amplitude": 1.0})
        preview = DistributionEngine.preview_timeseries(dist, months=10, start_month=2, end_month=7)
        for p in preview:
            if 2 <= p["month"] <= 7:
                assert abs(p["value"] - 0.05) < 0.001
            else:
                assert p["value"] == 0.0

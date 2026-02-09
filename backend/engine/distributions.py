from typing import Dict, List, Optional
import numpy as np

from backend.models.stream import Distribution, DistributionType


class DistributionEngine:

    @staticmethod
    def sample(dist: Distribution, size: int = 1, month: Optional[int] = None) -> np.ndarray:
        p = dist.params
        dt = dist.dist_type

        if dt == DistributionType.FIXED:
            return np.full(size, p["value"])

        if dt == DistributionType.NORMAL:
            return np.random.normal(p["mean"], p["std"], size)

        if dt == DistributionType.LOGNORMAL:
            return np.random.lognormal(p["mean"], p["std"], size)

        if dt == DistributionType.UNIFORM:
            return np.random.uniform(p["min"], p["max"], size)

        if dt == DistributionType.TRIANGULAR:
            return np.random.triangular(p["min"], p["likely"], p["max"], size)

        if dt == DistributionType.LOGISTIC:
            # Return incremental adoption (derivative of S-curve) scaled by amplitude
            if month is None:
                return np.zeros(size)
            midpoint = p["midpoint"]
            steepness = p["steepness"]
            amplitude = p.get("amplitude", 1.0)
            s_t = 1.0 / (1.0 + np.exp(-steepness * (month - midpoint)))
            incremental = amplitude * steepness * s_t * (1.0 - s_t)
            return np.full(size, incremental)

        if dt == DistributionType.LINEAR:
            rate = p["rate"]
            amplitude = p.get("amplitude", 1.0)
            return np.full(size, amplitude * rate)

        raise ValueError(f"Unknown distribution type: {dt}")

    @staticmethod
    def get_deterministic_value(dist: Distribution, month: Optional[int] = None) -> float:
        p = dist.params
        dt = dist.dist_type

        if dt == DistributionType.FIXED:
            return p["value"]

        if dt == DistributionType.NORMAL:
            return p["mean"]

        if dt == DistributionType.LOGNORMAL:
            return float(np.exp(p["mean"] + p["std"] ** 2 / 2))

        if dt == DistributionType.UNIFORM:
            return (p["min"] + p["max"]) / 2

        if dt == DistributionType.TRIANGULAR:
            return (p["min"] + p["likely"] + p["max"]) / 3

        if dt == DistributionType.LOGISTIC:
            if month is None:
                return 0.0
            midpoint = p["midpoint"]
            steepness = p["steepness"]
            amplitude = p.get("amplitude", 1.0)
            s_t = 1.0 / (1.0 + np.exp(-steepness * (month - midpoint)))
            return float(amplitude * steepness * s_t * (1.0 - s_t))

        if dt == DistributionType.LINEAR:
            rate = p["rate"]
            amplitude = p.get("amplitude", 1.0)
            return float(amplitude * rate)

        raise ValueError(f"Unknown distribution type: {dt}")

    @staticmethod
    def get_percentile(dist: Distribution, percentile: float, month: Optional[int] = None) -> float:
        """Get a specific percentile value from a distribution."""
        if dist.dist_type in (DistributionType.FIXED, DistributionType.LOGISTIC, DistributionType.LINEAR):
            return DistributionEngine.get_deterministic_value(dist, month)

        samples = DistributionEngine.sample(dist, size=10000, month=month)
        return float(np.percentile(samples, percentile * 100))

    @staticmethod
    def preview_timeseries(
        dist: Distribution,
        months: int = 60,
        start_month: int = 0,
        end_month: Optional[int] = None,
    ) -> List[Dict]:
        dt = dist.dist_type
        # end_month is inclusive; None means through end of forecast
        active_end = (end_month + 1) if end_month is not None else months

        def _is_active(m: int) -> bool:
            return start_month <= m < active_end

        if dt == DistributionType.LOGISTIC:
            result = []
            for m in range(months):
                val = DistributionEngine.get_deterministic_value(dist, month=m) if _is_active(m) else 0.0
                result.append({"month": m, "value": val})
            return result

        if dt == DistributionType.LINEAR:
            val = DistributionEngine.get_deterministic_value(dist)
            return [{"month": m, "value": val if _is_active(m) else 0.0} for m in range(months)]

        if dt == DistributionType.FIXED:
            val = dist.params["value"]
            return [{"month": m, "value": val if _is_active(m) else 0.0} for m in range(months)]

        # Stochastic distributions: sample and compute statistics
        samples = DistributionEngine.sample(dist, size=10000)
        mean_val = float(np.mean(samples))
        p10 = float(np.percentile(samples, 10))
        p90 = float(np.percentile(samples, 90))
        result = []
        for m in range(months):
            if _is_active(m):
                result.append({"month": m, "mean": mean_val, "p10": p10, "p90": p90})
            else:
                result.append({"month": m, "mean": 0.0, "p10": 0.0, "p90": 0.0})
        return result

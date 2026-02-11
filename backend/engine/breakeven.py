from typing import Dict, List

from scipy.optimize import brentq

from backend.models.model import FinancialModel
from backend.models.stream import Distribution, DistributionType
from backend.engine.sensitivity import SensitivityAnalyzer
from backend.engine.distributions import DistributionEngine
from backend.engine.calculator import DCFCalculator


class BreakevenAnalyzer:
    def __init__(self, model: FinancialModel):
        self.model = model

    def get_solvable_parameters(self) -> List[Dict]:
        """Return list of parameters that can be solved for breakeven."""
        analyzer = SensitivityAnalyzer(self.model)
        params = analyzer.identify_uncertain_parameters()
        # Also include FIXED distributions — any numeric parameter is solvable
        for sid, stream in self.model.streams.items():
            if stream.unit_value is not None and stream.market_units is not None:
                if stream.unit_value.dist_type == DistributionType.FIXED:
                    params.append({
                        "stream_id": sid,
                        "stream_name": stream.name,
                        "parameter_name": f"{stream.name} - Unit Value",
                        "distribution": stream.unit_value,
                    })
                if stream.market_units.dist_type == DistributionType.FIXED:
                    params.append({
                        "stream_id": sid,
                        "stream_name": stream.name,
                        "parameter_name": f"{stream.name} - Market Units",
                        "distribution": stream.market_units,
                    })
            elif stream.amount.dist_type == DistributionType.FIXED:
                label = f"{stream.name} - Amount"
                if stream.parent_stream_id is not None and stream.amount_is_ratio:
                    label = f"{stream.name} - Price Ratio"
                params.append({
                    "stream_id": sid,
                    "stream_name": stream.name,
                    "parameter_name": label,
                    "distribution": stream.amount,
                })

        if self.model.settings.discount_rate.dist_type == DistributionType.FIXED:
            params.append({
                "stream_id": "__settings__",
                "stream_name": "Model Settings",
                "parameter_name": "Discount Rate",
                "distribution": self.model.settings.discount_rate,
            })

        # Deduplicate by (stream_id, parameter_name)
        seen = set()
        unique = []
        for p in params:
            key = (p["stream_id"], p["parameter_name"])
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique

    def run_breakeven(self, stream_id: str, parameter_name: str, target_npv: float = 0.0) -> dict:
        """Find the parameter value that drives NPV to the target."""
        # Find the matching parameter
        params = self.get_solvable_parameters()
        param_info = None
        for p in params:
            if p["stream_id"] == stream_id and p["parameter_name"] == parameter_name:
                param_info = p
                break

        if param_info is None:
            return {
                "found": False,
                "error": f"Parameter '{parameter_name}' not found for stream '{stream_id}'",
            }

        # Get current deterministic value
        original_value = DistributionEngine.get_deterministic_value(param_info["distribution"])

        # Determine search bounds
        if parameter_name == "Discount Rate":
            lo, hi = 0.001, 1.0
        elif parameter_name == "Escalation Rate":
            lo, hi = -0.5, 1.0
        else:
            # For amounts: search from 0 to 10x current, or a wide range if current is 0
            magnitude = abs(original_value) if original_value != 0 else 10000
            lo, hi = 0.0, magnitude * 10

        # Objective: NPV(param_value) - target_npv = 0
        analyzer = SensitivityAnalyzer(self.model)

        def objective(value):
            return analyzer._run_with_override(param_info, value) - target_npv

        try:
            breakeven_value = brentq(objective, lo, hi, xtol=1e-6, maxiter=200)
            return {
                "found": True,
                "parameter_name": parameter_name,
                "stream_name": param_info["stream_name"],
                "stream_id": stream_id,
                "breakeven_value": float(breakeven_value),
                "original_value": float(original_value),
                "target_npv": target_npv,
            }
        except ValueError:
            return {
                "found": False,
                "parameter_name": parameter_name,
                "stream_name": param_info["stream_name"],
                "stream_id": stream_id,
                "original_value": float(original_value),
                "target_npv": target_npv,
                "error": "No breakeven found in search range — NPV does not cross the target.",
            }

from typing import Dict, List
import numpy as np

from backend.models.model import FinancialModel
from backend.models.stream import DistributionType
from backend.engine.distributions import DistributionEngine
from backend.engine.calculator import DCFCalculator


class SensitivityAnalyzer:
    def __init__(self, model: FinancialModel):
        self.model = model

    def identify_uncertain_parameters(self) -> List[Dict]:
        """Find all non-FIXED distributions in the model."""
        params = []

        # Discount rate
        if self.model.settings.discount_rate.dist_type != DistributionType.FIXED:
            params.append({
                "stream_id": "__settings__",
                "stream_name": "Model Settings",
                "parameter_name": "Discount Rate",
                "distribution": self.model.settings.discount_rate,
            })

        # Escalation rate (global)
        if (self.model.settings.escalation_rate is not None
                and self.model.settings.escalation_rate.dist_type != DistributionType.FIXED):
            params.append({
                "stream_id": "__settings__",
                "stream_name": "Model Settings",
                "parameter_name": "Escalation Rate",
                "distribution": self.model.settings.escalation_rate,
            })

        for sid, stream in self.model.streams.items():
            # Unit value mode: check unit_value and market_units instead of amount
            if stream.unit_value is not None and stream.market_units is not None:
                if stream.unit_value.dist_type != DistributionType.FIXED:
                    params.append({
                        "stream_id": sid,
                        "stream_name": stream.name,
                        "parameter_name": f"{stream.name} - Unit Value",
                        "distribution": stream.unit_value,
                    })
                if stream.market_units.dist_type != DistributionType.FIXED:
                    params.append({
                        "stream_id": sid,
                        "stream_name": stream.name,
                        "parameter_name": f"{stream.name} - Market Units",
                        "distribution": stream.market_units,
                    })
            elif stream.amount.dist_type != DistributionType.FIXED:
                label = f"{stream.name} - Amount"
                if stream.parent_stream_id is not None and stream.amount_is_ratio:
                    label = f"{stream.name} - Price Ratio"
                params.append({
                    "stream_id": sid,
                    "stream_name": stream.name,
                    "parameter_name": label,
                    "distribution": stream.amount,
                })

        return params

    def run_tornado_analysis(self) -> dict:
        """Run sensitivity analysis producing tornado chart data."""
        uncertain_params = self.identify_uncertain_parameters()

        if not uncertain_params:
            return {"baseline_npv": 0, "parameters": []}

        # Baseline NPV (all at deterministic/P50)
        calc = DCFCalculator(self.model)
        baseline_result = calc.run_deterministic()
        baseline_npv = baseline_result["npv"]

        results = []

        for param_info in uncertain_params:
            dist = param_info["distribution"]

            # Get P10 and P90 values
            p10_val = DistributionEngine.get_percentile(dist, 0.10)
            p90_val = DistributionEngine.get_percentile(dist, 0.90)

            # Run with parameter at P10
            npv_low = self._run_with_override(param_info, p10_val)

            # Run with parameter at P90
            npv_high = self._run_with_override(param_info, p90_val)

            swing = abs(npv_high - npv_low)

            results.append({
                "parameter_name": param_info["parameter_name"],
                "stream_name": param_info["stream_name"],
                "swing": swing,
                "npv_low": min(npv_low, npv_high),
                "npv_high": max(npv_low, npv_high),
                "p10_value": p10_val,
                "p90_value": p90_val,
            })

        # Sort by swing descending, take top 15
        results.sort(key=lambda x: x["swing"], reverse=True)
        results = results[:15]

        return {
            "baseline_npv": baseline_npv,
            "parameters": results,
        }

    def _run_with_override(self, param_info: Dict, override_value: float) -> float:
        """Run deterministic calculation with one parameter overridden to a fixed value."""
        from backend.models.stream import Distribution, DistributionType as DT

        override_dist = Distribution(DT.FIXED, {"value": override_value})

        stream_id = param_info["stream_id"]
        param_name = param_info["parameter_name"]

        if stream_id == "__settings__" and param_name == "Discount Rate":
            original = self.model.settings.discount_rate
            self.model.settings.discount_rate = override_dist
        elif stream_id == "__settings__" and param_name == "Escalation Rate":
            original = self.model.settings.escalation_rate
            self.model.settings.escalation_rate = override_dist
        elif param_name.endswith("- Unit Value"):
            original = self.model.streams[stream_id].unit_value
            self.model.streams[stream_id].unit_value = override_dist
        elif param_name.endswith("- Market Units"):
            original = self.model.streams[stream_id].market_units
            self.model.streams[stream_id].market_units = override_dist
        elif param_name.endswith("- Amount") or param_name.endswith("- Price Ratio"):
            original = self.model.streams[stream_id].amount
            self.model.streams[stream_id].amount = override_dist
        else:
            return 0.0

        try:
            calc = DCFCalculator(self.model)
            result = calc.run_deterministic()
            return result["npv"]
        finally:
            if stream_id == "__settings__" and param_name == "Discount Rate":
                self.model.settings.discount_rate = original
            elif stream_id == "__settings__" and param_name == "Escalation Rate":
                self.model.settings.escalation_rate = original
            elif param_name.endswith("- Unit Value"):
                self.model.streams[stream_id].unit_value = original
            elif param_name.endswith("- Market Units"):
                self.model.streams[stream_id].market_units = original
            elif param_name.endswith("- Amount") or param_name.endswith("- Price Ratio"):
                self.model.streams[stream_id].amount = original

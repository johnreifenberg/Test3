from typing import Dict, List, Optional, Tuple
import numpy as np

try:
    from scipy.optimize import brentq
except ImportError:
    brentq = None

from backend.models.model import FinancialModel
from backend.models.stream import Stream, StreamType, DistributionType
from backend.engine.distributions import DistributionEngine
from backend.engine.terminal_value import identify_perpetual_streams, calculate_terminal_value


class DCFCalculator:
    def __init__(self, model: FinancialModel):
        self.model = model
        self.n_months = model.settings.forecast_months

    def _sample_escalation(self, deterministic: bool) -> Optional[float]:
        """Sample or get deterministic escalation rate (annual)."""
        esc = self.model.settings.escalation_rate
        if esc is None:
            return None
        if deterministic:
            return DistributionEngine.get_deterministic_value(esc)
        return float(DistributionEngine.sample(esc, size=1)[0])

    def calculate_root_stream_cashflows(
        self,
        stream: Stream,
        deterministic: bool,
        annual_escalation: Optional[float] = None,
    ) -> np.ndarray:
        """Calculate cashflows for a root (parentless) stream."""
        cashflows = np.zeros(self.n_months)
        end = (stream.end_month + 1) if stream.end_month is not None else self.n_months

        for m in range(stream.start_month, min(end, self.n_months)):
            months_elapsed = m - stream.start_month

            # Base amount
            if stream.unit_value is not None and stream.market_units is not None:
                # Unit value x market units mode
                if deterministic:
                    uv = DistributionEngine.get_deterministic_value(stream.unit_value, month=m)
                    mu = DistributionEngine.get_deterministic_value(stream.market_units, month=m)
                else:
                    uv = float(DistributionEngine.sample(stream.unit_value, size=1, month=m)[0])
                    mu = float(DistributionEngine.sample(stream.market_units, size=1, month=m)[0])
                amount = uv * mu
            elif deterministic:
                amount = DistributionEngine.get_deterministic_value(stream.amount, month=m)
            else:
                amount = float(DistributionEngine.sample(stream.amount, size=1, month=m)[0])

            # Escalation rate (global, compounded monthly)
            if annual_escalation is not None:
                monthly_esc = annual_escalation / 12
                amount *= (1 + monthly_esc) ** months_elapsed

            # Adoption curve
            if stream.adoption_curve is not None:
                if deterministic:
                    adoption_factor = DistributionEngine.get_deterministic_value(
                        stream.adoption_curve, month=m
                    )
                else:
                    adoption_factor = float(
                        DistributionEngine.sample(stream.adoption_curve, size=1, month=m)[0]
                    )
                amount *= adoption_factor

            cashflows[m] = amount

        # Apply sign: costs are negative
        if stream.stream_type == StreamType.COST:
            cashflows = -np.abs(cashflows)

        return cashflows

    def calculate_child_stream_cashflows(
        self,
        stream: Stream,
        parent_cashflows: np.ndarray,
        deterministic: bool,
        annual_escalation: Optional[float] = None,
    ) -> np.ndarray:
        """Calculate cashflows for a child stream based on parent cashflows.

        For each month where the parent has non-zero cashflow, compute the child
        event value (locked at the original parent value) and place it at the
        appropriate months based on trigger_delay and periodicity.
        """
        cashflows = np.zeros(self.n_months)
        child_end = (stream.end_month + 1) if stream.end_month is not None else self.n_months

        # Sample the child's amount/ratio once per simulation
        if deterministic:
            child_amount = DistributionEngine.get_deterministic_value(stream.amount)
        else:
            child_amount = float(DistributionEngine.sample(stream.amount, size=1)[0])

        for pm in range(self.n_months):
            parent_val = parent_cashflows[pm]
            if parent_val == 0.0:
                continue

            # Compute child event value (locked at original parent value)
            if stream.amount_is_ratio:
                event_val = abs(parent_val) * child_amount * stream.conversion_rate
            else:
                event_val = child_amount * stream.conversion_rate

            first_event = pm + stream.trigger_delay_months

            if stream.periodicity_months is None:
                # Concurrent: single event at first_event
                if 0 <= first_event < min(child_end, self.n_months):
                    if first_event >= stream.start_month:
                        val = event_val
                        # Apply escalation based on months from stream start
                        if annual_escalation is not None:
                            months_elapsed = first_event - stream.start_month
                            if months_elapsed > 0:
                                monthly_esc = annual_escalation / 12
                                val *= (1 + monthly_esc) ** months_elapsed
                        cashflows[first_event] += val
            else:
                # Recurring: events at first_event, first_event+period, etc.
                event_month = first_event
                while event_month < min(child_end, self.n_months):
                    if event_month >= stream.start_month:
                        val = event_val
                        # Apply escalation based on months from stream start
                        if annual_escalation is not None:
                            months_elapsed = event_month - stream.start_month
                            if months_elapsed > 0:
                                monthly_esc = annual_escalation / 12
                                val *= (1 + monthly_esc) ** months_elapsed
                        cashflows[event_month] += val
                    event_month += stream.periodicity_months

        # Apply sign: costs are negative
        if stream.stream_type == StreamType.COST:
            cashflows = -np.abs(cashflows)

        return cashflows

    def calculate_npv(self, cashflows: np.ndarray, discount_rate: float) -> float:
        monthly_rate = discount_rate / 12
        discount_factors = np.array([
            1.0 / (1 + monthly_rate) ** t for t in range(len(cashflows))
        ])
        return float(np.sum(cashflows * discount_factors))

    def calculate_irr(self, cashflows: np.ndarray) -> Tuple[Optional[float], Optional[str]]:
        """Calculate IRR using scipy.optimize.brentq.

        Returns (irr_annualized, error_message). One of the two will be None.
        """
        # Check for sign change (need both positive and negative cashflows)
        has_positive = np.any(cashflows > 0)
        has_negative = np.any(cashflows < 0)
        if not (has_positive and has_negative):
            return None, "No sign change in cashflows (need both positive and negative values)"

        if brentq is None:
            return None, "scipy not installed"

        def npv_at_rate(monthly_rate):
            factors = np.array([1.0 / (1 + monthly_rate) ** t for t in range(len(cashflows))])
            return float(np.sum(cashflows * factors))

        try:
            # Search for monthly rate in a wide range
            monthly_irr = brentq(npv_at_rate, -0.5, 10.0, xtol=1e-10, maxiter=1000)
            return float(monthly_irr * 12), None  # Annualize
        except ValueError:
            return None, "IRR solver could not find a solution in the search range"
        except Exception as e:
            return None, f"IRR calculation failed: {str(e)}"

    def _run_single(self, deterministic: bool) -> tuple:
        """Run a single calculation pass (used by both deterministic and MC)."""
        execution_order = self.model.get_execution_order()
        stream_cashflows: Dict[str, np.ndarray] = {}
        annual_escalation = self._sample_escalation(deterministic)

        for sid in execution_order:
            stream = self.model.streams[sid]

            if stream.parent_stream_id is not None:
                parent_cfs = stream_cashflows.get(stream.parent_stream_id)
                if parent_cfs is not None:
                    cfs = self.calculate_child_stream_cashflows(
                        stream, parent_cfs, deterministic, annual_escalation
                    )
                else:
                    cfs = np.zeros(self.n_months)
            else:
                cfs = self.calculate_root_stream_cashflows(
                    stream, deterministic, annual_escalation
                )

            stream_cashflows[sid] = cfs

        # Sum all streams
        total_cashflows = np.zeros(self.n_months)
        for cfs in stream_cashflows.values():
            total_cashflows += cfs

        return stream_cashflows, total_cashflows

    def run_deterministic(self) -> dict:
        calc_mode = self.model.settings.calculation_mode
        if calc_mode == "IRR":
            return self._run_deterministic_irr()
        return self._run_deterministic_npv()

    def _run_deterministic_npv(self) -> dict:
        stream_cashflows, total_cashflows = self._run_single(deterministic=True)

        # Discount rate
        discount_rate = DistributionEngine.get_deterministic_value(self.model.settings.discount_rate)

        # NPV
        npv = self.calculate_npv(total_cashflows, discount_rate)

        # Terminal value
        perpetual_ids = identify_perpetual_streams(self.model)
        terminal_value_total = 0.0
        for sid in perpetual_ids:
            final_cf = stream_cashflows[sid][-1]
            tv = calculate_terminal_value(
                final_cf,
                self.model.settings.terminal_growth_rate,
                discount_rate,
                self.n_months,
            )
            terminal_value_total += tv

        npv += terminal_value_total

        # IRR (informational)
        irr, irr_error = self.calculate_irr(total_cashflows)

        return {
            "mode": "deterministic",
            "calculation_mode": "NPV",
            "npv": npv,
            "irr": irr,
            "irr_error": irr_error,
            "terminal_value": terminal_value_total,
            "discount_rate": discount_rate,
            "cashflows": total_cashflows.tolist(),
            "stream_details": {
                sid: cfs.tolist() for sid, cfs in stream_cashflows.items()
            },
        }

    def _run_deterministic_irr(self) -> dict:
        stream_cashflows, total_cashflows = self._run_single(deterministic=True)

        # IRR (primary result)
        irr, irr_error = self.calculate_irr(total_cashflows)

        return {
            "mode": "deterministic",
            "calculation_mode": "IRR",
            "npv": 0.0,
            "irr": irr,
            "irr_error": irr_error,
            "terminal_value": None,
            "discount_rate": None,
            "cashflows": total_cashflows.tolist(),
            "stream_details": {
                sid: cfs.tolist() for sid, cfs in stream_cashflows.items()
            },
        }

    def run_monte_carlo(self, n_simulations: int = 10000) -> dict:
        calc_mode = self.model.settings.calculation_mode
        if calc_mode == "IRR":
            return self._run_monte_carlo_irr(n_simulations)
        return self._run_monte_carlo_npv(n_simulations)

    def _run_monte_carlo_npv(self, n_simulations: int) -> dict:
        npv_results = []
        all_cashflows = []

        discount_dist = self.model.settings.discount_rate

        for _ in range(n_simulations):
            stream_cashflows, total_cashflows = self._run_single(deterministic=False)

            # Sample discount rate
            dr = float(DistributionEngine.sample(discount_dist, size=1)[0])
            if dr <= self.model.settings.terminal_growth_rate:
                dr = self.model.settings.terminal_growth_rate + 0.001

            npv = self.calculate_npv(total_cashflows, dr)

            # Terminal value
            perpetual_ids = identify_perpetual_streams(self.model)
            for sid in perpetual_ids:
                final_cf = stream_cashflows[sid][-1]
                tv = calculate_terminal_value(
                    final_cf,
                    self.model.settings.terminal_growth_rate,
                    dr,
                    self.n_months,
                )
                npv += tv

            npv_results.append(npv)
            all_cashflows.append(total_cashflows.tolist())

        npv_arr = np.array(npv_results)
        cashflow_arr = np.array(all_cashflows)

        # Cashflow distribution stats per month
        cashflow_distributions = []
        for m in range(self.n_months):
            month_cfs = cashflow_arr[:, m]
            cashflow_distributions.append({
                "month": m,
                "mean": float(np.mean(month_cfs)),
                "median": float(np.median(month_cfs)),
                "p10": float(np.percentile(month_cfs, 10)),
                "p90": float(np.percentile(month_cfs, 90)),
            })

        return {
            "mode": "monte_carlo",
            "calculation_mode": "NPV",
            "n_simulations": n_simulations,
            "npv_mean": float(np.mean(npv_arr)),
            "npv_median": float(np.median(npv_arr)),
            "npv_std": float(np.std(npv_arr)),
            "npv_p10": float(np.percentile(npv_arr, 10)),
            "npv_p25": float(np.percentile(npv_arr, 25)),
            "npv_p75": float(np.percentile(npv_arr, 75)),
            "npv_p90": float(np.percentile(npv_arr, 90)),
            "npv_distribution": npv_arr.tolist(),
            "cashflow_distributions": cashflow_distributions,
        }

    def _run_monte_carlo_irr(self, n_simulations: int) -> dict:
        irr_results = []
        irr_failed_count = 0
        all_cashflows = []

        for _ in range(n_simulations):
            _, total_cashflows = self._run_single(deterministic=False)
            irr, error = self.calculate_irr(total_cashflows)
            if irr is not None:
                irr_results.append(irr)
            else:
                irr_failed_count += 1
            all_cashflows.append(total_cashflows.tolist())

        cashflow_arr = np.array(all_cashflows)

        # Cashflow distribution stats per month
        cashflow_distributions = []
        for m in range(self.n_months):
            month_cfs = cashflow_arr[:, m]
            cashflow_distributions.append({
                "month": m,
                "mean": float(np.mean(month_cfs)),
                "median": float(np.median(month_cfs)),
                "p10": float(np.percentile(month_cfs, 10)),
                "p90": float(np.percentile(month_cfs, 90)),
            })

        result = {
            "mode": "monte_carlo",
            "calculation_mode": "IRR",
            "n_simulations": n_simulations,
            "irr_failed_count": irr_failed_count,
            "cashflow_distributions": cashflow_distributions,
        }

        if irr_results:
            irr_arr = np.array(irr_results)
            result.update({
                "irr_mean": float(np.mean(irr_arr)),
                "irr_median": float(np.median(irr_arr)),
                "irr_std": float(np.std(irr_arr)),
                "irr_p10": float(np.percentile(irr_arr, 10)),
                "irr_p25": float(np.percentile(irr_arr, 25)),
                "irr_p75": float(np.percentile(irr_arr, 75)),
                "irr_p90": float(np.percentile(irr_arr, 90)),
                "irr_distribution": irr_arr.tolist(),
            })
        else:
            result.update({
                "irr_mean": None,
                "irr_median": None,
                "irr_std": None,
                "irr_p10": None,
                "irr_p25": None,
                "irr_p75": None,
                "irr_p90": None,
                "irr_distribution": [],
            })

        return result

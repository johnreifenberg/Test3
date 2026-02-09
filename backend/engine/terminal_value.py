from typing import List

from backend.models.model import FinancialModel


def identify_perpetual_streams(model: FinancialModel) -> List[str]:
    """Return stream IDs where end_month is None or >= forecast_months."""
    perpetual = []
    for sid, stream in model.streams.items():
        if stream.end_month is None or stream.end_month >= model.settings.forecast_months:
            perpetual.append(sid)
    return perpetual


def calculate_terminal_value(
    final_month_cashflow: float,
    terminal_growth_rate: float,
    discount_rate: float,
    forecast_months: int,
) -> float:
    """
    Calculate the present value of terminal value using the perpetuity formula.

    TV = CF * (1 + g) / (r - g)
    PV(TV) = TV / (1 + r/12)^forecast_months
    """
    if discount_rate <= terminal_growth_rate:
        return 0.0

    tv = final_month_cashflow * (1 + terminal_growth_rate) / (discount_rate - terminal_growth_rate)
    monthly_rate = discount_rate / 12
    pv_tv = tv / ((1 + monthly_rate) ** forecast_months)
    return pv_tv

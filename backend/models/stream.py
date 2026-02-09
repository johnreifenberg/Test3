from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class DistributionType(str, Enum):
    FIXED = "FIXED"
    NORMAL = "NORMAL"
    LOGNORMAL = "LOGNORMAL"
    UNIFORM = "UNIFORM"
    TRIANGULAR = "TRIANGULAR"
    LOGISTIC = "LOGISTIC"
    LINEAR = "LINEAR"


@dataclass
class Distribution:
    dist_type: DistributionType
    params: Dict[str, float]

    def is_deterministic(self) -> bool:
        return self.dist_type == DistributionType.FIXED

    def to_dict(self) -> dict:
        return {
            "type": self.dist_type.value,
            "params": dict(self.params),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Distribution":
        return cls(
            dist_type=DistributionType(data["type"]),
            params=data["params"],
        )


class StreamType(str, Enum):
    REVENUE = "REVENUE"
    COST = "COST"


@dataclass
class Stream:
    id: str
    name: str
    stream_type: StreamType
    start_month: int
    amount: Distribution
    end_month: Optional[int] = None
    adoption_curve: Optional[Distribution] = None
    parent_stream_id: Optional[str] = None
    # Child stream fields (used when parent_stream_id is set)
    conversion_rate: float = 1.0
    trigger_delay_months: int = 0
    periodicity_months: Optional[int] = None
    amount_is_ratio: bool = True
    # Unit value mode: when both set, calculator uses unit_value * market_units instead of amount
    unit_value: Optional[Distribution] = None
    market_units: Optional[Distribution] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "stream_type": self.stream_type.value,
            "start_month": self.start_month,
            "end_month": self.end_month,
            "amount": self.amount.to_dict(),
            "adoption_curve": self.adoption_curve.to_dict() if self.adoption_curve else None,
            "parent_stream_id": self.parent_stream_id,
            "conversion_rate": self.conversion_rate,
            "trigger_delay_months": self.trigger_delay_months,
            "periodicity_months": self.periodicity_months,
            "amount_is_ratio": self.amount_is_ratio,
            "unit_value": self.unit_value.to_dict() if self.unit_value else None,
            "market_units": self.market_units.to_dict() if self.market_units else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Stream":
        return cls(
            id=data["id"],
            name=data["name"],
            stream_type=StreamType(data["stream_type"]),
            start_month=data["start_month"],
            end_month=data.get("end_month"),
            amount=Distribution.from_dict(data["amount"]),
            adoption_curve=Distribution.from_dict(data["adoption_curve"]) if data.get("adoption_curve") else None,
            parent_stream_id=data.get("parent_stream_id"),
            conversion_rate=data.get("conversion_rate", 1.0),
            trigger_delay_months=data.get("trigger_delay_months", 0),
            periodicity_months=data.get("periodicity_months"),
            amount_is_ratio=data.get("amount_is_ratio", True),
            unit_value=Distribution.from_dict(data["unit_value"]) if data.get("unit_value") else None,
            market_units=Distribution.from_dict(data["market_units"]) if data.get("market_units") else None,
        )

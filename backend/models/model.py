from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict

from backend.models.stream import Distribution, DistributionType, Stream


class ModelValidationError(Exception):
    pass


class CircularDependencyError(ModelValidationError):
    pass


@dataclass
class ModelSettings:
    forecast_months: int = 60
    discount_rate: Distribution = field(
        default_factory=lambda: Distribution(DistributionType.FIXED, {"value": 0.10})
    )
    terminal_growth_rate: float = 0.025
    escalation_rate: Optional[Distribution] = None
    calculation_mode: str = "NPV"  # "NPV" or "IRR"

    def to_dict(self) -> dict:
        return {
            "forecast_months": self.forecast_months,
            "discount_rate": self.discount_rate.to_dict(),
            "terminal_growth_rate": self.terminal_growth_rate,
            "escalation_rate": self.escalation_rate.to_dict() if self.escalation_rate else None,
            "calculation_mode": self.calculation_mode,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelSettings":
        return cls(
            forecast_months=data.get("forecast_months", 60),
            discount_rate=Distribution.from_dict(data["discount_rate"]),
            terminal_growth_rate=data.get("terminal_growth_rate", 0.025),
            escalation_rate=Distribution.from_dict(data["escalation_rate"]) if data.get("escalation_rate") else None,
            calculation_mode=data.get("calculation_mode", "NPV"),
        )


class FinancialModel:
    def __init__(self, name: str = "Untitled Model", settings: Optional[ModelSettings] = None):
        self.name: str = name
        self.settings: ModelSettings = settings or ModelSettings()
        self.streams: Dict[str, Stream] = {}
        self.stream_order: List[str] = []

    def add_stream(self, stream: Stream) -> None:
        self.streams[stream.id] = stream
        if stream.id not in self.stream_order:
            self.stream_order.append(stream.id)

    def remove_stream(self, stream_id: str) -> None:
        if stream_id not in self.streams:
            raise ModelValidationError(f"Stream '{stream_id}' not found")
        del self.streams[stream_id]
        if stream_id in self.stream_order:
            self.stream_order.remove(stream_id)
        # Clear parent references from children of the removed stream
        for stream in self.streams.values():
            if stream.parent_stream_id == stream_id:
                stream.parent_stream_id = None

    def reorder_streams(self, new_order: List[str]) -> None:
        for sid in new_order:
            if sid not in self.streams:
                raise ModelValidationError(f"Stream '{sid}' not found in model")
        if set(new_order) != set(self.streams.keys()):
            raise ModelValidationError("Order list must include all streams exactly once")
        self.stream_order = new_order

    def get_children(self, parent_id: str) -> List[Stream]:
        return [s for s in self.streams.values() if s.parent_stream_id == parent_id]

    def validate(self) -> None:
        # Check all parent references exist and validate child fields
        for sid, stream in self.streams.items():
            if stream.parent_stream_id is not None:
                if stream.parent_stream_id not in self.streams:
                    raise ModelValidationError(
                        f"Stream '{sid}' references non-existent parent '{stream.parent_stream_id}'"
                    )
                if not 0.0 <= stream.conversion_rate <= 1.0:
                    raise ModelValidationError(
                        f"Conversion rate must be between 0 and 1, got {stream.conversion_rate}"
                    )

        # Check for circular dependencies using DFS
        graph: Dict[str, List[str]] = defaultdict(list)
        for sid, stream in self.streams.items():
            if stream.parent_stream_id is not None:
                graph[stream.parent_stream_id].append(sid)

        visited = set()
        rec_stack = set()

        def _dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if _dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            rec_stack.discard(node)
            return False

        for stream_id in self.streams:
            if stream_id not in visited:
                if _dfs(stream_id):
                    raise CircularDependencyError("Circular dependency detected among streams")

        # Validate discount rate > terminal growth rate (NPV mode only)
        if self.settings.calculation_mode == "NPV":
            from backend.engine.distributions import DistributionEngine
            dr = DistributionEngine.get_deterministic_value(self.settings.discount_rate)
            if dr <= self.settings.terminal_growth_rate:
                raise ModelValidationError(
                    f"Discount rate ({dr}) must be greater than terminal growth rate "
                    f"({self.settings.terminal_growth_rate})"
                )

    def get_execution_order(self) -> List[str]:
        """Topological sort of stream IDs based on parent-child relationships."""
        graph: Dict[str, List[str]] = defaultdict(list)
        in_degree: Dict[str, int] = {sid: 0 for sid in self.streams}

        for sid, stream in self.streams.items():
            if stream.parent_stream_id is not None:
                graph[stream.parent_stream_id].append(sid)
                in_degree[sid] = in_degree.get(sid, 0) + 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in graph.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.streams):
            raise CircularDependencyError("Circular dependency detected during topological sort")

        return order

    def to_dict(self) -> dict:
        ordered = []
        for sid in self.stream_order:
            if sid in self.streams:
                ordered.append(self.streams[sid].to_dict())
        for sid, s in self.streams.items():
            if sid not in self.stream_order:
                ordered.append(s.to_dict())
        return {
            "name": self.name,
            "settings": self.settings.to_dict(),
            "streams": ordered,
            "stream_order": list(self.stream_order),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FinancialModel":
        model = cls(
            name=data.get("name", "Untitled Model"),
            settings=ModelSettings.from_dict(data["settings"]),
        )
        for s_data in data.get("streams", []):
            model.add_stream(Stream.from_dict(s_data))
        if "stream_order" in data:
            model.stream_order = data["stream_order"]
        return model

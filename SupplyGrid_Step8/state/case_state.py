from dataclasses import dataclass, asdict
from datetime import date
from decimal import Decimal
import math
import re


@dataclass(frozen=True)
class Scenario:
    supplier_id: str
    capacity_loss_percent: float
    duration_days: int
    assumed_delay_days: int
    daily_penalty_rate: str = "0.001"
    uncovered_unit_cost_cents: int = 0
    route_capacity_mode: str = "single-batch"
    time_limit_seconds: int = 60
    snapshot_what_if: bool = False
    analyze_low_risk_reason: str = ""

    def __post_init__(self):
        if not re.fullmatch(r"S\d{3}", self.supplier_id):
            raise ValueError("Invalid supplier ID")
        for field in ("duration_days", "assumed_delay_days", "time_limit_seconds"):
            val = getattr(self, field)
            if type(val) is not int or val <= 0:
                raise ValueError(f"{field} must be a positive integer")
        if type(self.capacity_loss_percent) not in (int, float) or not math.isfinite(self.capacity_loss_percent) or not 0 <= self.capacity_loss_percent <= 100:
            raise ValueError("Capacity loss outside [0,100]")
        rate = Decimal(self.daily_penalty_rate)
        if not rate.is_finite() or not 0 <= rate <= 1:
            raise ValueError("Penalty rate outside [0,1]")
        if type(self.uncovered_unit_cost_cents) is not int or self.uncovered_unit_cost_cents < 0:
            raise ValueError("Uncovered-unit cost must be nonnegative cents")
        if self.route_capacity_mode not in ("single-batch", "per-consignment"):
            raise ValueError("Invalid route capacity scope")
        if type(self.snapshot_what_if) is not bool or not isinstance(self.analyze_low_risk_reason, str):
            raise ValueError("Invalid review flags")
        if self.analyze_low_risk_reason and len(self.analyze_low_risk_reason.strip()) < 10:
            raise ValueError("Provide a substantive low-risk review reason")

    def as_dict(self):
        return asdict(self)


class CaseState:
    def __init__(self, case_id, scenario):
        self.case_id = case_id
        self.scenario = scenario
        self.messages = {}
        self.status = "STARTED"

    def add(self, role, message):
        from common import validate_message
        if role in self.messages:
            raise ValueError("Duplicate stage; create a new case for replanning")
        dependencies = {"risk": [], "impact": ["risk"], "financial": ["impact"],
                        "mitigation": ["impact"], "optimization": ["financial", "mitigation"]}
        if not all(k in self.messages for k in dependencies[role]):
            raise ValueError("Missing prerequisite agent handoff")
        validate_message(role, message, self.case_id, self.scenario.supplier_id)
        self.messages[role] = message

    def serialized(self):
        return {"case_id": self.case_id, "status": self.status, "scenario": self.scenario.as_dict(),
                "messages": self.messages, "actions_executed": False, "human_review_required": True,
                "scope": "Conditional what-if analysis; not confirmed causal loss or executed recovery"}

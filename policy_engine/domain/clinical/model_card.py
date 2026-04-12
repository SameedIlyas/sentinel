"""Model Card domain entities — pure Python, zero framework imports."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class LifecycleStage(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    PUBLISHED = "published"
    RETIRED = "retired"


# Valid transitions
_VALID_TRANSITIONS = {
    LifecycleStage.DRAFT: {LifecycleStage.REVIEW},
    LifecycleStage.REVIEW: {LifecycleStage.PUBLISHED, LifecycleStage.DRAFT},
    LifecycleStage.PUBLISHED: {LifecycleStage.RETIRED},
    LifecycleStage.RETIRED: set(),
}


@dataclass
class ModelCardMetricEntity:
    metric_name: str
    value: float
    subgroup: Optional[str] = None
    metric_type: Optional[str] = None


@dataclass
class ModelCardEntity:
    id: str
    name: str
    lifecycle_stage: LifecycleStage = LifecycleStage.DRAFT
    intended_use: Optional[str] = None
    performance_metrics: Dict = field(default_factory=dict)
    bias_summary: Dict = field(default_factory=dict)
    version: str = "1.0"
    fda_status: Optional[str] = None
    chai_version: str = "1.0"

    def transition_to(self, new_stage: LifecycleStage) -> None:
        """Advance lifecycle stage or raise ValueError on invalid transition."""
        allowed = _VALID_TRANSITIONS.get(self.lifecycle_stage, set())
        if new_stage not in allowed:
            raise ValueError(
                f"Invalid transition: {self.lifecycle_stage} -> {new_stage}. "
                f"Allowed: {allowed}"
            )
        self.lifecycle_stage = new_stage

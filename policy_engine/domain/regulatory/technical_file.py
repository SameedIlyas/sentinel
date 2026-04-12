"""Technical File domain — FDA 510(k) and EU MDR regulatory automation."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RegulatoryType(str, Enum):
    FDA_510K = "fda_510k"
    EU_MDR = "eu_mdr"
    BOTH = "both"


class TechnicalFileLifecycle(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    RETIRED = "retired"


# Valid forward transitions
LIFECYCLE_TRANSITIONS: Dict[TechnicalFileLifecycle, set] = {
    TechnicalFileLifecycle.DRAFT: {
        TechnicalFileLifecycle.SUBMITTED,
    },
    TechnicalFileLifecycle.SUBMITTED: {
        TechnicalFileLifecycle.UNDER_REVIEW,
        TechnicalFileLifecycle.DRAFT,
    },
    TechnicalFileLifecycle.UNDER_REVIEW: {
        TechnicalFileLifecycle.APPROVED,
        TechnicalFileLifecycle.DRAFT,
    },
    TechnicalFileLifecycle.APPROVED: {
        TechnicalFileLifecycle.RETIRED,
    },
    TechnicalFileLifecycle.RETIRED: set(),
}

# FDA 510(k) required section types
FDA_510K_SECTIONS: List[str] = [
    "device_description",
    "substantial_equivalence",
    "performance_testing",
    "labeling",
    "biocompatibility",
    "software_documentation",
]

# EU MDR required section types
EU_MDR_SECTIONS: List[str] = [
    "clinical_evaluation",
    "risk_management",
    "usability",
    "device_description",
    "labeling",
    "post_market_surveillance_plan",
]


@dataclass
class TechnicalFileSectionEntity:
    section_type: str
    content: str
    order_index: int
    auto_generated: bool = False


@dataclass
class TechnicalFileEntity:
    id: str
    title: str
    regulatory_type: RegulatoryType
    product_name: str
    device_version: str
    lifecycle_stage: TechnicalFileLifecycle = TechnicalFileLifecycle.DRAFT
    sections: List[TechnicalFileSectionEntity] = field(default_factory=list)
    organization_id: Optional[str] = None
    created_by: Optional[str] = None

    def transition_to(self, new_stage: TechnicalFileLifecycle) -> None:
        """Perform a lifecycle state transition, raising ValueError if invalid."""
        allowed = LIFECYCLE_TRANSITIONS.get(self.lifecycle_stage, set())
        if new_stage not in allowed:
            raise ValueError(
                f"Cannot transition from '{self.lifecycle_stage}' to '{new_stage}'. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )
        self.lifecycle_stage = new_stage

    def required_sections(self) -> List[str]:
        """Return the list of required section types for this regulatory type."""
        if self.regulatory_type == RegulatoryType.FDA_510K:
            return FDA_510K_SECTIONS
        if self.regulatory_type == RegulatoryType.EU_MDR:
            return EU_MDR_SECTIONS
        # BOTH: union of all sections
        return sorted(set(FDA_510K_SECTIONS) | set(EU_MDR_SECTIONS))

    def missing_sections(self) -> List[str]:
        """Return required section types not yet present."""
        present = {s.section_type for s in self.sections}
        return [s for s in self.required_sections() if s not in present]

    def completeness_score(self) -> float:
        """Return 0.0–1.0 based on how many required sections are present."""
        required = self.required_sections()
        if not required:
            return 1.0
        present = {s.section_type for s in self.sections}
        found = sum(1 for s in required if s in present)
        return found / len(required)

    def is_ready_to_submit(self) -> bool:
        """True when all required sections are present and lifecycle is DRAFT."""
        return (
            self.lifecycle_stage == TechnicalFileLifecycle.DRAFT
            and len(self.missing_sections()) == 0
        )


def auto_generate_sections(
    regulatory_type: RegulatoryType,
    product_name: str,
    device_version: str,
    metadata: Optional[Dict] = None,
) -> List[TechnicalFileSectionEntity]:
    """
    Generate placeholder sections for the given regulatory type.

    Each section contains a clearly marked auto-generated stub so authors
    know which fields need to be filled in before submission.
    """
    metadata = metadata or {}

    if regulatory_type == RegulatoryType.FDA_510K:
        section_types = FDA_510K_SECTIONS
    elif regulatory_type == RegulatoryType.EU_MDR:
        section_types = EU_MDR_SECTIONS
    else:
        section_types = sorted(set(FDA_510K_SECTIONS) | set(EU_MDR_SECTIONS))

    sections = []
    for i, section_type in enumerate(section_types):
        readable = section_type.replace("_", " ").title()
        sections.append(TechnicalFileSectionEntity(
            section_type=section_type,
            content=(
                f"[AUTO-GENERATED] {readable} for {product_name} v{device_version}. "
                "Replace this placeholder with actual regulatory content before submission."
            ),
            order_index=i,
            auto_generated=True,
        ))
    return sections

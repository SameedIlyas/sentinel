"""6-level data classification with PHI detection and access policy enforcement."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Set

from policy_engine.infrastructure.security.phi_redaction import PHIRedactionEngine, PHIFinding
from policy_engine.models.user import UserRole


class ClassificationLevel(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    PHI = "PHI"
    PII = "PII"
    PHI_RESTRICTED = "PHI_RESTRICTED"


# Keywords that escalate PHI classification to RESTRICTED
RESTRICTED_KEYWORDS: Set[str] = {
    "mental health",
    "depression",
    "anxiety",
    "schizophrenia",
    "bipolar",
    "substance abuse",
    "addiction",
    "alcohol",
    "drug",
    "hiv",
    "aids",
    "genetic",
    "dna",
    "chromosome",
    "minor",
    "pediatric",
    "adolescent",
}

# Roles allowed at each classification level
_ACCESS_POLICY = {
    ClassificationLevel.PUBLIC: set(UserRole),
    ClassificationLevel.INTERNAL: set(UserRole),
    ClassificationLevel.CONFIDENTIAL: {
        UserRole.SYSTEM_ADMIN,
        UserRole.ORG_ADMIN,
        UserRole.CMIO,
        UserRole.DATA_SCIENTIST,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.ANALYST,
    },
    ClassificationLevel.PHI: {
        UserRole.SYSTEM_ADMIN,
        UserRole.ORG_ADMIN,
        UserRole.CMIO,
        UserRole.DATA_SCIENTIST,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.CLINICAL_USER,
        UserRole.ANALYST,
    },
    ClassificationLevel.PII: {
        UserRole.SYSTEM_ADMIN,
        UserRole.ORG_ADMIN,
        UserRole.CMIO,
        UserRole.DATA_SCIENTIST,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.ANALYST,
    },
    ClassificationLevel.PHI_RESTRICTED: {
        UserRole.SYSTEM_ADMIN,
        UserRole.CMIO,
    },
}


@dataclass
class DataClassification:
    level: ClassificationLevel
    confidence: float
    reasons: List[str] = field(default_factory=list)
    phi_findings: List[PHIFinding] = field(default_factory=list)


class DataClassifier:
    """Classifies text into one of 6 sensitivity levels."""

    def __init__(self) -> None:
        self._engine = PHIRedactionEngine()

    def classify(self, text: str) -> DataClassification:
        if not text or not text.strip():
            return DataClassification(level=ClassificationLevel.PUBLIC, confidence=1.0)

        result = self._engine.redact(text)
        findings = result.findings
        phi_types = {f.phi_type for f in findings}
        text_lower = text.lower()

        if not findings:
            return DataClassification(
                level=ClassificationLevel.PUBLIC,
                confidence=0.9,
                reasons=["No PHI/PII identifiers detected"],
            )

        # Check for restricted trigger keywords combined with PHI findings
        has_restricted_keyword = any(kw in text_lower for kw in RESTRICTED_KEYWORDS)
        if findings and has_restricted_keyword:
            return DataClassification(
                level=ClassificationLevel.PHI_RESTRICTED,
                confidence=0.95,
                reasons=["PHI found with sensitive health context keywords"],
                phi_findings=findings,
            )

        # SSN, MRN, account numbers, NPI, DEA → PHI
        phi_types_high = {"SSN", "MRN", "HEALTH_PLAN_NUMBER", "NPI", "DEA_NUMBER"}
        if phi_types & phi_types_high:
            return DataClassification(
                level=ClassificationLevel.PHI,
                confidence=0.95,
                reasons=[
                    f"High-confidence PHI detected: {phi_types & phi_types_high}"
                ],
                phi_findings=findings,
            )

        # Other identifiers → PII
        return DataClassification(
            level=ClassificationLevel.PII,
            confidence=0.8,
            reasons=[f"PII identifiers detected: {phi_types}"],
            phi_findings=findings,
        )

    @staticmethod
    def enforce_access_policy(
        classification: DataClassification, user_role: UserRole
    ) -> bool:
        allowed_roles = _ACCESS_POLICY.get(classification.level, set())
        return user_role in allowed_roles

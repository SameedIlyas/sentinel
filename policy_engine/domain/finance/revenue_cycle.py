"""Revenue Cycle Integrity domain logic — pure Python."""
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional


BUNDLE_RULES: Dict[FrozenSet, str] = {
    frozenset(["99213", "99214"]): "99215",
    frozenset(["20610", "20611"]): "20612",
}


@dataclass
class RevenueFindings:
    finding_type: str
    severity: str  # low/medium/high/critical
    description: str
    affected_codes: List[str]
    estimated_overbilling: Optional[float]


@dataclass
class AuditResult:
    claim_id: str
    risk_score: float
    findings: List[RevenueFindings] = field(default_factory=list)
    status: str = "clean"


def detect_upcoding(billed_code: str, billed_amount: float, benchmark: dict) -> bool:
    """Returns True if billed_amount > p90_amount benchmark."""
    return billed_amount > benchmark.get("p90_amount", float("inf"))


def detect_unbundling(procedure_codes: list) -> List[str]:
    """Check if component codes are billed separately when a bundle code should be used."""
    warnings = []
    codes_set = set(procedure_codes)
    for component_set, bundle_code in BUNDLE_RULES.items():
        if component_set.issubset(codes_set):
            warnings.append(
                f"Possible unbundling: codes {sorted(component_set)} should use bundle code {bundle_code}"
            )
    return warnings


def detect_modifier_abuse(modifiers: list, procedure_codes: list) -> List[str]:
    """Flag suspicious modifier usage patterns."""
    warnings = []
    modifiers_set = set(modifiers)

    # Modifier 59: distinct procedural service — suspicious if duplicate procedure codes
    if "59" in modifiers_set:
        if len(procedure_codes) != len(set(procedure_codes)):
            warnings.append(
                "Modifier 59 (distinct procedural service) used with duplicate procedure codes"
            )

    # Modifier 25: significant separate E/M — suspicious if used multiple times (count in list)
    if modifiers.count("25") > 1:
        warnings.append(
            "Modifier 25 (significant separate E/M service) appears more than once"
        )

    # Modifier 76/77: repeat procedure — flag for review
    if "76" in modifiers_set or "77" in modifiers_set:
        warnings.append(
            "Modifier 76/77 (repeat procedure) detected — verify clinical documentation"
        )

    return warnings


def compute_risk_score(findings: List[RevenueFindings]) -> float:
    """Compute risk score 1-100 based on findings."""
    SEVERITY_WEIGHTS = {"critical": 30, "high": 20, "medium": 10, "low": 5}
    score = sum(SEVERITY_WEIGHTS.get(f.severity, 0) for f in findings)
    if findings:
        return float(min(100, max(1, score)))
    return 1.0

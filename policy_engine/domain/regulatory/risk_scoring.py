"""Risk Scoring Engine domain — proprietary formula per PRD.

Formula:
  Total Risk = (Severity Score × Exposure Score) + Regulatory Penalty Weight

Severity Score   = mean of 5 factors (model_confidence is INVERTED)
Exposure Score   = mean of 4 factors
Regulatory Penalty = sum(applicable USD penalties) / 25_000

Total Risk clamped to [1.0, 100.0].
"""
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Regulatory penalty table (USD per violation type)
# ---------------------------------------------------------------------------

REGULATORY_PENALTIES_USD = {
    "hipaa": 50_000,
    "fda_samd": 100_000,
    "cms_false_claims": 75_000,
    "onc_hti1": 25_000,
}

# Normalisation divisor: 25_000 USD → 1 unit on the 0–10 penalty scale
PENALTY_NORMALISATION_DIVISOR = 25_000

# Risk level thresholds
CRITICAL_THRESHOLD = 75.0
HIGH_THRESHOLD = 50.0
MEDIUM_THRESHOLD = 25.0


# ---------------------------------------------------------------------------
# Factor dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SeverityFactors:
    """
    5 clinical severity factors, each in [1.0, 10.0].

    NOTE: model_confidence is INVERTED when computing the score — a high
    confidence model contributes LOW severity (10 - model_confidence).
    """
    patient_safety_impact: float
    data_sensitivity: float
    model_confidence: float  # higher = less severe, inverted in scoring
    bias_magnitude: float
    drift_magnitude: float


@dataclass
class ExposureFactors:
    """4 operational exposure factors, each in [1.0, 10.0]."""
    patient_volume: float
    decision_frequency: float
    automation_level: float
    data_access_breadth: float


@dataclass
class RegulatoryFlags:
    """Boolean flags indicating which regulatory violations apply."""
    hipaa: bool = False
    fda_samd: bool = False
    cms_false_claims: bool = False
    onc_hti1: bool = False


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_factor(name: str, value: float) -> None:
    """
    Raise ValueError if a factor value is outside [1.0, 10.0].

    Used to validate request inputs before computing scores.
    """
    if value < 1.0 or value > 10.0:
        raise ValueError(
            f"Factor '{name}' value {value!r} is out of range [1.0, 10.0]"
        )


# ---------------------------------------------------------------------------
# Score computation functions
# ---------------------------------------------------------------------------


def compute_severity_score(factors: SeverityFactors) -> float:
    """
    Severity Score = mean of 5 factors.

    model_confidence is inverted: (10 - model_confidence).
    A perfectly confident model (10) contributes 0 severity on that axis;
    a zero-confidence model (1 → inverted=9) contributes near-maximum severity.
    """
    inverted_confidence = 10.0 - factors.model_confidence
    values = [
        factors.patient_safety_impact,
        factors.data_sensitivity,
        inverted_confidence,
        factors.bias_magnitude,
        factors.drift_magnitude,
    ]
    return sum(values) / len(values)


def compute_exposure_score(factors: ExposureFactors) -> float:
    """Exposure Score = mean of 4 operational exposure factors."""
    values = [
        factors.patient_volume,
        factors.decision_frequency,
        factors.automation_level,
        factors.data_access_breadth,
    ]
    return sum(values) / len(values)


def compute_regulatory_penalty(
    flags: RegulatoryFlags,
    multiplier: float = 1.0,
) -> float:
    """
    Compute regulatory penalty weight.

    Sum applicable USD penalties, divide by PENALTY_NORMALISATION_DIVISOR
    to produce a value on the 0–10 scale, then apply the org multiplier.

    With all four flags active: (50k+100k+75k+25k)/25k = 10.0
    """
    raw_usd = 0
    if flags.hipaa:
        raw_usd += REGULATORY_PENALTIES_USD["hipaa"]
    if flags.fda_samd:
        raw_usd += REGULATORY_PENALTIES_USD["fda_samd"]
    if flags.cms_false_claims:
        raw_usd += REGULATORY_PENALTIES_USD["cms_false_claims"]
    if flags.onc_hti1:
        raw_usd += REGULATORY_PENALTIES_USD["onc_hti1"]
    return (raw_usd / PENALTY_NORMALISATION_DIVISOR) * multiplier


def compute_total_risk(
    severity_score: float,
    exposure_score: float,
    regulatory_penalty: float,
) -> float:
    """
    Total Risk = (Severity Score × Exposure Score) + Regulatory Penalty Weight

    Clamped to [1.0, 100.0].
    """
    raw = (severity_score * exposure_score) + regulatory_penalty
    return max(1.0, min(100.0, raw))


def risk_level_from_score(score: float) -> str:
    """Map a numeric Total Risk score to a human-readable level string."""
    if score >= CRITICAL_THRESHOLD:
        return "critical"
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"

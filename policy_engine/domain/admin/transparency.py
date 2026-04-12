"""Transparency Portal domain logic — pure Python (ONC HTI-1)."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class TransparencyRecord:
    model_name: str
    model_version: str
    algorithm_description: str
    plain_language_summary: str
    evidence_base: str
    intended_population: str
    known_limitations: str
    performance_summary: Dict = field(default_factory=dict)
    bias_considerations: Optional[str] = None
    regulatory_status: Optional[str] = None


def validate_record(record: TransparencyRecord) -> List[str]:
    """Return list of validation errors. Empty = valid."""
    errors = []
    if not record.plain_language_summary:
        errors.append("plain_language_summary is required")
    elif len(record.plain_language_summary) < 50:
        errors.append("plain_language_summary must be at least 50 characters")
    if not record.intended_population:
        errors.append("intended_population is required")
    if not record.known_limitations:
        errors.append("known_limitations is required")
    return errors


def generate_version_snapshot(record: TransparencyRecord) -> dict:
    """Generate a versioned snapshot dict of a transparency record."""
    return {
        "model_name": record.model_name,
        "model_version": record.model_version,
        "algorithm_description": record.algorithm_description,
        "plain_language_summary": record.plain_language_summary,
        "evidence_base": record.evidence_base,
        "intended_population": record.intended_population,
        "known_limitations": record.known_limitations,
        "performance_summary": record.performance_summary,
        "bias_considerations": record.bias_considerations,
        "regulatory_status": record.regulatory_status,
    }

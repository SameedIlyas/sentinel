"""Bias audit domain logic — pure Python math, no ML framework required."""
from dataclasses import dataclass
from typing import Dict, List, Optional
import math


def disparate_impact_ratio(group_rate: float, reference_rate: float) -> float:
    """Compute disparate impact ratio (group / reference). Returns 0.0 if reference is 0."""
    if reference_rate == 0.0:
        return 0.0
    return group_rate / reference_rate


def equal_opportunity_difference(tpr_group: float, tpr_reference: float) -> float:
    """TPR(group) - TPR(reference). Negative means group is disadvantaged."""
    return tpr_group - tpr_reference


def demographic_parity_difference(positive_rate_group: float, positive_rate_reference: float) -> float:
    """P(positive|group) - P(positive|reference)."""
    return positive_rate_group - positive_rate_reference


@dataclass
class BiasAuditResult:
    subgroup: str
    metric_name: str
    metric_value: float
    reference_value: float
    disparity_ratio: float
    passes_80_percent_rule: bool
    threshold_used: float = 0.8


def run_bias_audit(
    predictions: List[int],
    labels: List[int],
    groups: Dict[str, List],
    reference_group: Optional[str] = None,
) -> List[BiasAuditResult]:
    """
    Run bias audit across all subgroups.

    Args:
        predictions: Model predictions (0/1)
        labels: Ground truth labels (0/1)
        groups: Dict of group_type -> list of group values per sample
        reference_group: Reference group name; if None, use highest positive rate

    Returns list of BiasAuditResult for each unique subgroup value.
    """
    results = []

    for group_type, group_values in groups.items():
        # Get unique group values
        unique_vals = list(set(group_values))

        # Compute positive rates per group
        group_rates = {}
        for val in unique_vals:
            indices = [i for i, g in enumerate(group_values) if g == val]
            if not indices:
                continue
            pos_rate = sum(predictions[i] for i in indices) / len(indices)
            group_rates[val] = pos_rate

        if not group_rates:
            continue

        # Reference = group with highest positive rate (most favored)
        ref_val = (
            reference_group
            if reference_group in group_rates
            else max(group_rates, key=group_rates.get)
        )
        ref_rate = group_rates[ref_val]

        for val, rate in group_rates.items():
            ratio = disparate_impact_ratio(rate, ref_rate)
            results.append(BiasAuditResult(
                subgroup=f"{group_type}:{val}",
                metric_name="disparate_impact_ratio",
                metric_value=rate,
                reference_value=ref_rate,
                disparity_ratio=ratio,
                passes_80_percent_rule=ratio >= 0.8,
            ))

    return results

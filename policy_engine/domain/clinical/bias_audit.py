"""Bias audit domain logic — pure Python math, no ML framework required.

Tier 2 Sprint 3 expands the existing demographic-parity audit with
equalized-odds metrics (TPR + FPR per subgroup) so the audit produces
Fairlearn-equivalent results without pulling Fairlearn as a dependency.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


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


def confusion_rates(
    predictions: List[int],
    labels: List[int],
    indices: List[int],
) -> Tuple[float, float]:
    """Compute (TPR, FPR) over the given index subset.

    Returns (0.0, 0.0) when the group is empty or has no positives/negatives.
    """
    if not indices:
        return 0.0, 0.0
    tp = fp = fn = tn = 0
    for i in indices:
        pred = predictions[i]
        label = labels[i]
        if pred == 1 and label == 1:
            tp += 1
        elif pred == 1 and label == 0:
            fp += 1
        elif pred == 0 and label == 1:
            fn += 1
        else:
            tn += 1
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    return tpr, fpr


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
    *,
    include_equalized_odds: bool = True,
) -> List[BiasAuditResult]:
    """
    Run bias audit across all subgroups.

    Args:
        predictions: Model predictions (0/1)
        labels: Ground truth labels (0/1)
        groups: Dict of group_type -> list of group values per sample
        reference_group: Reference group name; if None, use highest positive rate
        include_equalized_odds: Also emit TPR / FPR ratio rows per subgroup

    Returns a list of BiasAuditResult — at minimum one disparate-impact row per
    subgroup, plus (when include_equalized_odds=True) one TPR-ratio and one
    FPR-ratio row per subgroup. The 4/5ths-rule check applies to all ratios.
    """
    results: List[BiasAuditResult] = []

    for group_type, group_values in groups.items():
        unique_vals = list(set(group_values))

        # Compute positive rates per group + index lists
        group_indices: Dict = {}
        group_pos_rates: Dict = {}
        for val in unique_vals:
            indices = [i for i, g in enumerate(group_values) if g == val]
            if not indices:
                continue
            group_indices[val] = indices
            group_pos_rates[val] = (
                sum(predictions[i] for i in indices) / len(indices)
            )

        if not group_pos_rates:
            continue

        # Reference = group with highest positive rate (most favored), unless overridden
        ref_val = (
            reference_group
            if reference_group in group_pos_rates
            else max(group_pos_rates, key=group_pos_rates.get)
        )
        ref_rate = group_pos_rates[ref_val]
        ref_tpr, ref_fpr = confusion_rates(
            predictions, labels, group_indices[ref_val]
        )

        for val, rate in group_pos_rates.items():
            ratio = disparate_impact_ratio(rate, ref_rate)
            results.append(BiasAuditResult(
                subgroup=f"{group_type}:{val}",
                metric_name="disparate_impact_ratio",
                metric_value=rate,
                reference_value=ref_rate,
                disparity_ratio=ratio,
                passes_80_percent_rule=ratio >= 0.8,
            ))

            if not include_equalized_odds:
                continue

            tpr, fpr = confusion_rates(predictions, labels, group_indices[val])

            tpr_ratio = (tpr / ref_tpr) if ref_tpr > 0 else 0.0
            results.append(BiasAuditResult(
                subgroup=f"{group_type}:{val}",
                metric_name="equalized_odds_tpr_ratio",
                metric_value=tpr,
                reference_value=ref_tpr,
                disparity_ratio=tpr_ratio,
                passes_80_percent_rule=tpr_ratio >= 0.8,
            ))

            # FPR ratio: lower-is-better. Pass if both <= 0 OR ratio <= 1.25 (inverse 4/5ths).
            if ref_fpr == 0.0:
                fpr_ratio = 0.0 if fpr == 0.0 else float("inf")
                passes_fpr = (fpr == 0.0)
            else:
                fpr_ratio = fpr / ref_fpr
                # Inverse 4/5ths rule for FPR: ratio in [0.8, 1.25] is fair
                passes_fpr = 0.8 <= fpr_ratio <= 1.25
            results.append(BiasAuditResult(
                subgroup=f"{group_type}:{val}",
                metric_name="equalized_odds_fpr_ratio",
                metric_value=fpr,
                reference_value=ref_fpr,
                disparity_ratio=(
                    fpr_ratio if fpr_ratio != float("inf") else 999.0
                ),
                passes_80_percent_rule=passes_fpr,
            ))

    return results

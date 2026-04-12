"""Clinical drift detection — pure Python + numpy statistical tests."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple
import math

try:
    import numpy as np
    _NUMPY = True
except ImportError:
    _NUMPY = False


class DriftSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class DriftMeasurement:
    psi_scores: Dict[str, float] = field(default_factory=dict)
    ks_scores: Dict[str, float] = field(default_factory=dict)
    drift_detected: bool = False
    magnitude: float = 0.0
    severity: DriftSeverity = DriftSeverity.LOW


def population_stability_index(expected: List[float], actual: List[float], buckets: int = 10) -> float:
    """
    Compute PSI between expected and actual distributions.
    PSI < 0.1: no drift, 0.1-0.2: moderate, >0.2: significant
    """
    if not expected or not actual:
        return 0.0

    if _NUMPY:
        exp_arr = np.array(expected, dtype=float)
        act_arr = np.array(actual, dtype=float)

        # Create buckets based on expected distribution
        min_val = float(min(exp_arr.min(), act_arr.min()))
        max_val = float(max(exp_arr.max(), act_arr.max()))

        if min_val == max_val:
            return 0.0

        bins = np.linspace(min_val, max_val, buckets + 1)
        exp_counts, _ = np.histogram(exp_arr, bins=bins)
        act_counts, _ = np.histogram(act_arr, bins=bins)
        exp_counts = list(exp_counts)
        act_counts = list(act_counts)
    else:
        # Pure Python fallback
        all_vals = expected + actual
        min_val, max_val = min(all_vals), max(all_vals)
        if min_val == max_val:
            return 0.0
        step = (max_val - min_val) / buckets
        exp_counts = [0] * buckets
        act_counts = [0] * buckets
        for v in expected:
            idx = min(int((v - min_val) / step), buckets - 1)
            exp_counts[idx] += 1
        for v in actual:
            idx = min(int((v - min_val) / step), buckets - 1)
            act_counts[idx] += 1

    exp_total = sum(exp_counts) or 1
    act_total = sum(act_counts) or 1

    psi = 0.0
    epsilon = 1e-10  # avoid log(0)
    for e, a in zip(exp_counts, act_counts):
        exp_pct = (e / exp_total) + epsilon
        act_pct = (a / act_total) + epsilon
        psi += (act_pct - exp_pct) * math.log(act_pct / exp_pct)

    return abs(psi)


def kolmogorov_smirnov_test(expected_samples: List[float], actual_samples: List[float]) -> Tuple[float, float]:
    """
    Two-sample KS test. Returns (statistic, p_value).
    p_value < 0.05 indicates drift.
    """
    if _NUMPY:
        try:
            from scipy import stats
            result = stats.ks_2samp(expected_samples, actual_samples)
            return float(result.statistic), float(result.pvalue)
        except ImportError:
            pass

    # Pure Python two-sample KS test approximation
    n1 = len(expected_samples)
    n2 = len(actual_samples)
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0

    # For identical samples, return (0.0, 1.0)
    if expected_samples == actual_samples:
        return 0.0, 1.0

    combined = sorted(set(list(expected_samples) + list(actual_samples)))

    def ecdf(samples, x):
        return sum(1 for s in samples if s <= x) / len(samples)

    ks_stat = max(abs(ecdf(expected_samples, x) - ecdf(actual_samples, x)) for x in combined)

    # Approximate p-value using Kolmogorov distribution
    n_eff = (n1 * n2) / (n1 + n2)
    lambda_val = ks_stat * math.sqrt(n_eff)

    if lambda_val == 0:
        return 0.0, 1.0

    # Approximation: p ~ 2 * sum_{k=1}^{inf} (-1)^{k+1} * exp(-2k^2*lambda^2)
    p_value = 0.0
    for k in range(1, 20):
        term = ((-1) ** (k + 1)) * math.exp(-2 * k * k * lambda_val * lambda_val)
        p_value += term
    p_value = max(0.0, min(1.0, 2 * p_value))

    return ks_stat, p_value


def performance_drift_detected(baseline_auroc: float, current_auroc: float, threshold: float = 0.05) -> bool:
    """Returns True if AUROC dropped by more than threshold."""
    return (baseline_auroc - current_auroc) > threshold


def severity_from_psi(psi: float) -> DriftSeverity:
    if psi < 0.1:
        return DriftSeverity.LOW
    elif psi < 0.2:
        return DriftSeverity.MEDIUM
    elif psi < 0.25:
        return DriftSeverity.HIGH
    else:
        return DriftSeverity.CRITICAL

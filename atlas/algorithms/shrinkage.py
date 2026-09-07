"""
Empirical Bayes Shrinkage Subsystem
Handles low-sample regional cartography smoothing and credible intervals.
Prevents small-sample anomalies (e.g., 2 votes = 100%) from distorting the atlas.
"""

from dataclasses import dataclass
from typing import Tuple, Dict, Any
import numpy as np
from scipy.stats import beta


@dataclass
class SmoothedCellEstimate:
    cell_id: str
    sample_size: int
    raw_rate: float
    smoothed_rate: float
    ci_lower: float
    ci_upper: float
    is_hatched: bool          # True if sample size < min_sample_threshold
    weight_data: float        # Relative weight assigned to observed data vs prior


class EmpiricalBayesShrinkage:
    """
    Beta-Binomial Empirical Bayes shrinkage estimator.
    Shrinks regional observations towards a global or continental prior.
    """

    def __init__(
        self,
        prior_mean: float = 0.25,
        prior_weight: float = 30.0,    # Pseudo-observations (alpha_0 + beta_0)
        min_sample_threshold: int = 30,
        confidence_level: float = 0.95,
    ):
        self.prior_mean = prior_mean
        self.prior_weight = prior_weight
        self.min_sample_threshold = min_sample_threshold
        self.confidence_level = confidence_level

        # Compute prior alpha and beta
        self.alpha_0 = prior_mean * prior_weight
        self.beta_0 = (1.0 - prior_mean) * prior_weight

    def estimate_cell(self, cell_id: str, k: int, n: int) -> SmoothedCellEstimate:
        """
        Estimate smoothed proportion and credible intervals for a cell.
        k: Count of positive endorsements (e.g., voted Option A)
        n: Total responses recorded in cell
        """
        if n <= 0:
            # Unobserved cell: revert entirely to prior
            alpha_post = self.alpha_0
            beta_post = self.beta_0
            raw_rate = 0.0
            smoothed_rate = self.prior_mean
            weight_data = 0.0
        else:
            alpha_post = self.alpha_0 + k
            beta_post = self.beta_0 + (n - k)
            raw_rate = k / n
            smoothed_rate = (k + self.alpha_0) / (n + self.prior_weight)
            weight_data = n / (n + self.prior_weight)

        # Compute Equal-Tailed Credible Interval
        tail = (1.0 - self.confidence_level) / 2.0
        ci_lower = float(beta.ppf(tail, alpha_post, beta_post))
        ci_upper = float(beta.ppf(1.0 - tail, alpha_post, beta_post))

        return SmoothedCellEstimate(
            cell_id=cell_id,
            sample_size=n,
            raw_rate=round(raw_rate, 4),
            smoothed_rate=round(smoothed_rate, 4),
            ci_lower=round(ci_lower, 4),
            ci_upper=round(ci_upper, 4),
            is_hatched=(n < self.min_sample_threshold),
            weight_data=round(weight_data, 4),
        )
